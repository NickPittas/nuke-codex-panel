"""Guided Nuke surface: the bounded ``nuke_action`` tool and the stateful ``nuke_workflow`` tool.

Import-safe for the MCP sidecar: this module (and the two it builds on) imports neither
``nuke`` nor Qt at import time. The sidecar reads the schema/description constants;
the bridge owns one :class:`GuidedNuke` and calls it on Nuke's main thread, one request
at a time.

Contract with the bridge (see ``GuidedNuke`` methods): a result always has ``success``,
``graph_changed`` (True/False/None = unknown) and ``touched_nodes``; failures add
``error`` and focused facts (candidates, choices, current values). Visual evidence is
confirmed only through :meth:`GuidedNuke.evidence_delivered`.
"""

from __future__ import annotations

from functools import lru_cache

from ..knowledge import library as knowledge
from .guided_actions import ActionError, NativeActions, NukeFacts
from .guided_workflow import FAMILIES, WorkflowEngine, WorkflowError

_ACTION_NAMES = sorted(NativeActions.ALLOWED)

ACTION_DESCRIPTION = (
    "Bounded native Nuke actions: one validated step per call, real classes, knobs, enum labels and "
    "input ports, state read back and reported. One action creates at most one node; configure that "
    "node in the same call. Use these instead of execute_python for ordinary work.\n"
    "create {class, name?, knobs?, inputs?{port: node}, place?, select?} - a native class; Roto/RotoPaint "
    "for every shape; the one existing Viewer is reused, never added. A failed configuration removes the "
    "new node again (verified).\n"
    "set {node, knobs{name: value}} - enum labels exactly as the knob lists them; arrays as lists; "
    "{\"expression\": ...} is free-form and needs user approval.\n"
    "inspect {node?, knobs?[], match?, non_default?} - live knob values, enum choices, ports. match=text "
    "finds knob names/labels; no node = scene header.\n"
    "connect {node, inputs{port: node|null}} - ports are input indexes (Merge: 0=B background, 1=A "
    "foreground; 'B'/'A' accepted). swap {node, a, b} swaps two inputs. select {nodes[]}. delete {node}.\n"
    "layout {placements[{node, below|above|left_of|right_of: node | x+y, gap?, dx?, dy?}]} top-to-bottom "
    "B trunk, A branches to the side.\n"
    "project {width,height,pixel_aspect?,fps?,first_frame?,last_frame?,format_name?} - existing content "
    "needs allow_overwrite=true and a reason; same values change nothing.\n"
    "sample {node, x, y, frame?, size?[dx,dy], channels?} pixel measurements (never a visual verdict).\n"
    "render {node?, frame | frames[<=3], target?} synchronous Viewer render of node (existing Viewer "
    "is connected to it) and the image is delivered to you; target=nodegraph gives the all-scope graph "
    "view. view {node, input?} connects "
    "the Viewer without rendering. render and view (Viewer) also take real Viewer framing: zoom "
    "(percent or 'fit') with optional center [x, y], or region [x0, y0, x1, y1], in source-image "
    "pixels, y up. Results are viewport renders, not crops (100% is 1:1 detail); framing persists on "
    "the Viewer and a region does not follow tracking across frames.\n"
    "animate {node, knob, keys{frame: value} | [{frame, value}], interpolation?} keyframes one knob of a "
    "node; interpolation belongs to animate only.\n"
    "Roto/RotoPaint: shape {node, kind: ellipse|rectangle|polygon, center, size | points, name?, closed?} "
    "(coordinates are format pixels, y up); shape_style {node, shape, color[r,g,b], opacity?, feather?} "
    "(set the node's output knob to rgba for a coloured shape); shape_key {node, shape, keys{frame: "
    "[x, y]}} animates the shape's translation (keys only: no interpolation, no knob).\n"
    "internal_python {node, code} runs Python with `node` bound (Roto/RotoPaint hosts also get rp, curves, "
    "root_layer). It is unrestricted, like execute_python: it may create, delete, rewire or edit any node; "
    "whatever it changed is reported, nothing is refused or undone. Syntax errors run nothing; runtime "
    "errors report what already changed.\n"
    "Result: success, observed state; on failure error plus the real candidates/choices and a recovery "
    "object (accepted_arguments for the action, field applicability, read-only next_calls). Recovery "
    "never changes or replays your request; partial/rolled_back/touched_nodes tell what changed. A "
    "validation error (unknown action, argument, knob, enum label, port) is fixed from that recovery "
    "and the live inspect, not from API documentation; search_nuke_api_docs answers a Python run's "
    "api_errors only. Use the live knob names and enum labels from the error or inspect, not guessed "
    "aliases."
)

