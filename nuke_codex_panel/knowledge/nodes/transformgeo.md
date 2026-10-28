---
id: "nodes/transformgeo"
kind: "node"
title: "TransformGeo"
category: "3d-geometry"
summary: "TransformGeo translates, rotates, scales and skews classic 3D geometry, optionally driven by an Axis or aimed with look. New 3D equivalent: GeoTransform, which targets prims through a Mask."
aliases: ["Transform Geo", "GeoTransform", "3D transform", "GeoXform"]
tags: ["transform", "axis", "look at", "geometry"]
requires: ["fundamentals/coordinates"]
related: ["topics/geometry-animation-deformation", "topics/geometric-primitives", "topics/3d-navigation", "nodes/axis", "nodes/card"]
nodes: ["TransformGeo", "GeoTransform", "GeoXform", "Axis"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# TransformGeo

## Purpose
Moves a whole object or a MergeGeo group together in 3D space without editing each primitive.

## Inputs
- Unnamed: geometry (or MergeGeo for several objects).
- `look`: optional camera or 3D object to face.
- `axis`: optional Axis that overrides the node's own transform controls.

New 3D GeoTransform has unnamed (scene stage), `look at`, and `axis` inputs; its `mask_patterns` (Mask) choose the prims affected and `inject_mask` passes that mask to the node below if the latter has the default mask.

## Controls
Scripting names: `render_mode`, `transform_normals` (leave off in most cases), `translate`, `rotate`, `scale` (classic TransformGeo's scripting name), `skew`, `pivot`, `xform_order` (default SRT), `rot_order` (default ZXY), `useMatrix`, `matrix`; Look tab `look_axis` (+Z), `rotate_x/y/z`, `look_strength`, `use_quaternions`.

GeoTransform adds `pivot_translate`, a Snap menu and `geosnap_*` options. For direct Xform prim work the docs point to GeoXform.

## Verify
- Check pivot and transform order with a simple primitive first.
- Confirm that the Axis (not local values) drives the object if connected.
- Rotate along known angles and look at the Viewer handles.

## Pitfalls
- Axis connections overwrite local values.
- Look-at needs all three rotate axes on for a true aim.
- Quaternions only help with erratic look rotations.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/transformgeo.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geotransform.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
