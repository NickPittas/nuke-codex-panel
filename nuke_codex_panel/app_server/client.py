"""Backward-compatible shim; the Codex client now lives in harnesses.codex."""

import os
from pathlib import Path

from ..harnesses.base import resolve_binary
from ..harnesses.codex import CodexClient as CodexAppServerClient


def resolve_codex_binary() -> str | None:
    return resolve_binary(
        "NUKE_CODEX_BIN",
        "codex",
        [
            str(Path.home() / ".npm-global" / "bin" / "codex"),
            str(Path.home() / ".local" / "bin" / "codex"),
        ],
    )


__all__ = ["CodexAppServerClient", "resolve_codex_binary"]
