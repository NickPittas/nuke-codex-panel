"""Bounded native Nuke actions behind the nuke_action tool.

Every action uses the real Nuke Python API (actual classes, knobs, enum labels and input
ports), reads the state back after changing it, and reports what it observed. One
action creates at most one visible node. A node is configured atomically in one call,
and a failed configuration of a node this action just created removes that node again
(verified, never assumed). Nothing here builds a graph from a monolithic description.

Nothing in this module imports ``nuke`` at import time (the MCP sidecar imports the
package for schemas); ``nuke`` is imported inside the methods that run on Nuke's main
thread.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import re

MAX_KNOBS = 24
MAX_LIST = 25
MAX_CHOICES = 40
MAX_FRAMES = 3
MAX_PLACEMENTS = 16
MAX_KEYS = 200
MAX_CODE = 6000
MAX_OUTPUT = 2000
_TOLERANCE = 1e-4

# Studio rule: vector shapes are built inside Roto or RotoPaint, never as stand-alone primitives.
_SHAPE_WORDS = frozenset(
    {"circle", "ellipse", "oval", "rectangle", "rect", "square", "line", "polygon", "shape", "bezier", "triangle", "star"}
)
SHAPE_HOSTS = ("Roto", "RotoPaint")

_CODE_KNOBS = frozenset(
    {
        "onCreate",
        "onDestroy",
        "knobChanged",
        "updateUI",
        "autolabel",
        "beforeRender",
        "afterRender",
        "beforeFrameRender",
        "afterFrameRender",
        "afterBackgroundRender",
        "afterBackgroundFrameRender",
        "filenameFilter",
        "validate",
    }
)
_CODE_KNOB_CLASSES = frozenset({"PyScript_Knob", "PyCustom_Knob", "PythonCustomKnob", "PythonKnob", "Script_Knob"})
_SKIP_KNOBS = frozenset(
    {"xpos", "ypos", "selected", "name", "indicators", "cached", "hide_input", "dope_sheet", "postage_stamp", "postage_stamp_frame", "lifetimeStart", "lifetimeEnd", "useLifetime", "note_font", "note_font_size", "note_font_color", "tile_color", "gl_color", "label"}
)
_DECORATIVE_CLASSES = frozenset({"Tab_Knob", "Text_Knob", "Obsolete_Knob", "Help_Knob", "Link_Knob"})
_STRING_CLASSES = frozenset(
    {"String_Knob", "EvalString_Knob", "File_Knob", "Multiline_Eval_String_Knob", "Channel_Knob", "ChannelMask_Knob", "Input_Knob"}
)
_FROM_USER_TEXT_CLASSES = frozenset({"Read", "DeepRead"})

_INTERPOLATIONS = {
    "smooth": "SMOOTH",
    "linear": "LINEAR",
    "constant": "CONSTANT",
    "catmull_rom": "CATMULL_ROM",
    "cubic": "CUBIC",
}


class ActionError(Exception):
    """A refused or failed action. ``facts`` carry the focused candidates for recovery."""

    def __init__(self, message: str, **facts):
        super().__init__(message)
        self.facts = facts


def _nuke():
    import nuke

    return nuke


def _plain(value):
    """JSON-safe rendering of a Nuke value."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    name = getattr(value, "name", None)
    if callable(name):
        try:
            return name()
        except Exception:
            pass
    return repr(value)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _close(requested, actual) -> bool:
    if _is_number(requested) and _is_number(actual):
        return abs(requested - actual) <= _TOLERANCE * max(1.0, abs(requested))
    return requested == actual


def _candidates(name: str, options, count: int = 5) -> list[str]:
    options = [item for item in options if isinstance(item, str)]
    lowered = {item.lower(): item for item in options}
    close = [lowered[match] for match in difflib.get_close_matches(name.lower(), list(lowered), n=count, cutoff=0.5)]
    contains = [item for item in options if name.lower() in item.lower() and item not in close]
    return (close + contains)[:count]


def _as_int(value, label: str) -> int:
    if isinstance(value, bool) or not _is_number(value) or int(value) != value:
        raise ActionError("%s must be an integer, got %r" % (label, value))
    return int(value)


def _as_number(value, label: str) -> float:
    if not _is_number(value):
        raise ActionError("%s must be a number, got %r" % (label, value))
    return float(value)


