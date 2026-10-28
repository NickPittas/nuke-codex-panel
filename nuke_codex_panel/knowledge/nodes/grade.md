---
id: "nodes/grade"
kind: "node"
title: "Grade"
category: "color"
summary: "Black/white-point mapping plus lift, gain, multiply, offset and gamma for tonal and plate-matching adjustments."
aliases: ["Grade node", "lift gain gamma", "black point white point", "match plates"]
tags: ["grade", "levels", "color", "tonal"]
requires: ["fundamentals/color-spaces", "fundamentals/alpha-premultiplication"]
related: ["nodes/colorcorrect", "nodes/unpremult"]
nodes: ["Grade"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Grade

## Purpose
Source-documented: define white and black points by sampling pixels from the Viewer, useful for punch on overexposed images and for matching foreground to background plates. Created with G.

## Inputs
Unnamed image input and optional mask. By default the correction is limited to non-black mask areas.

## Controls
Documented knobs: channels (default rgb); blackpoint (0); whitepoint (1); lift -> `black`; gain -> `white`; multiply (1); offset -> `add` (0); gamma (1); reverse; black_clamp (enabled); white_clamp (disabled). Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Check values with pixel analysis and scopes; compare with alpha and mask; scrub frames; inspect for negative or clamped values. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: premultiplied input commonly needs Unpremult before and Premult after the grade; verify with edges. UI labels and scripting names differ (lift is `black`, gain is `white`, offset is `add`). Black clamp is enabled by default.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/color_nodes/grade.html
