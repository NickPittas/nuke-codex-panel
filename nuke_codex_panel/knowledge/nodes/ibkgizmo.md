---
id: "nodes/ibkgizmo"
kind: "node"
title: "IBKGizmo"
category: "keying"
summary: "Pulls a key using a clean plate input rather than a single colour picker; output is premultiplied with alpha."
aliases: ["IBKGizmoV3", "IBK", "image based keyer", "ibk key"]
tags: ["key", "ibk", "clean plate", "premultiplied"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data"]
related: ["nodes/ibkcolour", "nodes/merge", "nodes/keylight", "nodes/channelmerge", "nodes/copy"]
nodes: ["IBKGizmo"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# IBKGizmo

## Purpose
Source-documented: uses an input clean plate to drive the key, often helpful on uneven screens. The IBK pair is IBKColor plus IBKGizmo. The output is premultiplied with an alpha and does not composite over the background.

## Inputs
bg (background used for fine edge detail), c (IBKColor output or a location clean plate), and fg (the screen image).

## Controls
Documented knobs: screen type -> `st` (default C-blue); color; red_weight (default 0.5); blue_green_weight (default 0.5); more controls exist on the page. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Composite the result with Merge, inspect edges, spill and alpha against the actual background, and check the clean plate. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: output is premultiplied and not a finished comp; Foundry's IBK page also suggests Keymix to split IBKGizmos. Clean plate quality limits the key. Studio policy (studio-conventions; project preference, not a Foundry rule): default to taking only IBKGizmo's alpha on the shared original or cleaned RGB, merge regional alphas with nodes/channelmerge, Copy the final alpha to the retained RGB, then despill, edge treatment and the premultiplication the next Merge expects; keep Keymix splits as an explicit option (fundamentals/keying-conventions).

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/ibkgizmo.html
- Studio policy: studio-conventions (teacher-supplied production conventions; project preferences, not universal Nuke facts).
