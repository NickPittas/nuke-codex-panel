---
id: "nodes/transform"
kind: "node"
title: "Transform"
category: "geometry-2d"
summary: "2D translation, rotation, scale and skew with filter, motion blur and bounding-box-related controls."
aliases: ["Transform node", "2D transform", "translate rotate scale"]
tags: ["transform", "2d", "translate", "scale", "filtering"]
requires: ["fundamentals/coordinates", "fundamentals/filtering-concatenation"]
related: ["nodes/cornerpin", "nodes/reformat", "nodes/tracker"]
nodes: ["Transform"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Transform

## Purpose
Source-documented: translates, rotates, scales and skews from one control panel. Created with T. See TransformMasked for the masked variant.

## Inputs
One unnamed image input; no mask input is documented.

## Controls
Documented knobs: translate; rotate; scale; skewX, skewY; skew_order; center; invert_matrix; filter (default Cubic); clamp; black_outside (default enabled); motionblur; shutter; shutteroffset. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Check pivot and filtering, view edges, compare against a reference frame, and animate under keyframes carefully. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: filter choice affects softness and ringing; concatenation applies only through compatible adjacent transforms (see the fundamental). Clamp helps sharpening filters, but changes data.
Foundry's concatenation guide lists Transform among concatenating nodes, but node generation, settings and direction matter, and Crop or colour nodes break the chain. Studio preference: place a required Crop after the compatible transform run near the Merge. Large scales or moves can create huge bboxes; check all relevant frames (`fundamentals/quality-safeguards`).

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/transform.html
- How Nodes Concatenate: https://learn.foundry.com/nuke/17.1/content/comp_environment/transforming_elements/node_concatenation.html
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): Crop placement and bbox checks.
