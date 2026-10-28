---
id: "nodes/roto"
kind: "node"
title: "Roto"
category: "masking"
summary: "Vector Bezier/B-spline shape node for rotoscoping, drawing shapes such as ellipses/rectangles, and generating mattes in a chosen output channel."
aliases: ["Roto node", "rotoscope", "roto ellipse", "roto circle", "garbage matte"]
tags: ["roto", "matte", "mask", "shape", "ellipse"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/coordinates"]
related: ["nodes/rotopaint", "nodes/planartracker", "nodes/keymix"]
nodes: ["Roto"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Roto

## Purpose
Source-documented: Roto is for rotoscoping only and edits Bezier and B-spline shapes. Create shapes with the Viewer tools, including shape tools such as Ellipse and Rectangle, then edit them in the control panel. Created with O. For a circular matte, draw an Ellipse in Roto rather than generating one with Expression math.

## Inputs
bg (optional background; adding it gives Roto an input image and format) and mask (optional image). Roto without bg uses its format knob.

## Controls
Documented knobs: output -> `output` (default alpha); premultiply -> `premultiply` (default none); clip to -> `cliptype` (default format); replace -> `replace`; format -> `format` (used with no input); invert -> `invert_mask`; fringe -> `fringe`. Output channels receive the shape result; Roto can also be placed in PlanarTracker mode. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View alpha with the Viewer; check the output channel, clip-to setting, feather, and animated points at keyframes and in-between frames. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: `replace` clears existing channels before drawing. Output defaults to alpha, so shapes do not show as rgb unless output or the downstream setup says otherwise. The mask input and the shape result are separate concepts. Do not use Expression as a standin for ordinary shape drawing.
Studio preference: key at meaningful poses and occlusion changes and inspect interpolation; a key on every frame can cause jitter, though rapid change can justify per-frame keys. Deliberate placement, not a numeric ban (`fundamentals/quality-safeguards`). A wrong or unset root format gives wrong roto extents when no `bg` is connected.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/draw_nodes/roto.html
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): keyframe placement.
