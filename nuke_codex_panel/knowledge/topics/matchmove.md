---
id: "topics/matchmove"
kind: "topic"
title: "How to do a match move"
category: "tracking-warping-retiming"
summary: "Attach an element to plate motion with 2D tracks: pick 1-, 2- or 4-point data by what the surface does, set the reference frame, apply it as match-move/Transform/CornerPin2D/links, and verify drift."
aliases: ["match-move", "2d matchmove", "corner pin", "attach element to moving plate", "track and apply", "stabilize and restore", "screen replacement"]
tags: ["tracking", "matchmove", "cornerpin", "reference-frame", "transform"]
requires: ["fundamentals/coordinates", "fundamentals/filtering-concatenation", "fundamentals/alpha-premultiplication"]
related: ["topics/tracker", "topics/planar-tracking", "topics/apply-planar-track", "topics/camera-tracking", "topics/rig-removal"]
nodes: ["Tracker", "CornerPin2D", "Transform", "Merge", "Roto"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# How to do a match move

## Applicability
Use when an element must stick to a feature or surface in a moving plate and the motion is adequately described by image-plane transforms. Direction matters: **match-move** transforms the added element to follow the plate; **stabilize** transforms the plate to remove its motion. Choose data by the surface motion (Brinkmann): one track gives position; two give rotation and scale; four give perspective-like corner motion. Strong parallax or a changing 3D view needs topics/camera-tracking; a textured plane may suit topics/planar-tracking.

## Workflow
1. Track features that move rigidly with the attachment surface (topics/tracker). Tracking the stern of a boat to attach something to its bow fails because they move differently (Brinkmann).
2. Choose the reference frame: the frame where the element is positioned and looks correct. The reference is the identity pose; motion is measured relative to it.
3. Position the element at that frame, then apply motion by one route:
- Copy the Tracker node after the element, set `transform` to match-move (or 1pt for a single track), set `reference frame`, set `smooth` and `filter`. Export can create linked or baked Transform nodes.
- Four tracks to CornerPin2D: Tracker Export offers use current frame or use transform ref frame, linked or baked. Create the CornerPin2D with its input selected so the `to`/`from` fields start from the correct format; do not connect it to the Tracker or Tracker input. Pins run bottom-left, bottom-right, top-right, top-left.
- Linking expressions to any control (Roto translate, SplineWarp/GridWarp points). To make motion relative to the reference, subtract the reference-frame value, for example `Tracker1.tracks.1.track_x - Tracker1.tracks.1.track_x(1)`, where frame 1 is the chosen reference.
4. Integrate: choose `filter` and `clamp` deliberately (sharpening filters can halo); keep `black outside` on unless you need edge extension; set motion blur (`motionblur`/`shutter`, or topics/motion-blur-depth-of-field) to match the plate; match grain, softness and colour; then Merge over with the element's alpha and correct premultiplication.
5. To retouch a stabilized plate and restore the camera move, apply an inverse transform from the same track, and expect two filter passes.

## Verify
- At the reference frame the element sits exactly where authored; at first, middle and last frames overlay it against a high-contrast feature on the plate (for example a temporary CheckerBoard element).
- Step frame by frame at 100% zoom: no slide, pop or sub-pixel swim; check mid-shot and end-shot drift separately.
- Compare with the track's curve for kinks; the visible result decides.
- Verify the element's direction by checking against a clear foreground feature: wrong direction doubles the motion instead of cancelling it.

## Pitfalls
- Changing the reference frame after positioning the element shifts everything.
- Expression offsets using the wrong frame, or mixing absolute and relative values.
- Pins in the wrong order or tracks on different depth planes.
- Different format or proxy between track and application.
- Keeping a plate's own motion blur while the element has none.

## Sources
- Applying Tracking Data: https://learn.foundry.com/nuke/17.1/content/comp_environment/tracking_stabilizing/applying_tracking_data.html
- Tracker reference: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/tracker.html
- CornerPin2D reference: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/cornerpin2d.html
- Brinkmann 2e ch.8 "Choosing the Feature to Track", "Tracking Multiple Points", "Stabilizing a Plate".
