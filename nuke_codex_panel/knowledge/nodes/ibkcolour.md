---
id: "nodes/ibkcolour"
kind: "node"
title: "IBKColor"
category: "keying"
summary: "Creates the clean-plate image for IBKGizmo from a blue or green screen."
aliases: ["IBKColour", "IBKColor", "IBKColourV3", "ibk clean plate"]
tags: ["key", "ibk", "clean plate", "chroma"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data"]
related: ["nodes/ibkgizmo", "nodes/keylight"]
nodes: ["IBKColor", "IBKColour"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# IBKColor

## Purpose
Source-documented: the official page and node are named IBKColor (the requested IBKColour spelling has no page found). It is paired with IBKGizmo: IBKColor creates a clean plate and IBKGizmo pulls the key.

## Inputs
Input 1 is the blue- or green-screen image; its output connects to IBKGizmo's c input.

## Controls
Documented knobs: screen_type (default blue) and Size (default 10) shown on the Parameters tab; adjust until the output contains only background colours. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View IBKColor beside IBKGizmo; the clean plate should lack foreground detail. Prefer .exr if pre-rendering the clean plate. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: pre-rendering to formats that lose colour information can break the key per the docs. A real clean plate is more accurate when one exists.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/ibkcolor.html
