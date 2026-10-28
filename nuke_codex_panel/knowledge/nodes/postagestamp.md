---
id: "nodes/postagestamp"
kind: "node"
title: "PostageStamp"
category: "graph-organization"
summary: "Native thumbnail node that shows its input at the current or a static frame and leaves the image unchanged; it needs a real upstream input and is not a disconnected source or cache."
aliases: ["PostageStamp node", "postage stamp", "thumbnail node", "shared source stamp", "route one Read"]
tags: ["postagestamp", "graph", "organisation", "thumbnail", "concatenation", "stamps"]
requires: ["fundamentals/graph-conventions"]
related: ["nodes/dot", "nodes/backdrop", "nodes/read", "topics/node-graphs", "fundamentals/filtering-concatenation"]
nodes: ["PostageStamp", "Dot", "Backdrop"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# PostageStamp

## Purpose
Source-documented: displays a thumbnail render of its input at the current frame or a frame of your choice, and does not alter the input image in any way. In a graph it can stand as a labelled tap of one upstream node so several branches reuse that source without duplicate Reads or long pipes. Studio preference: do this through one appropriate Read.

## Inputs
One image input from a real upstream node. The node is not a disconnected source, an automatic cache, or a named global link; if the input is missing there is no image. Hiding the pipe changes how the graph is drawn, not the dependency.

## Controls
Documented: by default the stamp follows the current frame; the Preferences Node Graph tab has a postage stamp mode setting (Static frame), and the node properties then take a static frame to display. A frame outside the node's range is clamped to the first or last frame. No other knob names are asserted here; read the installed node to confirm. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Confirm the stamp's input is the intended upstream node, then compare its output with that node in the Viewer. Foundry's concatenation guide lists PostageStamp as passing transform concatenation through; check the transform chain around it if filtering matters. Runtime verified: false; availability and behaviour may differ in the installed build.

## Pitfalls
- The Stamps plugin (named routing) is not the native PostageStamp. Verify Stamps is installed before using it; do not install it, and do not assume the two behave alike.
- Do not treat a PostageStamp as a way to make a branch independent of its source; deleting or re-routing the upstream node still changes it.
- Thumbnail display does not imply the full image is cached or cheap to compute.
- Use a Dot where a plain pipe bend is enough (`nodes/dot`), and label sections with Backdrops (`nodes/backdrop`).

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/other_nodes/postagestamp.html
- How Nodes Concatenate: https://learn.foundry.com/nuke/17.1/content/comp_environment/transforming_elements/node_concatenation.html
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): single-Read reuse through shared-source stamps.
