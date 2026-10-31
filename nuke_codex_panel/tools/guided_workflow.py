"""Per-client guided workflow state for the nuke_workflow tool.

Pure Python: it never imports ``nuke``. Everything it needs to know about the live
graph comes through an injected facts object (see :class:`GraphFacts`), so the
state machine can be tested against any graph and the sidecar can import the module.

A workflow is an explicit, app-owned sequence of steps for one family of work
(``2d``, ``keying``, ``cleanup``, ``projection``). A step ends only when its
requirements hold against the *observed* graph and the evidence the model actually
received. Nothing here is a generic compositing rule: the 2D layer cycle (project,
background, Merge Over with the background on B, foreground, attach on A, layout,
composite review, repeat with the previous Merge as the next background) belongs to
the ``2d`` family only. Keying, cleanup and projection start from their own plate,
key or 3D structure and do not inherit it. Workflows compose: a family can be begun
nested inside another and its result node is handed back to the parent.

Visual evidence has three separate facts that must all hold before a review counts:
the image was captured by a synchronous Viewer render (metadata: frame, source node,
size, project format), the sidecar confirmed it handed that image to the model, and
the graph is still exactly as captured. Delivery never implies approval: approval is
an explicit ``review`` verdict carrying the model's own description of what it saw.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import re
from typing import Callable, Protocol

FAMILIES = ("2d", "keying", "cleanup", "projection")

MAX_CLIENTS = 64
MAX_EVIDENCE = 24
MAX_HISTORY = 12
MAX_STACK = 4
MAX_ROLE = 32

# Observations must describe the picture in words; metrics alone never approve it.
_MIN_OBSERVATION_CHARS = 30
_MIN_OBSERVATION_WORDS = 6
_WORD = re.compile(r"[A-Za-z]{3,}")

_ROLE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

GEOMETRY_PREFIXES = ("Card", "Cube", "Cylinder", "Sphere", "ReadGeo", "PoissonMesh", "ModelBuilder")


class GraphFacts(Protocol):
    """What the workflow engine may ask the live graph (all read-only)."""

    def node(self, name: str) -> dict | None:
        """``{name, class, inputs:[name|None], x, y, label, operation}`` or None."""

    def upstream(self, name: str) -> list[str]:
        """Names of every node feeding ``name`` (itself included)."""

    def animation(self, names: list[str]) -> dict:
        """``{animated, first_key, last_key, unreadable:[name]}`` over these nodes."""

    def project(self) -> dict:
        """``{format_name, width, height, fps, first_frame, last_frame}``."""

    def digest(self) -> str | None:
        """Digest of the whole graph state; None when it cannot be certified."""


class WorkflowError(ValueError):
    """A refused workflow request; the message is safe to show to the model."""


# ---------------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------------


@dataclass
class Evidence:
    """One captured Viewer render, tracked from capture to delivery to verdict."""

    evidence_id: str
    target: str
    frame: int | None
    node: str | None  # what the Viewer's active input showed
    viewer: str | None
    width: int
    height: int
    format_width: int | None
    format_height: int | None
    source: str
    freshness: str
    inputs_known: bool
    digest: str | None
    revision: int
    delivered: bool = False
    invalid: str | None = None
    judged: bool = False

    def certification_problem(self) -> str | None:
        """Why this image cannot certify a Viewer render of a node at a frame, or None."""
        if self.target != "viewer":
            return "a %s capture is graph evidence, not a rendered image" % self.target
        if self.source != "viewer_render" or self.freshness != "verified_by_synchronous_render":
            return "it is not a synchronous Viewer render"
        if self.frame is None:
            return "frame metadata is missing"
        if not self.inputs_known or not self.node:
            return "the Viewer input that was displayed is unknown"
        if self.width <= 0 or self.height <= 0:
            return "image size metadata is missing"
        if not self.format_width or not self.format_height:
            return "project format metadata is missing"
        return None


def evidence_from_capture(capture: dict, digest: str | None, revision: int) -> Evidence:
    """Build tracked evidence from a bridge capture dict (success=True)."""
    frame = capture.get("frame")
    return Evidence(
        evidence_id=str(capture.get("evidence_id") or ""),
        target=str(capture.get("target") or ""),
        frame=int(frame) if isinstance(frame, (int, float)) and not isinstance(frame, bool) else None,
        node=capture.get("viewer_input_node") or None,
        viewer=capture.get("viewer") or None,
        width=int(capture.get("image_width") or 0),
        height=int(capture.get("image_height") or 0),
        format_width=capture.get("project_format_width") or None,
        format_height=capture.get("project_format_height") or None,
        source=str(capture.get("source") or ""),
        freshness=str(capture.get("freshness") or ""),
        inputs_known=bool(capture.get("viewer_inputs_known")),
        digest=digest,
        revision=int(revision),
    )


def validate_observation(text) -> str:
    """The model's own description of the image; numeric-only text is not a visual decision."""
    if not isinstance(text, str) or not text.strip():
        raise WorkflowError(
            "review needs `observed`: describe in words what the rendered image(s) show "
            "(content, position, colour, edges, motion). Numbers alone are not a visual decision."
        )
    text = text.strip()
    compact = "".join(text.split())
    letters = sum(1 for char in compact if char.isalpha())
    words = _WORD.findall(text)
    if (
        len(text) < _MIN_OBSERVATION_CHARS
        or len(words) < _MIN_OBSERVATION_WORDS
        or letters * 2 < len(compact)
    ):
        raise WorkflowError(
            "`observed` is not a visual description (needs at least %d words of prose that "
            "describe what the image shows; measurements or pixel values alone never approve "
            "an image)." % _MIN_OBSERVATION_WORDS
        )
    return text


