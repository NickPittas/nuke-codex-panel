"""Unrestricted, persistent Python execution inside Nuke."""

from __future__ import annotations

import ast
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import time
import traceback


def _json_value(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return repr(value)


class PythonExecutor:
    """Execute arbitrary Nuke Python with a persistent namespace."""

    def __init__(self):
        import nuke

        self.namespace = {
            "__name__": "__nuke_codex__",
            "__builtins__": __builtins__,
            "nuke": nuke,
        }

    def execute(self, code: str, undo: bool = True, label: str = "Codex Python") -> dict:
        import nuke

        started = time.perf_counter()
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = None
        undo_started = False
        before = {node.fullName() for node in nuke.allNodes(recurseGroups=True)}
        try:
            if undo:
                nuke.Undo.begin(label)
                undo_started = True
            tree = ast.parse(code, filename="<codex-nuke>", mode="exec")
            with redirect_stdout(stdout), redirect_stderr(stderr):
                if tree.body and isinstance(tree.body[-1], ast.Expr):
                    prefix = ast.Module(body=tree.body[:-1], type_ignores=[])
                    if prefix.body:
                        exec(compile(prefix, "<codex-nuke>", "exec"), self.namespace)
                    expression = ast.Expression(tree.body[-1].value)
                    result = eval(compile(expression, "<codex-nuke>", "eval"), self.namespace)
                else:
                    exec(compile(tree, "<codex-nuke>", "exec"), self.namespace)
            after = {node.fullName() for node in nuke.allNodes(recurseGroups=True)}
            return {
                "success": True,
                "result": _json_value(result),
                "result_repr": repr(result),
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "traceback": None,
                "added_nodes": sorted(after - before),
                "removed_nodes": sorted(before - after),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        except BaseException as exc:
            return {
                "success": False,
                "result": None,
                "result_repr": None,
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "traceback": traceback.format_exc(),
                "error": "%s: %s" % (type(exc).__name__, exc),
                "added_nodes": [],
                "removed_nodes": [],
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        finally:
            if undo_started:
                nuke.Undo.end()
