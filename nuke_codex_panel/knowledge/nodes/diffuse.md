---
id: "nodes/diffuse"
kind: "node"
title: "Diffuse"
category: "3d-shaders"
summary: "Diffuse is a classic shader that sets an illuminated surface colour, darker where the surface faces away from light. In New 3D the documented counterparts are BasicSurface and MtlXStandardSurface."
aliases: ["Diffuse shader", "BasicSurface", "BasicMaterial", "MtlXStandardSurface", "diffuse material"]
tags: ["shader", "material", "lighting", "diffuse"]
requires: ["fundamentals/channels-data", "fundamentals/color-spaces"]
related: ["topics/lights-materials", "topics/multipass-cg", "nodes/specular", "nodes/light", "nodes/applymaterial"]
nodes: ["Diffuse", "Specular", "BasicMaterial", "BasicSurface", "MtlXStandardSurface"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Diffuse

## Purpose
Controls the colour of a lit surface. Shader nodes can be chained: Diffuse, Specular and Emission each take the previous shader (or an image) on the unnamed input, so effects build up one after the other.

## Inputs
- `map`: image that modulates the diffuse properties.
- Unnamed: the 2D texture, or another shader such as Diffuse, Specular or Emission.

## Controls
Scripting names: `channels` (default rgba) and `white` (default 0.18, the illuminated colour). When an image feeds the unnamed input and `white` changes, judge the result in the rendered 2D image, not the Viewer shading.

New 3D: BasicSurface combines diffuse, specular and emission in one panel (`diffuse` 0.18, `specular` 0.8, `roughness` 0.5, `emission`), with optional `diff`, `emis`, `spec`, `rough` inputs. The migration table maps Diffuse to BasicSurface or MtlXStandardSurface.

## Verify
- Add a Light and a Scene; the surface should darken as it turns from the light.
- Render and sample colour, with the working colour space known.

## Pitfalls
- Diffuse shading needs a light; without one only the renderer's `ambient` setting contributes.
- Stacking several shaders changes results by order.
- `white` is the illuminated material colour; the Viewer may not show the final result.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/diffuse.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/basicsurface.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