# ---------------------------------------------------------------------------------
# Step definitions
# ---------------------------------------------------------------------------------


def _step(step_id, title, do, *, bind=None, needs=(), review=None, motion=False, skippable=False, guidance=()):
    return {
        "id": step_id,
        "title": title,
        "do": do,
        "bind": bind,
        "needs": tuple(needs),
        "review": review,
        # motion: this review always needs several frames for sequences/animation.
        "motion": motion,
        "skippable": skippable,
        "guidance": tuple(guidance),
    }


def _graph_guidance():
    return (("fundamentals/graph-conventions", "verify"),)


_2D_PROJECT = _step(
    "project",
    "Project settings",
    "Check the project format/fps/range against the request. Change them only if they are not "
    "what the task needs (nuke_action project), otherwise advance with project=\"keep\".",
    needs=("project",),
    guidance=(("fundamentals/quality-safeguards", "workflow"),),
)
_2D_BACKGROUND = _step(
    "background",
    "Background",
    "Build the background with native nodes, view it, and review it. Bind its output node.",
    bind="background",
    review="background",
    needs=("review",),
    guidance=(("nodes/checkerboard", "controls"), ("nodes/constant", "controls")),
)
_2D_MERGE = _step(
    "merge",
    "Merge Over on the background",
    "Create a Merge (operation over) whose B input (index 0) is the background. Leave A (index 1) "
    "empty for now. Bind the Merge, then do a graph check.",
    bind="merge",
    needs=("merge_over", "graph"),
    guidance=(("nodes/merge", "inputs"),) + _graph_guidance(),
)
_2D_FOREGROUND = _step(
    "foreground",
    "Foreground element",
    "Build one foreground element (shapes start in Roto or RotoPaint), keep it unattached, view it "
    "and review it, then do a graph check. Bind its output node.",
    bind="foreground",
    review="foreground",
    needs=("foreground_free", "review", "graph"),
    guidance=(("fundamentals/node-selection", "workflow"), ("nodes/roto", "controls")),
)
_2D_ATTACH = _step(
    "attach",
    "Attach on A",
    "Connect the foreground to the Merge's A input (index 1). The background stays on B.",
    needs=("attach",),
    guidance=(("nodes/merge", "pitfalls"),),
)
_2D_LAYOUT = _step(
    "layout",
    "Graph layout",
    "Lay the graph out top to bottom: B trunk vertical, the foreground branch entering A from the "
    "side with room for its own tree. Then do a graph check.",
    needs=("layout", "graph"),
    guidance=_graph_guidance(),
)
_2D_COMPOSITE = _step(
    "composite",
    "Composite review",
    "View the Merge and review the composite. Animated work needs several frames including the "
    "ending. Then do a graph check.",
    review="merge",
    motion=True,
    needs=("review", "graph"),
    guidance=(("fundamentals/quality-safeguards", "verify"),),
)
_2D_NEXT = _step(
    "next",
    "Next layer or finish",
    "Another element: advance with next=\"layer\" (this Merge becomes the next background). "
    "Done: advance with next=\"finish\".",
    needs=("decision",),
)

TWO_D_FIRST_LAYER = (_2D_PROJECT, _2D_BACKGROUND, _2D_MERGE, _2D_FOREGROUND, _2D_ATTACH, _2D_LAYOUT, _2D_COMPOSITE, _2D_NEXT)
TWO_D_NEXT_LAYER = (_2D_MERGE, _2D_FOREGROUND, _2D_ATTACH, _2D_LAYOUT, _2D_COMPOSITE, _2D_NEXT)

KEYING = (
    _step(
        "plate",
        "Source plate",
        "Reuse the plate Read (one Read, branch from it), view it and review it. Bind the plate node.",
        bind="plate",
        review="plate",
        needs=("review",),
        guidance=(("nodes/read", "controls"),),
    ),
    _step(
        "cleanup",
        "RGB cleanup",
        "Shot-dependent cleanup comes before keying (degrain, rig/marker fixes; shapes start in Roto "
        "or RotoPaint). Bind the cleaned RGB node, or advance with skip=true and a reason.",
        bind="clean",
        review="clean",
        skippable=True,
        needs=("review",),
        guidance=(("fundamentals/keying-conventions", "workflow"),),
    ),
    _step(
        "key",
        "Alpha-only key",
        "Build the key(s) as alpha only, separate from the RGB branch; assemble regional mattes with "
        "ChannelMerge. View the matte alpha and review it. Bind the final matte node.",
        bind="matte",
        review="matte",
        needs=("review",),
        guidance=(("topics/chroma-keying", "workflow"), ("nodes/channelmerge", "inputs")),
    ),
    _step(
        "copy_alpha",
        "Copy alpha onto retained RGB",
        "Copy the final matte alpha onto the original or cleaned RGB: Copy with B = RGB, A = matte. "
        "Bind the Copy node.",
        bind="keyed",
        needs=("copy_alpha",),
        guidance=(("nodes/copy", "inputs"), ("fundamentals/alpha-premultiplication", "workflow")),
    ),
    _step(
        "edge",
        "Despill and edge treatment",
        "Despill/edge treatment after the matte transfer, respecting premultiplication. Bind the "
        "treated node, or advance with skip=true and a reason.",
        bind="treated",
        skippable=True,
        needs=("treated",),
        guidance=(("fundamentals/alpha-premultiplication", "pitfalls"),),
    ),
    _step(
        "review",
        "Keyed result review",
        "View the keyed result (over a contrasting check, not on the plate) and review it across "
        "several frames for motion.",
        review="final",
        motion=True,
        needs=("review", "graph"),
        guidance=(("fundamentals/keying-conventions", "verify"),),
    ),
)

