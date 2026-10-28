---
id: "topics/alembic"
kind: "topic"
title: "Alembic geometry"
category: "advanced-3d"
summary: "Import and export Alembic meshes, point clouds, cameras and transforms with ReadGeo/Camera/Axis (classic) or GeoImport (new 3D), and check frame rate, time offset, baked transforms and scale before trusting the result."
aliases: ["abc", "ReadGeo alembic", "GeoImport alembic", "Alembic camera import", "WriteGeo abc", "Alembic scenegraph", "animated geometry cache"]
tags: ["alembic", "readgeo", "geoimport", "frame-rate", "time-offset", "scale", "transform", "scenegraph"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["topics/3d-particles", "topics/camera-projection", "topics/geometry-animation-deformation", "topics/rendering-3d", "topics/cg-backgrounds"]
nodes: ["ReadGeo", "Camera", "Axis", "TransformGeo", "Scene", "ScanlineRender", "TimeOffset"]
version: "Nuke 17.1 documentation; classic ReadGeo/WriteGeo vs new-3D GeoImport/GeoExport; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Alembic geometry

## Applicability
Alembic (.abc) caches animated meshes, point clouds, cameras and axes from other packages. ReadGeo reads geometry; cameras and transforms go into Camera and Axis nodes. Materials and textures are not read in classic ReadGeo, so re-texture inside Nuke. New 3D uses GeoImport (a USD-based scene graph) for the same job; do not mix classic and new nodes in one scene.

## Workflow
1. Read the file (R). A file with one item loads directly; with several, use the scenegraph dialog. Choose all-in-one (one node) or parents as separate nodes (one ReadGeo per parent item), then keep or deselect items. Items can later be shown/hidden on the Scenegraph tab, with view entire scenegraph to see everything in the file.
2. Animated objects: leave **read on each frame** on (it bakes each object's transform into the points). If off, lock frame picks the single frame to load.
3. Time: set **frame rate** (default 24; it samples the animation) deliberately rather than assuming it equals the project rate; Camera has a use frame rate option to force your value over the file's. To shift timing use TimeOffset on the geometry stream; ReadGeo's frame range only controls the displayed Viewer range. GeoImport offers time_offset and time_scale on prim animation and a frame range (leave 1,1 for static files so the graph does not re-evaluate).
4. sub frame (default on) reads between frames for motion blur; disable it for faster interaction.
5. Cameras: pick animation stack and node name in Camera, enable read from file to track reloads, or uncheck it to edit. compute rotation derives rotation from look-at and up vector; when a look-at target exists, rotation is always computed.
6. Points: render points as point clouds or particles; use geometry colors turns on vertex color attributes (turning it off can change renders).
7. Scale and axes: the Alembic page does not state units conversion. Compare the imported object with a known measurement, or a locator in the matching camera solve, then correct with one uniform scale applied to every element sharing the shot (geometry, camera, axes), not just the mesh. GeoImport can promote layer metadata (meters per unit, up axis) for USD, subject to strongest layer.
8. Export: WriteGeo (needs a Scene input for abc), set file type abc, choose geometries/pointClouds/cameras/axes, storage format HDF (compatible) or Ogawa (faster, smaller), Execute with a frame range. GeoExport is the new 3D equivalent.

## Verify
- First, last and a middle frame: object position and camera framing match the source application at the same frame, allowing for any start-frame offset in the cache [INFERENCE: caches often start at a non-1 frame].
- Playback speed: one second of animation equals the expected frame count at the shot frame rate.
- Locator or mesh sits on the tracked features at known frames; scale correct against a measured dimension.
- Transforms: object pivots and axes behave in the Viewer as in the source package (rotation order, up axis).

## Pitfalls
- Re-reading with different frame rate or offset gives silent timing slips; set it deliberately.
- Importing the same file twice with GeoImport can collide paths; use GeoReference for copies.
- OBJ flattens transforms and has no animation; Alembic keeps hierarchy.
- Baked per-frame reads of huge caches are heavy; use localization policy and Ogawa where possible.
- Editing transforms on an object read from file is discarded on reload when read from file is on.
- Textures and materials must be rebuilt; UVs and normals are read, shaders are not.

## Sources
- Foundry Nuke 17.1: https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/readgeo.html (ABC options, scenegraph, frame range)
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/importing_abc.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/importing_alembic_cameras.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/writegeo.html (abc options, storage format)
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geoimport.html (time mapping, metadata)
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
