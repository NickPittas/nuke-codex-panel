"""Claude Code harness client over the stream-json print protocol.

Untested against a live claude binary (not installed on the build machine);
the protocol follows the documented `claude -p --input-format stream-json
--output-format stream-json` behavior.
"""

from __future__ import annotations

from pathlib import Path

from .base import JsonlProcessClient, compact_summary, resolve_binary, encode_image
from . import nuke_mcp

KNOWN_MODELS = [
    {"id": "opus", "label": "Opus", "efforts": []},
    {"id": "sonnet", "label": "Sonnet", "efforts": []},
    {"id": "haiku", "label": "Haiku", "efforts": []},
]


class ClaudeClient(JsonlProcessClient):
    """One long-lived `claude` print process accepting streaming JSON turns."""

    name = "claude"
    label = "Claude"
    binary_label = "Claude"
    env_var = "NUKE_CLAUDE_BIN"

    def __init__(self, cwd: str, parent=None, bridge_path: str | None = None):
        super().__init__(cwd, parent, bridge_path)
        self.model_id: str | None = None
        self.session_id: str | None = None
        self._turn_open = False
        self._mcp_config_path = nuke_mcp.runtime_config_dir() / "claude-mcp.json"

    def resolve_program(self) -> str | None:
        return resolve_binary(
            "NUKE_CLAUDE_BIN",
            "claude",
            [str(Path.home() / ".claude" / "local" / "claude")],
        )

    def launch_arguments(self) -> list[str]:
        nuke_mcp.write_claude_mcp_config(self._mcp_config_path)
        args = [
            "-p",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--mcp-config", str(self._mcp_config_path),
            "--permission-mode", "bypassPermissions",
            "--append-system-prompt", self.system_prompt(),
        ]
        if self.model_id:
            args.extend(["--model", self.model_id])
        if self.session_id:
            args.extend(["--resume", self.session_id])
        return args

    def session_state(self) -> dict:
        return {"session_id": self.session_id}

    def resume_session(self, state: dict):
        super().resume_session(state)
        self.session_id = (state or {}).get("session_id") or None

    def new_session(self):
        self._resuming = False
        # The print process owns its session, so a fresh one needs a restart
        # without --resume.
        self.session_id = None
        if self.ready:
            self.restart()

    def start(self):
        self._turn_open = False
        super().start()

    def _handle_message(self, message: dict):
        kind = message.get("type")
        if kind == "system" and message.get("subtype") == "init":
            self.session_id = message.get("session_id") or self.session_id
            self.models_changed.emit([dict(model) for model in KNOWN_MODELS])
            self._set_ready(True)
            self.status_changed.emit("Claude connected")
        elif kind == "stream_event":
            self._handle_stream_event(message.get("event") or {})
        elif kind == "result":
            self._turn_open = False
            self._usage_updated(message)
            self.turn_completed.emit(str(message.get("subtype", "completed")))
        elif kind == "control_request":
            self._respond_control(message)
        elif kind == "error":
            self.error.emit(str(message.get("message", "Claude error")))

    def _handle_stream_event(self, event: dict):
        event_type = event.get("type")
        if event_type == "message_start" and not self._turn_open:
            self._turn_open = True
            self.turn_started.emit()
        elif event_type == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                self._turn_open = True
                self.tool_event.emit(
                    {
                        "phase": "start",
                        "id": block.get("id"),
                        "tool": block.get("name", ""),
                        "detail": compact_summary(block.get("input")),
                    }
                )
        elif event_type == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta":
                self.message_delta.emit(delta.get("text", ""))
            elif delta.get("type") == "thinking_delta":
                self.thinking_delta.emit(delta.get("thinking", ""))

    def _usage_updated(self, message: dict):
        usage = message.get("usage") or {}
        cached = usage.get("cache_read_input_tokens") or 0
        self.usage_changed.emit(
            {
                "used": usage.get("input_tokens"),
                "window": None,
                "percent": None,
                "input": usage.get("input_tokens"),
                "cached": cached or None,
                "output": usage.get("output_tokens"),
                "cost": message.get("total_cost_usd"),
            }
        )

    def _respond_control(self, message: dict):
        # canUseTool style requests should not appear under bypassPermissions;
        # answer defensively so a stray request cannot stall the process.
        self._write(
            {
                "type": "control_response",
                "response": {
                    "request_id": message.get("request_id"),
                    "behavior": "allow",
                },
            }
        )

    def send_turn(self, text: str, image_paths: list[str] | None = None) -> bool:
        text = text.strip()
        if not self.ready or not text:
            return False
        content: list[dict] = [{"type": "text", "text": text}]
        for path in image_paths or []:
            mime, data = encode_image(path)
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": mime, "data": data},
                }
            )
        self.user_message.emit(text, list(image_paths or []))
        self._write(
            {
                "type": "user",
                "message": {"role": "user", "content": content},
                "parent_tool_use_id": None,
            }
        )
        return True

    def set_model(self, model_id: str):
        if model_id and model_id != self.model_id:
            self.model_id = model_id or None
            if self.ready:
                self.status_changed.emit("Claude applies model %s on restart" % model_id)
                self.restart()

    def set_thinking(self, level: str):
        # Claude Code exposes no CLI thinking-level switch; ignore.
        pass
