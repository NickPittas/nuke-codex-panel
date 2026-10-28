---
id: "topics/planar-tracking"
kind: "topic"
title: "How to do planar tracking"
category: "planar-particles"
summary: "Track a flat, textured surface as a whole with PlanarTracker (a Roto node in planar mode) from a drawn shape on a reference frame. It yields a 2D perspective transform of that plane, not a 3D camera."
aliases: ["PlanarTracker", "planar track", "surface tracking", "plane track", "roto planar tracking", "track a screen or wall"]
tags: ["planartracker", "roto", "reference-frame", "perspective", "holdout", "2d"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["topics/apply-planar-track", "topics/tracker", "topics/matchmove", "topics/rotoscoping-masking", "topics/camera-tracking"]
nodes: ["PlanarTracker", "Roto", "RotoPaint", "Tracker", "CornerPin2D"]
version: "Nuke 17.1 documentation; planar tracking lives in the Roto/PlanarTracker node; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-05"]
---
# How to do planar tracking

## Applicability
Use for a surface that stays flat (wall, screen, sign, floor patch, side of a vehicle) or deforms only slightly, has texture, and is never fully hidden. PlanarTracker uses the whole patch, so it is usually steadier than a few point tracks. It describes the 2D motion (translate, rotate, scale, shear, perspective) of one plane; it does not give camera position, 3D depth or the motion of non-planar objects. For camera movement use topics/camera-tracking; for single-point jobs use topics/tracker.

## Workflow
1. Scrub the shot, choose the best frame where the whole plane is visible and unobstructed. This frame becomes the **reference frame** for everything downstream.
2. Create the node: PlanarTracker (a Roto node already in planar mode) or Roto/RotoPaint with a Bezier drawn around the plane. Shapes drawn in Roto show red; converted track objects show purple. In Roto, right-click the shape and choose planar-track this shape (fwd/bkwd or no tracking data).
3. Draw tightly on the planar surface only, ignoring bumps, moving foreground and soft edges.
4. Stacked planes: order shapes from nearest the camera (top of the list) to farthest; layers above the current one are held out automatically. Docs note a key matte (e.g. from Keylight) cannot currently be used as holdout.
5. Set expected Track Motion types in the viewer tools (Translation, Rotate, Scale, Shear, Perspective). Restrict them for simple motion; allow Perspective for camera moves.
6. Tracking tab: choose channels (track channels / image channels), pre-track filter (adjust contrast is recommended by the docs, grayscale is faster), enable adjust for luminance changes only if brightness really changes (slower, less accurate). clamp super-white, sub-zero limits patch values to 0-1; disable it to track using the full range of over-range footage.
7. Track forward and backward from the reference frame. If the plane is partly hidden, track the fully visible stretch first and then the rest separately; use keyframes and clear forwards/backwards/all to re-track.
8. Review by scrubbing with display planar surface and grid on; fix drift by moving the surface corners (enable planar surface editing) at keyframes and re-tracking, or use the Correction offset on the four CornerPin points.

## Verify
- Grid or surface outline stays glued to texture at the start, middle and end, and after occlusion.
- Jump to Go to Reference Frame: the plane matches your drawn shape exactly.
- Export a stabilize CornerPin (topics/apply-planar-track) and play it: the plane should hold still; remaining wobble is track error.

## Pitfalls
- Always start tracking from the reference frame; changing the reference later changes all relative transforms.
- Textureless or occluded planes, repetitive patterns and fast motion blur drift.
- A plane in front of a moving background needs holdout layers, or the background pulls the track.
- Strongly non-planar motion slides; the docs report workable results on slightly deforming surfaces such as faces, but rigid planes track best.
- Do not call a planar track a 3D solve; depth, parallax and lens distortion remain unaccounted for.
- Course practice (lesson-05, teacher example): the frame where the planar shape is created becomes the reference frame and is what later frames are compared against; the grid helps check parallel lines on the surface and the surface can be corrected by hand. Official behaviour is in the Foundry pages above.

## Sources
- Foundry Nuke 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/planartracker/tracking_planar_surfaces.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/planartracker/tracking_plane.html (reference frame, layers, motion types, tracking tab, correction)
- Brinkmann 2e, ch. 8 "Tracking an Element into a Plate" and "Tracking Multiple Points" (four-point tracks give perspective).
- Lesson 05.srt (lesson-05, ASR transcript, teaching-practice only): 00:17:18–00:19:15 planar reference frame, grid and surface correction.