def _pair(value, label: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ActionError("%s must be [x, y]" % label)
    return _as_number(value[0], label + "[0]"), _as_number(value[1], label + "[1]")


# ---------------------------------------------------------------------------------
# Live graph facts for the workflow engine
# ---------------------------------------------------------------------------------


class NukeFacts:
    """Read-only live graph facts (implements ``guided_workflow.GraphFacts``)."""

    def node(self, name):
        nuke = _nuke()
        node = nuke.toNode(name) if isinstance(name, str) else None
        if node is None:
            return None
        inputs = []
        for index in range(node.inputs()):
            source = node.input(index)
            inputs.append(source.fullName() if source is not None else None)
        fact = {
            "name": node.fullName(),
            "class": node.Class(),
            "inputs": inputs,
            "x": node.xpos(),
            "y": node.ypos(),
            "label": None,
            "operation": None,
        }
        knobs = node.knobs()
        if "label" in knobs:
            fact["label"] = knobs["label"].value()
        if node.Class() == "Merge2" and "operation" in knobs:
            fact["operation"] = knobs["operation"].value()
        return fact

    def upstream(self, name):
        nuke = _nuke()
        start = nuke.toNode(name)
        if start is None:
            return []
        seen, stack = [], [start]
        names = set()
        while stack:
            node = stack.pop()
            full = node.fullName()
            if full in names:
                continue
            names.add(full)
            seen.append(full)
            for index in range(node.inputs()):
                source = node.input(index)
                if source is not None:
                    stack.append(source)
        return seen

    def animation(self, names):
        nuke = _nuke()
        animated = False
        keys = []
        unreadable = []
        for name in names:
            node = nuke.toNode(name)
            if node is None:
                continue
            for knob_name, knob in node.knobs().items():
                if node.Class() in SHAPE_HOSTS and knob_name == "curves":
                    continue
                try:
                    if not knob.isAnimated():
                        continue
                    animated = True
                    for curve in knob.animations():
                        keys.extend(key.x for key in curve.keys())
                except Exception:
                    unreadable.append("%s.%s" % (name, knob_name))
            if node.Class() in SHAPE_HOSTS:
                try:
                    times = _roto_key_times(node)
                except Exception:
                    unreadable.append("%s.curves" % name)
                else:
                    if times:
                        animated = True
                        keys.extend(times)
        return {
            "animated": animated,
            "first_key": min(keys) if keys else None,
            "last_key": max(keys) if keys else None,
            "unreadable": unreadable[:8],
        }

    def project(self):
        root = _nuke().root()
        fmt = root.format()
        return {
            "format_name": fmt.name() or "",
            "width": fmt.width(),
            "height": fmt.height(),
            "pixel_aspect": fmt.pixelAspect(),
            "fps": root.fps(),
            "first_frame": root.firstFrame(),
            "last_frame": root.lastFrame(),
        }

    def digest(self):
        from .python_executor import graph_snapshot

        snapshot = graph_snapshot()
        if snapshot is None:
            return None
        return hashlib.sha1(json.dumps(sorted(snapshot.items())).encode("utf-8")).hexdigest()


def _roto_elements(layer):
    for element in layer:
        yield element
        if type(element).__name__ == "Layer":
            yield from _roto_elements(element)


def _roto_key_times(node):
    """Frames at which any shape/layer transform or control point of a Roto node is keyed."""
    times = []
    curves = node["curves"]
    for element in _roto_elements(curves.rootLayer):
        kind = type(element).__name__
        if kind in ("Shape", "Layer"):
            times.extend(element.getTransform().getTransformKeyTimes())
        if kind == "Shape":
            for point in element:
                for part in (point.center, point.leftTangent, point.rightTangent):
                    times.extend(part.getControlPointKeyTimes())
    return times


# ---------------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------------


class NativeActions:
    """Runs one action on Nuke's main thread. ``capture`` is the bridge's synchronous capture."""

    ALLOWED = {
        "create": {"class", "name", "knobs", "inputs", "place", "select"},
        "select": {"nodes"},
        "inspect": {"node", "knobs", "match", "non_default"},
        "set": {"node", "knobs"},
        "connect": {"node", "inputs"},
        "swap": {"node", "a", "b"},
        "layout": {"placements"},
        "project": {"width", "height", "pixel_aspect", "format_name", "fps", "first_frame", "last_frame", "allow_overwrite", "reason"},
        "sample": {"node", "x", "y", "frame", "size", "channels"},
        "render": {"node", "frame", "frames", "target", "zoom", "center", "region"},
        "view": {"node", "input", "zoom", "center", "region"},
        "animate": {"node", "knob", "keys", "interpolation"},
        "shape": {"node", "kind", "name", "center", "size", "points", "closed"},
        "shape_style": {"node", "shape", "color", "opacity", "feather"},
        "shape_key": {"node", "shape", "keys"},
        "delete": {"node"},
        "internal_python": {"node", "code", "label"},
    }

    def __init__(self, facts: NukeFacts):
        self.facts = facts
        self.mutated = False
        self.touched: list[str] = []

    def touch(self, name: str) -> None:
        if name not in self.touched:
            self.touched.append(name)

    def _hydrate_reader_file(self, knob, value) -> None:
        """fromUserText, declaring Root's range auto-init (first_frame/last_frame/lock_range) when it is the only Root change."""
        from .python_executor import _stable_script

        range_knobs = ("first_frame", "last_frame", "lock_range")
        excluded = frozenset(range_knobs)
        try:
            root = _nuke().root()
            before_range = tuple(root[name].value() for name in range_knobs)
            before_rest = _stable_script(root, exclude_knobs=excluded)
        except Exception:
            root = None
        try:
            knob.fromUserText(value)
        finally:
            if root is not None:
                try:
                    after_range = tuple(root[name].value() for name in range_knobs)
                    after_rest = _stable_script(root, exclude_knobs=excluded)
                except Exception:
                    after_range, after_rest = before_range, None
                if after_range != before_range and after_rest == before_rest:
                    self.touch("<root>")

    def untouch(self, name: str) -> None:
        if name in self.touched:
            self.touched.remove(name)

    # ---- dispatch ----

    def run(self, action: str, arguments: dict, capture=None, on_capture=None) -> dict:
        handler = getattr(self, "_do_" + action, None)
        allowed = self.ALLOWED.get(action)
        if handler is None or allowed is None:
            raise ActionError("unknown action %r; one of %s" % (action, ", ".join(sorted(self.ALLOWED))))
        extra = sorted(set(arguments) - allowed - {"action"})
        if extra:
            raise ActionError(
                "action %s does not take %s; it takes: %s" % (action, ", ".join(extra), ", ".join(sorted(allowed)))
            )
        self.capture = capture
        self.on_capture = on_capture
        result = handler(arguments)
        result.setdefault("success", True)
        result["action"] = action
        return result

    # ---- node helpers ----

    def _node(self, name, label="node"):
        nuke = _nuke()
        if not isinstance(name, str) or not name.strip():
            raise ActionError("%s must be a node name" % label)
        node = nuke.toNode(name.strip())
        if node is None:
            names = [item.fullName() for item in nuke.allNodes(group=nuke.root(), recurseGroups=True)]
            raise ActionError(
                "no node named %r" % name,
                candidates=_candidates(name, names),
                node_count=len(names),
                missing_node=name.strip(),
            )
        return node

    def _describe(self, node) -> dict:
        inputs = []
        for index in range(node.inputs()):
            source = node.input(index)
            inputs.append(source.fullName() if source is not None else None)
        info = {
            "name": node.fullName(),
            "class": node.Class(),
            "inputs": inputs,
            "input_slots": node.maxInputs(),
            "x": node.xpos(),
            "y": node.ypos(),
        }
        try:
            info["error"] = bool(node.hasError())
        except Exception as exc:
            info["error_query_failed"] = "%s: %s" % (type(exc).__name__, exc)
        if node.Class() in ("Merge", "Merge2"):
            info["ports"] = "0=B (background), 1=A (foreground)"
        info.update(self._media_facts(node))
        return info

    @staticmethod
    def _media_facts(node) -> dict:
        """Effective frame range and format of a Read/DeepRead, as the node resolves them now."""
        if node.Class() not in _FROM_USER_TEXT_CLASSES:
            return {}
        facts = {}
        try:
            facts["frame_range"] = {"first": int(node["first"].value()), "last": int(node["last"].value())}
        except Exception as exc:
            facts["frame_range_error"] = "%s: %s" % (type(exc).__name__, exc)
        try:
            fmt = node.format()
            facts["format"] = {
                "width": fmt.width(),
                "height": fmt.height(),
                "pixel_aspect": round(float(fmt.pixelAspect()), 6),
                "name": fmt.name() or None,
            }
        except Exception as exc:
            facts["format_error"] = "%s: %s" % (type(exc).__name__, exc)
        return facts

    def _knob(self, node, name):
        knob = node.knob(name)
        if knob is not None:
            return knob
        knobs = node.knobs()

        def usable(candidate, strict=False):
            try:
                cls = candidate.Class()
                knob_name = candidate.name()
            except Exception:
                return False
            if cls in _DECORATIVE_CLASSES or cls in _CODE_KNOB_CLASSES or knob_name in _CODE_KNOBS:
                return False
            return not (strict and knob_name in _SKIP_KNOBS)

        def control(knob_name):
            candidate = knobs[knob_name]
            info = {"name": knob_name, "class": candidate.Class()}
            try:
                info["label"] = candidate.label()
            except Exception:
                pass
            if candidate.Class() == "Enumeration_Knob":
                try:
                    values = list(candidate.values())
                    info["choices"] = values[:12]
                    if len(values) > 12:
                        info["choices_total"] = len(values)
                except Exception:
                    pass
            return info

        wanted = name.strip().lower() if isinstance(name, str) else ""
        exact, folded = [], []
        for knob_name, candidate in knobs.items():
            if not usable(candidate):
                continue
            try:
                label = candidate.label()
            except Exception:
                continue
            if not isinstance(label, str):
                continue
            if label == name:
                exact.append(knob_name)
            elif label.strip().lower() == wanted:
                folded.append(knob_name)
        matches = exact or folded
        if len(matches) == 1:
            return knobs[matches[0]]
        eligible = {knob_name: item for knob_name, item in knobs.items() if usable(item, strict=True)}
        facts = {}
        if len(matches) > 1:
            facts["candidates"] = list(matches[:8])
            facts["ambiguous_label"] = [control(item) for item in matches[:8]]
            message = "label %r matches several knobs of node %s (%s); use one exact knob name" % (
                name, node.fullName(), node.Class(),
            )
        else:
            options = _candidates(name, list(eligible)) if isinstance(name, str) else []
            for knob_name, item in eligible.items():
                try:
                    label = item.label()
                except Exception:
                    continue
                if isinstance(label, str) and wanted and wanted in label.lower() and knob_name not in options:
                    options.append(knob_name)
            facts["candidates"] = list(options[:6])
            facts["candidate_controls"] = [control(item) for item in options[:6]]
            if not options:
                names = list(eligible)
                facts["available_controls"] = [control(item) for item in names[:MAX_LIST]]
                if len(names) > MAX_LIST:
                    facts["available_controls_total"] = len(names)
            message = "node %s (%s) has no knob %r" % (node.fullName(), node.Class(), name)
        facts["requested_knob"] = name
        facts["node_class"] = node.Class()
        facts["recovery"] = {
            "reference_kind": "tool_contract",
            "next_calls": [
                {
                    "tool": "nuke_action",
                    "arguments": {"action": "inspect", "node": node.fullName(), "match": name.strip()},
                }
            ]
            if isinstance(name, str) and name.strip()
            else [],
        }
        raise ActionError(message, **facts)

    def _read(self, knob):
        cls = knob.Class()
        try:
            size = knob.arraySize()
        except Exception:
            size = 1
        if cls in _STRING_CLASSES or cls in ("Enumeration_Knob", "Boolean_Knob"):
            return _plain(knob.value())
        if size > 1:
            return [_plain(knob.value(index)) for index in range(size)]
        return _plain(knob.value())

    def _summary(self, knob, choices=False) -> dict:
        info = {"class": knob.Class()}
        try:
            info["label"] = knob.label()
        except Exception:
            pass
        try:
            info["value"] = self._read(knob)
        except Exception as exc:
            info["value_error"] = "%s: %s" % (type(exc).__name__, exc)
        try:
            if knob.isAnimated():
                info["animated"] = True
        except Exception:
            pass
        if knob.Class() == "Format_Knob":
            try:
                fmt = knob.value()
                info["width"] = fmt.width()
                info["height"] = fmt.height()
                info["pixel_aspect"] = round(float(fmt.pixelAspect()), 6)
            except Exception:
                pass
        if choices and knob.Class() == "Enumeration_Knob":
            values = list(knob.values())
            info["choices"] = values[:MAX_CHOICES]
            if len(values) > MAX_CHOICES:
                info["choices_total"] = len(values)
        return info

    # ---- knob setting ----

    @staticmethod
    def _enum_forms(entry) -> list:
        """Every spelling of one enumeration entry: the full entry, its token and its label.

        Entries may be 'token<TAB>label' (Tracker4 warp: 'srt<TAB>Translation/Rotation/Scale'); value() reads
        back the token while values() may list the label or the full entry.
        """
        text = str(entry)
        forms = [text]
        if "\t" in text:
            token, _, label = text.partition("\t")
            forms += [token, label]
        return forms

    def _set_enumeration(self, node, knob, value):
        """Set an enumeration knob from the canonical token, a label or a full entry; read back the token."""
        knob_name = knob.name()
        choices = list(knob.values())
        match = None
        if isinstance(value, str):
            for fold in (False, True):
                needle = value.lower() if fold else value
                found = [
                    item
                    for item in choices
                    if needle in [form.lower() if fold else form for form in self._enum_forms(item)]
                ]
                if len(found) == 1:
                    match = found[0]
                    break
                if len(found) > 1:
                    raise ActionError(
                        "%r is ambiguous for %s.%s" % (value, node.fullName(), knob_name),
                        choices=choices[:MAX_CHOICES],
                        matches=found[:MAX_CHOICES],
                    )
        if match is None:
            raise ActionError(
                "%r is not a valid value of %s.%s" % (value, node.fullName(), knob_name),
                choices=choices[:MAX_CHOICES],
                close=_candidates(str(value), choices),
            )
        # `self.mutated` is raised immediately before a setter runs, never by validation.
        forms = self._enum_forms(match)
        wanted = choices.index(match)

        def took() -> bool:
            # value() reads the token; the index is the label-independent truth.
            if knob.value() in forms:
                return True
            try:
                return int(knob.getValue()) == wanted
            except Exception:
                return False

        self.mutated = True
        knob.setValue(forms[1] if len(forms) > 1 else match)
        if not took():
            # Some knobs only take the entry as listed.
            knob.setValue(match)
        if not took():
            raise ActionError(
                "%s.%s did not take %r: it reads %r" % (node.fullName(), knob_name, value, knob.value()),
                choices=choices[:MAX_CHOICES],
                graph_changed=True,
            )
        return _plain(knob.value())

    def _set_knob(self, node, name, value):
        """Set one knob to ``value`` and return what the knob reads afterwards."""
        knob = self._knob(node, name)
        knob_name = knob.name()
        cls = knob.Class()
        if knob_name in _CODE_KNOBS or cls in _CODE_KNOB_CLASSES:
            raise ActionError(
                "knob %s.%s holds code or runs a script; nuke_action does not set it (internal_python is the "
                "approved route)" % (node.fullName(), knob_name)
            )
        if knob_name == "curves" and node.Class() in SHAPE_HOSTS:
            raise ActionError("shapes live in the curves knob: use the shape, shape_style and shape_key actions")
        if isinstance(value, dict):
            return self._set_expression(node, knob, value)
        # `self.mutated` is raised immediately before a setter runs, never by validation.
        if cls == "Enumeration_Knob":
            return self._set_enumeration(node, knob, value)
        if cls == "Boolean_Knob":
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value in (0, 1):
                value = bool(value)
            if not isinstance(value, bool):
                raise ActionError("%s.%s is a checkbox: use true or false" % (node.fullName(), knob_name))
            self.mutated = True
            knob.setValue(value)
            self._verify(knob, value, node, knob_name)
            return self._read(knob)
        if cls == "Format_Knob":
            if not isinstance(value, str):
                raise ActionError("%s.%s takes a format name" % (node.fullName(), knob_name))
            names = [fmt.name() for fmt in _nuke().formats() if fmt.name()]
            if value not in names:
                raise ActionError(
                    "no format named %r" % value,
                    close=_candidates(value, names),
                    hint="define one with the project action (width/height) first",
                )
            self.mutated = True
            knob.setValue(value)
            return self._read(knob)
        if cls in _STRING_CLASSES:
            if not isinstance(value, str):
                raise ActionError("%s.%s takes a string, got %r" % (node.fullName(), knob_name, value))
            self.mutated = True
            if cls == "File_Knob" and node.Class() in _FROM_USER_TEXT_CLASSES and knob.name() == "file":
                self._hydrate_reader_file(knob, value)
            else:
                knob.setValue(value)
            return self._read(knob)
        listed = isinstance(value, (list, tuple))
        numbers = list(value) if listed else [value]
        if numbers and all(_is_number(item) for item in numbers):
            try:
                size = knob.arraySize()
            except Exception:
                size = 1
            values = numbers if listed else numbers * size
            if len(values) != size:
                raise ActionError(
                    "%s.%s (%s) takes %d number(s); got %r" % (node.fullName(), knob_name, cls, size, value)
                )
            self.mutated = True
            if size == 1:
                knob.setValue(values[0])
            else:
                for index, item in enumerate(values):
                    knob.setValue(item, index)
            actual = self._read(knob)
            readback = actual if isinstance(actual, list) else [actual]
            if not all(_close(a, b) for a, b in zip(values, readback)):
                return {"requested": values, "actual": actual, "adjusted": True}
            return actual
        raise ActionError(
            "knob %s.%s is a %s and %r is not a value it accepts through nuke_action"
            % (node.fullName(), knob_name, cls, value)
        )

    def _verify(self, knob, expected, node, name):
        actual = self._read(knob)
        if not _close(expected, actual):
            raise ActionError(
                "%s.%s reads %r after setting %r" % (node.fullName(), name, actual, expected)
            )

    def _set_expression(self, node, knob, spec):
        expression = spec.get("expression")
        unknown = set(spec) - {"expression", "channel"}
        if unknown or not isinstance(expression, str) or not expression.strip():
            raise ActionError('an expression value is {"expression": "<text>", "channel": <optional index>}')
        channel = spec.get("channel", -1)
        if not isinstance(channel, int) or isinstance(channel, bool):
            raise ActionError("expression channel must be an integer index")
        self.mutated = True
        if not knob.setExpression(expression, channel):
            raise ActionError(
                "%s.%s rejected the expression %r" % (node.fullName(), knob.name(), expression)
            )
        return {"expression": expression, "channel": channel}

    def _apply_knobs(self, node, knobs) -> dict:
        if not isinstance(knobs, dict) or not knobs:
            raise ActionError("knobs must be an object {knob name: value}")
        if len(knobs) > MAX_KNOBS:
            raise ActionError("at most %d knobs per action" % MAX_KNOBS)
        applied = {}
        items = list(knobs.items())
        if node.Class() in _FROM_USER_TEXT_CLASSES:
            # file hydration derives first/last/format; explicit overrides must follow it
            def is_file(item):
                try:
                    return self._knob(node, item[0]).name() == "file"
                except Exception:
                    return False  # unresolved names fail later, in normal application order

            items.sort(key=lambda item: not is_file(item))
        for name, value in items:
            try:
                applied[name] = self._set_knob(node, name, value)
            except ActionError as exc:
                if applied:
                    exc.facts.setdefault("applied", dict(applied))
                raise
            except Exception as exc:
                raise ActionError(
                    "Nuke rejected %r for %s.%s: %s: %s" % (value, node.fullName(), name, type(exc).__name__, exc),
                    applied=applied,
                ) from exc
        return applied

    # ---- ports ----

    def _port(self, node, port) -> int:
        if isinstance(port, str) and port.strip().lstrip("-").isdigit():
            port = int(port)
        if isinstance(port, str) and node.Class() in ("Merge", "Merge2") and port.strip().upper() in ("B", "A"):
            return 0 if port.strip().upper() == "B" else 1
        if isinstance(port, bool) or not isinstance(port, int) or port < 0:
            raise ActionError(
                "port must be an input index (0, 1, ...)%s" % (" or 'B'/'A' for a Merge" if node.Class() in ("Merge", "Merge2") else ""),
                input_slots=node.maxInputs(),
            )
        if port >= node.maxInputs():
            raise ActionError(
                "%s (%s) has %d input slot(s); port %d does not exist" % (node.fullName(), node.Class(), node.maxInputs(), port),
                input_slots=node.maxInputs(),
            )
        return port

    def _connect_inputs(self, node, inputs) -> dict:
        if not isinstance(inputs, dict) or not inputs:
            raise ActionError('inputs must be an object {"0": "SourceNode", "1": null}')
        pending = []
        for port, source_name in inputs.items():
            index = self._port(node, port)
            if source_name is None:
                pending.append((index, None))
                continue
            source = self._node(source_name, "input source")
            if source == node:
                raise ActionError("a node cannot feed itself")
            if not node.canSetInput(index, source):
                raise ActionError(
                    "%s input %d cannot connect to %s (would loop, or the slot does not accept it)"
                    % (node.fullName(), index, source.fullName()),
                    input_slots=node.maxInputs(),
                )
            pending.append((index, source))
        connected = {}
        for index, source in pending:
            self.mutated = True
            node.setInput(index, source)
            actual = node.input(index)
            if actual != source:
                raise ActionError(
                    "%s input %d reads %s after connecting"
                    % (node.fullName(), index, actual.fullName() if actual is not None else "nothing")
                )
            connected[str(index)] = source.fullName() if source is not None else None
        return connected

    # ---- placement ----

    def _place(self, node, spec):
        if not isinstance(spec, dict):
            raise ActionError('place must be an object such as {"below": "Node"}, {"right_of": "Node"}, {"x": 0, "y": 0}')
        gap = spec.get("gap")
        gap = 40 if gap is None else _as_int(gap, "gap")
        keys = set(spec) - {"gap", "dx", "dy"}
        relations = ("below", "above", "left_of", "right_of")
        by_coordinates = keys == {"x", "y"}
        relation = next(iter(keys)) if len(keys) == 1 else None
        if not by_coordinates and relation not in relations:
            raise ActionError("place takes one of below / above / left_of / right_of, or x and y")
        dx = _as_int(spec.get("dx", 0), "dx")
        dy = _as_int(spec.get("dy", 0), "dy")
        self.mutated = True
        if by_coordinates:
            x, y = _as_int(spec["x"], "x") + dx, _as_int(spec["y"], "y") + dy
        else:
            anchor = self._node(spec[relation], "place." + relation)
            ax, ay = anchor.xpos(), anchor.ypos()
            if relation == "below":
                x, y = ax, ay + anchor.screenHeight() + gap
            elif relation == "above":
                x, y = ax, ay - node.screenHeight() - gap
            elif relation == "right_of":
                x, y = ax + anchor.screenWidth() + gap, ay
            else:
                x, y = ax - node.screenWidth() - gap, ay
            x, y = x + dx, y + dy
        node.setXYpos(int(x), int(y))
        return {"x": node.xpos(), "y": node.ypos()}

    def _default_place(self, node, first_input):
        """Below the node's first input (keeps the B trunk vertical), else in a free column."""
        nuke = _nuke()
        self.mutated = True
        if first_input is not None:
            node.setXYpos(first_input.xpos(), first_input.ypos() + first_input.screenHeight() + 50)
            return
        others = [item for item in nuke.allNodes(group=nuke.root()) if item != node]
        if not others:
            node.setXYpos(0, 0)
            return
        right = max(item.xpos() + item.screenWidth() for item in others)
        top = min(item.ypos() for item in others)
        node.setXYpos(right + 60, top)

    # ---- create / select / inspect / set / connect / swap / delete ----

    def _do_create(self, args):
        nuke = _nuke()
        cls = args.get("class")
        if not isinstance(cls, str) or not cls.strip():
            raise ActionError("create needs `class` (a native Nuke node class such as Merge2, Blur, Roto)")
        cls = cls.strip()
        if cls.lower() in _SHAPE_WORDS:
            raise ActionError(
                "there is no %s node class. Studio rule: every shape (circle, rectangle, line, custom path) "
                "starts as a Roto or RotoPaint node; create Roto, then use the shape action." % cls,
                use=list(SHAPE_HOSTS),
            )
        if cls == "Viewer" and nuke.allNodes("Viewer", group=nuke.root(), recurseGroups=True):
            existing = [item.fullName() for item in nuke.allNodes("Viewer", group=nuke.root(), recurseGroups=True)]
            raise ActionError("a Viewer already exists: reuse it (view / render actions)", viewers=existing)
        name = args.get("name")
        if name is not None and (not isinstance(name, str) or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name)):
            raise ActionError("name must be a node name like Merge_BG (letters, digits, underscore)")
        for key in ("knobs", "inputs", "place"):
            if args.get(key) is not None and not isinstance(args[key], dict):
                raise ActionError("%s must be an object" % key)
        if args.get("inputs"):
            # Refuse bad sources before anything is created.
            for source_name in args["inputs"].values():
                if source_name is not None:
                    self._node(source_name, "input source")
        for current in nuke.selectedNodes():
            current.setSelected(False)  # createNode would connect to the selection
        self.mutated = True
        try:
            node = nuke.createNode(cls, inpanel=False)
        except Exception as exc:
            names = []
            try:
                names = [item for item in nuke.nodeTypes() if isinstance(item, str)]
            except Exception:
                pass
            raise ActionError(
                "could not create node class %r: %s" % (cls, exc),
                close=_candidates(cls, names),
            ) from exc
        self.touch(node.fullName())
        try:
            if name:
                created_name = node.fullName()
                node.setName(name)
                if node.fullName() != created_name:
                    self.untouch(created_name)  # the creation name no longer exists
                self.touch(node.fullName())
            result = {"node": node.fullName(), "class": node.Class()}
            if args.get("knobs"):
                result["knobs"] = self._apply_knobs(node, args["knobs"])
            first_input = None
            if args.get("inputs"):
                result["connected"] = self._connect_inputs(node, args["inputs"])
                source = node.input(0)
                first_input = source
            if args.get("place"):
                result["position"] = self._place(node, args["place"])
            else:
                self._default_place(node, first_input)
                result["position"] = {"x": node.xpos(), "y": node.ypos()}
            if args.get("select", True):
                node.setSelected(True)
        except ActionError as exc:
            created = node.fullName()
            nuke.delete(node)
            removed = nuke.toNode(created) is None
            root_changed = "<root>" in self.touched
            exc.facts.update(created_node=created, node_removed=removed, rolled_back=removed and not root_changed)
            recovery = dict(exc.facts.get("recovery") or {})
            recovery["reference_kind"] = "tool_contract"
            if removed and root_changed:
                recovery["next_calls"] = []
                recovery["note"] = (
                    "%s was removed, but loading its media already changed Project Settings (Root frame range / lock_range) "
                    "and that change was NOT undone. Inspect the project/Root range and fix it if unwanted, then reissue the "
                    "same create with the corrected arguments." % created
                )
            elif removed:
                # The node is gone: never point at it. Reissue create with the corrected arguments.
                recovery["next_calls"] = []
                recovery["note"] = (
                    "%s was rolled back and no longer exists; nothing else changed. Reissue the same create with the "
                    "corrected arguments (keep the class, knobs, inputs and place you intended), using the control "
                    "facts above." % created
                )
            else:
                exc.facts["note"] = "the new node %s could NOT be removed; inspect it" % created
                recovery["next_calls"] = [
                    {"tool": "nuke_action", "arguments": {"action": "inspect", "node": created}}
                ]
            exc.facts["recovery"] = recovery
            raise
        result.update(self._describe(node))
        return {**self._brief(result), "graph_changed": True}

    @staticmethod
    def _brief(result):
        return {
            k: v
            for k, v in result.items()
            if k
            in (
                "node", "class", "knobs", "connected", "position", "inputs", "input_slots", "error",
                "frame_range", "format", "frame_range_error", "format_error",
            )
        }

    def _do_select(self, args):
        nuke = _nuke()
        names = args.get("nodes")
        if not isinstance(names, list) or not names or len(names) > MAX_LIST:
            raise ActionError("nodes must be a non-empty list of node names (at most %d)" % MAX_LIST)
        nodes = [self._node(name) for name in names]
        for current in nuke.selectedNodes():
            current.setSelected(False)
        for node in nodes:
            node.setSelected(True)
        selected = [item.fullName() for item in nuke.selectedNodes()]
        if sorted(selected) != sorted(node.fullName() for node in nodes):
            raise ActionError("selection reads %r after selecting" % selected)
        return {"selected": selected, "graph_changed": False}

    def _do_inspect(self, args):
        if args.get("node") is None:
            return self._inspect_scene()
        node = self._node(args["node"])
        info = self._describe(node)
        knobs = node.knobs()
        wanted = args.get("knobs")
        if wanted is not None:
            if not isinstance(wanted, list) or not wanted or len(wanted) > MAX_LIST:
                raise ActionError("knobs must be a list of knob names (at most %d)" % MAX_LIST)
            info["knobs"] = {name: self._summary(self._knob(node, name), choices=True) for name in wanted}
        match = args.get("match")
        if match is not None:
            if not isinstance(match, str) or not match.strip():
                raise ActionError("match must be text to look for in knob names and labels")
            needle = match.strip().lower()
            found = {}
            for knob_name, knob in knobs.items():
                if knob.Class() in _DECORATIVE_CLASSES:
                    continue
                try:
                    label = knob.label()
                except Exception:
                    label = ""
                if needle in knob_name.lower() or needle in label.lower():
                    found[knob_name] = self._summary(knob, choices=True)
                if len(found) >= MAX_LIST:
                    break
            info["matches"] = found
        if wanted is None and match is None or args.get("non_default"):
            changed = {}
            for knob_name, knob in knobs.items():
                if knob_name in _SKIP_KNOBS or knob.Class() in _DECORATIVE_CLASSES or knob_name == "curves":
                    continue
                try:
                    if not knob.notDefault():
                        continue
                except Exception:
                    continue
                changed[knob_name] = self._summary(knob)
                if len(changed) >= MAX_LIST:
                    info["non_default_truncated"] = True
                    break
            info["non_default"] = changed
        if node.Class() in SHAPE_HOSTS:
            info["shapes"] = self._shape_names(node)
        return {"inspected": info, "graph_changed": False}

    def _inspect_scene(self):
        nuke = _nuke()
        facts = self.facts
        counts = {}
        for node in nuke.allNodes(group=nuke.root(), recurseGroups=True):
            counts[node.Class()] = counts.get(node.Class(), 0) + 1
        viewers = nuke.allNodes("Viewer", group=nuke.root(), recurseGroups=True)
        viewer = []
        for node in viewers:
            viewer.append({"name": node.fullName(), "inputs": [node.input(i).fullName() if node.input(i) else None for i in range(node.inputs())]})
        return {
            "scene": {
                "project": facts.project(),
                "frame": nuke.frame(),
                "selected": [item.fullName() for item in nuke.selectedNodes()],
                "viewers": viewer,
                "class_counts": counts,
            },
            "graph_changed": False,
            "note": "get_nuke_context(include_nodes=true) lists the nodes; inspect node=<name> shows one node.",
        }

    def _do_set(self, args):
        node = self._node(args.get("node"))
        self.touch(node.fullName())
        applied = self._apply_knobs(node, args.get("knobs"))
        result = {"node": node.fullName(), "knobs": applied, "graph_changed": True}
        result.update(self._media_facts(node))
        return result

    def _do_connect(self, args):
        node = self._node(args.get("node"))
        self.touch(node.fullName())
        connected = self._connect_inputs(node, args.get("inputs"))
        info = self._describe(node)
        return {"node": node.fullName(), "connected": connected, "inputs": info["inputs"], "input_slots": info["input_slots"], "graph_changed": True}

    def _do_swap(self, args):
        node = self._node(args.get("node"))
        a = self._port(node, args.get("a"))
        b = self._port(node, args.get("b"))
        if a == b:
            raise ActionError("a and b are the same port")
        source_a, source_b = node.input(a), node.input(b)
        if source_a is None and source_b is None:
            raise ActionError("both inputs are empty; nothing to swap")
        self.touch(node.fullName())
        for index, source in ((a, source_b), (b, source_a)):
            if source is not None and not node.canSetInput(index, source):
                raise ActionError(
                    "%s input %d cannot take %s" % (node.fullName(), index, source.fullName()),
                    input_slots=node.maxInputs(),
                )
        self.mutated = True
        node.setInput(a, source_b)
        node.setInput(b, source_a)
        if node.input(a) != source_b or node.input(b) != source_a:
            raise ActionError("inputs of %s did not swap as requested; inspect it" % node.fullName())
        info = self._describe(node)
        return {"node": node.fullName(), "swapped": [a, b], "inputs": info["inputs"], "graph_changed": True}

    def _do_delete(self, args):
        nuke = _nuke()
        node = self._node(args.get("node"))
        name = node.fullName()
        if node.Class() == "Viewer":
            raise ActionError("the Viewer is reused, never deleted")
        dependents = [item.fullName() for item in node.dependent(nuke.INPUTS)]
        self.touch(name)
        for item in dependents:
            self.touch(item)
        self.mutated = True
        nuke.delete(node)
        if nuke.toNode(name) is not None:
            raise ActionError("%s still exists after delete" % name)
        return {"deleted": name, "disconnected_dependents": dependents[:MAX_LIST], "graph_changed": True}

    # ---- layout ----

    def _do_layout(self, args):
        placements = args.get("placements")
        if not isinstance(placements, list) or not placements or len(placements) > MAX_PLACEMENTS:
            raise ActionError("placements must be a list of 1-%d {node, below|above|left_of|right_of|x+y, gap?}" % MAX_PLACEMENTS)
        positions = {}
        for entry in placements:
            if not isinstance(entry, dict) or "node" not in entry:
                raise ActionError("each placement is {node, ...place spec}")
            node = self._node(entry["node"])
            spec = {k: v for k, v in entry.items() if k != "node"}
            if not spec:
                raise ActionError("placement of %s needs below / above / left_of / right_of / x+y" % node.fullName())
            self.touch(node.fullName())
            positions[node.fullName()] = self._place(node, spec)
        return {"positions": positions, "graph_changed": True}

    # ---- project / sample ----

    def _project_in_use(self):
        nuke = _nuke()
        content = [item for item in nuke.allNodes(group=nuke.root(), recurseGroups=True) if item.Class() != "Viewer"]
        script = nuke.root().name()
        return bool(content) or script not in ("", "Root")

    def _do_project(self, args):
        nuke = _nuke()
        root = nuke.root()
        current = self.facts.project()
        width, height = args.get("width"), args.get("height")
        if (width is None) != (height is None):
            raise ActionError("width and height go together")
        wanted = {}
        if width is not None:
            width, height = _as_int(width, "width"), _as_int(height, "height")
            if width < 1 or height < 1:
                raise ActionError("width and height must be positive")
            aspect = _as_number(args.get("pixel_aspect", 1.0), "pixel_aspect")
            wanted["size"] = (width, height, aspect)
        if args.get("fps") is not None:
            wanted["fps"] = _as_number(args["fps"], "fps")
        if args.get("first_frame") is not None:
            wanted["first_frame"] = _as_int(args["first_frame"], "first_frame")
        if args.get("last_frame") is not None:
            wanted["last_frame"] = _as_int(args["last_frame"], "last_frame")
        if not wanted:
            return {"project": current, "changed": False, "graph_changed": False, "note": "no settings given; this is the current project"}
        differs = []
        if "size" in wanted and (current["width"], current["height"], current["pixel_aspect"]) != wanted["size"]:
            differs.append("format")
        for key in ("fps", "first_frame", "last_frame"):
            if key in wanted and not _close(wanted[key], current[key]):
                differs.append(key)
        if not differs:
            return {"project": current, "changed": False, "graph_changed": False, "note": "the project already has these settings; nothing changed"}
        if self._project_in_use():
            reason = str(args.get("reason") or "").strip()
            if args.get("allow_overwrite") is not True or len(reason) < 10:
                raise ActionError(
                    "this script already has content: project %s would change existing settings. Change them only "
                    "when the task requires it: repeat with allow_overwrite=true and a `reason`." % ", ".join(differs),
                    current=current,
                )
        self.touch("<root>")
        self.mutated = True
        if "format" in differs:
            width, height, aspect = wanted["size"]
            fmt = next(
                (
                    item
                    for item in nuke.formats()
                    if item.name() and item.width() == width and item.height() == height and abs(item.pixelAspect() - aspect) < 1e-6
                ),
                None,
            )
            if fmt is None:
                name = args.get("format_name") or "%dx%d" % (width, height)
                if not re.match(r"^[A-Za-z0-9_.\-]+$", str(name)):
                    raise ActionError("format_name must have no spaces")
                fmt = nuke.addFormat("%d %d %s %s" % (width, height, aspect, name))
                if fmt is None:
                    raise ActionError("Nuke refused to define format %r" % name)
            root["format"].setValue(fmt.name())
        if "fps" in differs:
            root["fps"].setValue(wanted["fps"])
        if "first_frame" in differs:
            root["first_frame"].setValue(wanted["first_frame"])
        if "last_frame" in differs:
            root["last_frame"].setValue(wanted["last_frame"])
        actual = self.facts.project()
        problems = []
        if "format" in differs and (actual["width"], actual["height"]) != wanted["size"][:2]:
            problems.append("format reads %dx%d" % (actual["width"], actual["height"]))
        for key in ("fps", "first_frame", "last_frame"):
            if key in differs and not _close(wanted[key], actual[key]):
                problems.append("%s reads %r" % (key, actual[key]))
        if problems:
            raise ActionError("project settings did not apply: " + "; ".join(problems), previous=current, project=actual)
        return {"project": actual, "previous": current, "changed": differs, "graph_changed": True}

    def _do_sample(self, args):
        nuke = _nuke()
        node = self._node(args.get("node"))
        x, y = _as_number(args.get("x"), "x"), _as_number(args.get("y"), "y")
        size = args.get("size")
        dx, dy = (1.0, 1.0) if size is None else _pair(size, "size")
        available = list(node.channels())
        wanted = args.get("channels") or ["rgba.red", "rgba.green", "rgba.blue", "rgba.alpha"]
        if not isinstance(wanted, list) or not wanted or len(wanted) > 8:
            raise ActionError("channels must be a list of channel names (at most 8)")
        unknown = [name for name in wanted if name not in available]
        if unknown:
            raise ActionError("node %s has no channel(s) %s" % (node.fullName(), unknown), channels=available[:MAX_LIST])
        frame = args.get("frame")
        previous = nuke.frame()
        if frame is not None:
            frame = _as_int(frame, "frame")
            nuke.frame(frame)
        try:
            values = {name: round(float(node.sample(name, x, y, dx, dy)), 6) for name in wanted}
        finally:
            if frame is not None and int(nuke.frame()) == frame:
                nuke.frame(previous)
        return {
            "node": node.fullName(),
            "frame": frame if frame is not None else previous,
            "at": [x, y],
            "values": values,
            "graph_changed": False,
            "note": "pixel values are measurements, not a visual judgement; judge the image itself with render.",
        }

    # ---- viewer / render ----

    def _viewer(self):
        nuke = _nuke()
        window = nuke.activeViewer()
        if window is not None:
            try:
                node = window.node()
                if node is not None and node.Class() == "Viewer" and nuke.toNode(node.fullName()) == node:
                    return node, window
            except Exception:
                pass
        viewers = nuke.allNodes("Viewer", group=nuke.root(), recurseGroups=True)
        if len(viewers) == 1:
            return viewers[0], None
        if not viewers:
            return None, None
        raise ActionError(
            "no Viewer is active and several exist; click the Viewer panel to activate one",
            viewers=[item.fullName() for item in viewers],
        )

    def _show(self, node, index=0):
        """Connect the existing Viewer (or create the single one needed) to ``node`` and activate it."""
        nuke = _nuke()
        viewer, window = self._viewer()
        self.mutated = True
        if viewer is None:
            nuke.connectViewer(index, node)
            viewer, window = self._viewer()
            if viewer is None:
                raise ActionError("Nuke did not create a Viewer")
        else:
            viewer.setInput(index, node)
        self.touch(viewer.fullName())
        if window is not None:
            window.activateInput(index)
        if viewer.input(index) != node:
            raise ActionError("the Viewer input %d reads %r after connecting" % (index, viewer.input(index)))
        return viewer

    @staticmethod
    def _navigation(args):
        """Validated Viewer framing options from ``args`` ({} when none were given)."""
        from ..capture.widgets import normalize_viewer_navigation

        options = {key: args[key] for key in ("zoom", "center", "region") if args.get(key) is not None}
        try:
            normalize_viewer_navigation(**options)
        except ValueError as exc:
            raise ActionError(str(exc)) from exc
        return options

    def _do_view(self, args):
        node = self._node(args.get("node"))
        index = _as_int(args.get("input", 0), "input")
        if not 0 <= index <= 9:
            raise ActionError("Viewer inputs are 0-9")
        navigation = self._navigation(args)
        viewer = self._show(node, index)
        result = {"viewer": viewer.fullName(), "input": index, "shows": node.fullName(), "graph_changed": True}
        if navigation:
            from ..capture.widgets import CaptureError, apply_viewer_navigation, normalize_viewer_navigation

            viewer, window = self._viewer()
            try:
                result["navigation"] = apply_viewer_navigation(
                    viewer, window, normalize_viewer_navigation(**navigation)
                )
            except CaptureError as exc:
                raise ActionError("Viewer navigation failed: %s" % exc, graph_changed=True) from exc
        return result

    def _do_render(self, args):
        if self.capture is None:
            raise ActionError("render is unavailable: no capture channel")
        target = args.get("target", "viewer")
        if target not in ("viewer", "nodegraph"):
            raise ActionError("target must be 'viewer' or 'nodegraph'")
        result = {"graph_changed": False}
        navigation = self._navigation(args)
        if target == "nodegraph":
            if args.get("node") or args.get("frame") is not None or args.get("frames") or navigation:
                raise ActionError("target='nodegraph' takes no node, frame, zoom, center or region")
            capture = self._capture("nodegraph", scope="all")
            result.update(capture=capture, captures=[self._capture_note(capture)])
            return result
        frames = args.get("frames")
        if frames is not None and args.get("frame") is not None:
            raise ActionError("give frame or frames, not both")
        if frames is None:
            frames = [args.get("frame")]
        if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_FRAMES:
            raise ActionError("frames must be a list of 1-%d integers" % MAX_FRAMES)
        frames = [None if frame is None else _as_int(frame, "frame") for frame in frames]
        if len(set(frames)) != len(frames):
            raise ActionError("frames must be distinct")
        shown = None
        if args.get("node") is not None:
            node = self._node(args["node"])
            viewer = self._show(node, 0)
            shown = node.fullName()
            result["graph_changed"] = True
            result["viewer"] = viewer.fullName()
        captures = []
        for frame in frames:
            capture = self._capture("viewer", **({} if frame is None else {"frame": frame}), **navigation)
            captures.append(capture)
            if shown is not None and capture.get("viewer_input_node") not in (None, shown):
                raise ActionError(
                    "the Viewer rendered %s, not the requested %s; the image is not evidence of %s"
                    % (capture.get("viewer_input_node"), shown, shown),
                    graph_changed=True,
                )
        result.update(
            capture=captures[-1],
            captures=[self._capture_note(item) for item in captures],
            note="Look at the delivered image(s), then judge them in words (nuke_workflow review) or fix what you see.",
        )
        result["frames_captured"] = len(captures)
        return result

    def _capture(self, target, **options):
        try:
            capture = self.capture(target, **options)
        except Exception as exc:
            raise ActionError("render failed: %s: %s" % (type(exc).__name__, exc)) from exc
        if not isinstance(capture, dict) or not capture.get("success"):
            raise ActionError("render failed: %s" % ((capture or {}).get("error") or "no result"))
        if self.on_capture is not None:
            self.on_capture(capture)
        return capture

    @staticmethod
    def _capture_note(capture):
        return {
            key: capture.get(key)
            for key in (
                "evidence_id", "frame", "viewer", "viewer_input_node", "image_width", "image_height", "target",
                "viewer_zoom_percent", "requested_viewer_center", "requested_region",
                "viewer_source_format_width", "viewer_source_format_height", "viewer_image_matches_viewport",
            )
            if capture.get(key) is not None
        }

    # ---- node animation ----

    def _do_animate(self, args):
        nuke = _nuke()
        node = self._node(args.get("node"))
        knob = self._knob(node, args.get("knob"))
        if knob.Class() in _CODE_KNOB_CLASSES or knob.Class() in _DECORATIVE_CLASSES or knob.name() == "curves":
            raise ActionError("knob %s.%s cannot be keyed here" % (node.fullName(), knob.name()))
        keys = args.get("keys")
        if isinstance(keys, dict):
            keys = [{"frame": frame, "value": value} for frame, value in keys.items()]
        if not isinstance(keys, list) or not 1 <= len(keys) <= MAX_KEYS:
            raise ActionError('keys must be {"1": value, "100": value} or [{"frame": 1, "value": value}] (at most %d)' % MAX_KEYS)
        try:
            size = knob.arraySize()
        except Exception:
            size = 1
        parsed = []
        for entry in keys:
            if not isinstance(entry, dict) or set(entry) != {"frame", "value"}:
                raise ActionError("each key is {frame, value}")
            frame = entry["frame"]
            if isinstance(frame, str) and re.match(r"^-?\d+(\.\d+)?$", frame):
                frame = float(frame)
            frame = _as_number(frame, "key frame")
            value = entry["value"]
            values = list(value) if isinstance(value, (list, tuple)) else [value] * size if size > 1 else [value]
            if len(values) != size or not all(_is_number(item) for item in values):
                raise ActionError("%s.%s takes %d number(s) per key; got %r" % (node.fullName(), knob.name(), size, value))
            parsed.append((frame, [float(item) for item in values]))
        interpolation = args.get("interpolation")
        if interpolation is not None and interpolation not in _INTERPOLATIONS:
            raise ActionError("interpolation must be one of %s" % ", ".join(_INTERPOLATIONS))
        self.touch(node.fullName())
        self.mutated = True
        knob.setAnimated()
        for frame, values in parsed:
            for index, item in enumerate(values):
                knob.setValueAt(item, frame, index)
        if interpolation is not None:
            kind = getattr(nuke, _INTERPOLATIONS[interpolation])
            for curve in knob.animations():
                curve.changeInterpolation(curve.keys(), kind)
        problems = []
        for frame, values in parsed:
            for index, item in enumerate(values):
                actual = knob.getValueAt(frame, index) if size > 1 else knob.getValueAt(frame)
                if not _close(item, actual):
                    problems.append("frame %s[%d] reads %r (wanted %r)" % (frame, index, actual, item))
        if problems:
            raise ActionError("keys did not read back as set: " + "; ".join(problems[:4]))
        return {
            "node": node.fullName(),
            "knob": knob.name(),
            "keys": [{"frame": frame, "value": values if size > 1 else values[0]} for frame, values in parsed][:MAX_LIST],
            "key_count": len(parsed),
            "graph_changed": True,
        }

    # ---- Roto / RotoPaint shapes ----

    def _host(self, node_name):
        node = self._node(node_name)
        if node.Class() not in SHAPE_HOSTS:
            raise ActionError(
                "shapes are built in Roto or RotoPaint; %s is a %s" % (node.fullName(), node.Class()),
                use=list(SHAPE_HOSTS),
            )
        return node

    def _shape_names(self, node):
        try:
            return [element.name for element in _roto_elements(node["curves"].rootLayer)][:MAX_LIST]
        except Exception as exc:
            return ["unreadable: %s: %s" % (type(exc).__name__, exc)]

    def _shape_element(self, node, name):
        curves = node["curves"]
        for element in _roto_elements(curves.rootLayer):
            if element.name == name and type(element).__name__ == "Shape":
                return element
        raise ActionError(
            "no shape named %r in %s" % (name, node.fullName()), shapes=self._shape_names(node)
        )

    @staticmethod
    def _outline(kind, args):
        """Control points as (x, y, left_tangent, right_tangent) offsets for the requested kind."""
        if kind == "ellipse":
            cx, cy = _pair(args.get("center"), "center")
            sx, sy = _pair(args.get("size"), "size")
            if sx <= 0 or sy <= 0:
                raise ActionError("size must be positive [width, height]")
            rx, ry = sx / 2.0, sy / 2.0
            k = 0.5522847498
            # Bezier circle: four points, tangents along the outline (screen space, y up).
            return [
                (cx + rx, cy, (0.0, -ry * k), (0.0, ry * k)),
                (cx, cy + ry, (rx * k, 0.0), (-rx * k, 0.0)),
                (cx - rx, cy, (0.0, ry * k), (0.0, -ry * k)),
                (cx, cy - ry, (-rx * k, 0.0), (rx * k, 0.0)),
            ]
        if kind == "rectangle":
            cx, cy = _pair(args.get("center"), "center")
            sx, sy = _pair(args.get("size"), "size")
            if sx <= 0 or sy <= 0:
                raise ActionError("size must be positive [width, height]")
            hx, hy = sx / 2.0, sy / 2.0
            zero = (0.0, 0.0)
            return [(cx - hx, cy - hy, zero, zero), (cx - hx, cy + hy, zero, zero), (cx + hx, cy + hy, zero, zero), (cx + hx, cy - hy, zero, zero)]
        if kind == "polygon":
            points = args.get("points")
            if not isinstance(points, list) or not 3 <= len(points) <= 64:
                raise ActionError("polygon needs `points`: 3-64 [x, y] pairs")
            zero = (0.0, 0.0)
            return [(*_pair(point, "points[%d]" % index), zero, zero) for index, point in enumerate(points)]
        raise ActionError("kind must be ellipse, rectangle or polygon")

    def _do_shape(self, args):
        nuke = _nuke()
        import nuke.rotopaint as rotopaint

        node = self._host(args.get("node"))
        kind = args.get("kind")
        outline = self._outline(kind, args)
        curves = node["curves"]
        root = curves.rootLayer
        existing = {element.name for element in _roto_elements(root)}
        name = args.get("name") or None
        if name is None:
            index = 1
            while "%s%d" % (kind.capitalize(), index) in existing:
                index += 1
            name = "%s%d" % (kind.capitalize(), index)
        elif name in existing:
            raise ActionError("a shape or layer named %r already exists" % name, shapes=self._shape_names(node))
        closed = args.get("closed", True)
        if not isinstance(closed, bool):
            raise ActionError("closed must be true or false")
        self.touch(node.fullName())
        self.mutated = True
        shape = rotopaint.Shape(curves)
        shape.name = name
        for x, y, _left, _right in outline:
            shape.append((x, y))
        frame = nuke.frame()
        for index, (x, y, left, right) in enumerate(outline):
            point = shape[index]
            # The feather outline has its own tangents (offsets from the feather centre); left at zero the
            # feather curve stays a straight-edged polygon that renders as a diamond inside the true outline.
            if left != (0.0, 0.0):
                point.leftTangent.setPosition((left[0], left[1], 0.0))
                point.featherLeftTangent.setPosition((left[0], left[1], 0.0))
            if right != (0.0, 0.0):
                point.rightTangent.setPosition((right[0], right[1], 0.0))
                point.featherRightTangent.setPosition((right[0], right[1], 0.0))
        shape.setFlag(rotopaint.FlagType.eOpenFlag, not closed)
        root.append(shape)
        curves.changed()
        problems = self._verify_outline(self._shape_element(node, name), outline, frame, len(outline))
        if problems:
            raise ActionError(
                "the shape %s was added to %s but does not read back as requested: %s. It was NOT removed; "
                "inspect it or delete it with internal_python." % (name, node.fullName(), "; ".join(problems[:3])),
                graph_changed=True,
            )
        return {
            "node": node.fullName(),
            "shape": name,
            "kind": kind,
            "points": len(outline),
            "closed": closed,
            "note": "Roto draws into its output channels (default alpha); set output to rgba and use shape_style for colour.",
            "graph_changed": True,
        }

    @staticmethod
    def _verify_outline(shape, outline, frame, count):
        problems = []
        if len(shape) != count:
            return ["%d control points read back, expected %d" % (len(shape), count)]
        for index, (x, y, left, right) in enumerate(outline):
            point = shape[index]
            centre = point.center.getPosition(frame)
            if not (_close(x, centre.x) and _close(y, centre.y)):
                problems.append("point %d centre reads (%.3f, %.3f), expected (%.3f, %.3f)" % (index, centre.x, centre.y, x, y))
            for label, expected, part in (
                ("left", left, point.leftTangent),
                ("right", right, point.rightTangent),
                ("feather left", left, point.featherLeftTangent),
                ("feather right", right, point.featherRightTangent),
            ):
                actual = part.getPosition(frame)
                if not (_close(expected[0], actual.x) and _close(expected[1], actual.y)):
                    problems.append(
                        "point %d %s tangent reads (%.3f, %.3f), expected (%.3f, %.3f)"
                        % (index, label, actual.x, actual.y, expected[0], expected[1])
                    )
        return problems

    def _do_shape_style(self, args):
        nuke = _nuke()
        import nuke.rotopaint as rotopaint

        node = self._host(args.get("node"))
        shape = self._shape_element(node, args.get("shape"))
        attributes = shape.getAttributes()
        wanted = {}
        color = args.get("color")
        if color is not None:
            if not isinstance(color, list) or len(color) not in (3, 4) or not all(_is_number(item) for item in color):
                raise ActionError("color must be [r, g, b] or [r, g, b, a]")
            wanted[rotopaint.AnimAttributes.kRedAttribute] = float(color[0])
            wanted[rotopaint.AnimAttributes.kGreenAttribute] = float(color[1])
            wanted[rotopaint.AnimAttributes.kBlueAttribute] = float(color[2])
            if len(color) == 4:
                wanted[rotopaint.AnimAttributes.kAlphaAttribute] = float(color[3])
        if args.get("opacity") is not None:
            wanted[rotopaint.AnimAttributes.kOpacityAttribute] = _as_number(args["opacity"], "opacity")
        if args.get("feather") is not None:
            wanted[rotopaint.AnimAttributes.kFeatherXAttribute] = _as_number(args["feather"], "feather")
            wanted[rotopaint.AnimAttributes.kFeatherYAttribute] = _as_number(args["feather"], "feather")
        if not wanted:
            raise ActionError("shape_style needs color, opacity or feather")
        frame = float(nuke.frame())
        self.touch(node.fullName())
        self.mutated = True
        for attribute, value in wanted.items():
            attributes.set(frame, attribute, value)
        node["curves"].changed()
        problems = []
        for attribute, value in wanted.items():
            actual = attributes.getValue(frame, attribute)
            if not _close(value, actual):
                problems.append("%s reads %r (wanted %r)" % (attribute, actual, value))
        if problems:
            raise ActionError("shape style did not read back as set: " + "; ".join(problems), graph_changed=True)
        return {"node": node.fullName(), "shape": shape.name, "style": {str(k): v for k, v in wanted.items()}, "graph_changed": True}

    def _do_shape_key(self, args):
        node = self._host(args.get("node"))
        shape = self._shape_element(node, args.get("shape"))
        keys = args.get("keys")
        if isinstance(keys, dict):
            keys = [{"frame": frame, "translate": value} for frame, value in keys.items()]
        if not isinstance(keys, list) or not 1 <= len(keys) <= MAX_KEYS:
            raise ActionError('keys must be {"1": [x, y], "50": [x, y]} or [{"frame": 1, "translate": [x, y]}]')
        parsed = []
        for entry in keys:
            if not isinstance(entry, dict) or set(entry) != {"frame", "translate"}:
                raise ActionError("each key is {frame, translate: [x, y]} (translation offset from the drawn position)")
            frame = entry["frame"]
            if isinstance(frame, str) and re.match(r"^-?\d+(\.\d+)?$", frame):
                frame = float(frame)
            parsed.append((_as_number(frame, "key frame"), *_pair(entry["translate"], "translate")))
        transform = shape.getTransform()
        self.touch(node.fullName())
        self.mutated = True
        for frame, x, y in parsed:
            transform.addTranslationKey(frame, x, y, 0.0)
        node["curves"].changed()
        problems = []
        for frame, x, y in parsed:
            actual = (transform.getTranslationAnimCurve(0).evaluate(frame), transform.getTranslationAnimCurve(1).evaluate(frame))
            if not (_close(x, actual[0]) and _close(y, actual[1])):
                problems.append("frame %s reads (%.3f, %.3f), wanted (%.3f, %.3f)" % (frame, actual[0], actual[1], x, y))
        if problems:
            raise ActionError("shape keys did not read back as set: " + "; ".join(problems[:4]), graph_changed=True)
        return {
            "node": node.fullName(),
            "shape": shape.name,
            "keys": [{"frame": frame, "translate": [x, y]} for frame, x, y in parsed][:MAX_LIST],
            "key_count": len(parsed),
            "graph_changed": True,
        }

    # ---- python with a node bound ----

    def _do_internal_python(self, args):
        """Unrestricted Python with ``node`` (and rp/curves/root_layer for Roto hosts) pre-bound.

        A convenience only: the code may create, delete, rewire or edit anything, exactly as in
        execute_python. Whatever it changed is reported, never refused, undone or flagged.
        """
        nuke = _nuke()
        from contextlib import redirect_stderr, redirect_stdout
        import io
        import traceback

        from .api_errors import ApiErrorTracker, SourceRegistry
        from .python_executor import diff_snapshots, graph_snapshot
        from .script_run import (
            compile_script,
            failure_report,
            not_run_graph_fields,
            PreflightError,
            rejected_report,
            run_compiled,
        )

        node = self._node(args.get("node"))
        code = args.get("code")
        if not isinstance(code, str) or not code.strip() or len(code) > MAX_CODE:
            raise ActionError("code must be Python source of at most %d characters" % MAX_CODE)
        sources = SourceRegistry()
        try:
            units = compile_script(code, sources, split_last_expression=False)
        except PreflightError as rejected:
            # Nothing ran: no undo group, no touched node, no graph change.
            return {
                "node": node.fullName(),
                "success": False,
                "stdout": "",
                "stderr": "",
                "result": None,
                "api_errors": [],
                **rejected_report(rejected, code),
                **not_run_graph_fields(),
            }
        before = graph_snapshot()
        scope = {"nuke": nuke, "node": node, "__builtins__": __builtins__}
        if node.Class() in SHAPE_HOSTS:
            import nuke.rotopaint as rotopaint

            scope.update(rp=rotopaint, curves=node["curves"], root_layer=node["curves"].rootLayer)
        tracker = ApiErrorTracker(scope, sources)
        stdout, stderr = io.StringIO(), io.StringIO()
        error = None
        running = False
        trace = None
        caught = None
        label = str(args.get("label") or "Codex node Python")[:60]
        self.touch(node.fullName())
        self.mutated = True
        undo_open = False
        try:
            nuke.Undo.begin(label)
            undo_open = True
            running = True
            with redirect_stdout(stdout), redirect_stderr(stderr), tracker:
                run_compiled(units, scope)
        except BaseException as exc:
            caught = exc
            error = "%s: %s" % (type(exc).__name__, exc)
            trace = traceback.format_exc()[-MAX_OUTPUT:]
        finally:
            if undo_open:
                nuke.Undo.end()
        failure = None
        if caught is not None:
            failure = failure_report(
                caught,
                scope,
                sources,
                executed=running,
                undo_note=(
                    "the changes made before the failure are recorded as one undo group %r; it was not undone" % label
                    if running
                    else None
                ),
            )
        diff = diff_snapshots(before, graph_snapshot())
        changed = [*diff["added_nodes"], *diff["removed_nodes"], *diff["modified_nodes"]]
        for name in changed:
            self.touch(name)
        fields = tracker.response_fields(caught)
        result = {
            "node": node.fullName(),
            "stdout": stdout.getvalue()[-MAX_OUTPUT:],
            "stderr": stderr.getvalue()[-MAX_OUTPUT:],
            "graph_changed": diff["graph_changed"],
            "api_errors": fields.get("api_errors") or [],
            "success": True,
        }
        result["result"] = _plain(scope.get("result"))
        for name in ("api_errors_omitted", "api_error_tracking_failures"):
            if name in fields:
                result[name] = fields[name]
        if error is not None:
            result.update(success=False, error=error, traceback=trace, failure=failure)
        elif diff["node_errors"]:
            result.update(success=False, error="a node reports an error after the code ran", node_errors=diff["node_errors"])
        return result
