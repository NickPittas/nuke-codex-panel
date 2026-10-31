"""Idempotent Nuke startup registration (``init.py`` + ``menu.py``) via managed blocks.

Only text between the plugin's own markers is ever rewritten; everything else is preserved byte for
byte. A registration the user already wrote by hand (an uncommented ``nuke.pluginAddPath`` of the
target, or ``import nuke_codex_panel.menu``) counts as registered and nothing is added. Each file
that changes is first backed up once beside itself, and the pair is applied all-or-nothing.
"""

from __future__ import annotations

import ast
import json
import os
import re
import time
from pathlib import Path

from .common import InstallError, atomic_write

BEGIN = "# >>> Nuke Codex Panel >>>"
END = "# <<< Nuke Codex Panel <<<"
_ADD_PATH = re.compile(r"""^\s*(?:nuke\s*\.\s*)?pluginAddPath\s*\(\s*[rRuU]?(['"])(.+?)\1\s*\)""")
_IMPORT_MENU = re.compile(r"^\s*(?:import\s+nuke_codex_panel\.menu\b|from\s+nuke_codex_panel\s+import\s+menu\b)")
_MENU_BODY = "import nuke_codex_panel.menu"


def _init_body(target: Path) -> str:
    return "import nuke\nnuke.pluginAddPath({})".format(json.dumps(target.as_posix()))


def _managed_block(body: str, newline: str) -> str:
    return newline.join([BEGIN] + body.split("\n") + [END]) + newline


def _split_block(text: str):
    """``(before, block, after)`` around the managed block (block includes its line ending), or None."""
    start = text.find(BEGIN)
    if start < 0:
        return None
    end = text.find(END, start)
    if end < 0:
        raise InstallError("a Nuke Codex Panel block in a startup file has no closing marker; fix it by hand")
    end += len(END)
    if text.startswith("\r\n", end):
        end += 2
    elif text.startswith("\n", end):
        end += 1
    return text[:start], text[start:end], text[end:]


def _visible_lines(text: str):
    """Uncommented lines outside the managed block."""
    block = _split_block(text)
    if block is not None:
        text = block[0] + block[2]
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


def _same_dir(path: str, base: Path, target: Path) -> bool:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = base / candidate
    try:
        return os.path.samefile(str(candidate), str(target))
    except OSError:
        return False


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InstallError("{} is not valid UTF-8; refusing to edit it".format(path)) from exc


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _unconditional(body):
    """Statements that run on every load: top level, plus ``if True`` and ``try`` bodies."""
    for node in body:
        yield node
        if isinstance(node, ast.If) and isinstance(node.test, ast.Constant) and node.test.value:
            yield from _unconditional(node.body)
        elif isinstance(node, ast.Try):
            yield from _unconditional(node.body)


def _tree(text: str):
    block = _split_block(text)
    if block is not None:
        text = block[0] + block[2]
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError) as exc:
        raise InstallError("a Nuke startup file (init.py/menu.py) is not valid Python ({}); fix it by hand".format(exc)) from exc


def _manual_init(text: str, nuke_dir: Path, target: Path) -> bool:
    tree = _tree(text)
    for node in _unconditional(tree.body):
        call = node.value if isinstance(node, ast.Expr) else None
        if not isinstance(call, ast.Call) or len(call.args) != 1 or call.keywords:
            continue
        func = call.func
        named = (isinstance(func, ast.Name) and func.id == "pluginAddPath") or (
            isinstance(func, ast.Attribute) and func.attr == "pluginAddPath"
            and isinstance(func.value, ast.Name) and func.value.id == "nuke"
        )
        arg = call.args[0]
        if named and isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _same_dir(arg.value, nuke_dir, target):
            return True
    return False


def _manual_menu(text: str) -> bool:
    tree = _tree(text)
    for node in _unconditional(tree.body):
        if isinstance(node, ast.Import) and any(alias.name == "nuke_codex_panel.menu" for alias in node.names):
            return True
        if (
            isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "nuke_codex_panel"
            and any(alias.name == "menu" for alias in node.names)
        ):
            return True
    return False


def _block_is_current(text: str, body: str) -> bool:
    block = _split_block(text)
    return block is not None and block[1].replace("\r\n", "\n") == _managed_block(body, "\n")


def registration_status(nuke_dir: Path, target: Path) -> dict:
    """Read-only: per startup file ``managed``, ``managed-stale``, ``existing-line`` or ``absent``."""
    status = {}
    for name, body in (("init.py", _init_body(target)), ("menu.py", _MENU_BODY)):
        text = _read(nuke_dir / name)
        if _split_block(text) is not None:
            status[name] = "managed" if _block_is_current(text, body) else "managed-stale"
        elif _manual_init(text, nuke_dir, target) if name == "init.py" else _manual_menu(text):
            status[name] = "existing-line"
        else:
            status[name] = "absent"
    return status


def _new_text(text: str, body: str, manual: bool):
    """The new content for a startup file, or None when it needs no change."""
    newline = _newline(text)
    block = _split_block(text)
    managed = _managed_block(body, newline)
    if block is not None:
        return None if _block_is_current(text, body) else block[0] + managed + block[2]
    if manual:
        return None
    if not text:
        return managed
    return text + (newline if text.endswith("\n") else newline * 2) + managed


def _backup(path: Path) -> Path:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    for n in range(100):
        candidate = path.with_name("{}.nuke-codex-panel.bak-{}{}".format(path.name, stamp, "" if n == 0 else "-" + str(n)))
        if not candidate.exists():
            atomic_write(candidate, path.read_bytes(), mode=path.stat().st_mode & 0o777)
            return candidate
    raise InstallError("cannot choose a backup name for {}".format(path))


def register(nuke_dir: Path, target: Path) -> list:
    """Register ``target`` in ``nuke_dir``; return human-readable result lines."""
    init_path, menu_path = nuke_dir / "init.py", nuke_dir / "menu.py"
    init_text, menu_text = _read(init_path), _read(menu_path)
    jobs = [
        (init_path, init_text, _new_text(init_text, _init_body(target), _manual_init(init_text, nuke_dir, target))),
        (menu_path, menu_text, _new_text(menu_text, _MENU_BODY, _manual_menu(menu_text))),
    ]
    nuke_dir.mkdir(parents=True, exist_ok=True)
    lines, applied = [], []
    try:
        for path, original, new_text in jobs:
            if new_text is None:
                lines.append("{}: already registered".format(path.name))
                continue
            existed = path.exists()
            mode = path.stat().st_mode & 0o777 if existed else None
            backup = _backup(path) if existed else None
            applied.append((path, original, existed, mode))
            atomic_write(path, new_text.encode("utf-8"), mode=mode)
            lines.append("{}: registered{}".format(path.name, " (backup {})".format(backup.name) if backup else " (created)"))
    except BaseException:
        for path, original, existed, mode in reversed(applied):
            if existed:
                atomic_write(path, original.encode("utf-8"), mode=mode)
            elif path.exists():
                path.unlink()
        raise
    return lines