ACTION_INPUT_SCHEMA = {
    "type": "object",
    "required": ["action"],
    "properties": {
        "action": {"type": "string", "enum": _ACTION_NAMES},
        "node": {"type": "string", "description": "Target node full name."},
        "nodes": {"type": "array", "items": {"type": "string"}},
        "class": {"type": "string", "description": "Native node class for create."},
        "name": {"type": "string"},
        "knobs": {"type": ["object", "array"], "description": "create/set: {knob: value}; inspect: [knob names]."},
        "inputs": {"type": "object", "description": "{port: source node name | null}."},
        "place": {"type": "object", "description": "{below|above|left_of|right_of: node} or {x, y}; gap/dx/dy."},
        "select": {"type": "boolean"},
        "knob": {"type": "string"},
        "keys": {"type": ["object", "array"], "description": "animate: {frame: value} or [{frame, value}] keyframes of `knob`; shape_key: {frame: [x, y]} translation keys of a Roto shape."},
        "interpolation": {"type": "string", "enum": ["smooth", "linear", "constant", "catmull_rom", "cubic"], "description": "animate ONLY. Not accepted by shape_key or any other action."},
        "match": {"type": "string"},
        "non_default": {"type": "boolean"},
        "a": {"type": ["integer", "string"]},
        "b": {"type": ["integer", "string"]},
        "placements": {"type": "array", "items": {"type": "object"}},
        "width": {"type": "integer"},
        "height": {"type": "integer"},
        "pixel_aspect": {"type": "number"},
        "format_name": {"type": "string"},
        "fps": {"type": "number"},
        "first_frame": {"type": "integer"},
        "last_frame": {"type": "integer"},
        "allow_overwrite": {"type": "boolean"},
        "reason": {"type": "string"},
        "x": {"type": "number"},
        "y": {"type": "number"},
        "frame": {"type": "integer"},
        "frames": {"type": "array", "items": {"type": "integer"}, "maxItems": 3},
        "size": {"type": "array", "items": {"type": "number"}, "description": "sample: [dx, dy]; shape: [width, height]."},
        "channels": {"type": "array", "items": {"type": "string"}},
        "target": {"type": "string", "enum": ["viewer", "nodegraph"]},
        "input": {"type": "integer"},
        "kind": {"type": "string", "enum": ["ellipse", "rectangle", "polygon"]},
        "center": {"type": "array", "items": {"type": "number"}, "description": "shape: [x, y] shape centre; render/view: [x, y] source pixel to centre in the Viewer."},
        "zoom": {"type": ["number", "string"], "description": "render/view Viewer zoom percent, or 'fit'."},
        "region": {"type": "array", "items": {"type": "number"}, "description": "render/view: [x0, y0, x1, y1] source pixels to frame in the Viewer; exclusive with zoom/center."},
        "points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
        "closed": {"type": "boolean"},
        "shape": {"type": "string"},
        "color": {"type": "array", "items": {"type": "number"}},
        "opacity": {"type": "number"},
        "feather": {"type": "number"},
        "code": {"type": "string"},
        "label": {"type": "string"},
    },
}

