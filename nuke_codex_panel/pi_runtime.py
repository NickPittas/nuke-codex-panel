"""Resolver for the plugin-owned Pi runtime (private Node + official Pi).

The runtime lives in ``<install>/runtime/pi`` and is pinned by ``manifest.json``. The
installer (``install.py``, ``nuke_codex_panel.installer``) provisions it and records
``install-state.json`` only after every download, hash and install step verified. This
module never falls back to a global Node, ``PATH`` or a global Pi installation; any missing
or mismatched piece raises with the exact repair command. It is Qt-free, standard-library
only, never spawns a process, never touches the network and is cheap (file stats plus a few
small hashes), so it is safe to call from the UI thread.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "runtime" / "pi"
PI_VERSION = "1.4.0"
DIAGNOSTICS_PATH = RUNTIME_ROOT / "nuke-runtime.ts"
MANIFEST_PATH = RUNTIME_ROOT / "manifest.json"
AUTH_HELPER_PATH = RUNTIME_ROOT / "auth-helper.mjs"

MANIFEST_SCHEMA = 2
STATE_SCHEMA = 1
STATE_FILENAME = "install-state.json"
PLATFORM_KEYS = ("linux-x64", "win-x64", "darwin-x64", "darwin-arm64")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def host_os_family() -> str:
    """``linux``, ``win`` or ``darwin``; anything else is unsupported."""
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform in ("win32", "cygwin"):
        return "win"
    if sys.platform == "darwin":
        return "darwin"
    raise RuntimeError(f"Private Pi runtime: unsupported operating system {sys.platform!r}.")


def install_hint(root: Path | None = None) -> str:
    """Exact repair instruction for the runtime rooted at ``root`` (default: this plugin's)."""
    root = Path(RUNTIME_ROOT if root is None else root)
    project = root.parents[1]
    script = project / "install.py"
    python = "py -3" if sys.platform == "win32" else "python3"
    if script.is_file():
        return (
            f'Install or repair the private Pi runtime with: {python} "{script}" '
            f'--target "{project}" --no-register (see docs/INSTALLATION.md).'
        )
    return (
        "Install or repair the private Pi runtime by running install.py from the Nuke Codex Panel "
        "source (see docs/INSTALLATION.md)."
    )


def _require_file(path: Path, what: str, root: Path) -> Path:
    if not Path(path).is_file():
        raise FileNotFoundError(f"Private Pi runtime: missing {what} at {path}. {install_hint(root)}")
    return Path(path)


def _require_hash(path: Path, expected: str, what: str, root: Path) -> None:
    actual = sha256_file(_require_file(path, what, root))
    if actual != expected:
        raise RuntimeError(
            f"Private Pi runtime: {what} sha256 {actual} does not match the pinned {expected}. "
            f"{install_hint(root)}"
        )


def load_manifest(path: Path) -> dict:
    """Read and structurally validate a runtime manifest. Raises ``RuntimeError``/``OSError``."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Private Pi runtime: invalid manifest {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != MANIFEST_SCHEMA:
        raise RuntimeError(f"Private Pi runtime: manifest {path} is not schema {MANIFEST_SCHEMA}.")
    if data.get("pi", {}).get("version") != PI_VERSION:
        raise RuntimeError(f"Private Pi runtime: manifest {path} does not pin Pi {PI_VERSION}.")
    node = data.get("node")
    platforms = node.get("platforms") if isinstance(node, dict) else None
    if not isinstance(platforms, dict) or not platforms:
        raise RuntimeError(f"Private Pi runtime: manifest {path} has no Node platform entries.")
    for key, spec in platforms.items():
        needed = ("archive_url", "archive_sha256", "archive_format", "archive_root", "executable", "npm_cli")
        if key not in PLATFORM_KEYS or not isinstance(spec, dict) or any(k not in spec for k in needed):
            raise RuntimeError(f"Private Pi runtime: manifest {path} has an invalid Node platform {key!r}.")
    for section, keys in (
        ("node", ("version", "install_dir")),
        ("pi", ("package", "rpc_entry", "package_json_sha256", "package_lock_sha256", "tarball_integrity")),
        ("credential_env", ("file", "sha256")),
        ("notices", ("dir", "allowed_licenses")),
    ):
        block = data.get(section)
        if not isinstance(block, dict) or any(k not in block for k in keys):
            raise RuntimeError(f"Private Pi runtime: manifest {path} is missing {section} fields.")
    return data


def read_state(root: Path) -> dict:
    """Read ``install-state.json`` (written by the installer after full verification)."""
    path = _require_file(Path(root) / STATE_FILENAME, "installer provenance (install-state.json)", root)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Private Pi runtime: invalid {path}: {exc}. {install_hint(root)}") from exc
    if not isinstance(state, dict) or state.get("schema") != STATE_SCHEMA:
        raise RuntimeError(f"Private Pi runtime: {path} has an unknown schema. {install_hint(root)}")
    return state


def check_runtime(root: Path, manifest: dict, manifest_path: Path) -> tuple[Path, Path]:
    """Cheap fail-closed consistency check of the runtime at ``root``; returns ``(node, rpc_entry)``.

    Verifies the installer's provenance record against the manifest, that the Node executable
    still has the recorded size, the pinned ``package.json``/``package-lock.json`` hashes, and the
    installed Pi version. It does not hash Node or ``node_modules``; ``install.py --check`` does.
    """
    root = Path(root)
    hint = install_hint(root)
    node_spec, pi_spec = manifest["node"], manifest["pi"]
    state = read_state(root)

    if state.get("manifest_sha256") != sha256_file(Path(manifest_path)):
        raise RuntimeError(
            f"Private Pi runtime: the install was made from a different manifest than {manifest_path}. {hint}"
        )
    platform = state.get("platform")
    spec = node_spec["platforms"].get(platform)
    if spec is None or platform.split("-", 1)[0] != host_os_family():
        raise RuntimeError(
            f"Private Pi runtime: installed platform {platform!r} cannot run on this operating system. {hint}"
        )
    recorded = state.get("node") or {}
    if (
        recorded.get("version") != node_spec["version"]
        or recorded.get("archive_sha256") != spec["archive_sha256"]
        or recorded.get("executable") != spec["executable"]
    ):
        raise RuntimeError(
            f"Private Pi runtime: Node recorded as {recorded.get('version')} does not match the "
            f"pinned {node_spec['version']}. {hint}"
        )

    node = _require_file(root / node_spec["install_dir"] / spec["executable"], "private Node binary", root)
    if node.stat().st_size != recorded.get("executable_size"):
        raise RuntimeError(f"Private Pi runtime: {node} changed since it was installed. {hint}")
    if os.name != "nt" and not os.access(node, os.X_OK):
        raise RuntimeError(f"Private Pi runtime: {node} is not executable. {hint}")

    _require_hash(root / "package.json", pi_spec["package_json_sha256"], "package.json", root)
    _require_hash(root / "package-lock.json", pi_spec["package_lock_sha256"], "package-lock.json", root)
    package_dir = root / "node_modules" / Path(*pi_spec["package"].split("/"))
    try:
        installed = json.loads(_require_file(package_dir / "package.json", "installed Pi package", root).read_text("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Private Pi runtime: invalid installed Pi package.json: {exc}. {hint}") from exc
    if installed.get("version") != pi_spec["version"]:
        raise RuntimeError(
            f"Private Pi runtime: Pi {installed.get('version')} installed, manifest pins "
            f"{pi_spec['version']}. {hint}"
        )
    entry = _require_file(root / pi_spec["rpc_entry"], "Pi RPC entry", root)
    _require_file(root / DIAGNOSTICS_PATH.name, "Nuke runtime diagnostics extension", root)
    _require_file(root / manifest["credential_env"]["file"], "credential-env.json", root)
    return node, entry


@lru_cache(maxsize=1)
def _manifest() -> dict:
    return load_manifest(_require_file(MANIFEST_PATH, "manifest", RUNTIME_ROOT))


def resolve_runtime() -> tuple[Path, Path]:
    """Return ``(node, rpc_entry)``: absolute private Node and Pi's official RPC entry.

    ``rpc_entry`` (``dist/bundle/rpc-entry.js``) already runs in RPC mode, so
    callers must not add ``--mode rpc``. Raises ``FileNotFoundError`` or
    ``RuntimeError`` when the owned runtime is absent or does not match the manifest.
    """
    return check_runtime(RUNTIME_ROOT, _manifest(), MANIFEST_PATH)


def runtime_status() -> tuple[bool, str]:
    """``(ok, text)`` for UI display; never raises. Same cost as ``resolve_runtime``."""
    try:
        node, _entry = resolve_runtime()
    except (RuntimeError, OSError) as exc:
        return False, f"Managed Pi {PI_VERSION} unavailable: {exc}"
    return True, f"Managed Pi {PI_VERSION} (private Node: {node})"


@lru_cache(maxsize=1)
def _credential_env() -> dict:
    manifest = _manifest()["credential_env"]
    path = RUNTIME_ROOT / manifest["file"]
    _require_hash(path, manifest["sha256"], "credential-env.json", RUNTIME_ROOT)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("generated_from", {}).get("@earendil-works/pi-coding-agent") != PI_VERSION:
        raise RuntimeError(
            f"Private Pi runtime: {path} was not generated from Pi {PI_VERSION}. {install_hint()}"
        )
    return data


def credential_env_names() -> tuple[str, ...]:
    """Environment variable names that can supply model-provider credentials to Pi.

    Provider API-key names are generated from the pinned pi-ai catalog; cloud
    credential/endpoint selectors (AWS, Google, Azure, Anthropic federation) are
    the documented set in ``generate-credential-env.mjs``. Names only, never values.
    """
    data = _credential_env()
    names = {name for group in data["provider_keys"].values() for name in group}
    names.update(data["cloud_selectors"])
    return tuple(sorted(names))


def pi_control_env_names() -> tuple[str, ...]:
    """Ambient Pi config/session/package controls that must not leak into the private runtime."""
    return tuple(_credential_env()["pi_controls"])


# Ambient names (beyond the generated credential selectors) and prefixes that must never reach a
# managed Pi process. Credential hygiene, not an OS sandbox.
_STRIPPED_NAMES = frozenset({"GOOGLE_APPLICATION_CREDENTIALS", "NODE_OPTIONS", "NODE_PATH"})
_STRIPPED_PREFIXES = ("PI_", "AWS_", "GOOGLE_CLOUD_", "GCLOUD_", "JITI_")


def resolve_auth_helper() -> tuple[Path, Path]:
    """Return ``(node, helper)``: the private Node and the SDK auth helper script. No fallback."""
    node, _entry = resolve_runtime()
    return node, _require_file(AUTH_HELPER_PATH, "Pi auth helper", RUNTIME_ROOT)


def managed_environment(agent_dir: Path | str, session_dir: Path | str | None = None) -> dict[str, str]:
    """Environment overrides every managed (private) Pi process needs."""
    env = {
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "PI_SKIP_VERSION_CHECK": "1",
        "PI_TELEMETRY": "0",
        # jiti's default cache is a shared /tmp directory; disable filesystem caching.
        "JITI_FS_CACHE": "false",
    }
    if session_dir is not None:
        env["PI_CODING_AGENT_SESSION_DIR"] = str(session_dir)
    return env


def managed_environment_removals(names) -> list[str]:
    """Names, among inherited environment ``names``, to drop from a managed Pi process."""
    credentials = frozenset(credential_env_names())
    return [
        name
        for name in names
        if name in credentials or name in _STRIPPED_NAMES or name.startswith(_STRIPPED_PREFIXES)
    ]


def check_sidecar_python(state: dict, root: Path) -> Path:
    """Validate the standalone Python the installer recorded in ``state``; never launches it."""
    hint = install_hint(root)
    recorded = (state.get("python") or {}).get("executable")
    if not isinstance(recorded, str) or not recorded:
        raise RuntimeError(f"Private Pi runtime: no standalone Python is recorded for the Nuke MCP server. {hint}")
    python = Path(recorded)
    if not python.is_absolute() or not python.is_file() or (os.name != "nt" and not os.access(python, os.X_OK)):
        raise FileNotFoundError(
            f"Private Pi runtime: the recorded standalone Python {recorded} is missing or not executable. {hint}"
        )
    if python.name.lower().startswith("nuke"):
        raise RuntimeError(
            f"Private Pi runtime: the recorded Python {recorded} is a Nuke binary, not a standalone Python. {hint}"
        )
    return python


def resolve_sidecar_python() -> Path:
    """Absolute standalone Python for the stdio MCP sidecar, as recorded by the installer.

    Nuke's ``sys.executable`` is the Nuke binary and is never used. Raises ``FileNotFoundError`` or
    ``RuntimeError`` (with the repair command) when the receipt is missing or the interpreter is gone.
    Cheap: reads the install receipt and stats the interpreter; no process is started.
    """
    return check_sidecar_python(read_state(RUNTIME_ROOT), RUNTIME_ROOT)
