"""Authenticated localhost JSONL bridge running on Nuke's Qt main thread."""

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
import secrets
import tempfile

from PySide6 import QtCore, QtNetwork

from ..capture import capture_target
from ..tools import PythonExecutor, get_context


def runtime_directory() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return Path(base) / ("nuke-codex-panel-%s" % os.getuid())


class NukeBridgeServer(QtCore.QObject):
    """Serve Nuke operations without letting worker threads touch Nuke."""

    status_changed = QtCore.Signal(str)

    def __init__(self, approval_callback, parent=None):
        super().__init__(parent)
        self.approval_callback = approval_callback
        self.server = QtNetwork.QTcpServer(self)
        self.server.newConnection.connect(self._accept_connections)
        self.token = secrets.token_urlsafe(32)
        self.executor = PythonExecutor()
        self.buffers = {}
        self.discovery_path = None

    def start(self) -> bool:
        if self.server.isListening():
            return True
        if not self.server.listen(QtNetwork.QHostAddress.SpecialAddress.LocalHost, 0):
            self.status_changed.emit("Nuke bridge failed: %s" % self.server.errorString())
            return False
        directory = runtime_directory()
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        self.discovery_path = directory / ("session-%s.json" % os.getpid())
        record = {
            "pid": os.getpid(),
            "host": "127.0.0.1",
            "port": self.server.serverPort(),
            "token": self.token,
        }
        temporary = self.discovery_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.discovery_path)
        self.status_changed.emit("Nuke bridge ready on localhost")
        return True

    def stop(self):
        self.server.close()
        for socket in list(self.buffers):
            socket.disconnectFromHost()
        self.buffers.clear()
        if self.discovery_path:
            try:
                self.discovery_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _accept_connections(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.buffers[socket] = b""
            socket.readyRead.connect(lambda current=socket: self._read_socket(current))
            socket.disconnected.connect(lambda current=socket: self._drop_socket(current))

    def _drop_socket(self, socket):
        self.buffers.pop(socket, None)
        socket.deleteLater()

    def _read_socket(self, socket):
        buffer = self.buffers.get(socket, b"") + bytes(socket.readAll())
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                request = json.loads(line.decode("utf-8"))
                response = self._handle_request(request)
            except Exception as exc:
                response = {"success": False, "error": "%s: %s" % (type(exc).__name__, exc)}
            socket.write((json.dumps(response) + "\n").encode("utf-8"))
            socket.flush()
        self.buffers[socket] = buffer

    def _handle_request(self, request: dict) -> dict:
        if not hmac.compare_digest(str(request.get("token", "")), self.token):
            return {"success": False, "error": "Unauthorized Nuke bridge request"}
        method = request.get("method")
        params = request.get("params") or {}
        if method == "execute_python":
            code = str(params.get("code", ""))
            if not code.strip():
                return {"success": False, "error": "Python code is empty"}
            if not self.approval_callback(code):
                return {"success": False, "error": "Python execution denied by the user"}
            return self.executor.execute(
                code,
                undo=bool(params.get("undo", True)),
                label=str(params.get("label", "Codex Python")),
            )
        if method == "get_context":
            return {"success": True, "context": get_context(bool(params.get("include_nodes", True)))}
        if method == "capture_screenshot":
            path = capture_target(str(params.get("target", "viewer")))
            return {"success": True, "path": str(path)}
        return {"success": False, "error": "Unknown bridge method: %s" % method}
