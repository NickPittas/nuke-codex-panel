---
id: "nodes/cube"
kind: "node"
title: "Cube"
category: "3d-geometry"
summary: "Cube creates an adjustable box primitive with texture input and optional separate faces. New 3D equivalent: GeoCube, which also supports shared-vertex smoothing."
aliases: ["Cube node", "GeoCube", "3D cube", "box primitive"]
tags: ["primitive", "geometry", "box", "uv"]
requires: ["fundamentals/coordinates"]
related: ["topics/geometric-primitives", "topics/geometry-from-images", "nodes/sphere", "nodes/cylinder", "nodes/card"]
nodes: ["Cube", "GeoCube"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Cube

## Purpose
A rectangular primitive for blocking, projection targets and rough scene proxies.

## Inputs
- `img`: texture for the faces. GeoCube has a scene-stage input and `mat`.

## Controls
Classic scripting names: `rows`, `columns` (10 each, max 512), `separate_faces` (default on: faces do not share UV vertex data; turn off for continuous mapping), `cube` (default -0.5, 0.5; six values x, y, n, r, t, f set the left, bottom, back, right, top and front faces, seen from +Z), `render_mode`, `cast_shadow`, `receive_shadow`, transform knobs.

GeoCube (New 3D) is a prim at a path such as /GeoCube1; its Mesh Type can be shared vertices with a Subdivision option, and Viewer refine level affects only the Viewer, not the render.

## Verify
- View in 3D: extents and faces match what you typed.
- Apply a checker texture (e.g. through `img`) and confirm UVs per face.

## Pitfalls
- Non-uniform extents distort texture.
- Separate faces produce seams for continuous textures.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/cube.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geocube.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
