---
id: "topics/pointclouds-from-cg"
kind: "topic"
title: "Creating point clouds from CG renders"
category: "advanced-3d"
summary: "Build a 3D point cloud from a CG position pass, or from a depth pass plus the render camera, using PositionToPoints, DepthToPosition or DepthToPoints. Depth and position are different data and depth needs its type and camera interpreted correctly."
aliases: ["PositionToPoints", "DepthToPosition", "DepthToPoints", "position pass to points", "depth to point cloud", "P pass", "z depth to 3D", "GeoPoints"]
tags: ["position-pass", "depth", "pointcloud", "1/z", "camera", "normals", "aov"]
requires: ["fundamentals/channels-data", "fundamentals/coordinates", "topics/channels"]
related: ["topics/multipass-cg", "topics/pointcloud-meshing", "topics/3d-particles", "topics/camera-tracking"]
nodes: ["PositionToPoints", "DepthToPosition", "DepthGenerator", "Camera", "ScanlineRender"]
version: "Nuke 17.1 documentation; classic PositionToPoints/DepthToPoints vs new-3D GeoPoints; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# Creating point clouds from CG renders

## Applicability
Use when a render carries scene geometry as an AOV. Two inputs differ:
- **Position pass (P)**: each pixel stores x, y, z of the surface point. It needs no camera to become points.
- **Depth pass (Z)**: each pixel stores only distance to the camera in the renderer's convention. Rebuilding 3D needs the matching camera and the correct depth type. A pixel holds one depth, so transparent regions are unreliable (Brinkmann: Z compositing is problematic with transparency) and anti-aliased or motion-blurred edges likely mix depths [INFERENCE].
Neither gives hidden surfaces: the cloud is only what the camera saw. Check the position pass coordinate space (world vs camera, units, up axis) with the renderer; the Nuke pages do not define it. For shots without CG passes use CameraTracker/DepthGenerator (topics/camera-tracking).

## Workflow
1. Read the EXR with the data layers kept as float and not colour transformed (fundamentals/channels-data). Confirm the P, N and depth channels exist via the Viewer channel list.
2. Position pass: PositionToPoints; set surface point to the P channels (and surface normal if present), or connect separate streams to the hidden pos and norm inputs (these appear after the main input is connected, and then override the dropdowns). The main input also supplies color.
3. Depth pass: DepthToPosition with the render's camera on the camera input; set depth to the depth channel, tick invert depth if it is Z rather than 1/Z, and set far (depths beyond it are ignored, which avoids banding from float precision); then feed PositionToPoints. DepthToPoints is a gizmo that bundles both. In new 3D, GeoPoints takes cam, src, P/N channels or a depth channel with a depth type (Z, 1/Z, -Z, -1/Z; Nuke and RenderMan default 1/Z, Maya -1/Z), and can take deep data.
4. DepthGenerator output differs: Depth (1/Z) matches ScanlineRender; Distance is along the camera ray, so do not interchange them.
5. Adjust point detail (fraction of available points shown) and point size; cloud may look empty if alpha is black or points are too small.
6. Feed the cloud to ParticleEmitter emit input, a mesh step, or reference for alignment. Meshing needs normals and quality filtering (topics/pointcloud-meshing).

## Verify
- Points reproduce a known object: its size, position and orientation match a locator or primitive in the same scene.
- DepthToPosition result viewed as RGB should vary smoothly across surfaces; banding or flat regions suggest the wrong depth type, inverted depth or an overly large far.
- Switch the Viewer to the render camera: the cloud must re-project onto the original frame.
- Compare with the scene's world axes by placing an Axis or a Card at a known coordinate.

## Pitfalls
- Reading depth as distance or Z as 1/Z gives plausible but warped shape.
- Anti-aliased silhouettes produce stray points between foreground and background; use masks or filtering/density settings.
- Camera mismatch (film back, focal length, frame offset or scale) skews the cloud only for depth-based pipelines, not for P-pass ones.
- Colour management on data layers moves points.
- PositionToPoints is a visualisation or modelling aid; the cloud is not a mesh and has no occlusion information for unseen areas.

## Sources
- Foundry Nuke 17.1: https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/positiontopoints.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/using_positiontopoints.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/depthtoposition.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/depthtopoints.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/depthgenerator.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/using_depthtoposition.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/using_depthtopoints.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geopoints.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/create-point-cloud.html
- Brinkmann 2e, ch. 14 "Working with CG Elements" and "Z-Depth Compositing" (depth relative to camera or origin, limitations with transparency).
