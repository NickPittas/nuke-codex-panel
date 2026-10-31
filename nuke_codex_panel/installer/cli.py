"""Command line of ``install.py``: install, repair, ``--check`` and Nuke registration."""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .. import pi_runtime
from . import registration, runtime_provision, stage
from .common import InstallError, force_rmtree, link_or_copy_tree, log, sibling_temp, warn

DEFAULT_NUKE_DIR = Path("~/.nuke")
DEFAULT_TARGET = DEFAULT_NUKE_DIR / "nuke-codex-panel"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="install.py",
        description=(
            "Install or verify the Nuke Codex Panel plugin with its private official Pi runtime "
            "(pinned Node + Pi). Run it with a standalone Python 3.11+, not Nuke's Python."
        ),
    )
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="install directory (default: %(default)s)")
    parser.add_argument(
        "--nuke-dir", default=str(DEFAULT_NUKE_DIR),
        help="Nuke user directory whose init.py/menu.py register the plugin (default: %(default)s)",
    )
    parser.add_argument(
        "--no-register", action="store_true",
        help="do not read or change init.py/menu.py (also skips the registration part of --check)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="read-only: verify an existing install (runtime, hashes, Node, licenses, Python, registration)",
    )
    return parser


def _ensure_standalone_python() -> None:
    executable = sys.executable or ""
    if "nuke" in sys.modules or not executable or Path(executable).name.lower().startswith("nuke"):
        raise InstallError(
            "install.py must run with a standalone Python 3.11+ (python3 / py -3), not Nuke's Python: "
            "Nuke's interpreter is the Nuke binary and cannot host the MCP server."
        )
    if sys.version_info < (3, 11):
        raise InstallError("Python 3.11 or newer is required (found {}).".format(sys.version.split()[0]))
    try:
        import ctypes  # noqa: F401  (the MCP sidecar registers its process identity through ctypes)
    except ImportError as exc:
        raise InstallError("this Python has no ctypes module, which the MCP sidecar requires: {}".format(exc)) from exc


