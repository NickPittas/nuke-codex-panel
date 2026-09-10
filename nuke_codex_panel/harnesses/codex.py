"""Codex App Server harness client."""

from __future__ import annotations

from pathlib import Path

from .base import JsonlProcessClient, compact_summary, resolve_binary
from .nuke_mcp import server_environment, server_command


class CodexClient(JsonlProcessClient):
    """Own one local Codex app-server process and one persistent thread."""

    name = "codex"
    label = "Codex"
    binary_label = "Codex"
    env_var = "NUKE_CODEX_BIN"

    def __init__(self, cwd: str, parent=None, bridge_path: str | None = None):
        super().__init__(cwd, parent, bridge_path)
        self.thread_id = None
        self.turn_id = None
        self.model_id: str | None = None
        self.effort: str | None = None
        self._fatal_ids = set()
        self._agent_item_id = None
        self._model_list_id = None

    def resolve_program(self) -> str | None:
        return resolve_binary(
            "NUKE_CODEX_BIN",
            "codex",
            [
                str(Path.home() / ".npm-global" / "bin" / "codex"),
                str(Path.home() / ".local" / "bin" / "codex"),
            ],
        )

    def launch_arguments(self) -> list[str]:
        return ["app-server"]

    def start(self):
        # Keep thread_id: a reconnect resumes the same conversation, and the
        # panel clears it explicitly for a new chat.
        self.turn_id = None
        super().start()

    def _on_started(self):
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

    def _initialized(self, _message):
        self._write({"method": "initialized", "params": {}})
        if self.thread_id:
            self.status_changed.emit("Resuming conversation…")
            self._request(
                "thread/resume",
                {
                    "threadId": self.thread_id,
                    "cwd": self.cwd,
                    "config": self._thread_config(),
                    "developerInstructions": self.system_prompt(),
                },
                self._thread_started,
                fatal=True,
            )
            return
        self.status_changed.emit("Starting conversation…")
        self._start_thread()

    def _thread_config(self) -> dict:
        nuke_env = dict(server_environment())
        if self.bridge_path:
            nuke_env["NUKE_CODEX_BRIDGE_FILE"] = self.bridge_path
        config = {
            "mcp_servers": {
                "nuke": {
                    "command": server_command()[0],
                    "args": server_command()[1:],
                    "cwd": self.cwd,
                    "env": nuke_env,
                    "startup_timeout_sec": 15,
                    "tool_timeout_sec": 300,
                }
            }
        }
        if self.model_id:
            config["model"] = self.model_id
        if self.effort:
            config["model_reasoning_effort"] = self.effort
        return config

    def _start_thread(self):
        self._request(
            "thread/start",
            {
                "cwd": self.cwd,
                "sandbox": "read-only",
                "approvalPolicy": "never",
                "ephemeral": False,
                "developerInstructions": self.system_prompt(),
                "config": self._thread_config(),
            },
            self._thread_started,
            fatal=True,
        )

    def _thread_started(self, message):
        self._agent_item_id = None
        self.thread_id = (message.get("result") or {}).get("thread", {}).get("id")
        if not self.thread_id:
            self._fail("Codex started without returning a thread id")
            return
        self._model_list_id = self._request("model/list", {}, self._models_loaded)

    def _usage_updated(self, params: dict):
        usage = params.get("tokenUsage") or {}
        last = usage.get("last") or {}
        total = usage.get("total") or {}
        window = usage.get("modelContextWindow")
        used = last.get("totalTokens") or total.get("totalTokens")
        percent = (used / window * 100) if used and window else None
        self.usage_changed.emit(
            {
                "used": used,
                "window": window,
                "percent": percent,
                "input": last.get("inputTokens"),
                "cached": last.get("cachedInputTokens"),
                "output": last.get("outputTokens"),
                "cost": None,
            }
        )

    def _models_loaded(self, message):
        models = []
        for entry in (message.get("result") or {}).get("data") or []:
            if entry.get("hidden"):
                continue
            efforts = [
                item.get("reasoningEffort")
                for item in entry.get("supportedReasoningEfforts") or []
                if item.get("reasoningEffort")
            ]
            models.append(
                {
                    "id": entry.get("model") or entry.get("id"),
                    "label": entry.get("displayName") or entry.get("model"),
                    "efforts": efforts,
                }
            )
        # Ready before the emit so a panel-side model pick restarts the thread.
        self._set_ready(True)
        if models:
            self.models_changed.emit(models)
        self.status_changed.emit("Codex connected")

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
        )
        return True

    def interrupt(self):
        if not self.thread_id or not self.turn_id:
            return
        self._request(
            "turn/interrupt",
            {"threadId": self.thread_id, "turnId": self.turn_id},
        )

    def session_state(self) -> dict:
        return {"thread_id": self.thread_id}

    def resume_session(self, state: dict):
        super().resume_session(state)
        self.thread_id = (state or {}).get("thread_id") or None

    def new_session(self):
        self._resuming = False
        self.thread_id = None
        self._agent_item_id = None
        if self.ready:
            self._start_thread()

    def set_model(self, model_id: str):
        if model_id and model_id != self.model_id:
            self.model_id = model_id or None
            self._apply_config_change("model %s" % model_id)

    def set_thinking(self, level: str):
        if level and level != self.effort:
            self.effort = level or None
            self._apply_config_change("reasoning effort %s" % level)

    def _apply_config_change(self, what: str):
        if not self.ready:
            return
        self.status_changed.emit(
            "Codex applies %s in a fresh thread — conversation reset" % what
        )
        self.thread_id = None
        # Not ready until the replacement thread exists, so a Send during the
        # swap fails visibly instead of silently dropping the prompt.
        self._set_ready(False)
        self._start_thread()

    def _request(self, method: str, params: dict, callback=None, fatal: bool = False):
        request_id = self._next_id
        self._next_id += 1
        self._callbacks[request_id] = callback
        if fatal:
            self._fatal_ids.add(request_id)
        self._write({"method": method, "id": request_id, "params": params})
        return request_id

    def _handle_message(self, message: dict):
        if "id" in message and ("result" in message or "error" in message):
            error_text = None
            if "error" in message:
                error = message.get("error") or {}
                error_text = error.get("message") or str(error)
                if message.get("id") in self._fatal_ids:
                    self._fatal_ids.discard(message.get("id"))
                    self._fail(error_text)
                    return
                if message.get("id") == self._model_list_id:
                    # Model listing is best-effort; never block readiness on it.
                    self._models_loaded({})
                    return
            self._dispatch_response(message, error_text)
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
            item_type = item.get("type")
            if item_type == "agentMessage":
                item_id = str(item.get("id", ""))
                if self._agent_item_id and item_id != self._agent_item_id:
                    self.message_delta.emit("\n\n")
                self._agent_item_id = item_id
            elif item_type == "commandExecution":
                self.tool_event.emit(
                    {
                        "phase": "start",
                        "id": item.get("id"),
                        "tool": "shell",
                        "detail": compact_summary(item.get("command")),
                    }
                )
        elif method == "item/completed":
            item = params.get("item") or {}
            if item.get("type") == "commandExecution":
                exit_code = item.get("exitCode")
                self.tool_event.emit(
                    {
                        "phase": "end",
                        "id": item.get("id"),
                        "tool": "shell",
                        "ok": exit_code in (0, None),
                        "detail": "exit %s — %s"
                        % (exit_code, compact_summary(item.get("aggregatedOutput"))),
                    }
                )
        elif method == "item/agentMessage/delta":
            self.message_delta.emit(params.get("delta", ""))
        elif method == "item/reasoning/textDelta":
            self.thinking_delta.emit(params.get("delta", ""))
        elif method == "thread/tokenUsage/updated":
            self._usage_updated(params)
        elif method == "turn/completed":
            turn = params.get("turn", {})
            self.turn_id = None
            self.turn_completed.emit(turn.get("status", "completed"))
