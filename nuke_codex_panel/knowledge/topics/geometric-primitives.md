---
id: "topics/geometric-primitives"
kind: "topic"
title: "Working with geometric primitives"
category: "3d-basics"
summary: "Choose and place Card, Cube, Cylinder and Sphere (Classic 3D) or GeoCard/GeoCube/GeoCylinder/GeoSphere (New 3D) as stand-ins, projection surfaces and image planes, with correct scale, tessellation and scene wiring."
aliases: ["card cube sphere cylinder", "3d primitives", "image plane", "geocard", "geosphere", "proxy geometry"]
tags: ["3d", "geometry", "card", "primitives", "scene"]
requires: ["fundamentals/coordinates"]
related: ["topics/texture-projection", "topics/rendering-3d", "topics/set-extension", "topics/geometry-from-images"]
nodes: ["Card", "Cube", "Cylinder", "Sphere", "GeoCard", "GeoCube", "GeoCylinder", "GeoSphere", "Scene", "GeoScene"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# Working with geometric primitives

## Applicability
Use primitives when a simple surface is enough: an image plane for a still or clip, a ground/wall stand-in for projection, a sphere or cylinder for pan-and-tile environments, or proxy geometry for lighting, shadows and occlusion. For scanned, imported or tracked-surface shapes use import or modeling topics instead.

Choose one generation per scene tree:
- Classic 3D: Card, Cube, Cylinder, Sphere; their `img` input carries the texture; they feed a Scene node.
- New 3D System: GeoCard, GeoCube, GeoCylinder, GeoSphere (Classic-to-New table pairs them); the `mat` input takes a texture/shader; they feed GeoScene and create USD prims at a prim path (default `{nodename}`, e.g. `/GeoCard1`). Imported geometry has no `mat` input, so bind materials with GeoBindMaterial.
Classic and New nodes are not interchangeable in one tree.

## Workflow
1. Pick the primitive from the shape you must match: plane for flat artwork or a wall, cylinder/sphere for wraparound, cube for blocking volumes.
2. Card: image aspect follows the input image when enabled; `z` plus `lens_in_focal`/`lens_in_haperture` size the card so, at distance z, it fills the field of view of the camera that took the image. Enter the real source focal length and aperture, not the defaults.
3. Raise `rows`/`columns` only when needed for later projection, deformation or displacement. Documented maxima are 4096 for cards and 512 for sphere, cube and cylinder; the docs warn high values may cause instability.
4. Place with the primitive's own translate/rotate/scale or via Axis/TransformGeo (Classic) or GeoTransform (New). Check handles in the Viewer transform space.
5. Wire: primitives to Scene (Classic) or GeoScene (New); add a Camera and a render node. Primitives only render when the render node's `obj/scn` input sees them.

## Verify
- In 3D view, the primitive sits where intended in world axes and, through the render camera, covers the expected frame area.
- Display knobs (display, selectable) are Viewer-only; `render` controls how it renders. Check both when something shows but does not render, or vice versa.
- With a texture: right orientation (Card `orientation` XY/YZ/ZX) and aspect, no distortion.

## Pitfalls
- Same names, different nodes: both systems have Camera, Axis and ScanlineRender; pick from 3D Classic or 3D menus deliberately. New ScanlineRender appears as `ScanlineRender2`.
- Wrong lens-in values make a card scale wrong while still looking plausible in one frame.
- Sphere/cube/cylinder knob maxima differ from card; confirm the knobs in the installed version.
- A primitive is an approximation: parallax, occlusion and silhouette limits apply (Brinkmann, Ch. 2 "Motion Parallax"; Ch. 13 "Camera Movements").
- Cylinder/sphere `close top`/`close bottom` defaults differ between nodes; set caps deliberately.

## Sources
- Foundry 17.1: https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/card.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geocard.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/sphere.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/cube.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/cylinder.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/3d_scene_geometry.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/materials-shaders.html
- Brinkmann 2e: Ch. 2 "Depth, Distance, and Perspective"; Ch. 13 "Camera Movements".
