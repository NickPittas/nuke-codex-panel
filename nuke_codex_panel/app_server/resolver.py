"""Resolve coding-agent CLI binaries from anywhere.

Desktop-launched Nuke inherits a stripped PATH, so plain ``shutil.which`` misses
binaries an interactive shell can see. We search the common global-install
roots in addition to PATH and an explicit ``NUKE_*_BIN`` override per backend.
Results are cached for the Nuke session.
"""

from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path

# ponytail: per-backend (binary_name, env_override). NUKE_<NAME>_BIN convention.
BACKENDS: dict[str, tuple[str, str]] = {
    "codex": ("codex", "NUKE_CODEX_BIN"),
    "opencode": ("opencode", "NUKE_OPENCODE_BIN"),
    "claude": ("claude", "NUKE_CLAUDE_BIN"),
}

# Display labels for the backend selector (incl. detected-but-unimplemented).
BACKEND_DISPLAY: dict[str, str] = {
    "codex": "Codex",
    "opencode": "OpenCode",
    "claude": "Claude",
}


@lru_cache(maxsize=1)
def _search_path() -> list[str]:
    """PATH augmented with common global-install roots (cached per session)."""
    home = Path.home()
    roots = [
        home / ".local" / "bin",
        home / ".npm-global" / "bin",
        home / ".local" / "npm-global" / "bin",
        home / ".cargo" / "bin",
        home / ".bun" / "bin",
        home / ".opencode" / "bin",
        home / ".volta" / "bin",
        Path("/usr/local/bin"),
        Path("/opt/homebrew/bin"),
        Path("/usr/bin"),
    ]
    # nvm installs one bin dir per node version
    nvm_versions = home / ".nvm" / "versions" / "node"
    if nvm_versions.is_dir():
        roots += sorted(nvm_versions.glob("*/bin"))
    return [str(p) for p in roots if p.is_dir()]


@lru_cache(maxsize=None)
def resolve(name: str) -> str | None:
    """Resolve a backend binary to an absolute path, or None if not found.

    Order: explicit env override, then PATH/augmented-roots ``which``, then a
    direct file check in each root (covers desktop Nuke with an empty PATH).
    """
    backend = BACKENDS.get(name)
    if backend is None:
        return None
    binary, env_var = backend
    roots = _search_path()
    augmented = os.pathsep.join([*roots, os.environ.get("PATH", "")])
    candidates = [
        os.environ.get(env_var),
        shutil.which(binary, path=augmented),
        *(str(Path(root) / binary) for root in roots),
    ]
    return next((p for p in candidates if p and Path(p).is_file()), None)


def resolve_codex_binary() -> str | None:
    """Backward-compatible codex resolver used by CodexAppServerClient."""
    return resolve("codex")


def detected_backends() -> dict[str, str]:
    """Map each available backend name to its resolved binary path."""
    return {name: path for name in BACKENDS if (path := resolve(name))}


if __name__ == "__main__":  # ponytail: smallest self-check of resolution logic
    for name, path in detected_backends().items():
        print(f"{name}: {path}")
    missing = [n for n in BACKENDS if not resolve(n)]
    print("missing:", ", ".join(missing) if missing else "none")
