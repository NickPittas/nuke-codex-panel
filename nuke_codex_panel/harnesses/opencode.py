"""opencode harness client over the headless `opencode serve` HTTP + SSE API."""

from __future__ import annotations

import json
from pathlib import Path
import re

from PySide6 import QtCore, QtNetwork

from .base import HarnessClient, compact_summary, encode_image
from . import nuke_mcp


class OpencodeClient(HarnessClient):
    """Drive one opencode server process through QtNetwork REST + SSE."""

    name = "opencode"
    label = "Opencode"
    env_var = "NUKE_OPENCODE_BIN"
    binary_label = "opencode"

    def __init__(self, cwd: str, parent=None, bridge_path: str | None = None):
        super().__init__(cwd, parent, bridge_path)
        self.process = QtCore.QProcess(self)
        self.process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_server_output)
        self.process.errorOccurred.connect(self._on_process_error)
        self.process.finished.connect(self._on_process_finished)
        self._nam = QtNetwork.QNetworkAccessManager(self)
        self._base_url: str | None = None
        self.session_id: str | None = None
        self.model_id: str | None = None
        self.variant: str | None = None
        self._models: list[dict] = []
        self._turn_open = False
        self._part_types: dict[str, str] = {}
        self._tool_status: dict[str, str] = {}
        self._resume_session_id: str | None = None
        self._model_windows: dict[str, int] = {}
        self._sse_reply: QtNetwork.QNetworkReply | None = None
        self._sse_buffer = ""
        self._stopping = False
        self._restart_requested = False
        self._config_path = nuke_mcp.runtime_config_dir() / "opencode-nuke.json"

    def resolve_program(self) -> str | None:
        from .base import resolve_binary

        return resolve_binary(
            "NUKE_OPENCODE_BIN",
            "opencode",
            [str(Path.home() / ".opencode" / "bin" / "opencode")],
        )

    def start(self):
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            return
        program = self.resolve_program()
        if not program:
            self._fail(
                "opencode executable not found on PATH. Set %s to its full path."
                % self.env_var
            )
            return
        self._stopping = False
        self._turn_open = False
        nuke_mcp.write_opencode_config(self._config_path)
        self.status_changed.emit("Starting opencode server…")
        self.process.setProgram(program)
        self.process.setArguments(["serve", "--port", "0", "--hostname", "127.0.0.1"])
        env = QtCore.QProcessEnvironment.systemEnvironment()
        env.insert("OPENCODE_CONFIG", str(self._config_path))
        env.insert("OPENCODE_DISABLE_TUI", "1")
        if self.bridge_path:
            env.insert("NUKE_BRIDGE_FILE", self.bridge_path)
        self.process.setProcessEnvironment(env)
        self.process.setWorkingDirectory(self.cwd)
        self.process.start()

    def stop(self, restart: bool = False):
        self._stopping = True
        self._restart_requested = restart
        self._set_ready(False)
        self._close_sse()
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning:
            if restart:
                QtCore.QTimer.singleShot(0, self.start)
            return
        self.process.terminate()
        QtCore.QTimer.singleShot(1000, self._kill_if_still_running)

    def _kill_if_still_running(self):
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self.process.kill()

    # -- server startup ---------------------------------------------------

    def _read_server_output(self):
        chunk = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        match = re.search(r"listening on (http://127\.0\.0\.1:\d+)", chunk)
        if match and not self._base_url:
            self._base_url = match.group(1)
            self._bootstrap()

    def _bootstrap(self):
        self.status_changed.emit("Loading opencode models…")
        self._get("/config/providers", self._providers_loaded)
        if self._resume_session_id:
            self._get("/session", self._reuse_session)
        else:
            self._post("/session", {"title": "Nuke Panel"}, self._session_created)

    def _reuse_session(self, data):
        wanted = self._resume_session_id
        for entry in data or []:
            if entry.get("id") == wanted:
                self._session_created({"id": wanted})
                return
        self.status_changed.emit("Previous opencode session is gone; starting a new one")
        self._post("/session", {"title": "Nuke Panel"}, self._session_created)

    def _providers_loaded(self, data):
        providers = (data or {}).get("providers") or []
        models = []
        for provider in providers:
            provider_id = provider.get("id", "")
            for model_id, model in (provider.get("models") or {}).items():
                variants = sorted((model.get("variants") or {}).keys())
                models.append(
                    {
                        "id": "%s/%s" % (provider_id, model_id),
                        "label": model.get("name") or model_id,
                        "efforts": variants,
                        "window": (model.get("limit") or {}).get("context"),
                    }
                )
                if (model.get("limit") or {}).get("context"):
                    self._model_windows["%s/%s" % (provider_id, model_id)] = model["limit"][
                        "context"
                    ]
        self._models = models
        if models:
            self.models_changed.emit(models)
        if self.session_id:
            self._set_ready(True)

    def _session_created(self, data):
        self.session_id = (data or {}).get("id")
        if not self.session_id:
            self._fail("opencode started without returning a session id")
            return
        if self._models:
            self._set_ready(True)
        self.status_changed.emit("Opencode connected")
        self._subscribe_events()

    # -- events ------------------------------------------------------------

    def _subscribe_events(self):
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(self._base_url + "/event"))
        self._sse_reply = self._nam.get(request)
        self._sse_reply.readyRead.connect(self._read_sse)
        self._sse_reply.finished.connect(self._sse_finished)

    def _sse_finished(self):
        self._close_sse()

    def _close_sse(self):
        if self._sse_reply is not None:
            self._sse_reply.deleteLater()
            self._sse_reply = None

    def _read_sse(self):
        if self._sse_reply is None:
            return
        chunk = bytes(self._sse_reply.readAll()).decode("utf-8", errors="replace")
        self._sse_buffer += chunk
        while "\n" in self._sse_buffer:
            line, self._sse_buffer = self._sse_buffer.split("\n", 1)
            line = line.strip()
            if not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[5:].strip())
            except ValueError:
                continue
            self._handle_event(event)

    def _handle_event(self, event: dict):
        event_type = event.get("type", "")
        properties = event.get("properties") or {}
        if properties.get("sessionID") != self.session_id:
            return
        if event_type == "message.part.delta" and properties.get("field") == "text":
            self._open_turn()
            if self._part_types.get(properties.get("partID")) == "reasoning":
                self.thinking_delta.emit(properties.get("delta", ""))
            else:
                self.message_delta.emit(properties.get("delta", ""))
        elif event_type == "message.part.updated":
            part = properties.get("part") or {}
            if part.get("id"):
                self._part_types[part["id"]] = part.get("type", "")
            if part.get("type") == "tool":
                self._handle_tool_part(part)
        elif event_type == "message.updated":
            self._usage_updated(properties.get("info") or {})
        elif event_type == "session.idle":
            if self._turn_open:
                self._turn_open = False
                self.turn_completed.emit("completed")
        elif event_type == "session.error":
            self._turn_open = False
            self.error.emit(str(properties.get("error") or "opencode session error"))

    def _open_turn(self):
        if not self._turn_open:
            self._turn_open = True
            self.turn_started.emit()

    def _usage_updated(self, info: dict):
        if info.get("role") != "assistant":
            return
        tokens = info.get("tokens") or {}
        if not tokens:
            return
        cached = (tokens.get("cache") or {}).get("read") or 0
        used = tokens.get("total") or (tokens.get("input") or 0) + cached
        model_id = "%s/%s" % (info.get("providerID", ""), info.get("modelID", ""))
        window = self._model_windows.get(model_id) or self._model_windows.get(self.model_id or "")
        self.usage_changed.emit(
            {
                "used": used,
                "window": window,
                "percent": (used / window * 100) if used and window else None,
                "input": tokens.get("input"),
                "cached": cached or None,
                "output": tokens.get("output"),
                "cost": info.get("cost"),
            }
        )

    def session_state(self) -> dict:
        return {"session_id": self.session_id}

    def resume_session(self, state: dict):
        super().resume_session(state)
        self._resume_session_id = (state or {}).get("session_id") or None

    def new_session(self):
        self._resuming = False
        self.session_id = None
        self._turn_open = False
        if self._base_url:
            self._post("/session", {"title": "Nuke Panel"}, self._session_created)

    def _handle_tool_part(self, part: dict):
        state = part.get("state") or {}
        status = state.get("status", "")
        part_id = part.get("id") or ""
        if status == self._tool_status.get(part_id):
            return
        self._tool_status[part_id] = status
        self._open_turn()
        tool_id = part.get("callID") or part_id
        if status in ("pending", "running"):
            self.tool_event.emit(
                {
                    "phase": "start",
                    "id": tool_id,
                    "tool": part.get("tool", ""),
                    "detail": compact_summary(state.get("input")),
                }
            )
        elif status in ("completed", "error"):
            self.tool_event.emit(
                {
                    "phase": "end",
                    "id": tool_id,
                    "tool": part.get("tool", ""),
                    "ok": status == "completed",
                    "detail": compact_summary(
                        state.get("output") or state.get("error") or ""
                    ),
                }
            )

    # -- requests ----------------------------------------------------------

    def _get(self, path: str, callback):
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(self._base_url + path))
        request.setTransferTimeout(15000)
        reply = self._nam.get(request)
        reply.finished.connect(lambda target=reply, cb=callback: self._reply_done(target, cb))

    def _post(self, path: str, body: dict, callback=None):
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(self._base_url + path))
        request.setHeader(QtNetwork.QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setTransferTimeout(60000)
        payload = QtCore.QByteArray(json.dumps(body).encode("utf-8"))
        reply = self._nam.post(request, payload)
        if callback is not None:
            reply.finished.connect(lambda target=reply, cb=callback: self._reply_done(target, cb))
        return reply

    def _reply_done(self, reply, callback):
        reply.deleteLater()
        if reply.error() != QtNetwork.QNetworkReply.NetworkError.NoError:
            message = reply.errorString()
            self.status_changed.emit("Opencode request failed: %s" % message)
            self.error.emit(message)
            return
        raw = bytes(reply.readAll())
        try:
            data = json.loads(raw.decode("utf-8")) if raw.strip() else {}
        except ValueError:
            data = {}
        callback(data)

    def send_turn(self, text: str, image_paths: list[str] | None = None) -> bool:
        text = text.strip()
        if not self.ready or not self.session_id or not text:
            return False
        parts: list[dict] = [{"type": "text", "text": text}]
        for path in image_paths or []:
            mime, data = encode_image(path)
            parts.append(
                {
                    "type": "file",
                    "mime": mime,
                    "filename": Path(path).name,
                    "url": "data:%s;base64,%s" % (mime, data),
                }
            )
        body: dict = {"parts": parts, "system": self.system_prompt()}
        if self.model_id and "/" in self.model_id:
            provider, model = self.model_id.split("/", 1)
            body["model"] = {"providerID": provider, "modelID": model}
        if self.variant:
            body["variant"] = self.variant
        self.user_message.emit(text, list(image_paths or []))
        self._turn_open = False
        self._part_types.clear()
        self._tool_status.clear()
        self._post("/session/%s/message" % self.session_id, body)
        return True

    def interrupt(self):
        if self.session_id:
            self._post("/session/%s/abort" % self.session_id, {})

    def set_model(self, model_id: str):
        self.model_id = model_id or None

    def set_thinking(self, level: str):
        self.variant = level or None

    # -- process lifecycle ---------------------------------------------------

    def _on_process_error(self, error):
        if self._stopping:
            return
        self._fail("opencode process error: %s" % error)

    def _on_process_finished(self, exit_code, _status):
        self._set_ready(False)
        self._close_sse()
        if self._stopping:
            restart = self._restart_requested
            self._stopping = False
            self._restart_requested = False
            if restart:
                self.status_changed.emit("Restarting opencode…")
                QtCore.QTimer.singleShot(0, self.start)
            else:
                self.status_changed.emit("Opencode stopped")
            return
        self.status_changed.emit("Opencode stopped (exit %s)" % exit_code)

    def _fail(self, message: str):
        self._set_ready(False)
        self.status_changed.emit(message)
        self.error.emit(message)
