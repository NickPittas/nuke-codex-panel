"""Harness client for the managed official Pi over `--mode rpc`.

Besides plain turns this client implements *manual steering*: a message sent while the agent is
busy stops the old work safely and resumes the same conversation with that message (see
``intervention``). It never uses the protocol's ``followUp``/``steer`` queues for that; those
deliver only after the whole agent run (followUp) or after the current tool batch (steer), and
cannot stop a long generation or a long tool call.

Safe stopping needs more than ``abort``: the MCP sidecar of the old run can still hold unread
tool calls that would run the moment the bridge reopens. So a manual intervention ends by
*renewing the agent process* (and thereby its sidecar) on the same persisted session, behind a
per-process lease the bridge enforces (``NUKE_CODEX_CONTROL_EPOCH``). That is process renewal,
not a new conversation: session id, session directory, history, model and effort are kept.

Changed stored Pi accounts (``pi_auth.accounts_changed``) reach the managed Pi the same way, but
only when it is idle: the agent reads credentials and the model catalog once at startup and the
RPC cannot reload them, so an idle renewal is how a change is applied (see ``refresh_accounts``).
A run or steering step in progress is never interrupted for it. Whichever launch loads a changed
account revision (Reconnect, a normal start or any renewal), the model list the UI shows is then
replaced by that agent's catalog, an empty one included, once a model query has succeeded.
"""

from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
import time
import uuid

from PySide6 import QtCore, QtWidgets

from .base import JsonlProcessClient, compact_summary, encode_image
from .intervention import (
    APPROVAL_DIALOG_NAME,
    INTERVENTION_NOTICE,
    MAX_ABORT_ATTEMPTS,
    ActivityTracker,
    ControlLease,
    SteeringBackend,
    SteeringController,
    is_nuke_tool,
)
from . import nuke_mcp, pi_auth
from .. import chat_store, pi_runtime
from ..process_ownership import (
    CONTROL_EPOCH_ENV,
    KILL,
    TERM,
    ProcessOwnershipError,
    lease_processes,
    process_alive,
    signal_processes,
)


PI_NATIVE_MCP_GUIDANCE = (
    "\n\nNuke tools (namespace mcp__nuke) are declared to you directly and stay available for "
    "the whole session, including after steering; call them by name, or from codemode via "
    "tools.mcp__nuke__<name>(). Use describeTool() in codemode if you need an input schema. "
    "Only codemode, tool_search and mcp__nuke tools exist (no host read tool); the runtime "
    "extension delivers full failure payloads, caught API errors and images to you. Await each "
    "dependent Nuke mutation, then read fresh graph/context/image state before the next one; "
    "never use Promise.all for dependent mutations. When a script relies on documentation or "
    "API evidence, print it. For large output, filter or use the codemode structured result "
    "instead of trying to read a file."
)


# Pi's own built-in code tools stay off: the model reaches Nuke only through codemode / MCP.
_PI_EXCLUDED_TOOLS = "read,bash,edit,write,grep,find,ls,powershell"
_PI_TOOLS = "codemode,tool_search,mcp__nuke__*"
# How long a fresh agent may take to declare every Nuke tool before the panel reports an error.
_TOOLS_READY_SECONDS = 60.0
# Prefix of the owned /nuke_tools command's compact notify reply (must match runtime/pi/nuke-runtime.ts).
_TOOLS_REPLY_PREFIX = "nuke-tool-readiness:"


def managed_pi_dir() -> Path:
    """Private Pi agent dir, under the app-data dir next to the chats (never ``~/.pi``)."""
    return chat_store.chats_root().parent / "pi"


# Presentation-only copies of tool arguments/results for the chat. The model's own tool results are
# never touched; image bytes are never copied here (the exact delivered images arrive separately).
_PRESENT_STRING_LIMIT = 400_000
_PRESENT_DEPTH_LIMIT = 24


