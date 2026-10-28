---
id: "topics/apply-planar-track"
kind: "topic"
title: "How to use planar tracking results"
category: "planar-particles"
summary: "Turn a planar track into a CornerPin2D (relative, absolute or stabilize), a Tracker with four corner tracks, or a Roto transform. The reference frame and CornerPin from/to values decide whether the result drifts or stays aligned."
aliases: ["CornerPin from planar track", "screen replacement", "relative cornerpin", "absolute cornerpin", "stabilize cornerpin", "export planar tracker", "match move patch"]
tags: ["cornerpin2d", "planartracker", "reference-frame", "stabilize", "baked", "screen-replacement"]
requires: ["topics/planar-tracking", "fundamentals/coordinates", "fundamentals/filtering-concatenation"]
related: ["topics/tracker", "topics/matchmove", "topics/rig-removal", "topics/rotoscoping-masking"]
nodes: ["PlanarTracker", "CornerPin2D", "Tracker", "Roto", "Merge"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-05"]
---
# How to use planar tracking results

## Applicability
Use after a planar track is clean (topics/planar-tracking). Goal: make an element follow the plane (screen replacement, sign, patch, matte), or lock the plane still (stabilize, clean-up in a stable space). Corner pins give a 2D perspective warp only; they do not add parallax or distortion.

## Workflow
1. Select the node that supplies the element (not the tracker) before creating the CornerPin from the PlanarTracker CornerPin dropdown plus Create. Format-dependent from/to values come from the selected node; an unconnected CornerPin2D uses root format.
2. Pick the kind:
   - **relative**: warps by the transform between each frame and the reference frame; the element is unchanged on the reference frame. Use for elements already composed to sit at the plane there (graphics, paint-over, patch).
   - **absolute**: places the element exactly inside the tracked plane using from/to; it can skew the image throughout the shot. Use for full-frame replacement (screen insert); its input must match the format the corners were set for.
   - **stabilize**: applies the inverse transform to lock the plane in place for clean-up, then apply a relative/matching pin to put the work back.
   - **Tracker**: creates a Tracker node with four tracks at the corners for averaging and smoothing.
3. Choose linked or baked. Linked follows later track edits (Link output on); baked copies keyframes, so later track changes are ignored.
4. In CornerPin2D, pins follow a fixed corner order: 1 bottom-left, 2 bottom-right, 3 top-right, 4 top-left. The from tab holds source corners; the to tab holds tracked destination positions. Do not hand-edit linked to values; edit offsets or the track.
5. For tracker-exported pins, use the Tracker export options: current frame or transform reference frame, linked or baked.
6. Layer the result with Merge over the plate. Set CornerPin2D filter appropriate to the move (Cubic default); enable clamp if sharpening filters halo; keep black outside on for layering (it adds a solid alpha if none exists); motionblur and shutter settings give blur matching the camera.
7. Roto/RotoPaint transform data can be copied to CornerPin2D's extra matrix; Tracker data can drive a Roto shape's translate by Link to, including offset by subtracting frame-one position, for garbage mattes.

## Verify
- On the reference frame, relative output equals the source placement; absolute output exactly fills the plane.
- Scrub start, middle, end: element edges stay on the plane edges; compare with the stabilize version for residual motion.
- Alpha and edge: no black or edge-extended pixels leaking from black outside off or wrong format.

## Pitfalls
- Moving the reference frame after export breaks the relationship; re-export.
- Relative on an element that was not positioned at the reference frame gives an offset throughout.
- Absolute pin with an element of different format or aspect stretches it.
- Filtering twice (stabilize then pin) softens; combine into one warp when possible (fundamentals/filtering-concatenation).
- A plane track that is slightly off looks fine on static frames but slides in motion; judge at speed.
- Course practice (lesson-05): a linked pin stays expression-linked to the planar track; a baked pin holds keyframes inside the pin, so verify which you have after editing the surface. A pin that enlarges the bounding box can be cropped, or handled with the Merge set-bounding-box option (A, B, union, intersection).

## Sources
- Foundry Nuke 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/planartracker/tracking_plane.html (CornerPin dropdown, export, correction, reference frame)
- https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/cornerpin2d.html (pins, from/to, filter, black outside, motionblur, extra matrix)
- https://learn.foundry.com/nuke/17.1/content/comp_environment/tracking_stabilizing/applying_tracking_data.html (Tracker export, linking, CornerPin2D)
- Brinkmann 2e, ch. 8 "Tracking Multiple Points" (four-point perspective), "Stabilizing a Plate".
- Lesson 05.srt (lesson-05, ASR transcript, teaching-practice only): 00:44:44–00:46:47 linked versus baked pins; 00:51:47–00:53:17 bounding box, Crop or Merge option.
