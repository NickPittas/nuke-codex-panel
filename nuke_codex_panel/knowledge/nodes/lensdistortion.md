---
id: "nodes/lensdistortion"
kind: "node"
title: "LensDistortion"
category: "lens"
summary: "LensDistortion estimates lens distortion from a calibration grid or drawn lines, then undistorts, redistorts or writes STMaps. Analysis is documented for NukeX and Nuke Studio; the solved node can run in Nuke."
aliases: ["Lens Distortion", "undistort", "redistort", "STMap lens", "lens calibration", "grid detection"]
tags: ["lens", "distortion", "undistort", "stmap", "calibration"]
requires: ["fundamentals/coordinates", "fundamentals/filtering-concatenation"]
related: ["topics/lens-distortion", "topics/camera-tracking", "nodes/cameratracker", "nodes/camera"]
nodes: ["LensDistortion", "CameraTracker", "STMap"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# LensDistortion

## Purpose
Models and removes lens distortion so tracking, projection and 3D elements are made on straight (rectilinear) imagery, then re-applies it so the CG matches the plate. Estimation uses Grid Detection (a calibration chart shot) or manual Line Detection; the docs require NukeX or Nuke Studio for analysis but say the results can be used in Nuke.

## Inputs
- `Source`: the sequence to warp.

## Controls
Scripting names: `distortionModelPreset` (NukeX Classic, CaraVR Radial Degree 3, 3DEqualizer, Custom), `lens` (Spherical or Anamorphic with `anamorphicSqueeze`, `anamorphicTwist`, `anamorphicScale`), `centre`, `output` (STMap, Undistort, Redistort), `useFisheye`, `filter`, `bboxType`, `outputFormatType`, `distortionScalingType`; analysis `detect`, `detectionFrameType`, `solveDistortion`, `deleteOutliers`, `errorThreshold` (10), `solveError` (RMS pixels), `resetDistortion`; feature detection settings such as `numFeatures` (5000), `featureSeparation`, `detectionThreshold`.

STMap mode writes undistortion (forward channels) and redistortion (backward channels) maps into the motion channels.

## Verify
- Straight lines in the scene should be straight in the undistorted view; check the overlay grid.
- Inspect `solveError` and rejected outliers; do not trust a low error with few features.
- Round trip (undistort then redistort) should return close to the plate [inference].

## Pitfalls
- Output bounding box and format change when undistorting; set BBox and format deliberately.
- `filter` resamples pixels, so choose it deliberately for plates versus data passes.
- Use one distortion model consistently between solving and re-applying it [inference].

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/lensdistortion.html
- CameraTracker `Lens Distortion` options (No Lens Distortion, Unknown Lens): https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/cameratracker.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
