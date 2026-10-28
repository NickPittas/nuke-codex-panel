---
id: "nodes/splinewarp"
kind: "node"
title: "SplineWarp"
category: "warp"
summary: "Warps an image using drawn shapes or pins, with differing point counts permitted between corresponding shapes."
aliases: ["SplineWarp3", "spline warp", "shape warp", "morph"]
tags: ["warp", "spline", "morph", "roto"]
requires: ["fundamentals/coordinates", "fundamentals/filtering-concatenation"]
related: ["nodes/gridwarp", "nodes/roto"]
nodes: ["SplineWarp"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# SplineWarp

## Purpose
Source-documented: warps based on shapes or pins that may be drawn anywhere on either image; corresponding shapes can have different numbers of points; shapes can be pasted from Roto/RotoPaint or other SplineWarp nodes. See GridWarp for grid-based warping.

## Inputs
A (image to warp from), B (image to warp to), and optional mask. The docs say B to A warps are equally valid. Pixels outside the mask region are copied from A.

## Controls
Documented knobs: channels (default all); premultiply input -> `premultiply`; output mask -> `outputMask` (default mask_splinwarp.a as the page spells it); crop to format -> `crop_to_format`; bbox boundary curve -> `boundary_bbox`. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Compare against both images at several frames, look at fold-over, edges and the output mask channel. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: keyframe density and boundaries control warp stability. The knob default mask_splinwarp.a is quoted from the docs and may contain the page's own spelling.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/splinewarp.html
