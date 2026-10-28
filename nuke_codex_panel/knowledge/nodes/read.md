---
id: "nodes/read"
kind: "node"
title: "Read"
category: "image-io"
summary: "Loads image sequences or movies from disk and converts them to Nuke's working colorspace using the selected input transform."
aliases: ["Read node", "load footage", "import plate", "file input"]
tags: ["io", "footage", "colorspace", "exr"]
requires: ["fundamentals/color-spaces", "fundamentals/channels-data"]
related: ["nodes/write", "nodes/reformat", "nodes/ociocolorspace"]
nodes: ["Read"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Read

## Purpose
Source-documented: loads images from disk at native resolution and frame range, picks the reader from the file extension, and converts to Nuke's native 32-bit linear working space. Created with R in the Node Graph.

## Inputs
No image input is documented; it is a source node. Related but separate nodes: DeepRead, ReadGeo, AudioRead.

## Controls
Documented knobs (UI label -> scripting name): File -> `file` (#### or %04d padding); Format -> `format`; Frame Range `first`/`last` with `before`/`after` behaviour; Frame -> `frame_mode` + `frame` (expression/startat/offset); Missing Frames -> `on_error`; Input Transform -> `colorspace` (label updated, knob name unchanged per docs); Premultiplied -> `premultiplied`; Raw Data -> `raw`; Auto Alpha -> `auto_alpha`. EXR reads add Channel Filter / `channel_filters` controls for large AOV files. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Check the Format and colorspace match the plate's real encoding; inspect the metadata tab; view alpha and every needed layer; confirm first/last frames and out-of-range behaviour. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: `raw` skips conversion, so use only for data (normals, depth, vectors) rather than colour. `premultiplied` is for plates whose colour is premultiplied; enabling it on straight plates is wrong. Too many EXR AOV channels can hit the documented 1024 channel limit; filter them.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/image_nodes/read.html
