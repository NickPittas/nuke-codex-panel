---
id: "nodes/rotopaint"
kind: "node"
title: "RotoPaint"
category: "masking"
summary: "Vector shape and paint node for rotoscoping, clean-up, rig removal, garbage mattes and dust-busting, sharing the Roto shape tools."
aliases: ["RotoPaint node", "paint", "clone", "dustbust", "rig removal paint"]
tags: ["paint", "clone", "cleanup", "roto", "rig removal"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/time-sampling"]
related: ["nodes/roto", "nodes/planartracker"]
nodes: ["RotoPaint"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions", "lesson-06", "lesson-07"]
---
# RotoPaint

## Purpose
Source-documented: RotoPaint is vector based, handles rotoscoping, rig removal, garbage matting and dustbusting, and has per-point/global feather, motion blur, blend modes and layer transforms. It has all Roto shape tools plus brush, clone/reveal, blur and dodge/burn. Created with P.

## Inputs
bg (background image) and mask (optional image).

## Controls
Documented knobs overlap Roto: output -> `output` (default rgba for RotoPaint), premultiply, clip to -> `cliptype`, `replace`, format. Paint strokes and shapes are listed together in the stroke/shape list. The docs point to Project3D, F_RigRemoval and F_WireRemoval as related. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View result and alpha, compare against the source, scrub at several frames and look for stroke/clone-offset drift, edge buildup and frame-dependent paint. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: use Roto for pure matte work and RotoPaint when painting. Paint strokes are frame-sensitive unless set to animate or lifetime. Keep clone offset and source frame under review. Source-bound claims here are not live-tested.
Studio preference: a single RotoPaint with hundreds of strokes is hard to review and revise; split by purpose, region and time span, and chain the pieces. No fixed stroke limit is implied. Choose key placement deliberately (`fundamentals/quality-safeguards`). Set the root format before painting.
Course practice (lessons 06-07): set each stroke's lifetime to its intended span. A patch meant to persist, as on a stabilized plate, was painted on one frame by mistake and needed all frames; a one-frame fix should stay limited. Scrub to check. Verify a stabilize/inverse pair by disabling the paint: the plate must come back unchanged.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/draw_nodes/rotopaint.html
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): splitting paint work.
- Lesson 06.srt (lesson-06; ASR, teaching-practice only): 00:20:48–00:25:40 persistent patch on stabilized plate; Lesson 07.srt (lesson-07): 00:45:54–00:46:15 one-frame clone fixed by changing lifetime.
