---
id: "nodes/merge"
kind: "node"
title: "Merge"
category: "compositing"
summary: "Layers A over B (or another operation) with premultiplied-input assumptions, channel selectors, mask and mix."
aliases: ["Merge2", "over", "merge node", "layer images", "composite over"]
tags: ["merge", "over", "matte", "stencil", "compositing"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data", "fundamentals/coordinates"]
related: ["nodes/keymix", "nodes/addmix", "nodes/premult", "nodes/channelmerge"]
nodes: ["Merge"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Merge

## Purpose
Source-documented: layers multiple images using the operation dropdown (default over). Most algorithms expect premultiplied inputs; the documentation says the matte operation should use unpremultiplied images. Created with M.

## Inputs
A (foreground/source; connecting A spawns A1, A2 for additional inputs), B (the image to merge with), and optional mask. Do not swap A and B without checking the operation.

## Controls
Documented knobs: operation -> `operation` (default over); alpha masking -> `screen_alpha`; set bbox to -> `bbox` (default union); metadata from -> `metainput`; range from -> `rangeinput`; A channels -> `Achannels`; B channels -> `Bchannels`; output -> `output`; also merge -> `also_merge`; mask handling `inject`/`invert_mask`/`fringe`; mix -> `mix`. The docs state stencil is the reverse of out and shows B where A is absent. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Check A/B connection, operation, alpha, premultiplication, bbox and channel routing; view RGB and alpha and look for fringes. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: if the fg is unpremultiplied, premultiply it first. Do not treat Keymix or AddMix as drop-in Merge replacements: they have different alpha formulas and output behaviour. Default bbox union can enlarge processing area.
Studio preference (not a Foundry rule; `fundamentals/graph-conventions`): B is the vertical background trunk, one A per Merge, chained sequentially instead of a many-A Merge; A enters from the left or right. To contain a comp to the background, set bbox to B, or Crop A to the background window right before the Merge; format itself is not a crop (`fundamentals/quality-safeguards`). For assembling key mattes prefer ChannelMerge (`nodes/channelmerge`).

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/merge.html
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): one-A-per-Merge layout and bbox containment.
