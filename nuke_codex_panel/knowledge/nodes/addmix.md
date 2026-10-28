---
id: "nodes/addmix"
kind: "node"
title: "AddMix"
category: "compositing"
summary: "Uses A's alpha to index two lookup curves, one multiplying A and one multiplying B, then adds the results."
aliases: ["AddMix node", "add mix", "lut mix", "keymix vs addmix"]
tags: ["addmix", "lut", "alpha", "mix", "premultiply"]
requires: ["fundamentals/alpha-premultiplication"]
related: ["nodes/keymix", "nodes/merge"]
nodes: ["AddMix"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# AddMix

## Purpose
Source-documented: A's alpha indexes two colour-correction LUT curves; the first multiplies A, the second B, and the results are added. It resembles Merge over but also premultiplies implicitly; the premultiplied toggle only compensates for an already-premultiplied A. It is not a simple plus node. The docs warn that CG already premultiplied may be premultiplied twice and lose detail.

## Inputs
A (must include an alpha channel), B (second input), and optional mask.

## Controls
Documented knobs: A -> `A`, B -> `B`, output -> `output` (rgba defaults); premultiplied -> `premultiplied` compensates for A being premultiplied (divides colours); nonlinear -> `nonlinear` remaps 0-infinity into 0-1 logarithmically; LUT curves -> `lut`; mix -> `mix`. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Compare against Merge over and Keymix on the same inputs; examine edges and alpha for double premultiplication. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: choose AddMix when you specifically want alpha-indexed LUT behaviour or a roto-shape mix. Do not use it blindly on rendered CG. Do not confuse AddMix with Merge's `mix` knob.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/addmix.html
