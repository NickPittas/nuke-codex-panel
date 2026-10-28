---
id: "nodes/checkerboard"
kind: "node"
title: "CheckerBoard"
category: "image-io"
summary: "Native generator for checkerboard test images or placeholder textures with controllable box size, four colours and guide lines."
aliases: ["CheckerBoard2", "checker", "test pattern", "checkerboard texture"]
tags: ["generator", "pattern", "texture", "placeholder"]
requires: ["fundamentals/coordinates", "fundamentals/channels-data"]
related: ["nodes/constant", "nodes/reformat"]
nodes: ["CheckerBoard"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# CheckerBoard

## Purpose
Source-documented: a checkerboard image usable as a placeholder texture or background. Use this node rather than rebuilding a checker pattern with an Expression-based stand-in.

## Inputs
No image input is documented; it has its own format control.

## Controls
Documented knobs: format -> `format`; size -> `boxsize` (default 64); `color0`-`color3` (four box colours, color 0 starts at 0,0 then alternates); line color -> `linecolor`; line width -> `linewidth`; centerline color -> `centerlinecolor`; centerline width -> `centerlinewidth`. The doc notes proxy mode may round boxes to the nearest pixel. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View at full resolution, confirm box size, colours, format and bounding box; test stretching or projection with the pattern to see distortion. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: because of proxy rounding, evaluate pixel-accuracy at full resolution. If the pattern is only needed as a flat tone, use Constant. The class name CheckerBoard2 is commonly seen in scripts but is not given on the cited page; confirm with node.Class().

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/image_nodes/checkerboard.html
