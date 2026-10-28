---
id: "topics/rendering-3d"
kind: "topic"
title: "Rendering 3D scenes"
category: "3d-basics"
summary: "Turn a Nuke 3D scene into a 2D image with the render node that matches the scene generation, then treat the result as ordinary image data: format, depth, vectors, alpha, overscan and motion blur."
aliases: ["scanlinerender", "scanlinerender2", "rayrender", "georender", "render 3d to 2d", "obj/scn cam bg", "3d render output"]
tags: ["3d", "render", "scanlinerender", "camera", "output", "aov"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data", "fundamentals/time-sampling", "fundamentals/quality-safeguards"]
related: ["topics/lights-materials", "topics/camera-projection", "topics/cg-backgrounds", "topics/motion-blur-depth-of-field", "topics/multipass-cg"]
nodes: ["ScanlineRender", "RayRender", "GeoRender", "SplatRender", "Scene", "GeoScene", "Camera", "Write", "VectorBlur"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions"]
---
# Rendering 3D scenes

## Applicability
Pick the renderer from the scene generation first:
- Classic 3D (3D Classic menu): Scene -> ScanlineRender (fast scanline, deep support, weaker reflection/refraction) or RayRender (more accurate reflections, slower, no deep, no sprite particles). PrmanRender is a separate option where licensed.
- New 3D System (3D menu): GeoScene -> ScanlineRender (class appears as `ScanlineRender2`, now with ray-tracing, AOVs, richer motion blur), GeoRender (Hydra 2.0 render delegates) or SplatRender (Gaussian splats).
The two ScanlineRenders share a display name but are different nodes. Foundry describes ScanlineRender as a utility renderer for late-stage compositing passes, not a full-production renderer.

## Workflow
1. Connect the scene to `obj/scn`, the render camera to `cam`, optional background to `bg`. Without `cam` it uses a default camera at the origin facing negative Z.
2. Output size comes from `bg` if connected, otherwise from `root.format`/`root.proxy_format` in Project Settings. A depth channel in `bg` is used for Z-buffer/Z-blend.
3. Projection mode defaults to render camera: perspective, orthographic, spherical, cylindrical (New), or UV unwrap/uv (renders every object's UV space for baking textures). Classic lists uv, spherical, orthographic, perspective.
4. Classic motion blur: MultiSample `samples`, `shutter`, `shutter offset`; Foundry notes that with samples in use you can usually turn off the antialiasing and filter controls on the ScanlineRender tab. New: Camera Samples, Shutter Length/Offset/Segments, per-source toggles (camera, lens, object transform, deform, lights), Scene Time Offset to slip scene time while keeping output frame.
5. Overscan renders pixels outside the frame when downstream blur or LensDistortion needs them.
6. Data outputs: Classic `output vectors` writes world-space P and N; motion vectors default to distance, which VectorBlur can use. New: Outputs tab has 1/Z toggle, motion-vector type and AOV list. Check the Z convention (1/Z versus absolute) before using depth.
7. Toggle the Viewer to 2D, then connect the render output to 2D comp nodes and Write for disk output.

## Verify
- Dimensions and bounding box match the plate; transparent areas have alpha; Z is nonzero where geometry exists.
- Compare 2D view with 3D view through the same camera: positions should agree.
- Scrub frames; step through motion blur settings. Use samples >= 2 (New: camera samples/time jitter) or no blur is created, though vectors still exist.

## Pitfalls
- Lights and materials must belong to the same generation as the renderer (see topics/lights-materials). New ScanlineRender treats 'lighting enable' auto: no lights means constant shading.
- Point-light shadows are not supported by Classic ScanlineRender (Light node doc).
- Spherical/cylindrical or distorted renders can need higher tessellation (Classic `max_tessellation`) near edges.
- Depth of field and motion blur in 3D are not equivalent to later 2D blur; the choice depends on the shot (Brinkmann, Ch. 2 "Motion Blur", Ch. 14 "Working with CG Elements").
- Render, then match grain, lens distortion and black levels in 2D; CG does not inherit camera artifacts (Brinkmann Ch. 14).
- New 3D Deep and particle integration is limited per Foundry; verify before relying on it. GeoRender/SplatRender availability depends on the installed build.
- Studio graph preference: keep scene, camera and render nodes in a labelled 3D Backdrop and return the render as an A input on a sequential Merge down the 2D B trunk. Confirm the render's format and bbox against the background first, and crop or use the Merge B-side bbox only after any transform chain (`fundamentals/quality-safeguards`).

## Sources
- Foundry 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/rendering_3d_scene.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/render-scene.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/rendering-scanline.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/scanlinerender.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/scanlinerender.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
- Brinkmann 2e Ch. 2 "The Camera"/"Motion Blur"; Ch. 14 "Working with CG Elements".
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): 3D backdrop separation, return to the 2D trunk.
