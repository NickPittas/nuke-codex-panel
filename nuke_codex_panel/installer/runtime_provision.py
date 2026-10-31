"""Provision the private Node + official Pi runtime into a runtime directory.

Everything is pinned by ``runtime/pi/manifest.json``: the official Node archive is downloaded
over verified TLS and must match the manifest's SHA-256; Pi and its dependencies come from the
pinned ``package-lock.json`` (sha512 integrity enforced by npm) installed by the private Node's
own npm with ``npm ci --ignore-scripts``. No global Node/npm/Pi, ``PATH``, ``~/.npmrc``,
``NODE_OPTIONS``/``NODE_PATH``/``npm_config_*`` or credential environment is ever consulted:
child processes run with a freshly built environment and empty, owned npm config files.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import posixpath
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .. import pi_runtime
from .common import InstallError, atomic_write, force_rmtree, log, rename, run, tail
from .notices import generate_notices, verify_notices

_MAX_EXTRACTED_BYTES = 2 * 1024 ** 3
_PROXY_NAMES = ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "ALL_PROXY")
_CA_NAMES = ("SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS")
_WINDOWS_BASE_ENV = ("SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "PATHEXT", "WINDIR", "PROCESSOR_ARCHITECTURE")


def detect_platform_key() -> str:
    """The pinned Node platform for this machine (real hardware on macOS, even under Rosetta)."""
    family = pi_runtime.host_os_family()
    machine = platform.machine().lower()
    x64 = machine in ("x86_64", "amd64")
    if family == "darwin":
        arm = machine in ("arm64", "aarch64")
        if not arm:
            try:
                result = subprocess.run(
                    ["/usr/sbin/sysctl", "-n", "hw.optional.arm64"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    universal_newlines=True,
                    timeout=10,
                    check=False,
                )
                arm = result.stdout.strip() == "1"
            except (OSError, subprocess.SubprocessError):
                arm = False
        return "darwin-arm64" if arm else "darwin-x64"
    if x64:
        return family + "-x64"
    raise InstallError(
        "unsupported CPU architecture {!r} for {}: the pinned Node runtime supports {}.".format(
            machine, family, ", ".join(pi_runtime.PLATFORM_KEYS)
        )
    )


def _base_env(work: Path, node_dir: Path) -> dict:
    """A fresh environment: private temp/home, PATH limited to the private Node, no ambient config."""
    home = work / "home"
    temp = work / "tmp"
    for path in (home, temp):
        path.mkdir(parents=True, exist_ok=True)
    env = {"PATH": str(node_dir), "HOME": str(home), "TMPDIR": str(temp)}
    if os.name == "nt":
        for name in _WINDOWS_BASE_ENV:
            if os.environ.get(name):
                env[name] = os.environ[name]
        env.update(
            USERPROFILE=str(home),
            APPDATA=str(home / "AppData" / "Roaming"),
            LOCALAPPDATA=str(home / "AppData" / "Local"),
            TEMP=str(temp),
            TMP=str(temp),
        )
    for name in _PROXY_NAMES + _CA_NAMES:
        for variant in (name, name.lower()):
            if os.environ.get(variant):
                env[variant] = os.environ[variant]
    return env


def _npm_env(work: Path, node_dir: Path, registry: str) -> dict:
    env = _base_env(work, node_dir)
    userrc, globalrc = work / "userrc", work / "globalrc"
    userrc.write_text("", encoding="utf-8")
    globalrc.write_text("", encoding="utf-8")
    env.update(
        npm_config_userconfig=str(userrc),
        npm_config_globalconfig=str(globalrc),
        npm_config_cache=str(work / "npm-cache"),
        npm_config_prefix=str(work / "npm-prefix"),
        npm_config_registry=registry,
        npm_config_ignore_scripts="true",
        npm_config_audit="false",
        npm_config_fund="false",
        npm_config_update_notifier="false",
        npm_config_progress="false",
        npm_config_fetch_retries="3",
    )
    return env


def node_probe_env(work: Path, node_dir: Path) -> dict:
    return _base_env(work, node_dir)


def installed_node_version(node: Path, work: Path) -> str:
    result = run([node, "--version"], cwd=work, env=node_probe_env(work, node.parent), timeout=60)
    if result.returncode != 0:
        raise InstallError("the private Node does not run: " + tail(result.stderr or result.stdout, 5))
    return result.stdout.strip()


# --- download -------------------------------------------------------------------------------------


class _HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).scheme != "https":
            raise urllib.error.URLError("refusing a redirect to a non-https URL: " + newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url: str, destination: Path, expected_sha256: str) -> None:
    """Download ``url`` (https only, certificates verified) and require the pinned SHA-256."""
    if urllib.parse.urlparse(url).scheme != "https":
        raise InstallError("refusing non-https download URL: " + url)
    opener = urllib.request.build_opener(_HttpsOnlyRedirects())
    request = urllib.request.Request(url, headers={"User-Agent": "nuke-codex-panel-installer"})
    digest = hashlib.sha256()
    partial = destination.with_name(destination.name + ".part")
    log("Downloading " + url)
    try:
        with opener.open(request, timeout=60) as response, open(str(partial), "wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            done, reported = 0, 0
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                digest.update(chunk)
                handle.write(chunk)
                done += len(chunk)
                if total and done * 10 // total > reported:
                    reported = done * 10 // total
                    log("  {}% ({:.1f} of {:.1f} MiB)".format(reported * 10, done / 1048576, total / 1048576))
    except urllib.error.URLError as exc:
        hint = ""
        if "CERTIFICATE" in str(exc).upper():
            hint = (
                " TLS certificate verification failed; the installer never disables it. On macOS python.org "
                "builds run 'Install Certificates.command', or set SSL_CERT_FILE to a CA bundle."
            )
        raise InstallError("download failed: {}.{}".format(exc, hint)) from exc
    except (OSError, ValueError) as exc:
        raise InstallError("download failed: {}".format(exc)) from exc
    if digest.hexdigest() != expected_sha256:
        raise InstallError(
            "downloaded archive sha256 {} does not match the pinned {} ({}).".format(
                digest.hexdigest(), expected_sha256, url
            )
        )
    os.replace(str(partial), str(destination))


# --- safe extraction ------------------------------------------------------------------------------


def _checked_member_path(name: str) -> str:
    normal = posixpath.normpath(name.replace("\\", "/"))
    if normal.startswith("/") or normal == ".." or normal.startswith("../") or re.match(r"^[A-Za-z]:", normal):
        raise InstallError("unsafe path in archive: " + name)
    return normal


def extract_archive(archive: Path, fmt: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if fmt == "tar.gz":
        with tarfile.open(str(archive), "r:gz") as tar:
            members, total = tar.getmembers(), 0
            for member in members:
                base = _checked_member_path(member.name)
                total += max(member.size, 0)
                if member.isdir() or member.isreg():
                    pass
                elif member.issym():
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(base), member.linkname))
                    if member.linkname.startswith("/") or target == ".." or target.startswith("../"):
                        raise InstallError("symlink escapes the archive: {} -> {}".format(member.name, member.linkname))
                elif member.islnk():
                    _checked_member_path(member.linkname)
                else:
                    raise InstallError("unsupported entry type in archive: " + member.name)
            if total > _MAX_EXTRACTED_BYTES:
                raise InstallError("archive expands beyond the size limit")
            kwargs = {"filter": "tar"} if hasattr(tarfile, "tar_filter") else {}
            tar.extractall(str(destination), members=members, **kwargs)
    elif fmt == "zip":
        with zipfile.ZipFile(str(archive)) as bundle:
            infos = bundle.infolist()
            if sum(i.file_size for i in infos) > _MAX_EXTRACTED_BYTES:
                raise InstallError("archive expands beyond the size limit")
            for info in infos:
                _checked_member_path(info.filename)
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise InstallError("symlink entry in zip archive: " + info.filename)
            bundle.extractall(str(destination))
    else:
        raise InstallError("unsupported archive format " + fmt)


# --- verification ---------------------------------------------------------------------------------


def verify_node_modules(runtime_dir: Path) -> list:
    """Problems found comparing installed packages with ``package-lock.json`` (versions only)."""
    problems = []
    lock = json.loads((runtime_dir / "package-lock.json").read_text(encoding="utf-8"))
    for key, entry in lock.get("packages", {}).items():
        if not key or entry.get("link"):
            continue
        manifest = runtime_dir.joinpath(*key.split("/")) / "package.json"
        if not manifest.is_file():
            if not entry.get("optional"):
                problems.append("missing package " + key)
            continue
        try:
            installed = json.loads(manifest.read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError):
            problems.append("unreadable " + str(manifest))
            continue
        if installed != entry.get("version"):
            problems.append("{} is {} but the lock pins {}".format(key, installed, entry.get("version")))
    return problems


def verify_sources(runtime_dir: Path, manifest: dict) -> None:
    """The source files next to the manifest must be the pinned ones."""
    pi_spec, cred = manifest["pi"], manifest["credential_env"]
    for filename, expected in (
        ("package.json", pi_spec["package_json_sha256"]),
        ("package-lock.json", pi_spec["package_lock_sha256"]),
        (cred["file"], cred["sha256"]),
    ):
        path = runtime_dir / filename
        if not path.is_file():
            raise InstallError("runtime source file missing: {}".format(path))
        actual = pi_runtime.sha256_file(path)
        if actual != expected:
            raise InstallError(
                "{} sha256 {} does not match the manifest pin {}; update the manifest deliberately "
                "(see runtime/pi/README.md) rather than installing unpinned files.".format(path, actual, expected)
            )
    lock = json.loads((runtime_dir / "package-lock.json").read_text(encoding="utf-8"))
    locked = lock.get("packages", {}).get("node_modules/" + pi_spec["package"], {})
    if locked.get("version") != pi_spec["version"] or locked.get("integrity") != pi_spec["tarball_integrity"]:
        raise InstallError("package-lock.json does not pin {} {} with the manifest integrity".format(
            pi_spec["package"], pi_spec["version"]))
    for name in ("nuke-runtime.ts", "auth-helper.mjs"):
        if not (runtime_dir / name).is_file():
            raise InstallError("owned runtime file missing: {}".format(runtime_dir / name))


def verify_runtime_deep(runtime_dir: Path, manifest: dict, work: Path, check_notices: bool = True) -> list:
    """Full read-only verification of an installed runtime. Returns problems (empty = good).

    Beyond the resolver's cheap checks: re-hashes the Node executable against the recorded hash (and
    the manifest pin where one exists), runs ``node --version``, compares installed packages with the
    lock, verifies the credential list and the license index.
    """
    problems = []
    try:
        node, _entry = pi_runtime.check_runtime(runtime_dir, manifest, runtime_dir / "manifest.json")
    except (RuntimeError, OSError) as exc:
        return [str(exc)]
    state = pi_runtime.read_state(runtime_dir)
    spec = manifest["node"]["platforms"][state["platform"]]
    recorded = state["node"]
    actual = pi_runtime.sha256_file(node)
    if actual != recorded.get("executable_sha256"):
        problems.append("Node executable hash differs from the recorded install")
    if spec.get("binary_sha256") and actual != spec["binary_sha256"]:
        problems.append("Node executable hash differs from the manifest pin")
    if state["platform"].split("-", 1)[0] == pi_runtime.host_os_family():
        try:
            found = installed_node_version(node, work)
            if found != "v" + manifest["node"]["version"]:
                problems.append("Node reports {} but {} is pinned".format(found, manifest["node"]["version"]))
        except InstallError as exc:
            problems.append(str(exc))
    try:
        verify_sources(runtime_dir, manifest)
    except InstallError as exc:
        problems.append(str(exc))
    problems.extend(verify_node_modules(runtime_dir))
    if check_notices:
        notices = runtime_dir / manifest["notices"]["dir"] / "index.json"
        if not notices.is_file():
            problems.append("license index missing: " + str(notices))
        elif pi_runtime.sha256_file(notices) != (state.get("notices") or {}).get("index_sha256"):
            problems.append("license index changed since it was installed")
        else:
            problems.extend(verify_notices(notices.parent, runtime_dir, manifest))
    if not (runtime_dir / "node_modules").is_dir():
        problems.append("node_modules missing")
    return problems


# --- provisioning ---------------------------------------------------------------------------------


def _python_record() -> dict:
    executable = sys.executable or ""
    if sys.platform == "win32" and sys.prefix != sys.base_prefix:
        # A venv's python.exe is a launcher shim that starts the base interpreter as a child process, so
        # the pid the panel launches would not be the interpreter's own; record the real interpreter.
        executable = getattr(sys, "_base_executable", None) or executable
    return {
        "executable": os.path.abspath(executable) if executable else "",
        "version": "{}.{}.{}".format(*sys.version_info[:3]),
    }


def finalize_runtime(
    *,
    runtime_dir: Path,
    project_root: Path,
    manifest: dict,
    platform_key: str,
    origin: str,
    out_dir: Path | None = None,
) -> dict:
    """Generate the license inventory and write ``install-state.json`` last (provenance record).

    ``runtime_dir`` holds Node, ``node_modules`` and the pinned sources; the inventory and receipt go
    to ``out_dir`` (default ``runtime_dir``) so they can be staged and activated atomically.
    """
    out_dir = runtime_dir if out_dir is None else out_dir
    spec = manifest["node"]["platforms"][platform_key]
    node = runtime_dir / manifest["node"]["install_dir"] / spec["executable"]
    if not node.is_file():
        raise InstallError("Node executable missing after install: {}".format(node))
    notices_dir = out_dir / manifest["notices"]["dir"]
    if notices_dir.exists():
        force_rmtree(notices_dir)
    index = generate_notices(
        runtime_dir=runtime_dir, project_root=project_root, manifest=manifest, node_spec=spec, out_dir=notices_dir
    )
    state = {
        "schema": pi_runtime.STATE_SCHEMA,
        "platform": platform_key,
        "origin": origin,
        "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "manifest_sha256": pi_runtime.sha256_file(runtime_dir / "manifest.json"),
        "node": {
            "version": manifest["node"]["version"],
            "archive_sha256": spec["archive_sha256"],
            "executable": spec["executable"],
            "executable_sha256": pi_runtime.sha256_file(node),
            "executable_size": node.stat().st_size,
        },
        "pi": {
            "package": manifest["pi"]["package"],
            "version": manifest["pi"]["version"],
            "tarball_integrity": manifest["pi"]["tarball_integrity"],
        },
        "notices": {
            "index_sha256": pi_runtime.sha256_file(notices_dir / "index.json"),
            "packages": index["summary"]["packages"],
            "unresolved": index["unresolved"],
        },
        "python": _python_record(),
    }
    atomic_write(out_dir / pi_runtime.STATE_FILENAME, (json.dumps(state, indent=2) + "\n").encode("utf-8"))
    return state


def install_fresh(*, runtime_dir: Path, project_root: Path, manifest: dict, platform_key: str, work: Path) -> dict:
    """Download Node, ``npm ci`` Pi, finalize. ``runtime_dir`` already holds the pinned sources."""
    spec = manifest["node"]["platforms"][platform_key]
    verify_sources(runtime_dir, manifest)
    work.mkdir(parents=True, exist_ok=True)

    archive = work / posixpath.basename(urllib.parse.urlparse(spec["archive_url"]).path)
    download(spec["archive_url"], archive, spec["archive_sha256"])
    extracted = work / "node-extract"
    log("Extracting Node " + manifest["node"]["version"])
    extract_archive(archive, spec["archive_format"], extracted)
    root = extracted / spec["archive_root"]
    if not root.is_dir():
        raise InstallError("unexpected Node archive layout: {} missing".format(spec["archive_root"]))
    node_dir = runtime_dir / manifest["node"]["install_dir"]
    if node_dir.exists():
        raise InstallError("refusing to extract over existing " + str(node_dir))
    shutil.move(str(root), str(node_dir))
    archive.unlink()

    node = node_dir / spec["executable"]
    if not node.is_file():
        raise InstallError("Node executable missing from the archive: " + spec["executable"])
    if os.name != "nt":
        node.chmod(0o755)
    actual = pi_runtime.sha256_file(node)
    if spec.get("binary_sha256") and actual != spec["binary_sha256"]:
        raise InstallError("Node executable sha256 {} does not match the pin {}".format(actual, spec["binary_sha256"]))
    found = installed_node_version(node, work)
    if found != "v" + manifest["node"]["version"]:
        raise InstallError("Node reports {} but {} is pinned".format(found, manifest["node"]["version"]))

    npm_cli = node_dir.joinpath(*spec["npm_cli"].split("/"))
    if not npm_cli.is_file():
        raise InstallError("npm missing from the Node archive: " + str(npm_cli))
    log("Installing Pi {} from the pinned lockfile (npm ci --ignore-scripts)".format(manifest["pi"]["version"]))
    result = run(
        [node, npm_cli, "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--no-update-notifier"],
        cwd=runtime_dir,
        env=_npm_env(work, node.parent, manifest["pi"]["registry"]),
        timeout=1800,
    )
    if result.returncode != 0:
        raise InstallError("npm ci failed (exit {}):\n{}".format(result.returncode, tail(result.stderr or result.stdout)))

    problems = verify_node_modules(runtime_dir)
    entry = runtime_dir / manifest["pi"]["rpc_entry"]
    if not entry.is_file():
        problems.append("Pi RPC entry missing: " + str(entry))
    if problems:
        raise InstallError("Pi install is inconsistent with the lockfile:\n  " + "\n  ".join(problems[:20]))
    return finalize_runtime(
        runtime_dir=runtime_dir, project_root=project_root, manifest=manifest,
        platform_key=platform_key, origin="installed",
    )


def reusable_kind(existing: Path, manifest: dict, manifest_path: Path, platform_key: str, work: Path):
    """``'valid'``, ``'legacy'`` or ``None`` for the runtime directory ``existing``.

    'valid' = installer-provisioned for exactly this manifest and platform, and it passes the full
    deep verification. 'legacy' = a pre-installer runtime (no provenance record) whose Node
    executable matches the manifest's pinned binary hash and whose packages match the lock: it is
    adopted without a download. Anything else (including a corrupt one) is not reused.
    """
    existing_manifest = existing / "manifest.json"
    if not existing_manifest.is_file():
        return None
    if (existing / pi_runtime.STATE_FILENAME).is_file():
        try:
            state = pi_runtime.read_state(existing)
            if (
                state.get("platform") != platform_key
                or pi_runtime.sha256_file(existing_manifest) != pi_runtime.sha256_file(manifest_path)
            ):
                return None
            return "valid" if not verify_runtime_deep(existing, manifest, work, check_notices=False) else None
        except (RuntimeError, OSError, ValueError, KeyError):
            return None
    spec = manifest["node"]["platforms"][platform_key]
    node = existing / manifest["node"]["install_dir"] / spec["executable"]
    if not spec.get("binary_sha256") or not node.is_file():
        return None
    try:
        if pi_runtime.sha256_file(node) != spec["binary_sha256"]:
            return None
        verify_sources(existing, manifest)
        if verify_node_modules(existing) or not (existing / manifest["pi"]["rpc_entry"]).is_file():
            return None
        if installed_node_version(node, work) != "v" + manifest["node"]["version"]:
            return None
    except (InstallError, OSError, ValueError, KeyError):
        return None
    return "legacy"
