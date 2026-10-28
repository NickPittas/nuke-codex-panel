---
id: "topics/interface-navigation"
kind: "topic"
title: "Navigating the Nuke interface"
category: "interface"
summary: "How to move around the Node Graph, Viewer and timeline, read the Viewer's format/bbox/pixel info, and inspect channels without altering the composite."
aliases: ["pan zoom node graph", "viewer controls", "timeline playback range", "find node in script", "bookmark node", "view alpha"]
tags: ["viewer", "node graph", "timeline", "navigation", "hotkeys", "inspection"]
requires: ["fundamentals/node-selection", "fundamentals/channels-data"]
related: ["topics/node-graphs", "topics/interface-keyframes", "topics/channels", "nodes/dot", "nodes/backdrop", "fundamentals/graph-conventions"]
nodes: ["Viewer", "Dot", "Backdrop"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions", "lesson-01"]
---
# Navigating the Nuke interface

## Applicability
Use when orienting in an unfamiliar script, checking what a node actually outputs, or changing the frame/playback range. This is navigation and inspection only; building and wiring nodes is `topics/node-graphs`, and setting or editing keys is `topics/interface-keyframes`. Shortcuts below are the Nuke 17.1 documentation defaults. A studio or user `menu.py` can rebind them, and on Linux window managers Alt+drag may be captured by the desktop. When a shortcut fails, use the menu item named alongside it: Nuke menus show the live binding.

## Workflow
1. **Node Graph view.** Pan with middle-mouse drag (or Alt+drag), or drag the pink rectangle of the navigator map. Zoom with + / - over the target area, or Alt plus middle-drag. Press F with nodes selected to fit them; with nothing selected, F fits the whole tree.
2. **Jump in large scripts.** Search with Edit > Search (`/`); the field takes regular expressions, so `(Read|Write)` selects both kinds, and repeating the search steps through matches. For recurring destinations, tick *bookmark* on the node's Node tab (Backdrops are bookmarked by default), then press `J` and type the name. Pan/zoom locations can be saved with Ctrl/Cmd+F7..F10 and restored with Shift+F7..F10, but they are temporary, not stored in the script, and not shared between Node Graphs.
3. **Inspect a node.** Select it and press `I` for its information window. Reading the node's channel indicator (wide bars = processed, thin bars = passed through) and its mask, animation, expression and disabled indicators explains most surprises before opening any panel.
4. **Viewer timeline.** Drag the orange marker or type a frame; the field accepts relative values such as `+20`. The frame-range source menu offers *Global* (Project Settings range), *Input* (the connected clip's range) or *Custom*; locking the playback range stops later panning from altering it. Alt+G opens Go to frame.
5. **Channel and matte inspection.** R, G, B, A show single channels; press again to return. The layer and channel menus change which layer and which channel the A key shows. M overlays alpha in red on the RGB. Shift while choosing a channel affects only the active Viewer input, which lets input 1 show RGB and input 2 show alpha.
6. **Read the info bar.** It reports image resolution, bounding-box size and pixel values. Ctrl/Cmd+click samples one Viewer pixel; Ctrl/Cmd+Alt+click samples the node's input rather than the displayed output.

## Verify
- The Viewer input number and the node you intended to view match; check the format and bbox values in the info bar at that node, not at the script's end.
- Gain, gamma and saturation sliders change only display; before sampling or judging a matte, return them to defaults or note the offset.
- After changing frame range, confirm in/out frames in the timeline match the intended clip, and that Viewers are locked or unlocked as expected.

## Pitfalls
- Viewer display adjustments are not part of the render; do not bake judgments taken with a boosted gain into node values.
- Pausing Viewer update holds an old frame; refresh with `U` while paused.
- A saved navigator location from one Node Graph does not restore in another.
- Brinkmann's Chapter 9 discusses timelines and image viewing/analysis tools in general terms; the concrete Nuke controls and shortcuts above come from the Foundry pages.
- Navigation aids only help if named: label each Backdrop for its section (plate prep, each A branch, key, 3D/projection) so `J` lands on it. Studio layout preference: `fundamentals/graph-conventions`.
- Check format and bbox at the node under inspection, not only at the Viewer end of the tree; a huge bbox after CornerPin/Transform shows in the info bar first (`fundamentals/quality-safeguards`).
- Course practice (lesson-01, teacher demonstration): a Viewer shows only the node its active input is wired to, so after adding a blur or grade move the Viewer input to that node before judging it; do not conclude from the end-of-tree view. A file dragged into the graph becomes a Read with the format usually auto-detected, but confirm the format in the info bar rather than trusting detection. Shortcut and layout claims stay governed by the 17.1 pages above.

## Sources
- Foundry Nuke 17.1, Navigating Inside the Node Graph: https://learn.foundry.com/nuke/17.1/content/getting_started/using_interface/navigating_node_graph.html
- Foundry Nuke 17.1, Using the Viewer Controls: https://learn.foundry.com/nuke/17.1/content/getting_started/using_interface/using_viewer_controls.html
- Foundry Nuke 17.1, Working with Nodes (node information, indicators): https://learn.foundry.com/nuke/17.1/content/getting_started/using_interface/working_nodes.html
- Brinkmann, The Art and Science of Digital Compositing 2e, Chapter 9 Interface Interactions (Timelines; Image Viewing and Analysis Tools).
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): see `fundamentals/graph-conventions`.
- Lesson 01 Final.srt (lesson-01, ASR transcript, teaching-practice only): 00:01:42–00:02:42 Viewer shows the connected node's output; 00:33:50–00:34:47 dragging a file creates a Read, format usually auto-detected.
