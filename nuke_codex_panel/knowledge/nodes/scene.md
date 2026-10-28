---
id: "nodes/scene"
kind: "node"
title: "Scene"
category: "3d-nodes"
summary: "Scene collects geometry, lights, cameras and materials into one 3D scene for a render node. In New 3D the counterpart is GeoScene, the only node that accepts cameras, axes and lights."
aliases: ["Scene node", "GeoScene", "3D scene merge", "merge scene"]
tags: ["scene", "classic 3d", "new 3d", "lights", "geometry"]
requires: ["fundamentals/node-selection"]
related: ["topics/rendering-3d", "topics/geometric-primitives", "topics/lights-materials", "nodes/scanlinerender", "nodes/camera", "nodes/light"]
nodes: ["Scene", "GeoScene", "GeoMerge", "ScanlineRender"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Scene

## Purpose
Classic Scene is the highest-level node of a classic 3D hierarchy: it references all geometry, cameras and lights and should be connected to a ScanlineRender, RayRender or PrmanRender. It has no image output of its own.

New 3D uses GeoScene instead. Foundry states it is the only node that lets Camera, Axis, DirectLight, SpotLight, EnvironmentLight and PointLight connect into the scene; GeoMerge cannot take them. Prims downstream with Mask set to {lastmodified} inherit from the strongest layer, meaning the highest-numbered input.

## Inputs
- Classic: numbered inputs for 3D objects, lights, cameras and materials; any number.
- GeoScene: numbered inputs combining New 3D objects.

## Controls
Classic scripting names: `display`, `selectable`, `render_mode`, `shadow_override`, `cast_shadow`, `receive_shadow`. Display only affects the Viewer; `render_mode` affects what renders. `shadow_override` can force shadow behaviour onto all connected geometry. GeoScene has no node-specific properties.

## Verify
- Viewer in 3D mode shows every expected object, light and camera; the Scene output feeds the renderer's obj/scn input.
- Pick the viewing camera from the Viewer dropdown to confirm cameras were actually included.

## Pitfalls
- Classic (green) and New 3D nodes are two systems; keep one system per scene [inference].
- Lights that are not connected to the Scene do not light its geometry.
- Overriding shadow settings at the Scene replaces per-object settings.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/scene.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geoscene.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