CLEANUP = (
    _step(
        "plate",
        "Source plate",
        "View the plate and review it, identifying what must be removed. Bind the plate node.",
        bind="plate",
        review="plate",
        needs=("review",),
        guidance=(("topics/rig-removal", "workflow"),),
    ),
    _step(
        "fix",
        "Cleanup branch",
        "Build the fix as a branch of the plate (manual shapes and paint start in Roto or RotoPaint; "
        "split large paint work). Bind the cleaned output node.",
        bind="fixed",
        needs=("fixed",),
        guidance=(("topics/rotoscoping-masking", "workflow"), ("nodes/rotopaint", "controls")),
    ),
    _step(
        "review",
        "Cleanup review",
        "View the cleaned result and review it across several frames, including the fix region.",
        review="fixed",
        motion=True,
        needs=("review", "graph"),
        guidance=(("fundamentals/quality-safeguards", "verify"),),
    ),
)

PROJECTION = (
    _step(
        "plate",
        "Source plate",
        "View the plate/texture source and review it. Bind the plate node.",
        bind="plate",
        review="plate",
        needs=("review",),
        guidance=(("topics/camera-projection", "workflow"),),
    ),
    _step(
        "camera",
        "Projection camera",
        "Create or select the camera for the projection (own 3D branch). Bind the camera node.",
        bind="camera",
        needs=("camera",),
        guidance=(("nodes/camera", "inputs"),),
    ),
    _step(
        "geometry",
        "Receiving geometry",
        "Create the geometry that receives the projection (own 3D branch). Bind the geometry node.",
        bind="geometry",
        needs=("geometry",),
        guidance=(("topics/geometric-primitives", "workflow"),),
    ),
    _step(
        "projection",
        "Project3D",
        "Create Project3D with the plate and the camera and apply it to the geometry. Bind the "
        "projection node.",
        bind="projection",
        needs=("projection",),
        guidance=(("nodes/project3d", "inputs"),),
    ),
    _step(
        "render",
        "Scanline render",
        "Render the 3D branch to 2D with ScanlineRender (geometry on obj, camera on cam). Bind the "
        "render node.",
        bind="render",
        needs=("render3d",),
        guidance=(("nodes/scanlinerender", "inputs"),),
    ),
    _step(
        "review",
        "Projection review",
        "View the render and review it across several frames (parallax, stretching, edges).",
        review="render",
        motion=True,
        needs=("review",),
        guidance=(("topics/texture-projection", "verify"),),
    ),
    _step(
        "handoff",
        "2D hand-off",
        "Return the controlled 2D result with one labelled Dot after the render. Bind the Dot, then "
        "do a graph check.",
        bind="handoff",
        needs=("handoff", "graph"),
        guidance=_graph_guidance(),
    ),
)

_FAMILY_STEPS = {"2d": TWO_D_FIRST_LAYER, "keying": KEYING, "cleanup": CLEANUP, "projection": PROJECTION}


# ---------------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------------


@dataclass
class Workflow:
    workflow_id: int
    family: str
    goal: str
    steps: tuple
    index: int = 0
    layer: int = 1
    targets: dict = field(default_factory=dict)
    skipped: dict = field(default_factory=dict)
    project_ack: bool = False
    declared_animated: bool | None = None
    # step id -> {"digest", "node", "frames", "evidence_ids", "observed"}
    reviews: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    result: str | None = None

    @property
    def step(self) -> dict:
        return self.steps[self.index]

    def log(self, text: str) -> None:
        self.history.append(text)
        del self.history[:-MAX_HISTORY]


@dataclass
class ClientState:
    stack: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    next_id: int = 1
    animated_nodes: set = field(default_factory=set)
    project_changed: bool = False


class _Context:
    """What a requirement check can see."""

    def __init__(self, workflow, facts, missing_inspection, state, lenient=False):
        self.workflow = workflow
        self.facts = facts
        self.missing_inspection = missing_inspection
        self.state = state
        # Brief status inside action results has no inspection report: do not claim one is owed.
        self.lenient = lenient

    def role_node(self, role):
        """``(fact, problem)`` for a bound role."""
        name = self.workflow.targets.get(role)
        if not name:
            return None, "bind the %s node first (nuke_workflow bind role=%s node=<name>)" % (role, role)
        fact = self.facts.node(name)
        if fact is None:
            return None, "the %s node %r no longer exists" % (role, name)
        return fact, None


def _check_project(context):
    if context.workflow.project_ack:
        return None
    return "project not confirmed: nuke_action project (changes) or advance with project=\"keep\""


def _check_graph(context):
    missing = context.missing_inspection
    if missing is None:
        return None if context.lenient else "graph check unavailable: the bridge did not report inspection status"
    if missing:
        return "graph check owed: " + "; ".join(missing)
    return None


def _inputs(fact):
    return list(fact.get("inputs") or [])


def _input(fact, index):
    values = _inputs(fact)
    return values[index] if index < len(values) else None


