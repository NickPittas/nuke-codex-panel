---
id: "nodes/light"
kind: "node"
title: "Light"
category: "3d-lights"
summary: "Classic Light creates a point, directional or spot light and can import lights from FBX. New 3D uses PointLight, DirectLight, SpotLight, EnvironmentLight or GeoEditLight, connected through GeoScene."
aliases: ["Light node", "PointLight", "DirectLight", "SpotLight", "EnvironmentLight", "GeoEditLight", "spot light", "point light"]
tags: ["light", "shadows", "lighting", "falloff"]
requires: ["fundamentals/coordinates"]
related: ["topics/lights-materials", "topics/rendering-3d", "nodes/diffuse", "nodes/specular", "nodes/scene", "nodes/scanlinerender"]
nodes: ["Light", "Point", "Direct", "Spot", "PointLight", "DirectLight", "SpotLight", "GeoEditLight"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Light

## Purpose
Illuminates 3D geometry for the renderer. Classic Light is configured by `light_type` (point, directional, spot), and can read lights from .fbx.

## Inputs
- `axis`: parent Axis overrides local transform.
- `look`: Camera, Light or Axis to aim at.
New 3D PointLight has `look`, `axis` and `scene` inputs (connect to GeoScene).

## Controls
Classic scripting names: `light_type` (default point), `color`, `intensity`, spot-only `cone_angle` (40), `cone_penumbra_angle`, `cone_falloff`; `falloff_type` (No falloff, Linear, Quadratic, Cubic; point and spot only); Shadows tab `cast_shadows` (off), `shadow_mode`, `filter`, `scene_epsilon`, `samples`, `sample_width`, `depthmap_bias`; File tab `read_from_file`.

ScanlineRender shadows only work for directional or spot lights; point-light shadows are not supported in the classic ScanlineRender.

New 3D: PointLight, DirectLight, SpotLight and EnvironmentLight use `intensity` and `exposure` (power of 2, like f-stops), Live Read and Source Prim. Their USD equivalents are SphereLight, DistantLight, DiskLight and DomeLight (GeoSphereLight etc.); GeoEditLight creates or edits USD lights.

## Verify
- Check the light is connected to the same Scene as the geometry.
- Enable shadows and look through the render, not only the Viewer.

## Pitfalls
- Casting shadows from a point light in classic ScanlineRender gives nothing.
- Self-shadow artefacts: the docs advise raising `scene_epsilon` or `depthmap_bias`.
- Do not assume classic intensity values carry over to New 3D lights.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/light.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/pointlight.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
