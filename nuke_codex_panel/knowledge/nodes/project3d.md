---
id: "nodes/project3d"
kind: "node"
title: "Project3D"
category: "3d-shaders"
summary: "Project3D projects a 2D image through a camera onto 3D geometry as a shader. New 3D replaces it with Project3DShader; GeoProjectUV is a separate node that rewrites UVs, like classic UVProject."
aliases: ["Project3DShader", "camera projection shader", "texture projection", "projection shader", "GeoProjectUV"]
tags: ["projection", "camera", "texture", "shader", "uv"]
requires: ["fundamentals/coordinates", "fundamentals/filtering-concatenation"]
related: ["topics/texture-projection", "topics/camera-projection", "topics/set-extension", "nodes/camera", "nodes/card", "nodes/applymaterial"]
nodes: ["Project3D", "Project3DShader", "GeoProjectUV", "UVProject", "Camera"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Project3D

## Purpose
Casts an image onto geometry from a projection Camera, independent of the render camera. This is the core of camera projection, set extension and rig clean-up with 3D patches. It acts as a shader: its output connects to the geometry's image input (or a shader chain).

## Inputs
- `cam`: the projection Camera.
- unnamed: the 2D image to project.
Classic setup per Foundry: projection camera + Project3D + geometry + the 2D image, then a Scene and a render camera.

## Controls
Classic: `project_on` (both, front, back), `crop` (on extends black beyond the frame; off extends edge colour), `occlusion_mode` (disabled by default; self or world use ray casting).

New 3D Project3DShader: same `project_on`, `crop` (Crop To Format), `near_clip_enable`, `far_clip_enable` (use the projection camera planes), `occlusion_mode` (none, self, world). Bind it with GeoBindMaterial or a mat input. GeoProjectUV changes vertex UVs instead; it has Cull Behind Projection Source.

## Verify
- Look through the render camera: the projection should hold on the object at the projection frame and distort only through parallax.
- Toggle occlusion mode to see if the image leaks onto hidden surfaces.

## Pitfalls
- A projection camera needs the true focal length and aperture of the projected photograph; a mismatch shifts the image.
- Edge colour smearing beyond the frustum means `crop` is off.
- Projection onto back faces appears when `project_on` is both.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/project3d.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/project3dshader.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/projection_cameras.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/projections.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
