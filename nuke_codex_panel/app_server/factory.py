"""Backend factory: select a coding-agent backend by key.

Implemented backends register here; unimplemented keys (a detected CLI whose
adapter lands in a later phase) resolve to None so the UI reports a graceful
"not available yet" instead of crashing.
"""

from __future__ import annotations

from PySide6 import QtCore

from .base import BackendClient
from .claude import ClaudeBackend
from .client import CodexAppServerClient
from .opencode import OpencodeBackend

_IMPLEMENTED: dict[str, type[BackendClient]] = {
    "codex": CodexAppServerClient,
    "opencode": OpencodeBackend,
    "claude": ClaudeBackend,
}


def implemented_backends() -> list[str]:
    """Keys with a working adapter."""
    return list(_IMPLEMENTED)


def create_backend(
    key: str, cwd: str, parent: QtCore.QObject | None = None, bridge_path: str | None = None
) -> BackendClient | None:
    """Return a backend instance for key, or None if no adapter is implemented yet."""
    cls = _IMPLEMENTED.get(key)
    if cls is None:
        return None
    return cls(cwd, parent=parent, bridge_path=bridge_path)
