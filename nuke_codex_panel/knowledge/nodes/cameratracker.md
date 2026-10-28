---
id: "nodes/cameratracker"
kind: "node"
title: "CameraTracker"
category: "tracking-3d"
summary: "CameraTracker auto-tracks 2D features and solves a camera path and 3D points for match-moving. Documented for NukeX and Nuke Studio only; it exports cameras, scenes, point clouds and lens-distortion nodes."
aliases: ["Camera Tracker", "3D camera tracking", "matchmove solve", "camera solve"]
tags: ["tracking", "solve", "matchmove", "camera", "point cloud", "lens"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["topics/camera-tracking", "topics/matchmove", "topics/lens-distortion", "nodes/camera", "nodes/pointcloudgenerator", "nodes/lensdistortion", "nodes/scene"]
nodes: ["CameraTracker", "Camera", "LensDistortion"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# CameraTracker

## Purpose
Creates a virtual camera whose motion matches the real one, so 3D elements can be added to 2D footage. Documented as NukeX and Nuke Studio only; confirm the installed licence before planning a solve.

## Inputs
- `Source`: the sequence to track.
- `Mask`: optional, hidden until Source is connected; the `ignore` knob chooses how mask or source alpha excludes areas (None, Source Alpha, Mask Luminance and inverted variants).

## Controls
Analysis flow, scripting names: `trackFeatures` (Track), `solveCamera` (Solve), `updateTrack`, `updateSolve`, `clearTrack`, `resetSolve`, `solveRMSE` (RMS error in pixels), `solveError` (per frame).

Set-up knobs: `sourceType` (Sequence or Stills), `trackRange`, `cameraMotionLink` (Rotation Only, Free Camera, Linear Motion, Planar Motion), `focalLengthType` (Known, Approximate Varying/Constant, Unknown Varying/Constant) with `knownFocalLength`, `filmBackSize`, `filmbackUnits`, `undistort`.

Settings tab: `numberFeatures` (150; docs suggest more than 100 per frame), `featureThreshold`, `featureSeparation`, `minTrackLength`, `matchThreshold`, `smoothnessThreshold`, `consistencyThreshold`. Cleanup: `minLengthThreshold`, `maxRMSEThreshold`, `maxErrorThreshold`, `refineSolve`, `deleteRejectedTracks`.

Export: `exportMenu` (Camera, Camera rig, Scene, Scene+, Point cloud, Distortion, Undistortion, Cards) then `exportButton`; `linkOutput` and `new3D` (default on) choose linked output and the 3D system of the created nodes.

## Verify
- Solve error: the docs give an RMS above 1.0 pixel as a reason to refine.
- Inspect track-length and error curves; reject short or high-error tracks, then Update Solve.
- Place a test Card at a solved point and confirm it sticks through the shot.

## Pitfalls
- Unknown lens distortion: choose Unknown Lens or undistort first, or the solve absorbs it.
- Moving objects and reflections need masking.
- The migration table says to uncheck a "Classic 3D" checkbox for New 3D, while the knob table lists `new3D`; read the panel label in the installed build.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/cameratracker.html
- Classic-to-New 3D mapping (CameraTracker shared by both systems): https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
