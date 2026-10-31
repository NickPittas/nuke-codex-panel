"""Structured, compact context from the active Nuke session."""

from __future__ import annotations

ROOT_GROUP = "root"


def _source_names(node):
    """Positional input sources by full name; None marks a gap. Trailing free slots are omitted."""
    sources = []
    for index in range(node.inputs()):
        source = node.input(index)
        sources.append(source.fullName() if source is not None else None)
    return sources


def _knob_value(node, name):
    """Knob value, or None when the knob is absent or unreadable on this Nuke."""
    try:
        return node[name].value()
    except Exception:
        return None


def _node_summary(node):
    sources = _source_names(node)
    name = node.fullName()
    try:
        slots = node.maxInputs()
    except Exception:
        slots = None
    return {
        "name": name,
        "class": node.Class(),
        # Enclosing group's full name ("root" at the top level); nested nodes are
        # also addressable through their dotted full name.
        "group": name.rpartition(".")[0] or ROOT_GROUP,
        "x": node.xpos(),
        "y": node.ypos(),
        "selected": bool(node["selected"].value()) if "selected" in node.knobs() else False,
        # Positional, with None for unconnected gaps (existing key, unchanged).
        "inputs": sources,
        # Explicit index -> source, and the total number of input pipes the node has,
        # so an unconnected trailing slot (e.g. a Merge mask) is distinguishable from absent.
        "connected_inputs": {str(index): source for index, source in enumerate(sources) if source is not None},
        "input_slots": slots,
    }


def _project(root):
    fmt = root.format()
    return {
        "format_name": fmt.name(),
        "width": fmt.width(),
        "height": fmt.height(),
        "pixel_aspect": fmt.pixelAspect(),
        "fps": root.fps(),
        "first_frame": root.firstFrame(),
        "last_frame": root.lastFrame(),
        "lock_range": _knob_value(root, "lock_range"),
        "proxy": _knob_value(root, "proxy"),
        "color_management": _knob_value(root, "colorManagement"),
        "ocio_config": _knob_value(root, "OCIO_config"),
    }


def _active_viewer():
    """What the active Viewer window actually shows, or None when no Viewer window is active."""
    import nuke

    window = nuke.activeViewer()
    if window is None:
        return None
    node = window.node()

    def wired(index):
        if index is None:
            return None
        source = node.input(index)
        return source.fullName() if source is not None else None

    try:
        primary = window.activeInput()
    except Exception:
        primary = None
    try:
        wipe = window.activeInput(True)
    except Exception:
        wipe = None
    return {
        "name": node.fullName(),
        "active_input": primary,
        "active_input_node": wired(primary),
        "wipe_input": wipe,
        "wipe_input_node": wired(wipe),
        "viewer_process": _knob_value(node, "viewerProcess"),
        "inputs": _source_names(node),
    }


def get_context(include_nodes: bool = True) -> dict:
    import nuke

    root = nuke.root()
    selected = [node.fullName() for node in nuke.selectedNodes()]
    # Root-anchored so the answer never depends on which group is the current Python context.
    viewers = [node.fullName() for node in nuke.allNodes("Viewer", group=root, recurseGroups=True)]
    context = {
        "nuke_version": nuke.NUKE_VERSION_STRING,
        "gui": bool(nuke.GUI),
        "script": root.name(),
        "modified": bool(root.modified()),
        "frame": nuke.frame(),
        "frame_range": [root.firstFrame(), root.lastFrame()],
        "fps": root.fps(),
        "format": root.format().name(),
        "project": _project(root),
        "selected_nodes": selected,
        "viewers": viewers,
        "active_viewer": _active_viewer(),
    }
    if include_nodes:
        context["nodes"] = [
            _node_summary(node) for node in nuke.allNodes(group=root, recurseGroups=True)
        ]
    return context
