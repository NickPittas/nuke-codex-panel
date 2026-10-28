---
id: "nodes/shuffle"
kind: "node"
title: "Shuffle"
category: "channels"
summary: "Rearranges, fills and creates channels. Nuke 12.1 introduced Shuffle2, which the docs say makes Shuffle and ShuffleCopy obsolete."
aliases: ["Shuffle2", "Shuffle node", "shuffle channels", "ShuffleCopy", "swap channels"]
tags: ["channels", "alpha", "layers", "shuffle", "shuffle2"]
requires: ["fundamentals/channels-data", "fundamentals/alpha-premultiplication"]
related: ["nodes/copy", "nodes/premult"]
nodes: ["Shuffle", "Shuffle2"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Shuffle

## Purpose
Source-documented: rearranges up to eight channels from a single image (B input), rearranges channels between two images (A and B), replaces a channel with black (0) or white (1) constants, and creates new channels. The Shuffle reference page carries a note that Nuke 12.1 introduced Shuffle2, making Shuffle and ShuffleCopy obsolete but still available for backward compatibility by pressing X in the Node Graph and entering Shuffle or ShuffleCopy. The 17.1 user guide ("Shuffling Channels") describes the current noodle-style Properties panel: an Input Layer (channels from B and A) wired to an Output Layer by dragging noodles between sockets. The docs do not state which script class backs the Tab-menu "Shuffle" entry; check with node.Class() before relying on it.

## Inputs
B (primary image) and A (secondary image) as documented. B supplies the first channel group in the panel and A the second. Example from the guide: to take alpha from A, disconnect B's alpha noodle and connect A's alpha to the output alpha; the output is B's rgb plus A's alpha.

## Controls
Documented table on the reference page (UI label -> scripting name): Input Layer "In" -> `fromInput1` (default B) and `fromInput2` (default B); these choose which INPUT (A or B) each input layer group reads from, not the layer. The layer shown in each group is chosen by `in1` (default rgba) and `in2` (default none). Output Layer: `out1` (default rgba) and `out2` (default none) choose the output layers; the "new" dropdown option creates a layer or channels. Per the guide, noodles connect input to output channels, up to eight channels per group, constants 0/1 can be assigned (black/white buttons, or Ctrl/Cmd+click for all outputs), and shortcuts exist for auto-connecting (drag-drop all, double-click by order, Ctrl/Cmd+double-click by name, Alt+drag broadcast). Knob names beyond this table were not confirmed, and the table sits on the page that carries the obsolescence note, so inspect the installed node before scripting. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
After rearranging, view each affected channel and layer; verify alpha is not accidentally black/white filled and downstream channel selectors still match. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: the Shuffle reference page and the 17.1 guide describe the same channel-routing model, but the page notes a generation change (Shuffle/ShuffleCopy to Shuffle2 in 12.1); confirm the node class and knob set in the installed build before generating scripts. Guide tip: use the first output layer for swapping within the current stream and the second for creating new channels, which protects rgba from overwriting. Use Copy for a simple channel copy. Shuffling alpha changes the alpha state but not colour premultiplication.

## Sources
- Foundry Nuke 17.1 documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/shuffle.html
- Foundry Nuke 17.1 documentation: https://learn.foundry.com/nuke/17.1/content/comp_environment/channels/swapping_channels.html
