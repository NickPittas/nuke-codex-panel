---
id: "topics/channels"
kind: "topic"
title: "Channels system: image channels vs data channels"
category: "cg-channels"
summary: "How Nuke layers/channels route image and data (depth, vectors, mattes), when to shuffle, copy, mask or remove them, and how to keep data channels from being treated as colour."
aliases: ["layers", "aov channels", "exr layers", "shuffle channels", "mask channel", "depth.Z", "shuffle2", "channel count"]
tags: ["channels", "layers", "shuffle", "copy", "data", "mask"]
requires: ["fundamentals/channels-data", "fundamentals/alpha-premultiplication"]
related: ["topics/multipass-cg", "topics/motion-blur-depth-of-field", "topics/combine-keys", "nodes/channelmerge", "fundamentals/keying-conventions"]
nodes: ["Shuffle", "Copy", "ChannelMerge", "Remove", "Read", "Merge"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions"]
---
# Channels system: image channels vs data channels

## Applicability
Use when a stream carries more than rgba: render passes, mattes, depth, motion vectors, or custom layers. Classify every channel first:
- **Image channels** hold light/colour (rgba, lighting passes). They are colour-managed, graded, filtered and merged like pictures.
- **Data channels** hold numbers whose value is the information: depth.Z, forward/backward u,v, normals, position, and categorical IDs. Treat them as non-colour: do not apply colour transforms, and choose resampling or blending according to each channel’s meaning and the consuming node’s requirements rather than processing them indiscriminately like RGB. A blended depth is a surface at a false distance; a blended ID names no object. Mattes are different: they are coverage and are routinely filtered, feathered, motion-blurred (Foundry's TimeBlur averages tracked garbage mattes) and combined with Merge. Decide per channel whether processing is intended or accidental. Vectors have conventions (scale, offset, premultiplication); VectorBlur's `blur uv` softens them on purpose.

Facts from Foundry: a script holds up to 1023 uniquely named channels; every channel lives in a layer; unreferenced channels are dropped on save; the Channel Count does not fall until the script is reopened. Reserved names include rgba.*, depth.Z, forward.u/v, backward.u/v, deep.front/back, disparityL/R, mask.a, rotopaint_mask.a, mask_planartrack.a, mask_splinewarp.a; a custom `mask.a` is renamed `mask_extra`.

## Workflow
1. Inspect: switch the Viewer channel/layer selector through each layer and sample pixels. Note which are image and which are data.
2. Name by Foundry guidance: custom data in its own layer (not added to rgba), descriptive names, at most four channels per layer, same names and order across layers.
3. Route: most nodes read the channels in their `channels`/input control and write to `output`; set both deliberately. A mask control can pick any existing channel (for example a matte stored in its own layer) without piping a new branch; `inject` copies a mask input into mask.a for reuse downstream.
4. Move channels: Shuffle (Shuffle2 since Nuke 12.1; old Shuffle/ShuffleCopy remain only for compatibility) rearranges up to eight channels, can take B and A inputs, and can write constant 0 or 1. Copy replaces chosen channels of B with channels of A, optionally through a mask. ChannelMerge computes one output channel from one channel of each input (alpha by default) and passes everything else from B; use it to combine matte channels without touching RGB. Studio policy (studio-conventions, project preference): for key mattes, assemble alpha with ChannelMerge, then Copy only the final alpha back to the retained RGB (fundamentals/keying-conventions).
5. Limit: after the last use of a layer, Remove it (or use keep). Unused channels are not computed, but removal does not free channel-name slots.
6. File data: for u,v or other numbers read from disk, enable Read `raw` (UI: Raw Data) so no colour conversion is applied. VectorBlur's docs say this explicitly for uv files.

## Verify
- Sample each data channel before and after every node that touches it (Merge, filter, Transform/Reformat, Grade, colourspace): changes must be intended (for example an intentional matte feather or `blur uv`) and never an incidental side effect on depth, IDs or vectors.
- Check the Channel Count and that a node's `channels` selector lists only what it should change.
- After Shuffle/Copy, view rgba.alpha and the destination layer; confirm nothing wrote into rgba by accident.

## Pitfalls
- Unintended processing: Merge `also merge`, filters or Reformat with `channels = all`, and colourspace nodes reach data layers unless the channel set is restricted. Restrict, or Shuffle the data out of the stream and back.
- Writing a matte into rgba.alpha silently changes how every downstream Merge reads premultiplied RGB.
- Single-letter or colliding channel names get renamed or shared.

## Sources
- Foundry 17.1 Channels: https://learn.foundry.com/nuke/17.1/content/comp_environment/channels/channels.html
- Calling Channels: https://learn.foundry.com/nuke/17.1/content/comp_environment/channels/calling_channels.html
- Shuffling Channels: https://learn.foundry.com/nuke/17.1/content/comp_environment/channels/swapping_channels.html
- Shuffle: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/shuffle.html ; Copy: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/copy.html ; Remove: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/remove.html ; Read: https://learn.foundry.com/nuke/17.1/content/reference_guide/image_nodes/read.html
- Intentional matte/vector processing: https://learn.foundry.com/nuke/17.1/content/reference_guide/time_nodes/timeblur.html ; https://learn.foundry.com/nuke/17.1/content/reference_guide/filter_nodes/vectorblur.html ; https://learn.foundry.com/nuke/17.1/content/comp_environment/merging/merge_operations.html
- Brinkmann, Art and Science of Digital Compositing 2e: ch.3 "Pixels, Components, and Channels"; ch.14 "Z-Depth Compositing" (filtering depth is meaningless).
- ChannelMerge: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/channelmerge.html
- Studio policy: studio-conventions (teacher-supplied production conventions; project preferences, not universal Nuke facts).
