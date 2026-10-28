---
id: "topics/lens-distortion"
kind: "topic"
title: "Compensating for lens distortion"
category: "camera-tracking"
summary: "Undistort the plate or distort the CG, but track every distortion state once and apply the inverse consistently. Covers LensDistortion modes, STMap forward/backward layers and CameraTracker interaction."
aliases: ["undistort", "redistort", "LensDistortion", "STMap distortion", "lens grid", "distortion workflow", "defish"]
tags: ["lensdistortion", "stmap", "undistort", "redistort", "bbox", "overscan", "filtering"]
requires: ["fundamentals/coordinates", "fundamentals/filtering-concatenation", "fundamentals/channels-data"]
related: ["topics/camera-tracking", "topics/tracker", "topics/rendering-3d", "topics/cg-backgrounds"]
nodes: ["LensDistortion", "STMap", "CameraTracker", "ScanlineRender", "Reformat"]
version: "Nuke 17.1 documentation; LensDistortion analysis is NukeX/Studio only, results run in Nuke; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# Compensating for lens distortion

## Applicability
CG and 3D camera solves assume an ideal pinhole lens; real plates are distorted. Choose one strategy and keep it for the whole shot:
- **Undistort-comp-redistort**: remove distortion from the plate, track and comp in undistorted space, redistort only the VFX layer and merge over the original plate (original pixels stay untouched).
- **Distort the CG only**: leave the plate alone and distort the render to match.
Pick undistort workflows when tracking or matching straight lines matters; choose distort-the-CG when the plate must keep its original pixels.

## Workflow
1. Best input: a grid or chart shot with the same lens, focal length and format. Set Lens Type (Spherical or Anamorphic, with Squeeze/Twist/Scale), Model Preset (NukeX Classic, CaraVR, 3DEqualizer, Custom) and, for fisheye, the Projection Model with Focal Length and Sensor Size.
2. Analysis tab: **Detect** (Current Frame or Every N Frames), then **Solve**; inspect link errors (red = outside threshold). No grid: draw straight lines manually (line analysis).
3. Undistort: LensDistortion Mode Undistort on the plate. Track and matchmove here. Watch BBox and Output Format (undistorting expands the image; outside data is overscanned/edge-extended).
4. Redistort: paste the same node downstream of the VFX only, Mode Redistort, merge over the original plate.
5. Reusable warp: Mode STMap writes undistort and redistort maps in the motion channels. Forward channels remove distortion, backward channels add it. Apply with STMap nodes (src input, stmap input, UV channels set to forward or backward).
6. With CameraTracker: if the plate was undistorted beforehand, Lens Distortion = No Lens Distortion. Otherwise choose Unknown Lens, then export Distortion (applies it to CG; connect after ScanlineRender), Undistortion (removes it from the plate and feeds ScanlineRender bg), or enable Undistort Input on the tracker.

## Verify
- Straight scene lines (door frames, grid) are straight in Undistort mode with the overlay on.
- Round trip: undistort then redistort the plate; difference against the original should be near zero except filter softening and edges.
- CG edges and plate edges line up at the frame corners, where distortion is greatest.
- Format/bbox of the redistorted layer equals the plate format.

## Pitfalls
- Tracking a distorted plate and then placing CG through an undistorted camera (or the reverse) causes drift toward frame edges.
- Distortion is resampling: undistorting then redistorting the full plate softens it twice; filter only the VFX layer.
- STMap data is data, not color; keep it float and out of color transforms (fundamentals/channels-data). Different format between map and image misplaces pixels.
- Calibrate with the same focal length and focus as the shot; zoom or focus breathing needs keyframed analysis or Scale controls.
- Do not mix a CameraTracker-estimated lens and a separate LensDistortion on the same plate.

## Sources
- Foundry Nuke 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/lens_distortion/adding_removing_lens_distortion.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/lens_distortion/analyzing_distortion_grid.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/lens_distortion/removing_distortion.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/lens_distortion/applying_distortion.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/lens_distortion/working_with_stmaps.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/lensdistortion.html (modes, STMap, bbox, filter)
- https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/lens_distortion.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/camera_settings.html
- Brinkmann 2e, ch. 2 (lens imperfections, barrel distortion) and ch. 8 (distortion can break tracking).
