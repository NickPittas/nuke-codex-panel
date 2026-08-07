"""Claude Code backend: drives `claude -p` headlessly (process-per-turn).

Unlike codex/opencode (long-lived servers), Claude Code's headless mode is a
fresh subprocess per turn. Each turn spawns `claude -p <prompt>` streaming
newline-delimited JSON; the session id from `system/init`/`result` is reused via
`--resume` on the next turn. Cancellation is SIGTERM (clean abort, exit 143).

Images are not attachable inline in `-p` mode (supports_images=False); they are
referenced by absolute path and read via the Read tool.

NOTE: claude is not installed on this machine, so this adapter is built to-spec
from the official stream-json schema and is UNVERIFIED. Install claude
(`npm i -g @anthropic-ai/claude-code`) and run a turn to validate. Most likely
first-run adjustment: the `--allowedTools` specs if headless permission rules
block the nuke MCP tools or Read.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PySide6 import QtCore

from .base import BackendClient
from .resolver import resolve

_DEVELOPER_INSTRUCTIONS = (
    "You are embedded in Foundry Nuke through the Nuke Codex Panel. Use the Nuke "
    "MCP tools to inspect the current comp and execute Python; execute_python is "
    "the primary unrestricted Nuke control surface. Attached screenshots are "
    "given as absolute file paths — read them with the Read tool to view the "
    "current compositing context, and capture fresh visual evidence when you need "
    "to verify a change."
)


class ClaudeBackend(BackendClient):
    """Runs one `claude -p` subprocess per turn over NDJSON stdio."""

    backend_key = "claude"
    display_name = "Claude"
    supports_images = False  # path-reference only; no inline image input in -p

    def __init__(self, cwd: str, parent=None, bridge_path: str | None = None):
        super().__init__(cwd, parent, bridge_path)
        self.sidecar_python = shutil.which("python3") or "/usr/bin/python3"
        self.binary = None
        self.session_id = None
        self.process = None
        self._stdout_buffer = ""
        self._stderr_tail = ""
        self._stopping = False
        self._restart_requested = False
        self._in_turn = False
        self._cancel_requested = False

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        """Resolve the binary and mark ready; there is no server to start."""
        self.binary = resolve("claude")
        if not self.binary:
            self._fail(
                "Claude executable not found. Set NUKE_CLAUDE_BIN or install claude."
            )
            return
        self._stopping = False
        self._set_ready(True)
        self.status_changed.emit("Claude ready")

    def stop(self, restart: bool = False):
        self._stopping = True
        self._restart_requested = restart
        self._set_ready(False)
        if self.process is not None and self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self.process.terminate()
        else:
            self._on_stop_finished(restart)

    def restart(self):
        self.session_id = None
        self.stop(restart=True)

    def new_conversation(self):
        # Process-per-turn: dropping the session id starts the next turn fresh.
        if self._in_turn:
            return
        self.session_id = None
        self.status_changed.emit("New conversation")

    def _on_stop_finished(self, restart: bool):
        self._stopping = False
        if restart:
            QtCore.QTimer.singleShot(0, self.start)
        else:
            self.status_changed.emit("Claude stopped")

    # -- turns ---------------------------------------------------------------
    def send_turn(self, text: str, image_paths: list[str] | None = None) -> bool:
        text = text.strip()
        if not self.ready or not self.binary or not text or self._in_turn:
            return False
        prompt = self._build_prompt(text, image_paths or [])
        images = [str(Path(p).resolve()) for p in (image_paths or [])]
        self.user_message.emit(text, images)
        self._in_turn = True
        self._cancel_requested = False
        self.turn_started.emit()
        self._spawn_turn(prompt)
        return True

    def _build_prompt(self, text: str, image_paths: list[str]) -> str:
        parts = []
        if self.session_id is None:
            # First turn establishes Nuke context; --resume keeps it for later turns.
            parts.append(_DEVELOPER_INSTRUCTIONS)
        for path in image_paths:
            resolved = str(Path(path).resolve())
            parts.append("Attached screenshot (current compositing context): %s" % resolved)
        parts.append(text)
        return "\n\n".join(parts)

    def _spawn_turn(self, prompt: str):
        assert self.binary is not None  # guarded by send_turn (start() resolved it)
        args = [
            "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--mcp-config", self._mcp_config_json(),
            "--allowedTools", "mcp__nuke", "Read",
        ]
        if self.session_id:
            args += ["--resume", self.session_id]
        self._stdout_buffer = ""
        self._stderr_tail = ""
        self.process = QtCore.QProcess(self)
        self.process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.errorOccurred.connect(self._on_process_error)
        self.process.finished.connect(self._on_turn_finished)
        self.process.setProgram(self.binary)
        self.process.setArguments(args)
        self.process.setWorkingDirectory(self.cwd)
        self.process.start()

    def _mcp_config_json(self) -> str:
        env = {"PYTHONPATH": self.cwd}
        if self.bridge_path:
            env["NUKE_CODEX_BRIDGE_FILE"] = self.bridge_path
        return json.dumps(
            {
                "mcpServers": {
                    "nuke": {
                        "type": "stdio",
                        "command": self.sidecar_python,
                        "args": ["-m", "nuke_codex_panel.mcp_server.server"],
                        "env": env,
                    }
                }
            }
        )

    def interrupt(self):
        if not self._in_turn or self.process is None:
            return
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning:
            return
        self._cancel_requested = True
        self.process.terminate()  # SIGTERM: documented clean abort (exit 143)

    # -- stdio parsing ---------------------------------------------------------
    def _read_stdout(self):
        if self.process is None:
            return
        self._stdout_buffer += bytes(self.process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            if not line.strip():
                continue
            try:
                self._handle_message(json.loads(line))
            except Exception:
                continue

    def _read_stderr(self):
        if self.process is None:
            return
        chunk = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        self._stderr_tail = (self._stderr_tail + chunk)[-4000:]

    def _handle_message(self, message: dict):
        session = message.get("session_id")
        if session and not self.session_id:
            self.session_id = session
        mtype = message.get("type")
        if mtype == "stream_event":
            event = message.get("event") or {}
            delta = event.get("delta") or {}
            if event.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                self.message_delta.emit(str(delta.get("text", "")))
        elif mtype == "result":
            subtype = message.get("subtype")
            if subtype == "success":
                self._finish_turn("completed")
            else:
                if self._cancel_requested:
                    return  # let the finished handler emit "interrupted"
                errors = message.get("errors") or []
                self.error.emit("; ".join(str(e) for e in errors) or "Claude turn failed")
                self._finish_turn("failed")

    def _on_process_error(self, error):
        # FailedToStart emits errorOccurred but not finished; still end the turn.
        # terminate() also fires errorOccurred(Crashed) before finished — in
        # cancel/stop paths the finished handler owns the turn completion.
        if self._cancel_requested or self._stopping:
            return
        detail = self._stderr_tail.strip().splitlines()
        suffix = (": " + detail[-1]) if detail else ""
        self.error.emit("Claude process error: %s%s" % (error, suffix))
        self._finish_turn("failed")
        self._cleanup_process()
        if self._stopping:
            self._on_stop_finished(self._restart_requested)

    def _on_turn_finished(self, exit_code, _status):
        self._read_stdout()  # drain a result line still buffered in the pipe
        if self._cancel_requested:
            self._cancel_requested = False
            self._finish_turn("interrupted")
        elif self._in_turn:
            # Exited without a result event (crash or hard failure).
            detail = self._stderr_tail.strip().splitlines()
            if detail:
                self.error.emit("Claude exited (%s): %s" % (exit_code, detail[-1]))
            self._finish_turn("failed")
        self._cleanup_process()
        if self._stopping:
            self._on_stop_finished(self._restart_requested)

    def _cleanup_process(self):
        if self.process is not None:
            self.process.deleteLater()
            self.process = None

    def _finish_turn(self, status: str):
        if not self._in_turn:
            return
        self._in_turn = False
        self.turn_completed.emit(status)
