---
id: "topics/texture-projection"
kind: "topic"
title: "Projecting texture maps"
category: "3d-basics"
summary: "Decide between texture UV mapping, UV re-projection (UVProject/GeoProjectUV) and camera-projection shaders (Project3D/Project3DShader), then wire them correctly for Classic or New 3D."
aliases: ["uvproject", "project3d", "geoprojectuv", "project3dshader", "texture mapping", "uv vs projection", "sticky projection"]
tags: ["3d", "texture", "projection", "uv", "material"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling", "fundamentals/graph-conventions"]
related: ["topics/camera-projection", "topics/lights-materials", "topics/rendering-3d", "topics/set-extension", "nodes/postagestamp", "nodes/backdrop"]
nodes: ["UVProject", "GeoProjectUV", "Project3D", "Project3DShader", "FrameHold", "Camera", "ApplyMaterial", "GeoBindMaterial"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions"]
---
# Projecting texture maps

## Applicability
Choose the texture strategy first; it decides the nodes.
- Texture UVs: the geometry already has UV coordinates (imported or from a primitive); the image is looked up by UV. Use when the surface owns its texture.
- UV re-projection: UVProject (Classic) or GeoProjectUV (New 3D) rewrites vertex UVs from an Axis or Camera (planar/spherical etc.), replacing existing UVs. The image still comes in as a material.
- Camera projection: Project3D (Classic) or Project3DShader (New 3D) is a shader that projects an image through a camera. Use for plate-based patches, matte paintings and clean-plate fixes. See topics/camera-projection for tracked-camera practice.
Spaces: UV is surface texture space; world is scene space; camera space looks down negative Z; image space is the frame's pixels. A projection camera maps image space onto world space.

## Workflow
Classic 3D:
1. Camera -> Project3D `cam`; image -> Project3D's unnamed input; Project3D output goes to the geometry's `img` input, or to ApplyMaterial `mat` for imported geometry. Geometry goes to Scene, render camera to the render node.
2. Match the projecting lens: focal length, `haperture`, `vaperture` of the camera that shot the image (Foundry's math: horizontal resolution / scanner pitch = horizontal aperture).
3. `project on` front/back/both; `occlusion mode`: none, self (the bound geometry occludes) or world (all scene geometry occludes, ray cast).
4. UVProject: connect Axis or Camera to `axis/cam`; choose a projection type near the shape (for example planar or spherical); optional view frustum culling, U/V invert, scale.

New 3D System:
1. GeoProjectUV is placed after the geometry; image goes through GeoBindMaterial `mat`. Knobs of note: Cull Behind Projection Source, View Frustum Culling, Generate Perspective ('stw'), Reference Frame (sticky projection that applies only at the referenced frame).
2. Project3DShader binds like any shader (GeoBindMaterial or the primitive's `mat`), with Near/Far Plane Clip and Occlusion Mode (none/self/world).
3. Several projections combine with MergeLayerShader (Classic equivalent: MergeMat).

Stick a projection in time (Classic): hold the projected image and the camera on one frame with FrameHold, as ModelBuilder's Projection bake does (Project3D with FrameHold locking image and camera). In the New system, use GeoProjectUV Reference Frame or verify an equivalent time lock in the installed version.

## Verify
- View the render through the render camera in 2D, then wipe against the source plate at the projection frame; the texture must register exactly there.
- Scrub: tracked geometry should slide correctly relative to the plate (parallax). Inspect edges and back faces.
- Compare Project3D `crop` behaviour on edges; Foundry pages describe it differently (black extension vs edge color), so test it.

## Pitfalls
- Projection is not UV mapping: moving the geometry under a projection changes the result; moving UVs under UVProject does not.
- Projecting onto coarse meshes in the New 3D Viewer shows perspective distortion; GeoProjectUV works per vertex, so increase tessellation (Foundry note about Storm).
- Camera projection only gives pixels the projection camera saw: occluded or off-frame surfaces stretch or go black; large parallax breaks flat cards (Brinkmann, Ch. 13 "Camera Movements").
- An animated projection camera or animated image animates the projection; lock both to one frame when a still patch is intended.
- Classic and New projection nodes do not mix.
- Graph hygiene (studio preference, `fundamentals/graph-conventions`): keep texture/projection nodes in a labelled 3D Backdrop, reuse the one Read through Dots or a PostageStamp with a real upstream input (or Stamps if available), and bring only the controlled render back to the 2D B trunk.

## Sources
- Foundry 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/projecting_textures_objects.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/projection_cameras.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/projections.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/project3d.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/project3dshader.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/modelbuilder/projecting_textures.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/shading-geometry.html
- Brinkmann 2e Ch. 13 "Camera Movements"; Ch. 2 perspective sections.
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): separate 3D backdrops and source reuse.
