"""In-process execution control for bridge clients: pause, revoke, resume, and operation counts.

The bridge runs a request to completion on Nuke's GUI thread, so a manual intervention cannot
cancel an operation that is already executing; it can only make sure that nothing *else* from
the interrupted model run starts. Control state is therefore kept in-process (a UI event
handler, even one running inside an approval dialog's nested event loop, calls it directly and
the effect is visible to the next request check) and is keyed by a stable ``control_id``, one
per harness client. A client with another control id, or none, is never affected.

A bare "paused" flag is not enough: the MCP sidecar may already hold a batch of tool calls from
the old run in its stdin pipe, and they would run the moment the flag clears. The primary
guarantees are structural: an intervention permanently retires the control's sidecar client ids
(``control_retired`` forever, no rebind), and ``begin_process`` fixes a process epoch so any
request from a replaced process is refused and its client tombstoned. A supplementary fence is
``received_ns``, a ``CLOCK_MONOTONIC`` stamp taken by the sidecar's stdin reader thread when the
line arrived (shared across processes on one host); ``resume`` and ``revoke`` move a per-control
watermark to *now*, so anything stamped before that instant stays stale. The stamp alone cannot
see bytes still unwritten to the pipe, which is why retirement/epoch are primary and ``resume``
also refuses while the bridge still counts an active operation. This protects model-run
sequencing; it is not a sandbox against code that is deliberately lying about its stamp,
epoch or control id.
"""

from __future__ import annotations

from collections import deque
import itertools
import os
import threading
import time

LEGACY_CLIENT = "legacy"  # mirrors inspection.LEGACY_CLIENT: callers without an id share it
MAX_CONTROL_ID = 64
UNSCOPED = ""

PAUSED = "control_paused"
STALE = "control_stale"
MISMATCH = "control_mismatch"
CLOSED = "control_closed"
RETIRED = "control_retired"

# Messages shown to the model; the real user message follows on the new run.
_MESSAGES = {
    PAUSED: "The user has paused this run to give new instructions. Nothing was executed. "
    "Stop issuing Nuke tool calls and wait for the user's next message.",
    STALE: "This request belongs to a run the user interrupted. Nothing was executed. "
    "Discard it and follow the user's latest message.",
    MISMATCH: "This request names a different control scope than the client that made earlier requests. "
    "Nothing was executed.",
    CLOSED: "The Nuke bridge for this request is shutting down. Nothing was executed.",
    RETIRED: "This tool session was ended by the user's intervention and can never run again. "
    "Nothing was executed. Discard this request.",
}


def normalize_control_id(value) -> str:
    """Control id from the private envelope; absent means the caller is not controllable."""
    text = str(value).strip()[:MAX_CONTROL_ID] if value else ""
    return text or UNSCOPED


class ControlRefused(Exception):
    """A request was refused before any code, approval or graph access happened."""

    def __init__(self, code: str):
        super().__init__(_MESSAGES.get(code, code))
        self.code = code

    def response(self) -> dict:
        return {"success": False, "graph_changed": False, "error_code": self.code, "error": "%s: %s" % (self.code, self)}


class ControlBusy(Exception):
    """resume() while the bridge still has operations running for this control."""

    def __init__(self, control_id: str, active: int):
        super().__init__(
            "cannot resume %r: %d bridge operation(s) are still running; wait for them to finish" % (control_id, active)
        )
        self.control_id = control_id
        self.active_operations = active


class _State:
    def __init__(self):
        self.paused = False
        self.revoked = False
        self.generation = 0
        self.valid_from_ns = 0
        self.clients: set[str] = set()
        self.retiring = False
        self.epoch = None
        self.operations: dict[int, "Operation"] = {}


class Operation:
    """One admitted bridge request. ``finish`` is idempotent; ``recheck`` is for after waiting."""

    def __init__(self, control: "BridgeControl", operation_id: int, control_id: str, client_id: str, kind: str, detail: str, generation: int):
        self._control = control
        self.operation_id = operation_id
        self.control_id = control_id
        self.client_id = client_id
        self.kind = kind
        self.detail = detail
        self.generation = generation
        self.started_ns = time.monotonic_ns()
        self.finished = False

    def recheck(self) -> None:
        """Raise ControlRefused if the control was paused/revoked since admission (e.g. during an approval dialog)."""
        self._control._recheck(self)

    def finish(self, success: bool, error_code: str | None = None) -> None:
        self._control._finish(self, success, error_code)

    def __enter__(self):
        _active.append(self)
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self in _active:
            _active.remove(self)
        if not self.finished:
            self.finish(False, exc_type.__name__ if exc_type else None)
        return False


# Operations being served right now, innermost last (the bridge serves one at a time on the GUI thread).
_active: list = []


def current_operation() -> "Operation | None":
    """The operation the bridge is serving right now (e.g. for tagging its approval dialog), or None."""
    return _active[-1] if _active else None