def _check_merge_over(context):
    workflow = context.workflow
    merge, problem = context.role_node("merge")
    if problem:
        return problem
    background, problem = context.role_node("background")
    if problem:
        return problem
    if merge["class"] != "Merge2":
        return "merge node %s is class %s; a Merge2 (Merge) node is required" % (merge["name"], merge["class"])
    if merge.get("operation") != "over":
        return "merge %s operation is %r; set it to 'over'" % (merge["name"], merge.get("operation"))
    if _input(merge, 0) != background["name"]:
        return "merge B input (index 0) is %r; it must be the %s %s" % (
            _input(merge, 0),
            "background" if workflow.layer == 1 else "previous Merge",
            background["name"],
        )
    if _input(merge, 1):
        return "merge A input (index 1) is already %s; leave A empty until the foreground is reviewed" % _input(merge, 1)
    return None


def _check_foreground_free(context):
    foreground, problem = context.role_node("foreground")
    if problem:
        return problem
    merge, problem = context.role_node("merge")
    if problem:
        return problem
    if foreground["name"] in (merge["name"], context.workflow.targets.get("background")):
        return "the foreground must be its own node, not the Merge or the background"
    if _input(merge, 1) == foreground["name"]:
        return "the foreground is already attached to A; review it before attaching (disconnect A, then review)"
    return None


def _check_attach(context):
    merge, problem = context.role_node("merge")
    if problem:
        return problem
    foreground, problem = context.role_node("foreground")
    if problem:
        return problem
    background = context.workflow.targets.get("background")
    if _input(merge, 1) != foreground["name"]:
        return "merge A input (index 1) is %r; connect the foreground %s there" % (_input(merge, 1), foreground["name"])
    if _input(merge, 0) != background:
        return "merge B input (index 0) is %r; it must stay on %s" % (_input(merge, 0), background)
    return None


_LAYOUT_COLUMN_TOLERANCE = 20
_LAYOUT_SIDE_MIN = 70


def _check_layout(context):
    merge, problem = context.role_node("merge")
    if problem:
        return problem
    background, problem = context.role_node("background")
    if problem:
        return problem
    foreground, problem = context.role_node("foreground")
    if problem:
        return problem
    issues = []
    if abs(merge["x"] - background["x"]) > _LAYOUT_COLUMN_TOLERANCE:
        issues.append("Merge %s is not in the B column of %s (x %s vs %s)" % (merge["name"], background["name"], merge["x"], background["x"]))
    if merge["y"] <= background["y"]:
        issues.append("Merge %s must sit below its B input %s" % (merge["name"], background["name"]))
    if abs(foreground["x"] - merge["x"]) < _LAYOUT_SIDE_MIN:
        issues.append("foreground %s must enter A from the left or right side, not stack on the B trunk" % foreground["name"])
    if foreground["y"] >= merge["y"]:
        issues.append("foreground %s must sit above the Merge %s" % (foreground["name"], merge["name"]))
    return "; ".join(issues) or None


def _check_decision(context):
    return "decision pending: advance with next=\"layer\" or next=\"finish\""


def _upstream_has(context, fact, role):
    name = context.workflow.targets.get(role)
    if not name:
        return "role %s is not bound" % role
    if name not in context.facts.upstream(fact["name"]):
        return "%s is not upstream of %s" % (name, fact["name"])
    return None


def _check_copy_alpha(context):
    keyed, problem = context.role_node("keyed")
    if problem:
        return problem
    if keyed["class"] not in ("Copy", "ShuffleCopy"):
        return "keyed node %s is class %s; Copy (or ShuffleCopy) is required to move the alpha onto RGB" % (keyed["name"], keyed["class"])
    if not _input(keyed, 0) or not _input(keyed, 1):
        return "Copy needs B (index 0) = retained RGB and A (index 1) = matte"
    rgb_role = "clean" if context.workflow.targets.get("clean") else "plate"
    problem = _upstream_has_via(context, _input(keyed, 0), rgb_role)
    if problem:
        return "Copy B (index 0): " + problem
    problem = _upstream_has_via(context, _input(keyed, 1), "matte")
    if problem:
        return "Copy A (index 1): " + problem
    return None


def _upstream_has_via(context, source_name, role):
    expected = context.workflow.targets.get(role)
    if not expected:
        return "role %s is not bound" % role
    if expected not in context.facts.upstream(source_name):
        return "does not come from the %s node %s" % (role, expected)
    return None


def _check_treated(context):
    if context.workflow.skipped.get("edge"):
        return None
    treated, problem = context.role_node("treated")
    if problem:
        return problem
    return _upstream_has(context, treated, "keyed")


def _check_fixed(context):
    fixed, problem = context.role_node("fixed")
    if problem:
        return problem
    plate = context.workflow.targets.get("plate")
    if fixed["name"] == plate:
        return "the cleaned output must be a new node after the plate, not the plate itself"
    return _upstream_has(context, fixed, "plate")


def _check_camera(context):
    camera, problem = context.role_node("camera")
    if problem:
        return problem
    if not camera["class"].startswith("Camera"):
        return "camera node %s is class %s; a Camera node is required" % (camera["name"], camera["class"])
    return None


def _check_geometry(context):
    geometry, problem = context.role_node("geometry")
    if problem:
        return problem
    if not geometry["class"].startswith(GEOMETRY_PREFIXES):
        return "geometry node %s is class %s; expected 3D geometry (Card, Cube, Sphere, ReadGeo, ...)" % (
            geometry["name"],
            geometry["class"],
        )
    return None


