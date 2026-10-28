---
id: "topics/spline-grid-warp"
kind: "topic"
title: "Spline warp and Grid warp"
category: "tracking-warping-retiming"
summary: "Use SplineWarp or GridWarp for local non-rigid distortion and morphs: source/destination semantics, boundaries and pins, and keeping shapes temporally coherent by keying, rippling or tracker-driven points."
aliases: ["splinewarp", "gridwarp", "warp", "morph", "gridwarptracker", "source and destination curves", "reshape", "boundary curve", "pin"]
tags: ["warp", "morph", "splinewarp", "gridwarp", "temporal-coherence"]
requires: ["fundamentals/coordinates", "fundamentals/filtering-concatenation", "fundamentals/time-sampling", "fundamentals/alpha-premultiplication"]
related: ["topics/tracker", "topics/planar-tracking", "topics/rotoscoping-masking", "topics/optical-flow-retiming"]
nodes: ["SplineWarp", "GridWarp", "GridWarpTracker", "Tracker", "PlanarTracker", "Roto"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# Spline warp and Grid warp

## Applicability
Use for localised reshaping (a smile, a prop silhouette, lens-like bends) or AB morphs, not for whole-frame moves (Transform/Tracker). Warps pull neighbouring pixels along; influence falls off with distance, so isolate the subject (roto/key) or limit influence with boundaries and grid lines. Local warping assumes the subject is shape-stable between your keyed frames.

## Workflow
1. Choose the tool. SplineWarp: curves or pins drawn anywhere, open or closed, correspondences with different point counts; inputs `A`, `B`, `mask` (pixels outside the mask pass through unchanged from A). GridWarp: bezier source grid and destination grid on `src`, `dst`, `bg`, `mask`; grid divisions are 3 to 20.
2. Define source (where to warp from) on the image feature, then the destination (where it ends up). With both grids visible and coincident, dragging a point moves both and nothing distorts (Foundry): edit the destination only. SplineWarp: draw a source curve, then draw a destination and Join, or duplicate in A and join. GridWarp: conform grid lines to the feature outline.
3. Restrict influence: grid lines placed between warped and fixed regions, SplineWarp boundary shapes, hard boundaries (closed curves), pins, and `bbox boundary curve`. Layer warp and pair warp multiply into root warp.
4. Make it coherent in time. Options:
- Key source and destination shapes on enough frames; `autokey` adds keys while adjusting, otherwise add keys manually. `ripple` applies a relative adjustment to every frame or a range.
- Link points to Tracker (Ctrl/Cmd-drag the track's animation button onto the point, or Link to) or paste a PlanarTracker transform into the `extra matrix`. A Tracker can drive GridWarpTracker grids; tracking every grid vertex gives the best result, with fewer tracks for simple shots (Foundry).
- SplineWarp's `transform linked` toggle expression-links a shape's transform (all types, or all but extra matrix) to other shapes, so related shapes share one animation instead of separate keys.
5. Quality: raise `curve resolution` on the Render tab if open splines tear or edges jag; use correspondence points sparingly. `crop to format` off lets the warp draw from outside the format at a cost. Use `premultiply input` and `output mask` only with cookie-cutter shapes.
6. Hand-off: choose the `output` view you intend (for example source warped), and check alpha, since `channels` defaults to all and warps alpha too.

## Verify
- Toggle the node (D) and overlays (Q) to compare; play at speed, not only stills (Brinkmann on temporal artifacts).
- Inspect between your keyed frames, where interpolation can wander; look for wobble, tearing near open curves and drift of boundary pixels.
- Check unwanted motion in regions that should be unchanged and that filtering did not soften them noticeably.
- Check motion blur: warps do not blur; Brinkmann says tricks are often needed.

## Pitfalls
- Moving both grids together; relying on pair/layer/root multipliers you forgot you set.
- Overusing correspondence points or high resolution causes slow renders; low-resolution viewer update modes hide final tearing.
- Morph quality depends on matching timing and detail between A and B plates (Brinkmann).
- Tracker-linked points assume the tracker follows the surface at that vertex; check in sequence slips.

## Sources
- Warping (GridWarp/SplineWarp): https://learn.foundry.com/nuke/17.1/content/comp_environment/warping/warping.html
- Transforming and Animating Warps: https://learn.foundry.com/nuke/17.1/content/comp_environment/warping/transforming_animating_warps.html
- Tracking Using the Tracker Node (GridWarpTracker): https://learn.foundry.com/nuke/17.1/content/comp_environment/warping/tracking_tracker.html
- SplineWarp: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/splinewarp.html ; GridWarp: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/gridwarp.html
- Brinkmann 2e ch.5 "Morphing"; ch.7 "Temporal Artifacts"; ch.4 "Motion Blur".
