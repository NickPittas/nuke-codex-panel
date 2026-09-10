"""Shared harness client interface plus a JSONL subprocess base class."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

from PySide6 import QtCore


def resolve_binary(env_var: str, name: str, extra_paths: list[str] | None = None) -> str | None:
    """Resolve a harness binary without assuming the desktop-launched Nuke PATH.

    Precedence: Settings dialog override, env var, PATH, known install dirs.
    """
    override = QtCore.QSettings("nuke-codex-panel", "panel").value("binary/%s" % name, "")
    candidates = [str(override) if override else None, os.environ.get(env_var), shutil.which(name)]
    candidates.extend(extra_paths or [])
    return next((path for path in candidates if path and Path(path).is_file()), None)


def compact_summary(value, limit: int = 120) -> str:
    """One-line, length-capped rendering of tool args/results for the chat."""
    if isinstance(value, dict):
        try:
            value = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError):
            value = str(value)
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class HarnessClient(QtCore.QObject):
    """Uniform interface the panel talks to, one implementation per agent harness."""

    name = "base"
    label = "Base"
    env_var = ""

    status_changed = QtCore.Signal(str)
    ready_changed = QtCore.Signal(bool)
    error = QtCore.Signal(str)
    user_message = QtCore.Signal(str, list)
    turn_started = QtCore.Signal()
    message_delta = QtCore.Signal(str)
    thinking_delta = QtCore.Signal(str)
    # {"phase": "start"|"end", "id": str, "tool": str, "detail": str, "ok": bool}
    tool_event = QtCore.Signal(dict)
    # {"used", "window", "percent", "input", "cached", "output", "cost"}
    usage_changed = QtCore.Signal(dict)
    turn_completed = QtCore.Signal(str)
    # [{"id": "provider/model", "label": "Pretty name", "efforts": ["low", ...]}]
    models_changed = QtCore.Signal(list)

    def __init__(self, cwd: str, parent=None, bridge_path: str | None = None):
        super().__init__(parent)
        self.cwd = str(Path(cwd).resolve())
        self.bridge_path = bridge_path
        self.ready = False
        # Where harness session files live for this project (pi/omp use it).
        self.session_dir = None
        # True while the session was restored from a previous conversation; the
        # harness then tells the model not to continue pre-restore work.
        self._resuming = False

    def start(self):
        raise NotImplementedError

    def stop(self, restart: bool = False):
        raise NotImplementedError

    def restart(self):
        self.stop(restart=True)

    def send_turn(self, text: str, image_paths: list[str] | None = None) -> bool:
        raise NotImplementedError

    def interrupt(self):
        pass

    def session_state(self) -> dict:
        """Handle that lets a later run resume the same model-side session."""
        return {}

    def resume_session(self, state: dict):
        """Adopt a stored session handle; call before start()."""
        self._resuming = bool(state)

    def system_prompt(self) -> str:
        """Harness system prompt, plus a do-not-continue note after a restore."""
        from .nuke_mcp import NUKE_SYSTEM_PROMPT

        if not self._resuming:
            return NUKE_SYSTEM_PROMPT
        return (
            NUKE_SYSTEM_PROMPT
            + "\n\nThis session was restored from a previous conversation. Do not "
              "resume, continue, or redo any task from before the restore, even if "
              "it looks unfinished. Wait for the user's new instruction and act "
              "only on that."
        )

    def new_session(self):
        """Drop the current session so the model starts from empty context."""
        pass

    def set_model(self, model_id: str):
        pass

    def set_thinking(self, level: str):
        pass

    def _set_ready(self, value: bool):
        if self.ready == value:
            return
        self.ready = value
        self.ready_changed.emit(value)


class JsonlProcessClient(HarnessClient):
    """HarnessClient over a long-lived JSON-lines stdio subprocess."""

    binary_label = "agent"

    def __init__(self, cwd: str, parent=None, bridge_path: str | None = None):
        super().__init__(cwd, parent, bridge_path)
        self.process = QtCore.QProcess(self)
        self.process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.SeparateChannels)
        self.process.started.connect(self._on_started)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.errorOccurred.connect(self._on_process_error)
        self.process.finished.connect(self._on_finished)
        self._stdout_buffer = ""
        self._stderr_tail = ""
        self._next_id = 1
        self._callbacks = {}
        self._stopping = False
        self._restart_requested = False

    def resolve_program(self) -> str | None:
        raise NotImplementedError

    def launch_arguments(self) -> list[str]:
        raise NotImplementedError

    def launch_environment(self) -> dict[str, str] | None:
        # Pin this client to its own Nuke session's bridge: with several Nuke
        # instances open, "newest discovery file" would target the wrong one.
        if self.bridge_path:
            return {"NUKE_BRIDGE_FILE": self.bridge_path}
        return None

    def start(self):
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            return
        program = self.resolve_program()
        if not program:
            hint = " Set %s to its full path." % self.env_var if self.env_var else ""
            self._fail("%s executable not found on PATH.%s" % (self.binary_label, hint))
            return
        self._stopping = False
        self.status_changed.emit("Starting %s…" % self.label)
        self.process.setProgram(program)
        self.process.setArguments(self.launch_arguments())
        env = self.launch_environment()
        if env is not None:
            process_env = QtCore.QProcessEnvironment.systemEnvironment()
            for key, value in env.items():
                process_env.insert(key, value)
            self.process.setProcessEnvironment(process_env)
        self.process.setWorkingDirectory(self.cwd)
        self.process.start()

    def stop(self, restart: bool = False):
        self._stopping = True
        self._restart_requested = restart
        self._set_ready(False)
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning:
            if restart:
                self._stopping = False
                self._restart_requested = False
                QtCore.QTimer.singleShot(0, self.start)
            return
        self.process.terminate()
        QtCore.QTimer.singleShot(1000, self._kill_if_still_running)

    def _kill_if_still_running(self):
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self.process.kill()

    def _send(self, message: dict, callback=None):
        request_id = self._next_id
        self._next_id += 1
        message["id"] = request_id
        self._callbacks[request_id] = callback
        self._write(message)
        return request_id

    def _write(self, message: dict):
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning:
            self._fail("%s is not running" % self.label)
            return
        self.process.write((json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8"))

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
                self._fail("Invalid %s message: %s" % (self.label, exc))

    def _handle_message(self, message: dict):
        raise NotImplementedError

    def _dispatch_response(self, message: dict, error_text: str | None = None) -> bool:
        """Resolve a pending request callback. Returns False for unknown ids."""
        request_id = message.get("id")
        if request_id not in self._callbacks:
            return False
        callback = self._callbacks.pop(request_id)
        if error_text:
            self.status_changed.emit("%s request failed: %s" % (self.label, error_text))
            self.error.emit(error_text)
        elif callback is not None:
            callback(message)
        return True

    def _read_stderr(self):
        chunk = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        self._stderr_tail = (self._stderr_tail + chunk)[-4000:]
        self._on_stderr(chunk)

    def _on_stderr(self, chunk: str):
        pass

    def _on_started(self):
        pass

    def _on_process_error(self, error):
        if self._stopping:
            return
        self._read_stderr()
        detail = self._stderr_tail.strip().splitlines()
        suffix = (": " + detail[-1]) if detail else ""
        self._fail("%s process error: %s%s" % (self.label, error, suffix))

    def _on_finished(self, exit_code, _status):
        self._set_ready(False)
        self._callbacks.clear()
        if self._stopping:
            restart = self._restart_requested
            self._stopping = False
            self._restart_requested = False
            if restart:
                self.status_changed.emit("Restarting %s…" % self.label)
                QtCore.QTimer.singleShot(0, self.start)
            else:
                self.status_changed.emit("%s stopped" % self.label)
            return
        detail = self._stderr_tail.strip().splitlines()
        suffix = (": " + detail[-1]) if detail else ""
        self.status_changed.emit("%s stopped (exit %s)%s" % (self.label, exit_code, suffix))

    def _fail(self, message: str):
        self._set_ready(False)
        self.status_changed.emit(message)
        self.error.emit(message)


def encode_image(path: str) -> tuple[str, str]:
    """Return (mime_type, base64_data) for a local image path."""
    suffix = Path(path).suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp"}.get(suffix, "image/png")
    import base64

    return mime, base64.b64encode(Path(path).read_bytes()).decode("ascii")
