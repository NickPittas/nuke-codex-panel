---
id: "nodes/pointcloudgenerator"
kind: "node"
title: "PointCloudGenerator"
category: "point-clouds"
summary: "PointCloudGenerator builds a dense point cloud from a CameraTracker camera and the source footage (analysis in NukeX or Nuke Studio). New 3D counterpart: GeoGeneratePoints, documented as NukeX only."
aliases: ["Point Cloud Generator", "dense point cloud", "GeoGeneratePoints", "dense tracking"]
tags: ["point cloud", "dense", "camera tracker", "mesh"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["topics/pointcloud-meshing", "topics/camera-tracking", "topics/geometry-from-images", "nodes/cameratracker", "nodes/poissonmesh", "nodes/modelbuilder"]
nodes: ["PointCloudGenerator", "GeoGeneratePoints", "CameraTracker", "PoissonMesh"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# PointCloudGenerator

## Purpose
Creates a dense point cloud, a starting point for 3D modelling and object placement, from the solved camera and original footage. The analysis must be done in NukeX (or Nuke Studio); the result can be used in Nuke. Dense clouds then feed PoissonMesh (GeoPointsToMesh in New 3D) or ModelBuilder reference.

## Inputs
- `Camera`: the camera track of the scene.
- `Mask`: optional; non-black areas are used by default (`ignore` sets alpha/luminance behaviour).
- `Source`: the footage the camera was solved from.

## Controls
Scripting names: `analyzeSequence` then `keyframes`, `addKeyframe`, `frameSpacing` (15), `addAllKeyframes`, `accuracy` (calculated depth accuracy); dense tracking `pointSeparation` (2 px), `matchThreshold` (0.5), `track`, `clearPoints`; post filter `minTriAngle` (1 degree), `densityThreshold`, `deleteRejected`, `displayRejectedPoints`; output `pointSize`, `outputPerFrame`; group display `displayGroups`, `outputGroups`; `principalView` for stereo.

## Verify
- Point cloud lines up with the footage at several frames when viewed through the solved camera.
- Use `outputPerFrame` to inspect each frame's points and delete rejected points to clean up.

## Pitfalls
- Poor camera solves give misaligned clouds.
- Lower point separation means denser, heavier clouds.
- Frame ranges for tracking use standard Nuke notation (e.g. 1-19, 40-60).

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/pointcloudgenerator.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geogeneratepoints.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
