---
id: "topics/geometry-animation-deformation"
kind: "topic"
title: "Animating and deforming 3D geometry"
category: "3d-animation-shaders"
summary: "Animate geometry with transform nodes, Axis parenting, imported animation or keyed vertex edits, and deform it with displacement/noise/warps, using Classic or New 3D nodes consistently and checking time and motion blur."
aliases: ["transformgeo", "geotransform", "axis parenting", "editgeo", "displacegeo", "geodisplace", "deform geometry", "animate geometry", "chan file"]
tags: ["3d", "animation", "deformation", "transform", "displacement"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["topics/keyframe-animation", "topics/rendering-3d", "topics/geometric-primitives", "topics/alembic", "topics/matchmove"]
nodes: ["TransformGeo", "GeoTransform", "Axis", "EditGeo", "DisplaceGeo", "GeoDisplace", "ProceduralNoise", "GeoNoise", "Trilinear", "GeoTrilinearWarp", "RadialDistort", "GeoRadialWarp"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# Animating and deforming 3D geometry

## Applicability
Use to move or reshape geometry that is rendered, projected on or used for occlusion/shadows. Pick the node family of the scene:
- Classic: TransformGeo, Axis, EditGeo, DisplaceGeo, ProceduralNoise, Trilinear, RadialDistort, Normals; geometry travels as objects through MergeGeo/Scene.
- New 3D: GeoTransform (a `Mask` of prim paths decides what moves), GeoDisplace, GeoNoise, GeoRadialWarp, GeoTrilinearWarp, GeoNormals, GeoSelection; geometry is a USD stage through GeoScene.
Do not feed Classic geometry into Geo* nodes or the reverse.

## Workflow
Transform animation:
1. Classic: TransformGeo takes geometry (or a MergeGeo to move several objects together); optional `axis` input links to an Axis (a null/locator that overrides the node's transform) and `look` points the object at a camera or object, useful for a card that must always face camera. New: GeoTransform has `axis` and `look at` inputs plus the Mask.
2. Keyframe translate/rotate/scale/skew/pivot, import a chan file, link to track or camera data, or import FBX/Alembic/USD transforms. Transform order (default SRT) and rotation order (default ZXY) are knobs, so match them to imported data.
3. Check the transform space the Viewer uses (object/screen/world) before editing in the Viewer.

Deformation:
1. EditGeo (Classic): select vertices or faces in the Viewer and drag; keyframe selections with the node's animate button; reset geometry returns the original positions.
2. DisplaceGeo (Classic) / GeoDisplace (New) moves each vertex along its normal by the `displace` image value at the vertex UV; it needs UVs and enough tessellation (card rows/columns). Choose `source` (luminance, a channel, rgb absolute/relative) and `scale`.
3. Noise, radial and trilinear warps are separate nodes in each family; Classic-to-New names are in Foundry's mapping table.
4. Transform normals only when necessary; `transform_normals` is normally left off.

Rendering: with New ScanlineRender, Object Xform and Object Deform blur toggles exist separately (animated transform versus animated vertex positions).

## Verify
- Scrub the timeline in the 3D Viewer and in the rendered 2D view; positions at keys must match.
- Inspect geometry in wireframe, silhouettes after deformation, and normals after displacement.
- Confirm Scene Time Offset (New ScanlineRender) is zero unless slipping deliberately.

## Pitfalls
- Deforming a mesh under a camera projection changes what the projection lands on; check registration after any deform [INFERENCE: projection works through camera and vertices; not tested]. Locked projections need time locks on image and camera (see topics/texture-projection).
- Displacement on a low-resolution card can only produce coarse shapes; too many rows/columns slows work (documented maxima).
- Imported animation can carry unit/scale/frame-rate conventions (Camera/Light read-in offers frame-rate override and, in New 3D, `world_to_meters`).
- Motion blur from rotation and deformation can show artifacts; Foundry suggests raising Shutter Segments for heavy rotational blur (New ScanlineRender).
- Animation in 3D is not a substitute for tracking: object paths must still agree with the plate camera.

## Sources
- Foundry 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/transforming_objects.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/modifying_object_shapes.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/transformgeo.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geotransform.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/displacegeo.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geodisplace.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/transforming.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/scanlinerender.html
- Brinkmann 2e Ch. 4 motion blur; Ch. 13 "Camera Movements" (animation must follow plate camera).
