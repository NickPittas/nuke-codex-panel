---
id: "nodes/scanlinerender"
kind: "node"
title: "ScanlineRender"
category: "3d-nodes"
summary: "ScanlineRender renders a 3D scene through a camera to a 2D image; classic and New 3D versions share a name but differ. The New 3D one adds ray-traced reflections and refractions, AOVs and USD scene masks."
aliases: ["Scanline Render", "3D render node", "render 3D scene", "RayRender"]
tags: ["render", "motion blur", "z depth", "motion vectors", "classic 3d", "new 3d"]
requires: ["fundamentals/channels-data", "fundamentals/time-sampling", "fundamentals/coordinates"]
related: ["topics/rendering-3d", "topics/motion-blur-depth-of-field", "topics/camera-projection", "topics/cg-backgrounds", "nodes/scene", "nodes/camera", "nodes/light"]
nodes: ["ScanlineRender", "Scene", "GeoScene", "Camera"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# ScanlineRender

## Purpose
Turns a 3D scene into a 2D image seen from the camera on `cam`, defaulting to a default camera when none is connected. It can output deep data when a Deep node is downstream. In the New 3D system the same node name is a different node, also covering the old RayRender workflow; use 3D > 3D, not 3D Classic.

## Inputs
- `obj/scn`: classic: a Scene node or 3D object/MergeGeo; New 3D: GeoScene, GeoMerge, an object or prim.
- `cam`: optional render camera.
- `bg`: optional background; it composites into the render and determines output resolution (defaults to root format).

## Controls
Classic: `transparency`, `ztest_enabled`, `filter`, `antialiasing`, `projection_mode` (default render camera), `overscan`, `ambient`; MultiSample `samples`, `shutter`, `shutteroffset`; `motion_vectors_type` (distance recommended), `output_shader_vectors` with `P_channel` and `N_channel` (world-space positions/normals).

New 3D: `camera_sample_mode`, `projection_mode`, `shutter`, motion-blur toggles (`camera_motion_blur`, `object_motion_blur`, `light_motion_blur`), `ray_max_depth`, `lighting_enable_mode`, `shadowing_enabled`, `objects_mask`, `lights_mask`, and `one_over_z` (on gives classic 1/Z).

## Verify
- Check alpha, Z and motion-vector channels exist when needed.
- Compare output resolution with the bg or project format.
- `samples` above 1 add motion blur and antialiasing at render cost; shutter is in frames.

## Pitfalls
- Without `cam`, the default camera is used silently.
- 1/Z is not normalized Z.
- Overscan costs render area.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/scanlinerender.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/scanlinerender.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
