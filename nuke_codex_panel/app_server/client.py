"""Small asynchronous Codex App Server JSON-RPC client for Nuke's Qt loop."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys

from PySide6 import QtCore


def resolve_codex_binary() -> str | None:
    """Resolve Codex without assuming the desktop-launched Nuke PATH."""
    candidates = [
        os.environ.get("NUKE_CODEX_BIN"),
        shutil.which("codex"),
        str(Path.home() / ".npm-global" / "bin" / "codex"),
        str(Path.home() / ".local" / "bin" / "codex"),
    ]
    return next((path for path in candidates if path and Path(path).is_file()), None)


class CodexAppServerClient(QtCore.QObject):
    """Own one local app-server process and one persistent Codex thread."""

    status_changed = QtCore.Signal(str)
    ready_changed = QtCore.Signal(bool)
    user_message = QtCore.Signal(str, list)
    turn_started = QtCore.Signal()
    agent_message_started = QtCore.Signal(str, str)
    message_delta = QtCore.Signal(str)
    turn_completed = QtCore.Signal(str)
    error = QtCore.Signal(str)

    def __init__(self, cwd: str, parent=None, bridge_path: str | None = None):
        super().__init__(parent)
        self.cwd = str(Path(cwd).resolve())
        self.bridge_path = str(Path(bridge_path).resolve()) if bridge_path else None
        self.sidecar_python = shutil.which("python3") or "/usr/bin/python3"
        self.process = QtCore.QProcess(self)
        self.process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.SeparateChannels)
        self.process.started.connect(self._on_process_started)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.errorOccurred.connect(self._on_process_error)
        self.process.finished.connect(self._on_process_finished)
        self._stdout_buffer = ""
        self._stderr_tail = ""
        self._next_id = 1
        self._callbacks = {}
        self.thread_id = None
        self.turn_id = None
        self.ready = False
        self._stopping = False
        self._restart_requested = False

    def start(self):
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            return
        binary = resolve_codex_binary()
        if not binary:
            self._fail(
                "Codex executable not found. Set NUKE_CODEX_BIN or install codex on PATH."
            )
            return
        self._stopping = False
        self.status_changed.emit("Starting Codex App Server…")
        self.process.setProgram(binary)
        self.process.setArguments(["app-server"])
        self.process.setWorkingDirectory(self.cwd)
        self.process.start()

    def stop(self, restart: bool = False):
        self._stopping = True
        self._restart_requested = restart
        self._set_ready(False)
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning:
            if restart:
                self._restart_requested = False
                self._stopping = False
                QtCore.QTimer.singleShot(0, self.start)
            return
        self.process.terminate()
        QtCore.QTimer.singleShot(1000, self._kill_if_still_running)

    def restart(self):
        self.thread_id = None
        self.turn_id = None
        self._callbacks.clear()
        self._stdout_buffer = ""
        self._stderr_tail = ""
        self.stop(restart=True)

    def _kill_if_still_running(self):
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self.process.kill()

    def send_turn(self, text: str, image_paths: list[str] | None = None) -> bool:
        text = text.strip()
        if not self.ready or not self.thread_id or not text:
            return False
        images = [str(Path(path).resolve()) for path in (image_paths or [])]
        inputs = [{"type": "text", "text": text}]
        inputs.extend({"type": "localImage", "path": path} for path in images)
        self.user_message.emit(text, images)
        self._request(
            "turn/start",
            {
                "threadId": self.thread_id,
                "input": inputs,
                "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
                "approvalPolicy": "never",
            },
            self._turn_start_response,
        )
        return True

    def interrupt(self):
        if not self.thread_id or not self.turn_id:
            return
        self._request(
            "turn/interrupt",
            {"threadId": self.thread_id, "turnId": self.turn_id},
        )

    def _on_process_started(self):
        self.status_changed.emit("Initializing Codex…")
        self._request(
            "initialize",
            {
                "clientInfo": {
                    "name": "nuke_codex_panel",
                    "title": "Nuke Codex Panel",
                    "version": "0.1.0.dev0",
                }
            },
            self._initialized,
            fatal=True,
        )

    def _initialized(self, _result):
        self._notification("initialized", {})
        self.status_changed.emit("Starting conversation…")
        nuke_server = {
            "command": self.sidecar_python,
            "args": ["-m", "nuke_codex_panel.mcp_server.server"],
            "cwd": self.cwd,
            "startup_timeout_sec": 15,
            "tool_timeout_sec": 300,
        }
        if self.bridge_path:
            nuke_server["env"] = {"NUKE_CODEX_BRIDGE_FILE": self.bridge_path}
        self._request(
            "thread/start",
            {
                "cwd": self.cwd,
                "sandbox": "read-only",
                "approvalPolicy": "never",
                "ephemeral": False,
                "developerInstructions": (
                    "You are embedded in Foundry Nuke through the Nuke Codex Panel. "
                    "Treat attached screenshots as current compositing context. Use the Nuke "
                    "MCP tools to inspect the current comp, capture fresh visual evidence, and "
                    "execute Python. execute_python is the primary unrestricted Nuke control "
                    "surface; prefer concise Python over inventing many narrow actions. Verify "
                    "visual changes with a fresh Viewer or Node Graph screenshot."
                ),
                "config": {
                    "mcp_servers": {
                        "nuke": nuke_server
                    }
                },
            },
            self._thread_started,
            fatal=True,
        )

    def _thread_started(self, result):
        self.thread_id = (result or {}).get("thread", {}).get("id")
        if not self.thread_id:
            self._fail("Codex started without returning a thread id")
            return
        self._set_ready(True)
        self.status_changed.emit("Codex connected")

    def _turn_start_response(self, result):
        turn = (result or {}).get("turn", {})
        self.turn_id = turn.get("id") or self.turn_id

    def _request(self, method: str, params: dict, callback=None, fatal: bool = False):
        request_id = self._next_id
        self._next_id += 1
        self._callbacks[request_id] = (callback, fatal)
        self._write({"method": method, "id": request_id, "params": params})
        return request_id

    def _notification(self, method: str, params: dict):
        self._write({"method": method, "params": params})

    def _write(self, message: dict):
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning:
            self._fail("Codex App Server is not running")
            return
        payload = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
        self.process.write(payload)

    def _read_stdout(self):
        self._stdout_buffer += bytes(self.process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            if not line.strip():
                continue
            try:
                self._handle_message(json.loads(line))
            except Exception as exc:
                self._fail("Invalid App Server message: %s" % exc)

    def _read_stderr(self):
        chunk = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        self._stderr_tail = (self._stderr_tail + chunk)[-4000:]

    def _handle_message(self, message: dict):
        if os.environ.get("NUKE_CODEX_DEBUG"):
            print("NUKE_CODEX_EVENT", json.dumps(message, default=str), file=sys.stderr)
        if "id" in message and ("result" in message or "error" in message):
            callback, fatal = self._callbacks.pop(message["id"], (None, False))
            if "error" in message:
                error = message.get("error") or {}
                error_message = error.get("message") or str(error)
                if fatal:
                    self._fail(error_message)
                else:
                    self.status_changed.emit("Codex request failed: %s" % error_message)
                    self.error.emit(error_message)
            elif callback is not None:
                callback(message.get("result"))
            return

        method = message.get("method")
        params = message.get("params") or {}
        if "id" in message:
            # Codex asks the host to approve state-changing MCP tools. Accept only
            # our authenticated localhost server here; execute_python still reaches
            # the separate in-Nuke confirmation dialog (unless Trusted is enabled).
            if (
                method == "mcpServer/elicitation/request"
                and params.get("serverName") == "nuke"
                and (params.get("_meta") or {}).get("codex_approval_kind")
                == "mcp_tool_call"
            ):
                self._write(
                    {"id": message["id"], "result": {"action": "accept", "content": {}}}
                )
            else:
                self._write(
                    {
                        "id": message["id"],
                        "error": {
                            "code": -32601,
                            "message": "Nuke Codex Panel does not handle %s yet" % method,
                        },
                    }
                )
        elif method == "turn/started":
            self.turn_id = params.get("turn", {}).get("id")
            self.turn_started.emit()
        elif method == "item/started":
            item = params.get("item") or {}
            if item.get("type") == "agentMessage":
                self.agent_message_started.emit(
                    str(item.get("id", "")), str(item.get("phase", ""))
                )
        elif method == "item/agentMessage/delta":
            self.message_delta.emit(params.get("delta", ""))
        elif method == "turn/completed":
            turn = params.get("turn", {})
            self.turn_id = None
            self.turn_completed.emit(turn.get("status", "completed"))

    def _on_process_error(self, error):
        if self._stopping:
            return
        self._read_stderr()
        detail = self._stderr_tail.strip().splitlines()
        suffix = (": " + detail[-1]) if detail else ""
        self._fail("Codex process error: %s%s" % (error, suffix))

    def _on_process_finished(self, exit_code, _status):
        self._set_ready(False)
        if self._stopping:
            restart = self._restart_requested
            self._stopping = False
            self._restart_requested = False
            if restart:
                self.status_changed.emit("Restarting Codex…")
                QtCore.QTimer.singleShot(0, self.start)
            else:
                self.status_changed.emit("Codex stopped")
            return
        detail = self._stderr_tail.strip().splitlines()
        suffix = (": " + detail[-1]) if detail else ""
        self.status_changed.emit("Codex stopped (exit %s)%s" % (exit_code, suffix))

    def _set_ready(self, value: bool):
        if self.ready == value:
            return
        self.ready = value
        self.ready_changed.emit(value)

    def _fail(self, message: str):
        self._set_ready(False)
        self.status_changed.emit(message)
        self.error.emit(message)
