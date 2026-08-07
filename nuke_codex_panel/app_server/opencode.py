"""OpenCode backend: drives `opencode serve` over HTTP + Server-Sent Events.

Unlike codex (a long-lived stdio JSON-RPC process), OpenCode exposes a REST +
SSE server. This backend owns one `opencode serve` subprocess, creates one
session, streams assistant text from the `/event` SSE feed, and registers the
Nuke MCP server via `POST /mcp`. The panel-facing signal contract is unchanged.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from PySide6 import QtCore, QtNetwork

from .base import BackendClient
from .resolver import resolve

_DEVELOPER_INSTRUCTIONS = (
    "You are embedded in Foundry Nuke through the Nuke Codex Panel. "
    "Treat attached screenshots as current compositing context. Use the Nuke "
    "MCP tools to inspect the current comp, capture fresh visual evidence, and "
    "execute Python. execute_python is the primary unrestricted Nuke control "
    "surface; prefer concise Python over inventing many narrow actions. Verify "
    "visual changes with a fresh Viewer or Node Graph screenshot."
)

_URL_RE = re.compile(r"listening on (https?://\S+)")


class OpencodeBackend(BackendClient):
    """Owns one `opencode serve` subprocess and one session over HTTP/SSE."""

    backend_key = "opencode"
    display_name = "OpenCode"
    supports_images = True
    supports_model_select = True

    def __init__(self, cwd: str, parent=None, bridge_path: str | None = None):
        super().__init__(cwd, parent, bridge_path)
        self.sidecar_python = shutil.which("python3") or "/usr/bin/python3"
        self.nam = QtNetwork.QNetworkAccessManager(self)
        self.process = QtCore.QProcess(self)
        self.process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_serve_output)
        self.process.errorOccurred.connect(self._on_process_error)
        self.process.finished.connect(self._on_process_finished)
        self.base_url = None
        self.session_id = None
        self.event_reply = None
        self._serve_buffer = ""
        self._sse_buffer = ""
        self._stopping = False
        self._restart_requested = False
        self._in_turn = False
        self._abort_requested = False
        self._stderr_tail = ""
        self._model_id = None
        self._effort = None
        self._part_types = {}
        self._thinking_buffers = {}

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            return
        binary = resolve("opencode")
        if not binary:
            self._fail(
                "OpenCode executable not found. Set NUKE_OPENCODE_BIN or install opencode."
            )
            return
        self._stopping = False
        self.status_changed.emit("Starting OpenCode server…")
        self.process.setProgram(binary)
        self.process.setArguments(
            ["serve", "--hostname", "127.0.0.1", "--port", "0", "--print-logs"]
        )
        self.process.setWorkingDirectory(self.cwd)
        self.process.start()

    def stop(self, restart: bool = False):
        self._stopping = True
        self._restart_requested = restart
        self._set_ready(False)
        self._close_event_stream()
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning:
            if restart:
                self._stopping = False
                self._restart_requested = False
                QtCore.QTimer.singleShot(0, self.start)
            return
        self.process.terminate()
        QtCore.QTimer.singleShot(1500, self._kill_if_still_running)

    def restart(self):
        self.session_id = None
        self.base_url = None
        self._serve_buffer = ""
        self._sse_buffer = ""
        self._in_turn = False
        self._abort_requested = False
        self._clear_part_state()
        self.stop(restart=True)

    def _kill_if_still_running(self):
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self.process.kill()

    # -- serve output -> discover bound URL ---------------------------------
    def _read_serve_output(self):
        chunk = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._serve_buffer += chunk
        self._stderr_tail = (self._stderr_tail + chunk)[-4000:]
        if self.base_url is None:
            match = _URL_RE.search(self._serve_buffer)
            if match:
                self.base_url = match.group(1)
                self._create_session()

    # -- HTTP helpers -------------------------------------------------------
    def _post(self, path: str, payload: dict, on_finished, fatal: bool = False):
        if not self.base_url:
            self._fail("OpenCode server is not up")
            return
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(self.base_url + path))
        request.setHeader(
            QtNetwork.QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json"
        )
        reply = self.nam.post(request, json.dumps(payload).encode("utf-8"))
        reply.finished.connect(lambda: self._on_reply(reply, on_finished, fatal))

    def _get(self, path: str, on_finished):
        if not self.base_url:
            self.error.emit("OpenCode server is not up")
            on_finished(None)
            return
        reply = self.nam.get(QtNetwork.QNetworkRequest(QtCore.QUrl(self.base_url + path)))
        reply.finished.connect(lambda: self._on_get_reply(reply, on_finished))

    def _on_get_reply(self, reply, on_finished):
        error = reply.error()
        body = bytes(reply.readAll()).decode("utf-8", errors="replace")
        message = reply.errorString()
        reply.deleteLater()
        if error != QtNetwork.QNetworkReply.NetworkError.NoError:
            self.error.emit("OpenCode model request failed: %s" % message)
            on_finished(None)
            return
        on_finished(body)

    def _on_reply(self, reply, on_finished, fatal):
        status = reply.attribute(QtNetwork.QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        error = reply.error()
        body = bytes(reply.readAll()).decode("utf-8", errors="replace")
        reply.deleteLater()
        if error != QtNetwork.QNetworkReply.NetworkError.NoError:
            message = "OpenCode request failed: %s" % reply.errorString()
            if self._in_turn:
                self._finish_turn("failed")
            if fatal:
                self._fail(message)
            else:
                self.status_changed.emit(message)
                self.error.emit(message)
            return
        if on_finished is not None:
            on_finished(body, status)

    # -- session + MCP setup --------------------------------------------------
    def _create_session(self):
        self.status_changed.emit("Creating OpenCode session…")
        self._post("/session", {"title": "Nuke Codex Panel"}, self._session_created, fatal=True)

    def _session_created(self, body, _status):
        try:
            self.session_id = (json.loads(body) or {}).get("id")
        except Exception as exc:
            self._fail("Invalid OpenCode session response: %s" % exc)
            return
        if not self.session_id:
            self._fail("OpenCode session had no id")
            return
        self._subscribe_events()
        self._register_mcp()

    def new_conversation(self):
        if self._in_turn or not self.base_url:
            return
        self._post("/session", {"title": "Nuke Codex Panel"}, self._new_session_created)

    def _new_session_created(self, body, _status):
        try:
            session_id = (json.loads(body) or {}).get("id")
        except Exception as exc:
            self.error.emit("Invalid OpenCode session response: %s" % exc)
            return
        if not session_id:
            self.error.emit("OpenCode session had no id")
            return
        self.session_id = session_id
        self._clear_part_state()
        self.status_changed.emit("New conversation")

    def _register_mcp(self):
        environment = {"PYTHONPATH": self.cwd}
        if self.bridge_path:
            environment["NUKE_CODEX_BRIDGE_FILE"] = self.bridge_path
        config = {
            "type": "local",
            "command": [self.sidecar_python, "-m", "nuke_codex_panel.mcp_server.server"],
            "environment": environment,
            "timeout": 300000,
            "enabled": True,
        }
        self._post("/mcp", {"name": "nuke", "config": config}, self._mcp_registered)

    def _mcp_registered(self, body, status):
        # The panel stays usable as chat even if Nuke tools failed to register.
        ok = status is None or int(status) < 400
        if not ok:
            self.status_changed.emit("OpenCode Nuke tools failed to register")
        # Contract: ready only after the MCP registration attempt completes.
        self._set_ready(True)
        self.status_changed.emit("OpenCode connected")

    # -- SSE subscription ----------------------------------------------------
    def _subscribe_events(self):
        self._close_event_stream()
        if not self.base_url:
            return
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(self.base_url + "/event"))
        self.event_reply = self.nam.get(request)
        self.event_reply.readyRead.connect(self._read_events)
        self.event_reply.finished.connect(self._on_event_stream_finished)

    def _close_event_stream(self):
        if self.event_reply is not None:
            try:
                self.event_reply.readyRead.disconnect(self._read_events)
            except (RuntimeError, TypeError):
                pass
            self.event_reply.abort()
            self.event_reply.deleteLater()
            self.event_reply = None

    def _read_events(self):
        if self.event_reply is None:
            return
        self._sse_buffer += bytes(self.event_reply.readAll()).decode("utf-8", errors="replace")
        while "\n" in self._sse_buffer:
            line, self._sse_buffer = self._sse_buffer.split("\n", 1)
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            try:
                self._handle_event(json.loads(payload))
            except Exception:
                continue

    def _on_event_stream_finished(self):
        self.event_reply = None

    def _handle_event(self, event: dict):
        props = event.get("properties") or {}
        part = props.get("part") or {}
        event_session_id = props.get("sessionID") or part.get("sessionID")
        if event_session_id and event_session_id != self.session_id:
            return
        etype = event.get("type")
        if etype == "message.part.delta" and props.get("field") == "text":
            part_id = props.get("partID")
            if self._part_types.get(part_id, "text") == "reasoning":
                text = self._thinking_buffers.get(part_id, "") + str(props.get("delta", ""))
                self._thinking_buffers[part_id] = text
                self.thinking_updated.emit(part_id, text)
            else:
                self.message_delta.emit(str(props.get("delta", "")))
        elif etype == "message.part.updated":
            part_id = part.get("id")
            part_type = part.get("type")
            if not part_id or not part_type:
                return
            self._part_types[part_id] = part_type
            if part_type == "reasoning":
                text = str(part.get("text", ""))
                self._thinking_buffers[part_id] = text
                self.thinking_updated.emit(part_id, text)
                if (part.get("time") or {}).get("end"):
                    self.thinking_completed.emit(part_id)
                    self._thinking_buffers.pop(part_id, None)
            elif part_type == "tool":
                state = part.get("state") or {}
                state_name = state.get("status") or state.get("state")
                status = {"pending": "running", "running": "running", "completed": "completed", "error": "error"}.get(state_name, "running")
                output = state.get("output") or state.get("error") or ""
                self.tool_updated.emit(part_id, str(part.get("tool", "tool")), status,
                                       json.dumps(state.get("input") or {}), str(output))
        elif etype == "session.idle":
            self._finish_turn("interrupted" if self._abort_requested else "completed")
            self._abort_requested = False
        elif etype == "session.error":
            err = props.get("error")
            message = err.get("message") if isinstance(err, dict) else (str(err) if err else None)
            self.error.emit(message or "OpenCode session error")
            self._finish_turn("failed")

    def _finish_turn(self, status: str):
        if not self._in_turn:
            return
        self._in_turn = False
        self.turn_completed.emit(status)

    def _clear_part_state(self):
        self._part_types.clear()
        self._thinking_buffers.clear()

    # -- model selection -----------------------------------------------------
    def request_models(self):
        self._get("/provider", self._models_received)

    def _models_received(self, body):
        if body is None:
            self.models_changed.emit([])
            return
        try:
            payload = json.loads(body)
            connected = set(payload.get("connected") or [])
            defaults = payload.get("default") or {}
            models = []
            for provider in payload.get("all") or []:
                provider_id = provider.get("id")
                if provider_id not in connected:
                    continue
                for model_id, model in (provider.get("models") or {}).items():
                    reasoning = (model.get("capabilities") or {}).get("reasoning")
                    models.append({
                        "id": "%s/%s" % (provider_id, model_id),
                        "name": model.get("name", model_id),
                        "efforts": sorted((model.get("variants") or {}).keys()) if reasoning else [],
                        "default_effort": None,
                        "is_default": defaults.get(provider_id) == model_id,
                    })
        except Exception:
            self.error.emit("Invalid OpenCode model response")
            self.models_changed.emit([])
            return
        self.models_changed.emit(models)

    def set_model(self, model_id: str | None, effort: str | None = None):
        self._model_id = model_id
        self._effort = effort

    # -- turns ---------------------------------------------------------------
    def send_turn(self, text: str, image_paths: list[str] | None = None) -> bool:
        text = text.strip()
        if not self.ready or not self.session_id or not text:
            return False
        images = [str(Path(p).resolve()) for p in (image_paths or [])]
        parts = [{"type": "text", "text": text}]
        for path in images:
            resolved = Path(path)
            parts.append(
                {
                    "type": "file",
                    "mime": "image/png",
                    "filename": resolved.name,
                    "url": "file://" + str(resolved),
                }
            )
        self.user_message.emit(text, images)
        self._in_turn = True
        self._clear_part_state()
        self.turn_started.emit()
        body = {"parts": parts, "system": _DEVELOPER_INSTRUCTIONS}
        if self._model_id:
            provider_id, model_id = self._model_id.split("/", 1)
            body["model"] = {"providerID": provider_id, "modelID": model_id}
        if self._effort:
            body["variant"] = self._effort
        self._post(
            "/session/%s/prompt_async" % self.session_id,
            body,
            self._prompt_posted,
        )
        return True

    def _prompt_posted(self, _body, _status):
        # prompt_async returns 204; the response streams over the SSE feed.
        pass

    def interrupt(self):
        if not self.session_id or not self._in_turn:
            return
        self._abort_requested = True
        self._post("/session/%s/abort" % self.session_id, {}, None)

    # -- process signals ------------------------------------------------------
    def _on_process_error(self, error):
        if self._stopping:
            return
        detail = self._stderr_tail.strip().splitlines()
        suffix = (": " + detail[-1]) if detail else ""
        self._fail("OpenCode process error: %s%s" % (error, suffix))

    def _on_process_finished(self, exit_code, _status):
        self._set_ready(False)
        self._close_event_stream()
        if self._stopping:
            restart = self._restart_requested
            self._stopping = False
            self._restart_requested = False
            if restart:
                self.status_changed.emit("Restarting OpenCode…")
                QtCore.QTimer.singleShot(0, self.start)
            else:
                self.status_changed.emit("OpenCode stopped")
            return
        detail = self._stderr_tail.strip().splitlines()
        suffix = (": " + detail[-1]) if detail else ""
        self.status_changed.emit("OpenCode stopped (exit %s)%s" % (exit_code, suffix))
