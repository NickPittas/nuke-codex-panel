"""Small asynchronous Codex App Server JSON-RPC client for Nuke's Qt loop."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys

from PySide6 import QtCore

from .base import BackendClient
from .resolver import resolve_codex_binary


class CodexAppServerClient(BackendClient):
    """Own one local app-server process and one persistent Codex thread."""

    backend_key = "codex"
    display_name = "Codex"
    supports_model_select = True

    def __init__(self, cwd: str, parent=None, bridge_path: str | None = None):
        super().__init__(cwd, parent, bridge_path=bridge_path)
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
        self._model_id = None
        self._effort = None
        self._thinking_buffers = {}
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
        self._thinking_buffers.clear()
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
        params = {
            "threadId": self.thread_id,
            "input": inputs,
            "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            "approvalPolicy": "never",
        }
        if self._model_id:
            params["model"] = self._model_id
        if self._effort:
            params["effort"] = self._effort
        self._request("turn/start", params, self._turn_start_response)
        return True

    def request_models(self):
        if not self.ready:
            self.models_changed.emit([])
            self.error.emit("Codex is not ready")
            return

        def received(result):
            try:
                models = [
                    {
                        "id": model["id"],
                        "name": model["displayName"],
                        "efforts": [
                            effort["reasoningEffort"]
                            for effort in model.get("supportedReasoningEfforts", [])
                        ],
                        "default_effort": model.get("defaultReasoningEffort"),
                        "is_default": bool(model.get("isDefault")),
                    }
                    for model in result["data"]
                ]
            except (KeyError, TypeError):
                self.models_changed.emit([])
                self.error.emit("Invalid model list response")
                return
            self.models_changed.emit(models)

        self._request("model/list", {}, received)

    def set_model(self, model_id: str | None, effort: str | None = None):
        self._model_id = model_id
        self._effort = effort

    def new_conversation(self):
        if self.turn_id:
            self.status_changed.emit("Cannot start a new conversation during a turn")
            return False
        if not self.ready:
            return False
        self.thread_id = None
        self.turn_id = None
        self._thinking_buffers.clear()
        self.status_changed.emit("New conversation")
        self._start_thread()
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
        self._start_thread()

    def _start_thread(self):
        self._thinking_buffers.clear()
        nuke_server = {
            "command": self.sidecar_python,
            "args": ["-m", "nuke_codex_panel.mcp_server.server"],
            "cwd": self.cwd,
            "startup_timeout_sec": 15,
            "tool_timeout_sec": 300,
        }
        if self.bridge_path:
            nuke_server["env"] = {"NUKE_CODEX_BRIDGE_FILE": self.bridge_path}
        params = {
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
            "config": {"mcp_servers": {"nuke": nuke_server}},
        }
        if self._model_id:
            params["model"] = self._model_id
        self._request("thread/start", params, self._thread_started, fatal=True)

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
        self._callbacks[request_id] = (callback, fatal, method)
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
            callback, fatal, request_method = self._callbacks.pop(
                message["id"], (None, False, None)
            )
            if "error" in message:
                error = message.get("error") or {}
                error_message = error.get("message") or str(error)
                if fatal:
                    self._fail(error_message)
                else:
                    if request_method == "model/list":
                        self.models_changed.emit([])
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
            item_type = item.get("type")
            if item_type == "agentMessage":
                self.agent_message_started.emit(
                    str(item.get("id", "")), str(item.get("phase", ""))
                )
            elif item_type == "reasoning":
                self._thinking_buffers[item.get("id", "")] = ""
            elif item_type == "mcpToolCall":
                self.tool_updated.emit(
                    item.get("id", ""),
                    item.get("server", "") + ":" + item.get("tool", ""),
                    "running",
                    json.dumps(item.get("arguments")),
                    "",
                )
            elif item_type == "commandExecution":
                self.tool_updated.emit(
                    item.get("id", ""),
                    "command: " + str(item.get("command", ""))[:80],
                    "running",
                    json.dumps({"command": item.get("command")}),
                    "",
                )
            elif item_type == "fileChange":
                self.tool_updated.emit(
                    item.get("id", ""), "fileChange", "running",
                    json.dumps(item.get("changes") or []), "",
                )
            elif item_type == "dynamicToolCall":
                self.tool_updated.emit(
                    item.get("id", ""), str(item.get("tool", "tool")), "running",
                    json.dumps(item.get("arguments")), "",
                )
            elif item_type == "webSearch":
                self.tool_updated.emit(
                    item.get("id", ""), "webSearch", "running",
                    json.dumps({"query": item.get("query")}), "",
                )
        elif method == "item/agentMessage/delta":
            self.message_delta.emit(params.get("delta", ""))
        elif method in ("item/reasoning/textDelta", "item/reasoning/summaryTextDelta"):
            item_id = params.get("itemId", "")
            text = self._thinking_buffers.get(item_id, "") + params.get("delta", "")
            self._thinking_buffers[item_id] = text
            self.thinking_updated.emit(item_id, text)
        elif method == "item/completed":
            item = params.get("item") or {}
            item_type = item.get("type")
            item_id = item.get("id", "")
            if item_type == "reasoning":
                self.thinking_completed.emit(item_id)
                self._thinking_buffers.pop(item_id, None)
            elif item_type == "mcpToolCall":
                output = (
                    json.dumps(item.get("result"))
                    if item.get("result")
                    else (item.get("error") or {}).get("message", "")
                )
                self.tool_updated.emit(
                    item_id,
                    item.get("server", "") + ":" + item.get("tool", ""),
                    "completed" if item.get("status") == "completed" else "error",
                    json.dumps(item.get("arguments")), output,
                )
            elif item_type == "commandExecution":
                output = item.get("aggregatedOutput") or ""
                if item.get("exitCode"):
                    output += ("\n" if output else "") + "exitCode: %s" % item["exitCode"]
                self.tool_updated.emit(
                    item_id, "command: " + str(item.get("command", ""))[:80],
                    "completed" if item.get("status") == "completed" else "error",
                    json.dumps({"command": item.get("command")}), output,
                )
            elif item_type == "fileChange":
                self.tool_updated.emit(
                    item_id, "fileChange",
                    "completed" if item.get("status") == "completed" else "error",
                    json.dumps(item.get("changes") or []),
                    json.dumps(item.get("changes") or []),
                )
            elif item_type in ("dynamicToolCall", "webSearch"):
                self.tool_updated.emit(
                    item_id,
                    str(item.get("tool", "tool")) if item_type == "dynamicToolCall" else "webSearch",
                    "completed" if item.get("status") == "completed" else "error",
                    json.dumps(item.get("arguments")) if item_type == "dynamicToolCall" else json.dumps({"query": item.get("query")} ),
                    json.dumps(item.get("contentItems") or item.get("results") or ""),
                )
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
