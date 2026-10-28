---
id: "nodes/colorcorrect"
kind: "node"
title: "ColorCorrect"
category: "color"
summary: "Adjusts saturation, contrast, gamma, gain and offset for master, shadows, midtones and highlights."
aliases: ["ColorCorrect node", "shadows midtones highlights", "color correct"]
tags: ["color", "correction", "tonal range", "midtones"]
requires: ["fundamentals/color-spaces", "fundamentals/alpha-premultiplication"]
related: ["nodes/grade", "nodes/unpremult"]
nodes: ["ColorCorrect"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# ColorCorrect

## Purpose
Source-documented: quick adjustments to contrast, gamma, gain and offset over the whole tonal range or limited to shadows, midtones or highlights. Created with C. The Ranges tab lookup curves define the regions; the docs say not to adjust the midtone curve because it equals 1 minus the other two.

## Inputs
Unnamed image input and optional mask limiting correction to non-black areas.

## Controls
Documented knobs: channels (default rgb); master saturation, contrast, gamma and gain (all default 1 as listed); Ranges tab lookup curves for shadows/highlights. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Inspect with scopes, isolate the range using the Viewer, and compare against a Grade-based alternative when matching plates. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: premultiplied input should be unpremultiplied before the correction, then premultiplied again. Range overlap can create banding on high-contrast edges. Use Grade for explicit black/white point matching.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/color_nodes/colorcorrect.html