def _present_value(value, depth: int = 0):
    """JSON-safe copy of ``value`` with image payloads reduced to metadata and giant strings capped."""
    if depth > _PRESENT_DEPTH_LIMIT:
        return "…"
    if isinstance(value, dict):
        if value.get("type") == "image" and ("data" in value or "source" in value):
            data = value.get("data")
            return {
                "type": "image",
                "mimeType": value.get("mimeType") or value.get("mime_type"),
                "base64_chars": len(data) if isinstance(data, str) else None,
            }
        return {str(key): _present_value(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_present_value(item, depth + 1) for item in value]
    if isinstance(value, str):
        if len(value) > _PRESENT_STRING_LIMIT:
            return value[:_PRESENT_STRING_LIMIT] + "… [%d more characters]" % (len(value) - _PRESENT_STRING_LIMIT)
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _present_result(result):
    """Structured, image-free copy of a tool result (None when the agent sent none)."""
    if result is None:
        return None
    return _present_value(result)


def _result_text(result) -> str:
    """The text blocks of a tool result, joined (the model-visible text; images contribute nothing)."""
    if not isinstance(result, dict):
        return ""
    return " ".join(
        block.get("text", "")
        for block in result.get("content") or []
        if isinstance(block, dict) and isinstance(block.get("text", ""), str)
    )


def _read_private_json(path: Path) -> dict:
    """Existing JSON object, or {} when absent. Unreadable/invalid fails closed (never overwritten)."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    config = json.loads(text)
    if not isinstance(config, dict):
        raise ValueError("%s is not a JSON object" % path)
    return config


def _write_private_json(path: Path, config: dict) -> None:
    """Atomic 0600 write through a unique exclusive temp file in the same directory."""
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(config, indent=2) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _queue_item(entry) -> dict:
    """A message the agent still had queued, as a withdrawn-guidance record."""
    if isinstance(entry, dict):
        return {"id": None, "text": str(entry.get("text", "")), "image_paths": [],
                "images_dropped": len(entry.get("images") or []), "source": "agent_queue"}
    return {"id": None, "text": str(entry), "image_paths": [], "source": "agent_queue"}


class PiRpcClient(JsonlProcessClient):
    """The plugin-owned private Node + official Pi, driven over the JSONL RPC protocol."""

    supports_steering = True

    # The agent refused a model selection (payload: model id): the UI must forget it as applied.
    model_selection_failed = QtCore.Signal(str)
    # Bridge control events arrive on whichever thread the bridge runs on; this signal (queued
    # connection) hands them to the GUI thread, after the call that produced them has returned.
    _control_event = QtCore.Signal(dict)
    # Queued self-signal: re-checks for a pending stored-account change outside the caller's stack.
    _accounts_check = QtCore.Signal()
    # Managed Pi only: the client itself changed the desired model (new chat default, a saved
    # shortlist that removed the current model, ...). Payload: the new model id, "" when none.
    selected_model_changed = QtCore.Signal(str)
    # Managed Pi only: the model catalog or the private shortlist/default changed.
    model_preferences_changed = QtCore.Signal()

    def __init__(self, cwd: str, parent=None, bridge_path: str | None = None):
        super().__init__(cwd, parent, bridge_path)
        self.agent_dir = managed_pi_dir()
        self.name = "pi"
        self.label = "Pi"
        self.binary_label = "Pi runtime"
        self.env_var = ""
        # A run is open: agent_start .. final agent_end/agent_settled.
        self._busy = False
        # A prompt was sent (or acknowledged) but its run has not started yet.
        self._starting = False
        self._unacked = 0
        # An abort of the current run is in progress or was requested for it.
        self._interrupted_run = False
        # While a new chat replaces the session, the old run's late events must not reach the chat.
        self._ui_muted = False
        self._thinking_levels: list[str] = []
        self._supports_thinking = True
        self._content_index = -1
        # Managed Pi only: (private Node, official Pi entry) of the current launch.
        self._runtime: tuple[Path, Path] | None = None
        self.session_id: str | None = None
        self.session_file: str | None = None
        self.session_dir: Path | None = None
        self._models_signature: list | None = None
        # The model/effort the user selected; reapplied after every process renewal.
        self._selected_model: str | None = None
        self._selected_thinking: str | None = None
        # Set while the selected model/effort is not yet ACKed on the running session; calling it
        # re-applies the selection (user retry). None once confirmed or on a fresh process.
        self._gate_retry = None
        self._gate_generation = 0
        # Single-flight apply of the desired model/effort: at most one set_model/set_thinking
        # chain runs; picks made meanwhile only mark it "again" so the LATEST desire wins.
        self._gate_running = False
        self._gate_again = False
        self._gate_report = None
        self._renewal_report = None
        # Managed Pi only. The unfiltered catalog of the running agent; the shortlist/default live
        # solely in the private settings.json. ``_selection_block`` is the reason the desired model
        # may not be applied (never silently replaced); Send stays off until the user picks again.
        self._full_models: list[dict] = []
        self._full_signature: list | None = None
        self._selection_block: str | None = None
        # Managed Pi: the model get_state reports for the running session (or the last ACKed
        # set_model), "provider/id"; unknown until the first state reply of this process.
        self._session_model: str | None = None
        self._state_known = False
        self.model_preferences_error: str | None = None
        # Managed Pi only. Stored-account changes announced for this agent dir bump the revision;
        # ``_auth_applied`` is the newest revision a launch (or a renewal attempt) accounts for.
        # Pending = newer than that; ``_auth_notified`` limits the "applied later" notice to once.
        # ``_auth_loaded`` is the newest revision a launch really loaded; ``_auth_published`` the
        # newest whose model catalog the UI has received (a successful get_available_models).
        self._auth_revision = 0
        self._auth_applied = 0
        self._auth_notified = 0
        self._auth_loaded = 0
        self._auth_published = 0
        # Number of agent processes launched so far: the lease the bridge accepts requests from.
        self.process_epoch = 0
        self._announced_epoch = 0
        # True after a Cancel stopped an agent whose session cannot be resumed: it stays stopped
        # (bridge retired and closed) until the user reconnects, which starts a new session.
        self.parked = False
        # Set while the process is being replaced for a manual intervention.
        self._renewal: dict | None = None
        self._activity = ActivityTracker()
        self._activity_signature = None
        self._control_provider = self._default_control
        self._control_opened = False
        self._reopen_pending = False
        self._tools_probing = False
        # The process epoch whose Nuke tools were verified (readiness runs once per process; later
        # catalog/state/levels callbacks must never re-enter it). 0 = none.
        self._tools_verified_epoch = 0
        # Who chose ``_selected_model``: "human" (explicit set_model), "default" (configured private
        # default) or "sdk" (the actual state Pi reported). Only a non-human choice is provisional:
        # it is dropped when a process restarts or a stored session is resumed.
        self._selection_origin: str | None = None
        # Managed Pi: the effort get_state reports for the running session.
        self._session_thinking: str | None = None
        # Tool executions in flight (id -> name) and the activity label last published.
        self._running_tools: dict = {}
        self._activity_status: str | None = None
        # A new chat arrived while a non-steering renewal (accounts/preferences) was running.
        self._fresh_after_renewal = False
        # A new chat's replacement process has not yet ACKed its tools/model/effort: not a provider
        # turn, so the panel must not offer "Steer" for it.
        self._fresh_pending = False
        self._tools_probe: dict | None = None
        self._lease = ControlLease(self.control_id, lambda: self._control_provider())
        self._steering = SteeringController(_PiBackend(self), self._lease, self._publish_intervention)
        self._intervention_state = self._decorated(self._steering.snapshot())
        self._control_event.connect(self._on_control_event, QtCore.Qt.ConnectionType.QueuedConnection)
        # Re-reads the bridge while a steering step waits (a safety net for a missed event);
        # it never changes what the model does and is not a deadline.
        self._recheck_timer = QtCore.QTimer(self)
        self._recheck_timer.setInterval(500)
        self._recheck_timer.timeout.connect(self._on_recheck)
        # Polls the old agent's sidecar processes until they have really exited (there is no
        # event for a process that is not our child); it only observes and ends them.
        self._reap_timer = QtCore.QTimer(self)
        self._reap_timer.setInterval(100)
        self._reap_timer.timeout.connect(self._poll_reap)
        self._accounts_check.connect(self._apply_account_changes, QtCore.Qt.ConnectionType.QueuedConnection)
        pi_auth.accounts_changed.connect(self._on_accounts_changed)

    # -- identity ------------------------------------------------------------

    def _default_control(self):
        if not self.bridge_path:
            return None
        from ..bridge.control import get_control

        return get_control(self.bridge_path)

    def resolve_program(self) -> str | None:
        runtime = self._runtime
        if runtime is None:
            try:
                runtime = pi_runtime.resolve_runtime()
            except (RuntimeError, OSError):
                return None
        return str(runtime[0])

    def system_prompt(self) -> str:
        return super().system_prompt() + PI_NATIVE_MCP_GUIDANCE

    def launch_arguments(self) -> list[str]:
        args = self._managed_arguments()
        if self.session_dir is not None:
            args.extend(["--session-dir", str(self.session_dir)])
            if self.session_id:
                # pi creates the session when the id is unknown, so this doubles
                # as "resume if it exists, otherwise start clean under a stable id".
                args.extend(["--session-id", self.session_id])
        else:
            args.append("--no-session")
        return args

    def _managed_arguments(self) -> list[str]:
        """Official Pi entry with its own prompt, no discovered resources, and a closed tool set."""
        entry = self._runtime[1]
        args = [str(entry)]
        if Path(entry).name != "rpc-entry.js":
            args.extend(["--mode", "rpc"])
        args.extend(["--system-prompt", self.system_prompt()])
        # Nothing is discovered from global/project locations; only these extensions load.
        args.extend(["--no-extensions", "--no-skills", "--no-prompt-templates", "--no-context-files", "--no-themes"])
        args.extend(["--no-approve"])
        for extension in ("builtin:mcp", "builtin:codemode", "builtin:tool-search", str(pi_runtime.DIAGNOSTICS_PATH)):
            args.extend(["-e", extension])
        args.extend(["--tools", _PI_TOOLS, "--exclude-tools", _PI_EXCLUDED_TOOLS])
        return args

    def launch_environment(self) -> dict[str, str] | None:
        env = super().launch_environment() or {}
        # The bridge accepts tool requests only from the newest process of this client.
        env[CONTROL_EPOCH_ENV] = str(self.process_epoch)
        env.update(pi_runtime.managed_environment(self.agent_dir))
        return env

    def environment_removals(self, names: list[str]) -> list[str]:
        """Drop inherited provider keys, cloud selectors and ambient Pi/Node controls."""
        return pi_runtime.managed_environment_removals(names)

    def session_state(self) -> dict:
        return {"session_id": self.session_id, "session_file": self.session_file}

    def resume_session(self, state: dict):
        super().resume_session(state)
        self.session_id = (state or {}).get("session_id") or None
        self.session_file = (state or {}).get("session_file") or None

    # -- steering surface -------------------------------------------------------

    @property
    def busy(self) -> bool:
        return (
            self._busy
            or self._starting
            or self._unacked > 0
            or self._steering.active
            or self._steering.dirty
        )

    @property
    def selection_block(self) -> str | None:
        """Why the desired model is not applied (None when it is usable); never a Signal."""
        return self._selection_block

    @property
    def fresh_pending(self) -> bool:
        """True while a NEW conversation's process is being replaced/started and not yet ready.

        Distinct from a real provider turn or manual steering: ``busy`` is also true here (the
        reset fences the old process), but there is nothing to steer and Send must stay off until
        the new process has its Nuke tools and model/effort ACKed.
        """
        return bool(self._fresh_pending or self._fresh_after_renewal)

    def intervention_state(self) -> dict:
        return dict(self._intervention_state)

    def pending_guidance(self) -> list[dict]:
        return self._steering.pending()

    def can_renew_session(self) -> bool:
        """Whether the process can be replaced and still resume this very conversation.

        Pi reopens (or creates) a session by id.
        """
        if self.session_dir is None:
            return False
        return bool(self.session_id)

    def activity_snapshot(self) -> dict:
        snapshot = self._activity.snapshot()
        if self._lease.available:
            now = snapshot["now_ns"]
            snapshot["nuke_operations"] = [
                {
                    "operation_id": op.get("operation_id"),
                    "kind": op.get("kind"),
                    "started_ns": op.get("started_ns"),
                    "elapsed_s": max(0.0, (now - (op.get("started_ns") or now)) / 1e9),
                }
                for op in self._lease.status().get("operations") or []
            ]
        return snapshot

    def _decorated(self, snapshot: dict) -> dict:
        snapshot["control_id"] = self.control_id
        snapshot["process_epoch"] = self.process_epoch
        return snapshot

    def _publish_intervention(self, snapshot: dict):
        self._intervention_state = self._decorated(snapshot)
        if self._steering.active:
            if not self._recheck_timer.isActive():
                self._recheck_timer.start()
        else:
            self._recheck_timer.stop()
        self.intervention_changed.emit(self._intervention_state)
        if not self._steering.active:
            self._schedule_account_check()

    def _emit_activity(self, force: bool = False):
        snapshot = self.activity_snapshot()
        signature = (snapshot["state"], len(snapshot["tools"]), len(snapshot["nuke_operations"]),
                     self.busy)
        if force or signature != self._activity_signature:
            self._activity_signature = signature
            self.activity_changed.emit(snapshot)
        self._schedule_account_check()

    # -- bridge control lifecycle ---------------------------------------------------

    def _open_control(self):
        """Attach to the bridge control, lease it to this process, and reopen its tool requests."""
        self._control_opened = False
        self._reopen_pending = False
        if not self._lease.attach(self._control_event.emit):
            return
        self._control_opened = True
        try:
            self._announce_epoch(self.process_epoch)
        except Exception as exc:
            self.status_changed.emit("%s: Nuke control lease failed: %s" % (self.label, exc))
        self._reopen_control()

    def _announce_epoch(self, epoch: int):
        """Tell the bridge which process lease is current: older sidecars are refused for good."""
        if epoch > self._announced_epoch:
            self._lease.begin_process(epoch)
            self._announced_epoch = epoch

    def _reopen_control(self):
        try:
            status = self._lease.resume()
        except Exception as exc:
            self.status_changed.emit("%s: Nuke control could not be reopened: %s" % (self.label, exc))
            return
        self._reopen_pending = status is None
        if self._reopen_pending:
            self.status_changed.emit(
                "%s: a Nuke operation from the previous session is still running; "
                "Nuke tools reopen when it finishes" % self.label
            )

    def _close_control(self):
        """End this client's lease: nothing from the stopped process may run any more."""
        if self._control_opened:
            try:
                self._lease.revoke()
            except Exception:
                pass
        self._control_opened = False
        self._reopen_pending = False
        self._lease.detach()

    @QtCore.Slot(dict)
    def _on_control_event(self, event: dict):
        if self._stopping and self._renewal is None:
            return
        name = event.get("event")
        if name == "paused":
            self._reject_approval_dialogs()
        if self._reopen_pending and name == "operation_finished":
            self._reopen_control()
        self._retry_renewal_reopen()
        self._steering.on_control_event(event)
        self._emit_activity()

    def _reject_approval_dialogs(self):
        """A paused control must not sit behind an open Python approval dialog."""
        for widget in QtWidgets.QApplication.topLevelWidgets():
            if widget.objectName() == APPROVAL_DIALOG_NAME and widget.property("controlId") == self.control_id:
                widget.reject()

    # -- lifecycle ---------------------------------------------------------------

    def start(self):
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            return
        self._reset_runtime(keep_mute=self._renewal is not None)
        self.parked = False
        self.process_epoch += 1
        self._tools_probing = False
        if self._renewal is None and self._selection_origin != "human":
            # A provisional choice (configured default / adopted SDK state) belongs to the previous
            # launch: the new process decides again (default for fresh chats, restored state on resume).
            self._selected_model = None
            self._selection_block = None
            self._selection_origin = None
        self._open_control()
        if not self._prepare_runtime():
            self._close_control()
            return
        super().start()

    def stop(self, restart: bool = False):
        self._teardown_runtime("%s stopped" % self.label)
        self._close_control()
        super().stop(restart)

    def _on_finished(self, exit_code, status):
        if not self._stopping:
            # The process died on its own: nothing it had in flight can complete.
            self._teardown_runtime("%s exited" % self.label)
            self._close_control()
        renewing = self._stopping and self._renewal is not None and self._renewal["stage"] == "stopping"
        super()._on_finished(exit_code, status)
        if renewing:
            # Not from inside QProcess.finished: the replacement is started from a clean slot.
            QtCore.QTimer.singleShot(0, self._old_process_finished)

    def _fail(self, message: str):
        super()._fail(message)
        self._fresh_after_renewal = False
        self._fresh_pending = False
        renewal, self._renewal = self._renewal, None
        if renewal is not None:
            # The replacement process could not be started or broke while starting.
            self._ui_muted = False
            renewal["done"](False, message)

    def _reset_runtime(self, keep_mute: bool = False):
        self._busy = False
        self._starting = False
        self._unacked = 0
        self._gate_retry = None
        self._state_known = False
        self._session_model = None
        self._session_thinking = None
        self._tools_verified_epoch = 0
        self._tools_probing = False
        self._tools_probe = None
        self._gate_running = False
        self._gate_again = False
        self._gate_report = None
        self._renewal_report = None
        self._interrupted_run = False
        if not keep_mute:
            self._ui_muted = False
        self._content_index = -1
        self._clear_activity_status()
        self._activity.reset()

    def _teardown_runtime(self, reason: str):
        """Invalidate everything in flight and close the UI turn once; nothing resumes by itself."""
        was_busy = self._busy
        self._renewal = None
        self._fresh_after_renewal = False
        self._fresh_pending = False
        self._steering.shutdown(reason)
        self._recheck_timer.stop()
        self._reap_timer.stop()
        self._reset_runtime()
        if was_busy:
            self.turn_completed.emit("stopped")
        self._emit_activity(True)

    def _prepare_runtime(self) -> bool:
        """Resolve and configure what this process needs. Fails closed on any error."""
        try:
            self._runtime = pi_runtime.resolve_runtime()
            # Validated here so a broken credential list fails closed with a clear message, not
            # later inside start() when the environment removals are computed.
            pi_runtime.credential_env_names()
            self._write_managed_config()
            # Accounts stored from now on are newer than what this launch will load.
            self._auth_applied = self._auth_revision
            self._auth_loaded = self._auth_revision
        except Exception as exc:
            self._runtime = None
            self._fail("Pi could not start: %s" % exc)
            return False
        return True

    def _write_managed_config(self):
        """Private agent dir (0700) with 0600 settings and an MCP file holding only the Nuke server.

        Everything else in the dir (auth, sessions, the user's own settings) is preserved.
        """
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.agent_dir, 0o700)
        settings_path = self.agent_dir / "settings.json"
        settings = _read_private_json(settings_path)
        settings["enableInstallTelemetry"] = False
        mcp_path = self.agent_dir / "mcp.json"
        mcp = _read_private_json(mcp_path)
        # The bridge pin is inherited from the agent process env, never persisted here.
        mcp["mcpServers"] = {
            "nuke": {
                "command": nuke_mcp.server_command()[0],
                "args": nuke_mcp.server_command()[1:],
                "env": nuke_mcp.server_environment(),
                # Direct tools are activated by the --tools mcp__nuke__* wildcard on every registry
                # refresh; the default (codemode) is only restored from a transcript on default tools.
                "exposure": "direct",
            }
        }
        _write_private_json(settings_path, settings)
        _write_private_json(mcp_path, mcp)

    def request_runtime_diagnostics(self, callback) -> bool:
        """Ask the diagnostics extension for its measured record (no model turn, nothing in model context).

        ``callback(data_or_None, error_text_or_None)`` receives the latest ``nuke-runtime-diagnostics``
        custom entry's ``data``. Only possible while idle.
        """
        if not self.ready or self.busy:
            return False

        def fail(text, _message=None):
            callback(None, text)

        def ids(message):
            return {e.get("id") for e in (message.get("data") or {}).get("entries") or [] if isinstance(e, dict)}

        def commands(message):
            for command in (message.get("data") or {}).get("commands") or []:
                if (
                    isinstance(command, dict)
                    and command.get("name") == "nuke_runtime"
                    and command.get("source") == "extension"
                    and (command.get("sourceInfo") or {}).get("path") == str(pi_runtime.DIAGNOSTICS_PATH)
                ):
                    self._send({"type": "get_entries"}, before, fail)
                    return
            fail("diagnostics command /nuke_runtime is not registered by the owned extension")

        def before(message):
            known = ids(message)

            def entries(after):
                found = None
                for entry in (after.get("data") or {}).get("entries") or []:
                    if (
                        isinstance(entry, dict)
                        and entry.get("id") not in known
                        and entry.get("type") == "custom"
                        and entry.get("customType") == "nuke-runtime-diagnostics"
                    ):
                        found = entry.get("data")
                if found is None:
                    fail("no diagnostics entry recorded")
                else:
                    callback(found, None)

            self._send(
                {"type": "prompt", "message": "/nuke_runtime"},
                lambda _m: self._send({"type": "get_entries"}, entries, fail),
                fail,
            )

        self._send({"type": "get_commands"}, commands, fail)
        return True

    def _on_started(self):
        self.status_changed.emit("Initializing %s…" % self.label)
        # Older pi builds emit no "ready" event, so ask for state right away;
        # the first response doubles as the readiness signal.
        self._query_state()

    # -- protocol events -----------------------------------------------------------

    def _handle_message(self, message: dict):
        kind = message.get("type")
        activity_changed = self._activity.feed(message)
        self._route_message(kind, message)
        if activity_changed:
            self._emit_activity()

    def _route_message(self, kind, message: dict):
        if kind == "ready":
            self._mark_ready()
            self._query_state()
        elif kind == "response":
            error_text = None
            if not message.get("success"):
                if message.get("command") == "get_available_thinking_levels":
                    # An agent without this command: thinking levels stay empty.
                    self._supports_thinking = False
                    self._callbacks.pop(message.get("id"), None)
                    return
                error_text = message.get("error") or "%s request failed" % message.get("command")
            self._dispatch_response(message, error_text)
        elif kind == "agent_start":
            self._busy = True
            self._starting = False
            self._interrupted_run = False
            self._content_index = -1
            self._clear_activity_status()
            self._steering.on_run_started()
            if not self._ui_muted:
                self.turn_started.emit()
        elif kind in ("agent_end", "agent_settled"):
            # agent_settled is newer; older agents only emit agent_end (and mark continuations with
            # isTerminal/yielded=false, like a retry's willRetry).
            if self._busy and (kind == "agent_settled" or ActivityTracker.run_finished(message)):
                self._end_run("interrupted" if message.get("aborted") or self._interrupted_run else "completed")
        elif kind == "prompt_result":
            if self._starting and not self._busy:
                # The prompt finished without running the agent (e.g. a local command).
                self._starting = False
                self._activity.starting = False
                self._emit_activity(True)
        elif kind == "turn_end":
            # A failed provider call still ends the turn; surface why instead
            # of leaving an empty reply on screen.
            failed = (message.get("message") or {}).get("errorMessage")
            if failed and not self._ui_muted:
                self.error.emit("%s: %s" % (self.label, failed))
        elif kind == "message_update":
            self._handle_stream_update(message.get("assistantMessageEvent") or {})
        elif kind == "tool_execution_start":
            args = message.get("args")
            if not self._ui_muted:
                self.tool_event.emit(
                    {
                        "phase": "start",
                        "id": message.get("toolCallId"),
                        "tool": message.get("toolName", ""),
                        "detail": compact_summary(args),
                        "arguments": _present_value(args),
                        "nuke": is_nuke_tool(message.get("toolName", ""), args),
                        "time_ns": time.monotonic_ns(),
                    }
                )
                self._tool_started(message)
        elif kind == "tool_execution_update":
            partial = message.get("partialResult")
            if not self._ui_muted:
                self.tool_event.emit(
                    {
                        "phase": "update",
                        "id": message.get("toolCallId"),
                        "tool": message.get("toolName", ""),
                        "detail": compact_summary(_result_text(partial)),
                        "partial": _present_result(partial),
                        "time_ns": time.monotonic_ns(),
                    }
                )
        elif kind == "tool_execution_end":
            result = message.get("result")
            if not self._ui_muted:
                self.tool_event.emit(
                    {
                        "phase": "end",
                        "id": message.get("toolCallId"),
                        "tool": message.get("toolName", ""),
                        "ok": not message.get("isError", False),
                        "detail": compact_summary(_result_text(result)),
                        "result": _present_result(result),
                        "time_ns": time.monotonic_ns(),
                    }
                )
            if not self._ui_muted:
                self._tool_finished(message)
            # The tracker already dropped this tool: a waiting steering step may continue.
            self._steering.on_backend_progress()
        elif kind == "extension_ui_request":
            if not self._take_tools_reply(message):
                self._handle_extension_ui(message)
        elif kind == "extension_error":
            self.status_changed.emit("%s extension error: %s" % (self.label, message.get("error", "")))
        elif kind == "thinking_level_changed":
            level = message.get("level")
            if isinstance(level, str) and level:
                self._session_thinking = level
                self._reconcile_thinking()

    def _end_run(self, status: str):
        """The run is over: close its UI turn once and let waiting steering steps continue."""
        self._busy = False
        self._starting = False
        self._interrupted_run = False
        self._clear_activity_status()
        self._activity.close_run()
        if not self._ui_muted:
            self.turn_completed.emit(status)
        self._send({"type": "get_session_stats"}, self._stats_loaded)
        self._steering.on_run_ended()
        self._emit_activity(True)
        self._reconcile_thinking()

    def _handle_stream_update(self, event: dict):
        if self._ui_muted:
            return
        event_type = event.get("type")
        if event_type == "text_start":
            index = event.get("contentIndex", 0)
            if self._content_index >= 0 and index != self._content_index:
                self.message_delta.emit("\n\n")
            self._content_index = index
            self._note_generating("writing the reply")
        elif event_type == "text_delta":
            if self._content_index < 0:
                self._content_index = 0
            self.message_delta.emit(event.get("delta", ""))
            self._note_generating("writing the reply")
        elif event_type == "thinking_delta":
            self.thinking_delta.emit(event.get("delta", ""))
            self._note_generating("thinking")
        elif event_type == "toolcall_start":
            self._note_generating("preparing tool call: %s" % (event.get("toolName") or "tool"))

    def _set_activity_status(self, text: str):
        """Publish an activity label only when it differs from the one already shown."""
        if text != self._activity_status:
            self._activity_status = text
            self.status_changed.emit(text)

    def _note_generating(self, what: str):
        """The model is generating: a tool that is really executing keeps its own label."""
        if not self._running_tools:
            self._set_activity_status("%s: %s" % (self.label, what))

    def _running_tools_status(self) -> str:
        names = list(dict.fromkeys(self._running_tools.values()))
        if len(self._running_tools) == 1:
            return "%s running tool: %s" % (self.label, names[0])
        return "%s running %d tools: %s" % (self.label, len(self._running_tools), ", ".join(names))

    def _tool_started(self, message: dict):
        key = message.get("toolCallId") or "%s#%d" % (message.get("toolName", ""), len(self._running_tools))
        self._running_tools[key] = message.get("toolName") or "tool"
        self._set_activity_status(self._running_tools_status())

    def _tool_finished(self, message: dict):
        key = message.get("toolCallId")
        if key not in self._running_tools:
            # Id-less events: the oldest execution of that tool name ended.
            key = next((k for k, name in self._running_tools.items() if name == message.get("toolName")), None)
        self._running_tools.pop(key, None)
        if self._running_tools:
            self._set_activity_status(self._running_tools_status())
        else:
            self._set_activity_status("%s: waiting for the model…" % self.label)

    def _clear_activity_status(self):
        self._running_tools.clear()
        self._activity_status = None

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

    def _query_state(self, models_loaded=None):
        self._send({"type": "get_available_models"}, models_loaded or self._models_loaded)
        self._send({"type": "get_available_thinking_levels"}, self._levels_loaded)
        self._send({"type": "get_state"}, self._state_loaded)
        self._send({"type": "get_session_stats"}, self._stats_loaded)

    def _apply_state(self, data: dict):
        self.session_id = data.get("sessionId") or self.session_id
        self.session_file = data.get("sessionFile") or self.session_file
        model = data.get("model")
        if isinstance(model, dict) and model.get("id"):
            provider = model.get("provider") or ""
            self._session_model = "%s/%s" % (provider, model["id"]) if provider else str(model["id"])
        else:
            self._session_model = None
        thinking = data.get("thinkingLevel")
        self._session_thinking = thinking if isinstance(thinking, str) and thinking else None

    def _state_loaded(self, message):
        before = self._session_model
        first = not self._state_known
        self._apply_state(message.get("data") or {})
        if first and self._selected_thinking is None and self._supports_thinking and self._session_thinking:
            # No effort was ever chosen: the effort Pi actually runs (e.g. a resumed conversation's) IS the
            # desire from now on, so a later process replacement reapplies and verifies it. The panel
            # shows it as the backend's and pushes nothing, which would leave the desire unrecorded.
            self._selected_thinking = self._session_thinking
        self._state_known = True
        if first and (self._renewal is None or self._renewal["fresh"]):
            # The actual SDK state is known: adopt it (or the configured default) unless the human chose.
            self._adopt_initial_selection()
        if self._renewal is None and (first or self._session_model != before):
            self.model_preferences_changed.emit()
        self._mark_ready()
        self._schedule_account_check()

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
        """Ready means usable: the managed Pi must first declare every Nuke MCP tool to the model.

        Pi's own startup wait for direct MCP servers is bounded (10 s) and then continues without
        tools, so it is not a guarantee. This probe uses the owned ``/nuke_tools`` command (no
        model turn) and fails closed, with a panel error, if the tools never appear.
        """
        if self.ready or self._tools_probing or self._tools_verified_epoch == self.process_epoch:
            # Already verified for this process: catalog/levels/state callbacks never re-enter readiness.
            return
        if not self._state_known:
            # The restored session's canonical model is not known yet: Send must stay off.
            return
        self._tools_probing = True
        self.status_changed.emit("%s: waiting for Nuke tools…" % self.label)
        self._probe_tools(self.process_epoch, time.monotonic() + _TOOLS_READY_SECONDS)

    def _finish_ready(self):
        if self._renewal is None or self._renewal["fresh"]:
            # Fresh start: the configured default, else the actual SDK state. A restored conversation
            # keeps ITS model (blocked, never silently replaced, when it is not allowed). A human
            # choice made while waiting is never overwritten.
            self._adopt_initial_selection()
        if self._renewal is not None:
            # Ready only after the selection is ACKed (see _restore_selection).
            self._restore_selection()
            return
        if self._selected_model or self._selected_thinking or self._selection_block:
            # Confirm the desired selection before Send is enabled.
            self._gate_selection(lambda: self.status_changed.emit("%s connected" % self.label))
        else:
            self._set_ready(True)
            self.status_changed.emit("%s connected" % self.label)

    def _probe_tools(self, epoch: int, deadline: float):
        def stale():
            return epoch != self.process_epoch or self._stopping or not self._tools_probing

        def give_up(text, _message=None):
            if stale():
                return
            self._tools_probing = False
            self._fail("%s: Nuke tools are not available (%s). Reconnect to retry." % (self.label, text))

        def retry(reason):
            if time.monotonic() >= deadline:
                give_up(reason)
            else:
                QtCore.QTimer.singleShot(500, lambda: None if stale() else self._probe_tools(epoch, deadline))

        def commands(message):
            if stale():
                return
            for command in (message.get("data") or {}).get("commands") or []:
                if (
                    isinstance(command, dict)
                    and command.get("name") == "nuke_tools"
                    and (command.get("sourceInfo") or {}).get("path") == str(pi_runtime.DIAGNOSTICS_PATH)
                ):
                    ask()
                    return
            retry("readiness command is not registered by the owned extension")

        def ask():
            # The owned command answers with one compact extension_ui_request notify carrying this
            # nonce (see ``_take_tools_reply``); the conversation history is never read.
            nonce = uuid.uuid4().hex
            self._tools_probe = {"epoch": epoch, "nonce": nonce, "result": None}

            def answered(_message):
                probe, self._tools_probe = self._tools_probe, None
                if stale():
                    return
                found = (probe or {}).get("result")
                if found is None:
                    retry("no readiness reply from the owned extension")
                    return
                from ..mcp_server import server as mcp_server_module

                required = {"mcp__nuke__%s" % tool["name"] for tool in mcp_server_module.TOOLS}
                missing = sorted(required - set(found.get("active") or []))
                if missing:
                    retry("not active yet: %s" % ", ".join(name.split("__", 2)[-1] for name in missing))
                    return
                self._tools_probing = False
                self._tools_verified_epoch = epoch
                self._finish_ready()

            self._send({"type": "prompt", "message": "/nuke_tools %s" % nonce}, answered, give_up)

        self._send({"type": "get_commands"}, commands, give_up)

    def _take_tools_reply(self, message: dict) -> bool:
        """Consume the owned readiness notify for the pending probe; True when it was one."""
        text = message.get("message")
        if message.get("method") != "notify" or not isinstance(text, str) or not text.startswith(_TOOLS_REPLY_PREFIX):
            return False
        probe = self._tools_probe
        if probe is None or probe["epoch"] != self.process_epoch:
            return True
        try:
            data = json.loads(text[len(_TOOLS_REPLY_PREFIX):])
        except ValueError:
            return True
        if isinstance(data, dict) and data.get("nonce") == probe["nonce"]:
            probe["result"] = data
        return True

    def _model_entries(self, message) -> list[dict]:
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
        return models

    def _announce_models(self, models: list[dict]):
        """Publish the catalog: ``models`` is the agent's full list; the UI gets the shortlisted part."""
        self._full_models = models
        full = [(m["id"], m["label"], tuple(m["efforts"])) for m in models]
        if full != self._full_signature:
            self._full_signature = full
            self.model_preferences_changed.emit()
        self._publish_visible_models()

    def _publish_visible_models(self):
        visible = self._visible_models()
        signature = [(m["id"], m["label"], tuple(m["efforts"])) for m in visible]
        # Only announce real changes: a re-query triggered by set_model must not bounce back into
        # the panel and re-select the model forever.
        if signature != self._models_signature:
            self._models_signature = signature
            self.models_changed.emit(visible)

    def _visible_models(self) -> list[dict]:
        """The catalog the user may pick from: the private shortlist, else everything."""
        enabled, _default, _error = self._read_model_preferences()
        if enabled is None:
            return list(self._full_models)
        allowed = set(enabled)
        return [m for m in self._full_models if m["id"] in allowed]

    def _models_loaded(self, message):
        models = self._model_entries(message)
        if self._renewal is None:
            if self._catalog_pending():
                # The UI still lacks the catalog of the stored accounts this launch loaded:
                # this successful answer is authoritative, an empty one included (every
                # provider may have been removed).
                self._announce_models(models)
                self._auth_published = self._auth_loaded
            elif models:
                # An empty list is not announced otherwise (model discovery may not be finished).
                self._announce_models(models)
            self._revalidate_selection()
        # A process being renewed starts on its default model; its list must not disturb the
        # user's choice. The renewal publishes a pending catalog itself once it has ended.
        self._mark_ready()

    def _levels_loaded(self, message):
        levels = [str(level) for level in (message.get("data") or {}).get("levels") or []]
        self._thinking_levels = levels
        # Re-emit models so the panel refreshes per-model effort lists.
        self._send({"type": "get_available_models"}, self._models_loaded)

    # -- sending -----------------------------------------------------------------

    def send_turn(self, text: str, image_paths: list[str] | None = None) -> bool:
        text = text.strip()
        if not text:
            return False
        if self._steering.active:
            # Mid-intervention (including while the agent process is being renewed).
            return self._steering.submit(text, list(image_paths or [])) is not None
        if not self.ready:
            return False
        if self.busy:
            return self.intervene(text, image_paths) is not None
        return self._send_idle(text, image_paths, self._steering.next_message_id())

    def intervene(self, text: str, image_paths: list[str] | None = None) -> int | None:
        """Manual steering (``/btw``): stop the old work safely, resume the conversation with ``text``."""
        text = text.strip()
        if not text:
            return None
        if self._steering.active:
            return self._steering.submit(text, list(image_paths or []))
        if not self.ready:
            return None
        if not self.busy:
            message_id = self._steering.next_message_id()
            return message_id if self._send_idle(text, image_paths, message_id) else None
        return self._steering.submit(text, list(image_paths or []))

    def _encode_images(self, image_paths) -> list[dict]:
        return [
            {"type": "image", **dict(zip(("mimeType", "data"), encode_image(path)))}
            for path in image_paths or []
        ]

    def _send_idle(self, text: str, image_paths, message_id: int) -> bool:
        payload = {"type": "prompt", "message": text}
        try:
            if image_paths:
                payload["images"] = self._encode_images(image_paths)
        except OSError as exc:
            self.error.emit("%s: could not read an attached image: %s" % (self.label, exc))
            return False
        paths = list(image_paths or [])
        self.user_message.emit(text, paths)
        restore = {"id": message_id, "text": text, "image_paths": paths, "source": "send"}
        self._dispatch_prompt(payload, restore=restore)
        return True

    def _dispatch_prompt(self, payload: dict, done=None, restore: dict | None = None):
        """Send one prompt and track it until the agent acknowledges (or rejects) it.

        ``done(ok, error)`` reports the acknowledgement; without it a rejected prompt hands
        ``restore`` back to the user. While un-acknowledged, no abort is issued for the run it
        would start (an abort before admission could miss it).
        """
        self._starting = True
        self._unacked += 1
        self._activity.note_starting()

        def acknowledged(message):
            if self._stopping:
                return
            self._unacked = max(0, self._unacked - 1)
            data = message.get("data") or {}
            if data.get("disposition") == "handled" or data.get("agentInvoked") is False:
                # Finished locally (an extension or slash command): no run will start.
                self._starting = False
                self._activity.starting = False
            if done is not None:
                done(True, None)
            self._steering.on_backend_progress()
            self._emit_activity(True)

        def rejected(text, _message):
            if self._stopping:
                return
            self._unacked = max(0, self._unacked - 1)
            if not self._busy:
                self._starting = False
                self._activity.starting = False
            self.error.emit("%s: the message was not delivered: %s" % (self.label, text))
            if done is not None:
                done(False, text)
            elif restore is not None:
                self._withdraw([restore], "the agent rejected it")
            self._steering.on_backend_progress()
            self._emit_activity(True)

        self._send(payload, acknowledged, rejected)
        self._emit_activity(True)

    def _withdraw(self, items: list, reason: str):
        """Hand never-delivered input back to the user (the panel restores it to its input box)."""
        if not items:
            return
        self.guidance_withdrawn.emit(items)
        self.status_changed.emit(
            "%s: %d message(s) were not delivered (%s) and were returned to the input box"
            % (self.label, len(items), reason)
        )

    # -- stopping the run ---------------------------------------------------------------

    def interrupt(self):
        """Cancel: stop the run safely and deliver nothing. Never resumes by itself."""
        self._steering.cancel()

    def _abort_run(self, done, stage):
        """Abort the current run, wait until the agent reports idle, and take back queued input.

        ``done({"ok", "error", "withdrawn"})`` fires once. ``abort``'s response only follows
        the run's unwinding, and ``get_state`` then confirms nothing is streaming (the abort is
        retried a few times if it raced the run's start); queues survive an abort in pi, so they
        are taken back before anything can resume.
        """
        state = {"attempts": 0, "withdrawn": [], "restore": False}

        def finish(ok, error=None):
            self._activity.note_stopping(False)
            done({"ok": ok, "error": error, "withdrawn": state["withdrawn"]})

        def attempt():
            state["attempts"] += 1
            command = "abort"
            self._interrupted_run = True
            self._activity.note_stopping(True)
            self._emit_activity(True)
            self._send({"type": command}, acknowledged, lambda text, _m: finish(False, text))

        def acknowledged(message):
            data = message.get("data") or {}
            for entry in list(data.get("steering") or []) + list(data.get("followUp") or []):
                state["withdrawn"].append(_queue_item(entry))
            self._send({"type": "get_state"}, verified, lambda text, _m: finish(False, text))

        def verified(message):
            data = message.get("data") or {}
            if data.get("isStreaming") or data.get("isCompacting"):
                if state["attempts"] < MAX_ABORT_ATTEMPTS:
                    attempt()
                    return
                finish(False, "the agent still reports a running turn after %d abort attempts" % state["attempts"])
                return
            stage("reconciling")

            def cleared(reply):
                body = reply.get("data") or {}
                for entry in list(body.get("steering") or []) + list(body.get("followUp") or []):
                    state["withdrawn"].append(_queue_item(entry))
                finish(True)

            # An agent without clear_queue has nothing queued by this client; carry on.
            self._send({"type": "clear_queue"}, cleared, lambda _text, _m: finish(True))

        attempt()

    def _run_interrupted(self):
        """The old run was stopped on purpose: whatever the events said, nothing runs now."""
        was_busy = self._busy
        self._busy = False
        self._clear_activity_status()
        self._starting = False
        self._interrupted_run = False
        self._activity.close_run()
        if was_busy and not self._ui_muted:
            self.turn_completed.emit("interrupted")
        self._emit_activity(True)

    # -- process renewal ---------------------------------------------------------------

    def _renew_process(self, fresh_session: bool, done, detail, restart: bool = True):
        """Replace the agent process (and its MCP sidecar), keeping the conversation.

        Order matters: the bridge first fences the old process (newer process lease), then the old
        agent is terminated and its sidecar processes are confirmed gone, then Nuke must be idle,
        the bridge control is reopened, and only then does the replacement start (same persisted
        session, or a fresh one for a new chat) with the selected model/effort reapplied.
        """
        if self._renewal is not None:
            done(False, "the agent process is already being replaced")
            return
        self._renewal = {
            "done": done,
            "detail": detail,
            "fresh": fresh_session,
            "restored": False,
            "stage": "stopping",
            "old_epoch": self.process_epoch,
            "pids": set(),
            "killed": False,
            "restart": restart,
        }
        # Not a restore of a previous conversation: the model must carry on, not wait.
        self._resuming = False
        if fresh_session:
            self.session_id = None
            self.session_file = None
        detail("stopping the old agent process (its tool requests are refused from now on)")
        try:
            self._announce_epoch(self.process_epoch + 1)
        except Exception as exc:
            self._renewal = None
            self._ui_muted = False
            done(False, "the Nuke bridge refused the new process lease: %s" % exc)
            return
        try:
            self._renewal["pids"] = set(lease_processes(self.control_id, self.process_epoch))
        except ProcessOwnershipError as exc:
            self._reap_unverifiable(exc)
            return
        self._reset_runtime(keep_mute=True)
        self.status_changed.emit(
            (
                "%s: starting a fresh conversation (new agent process)…"
                if fresh_session
                else "%s: reconnecting the same conversation (new agent process, same session)…"
            )
            % self.label
        )
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning:
            self._old_process_finished()
        else:
            # Without restart: the replacement starts only after the checks below.
            JsonlProcessClient.stop(self, restart=False)

    def _old_process_finished(self):
        """The old agent exited; now make sure its sidecar processes are gone too."""
        renewal = self._renewal
        if renewal is None or renewal["stage"] != "stopping":
            return
        renewal["stage"] = "reaping"
        try:
            renewal["pids"] |= set(lease_processes(self.control_id, renewal["old_epoch"]))
            alive = [pid for pid in renewal["pids"] if process_alive(pid)]
            if alive:
                signal_processes(alive, TERM)
        except ProcessOwnershipError as exc:
            self._reap_unverifiable(exc)
            return
        if alive:
            renewal["detail"]("waiting for the old agent's tool server to exit")
            renewal["reaped_at"] = time.monotonic()
            self._reap_timer.start()
        else:
            self._old_processes_gone()

    def _poll_reap(self):
        renewal = self._renewal
        if renewal is None or renewal["stage"] != "reaping":
            self._reap_timer.stop()
            return
        try:
            renewal["pids"] |= set(lease_processes(self.control_id, renewal["old_epoch"]))
            alive = [pid for pid in renewal["pids"] if process_alive(pid)]
            if alive and not renewal["killed"] and time.monotonic() - renewal["reaped_at"] > 2.0:
                # Process management, not a model deadline: a sidecar that ignores SIGTERM is ended.
                renewal["killed"] = True
                signal_processes(alive, KILL)
        except ProcessOwnershipError as exc:
            self._reap_unverifiable(exc)
            return
        if not alive:
            self._reap_timer.stop()
            self._old_processes_gone()

    def _reap_unverifiable(self, exc: Exception):
        """Ownership of the old tool server cannot be verified: fail closed, never start the replacement."""
        renewal = self._renewal
        self._reap_timer.stop()
        self._renewal = None
        self._ui_muted = False
        if renewal is not None:
            renewal["done"](False, "could not confirm the old agent's tool server is gone: %s" % exc)

    def _old_processes_gone(self):
        renewal = self._renewal
        if renewal is None:
            return
        if not renewal["restart"]:
            self._park(renewal)
            return
        renewal["stage"] = "reopening"
        self._retry_renewal_reopen()

    def _park(self, renewal: dict):
        """Cancel of a session that cannot be resumed: leave the agent stopped.

        The old agent and its sidecars are gone and the bridge control stays retired and closed
        (``begin_process`` already fenced the old process). Nothing is started and the control is
        not reopened here, so no conversation resumes; Reconnect launches a new process (a new,
        empty session) as an explicit user action.
        """
        self._renewal = None
        self._ui_muted = False
        self.parked = True
        self.status_changed.emit(
            "%s stopped. This session is not persisted, so its conversation cannot be resumed and "
            "Nuke tools stay closed to the stopped agent. Use Reconnect to start a new session."
            % self.label
        )
        renewal["done"](True, None)

    def _retry_renewal_reopen(self):
        """Nuke idle and old processes gone: reopen the bridge, then start the replacement."""
        renewal = self._renewal
        if renewal is None or renewal["stage"] != "reopening":
            return
        if self._lease.available and self._lease.status().get("active_operations"):
            renewal["detail"]("waiting for a Nuke operation to finish before the new agent starts")
            return
        try:
            status = self._lease.resume() if self._lease.available else {}
        except Exception as exc:
            self._renewal = None
            self._ui_muted = False
            renewal["done"](False, "could not reopen the Nuke bridge: %s" % exc)
            return
        if status is None:
            renewal["detail"]("waiting for a Nuke operation to finish before the new agent starts")
            return
        renewal["stage"] = "starting"
        renewal["detail"]("starting the new agent process on the same session")
        self.start()

    def _on_recheck(self):
        self._steering.recheck()
        self._retry_renewal_reopen()

    def _restore_selection(self):
        """The new process is up: reapply the user's model/effort, then report the renewal done."""
        renewal = self._renewal
        if renewal is None or renewal["restored"]:
            return
        renewal["restored"] = True
        renewal["detail"]("restoring the selected model and effort")

        def finish(ok, error=None):
            if self._renewal is not renewal:
                return  # stopped or failed in the meantime
            self._renewal = None
            self._ui_muted = False
            self._fresh_pending = bool(self._fresh_after_renewal)
            if ok:
                self._gate_retry = None
                self._set_ready(True)
                self.status_changed.emit(
                    "%s: fresh conversation ready" % self.label
                    if renewal["fresh"]
                    else "%s: reconnected to the same conversation" % self.label
                )
            # The replacement loaded the stored accounts of its launch; its renewal-time model
            # lists were not announced, so a catalog the UI still lacks is published now.
            self._publish_pending_catalog()
            renewal["done"](ok, error)
            if self._fresh_after_renewal:
                # A new chat arrived while this (non-steering) renewal ran: replace the process again.
                self._fresh_after_renewal = False
                self._ui_muted = True
                self._steering.begin_reset()

        # Picks made while the restore is pending join the same single-flight chain; the renewal
        # ends only when the LATEST desired selection is ACKed (or fails).
        self._gate_retry = self._gate_selection
        self._renewal_report = finish
        self._begin_gate(None)

    def _apply_selection(self, finish):
        """Reapply the user's model then effort; ``finish(ok, error)`` runs only once Pi's own state confirms both.

        Shared by renewal, fresh sessions and startup: a new Pi session/process starts on Pi's own
        default model, which must never serve a prompt the user sent under another selection.

        ``set_model`` resets the session effort to Pi's default and ``set_thinking_level`` answers
        success without the effective level (Pi clamps it to the model), so neither ACK proves the
        selection. Only a ``get_state`` issued after every apply operation does.
        """
        if self._selected_model:
            # Shortlist/catalog may have changed since the pick (settings are the single source).
            self._selection_block = self._block_reason(self._selected_model)
        if self._selection_block:
            # Never substitute another model: the desire is blocked until the user picks again.
            finish(False, self._selection_block)
            return

        epoch = self.process_epoch
        generation = self._gate_generation

        def stale():
            return epoch != self.process_epoch or self._stopping

        def verify(_message=None):
            def read(message):
                if stale():
                    return
                self._apply_state(message.get("data") or {})
                problem = self._selection_mismatch()
                finish(problem is None, problem)

            self._send(
                {"type": "get_state"},
                read,
                lambda text, _m: finish(False, "could not confirm the model and effort: %s" % text),
            )

        def apply_thinking(_message=None):
            wanted = self._selected_thinking
            if not wanted or not self._supports_thinking:
                verify()
                return
            self._send(
                {"type": "set_thinking_level", "level": wanted},
                verify,
                lambda text, _m: finish(False, "could not restore the thinking level: %s" % text),
            )

        def model_set(_reply):
            # Effort lists depend on the model (the UI refreshes from this; the readback does not use it).
            self._send({"type": "get_available_thinking_levels"}, self._levels_loaded)
            apply_thinking()

        def apply_model(_message=None):
            if self._selected_model and "/" in self._selected_model:
                selected = self._selected_model
                provider, model = selected.split("/", 1)
                if self._selection_origin == "sdk" and selected == self._session_model:
                    # Adopted from this very process' state: it already runs this model.
                    apply_thinking()
                    return

                def model_failed(text, _m):
                    if stale():
                        return  # a newer process superseded this chain
                    if generation == self._gate_generation and selected == self._selected_model:
                        self.model_selection_failed.emit(selected)
                    else:
                        # An obsolete selection failed: it must neither reach the UI nor block the
                        # newer desire, which the single-flight chain applies next.
                        self._gate_again = True
                    finish(False, "could not restore the model %s: %s" % (selected, text))

                self._send(
                    {"type": "set_model", "provider": provider, "modelId": model},
                    model_set,
                    model_failed,
                )
            else:
                apply_thinking()

        # Model discovery can finish after "ready"; set_model needs the complete catalog.
        self._send({"type": "get_available_models"}, apply_model, lambda _text, _m: apply_model())

    def _selection_mismatch(self) -> str | None:
        """Why Pi's own reported state differs from the desired model/effort (None when it matches)."""
        model = self._selected_model
        if model and self._session_model != model:
            return "Pi reports model %s instead of %s" % (self._session_model or "none", model)
        wanted = self._selected_thinking
        if wanted and self._supports_thinking and self._session_thinking != wanted:
            return "Pi runs effort %s instead of the selected %s" % (self._session_thinking or "unknown", wanted)
        return None

    def _reconcile_thinking(self):
        """Pi's effort moved outside the apply chain: Send closes until the desired effort is confirmed again.

        Runs on ``thinking_level_changed`` and at the end of a run (idle only, so a steering message
        is never blocked). Nothing is resent and Pi's effort is never adopted: the mismatch is reported
        and the user's explicit pick (the existing retry) re-applies and re-reads the selection.
        """
        if (
            self._gate_running
            or self._renewal is not None
            or self._stopping
            or self.busy
            or not self.ready
            or self._tools_verified_epoch != self.process_epoch
        ):
            return
        wanted = self._selected_thinking
        level = self._session_thinking
        if not wanted or not level or not self._supports_thinking or level == wanted:
            return
        self._gate_retry = self._gate_selection
        self._set_ready(False)
        self.error.emit(
            "%s: Pi runs effort %s instead of the selected %s. Pick the effort again to re-apply it."
            % (self.label, level, wanted)
        )

    # -- stored accounts ---------------------------------------------------------------

    def refresh_accounts(self) -> bool:
        """Stored Pi accounts changed: have the agent re-read them once that is safe.

        The agent loads credentials and the model catalog once at startup and Pi's RPC cannot
        reload them, so applying a change means replacing the agent process through the existing
        idle renewal: same persisted session, selected model and effort reapplied. A run, a
        steering step or a renewal in progress is never interrupted; the change stays pending and
        is applied when the agent is next idle. Changes that pile up (also during a renewal)
        collapse into at most one further renewal, and a failed attempt is not retried until the
        accounts change again.
        """
        self._auth_revision += 1
        self._schedule_account_check()
        return True

    @QtCore.Slot(str)
    def _on_accounts_changed(self, agent_dir: str):
        # The bus is process-wide; only changes to this client's own private Pi dir matter.
        if os.path.realpath(agent_dir) == os.path.realpath(self.agent_dir):
            self.refresh_accounts()

    def _schedule_account_check(self):
        if self._auth_applied < self._auth_revision:
            self._accounts_check.emit()

    def _note_pending_accounts(self, reason: str):
        if self._auth_notified != self._auth_revision:
            self._auth_notified = self._auth_revision
            self.status_changed.emit("%s: stored accounts changed; %s" % (self.label, reason))

    @QtCore.Slot()
    def _apply_account_changes(self):
        if self._auth_applied >= self._auth_revision:
            return
        if self._renewal is not None or self._stopping or self.parked:
            return  # re-checked when that renewal ends; any other launch loads the accounts itself
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning or not self.ready:
            # Not running (its next launch loads the accounts) or still starting (re-checked once ready).
            return
        if self.busy:
            self._note_pending_accounts("they apply when the agent is idle; the current work is not interrupted")
            return
        if not self.can_renew_session():
            # A replacement process would start an empty conversation: never trade the chat for accounts.
            if self.session_dir is None:
                self._note_pending_accounts(
                    "this session cannot be resumed in a new agent process, so they apply after Reconnect"
                )
            return
        launched = self.process_epoch
        self._auth_applied = self._auth_revision
        self.status_changed.emit(
            "%s: stored accounts changed; reconnecting the agent to apply them (same conversation)…"
            % self.label
        )
        self._renew_process(
            False,
            lambda ok, error=None: self._accounts_renewed(launched, ok, error),
            lambda text: self.status_changed.emit("%s: applying account changes: %s" % (self.label, text)),
        )

    def _catalog_pending(self) -> bool:
        """The UI has not yet received the model catalog of the stored accounts this launch loaded."""
        return self._auth_published < self._auth_loaded

    def _publish_pending_catalog(self):
        """Ask the running agent for its model catalog if the UI still lacks the one for its accounts.

        A launch consumes the stored-account revision as it starts, whatever started it, so the
        pending state is not tied to the account renewal. ``_models_loaded`` completes the
        publication when the answer arrives; a failed request leaves it pending, and nothing
        here retries it.
        """
        if self._catalog_pending() and self.ready and self._renewal is None and not self._stopping:
            self._send({"type": "get_available_models"}, self._models_loaded)

    def _accounts_renewed(self, launched: int, ok: bool, error: str | None):
        """The renewal ended: say whether the accounts were applied (the catalog was published by the renewal)."""
        if self.process_epoch != launched and self.ready:
            # The new agent is up on the same session (a model/effort that could not be restored
            # is reported, the user then picks one).
            if ok:
                self.status_changed.emit(
                    "%s: stored accounts applied; the conversation and your model selection are kept" % self.label
                )
            else:
                self.status_changed.emit(
                    "%s: stored accounts applied, but %s" % (self.label, error or "the selection was not restored")
                )
        else:
            message = "%s: stored accounts changed but could not be applied (%s). Use Reconnect to load them." % (
                self.label,
                error or "unknown error",
            )
            self.status_changed.emit(message)
            if self.process_epoch == launched:
                # No replacement was launched, so the base class has not reported anything yet.
                self.error.emit(message)
        # A change that arrived while renewing is newer than this launch and gets its own pass.
        self._schedule_account_check()

    def new_session(self):
        """Fresh conversation on the configured default model, in a NEW agent process.

        Pi's in-process ``new_session`` would keep this process' lease/epoch, so a late delivery
        of the old chat could still pass the panel's identity check. A fresh process raises the
        epoch (the bridge refuses the old sidecar) and goes through the same readiness probe and
        model/effort ACK barrier as every launch; busy, idle or still initializing/probing, it is
        the steering reset: the old process (and every callback it could still deliver) is fenced
        before the caller treats the chat as fresh.
        """
        self._resuming = False
        self.session_id = None
        self.session_file = None
        if not self._select_default() and self._selection_origin != "human":
            # No configured default: the new process' actual state decides again.
            self._selection_block = None
            self._set_selected_model(None)
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning or self._stopping:
            return
        # The old run's late events must not reach the cleared chat.
        self._ui_muted = True
        if self._renewal is not None and not self._steering.active:
            # A non-steering renewal (accounts/preferences) is running: replace again once it ends.
            self._fresh_after_renewal = True
            return
        self._fresh_pending = True
        self._steering.begin_reset()

    def set_model(self, model_id: str):
        """An explicit (human) choice: never overridden by a default or by the SDK's state."""
        if not model_id or "/" not in model_id:
            return
        if model_id == self._selected_model and (
            self._gate_running
            or (self._tools_verified_epoch == self.process_epoch and self.ready and self._gate_retry is None)
        ):
            # Already the desired model: being applied right now, or applied. (A failed apply is
            # not running, so picking the same model again still retries it.)
            self._selection_origin = "human"
            return
        self._selected_model = model_id
        self._selection_origin = "human"
        self._selection_block = self._block_reason(model_id)
        self._selection_changed()

    def set_thinking(self, level: str):
        if level and not (level == self._selected_thinking and self._gate_retry is None):
            self._selected_thinking = level
            self._selection_changed()

    def _selection_changed(self):
        """A new desired model/effort: gate Send until the LATEST desire is ACKed.

        Before the process is verified/ready the value is only stored (``_finish_ready`` applies it
        before Ready). Once ready, or while a gate/renewal apply is pending or failed, every change
        joins the single-flight apply, so an older completion never enables Ready.
        """
        if self._tools_verified_epoch == self.process_epoch and (self.ready or self._gate_retry is not None):
            self._gate_selection()

    def _gate_selection(self, after=None):
        """Not ready until the selected model/effort is ACKed; failure keeps Send off and is retryable.

        The pickers stay usable: any new pick or effort change re-runs the apply. The desired
        selection is never dropped or replaced by a fallback, and a failure is reported, not hidden.
        """

        def report(ok, error=None):
            if ok:
                self._gate_retry = None
                self._set_ready(True)
                if after is not None:
                    after()
                else:
                    self.status_changed.emit("%s connected" % self.label)
            elif self._selection_block:
                self.error.emit(
                    "%s: %s. Pick a model from your enabled list, or change the list under Manage models."
                    % (self.label, self._selection_block)
                )
            else:
                self.error.emit(
                    "%s: selected model could not be applied (%s). Pick the model again or Reconnect."
                    % (self.label, error or "unknown error")
                )

        self._begin_gate(report)

    def _begin_gate(self, report):
        """Record the newest desire and make sure exactly one apply chain serves it."""
        self._gate_generation += 1
        self._gate_retry = self._gate_selection
        if report is not None:
            self._gate_report = report
        self._set_ready(False)
        if self._gate_running:
            self._gate_again = True
            return
        self._run_gate()

    def _run_gate(self):
        self._gate_running = True
        self._gate_again = False
        epoch = self.process_epoch

        def done(ok, error=None):
            if epoch != self.process_epoch or self._stopping or not self._gate_running:
                return  # a newer process (or a teardown) superseded this chain
            self._gate_running = False
            if self._gate_again:
                self._run_gate()  # the desire changed meanwhile: apply the latest
                return
            renewal_report, self._renewal_report = self._renewal_report, None
            report, self._gate_report = self._gate_report, None
            if renewal_report is not None:
                renewal_report(ok, error)
            if report is not None and self._renewal is None:
                report(ok, error)

        self._apply_selection(done)

    # -- model shortlist and default (managed Pi) ------------------------------------------

    def _read_model_preferences(self) -> tuple:
        """(enabled ids or None for all, configured default id or None, error text or None).

        The private ``settings.json`` is the only store; an empty list means "all" like Pi's own.
        """
        try:
            settings = _read_private_json(self.agent_dir / "settings.json")
        except (OSError, ValueError) as exc:
            return None, None, "model settings are unreadable: %s" % exc
        enabled = settings.get("enabledModels")
        if not isinstance(enabled, list) or not enabled:
            enabled = None
        else:
            enabled = [item for item in enabled if isinstance(item, str)] or None
        provider, model = settings.get("defaultProvider"), settings.get("defaultModel")
        default = "%s/%s" % (provider, model) if isinstance(provider, str) and isinstance(model, str) and provider and model else None
        return enabled, default, None

    def _block_reason(self, model_id: str | None) -> str | None:
        """Why this model must not be applied (shortlist/catalog), or None when it may be."""
        if not model_id:
            return None
        enabled, _default, _error = self._read_model_preferences()
        if enabled is not None and model_id not in enabled:
            return "the model %s is not among your enabled models" % model_id
        if self._full_models and model_id not in {m["id"] for m in self._full_models}:
            return "the model %s is not available from the connected accounts" % model_id
        return None

    def _set_selected_model(self, model_id: str | None, origin: str | None = None):
        self._selection_origin = origin if model_id else None
        if model_id != self._selected_model:
            self._selected_model = model_id
            self.selected_model_changed.emit(model_id or "")

    @property
    def selected_model(self) -> str:
        """The model this client is applying (or blocked on); "" when none was chosen yet."""
        return self._selected_model or ""

    @property
    def selected_thinking(self) -> str:
        """The desired effort, else the one Pi's session state reports; "" when unknown."""
        return self._selected_thinking or self._session_thinking or ""

    @property
    def current_model(self) -> str:
        """The model Pi's own session state reports (canonical "provider/id"); "" until known."""
        return self._session_model or ""

    def _select_default(self) -> bool:
        """Adopt the configured private default (blocked, never replaced, when unusable).

        False when none is configured.
        """
        _enabled, default, _error = self._read_model_preferences()
        if default is None:
            return False
        reason = self._block_reason(default)
        if reason is None:
            self._selection_block = None
            self._set_selected_model(default, "default")
        else:
            self._selection_block = "the default model cannot be used: %s" % reason
            self._set_selected_model(None)
        return True

    def _adopt_initial_selection(self):
        """A new process without a human choice: configured default (fresh) or the actual SDK model.

        Never the first catalog entry. A restored conversation keeps the model Pi restored for it;
        when that is not allowed the selection is blocked, not replaced by the default. Idempotent;
        a human choice is left untouched.
        """
        if self._selection_origin == "human":
            return
        if not self._resuming and self._select_default():
            return
        if self._session_model:
            self._selection_block = self._block_reason(self._session_model)
            self._set_selected_model(self._session_model, "sdk")

    def _revalidate_selection(self):
        """The catalog changed: a desired model that vanished is reported, never silently replaced."""
        if not self._selected_model:
            return
        block = self._block_reason(self._selected_model)
        if block != self._selection_block:
            self._selection_block = block
            if self._tools_verified_epoch == self.process_epoch and (self.ready or self._gate_retry is not None):
                self._gate_selection()

    def can_edit_model_preferences(self) -> bool:
        """Idle and ready (or only blocked on the selection): the process can be safely replaced."""
        return (
            self.process.state() == QtCore.QProcess.ProcessState.Running
            and self._renewal is None
            and not self._stopping
            and not self.parked
            and not self.busy
            and not self._tools_probing
            and bool(self._full_models)
            and (self.ready or self._gate_retry is not None)
        )

    def get_model_preferences(self) -> dict | None:
        """Full catalog, persisted shortlist and default."""
        enabled, default, error = self._read_model_preferences()
        catalog = [m["id"] for m in self._full_models]
        fallback = self._selected_model or (catalog[0] if catalog else "")
        return {
            # What Pi's own session state reports (after a model ACK: the applied model). None
            # until the first state reply of this process; use it, not QSettings, for a restored chat.
            "session_model": self._session_model,
            "session_thinking": self._session_thinking,
            "session_model_known": self._state_known,
            "available_models": [dict(m, efforts=list(m["efforts"])) for m in self._full_models],
            "enabled_models": list(enabled) if enabled is not None else None,
            "default_model": default or fallback,
            "default_configured": default is not None,
            # Shortlisted ids the connected accounts do not currently offer (kept, not discarded).
            "missing_models": [item for item in (enabled or []) if item not in set(catalog)],
            "editable": self.can_edit_model_preferences(),
            "error": error,
        }

    def save_model_preferences(self, enabled_models: list, default_model: str) -> bool:
        """Persist the shortlist/default to the private Pi settings and apply them safely.

        Rejected without any change when not idle/ready, empty, duplicated, unknown or when the
        default is not in the list (``model_preferences_error`` says why). The exact ordered ids
        are always stored (selecting every current model does NOT mean "all"; future catalog
        additions stay unlisted). Pi reads the shortlist at startup, so a changed list is
        applied by the existing idle process renewal (same session, selection ACKed before Send);
        the current model is kept while still allowed, otherwise the new default is applied.
        """
        self.model_preferences_error = None

        def reject(text: str) -> bool:
            self.model_preferences_error = text
            return False

        if not self.can_edit_model_preferences():
            return reject("models can only be managed while the agent is idle and ready")
        if not isinstance(enabled_models, (list, tuple)) or not all(isinstance(i, str) for i in enabled_models):
            return reject("the enabled models must be a list of model ids")
        selected = list(enabled_models)
        if not selected:
            return reject("select at least one model (select all to allow every model)")
        if len(set(selected)) != len(selected):
            return reject("the enabled models contain duplicates")
        catalog = [m["id"] for m in self._full_models]
        unknown = [item for item in selected if item not in set(catalog)]
        if unknown:
            return reject("unknown model(s): %s" % ", ".join(unknown))
        if not isinstance(default_model, str) or default_model not in selected:
            return reject("the default model must be one of the enabled models")

        old_enabled, old_default, error = self._read_model_preferences()
        if error:
            return reject(error)
        # Ids the accounts do not offer right now stay shortlisted (they may come back).
        new_enabled = selected + [item for item in (old_enabled or []) if item not in set(catalog)]
        if new_enabled == old_enabled and default_model == old_default:
            return True
        try:
            settings = _read_private_json(self.agent_dir / "settings.json")
            settings["enabledModels"] = new_enabled
            provider, model = default_model.split("/", 1)
            settings["defaultProvider"] = provider
            settings["defaultModel"] = model
            _write_private_json(self.agent_dir / "settings.json", settings)
        except (OSError, ValueError) as exc:
            return reject("could not save the model settings: %s" % exc)

        # The current model stays while it is allowed; a model this save removed (or no model yet)
        # is replaced by the new default. A conversation already blocked on a disallowed model is
        # not switched silently: it stays blocked until that model is allowed again or one is picked.
        current = self._selected_model
        block_before = self._selection_block
        removed = bool(current) and block_before is None and new_enabled is not None and current not in new_enabled
        if not current or removed:
            self._set_selected_model(default_model, "default")
        self._selection_block = self._block_reason(self._selected_model)
        selection_changed = self._selected_model != current or self._selection_block != block_before
        scope_changed = new_enabled != old_enabled
        if scope_changed and self.can_renew_session():
            launched = self.process_epoch
            self._renew_process(
                False,
                lambda ok, error=None: self._preferences_renewed(launched, ok, error),
                lambda text: self.status_changed.emit("%s: applying model settings: %s" % (self.label, text)),
            )
        elif scope_changed or selection_changed:
            if scope_changed:
                self.status_changed.emit(
                    "%s: model list saved; Pi applies its own model cycling after Reconnect "
                    "(this session cannot be resumed in a new process)" % self.label
                )
            if selection_changed:
                self._gate_selection()
        self._publish_visible_models()
        self.model_preferences_changed.emit()
        return True

    def _preferences_renewed(self, launched: int, ok: bool, error: str | None):
        if self.process_epoch != launched and self.ready:
            self.status_changed.emit("%s: model settings applied; the conversation is kept" % self.label)
        else:
            self.error.emit(
                "%s: model settings were saved but the agent could not be restarted (%s). Use Reconnect to apply them."
                % (self.label, error or "unknown error")
            )


