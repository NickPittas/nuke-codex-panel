---
id: "nodes/viewer"
kind: "node"
title: "Viewer"
category: "image-io"
summary: "Displays the output of connected nodes without altering data; controls only affect what you see."
aliases: ["Viewer node", "preview", "view transform", "viewer process"]
tags: ["viewer", "display", "gain", "gamma"]
requires: ["fundamentals/color-spaces", "fundamentals/channels-data"]
related: ["nodes/read", "nodes/write"]
nodes: ["Viewer"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Viewer

## Purpose
Source-documented: shows results of connected process nodes and does not alter data. A script can have many Viewers, and one Viewer accepts up to ten process-node connections for cycling and comparing. Created with Ctrl/Cmd+I.

## Inputs
Unnamed inputs, up to ten (documented as 0-9). The docs do not give further per-input semantics.

## Controls
Documented knobs: frame_range, frame_range_lock, frame_increment, channels (default rgba), clip_warning, gain, gamma, downrez, view transform -> `viewerProcess` (default sRGB), input process -> `input_process_node`, input_process, `viewerInputOrder`. Gain and gamma are display adjustments; docs state gamma applies after gain, viewer process and any custom input process. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Compare Viewer inputs, view each channel/layer, and temporarily clear gain/gamma/IP before judging colour or alpha; a different Viewer process changes appearance but not rendered pixels. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: a clean-looking Viewer can hide wrong colour management if gain, gamma, input process or view transform differ from delivery. Downrez multiplies with global proxy scale. Do not treat Viewer settings as comp corrections.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/image_nodes/viewer.html
