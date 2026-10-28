---
id: "nodes/reformat"
kind: "node"
title: "Reformat"
category: "geometry-2d"
summary: "Resizes and repositions an image into a target format using resize and aspect-ratio controls."
aliases: ["Reformat node", "resize", "change format", "pixel aspect"]
tags: ["format", "resize", "resolution", "aspect"]
requires: ["fundamentals/coordinates", "fundamentals/filtering-concatenation"]
related: ["nodes/crop", "nodes/read", "nodes/transform"]
nodes: ["Reformat"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Reformat

## Purpose
Source-documented: lets plates of varying resolution coexist in one script. The page recommends Reformat after each Read to set at least output resolution.

## Inputs
One unnamed image input.

## Controls
Documented knobs: type (default to format); format (default root.format); box_width, box_height, box_fixed, box_pixel_aspect; scale; resize (default width); center; flip; flop; turn; filter (default Cubic); clamp; black_outside (default enabled); preserve bounding box -> `pbb` (default disabled). Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Verify the output format and pixel aspect ratio, check edges and overscan, and confirm the format at the Viewer. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: choose resize type deliberately; distortion happens when the target aspect differs. Reformatting data layers uses filtering, which may be unsuitable for non-colour data.
Foundry's concatenation guide lists Reformat among concatenating nodes; settings and direction still matter. Format metadata alone does not clip, but Reformat's `pbb` (preserve bounding box, default off) clips pixels outside the output format; enabling it keeps overscan. If later Transform/CornerPin work needs pixels beyond the frame, inspect and set `pbb` accordingly until the final containment step (Merge B-side bbox, a separate studio policy; `fundamentals/quality-safeguards`). Reformat's output format is root.format only by default; an explicit format, box or scale overrides it. Inspect each actual input's format rather than assuming a wrong root breaks a correct plate branch or that changing root fixes mismatched inputs.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/reformat.html
- How Nodes Concatenate: https://learn.foundry.com/nuke/17.1/content/comp_environment/transforming_elements/node_concatenation.html
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): root format first.
