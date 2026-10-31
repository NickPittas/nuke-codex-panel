"""Manual steering for agent harnesses: safe interrupt-and-resume plus observational clocks.

A user message sent while the agent is busy (or ``/btw <message>``) is a *manual intervention*,
never a queued follow-up. The sequence is fixed and event driven; nothing in it is a timeout, and
no timer ever interrupts the model:

1. **Barrier.** The harness's bridge execution control is paused at once, with its sidecar
   clients retired (works from a nested Qt event loop). Requests of the old run that have not
   started are refused; an operation that is already executing in Nuke cannot be preempted and
   is allowed to finish.
2. **Drain.** Wait until the bridge counts zero active operations for this control and until
   any Nuke tool call still on its way back to the model has returned (so the transcript does
   not record a completed graph change as an aborted call). A second Cancel skips that wait.
3. **Stop.** Abort the backend run, wait for it to settle, and take back any input still queued
   in the backend, so nothing is delivered twice or resumes by itself.
4. **Renew.** Aborting is not enough: the old MCP sidecar may still hold unread tool calls of
   the stopped run, and a timestamp watermark cannot see bytes it has not read yet. So the old
   transport is never reopened. The bridge fences the old process with a newer process lease
   (``NUKE_CODEX_CONTROL_EPOCH``, enforced per request) and permanently retires its sidecar
   clients; the old agent and its sidecar processes are confirmed gone; Nuke must have zero
   active operations; only then is the control reopened for the *replacement* process, which
   resumes the same persisted session with the same model and effort.
5. **Deliver.** Send the guidance as one prompt to the *same* session. Messages are delivered
   exactly once, in order; whatever was never delivered is handed back to the user.

Cancel runs the same barrier/drain/stop/retire and delivers nothing. When the session cannot be
resumed (not persisted) the agent is only stopped: the control stays retired and closed, nothing
is started, and a later Reconnect launches a new process explicitly. Cancel itself never resumes a
conversation, and a new chat always starts a fresh process.

The controller here is protocol agnostic and Qt free; ``SteeringBackend`` is what a concrete
harness (pi/omp RPC) implements. Everything asynchronous is guarded by an epoch, so a reset,
switch or stop invalidates every callback still in flight.
"""

from __future__ import annotations

import re
import dataclasses
import itertools
import time
import uuid
from typing import Callable

# objectName of the bridge's Python approval dialog (it also carries a ``controlId`` property).
APPROVAL_DIALOG_NAME = "NukeCodexPythonApproval"

IDLE = "idle"
RECEIVED = "received"
WAITING_OPERATION = "waiting_operation"
WAITING_RESULT = "waiting_result"
STOPPING = "stopping"
RECONCILING = "reconciling"
RENEWING = "renewing"
REOPENING = "reopening"
DELIVERING = "delivering"
DELIVERED = "delivered"
CANCELLED = "cancelled"
FAILED = "failed"

# Phases before the guidance prompt has been sent.
ACTIVE_PHASES = (RECEIVED, WAITING_OPERATION, WAITING_RESULT, STOPPING, RECONCILING, RENEWING, REOPENING)
IN_PROGRESS = ACTIVE_PHASES + (DELIVERING,)

# Message states move forward only: received -> waiting -> delivered | withdrawn.
MESSAGE_RECEIVED = "received"
MESSAGE_WAITING = "waiting"
MESSAGE_DELIVERED = "delivered"
MESSAGE_WITHDRAWN = "withdrawn"

MAX_ABORT_ATTEMPTS = 3

# Factual framing for the model, placed before the user's own words (never inside them).
INTERVENTION_NOTICE = (
    "[Manual intervention: the user stopped your previous run to send the message below. "
    "Unfinished steps were stopped; do not assume an interrupted step completed.]"
)

NO_CONTROL_MESSAGE = (
    "Cannot steer: this panel has no local Nuke bridge control, so it cannot guarantee that "
    "Nuke is idle before the old run is stopped. Use Cancel, then send your message again."
)

NO_PERSISTENCE_MESSAGE = (
    "Cannot steer: this session is not persisted, and stopping the old run safely requires "
    "restarting the agent process on the same saved session. Use Cancel, then send your message again."
)


def new_control_id() -> str:
    """Fresh control id (<= 64 chars, the bridge's normalisation limit)."""
    return uuid.uuid4().hex


_NUKE_TOOL_ARGS = re.compile(r"mcp_+nuke|['\"]tool['\"]\s*:\s*['\"](?:mcp_+)?nuke")


