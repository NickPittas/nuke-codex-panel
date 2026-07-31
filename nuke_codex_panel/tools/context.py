"""Structured, compact context from the active Nuke session."""

from __future__ import annotations


def _node_summary(node):
    inputs = []
    for index in range(node.inputs()):
        source = node.input(index)
        inputs.append(source.fullName() if source is not None else None)
    return {
        "name": node.fullName(),
        "class": node.Class(),
        "x": node.xpos(),
        "y": node.ypos(),
        "selected": bool(node["selected"].value()) if "selected" in node.knobs() else False,
        "inputs": inputs,
    }


def get_context(include_nodes: bool = True) -> dict:
    import nuke

    root = nuke.root()
    selected = [node.fullName() for node in nuke.selectedNodes()]
    viewers = [node.fullName() for node in nuke.allNodes("Viewer", recurseGroups=True)]
    context = {
        "nuke_version": nuke.NUKE_VERSION_STRING,
        "gui": bool(nuke.GUI),
        "script": root.name(),
        "modified": bool(root.modified()),
        "frame": nuke.frame(),
        "frame_range": [root.firstFrame(), root.lastFrame()],
        "fps": root.fps(),
        "format": root.format().name(),
        "selected_nodes": selected,
        "viewers": viewers,
    }
    if include_nodes:
        context["nodes"] = [
            _node_summary(node) for node in nuke.allNodes(recurseGroups=True)
        ]
    return context
