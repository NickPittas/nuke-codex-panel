---
id: "fundamentals/channels-data"
kind: "fundamental"
title: "Channels, layers and data images"
category: "fundamentals"
summary: "Nuke channels belong to layers; distinguish colour from data channels (depth, motion, masks, IDs), route them explicitly, and verify what a node actually reads and writes."
aliases: ["layers", "AOV", "render passes", "shuffle", "channel set", "depth channel", "mask channel", "motion vector channel"]
tags: ["channels", "layers", "data", "shuffle", "aov", "exr"]
requires: []
related: ["fundamentals/color-spaces", "fundamentals/alpha-premultiplication", "topics/channels", "topics/multipass-cg"]
nodes: ["Shuffle", "Copy", "Merge", "Roto", "Viewer"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "lesson-02"]
---
# Channels, layers and data images

## Applicability
Use with multi-layer EXR renders, mattes, depth, motion vectors, or any node that has an output, channels, mask or merge-channel control. Every channel is named layer.channel and belongs to a layer; rgba is the default one.

## Workflow
1. List the channels actually present at the point you care about (Viewer channels dropdown, or the node's channel menus). Channels persist downstream until replaced or removed, so upstream context can silently supply or lack data.
2. Classify each channel: colour (beauty, light passes) or data (depth.Z, forward/backward u,v, masks, IDs, normals, position). Data is not colour: it needs no display transform and no colour conversion, and in OCIO configs it belongs in a raw/data space. Config role lists show a data role such as Raw.
3. Route deliberately. Nodes with output or channels controls write to the chosen layer; for nodes without them, use Shuffle (rearranges channels from one or two inputs) or Copy to create and move channels.
4. Name custom layers yourself. Foundry's guidance: use proper multi-letter names, put custom channels in a custom layer, and keep layers to four channels or fewer since the interface handles four.
5. Set merge and mask channel menus to the intended channels; otherwise the default rgba pairing applies.

## Verify
- View each routed channel alone (including alpha) at a representative frame.
- Sample data channels at known pixels before and after processing: confirm no unintended colour conversion, blending or range change. Values often exceed 0-1 in float EXR. Processing can be intended: matte coverage may be feathered or motion blurred, and VectorBlur's blur uv option deliberately smooths motion vectors; categorical data such as object IDs has no meaningful in-between value.
- Confirm a downstream node reads the layer you routed, not a stale channel.

## Pitfalls
- Reserved names (rgba, depth.Z, forward/backward u v, mask.a and a few more) are renamed if reused for custom channels; mask.a becomes mask_extra.
- You cannot add new channels to built-in layers such as mask.
- Resampling is conditional on data type and consumer. Soft coverage or colour-like data tolerates filtering; categorical IDs generally do not (a filter blends two IDs into a third) [INFERENCE]. Vectors and positions also change meaning under a transform: an impulse filter keeps raw values but does not correct their coordinate basis or units after the pixels move, so verify downstream use.
- Unreferenced channels are dropped on script save, and the channel count does not shrink in-session.
- Source depth and format (lesson-02 teacher practice, not Foundry-confirmed): floating-point working precision does not restore detail a source already lost; banding and JPEG artifacts persist, so treat lossy files as reference. The lesson contrasts ordinary RGBA image handoffs with an EXR multichannel workflow for utility data such as depth; verify the actual reader/writer channel capabilities of the format in use.

## Sources
- Channels: https://learn.foundry.com/nuke/17.1v1/content/comp_environment/channels/channels.html
- Understanding Channels and Layers: https://learn.foundry.com/nuke/17.1/content/comp_environment/channels/understanding_channels.html
- Creating Channels and Layers: https://learn.foundry.com/nuke/17.1/content/comp_environment/channels/creating_channels.html
- OCIO roles (data role): https://learn.foundry.com/nuke/17.1/content/comp_environment/configuring_nuke/using_ocio_config_files.html
- VectorBlur (u/v channels, blur uv, raw-data colourspace for file-read vectors): https://learn.foundry.com/nuke/17.1/content/reference_guide/filter_nodes/vectorblur.html
- Lesson 02 Final.srt (lesson-02, ASR transcript, teaching-practice only): 00:12:33–00:15:10, 00:25:11–00:26:08, 00:34:07–00:35:10 working precision and RGBA versus multichannel handoffs.