def is_nuke_tool(name, args=None) -> bool:
    """Whether an agent tool call is a request to the Nuke bridge.

    pi/omp name MCP tools after their server (``nuke_execute_python``, ``mcp__nuke__...``) or
    reach them through a proxy tool or an ``xd://mcp__nuke...`` path whose arguments name the
    server. Only used to decide whether a finished Nuke result still has to reach the model
    before the run is aborted; a miss just aborts right after the operation finishes, and a
    false hit is released by a second Cancel.
    """
    if "nuke" in str(name or "").lower():
        return True
    return _NUKE_TOOL_ARGS.search(str(args).lower()) is not None if args is not None else False


# ---------------------------------------------------------------------------
# Observational activity clocks
# ---------------------------------------------------------------------------


class ActivityTracker:
    """What the agent is doing, derived only from backend events (never steers anything).

    ``snapshot()`` separates real generation from tool execution, provider retry waits and
    context compaction, so the UI clocks do not report waiting as model work.
    """

    def __init__(self, clock: Callable[[], int] = time.monotonic_ns):
        self._clock = clock
        self.reset()

    def reset(self):
        self.run_open = False
        self.starting = False
        self.stopping = False
        self.run_started_ns: int | None = None
        self.request_started_ns: int | None = None
        self.tools: dict = {}
        self.retry: dict | None = None
        self.compaction: dict | None = None

    # -- inputs ---------------------------------------------------------------

    def note_starting(self):
        if not self.run_open:
            self.starting = True

    def note_stopping(self, stopping: bool):
        self.stopping = stopping

    def tool_started(self, tool_id, name, args=None):
        self.tools[tool_id] = {
            "id": tool_id,
            "tool": name,
            "nuke": is_nuke_tool(name, args),
            "started_ns": self._clock(),
        }

    def tool_ended(self, tool_id):
        self.tools.pop(tool_id, None)

    def nuke_tool_ids(self) -> list:
        return [tool_id for tool_id, tool in self.tools.items() if tool["nuke"]]

    def feed(self, message: dict) -> bool:
        """Apply one backend event; True when the displayable state changed."""
        before = self._signature()
        kind = message.get("type")
        now = self._clock()
        if kind == "agent_start":
            self.run_open = True
            self.starting = False
            self.run_started_ns = now
            self.request_started_ns = now
            self.tools.clear()
            self.retry = None
            self.compaction = None
        elif kind in ("agent_end", "agent_settled", "session_settled"):
            if kind == "agent_settled" or self.run_finished(message):
                self.close_run()
        elif kind == "turn_start":
            self.request_started_ns = now
        elif kind == "message_start":
            if (message.get("message") or {}).get("role") == "assistant" and self.request_started_ns is None:
                self.request_started_ns = now
        elif kind == "message_end":
            if (message.get("message") or {}).get("role") == "assistant":
                self.request_started_ns = None
        elif kind == "turn_end":
            self.request_started_ns = None
        elif kind == "tool_execution_start":
            self.tool_started(message.get("toolCallId"), message.get("toolName", ""), message.get("args"))
        elif kind == "tool_execution_end":
            self.tool_ended(message.get("toolCallId"))
        elif kind == "auto_retry_start":
            delay_ns = int(float(message.get("delayMs") or 0) * 1_000_000)
            self.retry = {
                "attempt": message.get("attempt"),
                "max": message.get("maxAttempts"),
                "delay_ms": message.get("delayMs") or 0,
                "started_ns": now,
                "error": message.get("errorMessage") or "",
            }
            # The retried request starts after the delay; waiting is not generation.
            self.request_started_ns = now + delay_ns
        elif kind == "auto_retry_end":
            self.retry = None
            if self.run_open and self.request_started_ns is None:
                self.request_started_ns = now
        elif isinstance(kind, str) and kind.endswith("compaction_start"):
            self.compaction = {"reason": message.get("reason") or "", "started_ns": now}
        elif isinstance(kind, str) and kind.endswith("compaction_end"):
            self.compaction = None
            if message.get("willRetry") and self.run_open:
                self.request_started_ns = now
        return self._signature() != before

    @staticmethod
    def run_finished(message: dict) -> bool:
        """Whether an ``agent_end`` closes the run (retries and continuations keep it open)."""
        if message.get("willRetry"):
            return False
        if message.get("isTerminal") is False or message.get("yielded") is False:
            return False
        return True

    def close_run(self):
        self.run_open = False
        self.starting = False
        self.stopping = False
        self.request_started_ns = None
        self.tools.clear()
        self.retry = None
        self.compaction = None

    # -- output ---------------------------------------------------------------

    def _state(self, now: int) -> str:
        if not self.run_open:
            return "starting" if self.starting else "idle"
        if self.stopping:
            return "stopping"
        if self.tools:
            return "tool"
        if self.compaction:
            return "compacting"
        if self.request_started_ns is not None:
            if self.retry is not None and now < self.request_started_ns:
                return "retry_wait"
            return "generating"
        return "working"

    def _signature(self):
        return (self.run_open, self.starting, self.stopping, len(self.tools), self.retry is not None,
                self.compaction is not None, self.request_started_ns is not None)

    def snapshot(self) -> dict:
        now = self._clock()
        state = self._state(now)
        request_elapsed = None
        if self.request_started_ns is not None and state != "retry_wait":
            request_elapsed = max(0.0, (now - self.request_started_ns) / 1e9)
        tools = [
            {
                "id": tool["id"],
                "tool": tool["tool"],
                "nuke": tool["nuke"],
                "started_ns": tool["started_ns"],
                "elapsed_s": max(0.0, (now - tool["started_ns"]) / 1e9),
            }
            for tool in self.tools.values()
        ]
        retry = None
        if self.retry is not None:
            delay_ns = int(float(self.retry["delay_ms"]) * 1_000_000)
            retry = dict(self.retry)
            retry["remaining_s"] = max(0.0, (self.retry["started_ns"] + delay_ns - now) / 1e9)
        compaction = None
        if self.compaction is not None:
            compaction = dict(self.compaction)
            compaction["elapsed_s"] = max(0.0, (now - self.compaction["started_ns"]) / 1e9)
        return {
            "state": state,
            "run_started_ns": self.run_started_ns if self.run_open else None,
            "run_elapsed_s": max(0.0, (now - self.run_started_ns) / 1e9)
            if self.run_open and self.run_started_ns is not None
            else None,
            "request_started_ns": self.request_started_ns,
            "request_elapsed_s": request_elapsed,
            "tools": tools,
            "retry": retry,
            "compaction": compaction,
            "nuke_operations": [],
            "now_ns": now,
        }


