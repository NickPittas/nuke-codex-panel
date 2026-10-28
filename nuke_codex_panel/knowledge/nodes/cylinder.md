---
id: "nodes/cylinder"
kind: "node"
title: "Cylinder"
category: "3d-geometry"
summary: "Cylinder creates an adjustable cylinder with radius, height, wrap extent and optional end caps. New 3D equivalent: GeoCylinder."
aliases: ["Cylinder node", "GeoCylinder", "3D cylinder", "pan and tile cylinder"]
tags: ["primitive", "geometry", "cylinder", "uv"]
requires: ["fundamentals/coordinates"]
related: ["topics/geometric-primitives", "topics/cg-backgrounds", "nodes/sphere", "nodes/cube", "nodes/card"]
nodes: ["Cylinder", "GeoCylinder"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Cylinder

## Purpose
A cylindrical surface for wrapped backgrounds, columns and proxy shapes.

## Inputs
- `img`: texture on the outer surface. The end caps extrapolate the image edge toward the centre when closed.

## Controls
Classic scripting names: `radius` (1), `height` (2), `rows` and `columns` (30 each, max 512), `u_extent` (360), `close_top`, `close_bottom` (both off by default), `render_mode`, `cast_shadow`, `receive_shadow`, `frame_first`, `frame_last`, transform knobs.

Foundry's New 3D mapping lists GeoCylinder as the counterpart; its page was not read for this reference, so check its controls in the installed build.

## Verify
- Check height and radius, and that the open ends match what the shot needs.
- Rotate to inspect the UV seam.

## Pitfalls
- Open ends are the default.
- A `u_extent` under 360 closes the remainder by stretching image edges.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/cylinder.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
