---
id: "nodes/modelbuilder"
kind: "node"
title: "ModelBuilder"
category: "3d-modeling"
summary: "ModelBuilder creates simple 3D models for 2D shots by drawing shapes and aligning them to a tracked camera and footage. Creating and editing requires NukeX; the migration table lists no New 3D equivalent."
aliases: ["Model Builder", "3D modelling from footage", "image based modelling", "bake projection"]
tags: ["modeling", "camera", "geometry", "projection", "uv"]
requires: ["fundamentals/coordinates"]
related: ["topics/geometry-from-images", "topics/pointcloud-meshing", "topics/set-extension", "nodes/cameratracker", "nodes/pointcloudgenerator", "nodes/poissonmesh"]
nodes: ["ModelBuilder", "CameraTracker", "PointCloudGenerator"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# ModelBuilder

## Purpose
Builds proxy geometry for a shot: create shapes, edit them, then drag vertices onto their 2D locations in Align mode. It needs a tracked camera and an input image for alignment; without them you can still model but not align. Documented as NukeX and Nuke Studio only; the produced geometry can be used in Nuke. Foundry's classic-to-New table lists no equivalent node.

## Inputs
- `geo`: reference geometry, e.g. a PointCloudGenerator point cloud.
- `cam`: tracked camera.
- `src`: footage the camera was derived from.
- `tex`: optional 2D texture for UV preview and the model.

## Controls
Scripting names: `render_mode`, `cast_shadow`, `receive_shadow`, `sceneAdd`, `sceneDelete`, `sceneCopy`, `shapeDistance` (10, distance from the camera for new shapes), `textureType` (current frame, locked frame, frame difference), `textureFrame`, `previewTexture`, `bakeMenu`, `bake`, `srcDisplay`.

The bake menu can create geometry for selected items or a projection setup (a Project3D with a FrameHold that locks image and camera to the texture frame), which pairs with ApplyMaterial on the baked geometry.

## Verify
- Check alignment on several frames, not just one.
- Compare the model against the point cloud from different angles.

## Pitfalls
- Alignment needs a good camera solve.
- Projected texture follows `textureType`: current frame changes per frame, locked frame holds the chosen `textureFrame`.
- Scale has no specific units; `shapeDistance` is relative.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/modelbuilder.html
- Classic-to-New mapping: https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
