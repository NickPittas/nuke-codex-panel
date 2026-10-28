---
id: "nodes/displacegeo"
kind: "node"
title: "DisplaceGeo"
category: "3d-geometry"
summary: "DisplaceGeo moves each vertex of 3D geometry along its normal using an image sampled at the vertex UV. New 3D counterpart: GeoDisplace."
aliases: ["Displace Geo", "GeoDisplace", "displacement map", "vertex displacement"]
tags: ["displacement", "geometry", "deform", "uv"]
requires: ["fundamentals/channels-data", "fundamentals/coordinates"]
related: ["topics/geometry-animation-deformation", "topics/geometric-primitives", "nodes/card"]
nodes: ["DisplaceGeo", "GeoDisplace", "Displacement", "Card"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# DisplaceGeo

## Purpose
Adds detail or deformation to geometry from an image without modelling: each vertex is displaced along its normal by the value of the pixel its `uv` attribute points to. Higher pixel values displace more.

## Inputs
- Unnamed: geometry, e.g. a Card, or MergeGeo for several objects.
- `displace`: the displacement image.
GeoDisplace: `displace` plus the scene-stage unnamed input and a `mask_patterns` mask.

## Controls
Scripting names: `render_mode`, `channels` (rgb), `source` (luminance by default, or a chosen channel), `scale` (0.1), `weight` (1,1,1 per axis), `offset` (0,0,0), `filter_size` (5), `filter` (Parzen), `uv_attrib_name` (uv), `recalc_normals` (on).

## Verify
- Use a clearly patterned image (noise or ramp) and view in 3D wireframe/shaded.
- Check displacement direction by inverting the image.
- Confirm normals look right after displacement.

## Pitfalls
- Vertices move, so low subdivision means coarse deformation; raise Card rows/columns.
- Missing or wrong UVs give wrong sampling.
- `weight` and `offset` are per-axis; leave them at defaults until the basic result is right.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/displacegeo.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geodisplace.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