def format_duration(seconds) -> str:
    seconds = int(max(0, seconds or 0))
    if seconds < 60:
        return "%ds" % seconds
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return "%dm %02ds" % (minutes, secs)
    hours, minutes = divmod(minutes, 60)
    return "%dh %02dm" % (hours, minutes)


def describe_activity(snapshot: dict) -> str:
    """One status line for the run: observational clocks, no raw reasoning."""
    state = snapshot.get("state", "idle")
    if state == "idle":
        return ""
    run = snapshot.get("run_elapsed_s")
    suffix = " · run %s" % format_duration(run) if run is not None else ""
    if state == "starting":
        return "Starting request…"
    if state == "stopping":
        return "Stopping the agent run…%s" % suffix
    if state == "tool":
        tool = max(snapshot.get("tools") or [{"tool": "tool", "elapsed_s": 0}], key=lambda t: t["elapsed_s"])
        text = "Tool %s running %s" % (tool["tool"], format_duration(tool["elapsed_s"]))
        operations = snapshot.get("nuke_operations") or []
        if operations:
            oldest = max(operations, key=lambda op: op.get("elapsed_s", 0))
            text += " (Nuke operation %s executing %s)" % (
                oldest.get("kind") or "?",
                format_duration(oldest.get("elapsed_s", 0)),
            )
        return text + suffix
    if state == "retry_wait":
        retry = snapshot.get("retry") or {}
        return "Provider error; retry %s/%s in %s (not generating)%s" % (
            retry.get("attempt") or "?",
            retry.get("max") or "?",
            format_duration(retry.get("remaining_s", 0)),
            suffix,
        )
    if state == "compacting":
        compaction = snapshot.get("compaction") or {}
        return "Compacting context %s (not generating)%s" % (
            format_duration(compaction.get("elapsed_s", 0)),
            suffix,
        )
    if state == "generating":
        retry = snapshot.get("retry")
        label = "Model request"
        if retry:
            label = "Model request (retry %s/%s)" % (retry.get("attempt") or "?", retry.get("max") or "?")
        return "%s %s%s" % (label, format_duration(snapshot.get("request_elapsed_s")), suffix)
    return "Agent working%s" % suffix


