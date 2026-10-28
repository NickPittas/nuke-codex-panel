---
id: "nodes/write"
kind: "node"
title: "Write"
category: "image-io"
summary: "Renders upstream results to disk and can sit anywhere in the graph because it has an input and an output."
aliases: ["Write node", "render output", "export frames", "file output"]
tags: ["io", "render", "output", "exr"]
requires: ["fundamentals/color-spaces", "fundamentals/channels-data"]
related: ["nodes/read", "nodes/premult", "nodes/ociocolorspace"]
nodes: ["Write"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "lesson-03"]
---
# Write

## Purpose
Source-documented: renders everything upstream to disk, usually as the last node, and supports formats such as Cineon, TIFF, QuickTime, OpenEXR, HDRI and DPX. It renders at the currently active scale, either full or proxy resolution. Created with W.

## Inputs
One image input (unnamed in the docs) and an output connector, so it may be embedded mid-tree. WriteGeo is the separate geometry writer.

## Controls
Documented knobs: channels -> `channels` (default rgb); file -> `file` (#### or %04d); proxy -> `proxy`; frame -> `frame_mode` with a frame field (expression/startat/offset naming); output transform -> `colorspace`; premultiplied -> `premultiplied`; raw data -> `raw`. Format-specific option groups appear by file type; do not assume one set of controls for every codec. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Confirm the output channel list, colorspace, file path padding, frame range and proxy state before rendering; reopen a written frame in a Read and compare alpha and colorspace. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: rendering while proxy mode is active produces proxy-scale output, so check the scale first. Default channels is rgb, so alpha and AOVs are not written unless added. Data layers need a data-appropriate transform, usually raw/linear, rather than a display transform.
Course practice (lesson-03, teacher example, not a universal rule): per-file-type limits decide what a Write can store, since only some formats keep alpha and EXR is the one named for depth/vectors; render image sequences with `#`/`%04d` padding and a version token in the name, but a movie file cannot use frame hashes. Lossy JPEG sequences are for test renders only. Naming fields are a project convention; follow the project's, not the example's.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/image_nodes/write.html
- Lesson 03 Final.srt (lesson-03, ASR transcript, teaching-practice only): 00:40:13–00:41:26 Write file/type knobs; 00:41:26–00:42:30 channels default rgb, format limits; 00:54:28–00:55:48 versions and hashes versus movie files.
