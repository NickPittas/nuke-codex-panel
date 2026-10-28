---
id: "nodes/sphere"
kind: "node"
title: "Sphere"
category: "3d-geometry"
summary: "Sphere creates an adjustable textured sphere primitive for classic 3D, useful for spherical environments and proxies. New 3D equivalent: GeoSphere."
aliases: ["Sphere node", "GeoSphere", "3D sphere", "sky dome proxy"]
tags: ["primitive", "geometry", "sphere", "uv"]
requires: ["fundamentals/coordinates"]
related: ["topics/geometric-primitives", "topics/cg-backgrounds", "nodes/cube", "nodes/cylinder", "nodes/card"]
nodes: ["Sphere", "GeoSphere"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Sphere

## Purpose
Procedural sphere with UVs, for proxy volumes, spherical environment mapping and basic scene blocking.

## Inputs
- `img`: texture to wrap on the surface.

## Controls
Classic scripting names: `radius` (1), `rows` and `columns` (30 each, max 512), `u_extent` (360), `v_extent` (180), `close_top`, `close_bottom` (both on), `render_mode`, `cast_shadow`, `receive_shadow`, `frame_first`, `frame_last`, and the usual transform knobs.

`u_extent` and `v_extent` set how far the input image wraps; any remainder is closed by extrapolating the image edges (docs example: 180 wraps the image 90 degrees each side of the y axis).

## Verify
- In 3D, check radius and orientation; at default extents the image should wrap fully around.
- Rotate and inspect the poles for UV pinching.

## Pitfalls
- Few rows/columns produce visible facets; high values cost memory (max 512).
- Extents below the full sphere give stretched edge pixels over the remainder.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/sphere.html
- New 3D mapping (GeoSphere listed as counterpart; its page was not read): https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