WORKFLOW_DESCRIPTION = (
    "Stateful guided workflow kept by the application for this client: explicit steps, bound target nodes, "
    "and evidence. Families: " + ", ".join(FAMILIES) + ". Workflows compose (begin nested=true inside a step); "
    "a family never inherits another's steps. Nothing advances until the step's requirements hold on the "
    "observed graph.\n"
    "begin {family, goal?, nested?, bind?{role: node}} -> current step, what it needs, focused guidance.\n"
    "current {guidance?} shows the step and unmet requirements. bind {role?, node} names a step's target.\n"
    "review {verdict: accept|reject, observed, frames[], animated?} judges rendered images you actually "
    "received (nuke_action render): `observed` must be your own words on what you see, `frames` the frames "
    "actually delivered. Delivery is not approval; measurements never approve; renders that predate a graph "
    "change are refused. Animation needs several delivered frames including the ending. A refusal lists the "
    "unmet requirements in `workflow` and a `recovery` contract; nothing is accepted automatically.\n"
    "advance {node?, role?, project?: keep, skip?, reason?, next?: layer|finish} moves on when the step is met "
    "(2d: next=layer makes the finished Merge the next background). finish ends a non-2d workflow with its "
    "result node; abandon {reason} leaves the nodes in place."
)

WORKFLOW_INPUT_SCHEMA = {
    "type": "object",
    "required": ["action"],
    "properties": {
        "action": {"type": "string", "enum": ["begin", "current", "bind", "review", "advance", "finish", "abandon"]},
        "family": {"type": "string", "enum": list(FAMILIES)},
        "goal": {"type": "string"},
        "nested": {"type": "boolean"},
        "bind": {"type": "object", "description": "begin: pre-bound {role: node}."},
        "role": {"type": "string"},
        "node": {"type": "string"},
        "verdict": {"type": "string", "enum": ["accept", "reject"]},
        "observed": {"type": "string", "description": "Your own description in words of what the delivered image(s) actually show; never copied from requirements or prior results."},
        "frames": {"type": "array", "items": {"type": "integer"}, "description": "review: frames actually delivered to you by nuke_action render."},
        "animated": {"type": "boolean"},
        "project": {"type": "string", "enum": ["keep"]},
        "skip": {"type": "boolean"},
        "reason": {"type": "string"},
        "next": {"type": "string", "enum": ["layer", "finish"]},
        "guidance": {"type": "boolean"},
    },
}

_EXCERPT_CHARS = 700
_GUIDANCE_CHARS = 2000


@lru_cache(maxsize=64)
def _excerpt(doc_id: str, section: str) -> dict:
    base = knowledge.default_knowledge()
    try:
        if doc_id.startswith("nodes/"):
            part = base.get_node_reference(doc_id, section)
        else:
            part = base.get_guidance(doc_id, section)
    except (knowledge.KnowledgeError, knowledge.CorpusError) as exc:
        return {"id": doc_id, "section": section, "unavailable": str(exc)[:160]}
    text = part["content"].split("## Sources")[0].strip()
    if len(text) > _EXCERPT_CHARS:
        cut = text[:_EXCERPT_CHARS]
        text = (cut.rsplit("\n", 1)[0] if "\n" in cut else cut).rstrip() + " ..."
    entry = {"id": doc_id, "section": section, "text": text}
    if doc_id.startswith("nodes/"):
        entry["static_17_1_reference"] = True
    return entry


def _guidance(references) -> list:
    """Bounded excerpts of the existing corpus for one workflow step."""
    out, used = [], 0
    for doc_id, section in references:
        entry = _excerpt(doc_id, section)
        used += len(entry.get("text", ""))
        if used > _GUIDANCE_CHARS:
            break
        out.append(entry)
    return out


def _brackets(value) -> bool:
    return isinstance(value, str) and "[" in value and "]" in value


def _free_form_knobs(label, knobs) -> list[str]:
    lines = []
    if not isinstance(knobs, dict):
        return lines
    for name, value in knobs.items():
        if isinstance(value, dict) and "expression" in value:
            lines.append("%s: expression %s" % (name, value.get("expression")))
        elif _brackets(value):
            lines.append("%s: TCL/expression text %s" % (name, value))
    return ["%s %s" % (label, line) for line in lines]


