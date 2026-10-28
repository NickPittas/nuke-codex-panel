---
id: "nodes/unpremult"
kind: "node"
title: "Unpremult"
category: "compositing"
summary: "Divides colour channels by alpha, restoring a straight colour state for accurate colour correction."
aliases: ["Unpremult node", "unpremultiply", "divide by alpha"]
tags: ["alpha", "unpremultiply", "color correction"]
requires: ["fundamentals/alpha-premultiplication"]
related: ["nodes/premult", "nodes/grade", "nodes/colorcorrect"]
nodes: ["Unpremult"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Unpremult

## Purpose
Source-documented: by default divides RGB by alpha. Place before colour correcting a premultiplied image, then use Premult afterwards, especially before merging over another image.

## Inputs
One unnamed premultiplied image input.

## Controls
Documented knobs: divide -> `channels` (default rgb); by-channel selector (default rgba.alpha); invert -> `invert` (default disabled). Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View edges and low-alpha regions, ensure the pairing with a later Premult, and check alpha 0 areas for odd colour. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: unpremultiplying data that was not premultiplied brightens edges. Low-alpha pixels can amplify noise. Do not use on non-colour data unless alpha semantics are meaningful.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/unpremult.html
