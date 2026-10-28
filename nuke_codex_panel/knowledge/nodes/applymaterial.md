---
id: "nodes/applymaterial"
kind: "node"
title: "ApplyMaterial"
category: "3d-shaders"
summary: "ApplyMaterial assigns a material from its mat input to classic 3D geometry, replacing materials set earlier. New 3D uses GeoBindMaterial with prim masks and USD binding strength."
aliases: ["Apply Material", "GeoBindMaterial", "bind material", "assign shader"]
tags: ["material", "shader", "geometry", "binding"]
requires: ["fundamentals/channels-data"]
related: ["topics/lights-materials", "topics/texture-projection", "nodes/diffuse", "nodes/specular", "nodes/project3d"]
nodes: ["ApplyMaterial", "GeoBindMaterial", "BasicMaterial", "Project3D"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# ApplyMaterial

## Purpose
Applies one material or shader to one object or to many merged objects, overriding materials applied earlier to the individual pieces.

## Inputs
- Unnamed: the geometry (or MergeGeo for a group).
- `mat`: the material, e.g. a BasicMaterial node.
GeoBindMaterial: unnamed = scene stage; `mat` is optional, otherwise a scene-graph material is chosen with the `material_path` control.

## Controls
Classic scripting names: `render_mode`, `filter_type` (all or name), `filter_name_match` (equals, contains and similar), filter name field, `filter_refresh` (Object Name Chooser). Name filtering requires a name attribute on the geometry; per docs only ModelBuilder and ReadGeo reading Alembic/USD add one (third-party plug-ins may too).

GeoBindMaterial: `mask_patterns` (glob wildcards), `inject_mask`, `bindingStrength` (default Stronger than descendants), `material_path`, `purpose` (All Purpose, Full, Preview). A Checkerboard on `mat` can drive a texture on a prim such as /GeoCube1.

## Verify
- Render or view textured: every targeted object shows the material, others keep theirs.
- Check the name filter against the chooser list.

## Pitfalls
- Applying after a merge replaces all inner materials.
- Filter by name fails silently when the geometry has no name attribute.
- Material purposes (full vs preview) differ between Viewer and render.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/applymaterial.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geobindmaterial.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
