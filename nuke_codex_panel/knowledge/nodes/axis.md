---
id: "nodes/axis"
kind: "node"
title: "Axis"
category: "3d-nodes"
summary: "Axis is a null/locator object for parenting and constraining other 3D objects. Classic and New 3D versions share the name; New 3D adds Look At and Parent constraints."
aliases: ["Axis node", "null object", "locator", "parent axis"]
tags: ["axis", "null", "parent", "constraint", "transform"]
requires: ["fundamentals/coordinates"]
related: ["topics/3d-navigation", "topics/geometry-animation-deformation", "nodes/camera", "nodes/transformgeo", "nodes/reconcile3d"]
nodes: ["Axis", "TransformGeo", "Camera"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Axis

## Purpose
Adds a separate transform axis that other objects can follow. Rotating a parent Axis rotates everything connected to it, which is a common way to scale, shift or animate a scene as a group.

## Inputs
- `axis`: parent Axis.
- Classic `look`: Camera, Light or Axis to aim at.
- New 3D: `axis`, `scene` (import scene data) and `look at`.

## Controls
Classic scripting names: `read_from_file` plus file controls (`file`, `fbx_take_name`, `fbx_node_name`, `frame_rate`) and the standard transform set.

New 3D Axis: `read_from_scene_link` (Live Read), `snapshot_frame_link`, `snapshot_range_link`, `source_prim_path`, `constraint` (Look At or Parent), `local_parent_constrain_enable`. It works differently from the classic node despite the same name.

## Verify
- Move the Axis in the Viewer and confirm dependent objects follow.
- Check that nothing downstream still has local values conflicting with the Axis.

## Pitfalls
- Using the 3D Classic menu entry in a New 3D scene (or vice versa).
- Axis inputs override the dependent node's own transform knobs.
- Pivot position decides rotation and scaling centre.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/axis.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/axis.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
