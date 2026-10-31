---
id: "fundamentals/node-selection"
kind: "fundamental"
title: "Choosing native nodes versus expressions"
category: "fundamentals"
summary: "How to pick the purpose-built Nuke node, when an expression or Python is justified, and how to inspect the live script and verify RGB, alpha and time before and after."
aliases: ["native node", "which node", "expression instead of node", "Roto vs expression", "CheckerBoard vs expression", "inspect before editing", "node choice"]
tags: ["nodes", "native-first", "expression", "roto", "checkerboard", "verification"]
requires: []
related: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data", "fundamentals/time-sampling", "topics/node-graphs", "topics/rotoscoping-masking"]
nodes: ["Roto", "RotoPaint", "CheckerBoard", "Merge", "Viewer"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Choosing native nodes versus expressions

## Applicability
Use whenever a request could be met by a purpose-built node or by an expression, Expression node, or Python-generated pixels: shapes and mattes, test patterns, gradients, colour operations, transforms. General native-first is a preference grounded in editability and documented behaviour, not a ban. Shape creation is the exception: required studio rule below.

## Workflow
0. Required studio rule (user/teacher policy, not a Foundry fact; supersedes the general preference wording for shapes): ALL shape creation starts with Roto or RotoPaint as the first source, whether drawn by hand or a built-in preset: circles, ovals, lines, rectangles, custom paths, motion-graphics shapes. Either node may hold pure vector shapes with no paint; RotoPaint is optionally preferred when paint is also wanted, not a condition. Draw inside the node with its Ellipse, Rectangle and spline tools. Do not invent a standalone Circle/Ellipse/Line node, and do not default to generators, Expression or Python pixel math for shapes. Nuke generators remain valid for non-shape needs; only deviate when the user asks.
1. Inspect first: read the existing graph, selected nodes, channels, ranges, formats and the installed node classes. Do not assume a node, knob name, or licence exists because 17.1 documentation lists it.
2. State the needed output: image, alpha matte, data channel, or geometry, and whether it must be animated, tracked, edited by an artist, or keyed in time.
3. Prefer the node an artist would reach for. Shapes: Roto per rule 0 (Roto renders shapes into alpha by default, with shape tools, feather, lifetime and keyframable splines); RotoPaint adds paint tools when needed. A checker pattern is CheckerBoard (documented as a placeholder for texture or background, with box size, colours and lines controls).
4. Accept an expression or script when it is actually better: data no node generates, a computed value that must stay linked to other controls, a per-pixel formula with no equivalent node, bulk construction of many identical nodes, or a requirement the native node cannot meet. Say why, keep it small, and name it clearly.
5. Wire by role, not by position: Merge A is the foreground, B the background, mask is optional; set the channel menus explicitly; keep alpha state in mind.
6. Check the result with the Viewer: RGB, then alpha, then channels you routed, at several frames.

## Verify
- Alpha viewed alone matches the intended coverage; RGB over a contrast background shows no edge artifacts.
- The result holds at head, middle and tail frames and after a Viewer or cache refresh.
- A new node exists in the installed build and has the knobs you set; read them back.
- An artist can open the node and edit it; an expression replacement for an existing native node needs a stated reason.

## Pitfalls
- Replacing an existing Roto or CheckerBoard with an expression removes shape editing, keyframes and tool support; keep the native node unless asked otherwise. Shapes built from Expression, generators or pixel math instead of Roto/RotoPaint violate the studio rule.
- Nodes may offer legacy and newer variants; confirm which one is in the script before connecting.
- A node's default output channel or premultiply setting may not match your intent (Roto defaults to alpha and a none premultiply control).
- Doc examples are cues, not validated shot recipes; confirm against the real plate.
- Organisation is also native-first: use Dot, Backdrop and (with a real upstream input) PostageStamp (`nodes/dot`, `nodes/backdrop`, `nodes/postagestamp`) rather than scripted layout tricks. Studio layout preference, not a Nuke rule: `fundamentals/graph-conventions`.

## Sources
- Roto: https://learn.foundry.com/nuke/17.1/content/reference_guide/draw_nodes/roto.html
- CheckerBoard: https://learn.foundry.com/nuke/content/reference_guide/image_nodes/checkerboard.html
- Merge: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/merge.html
- Viewer: https://learn.foundry.com/nuke/content/reference_guide/image_nodes/viewer.html
- Studio conventions (teacher-supplied, 2026-10-28; updated 2026-10-29 with the Roto/RotoPaint-first shape rule; project requirements, not universal Nuke facts): native organisation nodes and layout; all shape creation starts in Roto/RotoPaint.
