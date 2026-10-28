---
id: "nodes/dot"
kind: "node"
title: "Dot"
category: "graph-organization"
summary: "Native pass-through node that bends connecting arrows to keep a script readable; it does not alter the image."
aliases: ["Dot node", "pipe bend", "reroute", "bend connecting arrow", "dot"]
tags: ["dot", "graph", "layout", "pipes", "organisation"]
requires: ["fundamentals/graph-conventions"]
related: ["nodes/postagestamp", "nodes/backdrop", "topics/node-graphs", "fundamentals/filtering-concatenation"]
nodes: ["Dot"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Dot

## Purpose
Source-documented: makes bends in the connecting arrows between other nodes to keep a script easy to read. It does not alter the input image in any way. Created by pressing . (period) on the Node Graph. Studio preference: use Dots to route a branch around the trunk instead of a long diagonal pipe, keeping B on a vertical trunk.

## Inputs
One unnamed input: the image after which you want a bend.

## Controls
No image controls are documented. Documented creation: select the node before the connector, then Other > Dot (a dot appears after it, drag to reposition), or Ctrl/Cmd+click the yellow dot on a connecting arrow to add one to an existing connection. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Check the Dot passes the same image as its input (compare in the Viewer) and that downstream nodes connect to the Dot. Foundry's concatenation guide lists Dot as not breaking a transform chain. Runtime verified: false; availability and behaviour may differ in the installed build.

## Pitfalls
- A Dot is routing, not storage: it adds no cache and no separate source.
- Dots between spread-out branches should keep the nested mini-tree structure readable; a tangle of Dots signals a layout problem (`fundamentals/graph-conventions`).
- For a shared source consumed far away, a PostageStamp or the Stamps plugin (if verified available) labels the tap better (`nodes/postagestamp`).

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/other_nodes/dot.html
- Bending Connecting Arrows: https://learn.foundry.com/nuke/17.1/content/getting_started/using_interface/connecting_nodes.html
- How Nodes Concatenate: https://learn.foundry.com/nuke/17.1/content/comp_environment/transforming_elements/node_concatenation.html
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): Dot routing for a vertical B trunk.
