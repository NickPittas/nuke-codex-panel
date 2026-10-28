---
id: "nodes/readgeo"
kind: "node"
title: "ReadGeo"
category: "3d-geometry"
summary: "ReadGeo imports Alembic, FBX, OBJ and USD geometry into classic 3D. New 3D uses GeoImport, which also handles MaterialX, PLY and Gaussian splat files, plus GeoReference for instances."
aliases: ["Read Geo", "GeoImport", "import geometry", "Alembic reader", "OBJ FBX USD import", "GeoReference"]
tags: ["alembic", "fbx", "obj", "usd", "geometry import"]
requires: ["fundamentals/time-sampling", "fundamentals/coordinates"]
related: ["topics/alembic", "topics/camera-projection", "topics/geometric-primitives", "nodes/camera", "nodes/transformgeo", "nodes/applymaterial"]
nodes: ["ReadGeo", "GeoImport", "GeoReference", "WriteGeo", "GeoExport"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# ReadGeo

## Purpose
Loads meshes and point clouds from disk. For .abc, .fbx and .usd the mesh vertices, normals, UVs and vertex colours are read per frame or at the first frame. Materials and textures are not read in. Alembic or FBX cameras go to Camera nodes; USD cameras are not currently supported by ReadGeo.

## Inputs
- `img`: texture to project onto the imported geometry.

## Controls
Scripting names: `file`, `localizationPolicy`, `updateLocalization`, `reload`, `range_first`, `range_last`, `render_mode`, `cast_shadow`, `receive_shadow`.

Alembic: `read_on_each_frame` (keep on for animated objects), `sub_frame` (needed for motion blur), `lock_frame`, `frame_rate`, `point_render_mode` (point clouds or particles), `use_geometry_colors`, scene graph options `scene_view`, `all_objects`.

New 3D GeoImport: supports .usd, .usda, .usdc, .abc, .fbx, .obj, .mltx, .ply and .splat; opens an Import Scene Graph dialog on first load. It cannot rename the prim path, so importing the same file twice can conflict; GeoReference makes light-weight instances.

## Verify
- Step through frames: animated meshes must move; if not, check `read_on_each_frame`.
- Compare scale and orientation with other assets in the scene.
- Confirm UVs exist before assigning textures.

## Pitfalls
- Frame rate mismatch changes animation timing.
- Expect to rebuild materials; they are not imported.
- Name filtering in ApplyMaterial needs a name attribute from ReadGeo (Alembic/USD).

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/readgeo.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geoimport.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
