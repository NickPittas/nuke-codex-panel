---
id: "topics/node-graphs"
kind: "topic"
title: "Building node graphs"
category: "interface"
summary: "How to create, connect, branch, replace and organise nodes so data flow, main-role inputs (B background, A foreground, mask) and channel routing are correct and readable."
aliases: ["connect nodes", "merge A B inputs", "node tree layout", "clone vs copy vs link", "dot node", "insert node between", "mask input connection"]
tags: ["node graph", "merge", "pipes", "inputs", "clone", "link", "layout"]
requires: ["fundamentals/node-selection", "fundamentals/channels-data", "fundamentals/alpha-premultiplication", "fundamentals/graph-conventions", "fundamentals/quality-safeguards"]
related: ["topics/interface-navigation", "topics/color-and-roto", "topics/rotoscoping-masking", "nodes/postagestamp", "nodes/dot", "nodes/backdrop"]
nodes: ["Merge", "Dot", "Roto", "Grade", "Viewer", "Backdrop", "PostageStamp"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions"]
---
# Building node graphs

## Applicability
Use when assembling or repairing a script. Pipes carry the image stream downstream; every node processes what arrives and passes through the rest. Shortcuts are 17.1 documentation defaults and may be rebound by a studio `menu.py`; menus display the live binding. Navigation/inspection is `topics/interface-navigation`.

## Workflow
1. **Add in the right place.** A new node connects to the *selected* node, so select the node it should follow first (Tab menu: Tab, type, Return; toolbar; right-click). Shift while creating starts a new branch from the selected node instead of inserting; Ctrl/Cmd while creating replaces the selected node (not available through single-key node shortcuts). With nothing selected the node arrives unconnected.
2. **Know the main-role inputs.**
   - Single-input operators (Blur, Grade, ColorCorrect): the unnamed input is the stream being modified.
   - **Merge**: B is the background/base, A the foreground; extra A inputs appear (A1, A2...) as you connect, with higher A numbers stacked on top. Studio policy: one A layer per Merge, chained sequentially down the B trunk (see `fundamentals/graph-conventions`). The Merge `mask` input limits the merge to the non-black areas of the chosen mask channel.
   - **Roto**: `bg` supplies the plate whose format/bbox/channels the roto builds on; its `mask` input is separate.
   - `mask` inputs appear as a small triangle on the right; drag it out. If an unconnected external mask connector is missing, set the node's *mask* control to `none` to expose it; after connecting the mask, select its intended channel (Foundry, Calling Channels).
3. **Keep layout meaningful.** Foundry guidance is B inputs vertical, A inputs entering from the left, masks from the right. Studio policy (`fundamentals/graph-conventions`, not a global Nuke rule): background on a top-to-bottom B trunk, each A branch from the left or right as its own nested mini-tree with room for its full B-pipe, one A per Merge. Autoplace (L) tidies a selection; Dot nodes bend pipes (`nodes/dot`); the *hide input* option, a shared source via `nodes/postagestamp`, and labelled Backdrops (`nodes/backdrop`) reduce long cross-graph pipes. Reuse one Read rather than duplicating it.
4. **Edit connections.** Drag the pipe's tail onto another node's centre to reconnect. Ctrl/Cmd+D disconnects the selected lower node. Shift-drag a pipe onto another node to duplicate the connection. Dragging a node onto an existing pipe inserts it. After pasting, nodes attach to whatever is selected, so click empty space first to paste unconnected.
5. **Choose the copy mechanism deliberately.** Copy/paste gives independent values; Clone (Edit > Clone, Ctrl+K for copy-as-clone) keeps all values synchronised but cannot clone gizmos (e.g. Grain, LightWrap, IBK nodes); Link nodes (Alt+L) keep a linked copy with optional per-knob overrides.
6. **Read indicators** on nodes for channels, mask use, disabled state, animation, expressions, clones, links and a mix below 1.

## Verify
- View the output of each new branch; check Merge inputs by disabling the A node (D): the stream should continue through B (Nuke's documentation states data flows from B when A is disabled).
- Confirm which channels a node processes (channel indicator) and which it only passes through.
- Merge output bbox follows its *set bbox to* control (union by default); confirm the result covers what downstream nodes need.

## Pitfalls
- Most Merge operations expect premultiplied inputs; only the `matte` operation expects unpremultiplied. Check alpha state before layering CG or keyed elements.
- Swapping A and B changes the result for over and other non-commutative operations.
- A many-A Merge or left-to-right sprawl hides which layer sits where; split into sequential Merges and re-space the branches before adding more.
- Long pipes across the graph or duplicated Reads: route from one source with Dots or a PostageStamp whose input is the real upstream node.
- Clones show only the clone link in the graph, hiding expression links.
- Conceptually, the A/B/mask roles follow Brinkmann's multisource-operator and mask discussion (Chapter 5); the Nuke-specific connection behaviour above comes from the Foundry pages.

## Sources
- Foundry Nuke 17.1, Working with Nodes: https://learn.foundry.com/nuke/17.1/content/getting_started/using_interface/working_nodes.html
- Foundry Nuke 17.1, Merge: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/merge.html
- Foundry Nuke 17.1, Roto (inputs): https://learn.foundry.com/nuke/17.1/content/reference_guide/draw_nodes/roto.html
- Foundry Nuke 17.1, Calling Channels (mask input): https://learn.foundry.com/nuke/17.1v1/content/comp_environment/channels/calling_channels.html
- Brinkmann 2e, Chapter 5 Basic Image Compositing (Multisource Operators, Masks); Chapter 9 Interface Interactions (Methods of Representing the Compositing Process).
- Studio conventions (teacher-supplied production conventions, 2026-10-28, project preferences rather than universal Nuke facts): see `fundamentals/graph-conventions`.
