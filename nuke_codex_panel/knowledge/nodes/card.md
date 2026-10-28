---
id: "nodes/card"
kind: "node"
title: "Card"
category: "3d-geometry"
summary: "Card is the simplest 3D object: a plane that carries a texture. It is used for pan-and-tile, matte paintings, projection targets and camera-space image planes. New 3D equivalent: GeoCard."
aliases: ["Card node", "image plane", "GeoCard", "3D card"]
tags: ["geometry", "plane", "texture", "matte painting", "lens-in"]
requires: ["fundamentals/coordinates"]
related: ["topics/geometric-primitives", "topics/set-extension", "topics/camera-projection", "topics/cg-backgrounds", "nodes/camera", "nodes/project3d"]
nodes: ["Card", "GeoCard"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Card

## Purpose
A plane for mapping a texture. It can be bent with bilinear or bicubic deformation or warped with the Lens Distortion tab. In classic 3D it renders through Scene and ScanlineRender; GeoCard creates a prim at a path such as /GeoCard1 in New 3D.

## Inputs
- `img`: the texture. GeoCard instead has an unnamed upstream-scene input and a `mat` input for a material.

## Controls
Classic scripting names: `orientation` (XY, YZ, ZX), `image_aspect` (match input shape; off gives a square card), `rows`, `columns` (default 8, max 4096), `z`, `lens_in_focal`, `lens_in_haperture`, distortion `lens_in_distort_a/b/c`, `lens_in_distortion`, `lens_in_power`, deform `type` (none, bilinear, bicubic), `render_mode`, `cast_shadow`, `receive_shadow`, and the usual transform knobs (`translate`, `rotate`, `scaling`, `uniform_scale`, `xform_order`, `rot_order`).

`z`, `lens_in_focal` and `lens_in_haperture` scale the card so it fills the stated camera's view at distance z, which gives camera-space image planes. GeoCard adds `prim_path`, `create_missing_parents`, `kind`, `purpose`, `visibility`.

## Verify
- View in 3D from the camera to confirm the card fills the expected frustum.
- Check orientation against the plate axis before animating.
- If the card is lens-distorted, confirm the same model as the plate lens.

## Pitfalls
- Disabling `image_aspect` stretches the image onto a square.
- High row/column counts can be unstable; use only what deformation needs.
- Check display versus render settings: `display` affects only the Viewer.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/card.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geocard.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