class BridgeControl:
    """Execution control for every client of one bridge."""

    def __init__(self, bridge_path: str | None = None):
        self.bridge_path = bridge_path
        self._lock = threading.RLock()
        self._states: dict[str, _State] = {}
        self._client_control: dict[str, str] = {}
        # client id -> control id: tombstones kept for the life of this control object.
        self._retired: dict[str, str] = {}
        self._listeners: list = []
        self._ids = itertools.count(1)
        self._closed = False
        # Listener exceptions never break the bridge, but they stay inspectable.
        self.listener_errors: deque = deque(maxlen=20)

    # ---- public control surface -------------------------------------------------
    def pause(self, control_id: str, retire: bool = False) -> dict:
        """Refuse every later request of this control immediately. Idempotent. Accepted operations finish.

        ``retire=True`` also permanently retires the control's sidecar clients (see retire_clients).
        """
        key = self._scoped(control_id)
        with self._lock:
            state = self._state(key)
            changed = not state.paused
            if changed:
                state.paused = True
                state.generation += 1
            status = self._status(key)
        if changed:
            self._emit("paused", key, status)
        if retire:
            self.retire_clients(key)
            status = self.status(key)
        return status

    def retire_clients(self, control_id: str) -> list:
        """Permanently retire every sidecar client this control has seen; returns their ids.

        A retired client id is refused (``control_retired``) for the life of this control object,
        even after resume, and cannot rebind: bytes still unread in that sidecar's stdin can never
        run. Until the next resume(), any other client of this control refused while it is
        paused is retired too. The replacement sidecar must be started (fresh client id) before resume.
        """
        key = self._scoped(control_id)
        with self._lock:
            state = self._state(key)
            clients = sorted(state.clients)
            for client in clients:
                self._retired[client] = key
            state.clients.clear()
            state.retiring = True
            status = self._status(key)
        self._emit("retired", key, status, clients=clients)
        return clients

    def begin_process(self, control_id: str, epoch: int) -> dict:
        """Make ``epoch`` the only process epoch this control accepts from now on.

        The harness calls it right before launching process ``epoch`` of a client (and before
        resume()), and exports the same number to that process's sidecar as NUKE_CODEX_CONTROL_EPOCH.
        Every request of this control whose ``control_epoch`` differs (or is missing) is then
        refused ``control_retired`` and its client id is tombstoned, whatever it was ever seen
        doing before. A control that never called this accepts any epoch. Epochs must increase.
        """
        key = self._scoped(control_id)
        if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 0:
            raise ValueError("epoch must be a non-negative integer")
        with self._lock:
            state = self._state(key)
            if state.epoch is not None and epoch <= state.epoch:
                raise ValueError("epoch %d does not advance control %r past %d" % (epoch, key, state.epoch))
            state.epoch = epoch
            status = self._status(key)
        self._emit("process_began", key, status, epoch=epoch)
        return status

    def resume(self, control_id: str) -> dict:
        """Reopen a paused/revoked control for requests stamped from now on.

        Idempotent when the control is already open. Raises ControlBusy while operations run.
        Retired clients stay retired.
        """
        key = self._scoped(control_id)
        with self._lock:
            state = self._state(key)
            if not (state.paused or state.revoked):
                state.retiring = False
                return self._status(key)
            if state.operations:
                raise ControlBusy(key, len(state.operations))
            # The watermark fences off everything the sidecar read before this instant.
            state.valid_from_ns = time.monotonic_ns()
            state.paused = False
            state.revoked = False
            state.retiring = False
            state.generation += 1
            status = self._status(key)
        self._emit("resumed", key, status)
        return status

    def revoke(self, control_id: str) -> dict:
        """End a session: pause, stale everything stamped so far, and permanently retire its sidecar clients.

        Stays closed until resume(). The ``revoked`` event lists the retired ``clients`` whose
        per-client bridge state (evidence) the bridge drops.
        """
        key = self._scoped(control_id)
        with self._lock:
            state = self._state(key)
            clients = sorted(state.clients)
            for client in clients:
                self._retired[client] = key
            state.clients.clear()
            state.paused = True
            state.revoked = True
            state.retiring = True
            state.generation += 1
            state.valid_from_ns = time.monotonic_ns()
            status = self._status(key)
        self._emit("revoked", key, status, clients=clients)
        return status

    def status(self, control_id: str) -> dict:
        """{"control_id","paused","revoked","generation","active_operations","operations":[...]}"""
        with self._lock:
            return self._status(normalize_control_id(control_id))

    def add_listener(self, callback):
        """Register ``callback(event: dict)``; returns a function that removes it."""
        with self._lock:
            self._listeners.append(callback)

        def remove():
            with self._lock:
                if callback in self._listeners:
                    self._listeners.remove(callback)

        return remove

    # ---- bridge-internal ----------------------------------------------------------
    def admit(self, control_id, client_id: str, kind: str, received_ns=None, detail: str = "", epoch=None) -> Operation:
        """Admit one request or raise ControlRefused. Nothing may run before this returns."""
        key = normalize_control_id(control_id)
        stamp = received_ns if isinstance(received_ns, int) and not isinstance(received_ns, bool) else time.monotonic_ns()
        refusal = None
        operation = None
        with self._lock:
            state = self._state(key)
            bound = self._client_control.get(client_id) if client_id != LEGACY_CLIENT else None
            if self._closed:
                refusal = CLOSED
            elif client_id != LEGACY_CLIENT and client_id in self._retired:
                refusal = RETIRED
            elif key != UNSCOPED and state.epoch is not None and epoch != state.epoch:
                refusal = RETIRED
            elif bound is not None and bound != key:
                refusal = MISMATCH
            elif key != UNSCOPED and state.paused:
                refusal = PAUSED
            elif key != UNSCOPED and stamp < state.valid_from_ns:
                refusal = STALE
            else:
                if client_id != LEGACY_CLIENT:
                    self._client_control[client_id] = key
                    if key != UNSCOPED:
                        state.clients.add(client_id)
                operation = Operation(self, next(self._ids), key, client_id, kind, detail, state.generation)
                state.operations[operation.operation_id] = operation
            if client_id != LEGACY_CLIENT and (
                refusal == RETIRED and key != UNSCOPED and state.epoch is not None and epoch != state.epoch
                or refusal in (PAUSED, STALE) and state.retiring
            ):
                # An old-run client still talking after its process was replaced or during an
                # intervention: it never gets in again.
                self._retired[client_id] = key
            status = self._status(key)
        if refusal is not None:
            self._emit("operation_refused", key, status, client_id=client_id, kind=kind, detail=detail, error_code=refusal)
            raise ControlRefused(refusal)
        self._emit("operation_started", key, status, operation=operation)
        return operation

    def clients(self, control_id: str) -> list:
        with self._lock:
            state = self._states.get(normalize_control_id(control_id))
            return sorted(state.clients) if state else []

    def open(self, bridge_path: str) -> None:
        with self._lock:
            self.bridge_path = bridge_path
            self._closed = False

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def _recheck(self, operation: Operation) -> None:
        if operation.control_id == UNSCOPED:
            return
        with self._lock:
            state = self._state(operation.control_id)
            if state.revoked:
                refusal = STALE
            elif state.paused:
                refusal = PAUSED
            elif state.generation != operation.generation:
                refusal = STALE
            else:
                return
        raise ControlRefused(refusal)

    def _finish(self, operation: Operation, success: bool, error_code) -> None:
        with self._lock:
            if operation.finished:
                return
            operation.finished = True
            state = self._state(operation.control_id)
            state.operations.pop(operation.operation_id, None)
            status = self._status(operation.control_id)
        self._emit("operation_finished", operation.control_id, status, operation=operation, success=bool(success), error_code=error_code)

    def _scoped(self, control_id) -> str:
        key = normalize_control_id(control_id)
        if key == UNSCOPED:
            raise ValueError("a control_id is required; unscoped clients cannot be paused")
        return key

    def _state(self, key: str) -> _State:
        state = self._states.get(key)
        if state is None:
            state = self._states[key] = _State()
        return state

    def _status(self, key: str) -> dict:
        state = self._state(key)
        return {
            "control_id": key,
            "paused": state.paused,
            "revoked": state.revoked,
            "generation": state.generation,
            "active_operations": len(state.operations),
            "operations": [
                {
                    "operation_id": op.operation_id,
                    "client_id": op.client_id,
                    "kind": op.kind,
                    "started_ns": op.started_ns,
                }
                for op in state.operations.values()
            ],
        }

    def _emit(self, event: str, key: str, status: dict, operation: Operation | None = None, **extra) -> None:
        payload = {
            "event": event,
            "control_id": key,
            "client_id": extra.pop("client_id", operation.client_id if operation else None),
            "operation_id": operation.operation_id if operation else None,
            "kind": extra.pop("kind", operation.kind if operation else None),
            "detail": extra.pop("detail", operation.detail if operation else None),
            "generation": status["generation"],
            "active_operations": status["active_operations"],
            "time_ns": time.monotonic_ns(),
            "wall_time": time.time(),
            "success": extra.pop("success", None),
            "error_code": extra.pop("error_code", None),
            **extra,
        }
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(dict(payload))
            except Exception as exc:
                self.listener_errors.append("%s: %s" % (type(exc).__name__, exc))


_registry: dict[str, BridgeControl] = {}
_registry_lock = threading.Lock()


def _key(bridge_path) -> str:
    return os.path.abspath(os.fspath(bridge_path))


def register(bridge_path, control: BridgeControl) -> BridgeControl:
    """Publish ``control`` (opening it) as the control of the bridge at a discovery path."""
    key = _key(bridge_path)
    control.open(key)
    with _registry_lock:
        previous = _registry.get(key)
        _registry[key] = control
    if previous is not None and previous is not control:
        previous.close()
    return control


def unregister(bridge_path) -> None:
    key = _key(bridge_path)
    with _registry_lock:
        control = _registry.pop(key, None)
    if control is not None:
        control.close()


def get_control(bridge_path) -> BridgeControl | None:
    """The live control of the in-process bridge at ``bridge_path`` (its discovery file), or None.

    None means there is no bridge in this process for that path; callers must treat that as
    "cannot stop anything", not as "nothing is running".
    """
    if bridge_path is None:
        return None
    with _registry_lock:
        return _registry.get(_key(bridge_path))
