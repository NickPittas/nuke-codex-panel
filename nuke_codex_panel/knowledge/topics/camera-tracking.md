---
id: "topics/camera-tracking"
kind: "topic"
title: "How to do camera tracking"
category: "camera-tracking"
summary: "Solve a 3D camera from parallax in a shot with CameraTracker, judge the solve, align it to the world and export it. A camera solve is not a 2D track: it needs a rigid scene and enough camera translation."
aliases: ["match move camera", "3D tracking", "solve camera", "CameraTracker", "camera solve", "matchmoving"]
tags: ["cameratracker", "solve", "parallax", "3d", "reprojection-error", "ground-plane"]
requires: ["fundamentals/coordinates", "fundamentals/channels-data"]
related: ["topics/lens-distortion", "topics/pointcloud-meshing", "topics/camera-projection", "topics/matchmove", "topics/planar-tracking"]
nodes: ["CameraTracker", "Camera", "Roto", "LensDistortion", "ScanlineRender", "Scene"]
version: "Nuke 17.1 documentation; CameraTracker is NukeX/Studio only; check installed node generation (classic or new 3D) and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-08"]
---
# How to do camera tracking

## Applicability
Use when 3D objects, projections or point clouds must follow a moving camera. The solver needs a rigid, textured scene and parallax (camera translation, depth variation). A tripod pan has no parallax: choose **Rotation Only** (cameraMotionLink) and expect no usable depth or scale. A camera solve does not track independently moving objects (an actor, a galloping horse); use planar/2D tracking for those (topics/planar-tracking). CameraTracker needs NukeX or Nuke Studio; results work in plain Nuke.
Course practice (lesson-08): prefer one shared camera to several 2D tracks when distortion, scarce features or several planes defeat 2D.

## Workflow
1. Decide the lens domain first. If the plate is already undistorted by a LensDistortion node, leave Lens Distortion at **No Lens Distortion**; otherwise set **Unknown Lens** before solving (topics/lens-distortion).
2. Connect the plate to **Source**. Mask moving objects and burn-ins with a Roto into **Mask** and set Mask to the matching mode (e.g. Mask Alpha). Masks may be rough.
3. Enter what is known: Camera Motion (Free Camera, Linear, Planar, Rotation Only), Focal Length type (Known / Approximate / Unknown, Constant or Varying), Film Back Size with matching Units. Wrong or mismatched film back/focal units corrupt the solve.
   Film back is the sensor area actually used (crop or high-frame-rate modes use less); take it and the lens from metadata or a camera report.
4. Tick Preview Features; features should spread evenly (docs advise >100 tracks per frame). Adjust Number of Features, Detection Threshold, Feature Separation, then **Track**.
5. Before solving, clean by length: on the AutoTracks tab inspect the num tracks and track-length curves, **raise** Min Length to reject short tracks (they turn red below the threshold), **Delete Rejected**, then **Update Track** over any thinned frame range. Delete drifting or jumping tracks by hand and add User Tracks for weak areas.
6. **Solve**, then review Error (RMS pixels; the docs' rule of thumb is above 1.0 px, refine tracks or settings). After this initial solve, clean by reprojection error: **reduce** Max Track Error (rejects tracks by RMS reprojection error) and **reduce** Max Error (rejects tracks with a large error on isolated frames); these thresholds apply to the error curves, which exist only once a solve exists. Tracks within the limits are inliers and are reused when you **Update Solve**; use **Delete Rejected**, then re-solve or Update Solve and recheck Error.
   Course practice (lesson-08): delete unsolved and rejected tracks, refine only genuinely unknown focal length/position/rotation, repeat until none are rejected; thresholds can drop good tracks, so inspect.
7. Set ground plane, axes or origin (right-click solved points, ground plane menu); add scale constraints from a measured distance (units are your choice, one Nuke unit equals your unit).
   Use solved points truly on the floor for the ground plane.
8. Export: Camera (Link output on = expression linked, off = baked), Scene, Point cloud, Distortion/Undistortion, Cards. The **New 3D** checkbox picks new-system (red) or classic (green) export nodes.

## Verify
- Per-frame error curve has no spikes; reprojected points sit on their features while scrubbing.
- Place a test card or cube on the aligned ground at a known feature and scrub the full range: it must stay locked, not swim or slide.
- Check the scale of the placed object against a known measurement.

## Pitfalls
- Low RMS can still be wrong when tracks cluster in one depth plane or on a moving object.
- Greenscreen and striped patterns cluster or confuse features; check Preview Features.
- Scale and orientation are arbitrary until aligned and constrained.
- CG rendered through the solved camera has no lens distortion; add the matching distortion or undistort the plate.
- Baked camera does not follow later re-solves; linked camera does.
- Do not promise a camera when the shot has no parallax; say so and propose a different approach.

## Sources
- Foundry Nuke 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/camera_tracking.html (quick start)
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/cameratracker.html (controls, export, New 3D)
- https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/camera_settings.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/masking.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/tracking_sequences.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/troubleshooting_sequences.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/setting_groundplane.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/creating_contraints.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/creating_cameras.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html (CameraTracker shared by both 3D systems)
- Brinkmann, The Art and Science of Digital Compositing 2e, ch. 8 "Camera Tracking" (camera tracking gives camera motion only; lens distortion can hurt tracking).
- Lesson 08.srt (lesson-08; ASR): 00:33:41–00:36:48 film back; 00:56:56–01:01:40 refine; 01:02:32–01:05:20 ground plane.
