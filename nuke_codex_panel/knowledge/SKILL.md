---
id: "overview"
kind: "router"
title: "Nuke compositing knowledge router"
category: "router"
summary: "Routes a Nuke compositing task to the few packaged fundamentals, topics and node references it needs, retrieved on demand through the knowledge tools."
aliases: ["nuke compositing", "compositing knowledge", "which guidance do I need"]
tags: ["router", "compositing", "nuke"]
requires: []
related: ["fundamentals/graph-conventions", "fundamentals/quality-safeguards", "fundamentals/keying-conventions", "fundamentals/node-selection", "fundamentals/alpha-premultiplication", "fundamentals/color-spaces", "fundamentals/channels-data"]
nodes: []
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions"]
name: "nuke-compositing"
description: "Use before building or changing a Nuke node graph, to retrieve targeted compositing guidance (keying, roto, color, 3D, tracking, retiming) instead of guessing."
---
# Nuke compositing knowledge router

## Applicability
Before building, organizing or keying a Nuke graph (even with familiar nodes), load the applicable studio conventions first; before an unfamiliar or consequential operation, retrieve the one or two documents that fit it. The pack is packaged and read-only; it works with Nuke closed and never replaces inspecting the live script. Conventions are studio preferences, not Foundry facts.

## Workflow
1. Name the task and its inputs: footage colour state, alpha state, channels, frame range, 2D or 3D.
2. Load conventions for the scope with `get_compositing_guidance(id, section="workflow")` (the default `overview` has no rules): `fundamentals/graph-conventions` and `fundamentals/quality-safeguards` for any graph construction or organization or comp; also `fundamentals/keying-conventions` for keying. Read `pitfalls` as needed. Skip them for tasks that touch no graph.
3. Search: `search_compositing_knowledge(query, kind)`. Use `kind: "topic"` for tasks, `"fundamental"` for prerequisites, `"node"` for a node.
4. Read the chosen document: `get_compositing_guidance(id, section)` or `get_node_reference(node, section)`. Start with `overview`, then `workflow`, `verify` or `pitfalls` as needed.
5. Follow the returned `requires` IDs only when that prerequisite is in doubt for this task.
6. Inspect the live graph, then act. Node references describe documented 17.1 behaviour, so confirm the class exists in the installed build.

## Route by prerequisite
- Building, organizing or compositing a graph: `fundamentals/graph-conventions`, `fundamentals/quality-safeguards`.
- Keying or assembling mattes: `fundamentals/keying-conventions`.
- Merging, keying, edge fringes, CG renders: `fundamentals/alpha-premultiplication`.
- Grading, file input/output, display: `fundamentals/color-spaces`.
- Passes, depth, masks, utility data: `fundamentals/channels-data`.
- Transforms, formats, bounding boxes, UVs: `fundamentals/coordinates`.
- Scaling, rotating, stacked transforms, sharpness: `fundamentals/filtering-concatenation`.
- Retiming, offsets, motion blur, frame ranges: `fundamentals/time-sampling`.
- Choosing between nodes, or replacing one with an expression: `fundamentals/node-selection`.

## Verify
Each task you route has reached a document, or you recorded that search returned nothing relevant.

## Pitfalls
- Loading every topic wastes context; fetch only the section you will use.
- A retrieved recipe is a starting hypothesis; the shot's actual data decides.

## Sources
- Nuke 17.1 reference guide: https://learn.foundry.com/nuke/17.1/content/reference_guide.html
- Brinkmann, The Art and Science of Digital Compositing, 2nd ed. (2008), as theory.
- Teacher-supplied Nuke production conventions (`studio-conventions`, 2026-10-28): project preferences.