@contextlib.contextmanager
def _install_lock(target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.parent / ".{}.install.lock".format(target.name)
    try:
        descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise InstallError(
            "another install of {} is running (lock file {}); if none is, delete that file.".format(target, lock)
        ) from None
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        yield
    finally:
        with contextlib.suppress(OSError):
            lock.unlink()


def _copy_runtime_sources(source_pi: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for entry in os.scandir(str(source_pi)):
        if entry.is_file(follow_symlinks=False):
            shutil.copy2(entry.path, str(destination / entry.name))


def _report_notices(state: dict) -> None:
    unresolved = (state.get("notices") or {}).get("unresolved") or []
    log("License inventory: {} packages under runtime/pi/third-party-notices (index.json).".format(
        (state.get("notices") or {}).get("packages", "?")))
    if unresolved:
        warn(
            "{} package(s) ship no verified upstream license text and are flagged unresolved in the index: {}".format(
                len(unresolved), ", ".join(unresolved)
            )
        )


def _install(args, source_root: Path) -> int:
    _ensure_standalone_python()
    stage.validate_source(source_root)
    manifest_path = source_root / stage.RUNTIME_REL / "manifest.json"
    manifest = pi_runtime.load_manifest(manifest_path)
    key = runtime_provision.detect_platform_key()
    if key not in manifest["node"]["platforms"]:
        raise InstallError("the manifest has no Node runtime for {}".format(key))

    target = Path(os.path.abspath(os.path.expanduser(args.target)))
    nuke_dir = Path(os.path.abspath(os.path.expanduser(args.nuke_dir)))
    mode = stage.classify_target(target, source_root, nuke_dir)
    log("Target: {} ({})  Platform: {}  Python: {}".format(target, mode, key, sys.executable))

    discarded: list = []
    with _install_lock(target):
        work = sibling_temp(target, "work")
        staging = sibling_temp(target, "installing") if mode != "in-place" else None
        try:
            work.mkdir(parents=True)
            if mode == "in-place":
                state = _install_in_place(target, manifest, key, work, discarded)
            else:
                state = _install_copy(source_root, target, mode, staging, manifest, key, work, discarded)
        except BaseException:
            if staging is not None and staging.exists():
                force_rmtree(staging)
            raise
        finally:
            force_rmtree(work)
        for path in discarded:
            try:
                force_rmtree(path)
            except OSError as exc:
                warn("could not remove the replaced {}: {}".format(path, exc))

    final = target / stage.RUNTIME_REL
    node, _entry = pi_runtime.check_runtime(final, pi_runtime.load_manifest(final / "manifest.json"), final / "manifest.json")
    pi_runtime.check_sidecar_python(state, final)
    log("Runtime ready: Node {} at {} ; Pi {}".format(manifest["node"]["version"], node, manifest["pi"]["version"]))
    log("MCP sidecar Python: " + state["python"]["executable"])
    _report_notices(state)

    if args.no_register:
        log("Registration skipped (--no-register).")
    else:
        for line in registration.register(nuke_dir, target):
            log(line)
        log("Restart Nuke to load the panel.")
    log("Install complete.")
    return 0


def _install_in_place(target: Path, manifest: dict, key: str, work: Path, discarded: list) -> dict:
    pi_dir = target / stage.RUNTIME_REL
    manifest_path = pi_dir / "manifest.json"
    staged = pi_dir / ".install-{}".format(os.getpid())
    if staged.exists():
        force_rmtree(staged)
    staged.mkdir()
    try:
        kind = runtime_provision.reusable_kind(pi_dir, manifest, manifest_path, key, work)
        if kind:
            log("Existing private runtime is {}; keeping it.".format("verified" if kind == "valid" else "pre-installer and adopted"))
            state = runtime_provision.finalize_runtime(
                runtime_dir=pi_dir, project_root=target, manifest=manifest, platform_key=key,
                origin=kind, out_dir=staged,
            )
        else:
            _copy_runtime_sources(pi_dir, staged)
            state = runtime_provision.install_fresh(
                runtime_dir=staged, project_root=target, manifest=manifest, platform_key=key, work=work,
            )
            problems = runtime_provision.verify_runtime_deep(staged, manifest, work)
            if problems:
                raise InstallError("new runtime failed verification:\n  " + "\n  ".join(problems[:20]))
        stage.activate_in_place(pi_dir, staged, manifest, discarded)
    finally:
        force_rmtree(staged)
    return state


def _install_copy(source_root, target, mode, staging, manifest, key, work, discarded) -> dict:
    stage.build_stage(source_root, staging)
    stage_pi = staging / stage.RUNTIME_REL
    existing = target / stage.RUNTIME_REL
    kind = None
    if mode == "update":
        kind = runtime_provision.reusable_kind(existing, manifest, stage_pi / "manifest.json", key, work)
    if kind:
        log("Existing private runtime is {}; reusing it.".format("verified" if kind == "valid" else "pre-installer and adopted"))
        link_or_copy_tree(existing / manifest["node"]["install_dir"], stage_pi / manifest["node"]["install_dir"])
        link_or_copy_tree(existing / "node_modules", stage_pi / "node_modules")
        state = runtime_provision.finalize_runtime(
            runtime_dir=stage_pi, project_root=staging, manifest=manifest, platform_key=key, origin=kind,
        )
    else:
        state = runtime_provision.install_fresh(
            runtime_dir=stage_pi, project_root=staging, manifest=manifest, platform_key=key, work=work,
        )
    problems = runtime_provision.verify_runtime_deep(stage_pi, manifest, work)
    if problems:
        raise InstallError("new runtime failed verification:\n  " + "\n  ".join(problems[:20]))
    stage.activate_copy(staging, target, mode, discarded)
    return state


# --- --check --------------------------------------------------------------------------------------


def _check(args, source_root: Path) -> int:
    target = Path(os.path.abspath(os.path.expanduser(args.target)))
    nuke_dir = Path(os.path.abspath(os.path.expanduser(args.nuke_dir)))
    pi_dir = target / stage.RUNTIME_REL
    failures, warnings = [], []

    def ok(text):
        log("ok:   " + text)

    def fail(text):
        failures.append(text)
        log("FAIL: " + text)

    log("Checking {} (read-only)".format(target))
    for relative in ("install.py", "nuke_codex_panel/__init__.py", "nuke_codex_panel/pi_runtime.py",
                     "runtime/pi/nuke-runtime.ts", "runtime/pi/auth-helper.mjs", "LICENSE"):
        if (target / relative).is_file():
            ok("present: " + relative)
        else:
            fail("missing: " + relative)

    manifest = None
    try:
        manifest = pi_runtime.load_manifest(pi_dir / "manifest.json")
        ok("manifest schema {} pins Node {} and Pi {}".format(
            manifest["schema"], manifest["node"]["version"], manifest["pi"]["version"]))
    except (RuntimeError, OSError) as exc:
        fail(str(exc))
    if manifest is not None:
        work = Path(tempfile.mkdtemp(prefix="nuke-codex-panel-check-"))
        try:
            problems = runtime_provision.verify_runtime_deep(pi_dir, manifest, work)
        finally:
            force_rmtree(work)
        if problems:
            for problem in problems:
                fail(problem)
        else:
            ok("runtime verified: provenance, Node hash + version, pinned sources, locked packages, license index")
        try:
            state = pi_runtime.read_state(pi_dir)
            python = pi_runtime.check_sidecar_python(state, pi_dir)
            ok("MCP sidecar Python {} ({})".format(python, state["python"].get("version", "?")))
            unresolved = (state.get("notices") or {}).get("unresolved") or []
            if unresolved:
                warnings.append(unresolved)
                warn("{} package(s) have no verified upstream license text: {}".format(len(unresolved), ", ".join(unresolved)))
        except (RuntimeError, OSError) as exc:
            fail(str(exc))
    if args.no_register:
        log("skip: registration (--no-register)")
    else:
        try:
            status = registration.registration_status(nuke_dir, target)
        except InstallError as exc:
            fail(str(exc))
        else:
            for name, value in sorted(status.items()):
                (ok if value in ("managed", "existing-line") else fail)(
                    "{}/{}: {}".format(nuke_dir, name, value))
    log("Check {}.".format("FAILED" if failures else "passed"))
    return 1 if failures else 0


def main(argv=None, source_root: Path | None = None) -> int:
    args = _parser().parse_args(argv)
    source_root = Path(source_root or Path(__file__).resolve().parents[2])
    try:
        return _check(args, source_root) if args.check else _install(args, source_root)
    except InstallError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    except (RuntimeError, OSError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted; the previous install (if any) is unchanged.", file=sys.stderr)
        return 1
