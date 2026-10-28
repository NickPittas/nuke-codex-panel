---
id: "nodes/cornerpin"
kind: "node"
title: "CornerPin2D"
category: "tracking"
summary: "Maps four corners to or from tracked positions to replace a four-corner feature with another image."
aliases: ["CornerPin2D", "corner pin", "screen replacement", "cornerpin"]
tags: ["tracking", "corner", "replace", "perspective"]
requires: ["fundamentals/coordinates", "fundamentals/filtering-concatenation"]
related: ["nodes/tracker", "nodes/planartracker", "nodes/transform"]
nodes: ["CornerPin2D"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# CornerPin2D

## Purpose
Source-documented: designed to map the four corners of an image sequence to or from tracked data. It requires four tracks from Tracker, one per corner. The documented node is CornerPin2D; no node literally named CornerPin has a reference page.

## Inputs
One unnamed image input: the image that replaces the feature. It should not be connected to the Tracker node or the Tracker's input image.

## Controls
Documented knobs: to1-to4 with enable1-enable4. Pin 1 is bottom left, pin 2 bottom right, pin 3 top right, and pin 4 top left. Matching from controls also exist. Create it with the input selected so to/from populate; unconnected creation uses root format values. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Compare against the target in several frames, check corners at keyframe drift, and view edge filtering and bounding box. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: absolute vs relative export has different behaviour on the PlanarTracker CornerPin dropdown. Unconnected creation can give wrong from points.
Foundry's concatenation guide lists CornerPin among concatenating nodes; settings and direction matter. A corner pin with extreme corners can produce a very large bbox and memory use even when the Merge later clips it: check all relevant frames and contain to the background window before the Merge (studio preference, `fundamentals/quality-safeguards`). Place any Crop after the pin run.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/cornerpin2d.html
- How Nodes Concatenate: https://learn.foundry.com/nuke/17.1/content/comp_environment/transforming_elements/node_concatenation.html
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): bbox checks.