def describe_intervention(state: dict, now_ns: int | None = None) -> str:
    """Status text for a manual intervention: per message received/waiting/delivered, plus phase."""
    phase = state.get("phase", IDLE)
    if phase == IDLE:
        return ""
    now = now_ns if now_ns is not None else time.monotonic_ns()
    lines = []
    for message in state.get("messages") or []:
        preview = " ".join(str(message.get("text", "")).split())
        if len(preview) > 48:
            preview = preview[:47] + "…"
        age = ""
        if message.get("received_ns") is not None:
            age = " (%s ago)" % format_duration((now - message["received_ns"]) / 1e9)
        lines.append("#%s %s%s: %s" % (message.get("id"), message.get("state"), age, preview))
    waiting = state.get("waiting_on") or {}
    sentence = {
        RECEIVED: "Message received; closing Nuke to the old run",
        WAITING_OPERATION: "Waiting for Nuke operation %s (%s) to finish; new tool calls are refused"
        % (waiting.get("kind") or "?", format_duration((now - waiting["started_ns"]) / 1e9) if waiting.get("started_ns") else "0s"),
        WAITING_RESULT: "Waiting for a Nuke tool result or acknowledgement to reach the agent (Cancel again to stop now)",
        STOPPING: "Stopping the agent run; the session and its history are kept",
        RECONCILING: "Reconciling input still queued in the agent",
        RENEWING: "Reconnecting the same conversation (%s)" % (state.get("detail") or "new agent process, same session"),
        REOPENING: "Reopening Nuke tools",
        DELIVERING: "Sending your message to the same session",
        DELIVERED: "Delivered; the agent is resuming",
        CANCELLED: "Cancelled; nothing was resumed",
        FAILED: "Intervention failed: %s" % (state.get("detail") or "unknown error"),
    }.get(phase, phase)
    if state.get("barrier") == "unavailable":
        sentence += "\nNo local Nuke bridge control: Nuke operations cannot be confirmed idle."
    return "\n".join([sentence] + lines)


# ---------------------------------------------------------------------------
# Bridge control handle
# ---------------------------------------------------------------------------

_EMPTY_STATUS = {
    "paused": False,
    "revoked": False,
    "generation": 0,
    "active_operations": 0,
    "operations": [],
}


class ControlLease:
    """A harness's handle on its in-process bridge execution control (stable control id).

    ``resolver`` returns the live control (``bridge.control.get_control(path)``) or None when
    there is no local bridge; None means nothing can be stopped, never "nothing is running".
    """

    def __init__(self, control_id: str, resolver: Callable[[], object | None]):
        self.control_id = control_id
        self._resolver = resolver
        self._control = None
        self._unlisten = None
        self._on_event: Callable[[dict], None] | None = None

    def attach(self, on_event: Callable[[dict], None]) -> bool:
        """Start relaying this control's bridge events to ``on_event``; True when a control exists."""
        self._on_event = on_event
        return self._ensure() is not None

    def detach(self):
        unlisten, self._unlisten = self._unlisten, None
        self._on_event = None
        self._control = None
        if unlisten is not None:
            try:
                unlisten()
            except Exception:
                pass

    def _ensure(self):
        if self._control is None:
            try:
                self._control = self._resolver()
            except Exception:
                self._control = None
        control = self._control
        # The control may have been resolved (by a status read) before anyone attached.
        if control is not None and self._on_event is not None and self._unlisten is None:
            self._unlisten = control.add_listener(self._relay)
        return control

    def _relay(self, event: dict):
        if event.get("control_id") != self.control_id:
            return
        callback = self._on_event
        if callback is not None:
            callback(event)

    @property
    def available(self) -> bool:
        return self._ensure() is not None

    def status(self) -> dict:
        control = self._ensure()
        if control is None:
            return dict(_EMPTY_STATUS, control_id=self.control_id)
        return control.status(self.control_id)

    def pause(self, retire: bool = True) -> dict:
        """Refuse every later request of this control. ``retire`` permanently tombstones the
        sidecar clients seen so far, so that transport can never be reopened (the steering
        controller always retires: the agent process is replaced or stopped afterwards)."""
        control = self._require()
        try:
            return control.pause(self.control_id, retire=retire)
        except TypeError:
            return control.pause(self.control_id)

    def begin_process(self, epoch: int):
        """Make ``epoch`` the only accepted process lease for this control (when the bridge supports it)."""
        control = self._ensure()
        begin = getattr(control, "begin_process", None) if control is not None else None
        if begin is not None:
            begin(self.control_id, epoch)

    def resume(self) -> dict | None:
        """Reopen; None while the bridge still counts an active operation (never forced)."""
        control = self._require()
        try:
            return control.resume(self.control_id)
        except Exception as exc:
            if type(exc).__name__ == "ControlBusy":
                return None
            raise

    def revoke(self) -> dict | None:
        control = self._ensure()
        return control.revoke(self.control_id) if control is not None else None

    def _require(self):
        control = self._ensure()
        if control is None:
            raise RuntimeError("no local Nuke bridge control")
        return control


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Guidance:
    """One user message in the intervention pipeline."""

    id: int
    text: str
    images: list
    received_ns: int
    wall_time: float
    state: str = MESSAGE_RECEIVED
    delivered_ns: int | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "state": self.state,
            "text": self.text,
            "images": len(self.images),
            "image_paths": list(self.images),
            "received_ns": self.received_ns,
            "wall_time": self.wall_time,
            "delivered_ns": self.delivered_ns,
        }


