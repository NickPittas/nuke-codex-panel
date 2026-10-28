---
id: "nodes/positiontopoints"
kind: "node"
title: "PositionToPoints"
category: "point-clouds"
summary: "PositionToPoints builds a 3D point cloud from an xyz position image, such as a position pass from CG. In New 3D the documented counterpart is GeoPoints. DepthToPosition and DepthToPoints derive positions from depth plus camera."
aliases: ["Position To Points", "position pass to point cloud", "GeoPoints", "DepthToPoints", "DepthToPosition", "P pass points"]
tags: ["point cloud", "position pass", "depth", "cg"]
requires: ["fundamentals/channels-data", "fundamentals/coordinates"]
related: ["topics/pointclouds-from-cg", "topics/multipass-cg", "topics/geometry-from-images", "nodes/scanlinerender", "nodes/particleemitter", "nodes/camera"]
nodes: ["PositionToPoints", "GeoPoints", "DepthToPoints", "DepthToPosition"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# PositionToPoints

## Purpose
Reads an xyz image channel set as point positions, taking point colour from the image. A ScanlineRender can output world-space surface positions (and normals) into channels with `output_shader_vectors`; use those channels (or a CG position pass) as the source. Emitter points can come from the cloud.

## Inputs
- Unnamed: image with xyz data and the colour.
- `pos`: image containing positions (hidden until unnamed input is connected).
- `norm`: image with normals (hidden until `pos` is connected).

## Controls
Scripting names: `P_channel`, `N_channel` (ignored when the `pos`/`norm` inputs are used), `detail` (0.5; 1 shows all available points), `pointSize` (5), `render_mode`, `cast_shadow`, `receive_shadow`, `frame_first`, `frame_last`.

Depth-based alternatives: DepthToPosition (inputs `camera` and `image`; knobs `output`, `depth`, `invert`, `far`) creates the position pass; DepthToPoints is a gizmo combining it with PositionToPoints. GeoPoints (New 3D) also takes a `cam` input for depth projection and `P_channel`, `N_channel`, `color_channel`, `point_size`.

## Verify
- Compare points with the render in 3D from the same camera.
- Check that the correct channels are selected (not rgba by mistake).

## Pitfalls
- Know the coordinate space of the position pass; ScanlineRender writes world space. Mismatched spaces misplace points [inference].
- Z depth must be correct (invert when z, not 1/z, for DepthToPosition).
- `detail` only limits how many points are displayed in the Viewer (0 shows none, 1 all).

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/positiontopoints.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/depthtoposition.html and https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/depthtopoints.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geopoints.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
