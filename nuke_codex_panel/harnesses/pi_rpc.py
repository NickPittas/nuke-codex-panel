"""Harness client for pi-style agents (pi and its omp fork) over `--mode rpc`."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from .base import JsonlProcessClient, compact_summary, resolve_binary, encode_image
from . import nuke_mcp


def _agent_dir(binary_name: str) -> Path:
    override = os.environ.get("PI_CODING_AGENT_DIR")
    if override:
        return Path(override)
    if binary_name == "omp":
        return Path.home() / ".omp" / "agent"
    return Path.home() / ".pi" / "agent"


class PiRpcClient(JsonlProcessClient):
    """pi / omp share one JSONL RPC protocol; only the binary and agent dir differ."""

    def __init__(
        self,
        cwd: str,
        binary_name: str,
        agent_dir: Path,
        parent=None,
        bridge_path: str | None = None,
    ):
        super().__init__(cwd, parent, bridge_path)
        self.binary_name = binary_name
        self.agent_dir = Path(agent_dir)
        self.name = binary_name
        self.label = "OMP" if binary_name == "omp" else "Pi"
        self.binary_label = binary_name
        self.env_var = "NUKE_%s_BIN" % self.binary_name.upper()
        self._busy = False
        self._thinking_levels: list[str] = []
        self._supports_thinking = True
        self._content_index = -1
        self.session_id: str | None = None
        self.session_file: str | None = None
        self.session_dir: Path | None = None
        self._models_signature: list | None = None

    def resolve_program(self) -> str | None:
        return resolve_binary(
            self.env_var,
            self.binary_name,
            [
                str(Path.home() / ".npm-global" / "bin" / self.binary_name),
                str(Path.home() / ".local" / "bin" / self.binary_name),
            ],
        )

    def launch_arguments(self) -> list[str]:
        args = [
            "--mode", "rpc",
            "--append-system-prompt", self.system_prompt(),
        ]
        if self.session_dir is not None:
            args.extend(["--session-dir", str(self.session_dir)])
            if self.session_id:
                # pi creates the session when the id is unknown, so this doubles
                # as "resume if it exists, otherwise start clean under a stable id".
                args.extend(["--session-id", self.session_id])
        else:
            args.append("--no-session")
        return args

    def session_state(self) -> dict:
        return {"session_id": self.session_id, "session_file": self.session_file}

    def resume_session(self, state: dict):
        super().resume_session(state)
        self.session_id = (state or {}).get("session_id") or None
        self.session_file = (state or {}).get("session_file") or None

    def new_session(self):
        self._resuming = False
        self.session_id = None
        self.session_file = None
        self._turn_error = None
        if self.ready:
            self._send({"type": "new_session"}, self._session_switched)

    def _session_switched(self, message):
        data = message.get("data") or {}
        if data.get("cancelled"):
            return
        self._query_state()
        self.status_changed.emit("%s started a fresh session" % self.label)

    def start(self):
        self._busy = False
        self._content_index = -1
        self._prepare_mcp()
        super().start()

    def _prepare_mcp(self):
        """Wire the Nuke MCP sidecar: native mcp.json for omp, adapter for pi."""
        try:
            nuke_mcp.merge_agent_mcp_config(self.agent_dir)
        except Exception as exc:
            self.status_changed.emit("%s MCP config failed: %s" % (self.label, exc))
            return
        if self.binary_name != "pi":
            return
        installed = self.agent_dir / "npm" / "node_modules" / "pi-mcp-adapter"
        if installed.exists():
            return
        self.status_changed.emit("Installing pi-mcp-adapter for Nuke tools…")
        try:
            subprocess.run(
                [self.resolve_program() or "pi", "install", "npm:pi-mcp-adapter"],
                check=False,
                capture_output=True,
                timeout=180,
            )
        except Exception as exc:
            self.status_changed.emit("pi-mcp-adapter install failed: %s" % exc)

    def _on_started(self):
        self.status_changed.emit("Initializing %s…" % self.label)
        # Older pi builds emit no "ready" event, so ask for state right away;
        # the first response doubles as the readiness signal.
        self._query_state()

    def _handle_message(self, message: dict):
        kind = message.get("type")
        if kind == "ready":
            self._mark_ready()
            self._query_state()
        elif kind == "response":
            error_text = None
            if not message.get("success"):
                if message.get("command") == "get_available_thinking_levels":
                    # omp predates this command; thinking levels stay empty.
                    self._supports_thinking = False
                    self._callbacks.pop(message.get("id"), None)
                    return
                error_text = message.get("error") or "%s request failed" % message.get("command")
            self._dispatch_response(message, error_text)
        elif kind == "agent_start":
            self._busy = True
            self._content_index = -1
            self.turn_started.emit()
        elif kind in ("agent_end", "agent_settled"):
            # agent_settled is newer; omp only emits agent_end.
            if not message.get("willRetry") and self._busy:
                self._busy = False
                self.turn_completed.emit("completed")
                self._send({"type": "get_session_stats"}, self._stats_loaded)
        elif kind == "turn_end":
            # A failed provider call still ends the turn; surface why instead
            # of leaving an empty reply on screen.
            failed = (message.get("message") or {}).get("errorMessage")
            if failed:
                self.error.emit("%s: %s" % (self.label, failed))
        elif kind == "message_update":
            self._handle_stream_update(message.get("assistantMessageEvent") or {})
        elif kind == "tool_execution_start":
            self.tool_event.emit(
                {
                    "phase": "start",
                    "id": message.get("toolCallId"),
                    "tool": message.get("toolName", ""),
                    "detail": compact_summary(message.get("args")),
                }
            )
        elif kind == "tool_execution_end":
            result = message.get("result") or {}
            output = " ".join(
                block.get("text", "")
                for block in result.get("content") or []
                if isinstance(block, dict)
            )
            self.tool_event.emit(
                {
                    "phase": "end",
                    "id": message.get("toolCallId"),
                    "tool": message.get("toolName", ""),
                    "ok": not message.get("isError", False),
                    "detail": compact_summary(output),
                }
            )
        elif kind == "extension_ui_request":
            self._handle_extension_ui(message)
        elif kind == "extension_error":
            self.status_changed.emit("%s extension error: %s" % (self.label, message.get("error", "")))

    def _handle_stream_update(self, event: dict):
        event_type = event.get("type")
        if event_type == "text_start":
            index = event.get("contentIndex", 0)
            if self._content_index >= 0 and index != self._content_index:
                self.message_delta.emit("\n\n")
            self._content_index = index
        elif event_type == "text_delta":
            if self._content_index < 0:
                self._content_index = 0
            self.message_delta.emit(event.get("delta", ""))
        elif event_type == "thinking_delta":
            self.thinking_delta.emit(event.get("delta", ""))
        elif event_type == "toolcall_start":
            self.status_changed.emit("%s running tool: %s" % (self.label, event.get("toolName", "")))

    def _handle_extension_ui(self, message: dict):
        # Dialog methods block until answered; decline them. Fire-and-forget
        # methods (notify/setStatus/setWidget/setTitle) are ignored.
        if message.get("method") in ("select", "confirm", "input", "editor"):
            self._write(
                {
                    "type": "extension_ui_response",
                    "id": message.get("id"),
                    "cancelled": True,
                }
            )

    def _query_state(self):
        self._send({"type": "get_available_models"}, self._models_loaded)
        self._send({"type": "get_available_thinking_levels"}, self._levels_loaded)
        self._send({"type": "get_state"}, self._state_loaded)
        self._send({"type": "get_session_stats"}, self._stats_loaded)

    def _state_loaded(self, message):
        data = message.get("data") or {}
        self.session_id = data.get("sessionId") or self.session_id
        self.session_file = data.get("sessionFile") or self.session_file
        self._mark_ready()

    def _stats_loaded(self, message):
        data = message.get("data") or {}
        tokens = data.get("tokens") or {}
        context = data.get("contextUsage") or {}
        self.usage_changed.emit(
            {
                "used": context.get("tokens"),
                "window": context.get("contextWindow"),
                "percent": context.get("percent"),
                "input": tokens.get("input"),
                "cached": tokens.get("cacheRead"),
                "output": tokens.get("output"),
                "cost": data.get("cost"),
            }
        )

    def _mark_ready(self):
        if not self.ready:
            self._set_ready(True)
            self.status_changed.emit("%s connected" % self.label)

    def _models_loaded(self, message):
        levels = self._thinking_levels
        models = []
        for entry in (message.get("data") or {}).get("models") or []:
            provider = entry.get("provider", "")
            model_id = entry.get("id", "")
            models.append(
                {
                    "id": "%s/%s" % (provider, model_id) if provider else model_id,
                    "label": entry.get("name") or model_id,
                    "efforts": list(levels),
                }
            )
        if models:
            signature = [(m["id"], m["label"], tuple(m["efforts"])) for m in models]
            # Only announce real changes: a re-query triggered by set_model must
            # not bounce back into the panel and re-select the model forever.
            if signature != self._models_signature:
                self._models_signature = signature
                self.models_changed.emit(models)
        self._mark_ready()

    def _levels_loaded(self, message):
        levels = [str(level) for level in (message.get("data") or {}).get("levels") or []]
        self._thinking_levels = levels
        # Re-emit models so the panel refreshes per-model effort lists.
        self._send({"type": "get_available_models"}, self._models_loaded)

    def send_turn(self, text: str, image_paths: list[str] | None = None) -> bool:
        text = text.strip()
        if not self.ready or not text:
            return False
        payload = {"type": "prompt", "message": text}
        if self._busy:
            payload["streamingBehavior"] = "followUp"
        if image_paths:
            payload["images"] = [
                {"type": "image", **dict(zip(("mimeType", "data"), encode_image(path)))}
                for path in image_paths
            ]
        self.user_message.emit(text, list(image_paths or []))
        self._send(payload)
        return True

    def interrupt(self):
        if self._busy:
            self._send({"type": "abort"})

    def set_model(self, model_id: str):
        if not model_id or "/" not in model_id:
            return
        provider, model = model_id.split("/", 1)
        self._send({"type": "set_model", "provider": provider, "modelId": model})
        self._send({"type": "get_available_thinking_levels"}, self._levels_loaded)

    def set_thinking(self, level: str):
        if level and self._supports_thinking:
            self._send({"type": "set_thinking_level", "level": level})