class SteeringBackend:
    """What a harness provides to the controller. Callbacks may complete synchronously."""

    def run_active(self) -> bool:
        """A run is open, starting, or a prompt is in flight."""
        raise NotImplementedError

    def prompt_unacked(self) -> bool:
        """A prompt was sent whose acknowledgement has not arrived (an abort could miss it)."""
        raise NotImplementedError

    def nuke_tools_running(self) -> list:
        """Ids of agent tool calls currently running that are Nuke bridge requests."""
        raise NotImplementedError

    def can_renew_session(self) -> bool:
        """Whether the agent process can be replaced without losing the conversation."""
        raise NotImplementedError

    def barrier_set(self, status: dict):
        """The bridge control was just paused (``status`` is its state)."""

    def abort(self, done: Callable[[dict], None], stage: Callable[[str], None]):
        """Abort the run, wait for it to settle, reconcile queues; ``done({"ok","withdrawn","error"})``."""
        raise NotImplementedError

    def renew(self, fresh_session: bool, done: Callable[..., None], detail: Callable[[str], None],
              restart: bool = True):
        """Replace the agent process (and its MCP sidecar): fence the old one, make sure it and its
        sidecars have exited, then (``restart``) start the replacement on the same persisted
        session, or a fresh one, with the selected model/effort reapplied. Without ``restart`` the
        agent is only stopped and stays stopped (the bridge stays closed). ``done(ok, error=None)``."""
        raise NotImplementedError

    def deliver(self, batch: list, done: Callable[..., None]):
        """Send the batch as one prompt to the same session; ``done(ok, error=None)`` at acknowledgement."""
        raise NotImplementedError

    def withdraw(self, items: list, reason: str):
        """Hand undelivered input back to the user."""

    def report_error(self, text: str):
        pass

    def run_interrupted(self):
        """The old run was stopped on purpose (close its UI turn once)."""


