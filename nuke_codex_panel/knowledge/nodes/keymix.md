---
id: "nodes/keymix"
kind: "node"
title: "Keymix"
category: "compositing"
summary: "Blends input A into B through a mask using A*a + B*(1-a); for unpremultiplied images. Docs say the result has no alpha; inspect output channels."
aliases: ["Keymix node", "mask merge", "matte mix", "keymix vs addmix"]
tags: ["keymix", "mask", "matte", "blend", "unpremultiplied"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data"]
related: ["nodes/addmix", "nodes/merge", "nodes/roto", "nodes/channelmerge"]
nodes: ["Keymix"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Keymix

## Purpose
Source-documented: copies input A to B where the mask is non-black, following Aa + B(1-a), similar to Over but for unpremultiplied images. The docs say the resulting image contains no alpha channel; the channels control and default all nuances mean you should inspect actual output channels rather than assume alpha is preserved or absent. Use it with a Roto shape or any image mask.

## Inputs
A (source copied where the mask allows), B (image underneath), mask (image used as the mask; default effect limited to non-black areas).

## Controls
Documented knobs: channels -> `channels` (default all); mask channel toggle and `maskChannel` (default rgba.alpha); invert -> `invertMask`; mix -> `mix` (dissolves from B at 0 to full Keymix at 1); Set BBox -> `bbox` (default union). Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View the output RGB and mask; confirm which input is the mask source, whether alpha is intentionally not carried, and compare edges with Merge over. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: Keymix is not AddMix; AddMix uses A's alpha to index two LUT curves and also premultiplies. For premultiplied renders, think about Merge over instead. Check output channels in the Viewer instead of asserting alpha is preserved or absent; add alpha explicitly if downstream needs it. Studio policy (studio-conventions; project preference, not a Foundry rule): Keymix is not the default for assembling key mattes. It mixes A's RGBA into B through a mask; prefer alpha-only assembly with nodes/channelmerge and Copy the final alpha to the retained RGB. Use Keymix deliberately, for example to replace a region of an image through a matte.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/keymix.html
- Studio policy: studio-conventions (teacher-supplied production conventions; project preferences, not universal Nuke facts).