def _check_projection(context):
    projection, problem = context.role_node("projection")
    if problem:
        return problem
    if not projection["class"].startswith("Project3D"):
        return "projection node %s is class %s; Project3D is required" % (projection["name"], projection["class"])
    for role in ("plate", "camera"):
        problem = _upstream_has(context, projection, role)
        if problem:
            return problem
    return None


def _check_render3d(context):
    render, problem = context.role_node("render")
    if problem:
        return problem
    if not render["class"].startswith("ScanlineRender"):
        return "render node %s is class %s; ScanlineRender is required" % (render["name"], render["class"])
    for role in ("geometry", "camera"):
        problem = _upstream_has(context, render, role)
        if problem:
            return problem
    return None


def _check_handoff(context):
    handoff, problem = context.role_node("handoff")
    if problem:
        return problem
    if handoff["class"] != "Dot":
        return "hand-off node %s is class %s; a labelled Dot is required" % (handoff["name"], handoff["class"])
    if not str(handoff.get("label") or "").strip():
        return "label the hand-off Dot by purpose (its label knob is empty)"
    render = context.workflow.targets.get("render")
    if _input(handoff, 0) != render:
        return "the Dot must take its input from the render %s" % render
    return None


_CHECKS: dict[str, Callable[[_Context], str | None]] = {
    "project": _check_project,
    "graph": _check_graph,
    "merge_over": _check_merge_over,
    "foreground_free": _check_foreground_free,
    "attach": _check_attach,
    "layout": _check_layout,
    "decision": _check_decision,
    "copy_alpha": _check_copy_alpha,
    "treated": _check_treated,
    "fixed": _check_fixed,
    "camera": _check_camera,
    "geometry": _check_geometry,
    "projection": _check_projection,
    "render3d": _check_render3d,
    "handoff": _check_handoff,
}


# ---------------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------------