class _PiBackend(SteeringBackend):
    """Adapter that lets the protocol-agnostic controller drive a PiRpcClient."""

    def __init__(self, client: PiRpcClient):
        self.client = client

    def run_active(self) -> bool:
        client = self.client
        return client._busy or client._starting or client._unacked > 0

    def prompt_unacked(self) -> bool:
        return self.client._unacked > 0

    def nuke_tools_running(self) -> list:
        return self.client._activity.nuke_tool_ids()

    def can_renew_session(self) -> bool:
        return self.client.can_renew_session()

    def barrier_set(self, status: dict):
        if status.get("active_operations"):
            self.client._reject_approval_dialogs()

    def abort(self, done, stage):
        self.client._abort_run(done, stage)

    def renew(self, fresh_session: bool, done, detail, restart: bool = True):
        self.client._renew_process(fresh_session, done, detail, restart)

    def deliver(self, batch: list, done):
        client = self.client
        text = INTERVENTION_NOTICE + "\n\n" + "\n\n".join(message.text for message in batch)
        images = [path for message in batch for path in message.images]
        payload = {"type": "prompt", "message": text}
        try:
            if images:
                payload["images"] = client._encode_images(images)
        except OSError as exc:
            done(False, "could not read an attached image: %s" % exc)
            return

        def acknowledged(ok, error=None):
            if ok:
                # Shown only once the agent has the message: chat order == session history order.
                for message in batch:
                    client.user_message.emit(message.text, list(message.images))
            done(ok, error)

        client._dispatch_prompt(payload, acknowledged)

    def withdraw(self, items: list, reason: str):
        self.client._withdraw(items, reason)

    def report_error(self, text: str):
        self.client.error.emit(text)

    def run_interrupted(self):
        self.client._run_interrupted()
