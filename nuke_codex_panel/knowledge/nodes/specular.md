---
id: "nodes/specular"
kind: "node"
title: "Specular"
category: "3d-shaders"
summary: "Specular is a classic shader controlling highlight brightness and width, with view-dependent brightest points. New 3D maps it to ReflectiveSurface; BasicSurface also has specular and roughness."
aliases: ["Specular shader", "ReflectiveSurface", "highlight shader", "shininess"]
tags: ["shader", "highlight", "shininess", "material"]
requires: ["fundamentals/channels-data", "fundamentals/color-spaces"]
related: ["topics/lights-materials", "topics/multipass-cg", "nodes/diffuse", "nodes/light", "nodes/applymaterial"]
nodes: ["Specular", "Diffuse", "ReflectiveSurface", "BasicSurface"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Specular

## Purpose
Adds highlights to a surface: how bright they are and how wide. They are brightest along the direct angle of reflection, so the viewpoint matters.

## Inputs
- `mapsh`: optional mask varying shininess; black = min shininess, white = max shininess.
- `map`: image that modulates specular properties.
- Unnamed: texture, or another shader to chain.

## Controls
Scripting names: `channels` (rgba), `white` (default 0.18; higher is shinier), `min_shininess` (10), `max_shininess` (10), `shininess_channel` (luminance; also red/green/blue/alpha choices). Higher shininess widens the highlight, per the docs.

New 3D: the migration table maps Specular to ReflectiveSurface; for combined diffuse/specular/emission use BasicSurface (`specular`, `roughness`, `shininess_channel`).

## Verify
- Move the camera or light and confirm the highlight shifts.
- With `mapsh` connected, compare min and max shininess regions.

## Pitfalls
- Needs a light in the scene.
- `min_shininess` and `max_shininess` default to the same value, so a mapsh has no visible effect until they differ.
- Do not assume classic shininess values transfer to roughness in New 3D.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/specular.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/basicsurface.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
