---
id: "nodes/zdefocus"
kind: "node"
title: "ZDefocus"
category: "filter"
summary: "Depth-of-field blur driven by a depth channel and optional bokeh filter image."
aliases: ["ZDefocus2", "depth of field", "z defocus", "defocus"]
tags: ["depth", "defocus", "dof", "bokeh"]
requires: ["fundamentals/channels-data", "fundamentals/coordinates"]
related: ["nodes/vectorblur"]
nodes: ["ZDefocus"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# ZDefocus

## Purpose
Source-documented: blurs according to a depth map channel to simulate depth of field. It splits the image into depth layers, blurs each with one size, then blends back to front to preserve object order.

## Inputs
filter (the kernel image representing camera aperture/bokeh), image (the sequence to blur; should contain the depth channel), and optional mask.

## Controls
Documented knobs: channels (default all); gpuName; useGPUIfAvailable; depth channel -> `z_channel` (default depth.Z); math (default depth), which interprets depth conventions, for example the direct mode relates Z directly to blur size; output (default result); show_image. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Use the focal-plane setup view, confirm depth values and convention, and compare near and far blur. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: depth conventions vary between renderers, so check what higher values mean. The docs name a depth channel but do not make your depth data valid; premultiplied or antialiased depth can create edge artefacts.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/filter_nodes/zdefocus.html
