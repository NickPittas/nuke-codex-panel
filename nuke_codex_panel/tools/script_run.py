"""Compile-before-run and structured failure reports, shared by execute_python and internal_python.

``compile_script`` turns the whole script into code objects BEFORE anything runs, so a syntax or
compile error (including ``yield``/``await`` outside a function, which only the compiler rejects)
can never leave a half-executed script behind. ``failure_report`` describes what stopped a script
that did run: the exception, the exact source location (also inside functions defined by earlier
calls, through the ``SourceRegistry``) and an honest statement of which effects are known (the
graph delta the caller reports) and which are not (everything else a script can touch).

Nothing here re-runs or replays user code, and a failure while describing a failure never
replaces the original exception: the report degrades to what could be read.
"""

from __future__ import annotations

import ast
import os
import traceback

from .api_errors import _clip, _message, _position_at, _segment_at, _split_lines

FILENAME = "<codex-nuke>"

_MAX_FRAMES = 8
_MAX_SOURCE = 300
_MAX_FILE = 80

_UNKNOWN_EFFECTS = (
    "Python namespace bindings made before the failure",
    "files written or read",
    "renders started or completed",
    "callbacks registered or triggered",
    "partial effects of the call that raised",
)


class PreflightError(Exception):
    """The script was rejected before any of it ran. ``phase`` is ``syntax`` or ``compile``."""

    def __init__(self, phase, error):
        super().__init__(phase)
        self.phase = phase
        self.error = error


def compile_script(code, sources, split_last_expression):
    """Compile ``code`` completely; return ``[(mode, code object), ...]`` to run in order.

    With ``split_last_expression`` a trailing expression statement becomes its own ``eval`` unit
    (its value is the script's result) but is compiled together with everything before it.
    Raises ``PreflightError``; the registered sources are untouched in that case.
    """
    try:
        tree = ast.parse(code, filename=FILENAME, mode="exec")
    except Exception as exc:  # SyntaxError, or ValueError/RecursionError/MemoryError on odd input
        raise PreflightError("syntax", exc) from None
    try:
        if split_last_expression and tree.body and isinstance(tree.body[-1], ast.Expr):
            units = []
            prefix = ast.Module(body=tree.body[:-1], type_ignores=[])
            if prefix.body:
                units.append(("exec", prefix))
            units.append(("eval", ast.Expression(tree.body[-1].value)))
        else:
            units = [("exec", tree)]
        compiled = [(mode, compile(node, FILENAME, mode)) for mode, node in units]
    except Exception as exc:
        raise PreflightError("compile", exc) from None
    for _mode, unit in compiled:
        sources.add(unit, code)
    return compiled


def run_compiled(units, namespace):
    """Run the units of ``compile_script`` in order; the value of an ``eval`` unit is returned."""
    result = None
    for mode, unit in units:
        if mode == "eval":
            result = eval(unit, namespace)
        else:
            exec(unit, namespace)
    return result


def not_run_graph_fields() -> dict:
    """Graph delta of a script that was rejected before running: it provably changed nothing."""
    return {
        "graph_changed": False,
        "graph_change_detection": "not executed: the code was rejected before anything ran",
        "added_nodes": [],
        "removed_nodes": [],
        "modified_nodes": [],
        "node_errors": [],
    }


def _line_text(lines, number):
    if isinstance(number, int) and 1 <= number <= len(lines):
        return _clip(" ".join(lines[number - 1].split()), _MAX_SOURCE)
    return None


def rejected_report(rejected: PreflightError, code: str) -> dict:
    """Failure entries (``error``, ``traceback``, ``failure``) for a script that never ran."""
    exc = rejected.error
    location = {}
    try:
        line = getattr(exc, "lineno", None)
        if isinstance(line, int):
            location["line"] = line
        offset = getattr(exc, "offset", None)
        if isinstance(offset, int):
            location["column"] = offset
        text = _line_text(_split_lines(code), line)
        if text:
            location["source"] = text
        message = getattr(exc, "msg", None)
        message = _clip(message, 400) if isinstance(message, str) else _message(exc)
    except Exception:
        message = _message(exc)
    try:
        formatted = "".join(traceback.format_exception_only(type(exc), exc))
    except Exception:
        formatted = "%s: %s" % (type(exc).__name__, message)
    return {
        "error": "%s: %s" % (type(exc).__name__, exc),
        "traceback": formatted,
        "failure": {
            "phase": rejected.phase,
            "executed": False,
            "exception_type": type(exc).__name__,
            "message": message,
            "location": location,
            "frames": [],
            "effects": {
                "graph": "unchanged: the code was only compiled, none of it ran",
                "unknown": [],
            },
        },
    }


def _frame_entry(tb, namespace, sources):
    code = tb.tb_frame.f_code
    source = sources.get(code)
    user = source is not None or tb.tb_frame.f_globals is namespace
    entry = {"function": code.co_name, "line": tb.tb_lineno, "user_code": user}
    if not user:
        entry["file"] = _clip(os.path.basename(code.co_filename or "?"), _MAX_FILE)
        return entry
    text = None
    if source is not None:
        position = _position_at(code, tb.tb_lasti)
        if position is not None:
            lines = _split_lines(source)
            first = lines[position[0] - 1].encode("utf-8") if 1 <= position[0] <= len(lines) else None
            if first is not None:
                entry["column"] = len(first[: position[2]].decode("utf-8", "replace")) + 1
        segment = _segment_at(code, tb.tb_lasti, source)
        text = " ".join(segment.split()) if segment else _line_text(_split_lines(source), tb.tb_lineno)
    if text:
        entry["source"] = _clip(text, _MAX_SOURCE)
    return entry


def failure_report(exc, namespace, sources, executed=True, undo_note=None) -> dict:
    """The ``failure`` entry for an exception that ended a script that had started to run."""
    effects = {
        "graph": (
            "see graph_changed / added_nodes / removed_nodes / modified_nodes (fingerprint comparison of the graph; "
            "nothing was undone, retried or replayed)"
        ),
        "unknown": list(_UNKNOWN_EFFECTS),
    }
    if undo_note:
        effects["undo"] = undo_note
    failure = {
        "phase": "runtime" if executed else "setup",
        "executed": bool(executed),
        "exception_type": type(exc).__name__,
        "message": _message(exc),
        "location": {},
        "frames": [],
        "effects": effects,
    }
    try:
        entries = []
        tb = exc.__traceback__
        while tb is not None:
            entries.append(tb)
            tb = tb.tb_next
        # The executor's own frames above the first line of user code are not the user's.
        for index, item in enumerate(entries):
            if sources.get(item.tb_frame.f_code) is not None or item.tb_frame.f_globals is namespace:
                entries = entries[index:]
                break
        else:
            entries = []
        frames = [_frame_entry(item, namespace, sources) for item in entries]
        user = [frame for frame in frames if frame["user_code"]]
        if user:
            last = user[-1]
            failure["location"] = {key: last[key] for key in ("function", "line", "column", "source") if key in last}
        if len(frames) > _MAX_FRAMES:
            failure["frames_omitted"] = len(frames) - _MAX_FRAMES
            frames = frames[-_MAX_FRAMES:]
        failure["frames"] = frames
    except Exception as describing:
        failure["limitations"] = [
            "the location could not be read: %s" % _clip(type(describing).__name__, 60)
        ]
    return failure
