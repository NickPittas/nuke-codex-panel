---
id: "nodes/vectorblur"
kind: "node"
title: "VectorBlur"
category: "filter"
summary: "Creates motion blur by blurring pixels along vectors in motion vector channels, usually u and v."
aliases: ["VectorBlur2", "vector blur", "motion blur from vectors", "uv motion blur"]
tags: ["motion blur", "vectors", "uv", "3d"]
requires: ["fundamentals/channels-data", "fundamentals/alpha-premultiplication"]
related: ["nodes/zdefocus", "nodes/kronos"]
nodes: ["VectorBlur"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# VectorBlur

## Purpose
Source-documented: blurs pixels into straight lines using u and v channels. Vectors may come from VectorGenerator, MotionBlur2D, MotionBlur3D, ScanlineRender or RayRender, or from third-party two-channel float images; the docs say unpremultiply those images if possible.

## Inputs
One unnamed image input and an optional mask.

## Controls
Documented knobs: channels (default none); uv; mv_presets (default Nuke Scanline Render; chooses renderer scale/offset); blur_uv; invert_uv; uv_offset; output (default result); gpuName and useGPUIfAvailable. The documentation says constant uv offsets can add camera movement or shake blur. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Compare vector preset and channel direction; view motion vectors as data; test invert and inspect the edge behaviour. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: wrong renderer preset gives wrong scale. Data passes like vectors should not be colour-converted. Alpha and edges around moving objects can need extra vector handling.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/filter_nodes/vectorblur.html
