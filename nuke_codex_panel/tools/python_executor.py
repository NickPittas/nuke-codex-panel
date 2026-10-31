"""Unrestricted, persistent Python execution inside Nuke."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import time
import traceback

from .api_errors import ApiErrorTracker, SourceRegistry
from .script_run import (
    compile_script,
    failure_report,
    not_run_graph_fields,
    PreflightError,
    rejected_report,
    run_compiled,
)

_MAX_LISTED = 50
_VOLATILE_KNOBS = frozenset({"selected", "indicators"})
# Root/Viewer `frame` is inspection state; on any other node (e.g. Read) it affects the image.
_INSPECTION_FRAME_CLASSES = frozenset({"Root", "Viewer"})
# Distinguishes "take your own baseline" from a caller's failed (None) baseline.
_UNSET = object()


def _semantic_gsv(knob):
    """Sorted-JSON of a Gsv_Knob's sets/values plus declared types and list options.

    Returns None (caller falls back to toScript) if any native query fails or the
    value is not the expected dict-of-dicts.
    """
    try:
        if knob.Class() != "Gsv_Knob":
            return None

        value = knob.value()
        if not isinstance(value, dict):
            return None
        sets = {}
        for set_name, variables in value.items():
            if not isinstance(variables, dict):
                return None
            entries = {}
            for var_name, var_value in variables.items():
                path = "%s.%s" % (set_name, var_name)
                data_type = knob.getDataType(path)
                options = list(knob.getListOptions(path))
                entries[var_name] = {"value": var_value, "type": str(data_type), "options": options}
            sets[set_name] = entries
        return json.dumps(sets, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except Exception:
        return None


def _stable_script(node, *, exclude_knobs=frozenset()) -> str:
    # Node.writeKnobs() returns '' for every node under `nuke -t` (probed in Nuke 17.1),
    # so fingerprint each knob's own script form, which includes animation curves.
    # Gsv_Knob uses its semantic dict value: toScript embeds panel presentation state.
    parts = []
    knobs = node.knobs()
    for name in sorted(knobs):
        if name in exclude_knobs:
            continue
        if name in _VOLATILE_KNOBS or (name == "frame" and node.Class() in _INSPECTION_FRAME_CLASSES):
            continue
        try:
            value = _semantic_gsv(knobs[name])
            if value is None:
                value = knobs[name].toScript()
            else:
                value = "gsv:" + value
        except Exception as exc:
            value = "<unreadable %s>" % type(exc).__name__
        parts.append("%s=%s" % (name, value))
    return "\n".join(parts)


def graph_snapshot():
    """Fingerprint of the root graph: name -> digest of class, wiring, knobs, animation.

    Returns None if it cannot be taken; callers must treat that as unknown.
    Digests stay in this process; only changed node names are reported.
    """
    import nuke

    try:
        fingerprints = {}
        for node in nuke.allNodes(group=nuke.root(), recurseGroups=True):
            inputs = []
            for index in range(node.inputs()):
                source = node.input(index)
                inputs.append(source.fullName() if source is not None else "")
            payload = "%s|%s|%s" % (node.Class(), inputs, _stable_script(node))
            fingerprints[node.fullName()] = hashlib.sha1(payload.encode("utf-8", "replace")).hexdigest()
        root = nuke.root()
        fingerprints["<root>"] = hashlib.sha1(_stable_script(root).encode("utf-8", "replace")).hexdigest()
        return fingerprints
    except Exception:
        return None


def _node_errors(names):
    """Nodes reporting an error state; a failed query is itself reported, never skipped."""
    import nuke

    errors = []
    root = nuke.root()
    root.begin()
    try:
        for name in names:
            node = nuke.toNode(name)
            if node is None:
                continue
            try:
                if node.hasError():
                    errors.append({"node": name, "error": "node reports an error state"})
            except Exception as exc:
                errors.append({"node": name, "error": "error query failed: %s: %s" % (type(exc).__name__, exc)})
    finally:
        root.end()
    return errors[:_MAX_LISTED]


def diff_snapshots(before, after) -> dict:
    """Mutation metadata. graph_changed is True/False, or None when unknown."""
    if before is None or after is None:
        return {
            "graph_changed": None,
            "graph_change_detection": "unknown: graph snapshot failed; inspect the graph",
            "added_nodes": [],
            "removed_nodes": [],
            "modified_nodes": [],
            "node_errors": [],
        }
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(name for name in set(before) & set(after) if before[name] != after[name])
    return {
        "graph_changed": bool(added or removed or modified),
        "graph_change_detection": "fingerprint",
        "added_nodes": added,
        "removed_nodes": removed,
        "modified_nodes": modified[:_MAX_LISTED],
        "node_errors": _node_errors([name for name in added + modified if name != "<root>"]),
    }


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
        # Source text of every executed code object, so a failing instruction can be located
        # even in functions defined by an earlier call.
        self._api_sources = SourceRegistry()

    def execute(
        self, code: str, undo: bool = True, label: str = "Codex Python", before=_UNSET
    ) -> dict:
        """Run ``code``. ``before`` is a graph_snapshot() the caller took just before
        (None = it failed, so change detection reports unknown); omitted, one is taken here.

        The whole script is compiled first: invalid code runs nothing, not even the statements
        before the invalid one, and opens no undo group."""
        import nuke

        started = time.perf_counter()

        def elapsed():
            return round((time.perf_counter() - started) * 1000, 3)

        try:
            units = compile_script(code, self._api_sources, split_last_expression=True)
        except PreflightError as rejected:
            return {
                "success": False,
                "result": None,
                "result_repr": None,
                "stdout": "",
                "stderr": "",
                **rejected_report(rejected, code),
                "api_errors": [],
                **not_run_graph_fields(),
                "elapsed_ms": elapsed(),
            }
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = None
        undo_started = False
        running = False
        tracker = ApiErrorTracker(self.namespace, self._api_sources)
        if before is _UNSET:
            before = graph_snapshot()

        def metadata():
            try:
                return diff_snapshots(before, graph_snapshot())
            except Exception:
                return diff_snapshots(None, None)

        try:
            if undo:
                nuke.Undo.begin(label)
                undo_started = True
            running = True
            with redirect_stdout(stdout), redirect_stderr(stderr), tracker:
                result = run_compiled(units, self.namespace)
            meta = metadata()
            response = {
                "success": not meta["node_errors"],
                "result": _json_value(result),
                "result_repr": repr(result),
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "traceback": None,
                **tracker.response_fields(),
                **meta,
                "elapsed_ms": elapsed(),
            }
            if meta["node_errors"]:
                response["error"] = "Code ran, but nodes report errors: " + ", ".join(
                    entry["node"] for entry in meta["node_errors"]
                )
            return response
        except BaseException as exc:
            # Partial changes made before the exception are real: report them.
            return {
                "success": False,
                "result": None,
                "result_repr": None,
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "traceback": traceback.format_exc(),
                "error": "%s: %s" % (type(exc).__name__, exc),
                "failure": failure_report(
                    exc,
                    self.namespace,
                    self._api_sources,
                    executed=running,
                    undo_note=(
                        "the changes made before the failure are recorded as one undo group %r; it was not undone" % label
                        if undo_started and running
                        else None
                    ),
                ),
                **tracker.response_fields(exc),
                **metadata(),
                "elapsed_ms": elapsed(),
            }
        finally:
            if undo_started:
                nuke.Undo.end()
