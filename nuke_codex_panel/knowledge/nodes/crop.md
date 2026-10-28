---
id: "nodes/crop"
kind: "node"
title: "Crop"
category: "geometry-2d"
summary: "Cuts an image to a box with optional softness, reformatting, and black outside area."
aliases: ["Crop node", "bounding box", "cut image"]
tags: ["crop", "bbox", "format", "edge"]
requires: ["fundamentals/coordinates"]
related: ["nodes/reformat", "nodes/transform"]
nodes: ["Crop"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Crop

## Purpose
Source-documented: removes unwanted portions of an image area. You may fill cropped areas with black or change output format to match the crop.

## Inputs
One unnamed image input.

## Controls
Documented knobs: box (x, y, r, t); softness (default 0); reformat; intersect; black outside -> `crop` (default enabled). Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View the bounding box/format and cropped area; check that softness does not erode intended alpha; confirm effect on downstream bounding boxes. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: UI label black outside maps to scripting name `crop`, a name that can mislead. Cropping reduces bounding boxes and affects downstream processing but is not always the same as reformatting.
Foundry's concatenation guide states Crop does not concatenate and breaks a Transform chain. Place a required Crop after the compatible Transform/Reformat/CornerPin run, near the Merge, or use the Merge B-side bbox instead. Do not casually crop away edges earlier transforms or filters need. Crop to the comp window just before the Merge is a studio preference (`fundamentals/quality-safeguards`); it does not make upstream work cheaper.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/crop.html
- How Nodes Concatenate: https://learn.foundry.com/nuke/17.1/content/comp_environment/transforming_elements/node_concatenation.html
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): Crop placement.