class GuidedNuke:
    """The bridge's one guided-surface object. All methods run on Nuke's main thread."""

    def __init__(self):
        self.facts = NukeFacts()
        self.engine = WorkflowEngine(self.facts, guidance=_guidance)

    # ---- approval ----

    def approval_text(self, arguments) -> str | None:
        """Text the user must approve before ``action`` runs; None for bounded native actions."""
        if not isinstance(arguments, dict):
            return None
        action = arguments.get("action")
        if action == "internal_python":
            return "# nuke_action internal_python on node %s\n%s" % (arguments.get("node"), arguments.get("code") or "")
        if action in ("create", "set"):
            target = arguments.get("node") or arguments.get("name") or arguments.get("class")
            lines = _free_form_knobs(str(target), arguments.get("knobs"))
            if lines:
                return "# nuke_action %s: free-form knob values\n%s" % (action, "\n".join(lines))
        return None

    # ---- actions ----

    def action(self, client_id, arguments, revision, capture_callback, missing_inspection=None) -> dict:
        arguments = dict(arguments or {})
        name = arguments.get("action")
        runner = NativeActions(self.facts)

        def record(capture):
            self.engine.record_capture(client_id, capture, capture.get("graph_revision", revision))

        try:
            if not isinstance(name, str):
                raise ActionError("action must be one of %s" % ", ".join(_ACTION_NAMES))
            result = runner.run(name, arguments, capture=capture_callback, on_capture=record)
            returned = True
        except ActionError as exc:
            result = {"success": False, "error": str(exc), **exc.facts}
            result.setdefault("graph_changed", True if runner.mutated else False)
            returned = False
            if name in NativeActions.ALLOWED:
                result["action"] = name
        except Exception as exc:  # native failure: report it, never swallow
            result = {
                "success": False,
                "error": "%s: %s" % (type(exc).__name__, exc),
                "graph_changed": None if runner.mutated else False,
                "action": name,
            }
            returned = False
        if result.get("success") is False or result.get("api_errors"):
            _merge_recovery(result, _action_recovery(name, arguments, result, runner, returned))
        result["touched_nodes"] = list(runner.touched)
        if result.get("graph_changed") is True and result.get("success") is False:
            result["partial"] = (
                "the action changed the graph before it failed; nothing is assumed rolled back - inspect the "
                "node(s) named in touched_nodes"
                if not result.get("rolled_back")
                else "the action's new node was removed again (verified)"
            )
        if isinstance(name, str):
            self.engine.note_action(client_id, name, arguments, result)
        status = self.engine.status(client_id, missing_inspection)
        if status is not None:
            result["workflow"] = status
        return result

    # ---- workflows ----

    def workflow(self, client_id, arguments, revision, missing_inspection=None) -> dict:
        try:
            result = self.engine.request(client_id, dict(arguments or {}), missing_inspection)
        except WorkflowError as exc:
            result = {"success": False, "error": str(exc)}
            status = self.engine.status(client_id, missing_inspection)
            _merge_recovery(result, _workflow_recovery(arguments or {}, status))
            if status is not None:
                result["workflow"] = status
        result["graph_changed"] = False
        result["touched_nodes"] = []
        return result

    # ---- evidence lifecycle ----

    def evidence_delivered(self, client_id, evidence, revision):
        return self.engine.evidence_delivered(client_id, dict(evidence or {}), revision)

    def invalidate(self, client_id, reason) -> None:
        self.engine.invalidate(client_id, str(reason))

    def forget_client(self, client_id) -> None:
        self.engine.forget(client_id)


# Per-field applicability that the flat input schema cannot express.
_FIELD_NOTES = {
    "interpolation": "animate only; shape_key takes keys{frame: [x, y]} and no interpolation",
    "keys": "animate: {frame: value} or [{frame, value}] for the named knob; shape_key: {frame: [x, y]} for the shape's translation",
    "knobs": "create/set: {knob: value}; inspect: [knob names]",
    "shape": "shape_style/shape_key: name of an existing shape in the Roto/RotoPaint node",
    "size": "sample: [dx, dy]; shape: [width, height]",
}

