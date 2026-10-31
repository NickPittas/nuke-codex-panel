"""Small filesystem/process helpers shared by the installer modules."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path


class InstallError(Exception):
    """A fail-closed installer error; its message is shown to the user as-is."""


def log(message: str) -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print("warning: " + message, file=sys.stderr, flush=True)


def tail(text: str, lines: int = 30) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def sibling_temp(path: Path, tag: str) -> Path:
    """A not-yet-existing hidden sibling of ``path`` on the same filesystem."""
    return path.parent / ".{}.{}-{}".format(path.name, tag, uuid.uuid4().hex[:8])


def is_within(child: Path, parent: Path) -> bool:
    """True if ``child`` equals or lies below ``parent`` (after symlink resolution)."""
    child, parent = Path(os.path.realpath(child)), Path(os.path.realpath(parent))
    return child == parent or parent in child.parents


def _retry(action, what: str, attempts: int = 8):
    """Retry ``action`` on transient failures (antivirus/indexer handles on Windows)."""
    for attempt in range(attempts):
        try:
            return action()
        except OSError:
            if attempt == attempts - 1 or os.name != "nt":
                raise
            time.sleep(0.25 * (attempt + 1))
    raise InstallError("{} failed".format(what))


def rename(src: Path, dst: Path) -> None:
    _retry(lambda: os.rename(str(src), str(dst)), "rename")


def _unlink(path: Path) -> None:
    try:
        _retry(lambda: os.unlink(str(path)), "unlink")
    except PermissionError:
        os.chmod(str(path), stat.S_IWRITE | stat.S_IREAD)
        _retry(lambda: os.unlink(str(path)), "unlink")


def is_link_like(path) -> bool:
    """True for a symlink or a Windows reparse point (junction, mount point, ...)."""
    try:
        info = os.lstat(str(path))
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    return bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _remove_link(path: Path) -> None:
    """Remove a link or junction itself; never chmod it (that would follow it)."""
    try:
        if os.name == "nt" and path.is_dir():
            _retry(lambda: os.rmdir(str(path)), "rmdir")
        else:
            _retry(lambda: os.unlink(str(path)), "unlink")
    except OSError as exc:
        raise InstallError("cannot remove link {} (its destination was left untouched): {}".format(path, exc)) from exc


def force_rmtree(path: Path) -> None:
    """Remove a file, link or directory tree; symlinks and junctions are removed, never followed."""
    path = Path(path)
    if is_link_like(path):
        _remove_link(path)
        return
    if path.is_file():
        _unlink(path)
        return
    if not path.is_dir():
        return
    for entry in os.scandir(str(path)):
        child = Path(entry.path)
        if is_link_like(child):
            _remove_link(child)
        elif entry.is_dir(follow_symlinks=False):
            force_rmtree(child)
        else:
            _unlink(child)
    try:
        _retry(lambda: os.rmdir(str(path)), "rmdir")
    except PermissionError:
        os.chmod(str(path), stat.S_IRWXU)
        _retry(lambda: os.rmdir(str(path)), "rmdir")


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    """Write ``data`` to ``path`` via a same-directory temp file and ``os.replace``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = sibling_temp(path, "tmp")
    try:
        with open(str(tmp), "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(str(tmp), mode)
        _retry(lambda: os.replace(str(tmp), str(path)), "replace")
    except BaseException:
        if tmp.exists():
            _unlink(tmp)
        raise


def link_or_copy_tree(src: Path, dst: Path) -> None:
    """Mirror ``src`` into the new directory ``dst`` using hard links (copy fallback).

    ``src`` is left untouched. Symlinks are recreated as symlinks, never followed.
    """
    src, dst = Path(src), Path(dst)
    dst.mkdir(parents=True)
    shutil.copymode(str(src), str(dst))
    for entry in os.scandir(str(src)):
        source, target = Path(entry.path), dst / entry.name
        if entry.is_symlink():
            os.symlink(os.readlink(str(source)), str(target))
        elif entry.is_dir(follow_symlinks=False):
            link_or_copy_tree(source, target)
        else:
            try:
                os.link(str(source), str(target))
            except OSError:
                shutil.copy2(str(source), str(target))


def run(argv, *, cwd: Path, env: dict, timeout: float) -> "subprocess.CompletedProcess[str]":
    """Run a child without a shell and with an explicit environment; output is captured."""
    try:
        return subprocess.run(
            [str(a) for a in argv],
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise InstallError("{} timed out after {:.0f}s".format(Path(str(argv[0])).name, timeout)) from exc
    except OSError as exc:
        raise InstallError("cannot run {}: {}".format(argv[0], exc)) from exc
