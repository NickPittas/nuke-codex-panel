"""Process-wide bridge lifecycle, independent of any open panel."""

from __future__ import annotations

import atexit
import itertools
import weakref

from PySide6 import QtCore, QtWidgets

from .approval import confirm_python_execution
from .server import NukeBridgeServer


_bridge = None
_stopped = False
_trust_sources = {}
_trust_ids = itertools.count()


def register_trust_source(is_trusted):
    """Register an open panel's "Trusted Python session" check.

    ``is_trusted`` MUST be a bound method; it is held weakly so a closed or
    destroyed panel can never be kept alive or consulted. Returns an idempotent
    ``unregister()`` callable to call when the panel closes.
    """
    key = next(_trust_ids)
    _trust_sources[key] = weakref.WeakMethod(is_trusted)

    def unregister():
        _trust_sources.pop(key, None)

    return unregister


def _trusted_by_open_panel() -> bool:
    """Skip the dialog only when exactly one live panel exists and trusts the session.

    Requests cannot be attributed to a pane, so with several panes open the
    per-request dialog is always used; trust is never merged across panes.
    """
    live = []
    for key, ref in list(_trust_sources.items()):
        method = ref()
        if method is None:
            _trust_sources.pop(key, None)
            continue
        live.append((key, method))
    if len(live) != 1:
        return False
    key, method = live[0]
    try:
        return bool(method())
    except RuntimeError:
        # Underlying Qt widget is already deleted.
        _trust_sources.pop(key, None)
        return False


def approve_python(code: str) -> bool:
    """Bridge approval policy: panel trust if applicable, else the shared dialog."""
    if _trusted_by_open_panel():
        return True
    return confirm_python_execution(code, QtWidgets.QApplication.activeWindow())


def _unlink_discovery():
    bridge = _bridge
    path = getattr(bridge, "discovery_path", None)
    if path:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def _shutdown():
    """Stop the bridge and remove its discovery file; runs once at Qt quit."""
    global _bridge, _stopped
    _stopped = True
    bridge, _bridge = _bridge, None
    _trust_sources.clear()
    if bridge is not None:
        try:
            bridge.stop()
        except RuntimeError:
            # Qt objects already torn down; fall back to removing discovery only.
            path = bridge.discovery_path
            if path:
                path.unlink(missing_ok=True)


def _discard(bridge):
    """Close and delete a bridge that never became the process-wide instance."""
    path = bridge.discovery_path
    bridge.stop()
    if path:
        path.with_suffix(".tmp").unlink(missing_ok=True)
    bridge.setParent(None)
    bridge.deleteLater()


def ensure_bridge() -> NukeBridgeServer:
    """Return the single started bridge, creating it on first use.

    Parented to the Qt application and stopped on ``aboutToQuit``. Raises
    ``RuntimeError`` if there is no QApplication, the process is shutting down,
    or the listener fails to start (a failed instance is discarded so a later
    call may retry).
    """
    global _bridge
    if _stopped:
        raise RuntimeError("Nuke bridge is shut down: application is quitting")
    if _bridge is not None:
        if _bridge.start():
            return _bridge
        raise RuntimeError("Nuke bridge failed to restart: %s" % _bridge.server.errorString())

    app = QtCore.QCoreApplication.instance()
    if app is None:
        raise RuntimeError("Nuke bridge needs a running Qt application")

    bridge = NukeBridgeServer(approve_python, app)
    try:
        started = bridge.start()
        error = None if started else bridge.server.errorString()
    except BaseException:
        _discard(bridge)
        raise
    if not started:
        _discard(bridge)
        raise RuntimeError("Nuke bridge failed to start: %s" % error)

    _bridge = bridge
    app.aboutToQuit.connect(_shutdown)
    atexit.register(_unlink_discovery)
    return bridge
