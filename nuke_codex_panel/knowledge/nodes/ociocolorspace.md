---
id: "nodes/ociocolorspace"
kind: "node"
title: "OCIOColorSpace"
category: "color"
summary: "OpenColorIO colourspace conversion between a chosen input and output colourspace."
aliases: ["OCIOColorSpace node", "OCIO transform", "color space conversion", "ColorSpace"]
tags: ["ocio", "color", "colorspace", "transform"]
requires: ["fundamentals/color-spaces"]
related: ["nodes/read", "nodes/write"]
nodes: ["OCIOColorSpace"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# OCIOColorSpace

## Purpose
Source-documented: converts an image sequence from one colourspace to another, like the standard ColorSpace node, using the OpenColorIO library.

## Inputs
Unnamed image input and optional mask that limits the transform to non-black areas.

## Controls
Documented knobs: channels (default rgb); input -> `in_colorspace` (default linear); output -> `out_colorspace` (default linear); swap input/output -> `swap`. The docs note control labels were updated while knob names remain. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Check names against the active OCIO config; round-trip a test chart; confirm alpha and data layers are not converted incorrectly. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: available colourspace names depend on the OCIO config, not on this reference. Converting twice or applying display transforms to data layers corrupts results.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/color_nodes/ociocolorspace.html
