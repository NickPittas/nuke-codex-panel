---
id: "topics/rig-removal"
kind: "topic"
title: "Rig removal"
category: "production-workflows"
summary: "Remove wires, rigs and stand-ins by first choosing a method from camera motion and background complexity: static clean-plate patch, tracked 2D patch, projected clean plate on geometry, or the FurnaceCore F_RigRemoval plug-in."
aliases: ["wire removal", "rig removal", "clean plate patch", "remove object from shot", "paint out", "f_rigremoval", "clean plate"]
tags: ["cleanup", "clean plate", "roto", "tracking", "projection", "production"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/time-sampling", "fundamentals/coordinates", "fundamentals/quality-safeguards"]
related: ["topics/camera-projection", "topics/rotoscoping-masking", "topics/tracker", "topics/planar-tracking", "topics/apply-planar-track", "topics/set-extension", "topics/optical-flow-retiming"]
nodes: ["RotoPaint", "Roto", "Tracker", "CornerPin", "FrameHold", "TimeOffset", "Merge", "Project3D", "Project3DShader", "Card", "F_RigRemoval"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions", "lesson-06", "lesson-07"]
---
# Rig removal

## Applicability
A rig is anything in the plate that must disappear: wires, harnesses, stands, markers. Everything depends on whether clean background pixels exist and how that background moves. Pick by shot:
1. Locked-off camera, static background: a clean plate (shot clean, or a frame or span where the rig is absent) patched in with a mask. Brinkmann (Ch. 12 "Clean Plates") says this works best with matched camera, lighting and exposure, so it is most common for non-moving cameras.
2. Camera moves but the patch area is a flat or near-flat surface: take clean pixels from another frame, stabilize with a track, patch, then reapply the motion (Tracker/CornerPin; see topics/tracker, topics/apply-planar-track). Brinkmann notes tracking can add motion to a clean plate to match the camera move.
3. Camera moves and the background has depth/parallax: solve the camera and project a clean frame onto approximating geometry (topics/camera-projection). Parallax and occluded areas limit this.
4. Rig moves over a background whose motion is a global 3D transform: FurnaceCore F_RigRemoval estimates background motion and searches earlier and later frames for fill. Foundry says results are poor when the background has several objects moving in different directions, and that it suits cases where an artist could have tracked in a clean plate. Installed availability and licence are unverified here; check them.
Optical-flow or neighbor-frame borrowing can also generate a clean plate (Brinkmann Ch. 12).

## Workflow
1. Inspect the whole shot: where does the rig overlap what? Find frames where the background behind it is visible, and note rig shadows, reflections and motion blur.
2. Build the mask first: Roto/RotoPaint matte that covers the rig and its blur, shadow and edge fringe. Animate it, and soften it; remember motion blur extends the matte area (Brinkmann Ch. 6 motion blur discussion).
3. Source the clean pixels: FrameHold/TimeOffset to pick frames; Project3D from a held frame on a Card or geometry; or a separate clean plate matched in format and color.
4. Match the patch to the plate: grade, grain, sharpness and lens distortion; apply the same image state (alpha/premult) used by the plate before Merge, with the matte as mask.
5. Composite: Merge (over) the patch through the mask onto the plate, or paint with RotoPaint clone from the held frame.

## Verify
- Play at speed and frame-by-frame; flicker, pops and boundary shimmer show mismatch in tracking, grade or grain.
- Check matte edges and the rig's shadow/reflection; wipe against the original.
- Check against transparent or motion-blurred areas of the foreground.
- If using a projected patch, scrub through the full camera move.

## Pitfalls
- A clean plate only repairs what it matches; mixed lighting, exposure drift and perspective change appear immediately.
- A 2D patch on a moving camera slides unless tracked; a tracked flat patch fails across depth discontinuities.
- Do not assume F_RigRemoval is available in every license; a licence/plugin gap makes the node unavailable.
- Over-cleaning grain or texture produces a visible soft patch; always compare grain.
- Camera-projected patches may need lens-distortion handling (topics/lens-distortion).
- One monolithic RotoPaint with hundreds of strokes is slow to review and hard to revise. Split by purpose, region and time span (one RotoPaint or clone patch per logical task) and chain them on the B trunk; no fixed stroke limit applies. Cleanup runs before keying, so keep the cleaned RGB as a deliberate branch (studio preference, `fundamentals/quality-safeguards`).
- Projected or CornerPinned patches can create very large bounding boxes; check bbox on all frames and contain the patch to the background window just before its Merge.
- Stabilize, paint, restore (course practice, lessons 06-07): to paint on a moving flat region, stabilize with a track, paint, then undo it with a copy of the same track set opposite. With the paint disabled the pair must return the untouched plate. A contrast grade added only to help a tracker lock stays out of the image path.
- Paint lifetime: a stroke exists only on its painted frame unless lifetime says otherwise. Set each stroke's intended span: a patch that must persist across a stabilized range needs it; a one-frame fix stays limited. Play the full range to catch pops.
- With a large rig, rough-roto the frame where all of it is visible to choose the clean area; refine afterwards.

## Sources
- Foundry 17.1: https://learn.foundry.com/nuke/17.1/content/furnacecore/rigremoval.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/time_nodes/framehold.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/projection_cameras.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/project3d.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/modelbuilder/projecting_textures.html
- Brinkmann 2e Ch. 12 "Creating Elements": "Clean Plates", "Matched Cameras"; Ch. 6 matte motion blur; Ch. 13 "Camera Movements".
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): split paint tasks, cleanup-before-key order, bbox containment.
- Lesson 06.srt (lesson-06; ASR, teaching-practice only): 00:20:48–00:25:40 stabilize, paint, restore.
- Lesson 07.srt (lesson-07; ASR, teaching-practice only): 00:13:00–00:13:26 rough roto first; 00:45:54–00:46:15 paint lifetime.
