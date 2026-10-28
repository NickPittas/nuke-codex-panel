---
id: "nodes/constant"
kind: "node"
title: "Constant"
category: "image-io"
summary: "Generates a flat colour image in every pixel, including outside the format, for backgrounds, masks and tests."
aliases: ["Constant node", "solid colour", "flat colour", "solid colour plate"]
tags: ["generator", "solid", "background", "mask"]
requires: ["fundamentals/channels-data", "fundamentals/coordinates"]
related: ["nodes/checkerboard", "nodes/merge"]
nodes: ["Constant"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Constant

## Purpose
Source-documented: every pixel is the same colour, inside and outside the image area. Use it as a native solid-colour source rather than faking one with an expression or tinted Grade.

## Inputs
No image input is documented.

## Controls
Documented knobs: channels -> `channels` (default rgba), color -> `color` (default 0), format -> `format` (project dependent), frame range -> `first`/`last` for animated colour. Set alpha explicitly if used as a solid matte. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View each channel and alpha; confirm format and bounding box before merging or using as a mask; use pixel analysis on RGB and alpha. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: default colour is black. Colour-managed values and premultiplication matter when merged; a flat coloured image with alpha 1 is already solid. A Constant used as a data layer should be treated as data, not display colour.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/image_nodes/constant.html
