---
id: "nodes/copy"
kind: "node"
title: "Copy"
category: "channels"
summary: "Replaces selected channels in B with channels from A, optionally using a mask and mix."
aliases: ["Copy node", "copy channel", "copy alpha", "ShuffleCopy"]
tags: ["channels", "alpha", "copy", "layer"]
requires: ["fundamentals/channels-data", "fundamentals/alpha-premultiplication"]
related: ["nodes/shuffle", "nodes/premult", "nodes/channelmerge"]
nodes: ["Copy"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Copy

## Purpose
Source-documented: replaces channels in the B input with channels from A. A mask can choose per-pixel which input is used or blend them, and mix can dissolve. Created with K. See Shuffle for broader rearrangement.

## Inputs
A (supplies the source channel), B (receives it), optional mask. Default mask behaviour uses A where the mask is white, B where black and a blend between.

## Controls
Documented knobs: pairs of from/to selectors with enable checkboxes, the first being `from0` and `to0`, further `from1`/`to1`; Layer Copy -> `channels`; Set BBox -> `bbox` (default union). The docs show defaults of rgba.alpha for the first copy pair. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View the destination channels and alpha; confirm layer names, the bounding box, and downstream premultiplication. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: copying alpha does not change RGB premultiplication, so premult/unpremult as needed. If the source layer is missing, results are not guaranteed by this reference; check in the Viewer. Studio policy (studio-conventions; project preference): for keys, Copy alpha only, from A (the assembled matte) onto B (the retained original or cleaned RGB), so B's RGB survives; then despill, edge treatment and appropriate premultiplication. Where applicable set `bbox` so the result stays bounded to B, and check it against the background window (fundamentals/quality-safeguards). Assemble the matte first with nodes/channelmerge; Copy does not combine mattes.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/copy.html
- Studio policy: studio-conventions (teacher-supplied production conventions; project preferences, not universal Nuke facts).
