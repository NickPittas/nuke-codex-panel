---
id: "nodes/premult"
kind: "node"
title: "Premult"
category: "compositing"
summary: "Multiplies colour channels by alpha, preparing unpremultiplied images for Merge."
aliases: ["Premult node", "premultiply", "multiply by alpha"]
tags: ["alpha", "premultiply", "merge", "fringe"]
requires: ["fundamentals/alpha-premultiplication"]
related: ["nodes/unpremult", "nodes/merge"]
nodes: ["Premult"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Premult

## Purpose
Source-documented: by default multiplies RGB by alpha. Use before Merge operations when inputs are unpremultiplied, and after colour correction applied to an unpremultiplied copy.

## Inputs
One unnamed unpremultiplied image input.

## Controls
Documented knobs: multiply -> `channels` (default rgb); by-channel selector (default rgba.alpha); invert -> `invert` (default disabled). Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Compare edges and black background, look for fringing, and confirm that the alpha being applied is the intended one. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: premultiplying already premultiplied images darkens edges. The docs give a rule of thumb that dark or black backgrounds can indicate premultiplied images, but check the source.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/premult.html
