---
id: "nodes/planartracker"
kind: "node"
title: "PlanarTracker"
category: "tracking"
summary: "Roto-based planar tracking workflow for surfaces that lie on a plane; produces CornerPin or Tracker exports."
aliases: ["PlanarTracker", "planar track", "planar tracking", "surface tracker"]
tags: ["tracking", "planar", "roto", "cornerpin"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["nodes/roto", "nodes/cornerpin", "nodes/tracker"]
nodes: ["PlanarTracker", "Roto"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# PlanarTracker

## Purpose
Source-documented: no separate reference-guide page was found for PlanarTracker. Official Tracking a Plane documentation says Transform > PlanarTracker inserts a Roto node already in PlanarTracker mode. A Bezier shape is added as a track object in PlanarTrackLayer1. In Roto or RotoPaint, right-click a shape and use the planar-track options.

## Inputs
Uses Roto node inputs, not a separate documented PlanarTracker port set. Shapes ordered closer to camera hold out those below.

## Controls
Documented concepts: reference frame; track motion options Translation, Rotate, Scale, Shear, Perspective; clear controls; CornerPin dropdown with relative, absolute, stabilize and Tracker choices; Tracking tab includes pre-track filter, adjust for luminance changes, and reference frame. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Review the planar surface across the shot, compare corner outputs to image corners, and verify the reference frame matches your setup frame. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: docs state textured, visible rigid planes track better; holdout from a keyed matte is documented as unavailable. Treat this as a Roto/PlanarTracker mode, not an independent reference page.

## Sources
- Foundry Nuke 17.1 documentation: https://learn.foundry.com/nuke/17.1/content/comp_environment/planartracker/tracking_plane.html
- Related: https://learn.foundry.com/nuke/17.1/content/reference_guide/draw_nodes/roto.html