class SteeringController:
    """Safe interrupt-and-resume state machine; see the module docstring."""

    def __init__(
        self,
        backend: SteeringBackend,
        lease: ControlLease,
        emit: Callable[[dict], None],
        clock: Callable[[], int] = time.monotonic_ns,
        wall: Callable[[], float] = time.time,
    ):
        self._backend = backend
        self._lease = lease
        self._emit = emit
        self._clock = clock
        self._wall = wall
        self._message_ids = itertools.count(1)
        self._intervention_ids = itertools.count(1)
        self._epoch = 0
        self._advancing = False
        self._again = False
        self.phase = IDLE
        self.detail = ""
        self._action: str | None = None
        self._intervention_id = 0
        self._resume = False
        self._messages: list[Guidance] = []   # accepted, not yet sent, oldest first
        self._visible: list[Guidance] = []    # this intervention's messages, for display
        self._deferred: list[Guidance] = []   # received while the prompt was being delivered
        self._inflight: list[Guidance] = []   # sent, acknowledgement pending
        self._deferred_cancel = False
        self._deferred_reset = False
        self._barrier = "none"
        # The old agent process is always replaced or stopped after an intervention: the bridge
        # retires its sidecar clients for good, so that transport can never be reopened.
        self._retire = True
        # Cancel of a session that cannot be resumed: the agent is stopped and stays stopped.
        self._stop_only = False
        self._waiting_on: dict | None = None
        self._force = False
        self._cancel_presses = 0
        self._renew_started = False
        self._renew_fresh = False
        # A stop failed: the old process may still be running; the next step must replace it.
        self._needs_renewal = False

    # -- queries --------------------------------------------------------------

    @property
    def active(self) -> bool:
        return self.phase in IN_PROGRESS

    @property
    def dirty(self) -> bool:
        """A failed intervention left the bridge closed to a process that must still be replaced."""
        return not self.active and self._needs_renewal

    def next_message_id(self) -> int:
        """Ids are shared with messages sent while idle so every user message has one order."""
        return next(self._message_ids)

    def pending(self) -> list:
        return [m.as_dict() for m in self._messages + self._inflight + self._deferred]

    def snapshot(self) -> dict:
        now = self._clock()
        return {
            "phase": self.phase,
            "intervention_id": self._intervention_id,
            "action": self._action,
            "resume": self._resume,
            "detail": self.detail,
            "barrier": self._barrier,
            "renews_process": not self._stop_only,
            "stop_only": self._stop_only,
            "time_ns": now,
            "now_ns": now,
            "wall_time": self._wall(),
            "waiting_on": dict(self._waiting_on) if self._waiting_on else None,
            "messages": [m.as_dict() for m in self._visible + self._deferred],
        }

    # -- public entry points ----------------------------------------------------

    def submit(self, text: str, images=None) -> int | None:
        """A user message while the agent is busy. Returns its id, or None when refused."""
        text = (text or "").strip()
        if not text:
            return None
        if self.active and self._action == "reset":
            self._backend.report_error("A new chat is starting; send your message once it has started.")
            return None
        if not self.active:
            if not self._lease.available:
                self._backend.report_error(NO_CONTROL_MESSAGE)
                return None
            if not self._backend.can_renew_session():
                self._backend.report_error(NO_PERSISTENCE_MESSAGE)
                return None
        message = self._new_message(text, images)
        if self.phase == DELIVERING:
            # The previous batch is already on the wire; this is a fresh intervention afterwards.
            self._deferred.append(message)
            self._publish()
            return message.id
        if self.active:
            self._messages.append(message)
            self._visible.append(message)
            if self._action == "cancel":
                if self._stop_only:
                    # This Cancel stops an agent whose session cannot be resumed; steering needs one.
                    self._messages.remove(message)
                    self._visible.remove(message)
                    self._backend.report_error(NO_PERSISTENCE_MESSAGE)
                    return None
                # Cancel followed by guidance is an intervention after all.
                self._action = "steer"
                self._resume = True
                self._cancel_presses = 0
            self._publish()
            self._advance()
            return message.id
        self._begin("steer", [message])
        return message.id

    def cancel(self) -> bool:
        """Cancel: stop the run safely, deliver nothing, never resume. False when nothing to cancel."""
        if self.phase == DELIVERING:
            self._deferred_cancel = True
            self._publish()
            return True
        if self.active:
            if self._action == "reset":
                return True  # the reset already stops the run
            self._withdraw(self._messages, "cancelled before delivery")
            self._messages = []
            self._action = "cancel"
            self._resume = False
            self._cancel_presses += 1
            if self._cancel_presses > 1:
                # Second press: stop waiting for a tool result or acknowledgement. The bridge
                # stays paused and the operation count is still honoured before it reopens.
                self._force = True
            self._publish()
            self._advance()
            return True
        if not self._backend.run_active() and not self.dirty:
            return False
        self._cancel_presses = 1
        self._begin("cancel", [])
        return True

    def begin_reset(self) -> bool:
        """New chat: stop any run safely, then start a fresh session. Input is not carried over."""
        self._withdraw(self._messages + self._deferred, "a new chat was started")
        self._messages = []
        self._deferred = []
        self._deferred_cancel = False
        if self.phase == DELIVERING:
            self._deferred_reset = True  # the prompt is already on the wire; reset right after
            return True
        if self.active:
            self._action = "reset"
            self._resume = False
            self._stop_only = False  # a new chat always starts a fresh process
            self._publish()
            self._advance()
            return True
        self._begin("reset", [])
        return True

    def shutdown(self, reason: str):
        """Stop/restart/close/process death: invalidate every callback in flight; hand input back."""
        self._epoch += 1
        self._withdraw(self._messages + self._inflight + self._deferred, reason)
        self._messages = []
        self._inflight = []
        self._deferred = []
        self._deferred_cancel = False
        self._deferred_reset = False
        self._needs_renewal = False
        self._waiting_on = None
        was_active = self.phase != IDLE
        self.phase = IDLE
        self.detail = reason
        if was_active:
            self._publish()

    def on_control_event(self, event: dict):
        if self.active:
            self._advance()

    def on_backend_progress(self):
        """A tool ended or a prompt was acknowledged: re-evaluate waiting phases."""
        if self.active:
            self._advance()

    def on_run_started(self):
        if self.phase == FAILED and not self.dirty:
            self.phase = IDLE
            self.detail = ""
            self._publish()

    def on_run_ended(self):
        if self.active:
            self._advance()

    def recheck(self):
        """Re-read the bridge (a safety net for a missed event); never changes policy."""
        if self.active:
            self._advance()

    # -- internals --------------------------------------------------------------

    def _new_message(self, text, images) -> Guidance:
        return Guidance(
            id=self.next_message_id(),
            text=text,
            images=list(images or []),
            received_ns=self._clock(),
            wall_time=self._wall(),
        )

    def _begin(self, action: str, messages: list):
        self._epoch += 1
        self._intervention_id = next(self._intervention_ids)
        self._action = action
        self._resume = action == "steer"
        self._messages = list(messages)
        self._visible = list(messages)
        self._barrier = "none"
        self._stop_only = False
        self._waiting_on = None
        self._force = False
        self._renew_started = False
        self._renew_fresh = False
        self.detail = ""
        self.phase = RECEIVED
        self._publish()
        self._advance()

    def _publish(self):
        self._emit(self.snapshot())

    def _set_phase(self, phase: str, detail: str = ""):
        if phase == self.phase and detail == self.detail:
            return
        self.phase = phase
        self.detail = detail
        self._publish()

    def _mark_waiting(self):
        changed = False
        for message in self._messages:
            if message.state == MESSAGE_RECEIVED:
                message.state = MESSAGE_WAITING
                changed = True
        if changed:
            self._publish()

    def _guard(self, epoch: int, function, *args):
        """Run an asynchronous continuation unless a reset/stop/new intervention outdated it."""
        if epoch != self._epoch:
            return
        function(*args)
        self._advance()

    def _advance(self):
        if self._advancing:
            self._again = True
            return
        self._advancing = True
        try:
            while True:
                self._again = False
                self._step()
                if not self._again:
                    break
        finally:
            self._advancing = False

    def _step(self):
        if self.phase == RECEIVED:
            self._take_barrier()
        if self.phase in (WAITING_OPERATION, WAITING_RESULT):
            self._mark_waiting()
            self._drain()
        if self.phase == RENEWING and not self._renew_started:
            self._start_renewal()
        if self.phase == REOPENING:
            self._reopen()

    def _take_barrier(self):
        # Every intervention ends by replacing or stopping the agent process, so the bridge
        # retires the old sidecar's clients for good (they can never be reopened).
        self._stop_only = self._action == "cancel" and not self._backend.can_renew_session()
        if self._lease.available:
            status = self._lease.pause(retire=True)
            self._barrier = "set"
            self._backend.barrier_set(status)
        else:
            # Cancel/reset still work, but nothing can confirm Nuke is idle: say so.
            self._barrier = "unavailable"
        self.phase = WAITING_OPERATION
        self.detail = ""
        self._publish()
        self._again = True

    def _active_operations(self) -> list:
        if self._barrier != "set":
            return []
        return list(self._lease.status().get("operations") or [])

    def _drain(self):
        operations = self._active_operations()
        if operations:
            first = min(operations, key=lambda op: op.get("started_ns") or 0)
            self._waiting_on = {
                "kind": first.get("kind"),
                "operation_id": first.get("operation_id"),
                "started_ns": first.get("started_ns"),
            }
            self._set_phase(WAITING_OPERATION, "waiting for Nuke operation %s" % first.get("kind"))
            return
        self._waiting_on = None
        if not self._force and not self._needs_renewal:
            # A finished Nuke result (or a refusal) is still on its way to the model; aborting
            # now would record a completed graph change as an aborted call.
            if self._backend.nuke_tools_running():
                self._set_phase(WAITING_RESULT, "waiting for a Nuke tool result to reach the agent")
                return
            # An abort sent before the previous prompt was acknowledged could miss that run.
            if self._backend.prompt_unacked():
                self._set_phase(WAITING_RESULT, "waiting for the agent to acknowledge the previous message")
                return
        if self._needs_renewal or not self._backend.run_active():
            # Nothing to abort (the run ended by itself, or a previous abort failed and the
            # process is about to be replaced anyway).
            self._after_stop()
            return
        self._set_phase(STOPPING, "stopping the agent run")
        epoch = self._epoch
        self._backend.abort(
            lambda result: self._guard(epoch, self._abort_done, result),
            lambda stage: self._guard(epoch, self._abort_stage, stage),
        )

    def _abort_stage(self, stage: str):
        if self.phase in (STOPPING, RECONCILING) and stage in (STOPPING, RECONCILING):
            self._set_phase(stage, self.detail)

    def _abort_done(self, result: dict):
        withdrawn = result.get("withdrawn") or []
        if withdrawn:
            self._backend.withdraw(withdrawn, "queued in the agent and never delivered")
        if not result.get("ok"):
            self._fail(
                "could not stop the agent run: %s. Nuke tools stay paused until the agent process is replaced."
                % (result.get("error") or "unknown error"),
                needs_renewal=True,
            )
            return
        self._backend.run_interrupted()
        self._after_stop()

    def _after_stop(self):
        self._renew_started = False
        self._set_phase(
            RENEWING,
            "stopping the agent process; this session cannot be resumed, so it stays stopped"
            if self._stop_only
            else "stopping the old agent process",
        )
        self._again = True

    def _start_renewal(self):
        self._renew_started = True
        self._renew_fresh = self._action == "reset"
        epoch = self._epoch
        self._backend.renew(
            self._renew_fresh,
            lambda ok, error=None: self._guard(epoch, self._renewed, ok, error),
            lambda text: self._guard(epoch, self._renew_detail, text),
            restart=not self._stop_only,
        )

    def _renew_detail(self, text: str):
        if self.phase == RENEWING:
            self._set_phase(RENEWING, text)

    def _renewed(self, ok: bool, error):
        if not ok:
            self._fail(
                "could not %s the agent process: %s"
                % ("stop" if self._stop_only else "replace", error or "unknown error"),
                needs_renewal=True,
            )
            return
        self._needs_renewal = False
        if self._stop_only:
            # Stopped for good: the bridge stays retired and closed; a later Reconnect starts a
            # new process explicitly. Cancel itself never resumes a conversation.
            self._conclude(CANCELLED)
            return
        if self._action == "reset" and not self._renew_fresh:
            # A new chat was requested while a same-session renewal ran: replace it once more.
            self._renew_started = False
            self._set_phase(RENEWING, "starting a fresh session")
            self._again = True
            return
        self._set_phase(REOPENING, "")
        self._again = True

    def _reopen(self):
        """Open the bridge to the (new) process; Nuke must be idle first, never forced."""
        if self._barrier == "set":
            status = self._lease.resume()
            if status is None:
                self._set_phase(REOPENING, "waiting for a Nuke operation to finish before reopening tools")
                return
        if self._action == "steer" and self._resume and self._messages:
            self._deliver()
            return
        self._conclude(CANCELLED if self._action == "cancel" else IDLE)

    def _deliver(self):
        batch, self._messages = self._messages, []
        self._inflight = batch
        self._set_phase(DELIVERING, "")
        epoch = self._epoch
        self._backend.deliver(batch, lambda ok, error=None: self._guard(epoch, self._delivered, batch, ok, error))

    def _delivered(self, batch: list, ok: bool, error):
        self._inflight = []
        if not ok:
            self._withdraw(batch, "the agent rejected it: %s" % (error or "unknown error"))
            self._fail("the agent did not accept your message: %s" % (error or "unknown error"))
            return
        now = self._clock()
        for message in batch:
            message.state = MESSAGE_DELIVERED
            message.delivered_ns = now
        self._conclude(DELIVERED)

    def _conclude(self, terminal: str):
        """Publish the terminal phase once, fall back to idle, then start any deferred follow-up."""
        self._waiting_on = None
        if terminal != IDLE:
            self.phase = terminal
            self.detail = ""
            self._publish()
        deferred, self._deferred = self._deferred, []
        cancel, self._deferred_cancel = self._deferred_cancel, False
        reset, self._deferred_reset = self._deferred_reset, False
        self.phase = IDLE
        self.detail = ""
        self._publish()
        if reset:
            self._begin("reset", [])
        elif deferred:
            self._begin("steer", deferred)
        elif cancel and self._backend.run_active():
            self._cancel_presses = 1
            self._begin("cancel", [])

    def _fail(self, reason: str, needs_renewal: bool = False):
        self._withdraw(self._messages + self._deferred, "the intervention failed")
        self._messages = []
        self._deferred = []
        self._deferred_cancel = False
        self._deferred_reset = False
        self._waiting_on = None
        self._needs_renewal = needs_renewal
        self._backend.report_error("Steering failed: %s" % reason)
        self.phase = FAILED
        self.detail = reason
        self._publish()

    def _withdraw(self, messages: list, reason: str):
        items = []
        for message in messages:
            if message.state in (MESSAGE_DELIVERED, MESSAGE_WITHDRAWN):
                continue
            message.state = MESSAGE_WITHDRAWN
            items.append(message.as_dict())
        if items:
            self._backend.withdraw(items, reason)