class WorkflowEngine:
    """All clients' workflow state, evidence and verdicts."""

    def __init__(self, facts: GraphFacts, guidance: Callable[[tuple], list] | None = None):
        self.facts = facts
        self.guidance = guidance
        self._clients: OrderedDict[str, ClientState] = OrderedDict()

    # ---- client state ----

    def _state(self, client_id: str) -> ClientState:
        state = self._clients.get(client_id)
        if state is None:
            state = self._clients[client_id] = ClientState()
            while len(self._clients) > MAX_CLIENTS:
                self._clients.popitem(last=False)
        self._clients.move_to_end(client_id)
        return state

    def forget(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    def active(self, client_id: str) -> Workflow | None:
        state = self._clients.get(client_id)
        return state.stack[-1] if state and state.stack else None

    def invalidate(self, client_id: str | None, reason: str) -> None:
        """The graph changed outside our own accounting: captured pixels can no longer be trusted."""
        targets = list(self._clients.values()) if client_id is None else [self._clients[client_id]] if client_id in self._clients else []
        for state in targets:
            for item in state.evidence:
                if not item.invalid:
                    item.invalid = reason

    # ---- evidence ----

    def record_capture(self, client_id: str, capture: dict, revision: int) -> Evidence | None:
        """A Viewer render was captured for this client (not yet delivered)."""
        if not capture.get("evidence_id"):
            return None
        evidence = evidence_from_capture(capture, self.facts.digest(), revision)
        state = self._state(client_id)
        state.evidence.append(evidence)
        del state.evidence[:-MAX_EVIDENCE]
        return evidence

    def evidence_delivered(self, client_id: str, evidence: dict, revision: int) -> dict | None:
        """The sidecar handed this image to the model. Delivery is not approval."""
        state = self._clients.get(client_id)
        evidence_id = str(evidence.get("evidence_id") or "")
        if state is not None:
            for item in state.evidence:
                if item.evidence_id == evidence_id:
                    item.delivered = True
                    return {"evidence_id": evidence_id, "delivered": True}
        if evidence.get("target") != "viewer" or not evidence_id:
            return None
        # A Viewer capture made outside nuke_action: it counts only for the graph it saw.
        if evidence.get("graph_revision") != revision:
            return {"evidence_id": evidence_id, "delivered": False, "stale": True}
        item = evidence_from_capture(evidence, self.facts.digest(), revision)
        item.delivered = True
        state = self._state(client_id)
        state.evidence.append(item)
        del state.evidence[:-MAX_EVIDENCE]
        return {"evidence_id": evidence_id, "delivered": True}

    def note_action(self, client_id: str, action: str, arguments: dict, result: dict) -> None:
        """A successful guided action: remember facts the graph alone cannot show."""
        if not result.get("success"):
            return
        state = self._state(client_id)
        if action == "project":
            state.project_changed = True
            workflow = self.active(client_id)
            if workflow is not None:
                workflow.project_ack = True
        if action in ("animate", "shape_key") and arguments.get("node"):
            state.animated_nodes.add(str(arguments["node"]))

    # ---- public requests ----

    def request(self, client_id: str, arguments: dict, missing_inspection) -> dict:
        action = str(arguments.get("action") or "")
        handlers = {
            "begin": self._begin,
            "current": self._current,
            "bind": self._bind,
            "review": self._review,
            "advance": self._advance,
            "finish": self._finish_request,
            "abandon": self._abandon,
        }
        handler = handlers.get(action)
        if handler is None:
            raise WorkflowError("unknown workflow action %r; one of %s" % (action, ", ".join(handlers)))
        return handler(client_id, arguments, missing_inspection)

    # ---- handlers ----

    def _begin(self, client_id, arguments, missing_inspection):
        family = arguments.get("family")
        if family not in FAMILIES:
            raise WorkflowError("family must be one of %s, got %r" % (", ".join(FAMILIES), family))
        state = self._state(client_id)
        nested = bool(arguments.get("nested"))
        if state.stack and not nested:
            current = state.stack[-1]
            raise WorkflowError(
                "workflow #%d (%s, step %s) is still active. Finish it (advance through its steps, or "
                "action=abandon with a reason), or begin this one with nested=true to run it inside the "
                "current step." % (current.workflow_id, current.family, current.step["id"])
            )
        if len(state.stack) >= MAX_STACK:
            raise WorkflowError("workflows are nested %d deep already; finish one first" % MAX_STACK)
        goal = str(arguments.get("goal") or "").strip()[:200]
        workflow = Workflow(state.next_id, family, goal, _FAMILY_STEPS[family])
        state.next_id += 1
        if state.stack:
            workflow.project_ack = state.stack[-1].project_ack
        # Pre-bound roles (e.g. a finished keying result handed to a 2d foreground).
        for role, name in (arguments.get("bind") or {}).items():
            self._bind_role(workflow, role, name)
        if family != "2d":
            workflow.project_ack = True  # project settings only gate 2d layer work
        state.stack.append(workflow)
        workflow.log("begin %s" % family)
        return self._snapshot(client_id, workflow, missing_inspection, guidance=True)

    def _current(self, client_id, arguments, missing_inspection):
        workflow = self._require(client_id)
        return self._snapshot(client_id, workflow, missing_inspection, guidance=bool(arguments.get("guidance", True)))

    def _bind(self, client_id, arguments, missing_inspection):
        workflow = self._require(client_id)
        role = arguments.get("role") or workflow.step.get("bind")
        self._bind_role(workflow, role, arguments.get("node"))
        return self._snapshot(client_id, workflow, missing_inspection)

    def _bind_role(self, workflow, role, name):
        if not isinstance(role, str) or not _ROLE.match(role):
            raise WorkflowError("role must be a short lowercase identifier (e.g. background), got %r" % (role,))
        if not isinstance(name, str) or not name:
            raise WorkflowError("bind needs node=<node name>")
        fact = self.facts.node(name)
        if fact is None:
            raise WorkflowError("no node named %r exists; create it first" % name)
        workflow.targets[role] = fact["name"]

    def _require(self, client_id) -> Workflow:
        workflow = self.active(client_id)
        if workflow is None:
            raise WorkflowError(
                "no active workflow; begin one: nuke_workflow action=begin family=%s" % "|".join(FAMILIES)
            )
        return workflow

    def _resolve_role(self, workflow, role):
        if role == "final":
            return "treated" if workflow.targets.get("treated") and not workflow.skipped.get("edge") else "keyed"
        return role

    # ---- review ----

    def _review_target(self, workflow, arguments):
        step = workflow.step
        role = step.get("review")
        if role is None:
            raise WorkflowError("step %s has no visual review" % step["id"])
        role = self._resolve_role(workflow, role)
        if step["id"] == "cleanup" and workflow.skipped.get("cleanup"):
            raise WorkflowError("cleanup was skipped; there is nothing to review")
        name = workflow.targets.get(role)
        if not name:
            raise WorkflowError("bind the %s node first (nuke_workflow bind role=%s node=<name>)" % (role, role))
        fact = self.facts.node(name)
        if fact is None:
            raise WorkflowError("the %s node %r no longer exists" % (role, name))
        return role, fact

    def _frames_needed(self, workflow, state, fact):
        """(count, ending_frame_or_None, reason) of distinct frames this review must cover."""
        names = self.facts.upstream(fact["name"])
        animation = self.facts.animation(names)
        project = self.facts.project()
        detected = bool(animation.get("animated")) or any(name in state.animated_nodes for name in names)
        unreadable = animation.get("unreadable") or []
        declared = workflow.declared_animated
        if detected:
            animated = True  # a statement of "not animated" never overrides keys that exist
        elif declared is not None:
            animated = declared
        elif unreadable:
            raise WorkflowError(
                "animation on %s could not be read from the graph; state it: review with animated=true "
                "or animated=false" % ", ".join(unreadable[:4])
            )
        else:
            animated = False
        first, last = project.get("first_frame"), project.get("last_frame")
        sequence = bool(first is not None and last is not None and last > first)
        if animated:
            last_key = animation.get("last_key")
            ending = None
            if last_key is not None and last is not None:
                ending = int(min(last_key, last))
            elif last is not None:
                ending = int(last)
            return 2, ending, "animated"
        if workflow.step.get("motion") and workflow.family != "2d" and sequence:
            return 2, None, "a sequence"
        return 1, None, "a still"

    def _review(self, client_id, arguments, missing_inspection):
        workflow = self._require(client_id)
        state = self._state(client_id)
        step = workflow.step
        role, fact = self._review_target(workflow, arguments)
        verdict = arguments.get("verdict")
        if verdict not in ("accept", "reject"):
            raise WorkflowError("verdict must be 'accept' or 'reject'")
        observed = validate_observation(arguments.get("observed"))
        frames = arguments.get("frames")
        if (
            not isinstance(frames, list)
            or not frames
            or not all(isinstance(frame, int) and not isinstance(frame, bool) for frame in frames)
        ):
            raise WorkflowError("review needs `frames`: the integer frames of the delivered renders you looked at")
        declared = arguments.get("animated")
        if declared is not None and not isinstance(declared, bool):
            raise WorkflowError("animated must be true or false")
        if declared is not None:
            workflow.declared_animated = declared
        digest = self.facts.digest()
        if digest is None:
            raise WorkflowError("the graph state cannot be certified right now; evidence cannot be judged")
        chosen = []
        for frame in sorted(set(frames)):
            match = self._find_evidence(state, fact["name"], frame, digest)
            chosen.append(match)
        needed, ending, why = self._frames_needed(workflow, state, fact)
        distinct = sorted({item.frame for item in chosen})
        if len(distinct) < needed:
            raise WorkflowError(
                "this review covers %s work and needs at least %d distinct delivered frames of %s; "
                "you gave %d. Render more frames (nuke_action render node=%s frames=[...])."
                % (why, needed, fact["name"], len(distinct), fact["name"])
            )
        if ending is not None and needed > 1 and max(distinct) < ending:
            raise WorkflowError(
                "the review must include the ending: render and look at frame %d (or later) of %s"
                % (ending, fact["name"])
            )
        for item in chosen:
            item.judged = True
        if verdict == "reject":
            workflow.reviews.pop(step["id"], None)
            workflow.log("%s review rejected" % step["id"])
            snapshot = self._snapshot(client_id, workflow, missing_inspection)
            snapshot["verdict"] = "rejected: fix the problem you described, then render and review again"
            return snapshot
        workflow.reviews[step["id"]] = {
            "digest": digest,
            "node": fact["name"],
            "frames": distinct,
            "evidence_ids": [item.evidence_id for item in chosen],
            "observed": observed[:300],
        }
        workflow.log("%s review accepted (%s frames %s)" % (step["id"], fact["name"], distinct))
        return self._snapshot(client_id, workflow, missing_inspection)

    def _find_evidence(self, state, node, frame, digest):
        candidates = [
            item for item in state.evidence if item.node == node and item.frame == frame
        ]
        if not candidates:
            raise WorkflowError(
                "no render of %s at frame %d exists. Render it first: nuke_action render node=%s frame=%d"
                % (node, frame, node, frame)
            )
        for item in reversed(candidates):
            problem = item.certification_problem()
            if problem:
                last_problem = problem
                continue
            if not item.delivered:
                raise WorkflowError(
                    "the render of %s at frame %d was captured but not yet delivered to you; "
                    "an undelivered image cannot be judged" % (node, frame)
                )
            if item.invalid:
                raise WorkflowError(
                    "the render of %s at frame %d is stale (%s). Render it again." % (node, frame, item.invalid)
                )
            if item.digest is None or item.digest != digest:
                raise WorkflowError(
                    "the render of %s at frame %d predates a graph change. Render it again." % (node, frame)
                )
            if item.judged:
                raise WorkflowError(
                    "the render of %s at frame %d was already judged; capture a fresh render" % (node, frame)
                )
            return item
        raise WorkflowError(
            "the render of %s at frame %d cannot be used: %s" % (node, frame, last_problem)
        )

    # ---- advance ----

    def _unmet(self, workflow, state, missing_inspection, lenient=False):
        step = workflow.step
        context = _Context(workflow, self.facts, missing_inspection, state, lenient)
        unmet = []
        bind = step.get("bind")
        skipped = workflow.skipped.get(step["id"])
        if bind and not skipped and not workflow.targets.get(bind):
            unmet.append("bind the %s node (nuke_workflow bind role=%s node=<name>)" % (bind, bind))
            return unmet
        if skipped:
            return unmet
        for name in step["needs"]:
            if name == "review":
                problem = self._review_problem(workflow, step)
            else:
                problem = _CHECKS[name](context)
            if problem:
                unmet.append(problem)
        return unmet

    def _review_problem(self, workflow, step):
        record = workflow.reviews.get(step["id"])
        role = self._resolve_role(workflow, step["review"])
        node = workflow.targets.get(role)
        if record is None:
            return "visual review of %s owed: nuke_action render node=%s, then nuke_workflow review" % (node or role, node or "<node>")
        if record["node"] != node:
            return "the accepted review was of %s, not the bound %s %s; review it again" % (record["node"], role, node)
        if self.facts.digest() != record["digest"]:
            return "the graph changed after the accepted review of %s; render and review again" % node
        return None

    def _advance(self, client_id, arguments, missing_inspection):
        workflow = self._require(client_id)
        state = self._state(client_id)
        step = workflow.step
        # Optional bind in the same call.
        if arguments.get("node"):
            role = arguments.get("role") or step.get("bind")
            self._bind_role(workflow, role, arguments["node"])
        if arguments.get("project") is not None:
            if arguments["project"] != "keep":
                raise WorkflowError("project may only be \"keep\" here; use nuke_action project to change settings")
            if step["id"] == "project":
                workflow.project_ack = True
        if arguments.get("skip"):
            reason = str(arguments.get("reason") or "").strip()
            if not step["skippable"]:
                raise WorkflowError("step %s cannot be skipped" % step["id"])
            if len(reason) < 10:
                raise WorkflowError("skipping %s needs a reason (why this shot does not need it)" % step["id"])
            workflow.skipped[step["id"]] = reason[:200]
        if step["id"] == "next" and workflow.family == "2d":
            return self._decide(client_id, workflow, state, arguments, missing_inspection)
        unmet = self._unmet(workflow, state, missing_inspection)
        if unmet:
            snapshot = self._snapshot(client_id, workflow, missing_inspection)
            snapshot["success"] = False
            snapshot["error"] = "step %s is not complete" % step["id"]
            snapshot["unmet"] = unmet
            return snapshot
        workflow.log("%s done" % step["id"])
        if workflow.index + 1 >= len(workflow.steps):
            return self._complete(client_id, workflow, state, missing_inspection)
        workflow.index += 1
        return self._snapshot(client_id, workflow, missing_inspection, guidance=True)

    def _decide(self, client_id, workflow, state, arguments, missing_inspection):
        choice = arguments.get("next")
        if choice not in ("layer", "finish"):
            raise WorkflowError("advance from `next` needs next=\"layer\" or next=\"finish\"")
        merge = workflow.targets.get("merge")
        if not merge or self.facts.node(merge) is None:
            raise WorkflowError("the layer's Merge no longer exists")
        if choice == "finish":
            return self._complete(client_id, workflow, state, missing_inspection)
        workflow.log("layer %d done" % workflow.layer)
        workflow.layer += 1
        workflow.targets = {"background": merge}
        workflow.reviews.clear()
        workflow.skipped.clear()
        workflow.steps = TWO_D_NEXT_LAYER
        workflow.index = 0
        return self._snapshot(client_id, workflow, missing_inspection, guidance=True)

    def _finish_request(self, client_id, arguments, missing_inspection):
        workflow = self._require(client_id)
        state = self._state(client_id)
        if workflow.family == "2d":
            raise WorkflowError("a 2d workflow ends at its `next` step: advance with next=\"finish\"")
        if workflow.index + 1 < len(workflow.steps):
            raise WorkflowError("finish after the last step (%s); now at %s" % (workflow.steps[-1]["id"], workflow.step["id"]))
        unmet = self._unmet(workflow, state, missing_inspection)
        if unmet:
            snapshot = self._snapshot(client_id, workflow, missing_inspection)
            snapshot.update(success=False, error="step %s is not complete" % workflow.step["id"], unmet=unmet)
            return snapshot
        return self._complete(client_id, workflow, state, missing_inspection)

    def _result_node(self, workflow):
        for role in {
            "2d": ("merge",),
            "keying": ("treated", "keyed"),
            "cleanup": ("fixed",),
            "projection": ("handoff", "render"),
        }[workflow.family]:
            if workflow.targets.get(role) and not (role == "treated" and workflow.skipped.get("edge")):
                return workflow.targets[role]
        return None

    def _complete(self, client_id, workflow, state, missing_inspection):
        result = self._result_node(workflow)
        workflow.result = result
        workflow.log("finished")
        state.stack.pop()
        parent = state.stack[-1] if state.stack else None
        outcome = {
            "success": True,
            "workflow": {"id": workflow.workflow_id, "family": workflow.family, "finished": True, "result_node": result},
        }
        if parent is not None:
            parent.targets["child_result"] = result or ""
            outcome["returned_to"] = self._status(parent, state, missing_inspection)
            outcome["note"] = "result node %s is available to %s as role child_result" % (result, parent.family)
        return outcome

    def _abandon(self, client_id, arguments, missing_inspection):
        workflow = self._require(client_id)
        state = self._state(client_id)
        reason = str(arguments.get("reason") or "").strip()
        if len(reason) < 10:
            raise WorkflowError("abandon needs a reason")
        state.stack.pop()
        outcome = {
            "success": True,
            "workflow": {"id": workflow.workflow_id, "family": workflow.family, "abandoned": True},
            "note": "built nodes stay in the graph; abandoning does not undo anything",
        }
        if state.stack:
            outcome["returned_to"] = self._status(state.stack[-1], state, missing_inspection)
        return outcome

    # ---- compact status ----

    def status(self, client_id: str, missing_inspection=None) -> dict | None:
        """Compact current-step context for action results; None without a workflow."""
        workflow = self.active(client_id)
        if workflow is None:
            return None
        return self._status(workflow, self._state(client_id), missing_inspection, brief=True)

    def _status(self, workflow, state, missing_inspection, brief=False):
        step = workflow.step
        unmet = self._unmet(workflow, state, missing_inspection, lenient=brief and missing_inspection is None)
        status = {
            "id": workflow.workflow_id,
            "family": workflow.family,
            "step": step["id"],
            "step_no": "%d/%d" % (workflow.index + 1, len(workflow.steps)),
            "unmet": unmet,
        }
        if workflow.family == "2d":
            status["layer"] = workflow.layer
        if not brief:
            status.update(title=step["title"], do=step["do"], targets=dict(workflow.targets))
            if workflow.goal:
                status["goal"] = workflow.goal
            if step["skippable"]:
                status["skippable"] = True
            if workflow.history:
                status["recent"] = workflow.history[-3:]
            status["evidence"] = self._evidence_summary(state)
        return status

    @staticmethod
    def _evidence_summary(state):
        delivered = {}
        captured = 0
        for item in state.evidence:
            if item.invalid or item.certification_problem():
                continue
            if item.delivered:
                delivered.setdefault(item.node, []).append(item.frame)
            else:
                captured += 1
        return {"delivered_frames": {node: sorted(set(frames)) for node, frames in delivered.items()}, "awaiting_delivery": captured}

    def _snapshot(self, client_id, workflow, missing_inspection, guidance=False):
        state = self._state(client_id)
        snapshot = {"success": True, "workflow": self._status(workflow, state, missing_inspection)}
        if guidance and self.guidance is not None:
            extra = self.guidance(workflow.step["guidance"])
            if extra:
                snapshot["guidance"] = extra
        return snapshot
