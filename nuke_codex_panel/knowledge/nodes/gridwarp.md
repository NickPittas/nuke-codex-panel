---
id: "nodes/gridwarp"
kind: "node"
title: "GridWarp"
category: "warp"
summary: "Warps by transferring information from a source Bezier grid onto a destination grid."
aliases: ["GridWarp3", "grid warp", "bezier grid"]
tags: ["warp", "grid", "morph"]
requires: ["fundamentals/coordinates", "fundamentals/filtering-concatenation"]
related: ["nodes/splinewarp"]
nodes: ["GridWarp"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# GridWarp

## Purpose
Source-documented: first position the source grid, defining where to warp from, then the destination grid, defining where to warp to. The destination can be a duplicate of the source or separately defined.

## Inputs
bg (background used when the background control is bg), dst (destination image), src (source image) and an optional mask.

## Controls
Documented knobs: channels (default all); mask handling `inject`, `invert_mask`; plus source/destination grid editing in the Viewer. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View both grids and the warp; check edges, folds and any mask effects; compare to source image. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: choose which grid is source and destination before keyframing. GridWarp moves points on grid lines, unlike SplineWarp's freeform shapes.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/gridwarp.html
