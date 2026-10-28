---
id: "nodes/tracker"
kind: "node"
title: "Tracker"
category: "tracking"
summary: "Two-dimensional point tracker that extracts translation, rotation and scale and can export CornerPin2D or Transform nodes."
aliases: ["Tracker4", "2D tracker", "point track", "stabilize", "match move"]
tags: ["tracking", "stabilize", "matchmove", "corners"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["nodes/cornerpin", "nodes/planartracker", "nodes/transform"]
nodes: ["Tracker"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Tracker

## Purpose
Source-documented: extracts animation of position, rotation and size, which can drive a Transform for matchmove or be inverted for stabilization. Typical process: connect, auto-track or place anchors, calculate, choose an operation.

## Inputs
One unnamed input (the sequence to track).

## Controls
Documented controls: Tracks list items with track_x and track_y, offset_x, offset_y and T/R/S toggles; add_track, del_tracks, select_all, average_tracks; Export dropdown `cornerPinOptions` plus create button `createCornerPin`; Settings tab `channels` and `pretrack_filter` (default median). Many track list controls have scripting name N/A. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Review track error, scrub the track at all frames, compare exported transform on a test element, and look for drift. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: rotation and scale need enough tracks (see the doc notes). Baked exports differ from expression-linked ones. Do not use point tracks for planar surfaces if PlanarTracker fits better.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/tracker.html
