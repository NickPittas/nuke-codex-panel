---
id: "nodes/backdrop"
kind: "node"
title: "Backdrop"
category: "graph-organization"
summary: "Native organisational box that visually groups nodes by colour and title; moving the box moves overlapping nodes, and it does not process images."
aliases: ["Backdrop node", "group nodes visually", "node box", "section label", "color box"]
tags: ["backdrop", "graph", "layout", "organisation", "bookmark"]
requires: ["fundamentals/graph-conventions"]
related: ["nodes/dot", "nodes/postagestamp", "topics/node-graphs", "topics/interface-navigation"]
nodes: ["Backdrop"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Backdrop

## Purpose
Source-documented: visually groups nodes in the Node Graph by creating a box behind them. Moving the box moves all nodes overlapping it. Several Backdrops with different colours and titles make a particular node easy to find in a large tree. Studio preference: give projection/3D, cleanup, key and each A branch its own titled Backdrop.

## Inputs
None; it has no image pipe. It is organisation, not image processing, and not a Group node (a Group nests nodes into one node; Backdrop only boxes them).

## Controls
Documented: Z Order layers Backdrops (lower values appear underneath); the box resizes by the lower-right triangle; colour and title are set in its properties (open by double-clicking the title bar); appearance can be set to Border to draw only the outline. Backdrops are bookmarked by default (see `topics/interface-navigation`). Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
After moving or resizing, confirm the intended nodes sit inside the box and the title names the section. Deleting from the title bar removes the box and its nodes; Ctrl/Cmd+click on the title bar then Delete removes only the box. Runtime verified: false; availability and behaviour may differ in the installed build.

## Pitfalls
- Overlap decides membership: a box dragged over unrelated nodes will move them too.
- Boxes do not fix tangled wiring; keep the nested mini-tree layout first (`fundamentals/graph-conventions`).
- Z Order layers Backdrops: lower values appear underneath higher ones, so set it deliberately when boxes overlap.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/other_nodes/backdrop.html
- Grouping Nodes in the Node Graph: https://learn.foundry.com/nuke/17.1/content/comp_environment/organizing_scripts/grouping_nodes.html
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): separate labelled sections for 3D/projection, cleanup and key.