_WORKFLOW_FIELDS = {
    "begin": ["family", "goal", "nested", "bind"],
    "current": ["guidance"],
    "bind": ["role", "node"],
    "review": ["verdict", "observed", "frames", "animated"],
    "advance": ["node", "role", "project", "skip", "reason", "next"],
    "finish": ["node", "reason"],
    "abandon": ["reason"],
}


def _action_recovery(name, arguments, result, runner, returned=False) -> dict | None:
    """Focused, read-only recovery facts for a failed ``nuke_action`` call.

    Built only from ``NativeActions.ALLOWED`` and the call itself; it never rewrites or replays the
    request. Facts already supplied by the action (``result['recovery']``) win.
    """
    allowed = NativeActions.ALLOWED.get(name) if isinstance(name, str) else None
    if allowed is None:
        return {"reference_kind": "tool_contract", "accepted_actions": list(_ACTION_NAMES)}
    recovery = {"reference_kind": "tool_contract", "action": name, "accepted_arguments": sorted(allowed)}
    unsupported = sorted(set(arguments) - allowed - {"action"})
    if unsupported:
        recovery["unsupported_arguments"] = unsupported
        recovery["field_applicability"] = {
            key: _FIELD_NOTES[key] for key in sorted(set(_FIELD_NOTES) & (allowed | set(unsupported)))
        }
        recovery["note"] = "nothing was run; the unsupported fields were not applied and none was dropped for you"
    api_errors = result.get("api_errors")
    if api_errors:
        recovery["reference_kind"] = "python_api"
        recovery["note_api"] = (
            "the Python run reported api_errors: runtime_evidence on each record is read from the running Nuke; "
            "search_nuke_api_docs/read_nuke_api_doc are optional references, nothing is held back"
        )
    elif returned and name == "internal_python" and result.get("success") is False and not unsupported:
        recovery["reference_kind"] = "python"
    node = arguments.get("node")
    if not isinstance(node, str) or not node.strip():
        node = runner.touched[0] if runner.touched else None
    nested = result.get("recovery") if isinstance(result.get("recovery"), dict) else {}
    missing = result.get("missing_node") or nested.get("missing_node")
    # An inspection only helps when the node exists and the refusal did not already explain everything.
    if (
        node
        and not unsupported
        and node.strip() != missing
        and not result.get("rolled_back")
        and name != "delete"
        and not (name == "create" and result.get("graph_changed") is False)
    ):
        recovery["next_calls"] = [{"tool": "nuke_action", "arguments": {"action": "inspect", "node": node.strip()}}]
    elif unsupported:
        recovery["next_calls"] = []
    return recovery


def _merge_recovery(result, recovery) -> None:
    """Attach ``recovery``. The failed action's own identity fields always win; other facts the
    action already supplied (contextual ``next_calls``, notes) are preserved."""
    if not recovery:
        return
    existing = result.get("recovery")
    if not isinstance(existing, dict):
        result["recovery"] = recovery
        return
    for key in ("reference_kind", "action", "accepted_arguments"):
        if key in recovery:
            existing[key] = recovery[key]
    for key, value in recovery.items():
        existing.setdefault(key, value)


def _workflow_recovery(arguments, status) -> dict:
    action = arguments.get("action")
    recovery = {
        "reference_kind": "tool_contract",
        "tool": "nuke_workflow",
        "accepted_actions": sorted(_WORKFLOW_FIELDS),
    }
    if action in _WORKFLOW_FIELDS:
        recovery["accepted_arguments"] = {"action": action, "fields": _WORKFLOW_FIELDS[action]}
    if status is None:
        recovery["note"] = "no workflow is active for this client; begin {family} starts one (families: %s)" % ", ".join(FAMILIES)
    else:
        recovery["note"] = "workflow status above lists the unmet requirements; nothing was accepted or advanced"
    if action == "review":
        recovery["review_requires"] = (
            "verdict, observed (your own words about images actually delivered by nuke_action render) and "
            "frames that were delivered; measurements never approve"
        )
    return recovery
