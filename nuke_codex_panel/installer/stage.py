"""Target ownership checks, staged copy of the project, and atomic activation.

Two modes. *In place*: the target is the checkout/unpacked source that ``install.py`` lives in; no
project file is copied or removed, only the generated runtime directories are (atomically)
replaced. *Copy*: a complete new tree is built beside the target and swapped in with renames; the
previous tree is kept until the swap succeeded and restored if it fails. A directory is only
replaced if it is empty or carries this installer's ownership marker.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .. import __version__
from .common import InstallError, atomic_write, force_rmtree, is_within, rename

MARKER = ".nuke-codex-panel-install"
PACKAGE_DIR = "nuke_codex_panel"
RUNTIME_REL = Path("runtime") / "pi"
_REQUIRED_FILES = ("install.py", "LICENSE", Path("runtime") / "pi" / "manifest.json")
_OPTIONAL_FILES = (
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    Path("docs") / "INSTALLATION.md",
    Path("docs") / "USAGE.md",
)
_OPTIONAL_DIRS = ("licenses",)
# Generated or private entries of runtime/pi that are never copied from a source tree.
_RUNTIME_GENERATED = ("node", "node_modules", "third-party-notices", "install-state.json")


def _ignore_code(_directory, names):
    return [n for n in names if n == "__pycache__" or n.endswith((".pyc", ".pyo"))]


def _ignore_runtime(directory, names):
    if Path(directory).name == "pi" and Path(directory).parent.name == "runtime":
        return [n for n in names if n in _RUNTIME_GENERATED or n.startswith(".") or n == "__pycache__"]
    return _ignore_code(directory, names)


def validate_source(source_root: Path) -> None:
    for relative in _REQUIRED_FILES:
        if not (source_root / relative).is_file():
            raise InstallError("incomplete source tree: {} is missing".format(source_root / relative))
    if not (source_root / PACKAGE_DIR / "__init__.py").is_file():
        raise InstallError("incomplete source tree: {} is missing".format(source_root / PACKAGE_DIR))


def classify_target(target: Path, source_root: Path, nuke_dir: Path) -> str:
    """Return ``'in-place'``, ``'new'`` or ``'update'``; raise for any target we must not touch."""
    target = Path(os.path.abspath(str(target)))
    if target.exists() and os.path.samefile(str(target), str(source_root)):
        return "in-place"
    home = Path.home()
    for protected, what in ((nuke_dir, "the Nuke user directory"), (home, "the home directory")):
        if protected.exists() and (os.path.realpath(str(protected)) == os.path.realpath(str(target))
                                   or is_within(protected, target)):
            raise InstallError("refusing target {}: it is or contains {} ({})".format(target, what, protected))
    if target.parent == target:
        raise InstallError("refusing to install into a filesystem root")
    if is_within(source_root, target) or is_within(target, source_root):
        raise InstallError(
            "target {} and source {} are nested; choose a separate target directory".format(target, source_root)
        )
    if target.is_symlink():
        raise InstallError("refusing target {}: it is a symbolic link".format(target))
    if not target.exists():
        return "new"
    if not target.is_dir():
        raise InstallError("target {} exists and is not a directory".format(target))
    if (target / MARKER).is_file():
        return "update"
    if not any(target.iterdir()):
        return "update"
    raise InstallError(
        "target {} exists and is not an empty directory or a Nuke Codex Panel install made by install.py "
        "(no {} marker); refusing to overwrite it. Choose another --target.".format(target, MARKER)
    )



def build_stage(source_root: Path, stage: Path) -> None:
    """Copy the distributable project into the new directory ``stage`` (runtime assets, no heavy dirs)."""
    stage.mkdir(parents=True)
    shutil.copytree(str(source_root / PACKAGE_DIR), str(stage / PACKAGE_DIR), ignore=_ignore_code)
    shutil.copytree(
        str(source_root / RUNTIME_REL), str(stage / RUNTIME_REL), ignore=_ignore_runtime
    )
    for relative in _REQUIRED_FILES + _OPTIONAL_FILES:
        source = source_root / relative
        if source.is_file():
            (stage / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(stage / relative))
    for name in _OPTIONAL_DIRS:
        if (source_root / name).is_dir():
            shutil.copytree(str(source_root / name), str(stage / name), ignore=_ignore_code)
    marker = {"schema": 1, "project": "nuke-codex-panel", "version": __version__}
    atomic_write(stage / MARKER, (json.dumps(marker, indent=2) + "\n").encode("utf-8"))


def activate_copy(stage: Path, target: Path, mode: str, discarded: list) -> None:
    """Swap ``stage`` into ``target``. The old tree (if any) is restored if the swap fails.

    The replaced tree's path is appended to ``discarded`` for the caller to delete after everything
    else succeeded.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "new":
        rename(stage, target)
        return
    previous = target.parent / ".{}.previous-{}".format(target.name, os.getpid())
    if previous.exists():
        force_rmtree(previous)
    try:
        rename(target, previous)
    except OSError as exc:
        raise InstallError(
            "cannot replace {}: {}. Close Nuke and any program using the old install, then retry.".format(target, exc)
        ) from exc
    try:
        rename(stage, target)
    except BaseException:
        rename(previous, target)
        raise
    discarded.append(previous)


def activate_in_place(runtime_dir: Path, staged: Path, manifest: dict, discarded: list) -> None:
    """Replace the generated entries of ``runtime_dir`` with those prepared in ``staged``.

    Each existing entry is renamed aside first and put back if a later rename fails; the install
    receipt moves last so a runtime is never described by a receipt it does not match.
    """
    names = [manifest["node"]["install_dir"], "node_modules", manifest["notices"]["dir"], "install-state.json"]
    moved, aside = [], []
    try:
        for name in names:
            source, destination = staged / name, runtime_dir / name
            if not source.exists():
                continue
            if os.path.lexists(str(destination)):
                parked = runtime_dir / ".{}.previous-{}".format(name, os.getpid())
                if os.path.lexists(str(parked)):
                    force_rmtree(parked)
                rename(destination, parked)
                aside.append((parked, destination))
            rename(source, destination)
            moved.append(destination)
    except BaseException:
        for destination in reversed(moved):
            if destination.is_dir() and not destination.is_symlink():
                force_rmtree(destination)
            elif os.path.lexists(str(destination)):
                destination.unlink()
        for parked, destination in reversed(aside):
            if os.path.lexists(str(parked)):
                rename(parked, destination)
        raise
    discarded.extend(parked for parked, _ in aside)
