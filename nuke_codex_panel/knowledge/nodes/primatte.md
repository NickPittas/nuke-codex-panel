---
id: "nodes/primatte"
kind: "node"
title: "Primatte"
category: "keying"
summary: "Polyhedron-in-colour-space keyer built by incrementally sampling screen colours."
aliases: ["Primatte node", "primatte keyer", "green screen"]
tags: ["key", "chroma", "polyhedron"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/color-spaces"]
related: ["nodes/keylight", "nodes/ibkgizmo", "nodes/channelmerge", "nodes/copy"]
nodes: ["Primatte"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Primatte

## Purpose
Source-documented: keys are created by sampling single pixels or ranges from the screen. The samples adjust a colourspace polyhedron that decides what is inside or outside the matte. Auto-Compute attempts to sense and remove the backing screen.

## Inputs
bg (background), fg (foreground to key) and optional mask.

## Controls
Documented knobs: foreground and background channel selectors (default rgb), crop, mask handling; also an operation setting for sample use and Ctrl-click or Ctrl+Shift-drag colour selection in the Viewer. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View alpha and composite, step sample operations, and inspect edge detail and spill. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: Primatte is a trademark and has patent notes in the docs. Sampling order matters and Nuke undo exists during sampling. Results are plate-dependent. Studio policy (studio-conventions; project preference, not a Foundry rule): take its alpha as one regional matte, assemble with nodes/channelmerge and Copy the final alpha to retained RGB rather than passing Primatte's processed RGB onward (fundamentals/keying-conventions).

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/primatte.html
- Studio policy: studio-conventions (teacher-supplied production conventions; project preferences, not universal Nuke facts).
