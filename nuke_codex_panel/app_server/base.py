"""Abstract coding-agent backend presenting the panel's chat signal contract.

Concrete backends (codex, pi, claude, opencode) translate their CLI's protocol
into these Qt signals so the panel UI stays backend-agnostic. The UI couples
only to this contract, never to a specific backend's transport.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore


class BackendClient(QtCore.QObject):
    """Common chat-backend interface consumed by CodexPanelWidget.

    Subclasses set ``backend_key``/``display_name`` and implement the lifecycle
    methods, emitting the signals below to drive the panel.

    Contract:
    - ``start()`` must make the Nuke MCP server available to the agent (via
      whatever mechanism the backend supports) before emitting
      ``ready_changed(True)``.
    - Every turn must terminate with exactly one ``turn_completed`` emission,
      including the interrupt and error paths, so the panel's Send/Cancel
      state machine cannot wedge.
    """

    backend_key: str = ""
    display_name: str = ""
    # False when the backend cannot accept inline image inputs (e.g. claude);
    # the panel surfaces this so capture is not silently degraded.
    supports_images: bool = True
    # True when the backend can list/select models and thinking levels.
    supports_model_select: bool = False

    status_changed = QtCore.Signal(str)
    ready_changed = QtCore.Signal(bool)
    user_message = QtCore.Signal(str, list)
    turn_started = QtCore.Signal()
    agent_message_started = QtCore.Signal(str, str)
    message_delta = QtCore.Signal(str)
    turn_completed = QtCore.Signal(str)
    error = QtCore.Signal(str)
    # [{"id": str, "name": str, "efforts": [str], "default_effort": str|None,
    #   "is_default": bool, "provider": str, "provider_name": str}] — provider
    # fields are optional; efforts is empty when the model has no thinking knob.
    models_changed = QtCore.Signal(list)
    # Thinking bubble: (item id, full text so far). Replace-based, not append —
    # adapters accumulate deltas and emit the whole text each time.
    thinking_updated = QtCore.Signal(str, str)
    thinking_completed = QtCore.Signal(str)  # item id
    # Tool bubble snapshot: (item id, tool name, status, args_json, output).
    # status is normalized to "running" | "completed" | "error"; output holds
    # the result text on completion or the error message on "error".
    tool_updated = QtCore.Signal(str, str, str, str, str)

    def __init__(self, cwd: str, parent=None, bridge_path: str | None = None):
        super().__init__(parent)
        self.cwd = str(Path(cwd).resolve())
        self.bridge_path = str(Path(bridge_path).resolve()) if bridge_path else None
        self.ready = False

    def start(self):
        raise NotImplementedError

    def stop(self, restart: bool = False):
        raise NotImplementedError

    def restart(self):
        raise NotImplementedError

    def send_turn(self, text: str, image_paths: list[str] | None = None) -> bool:
        raise NotImplementedError

    def interrupt(self):
        raise NotImplementedError

    def request_models(self):
        """Fetch available models asynchronously, then emit models_changed."""

    def set_model(self, model_id: str | None, effort: str | None = None):
        """Select model (and thinking level) for subsequent turns."""

    def new_conversation(self):
        """Drop the current conversation; the next turn starts a fresh one."""
        raise NotImplementedError

    def _set_ready(self, value: bool):
        if self.ready == value:
            return
        self.ready = value
        self.ready_changed.emit(value)

    def _fail(self, message: str):
        self._set_ready(False)
        self.status_changed.emit(message)
        self.error.emit(message)
