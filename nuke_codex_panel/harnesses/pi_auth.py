"""Qt client for the private Pi SDK auth helper (runtime/pi/auth-helper.mjs).

The helper drives the SDK's public ``ModelRuntime`` login/logout/refresh against the managed Pi
agent directory and speaks JSON lines over stdio (requests, interactive ``auth_prompt`` /
``auth_event`` messages, fire-and-forget ``reply`` / ``cancel``). This client only transports that
protocol; it is not an agent/session engine and never sees credentials: the helper's payloads are
non-secret metadata, while secrets typed into prompts travel only in ``reply`` messages and are
never stored, logged or echoed into status/error text.

``accounts_changed`` is a module-global Qt signal (argument: the resolved agent directory) emitted
whenever a persisted credential may have changed, so running Pi sessions can renew themselves.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore

from .base import JsonlProcessClient
from .nuke_mcp import BRIDGE_FILE_ENV
from .. import pi_runtime
from ..process_ownership import CONTROL_EPOCH_ENV, CONTROL_ID_ENV


class _AuthEvents(QtCore.QObject):
    # Argument: str(resolved agent directory) whose stored credentials changed.
    accounts_changed = QtCore.Signal(str)


_events = _AuthEvents()
accounts_changed = _events.accounts_changed

_MAX_ERROR = 500
_MUTATIONS = ("login", "logout", "refresh")


def _clean(text) -> str:
    text = " ".join(str(text or "").split())
    return text[:_MAX_ERROR]


class PiAuthClient(JsonlProcessClient):
    """JSONL client for the SDK auth helper. Connect signals before ``start()``."""

    label = "Pi accounts"
    binary_label = "Pi auth helper"

    # Full helper events, as received (``type``, ``operationId``, ...).
    catalog_ready = QtCore.Signal(dict)
    auth_prompt = QtCore.Signal(dict)
    auth_event = QtCore.Signal(dict)
    auth_prompt_cancelled = QtCore.Signal(dict)
    # Terminal result of login/logout/refresh: response fields plus kind/provider/authType.
    operation_finished = QtCore.Signal(dict)

    def __init__(self, agent_dir, parent=None):
        self.agent_dir = Path(agent_dir).resolve()
        super().__init__(str(self.agent_dir), parent)
        self._node: str | None = None
        self._helper: str | None = None
        self._operation: dict | None = None
        self._pending_prompts: set[int] = set()
        self._catalog_id: int | None = None
        # Environment metadata is validated once per start(); the base class then never raises.
        self._environment: dict[str, str] = {}
        self._removals: list[str] = []
        self._helper_ready = False
        # Restart flag of a stop() requested while a non-cancellable refresh runs; None = none.
        self._deferred_stop: bool | None = None
        self._stop_calls = 0
        self._start_calls = 0

    # -- state ----------------------------------------------------------------

    @property
    def operation_id(self) -> int | None:
        return self._operation["id"] if self._operation else None

    @property
    def busy(self) -> bool:
        return self._operation is not None or self._catalog_id is not None

    # -- process launch -------------------------------------------------------

    def start(self):
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            if self._deferred_stop is not None:
                # The caller wants the helper after all: drop the deferred stop, keep the refresh.
                self._deferred_stop = None
                if self._helper_ready:
                    self._set_ready(True)
            return
        self._start_calls += 1
        try:
            node, helper = pi_runtime.resolve_auth_helper()
            self.agent_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            # Validate every synchronous environment/metadata lookup the base start() performs,
            # so a malformed or hash-mismatched runtime reports an error instead of raising.
            environment = dict(pi_runtime.managed_environment(self.agent_dir))
            inherited = list(QtCore.QProcessEnvironment.systemEnvironment().keys())
            removals = set(pi_runtime.managed_environment_removals(inherited))
            removals.update(name for name in inherited if name in (CONTROL_ID_ENV, CONTROL_EPOCH_ENV, BRIDGE_FILE_ENV))
        except Exception as exc:
            self._fail("Pi accounts unavailable: %s" % _clean(exc))
            return
        self._node, self._helper = str(node), str(helper)
        self._environment, self._removals = environment, sorted(removals)
        super().start()

    def stop(self, restart: bool = False):
        self._stop_calls += 1
        operation = self._operation
        if (
            operation is not None
            and operation["kind"] == "refresh"
            and self.process.state() != QtCore.QProcess.ProcessState.NotRunning
        ):
            # The SDK refresh deliberately outlives cancellation and persists rotated tokens:
            # killing the helper now could lose them. Stop once the operation is terminal.
            first = self._deferred_stop is None
            self._deferred_stop = bool(restart)
            self._set_ready(False)
            if first:
                self.status_changed.emit("Pi accounts: finishing credential refresh before stopping")
            return
        self._deferred_stop = None
        super().stop(restart)

    def resolve_program(self) -> str | None:
        return self._node

    def launch_arguments(self) -> list[str]:
        # The only argument besides the script is the private agent dir: never credentials.
        return [self._helper, "--agent-dir", str(self.agent_dir)]

    def launch_environment(self) -> dict[str, str] | None:
        # Private Pi controls only; no Nuke control/bridge identity (see environment_removals).
        return dict(self._environment)

    def environment_removals(self, names) -> list[str]:
        # Computed (and validated) in start() from the same inherited environment.
        return list(self._removals)

    # -- requests -------------------------------------------------------------

    def request_catalog(self) -> bool:
        """Ask for the dynamic provider catalog; refused while ready is false or a mutation runs."""
        if not self.ready or self._operation is not None:
            return False
        if self._catalog_id is not None:
            return True
        self._catalog_id = self._send({"type": "catalog"}, self._on_catalog)
        return True

    def login(self, provider: str, auth_type: str) -> bool:
        if auth_type not in ("api_key", "oauth"):
            return False
        return self._begin("login", provider, auth_type)

    def logout(self, provider: str) -> bool:
        return self._begin("logout", provider, None)

    def refresh(self, provider: str) -> bool:
        return self._begin("refresh", provider, None)

    def respond(self, prompt_id: int, value: str) -> bool:
        """Answer a pending prompt (select prompts: the chosen option id). Fire-and-forget."""
        if self._operation is None or prompt_id not in self._pending_prompts:
            return False
        self._pending_prompts.discard(prompt_id)
        self._write(
            {"type": "reply", "operationId": self._operation["id"], "promptId": prompt_id, "value": str(value)}
        )
        return True

    def cancel(self) -> bool:
        """Abort the active login/logout; the terminal result reports ``cancelled``.

        A refresh is not cancellable: the SDK persists rotated tokens even when the caller gives up.
        """
        operation = self._operation
        if operation is None or operation["kind"] == "refresh":
            return False
        operation["cancelling"] = True
        self._write({"type": "cancel", "operationId": operation["id"]})
        self._withdraw_prompts(operation["id"])
        return True

    def _begin(self, kind: str, provider: str, auth_type: str | None) -> bool:
        if not self.ready or self.busy or not provider:
            return False
        message = {"type": kind, "provider": str(provider)}
        if auth_type:
            message["authType"] = auth_type
        info = {"kind": kind, "provider": str(provider), "authType": auth_type, "cancelling": False}
        # Register before the write: nothing can be dispatched until control returns to the loop.
        info["id"] = self._next_id
        self._operation = info
        self._pending_prompts.clear()
        self._send(message, self._on_operation_response)
        return True

    # -- helper messages ------------------------------------------------------

    def _handle_message(self, message: dict):
        kind = message.get("type")
        if kind == "ready":
            self._helper_ready = True
            if self._deferred_stop is None:
                self._set_ready(True)
                self.status_changed.emit("Pi accounts ready")
        elif kind == "response":
            self._dispatch_response(message)
        elif kind == "auth_prompt":
            if self._is_active(message):
                prompt_id = message.get("promptId")
                if isinstance(prompt_id, int):
                    self._pending_prompts.add(prompt_id)
                    self.auth_prompt.emit(message)
        elif kind == "auth_event":
            if self._is_active(message):
                self.auth_event.emit(message)
        elif kind == "auth_prompt_cancelled":
            prompt_id = message.get("promptId")
            if self._is_active(message) and prompt_id in self._pending_prompts:
                self._pending_prompts.discard(prompt_id)
                self.auth_prompt_cancelled.emit(message)

    def _is_active(self, message: dict) -> bool:
        operation = self._operation
        return (
            operation is not None
            and not operation["cancelling"]
            and message.get("operationId") == operation["id"]
        )

    def _on_catalog(self, message: dict):
        self._catalog_id = None
        if message.get("success"):
            self.catalog_ready.emit(message.get("data") or {})
            return
        text = _clean(message.get("error")) or "Pi accounts catalog failed"
        self.status_changed.emit("Pi accounts catalog failed: %s" % text)
        self.error.emit(text)

    def _on_operation_response(self, message: dict):
        operation = self._operation
        if operation is None or message.get("id") != operation["id"]:
            return
        self._finish_operation(
            success=bool(message.get("success")),
            cancelled=bool(message.get("cancelled")),
            changed=bool(message.get("changed")),
            error=_clean(message.get("error")),
            data=message.get("data"),
            persisted_unknown=False,
        )

    def _finish_operation(self, *, success, cancelled, changed, error, data, persisted_unknown):
        operation = self._operation
        if operation is None:
            return
        self._withdraw_prompts(operation["id"])
        self._operation = None
        result = {
            "type": "response",
            "id": operation["id"],
            "kind": operation["kind"],
            "provider": operation["provider"],
            "authType": operation["authType"],
            "success": success,
            "cancelled": cancelled,
            "changed": changed,
        }
        if error:
            result["error"] = error
        if isinstance(data, dict):
            result["data"] = data
        # Only a changed (or unknown-after-helper-death) credential store must reach running Pi
        # sessions; successful no-ops must not renew them.
        if changed or persisted_unknown:
            accounts_changed.emit(str(self.agent_dir))
        deferred, self._deferred_stop = self._deferred_stop, None
        stop_calls, start_calls = self._stop_calls, self._start_calls
        self.operation_finished.emit(result)
        if success:
            self.status_changed.emit("Pi accounts: %s finished" % operation["kind"])
        elif cancelled:
            self.status_changed.emit("Pi accounts: %s cancelled" % operation["kind"])
        else:
            self.status_changed.emit("Pi accounts: %s failed" % operation["kind"])
        if deferred is not None and self._start_calls == start_calls and not (
            deferred and self._stop_calls != stop_calls
        ):
            # Honour the stop requested during the refresh now that it is terminal.
            JsonlProcessClient.stop(self, deferred)

    def _withdraw_prompts(self, operation_id: int):
        pending, self._pending_prompts = sorted(self._pending_prompts), set()
        for prompt_id in pending:
            self.auth_prompt_cancelled.emit(
                {"type": "auth_prompt_cancelled", "operationId": operation_id, "promptId": prompt_id}
            )

    # -- failure / exit: resolve everything, never leak raw stderr -------------

    def _read_stderr(self):
        # Helper stderr is discarded: it could carry provider text we cannot prove secret-free.
        self.process.readAllStandardError()

    def _resolve_dead(self, reason: str):
        catalog_pending, self._catalog_id = self._catalog_id is not None, None
        if self._operation is not None:
            cancelled = bool(self._operation["cancelling"])
            self._finish_operation(
                success=False,
                cancelled=cancelled,
                changed=False,
                error="" if cancelled else reason,
                data=None,
                persisted_unknown=True,
            )
        if catalog_pending:
            self.error.emit(reason)

    def _on_process_error(self, error):
        state_running = self.process.state() != QtCore.QProcess.ProcessState.NotRunning
        if self._stopping:
            return
        if error == QtCore.QProcess.ProcessError.FailedToStart:
            self._fail("Pi accounts helper failed to start")
            self._resolve_dead("Pi accounts helper failed to start")
        elif state_running:
            self._fail("Pi accounts helper process error: %s" % error.name)

    def _on_finished(self, exit_code, status):
        stopping = self._stopping
        self._helper_ready = False
        super()._on_finished(exit_code, status)
        self._resolve_dead(
            "Pi accounts helper stopped" if stopping else "Pi accounts helper exited (exit %s)" % exit_code
        )
