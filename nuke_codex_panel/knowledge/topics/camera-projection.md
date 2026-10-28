---
id: "topics/camera-projection"
kind: "topic"
title: "Camera projection"
category: "production-workflows"
summary: "Project a plate frame through a matched projection camera onto geometry, then render with a separate moving render camera. Covers Classic Project3D and New Project3DShader, lens/aperture, frame locking, occlusion and parallax limits."
aliases: ["projection camera", "project3d", "camera mapping", "2.5d", "matte painting projection", "patch projection", "render camera vs projection camera"]
tags: ["3d", "projection", "camera", "tracking", "clean plate", "parallax"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling", "fundamentals/alpha-premultiplication", "fundamentals/graph-conventions"]
related: ["topics/texture-projection", "topics/camera-tracking", "topics/lens-distortion", "topics/rig-removal", "topics/set-extension", "topics/geometry-from-images", "nodes/postagestamp", "nodes/dot", "nodes/backdrop"]
nodes: ["Camera", "Project3D", "Project3DShader", "FrameHold", "ScanlineRender", "Card", "GeoCard", "CameraTracker"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions", "lesson-08"]
---
# Camera projection

## Applicability
Use when a still or short sequence must be re-seen from a moving camera: patches, matte paintings, clean plates, 2.5D parallax. Two cameras exist and must not be confused:
- Projection camera: where the image was captured; projects pixels through its lens onto geometry. For a still patch it is locked to one frame.
- Render camera: the animated (tracked) camera wired to the render node's `cam` input; decides the output view.
Required inputs: a camera solve or known camera data for the plate (CameraTracker, FBX/Alembic/USD), geometry that stands in for the surface, correct lens and film back, and the plate frame to project. Limits: pixels the projection camera never saw, parallax beyond what the geometry models, depth discontinuities, moving objects and heavy motion blur.

## Workflow
Classic 3D (Camera, Project3D, Scene, ScanlineRender):
1. Image -> Project3D unnamed input; projection Camera -> Project3D `cam`; Project3D output -> geometry `img` (or ApplyMaterial `mat`). Geometry -> Scene -> render node; render Camera -> render node `cam`.
2. Set the projection camera's Projection tab: `focal`, `haperture`, `vaperture` for the camera that shot the image. Foundry's formula for scans: resolution / scanner pitch = aperture. With a tracked camera, use the solved focal length and film back and the same format.
3. To freeze: put FrameHold on the image and on the projection camera at the reference frame (the pattern ModelBuilder's Projection bake creates). Leave the render camera animated.
4. Position geometry so it coincides with the real surface from the reference view; check from the render camera at other frames.
5. Set Project3D `project on` and `occlusion mode`: none, self (bound geometry only) or world (ray-cast occlusion by all scene geometry).

New 3D: Project3DShader is the material; bind via GeoBindMaterial or `mat`; geometry via GeoScene; camera `cam` input and the render camera as above; options include Near/Far Plane Clip and Occlusion Mode. For USD cameras use Camera with Live Read (or GeoEditCamera); a Camera pushed into the stage via GeoScene becomes a duplicate USD camera without Nuke-only spherical/cylindrical modes. Use time-locking checked in the installed build; the documented sticky tool for UVs is GeoProjectUV Reference Frame.

Lens distortion: virtual objects are not distorted by default after CameraTracker. Undistort the plate before projecting and redistort the render, or otherwise account for it (topics/lens-distortion). ScanlineRender `overscan` supplies extra pixels for downstream distortion.
Course practice (lesson-08): render every element through the same shot camera at the undistorted plate resolution. For a clean-plate patch, take the most detailed frame at the closest angle, undistort and premultiply it, alpha only the replaced part, and project through its own camera. Match softness only after the projection is correct, never to hide a wrong focal length.

## Verify
- Render at the projection frame and wipe against the plate: should match to the pixel.
- Step to far frames: edges, stretching, back-face bleed, and occlusion errors show where geometry is wrong.
- Toggle projection and render cameras separately; the image must follow the render camera while the patch stays pinned.
- Check output alpha and bounding box before downstream Merge.

## Pitfalls
- A single projected frame cannot show what was hidden at that frame; Brinkmann notes clean plates and added camera moves lose correct parallax when elements are flat (Ch. 12 "Matched Cameras"/"Clean Plates"; Ch. 13 "Camera Movements").
- Perspective belongs to camera position, not the lens alone (Ch. 2 "Perspective and the Camera").
- Wrong aperture or crop/format changes between solve and projection create a slow slide.
- Project3D `crop` extension behavior is described differently in Foundry pages; check edge extension visually.
- Classic and New projection nodes cannot be mixed.
- Graph hygiene (studio preference, `fundamentals/graph-conventions`): keep the projection rig in its own labelled Backdrop and return the rendered 2D result to the B trunk as one A branch. Feed the projected image from the single existing Read via Dots, a PostageStamp with a real upstream input, or Stamps if verified; no second Read or long cross-graph pipe.

## Sources
- Foundry 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/projection_cameras.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/project3d.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/project3dshader.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/camera.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/working-with-cameras.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/projections.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/modelbuilder/projecting_textures.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/camera_tracking.html
- Brinkmann 2e Ch. 2, Ch. 12, Ch. 13.
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): separate projection/3D backdrops and source reuse.
- Lesson 08.srt (lesson-08; ASR, teaching-practice only): 00:18:22–00:19:46 same camera, undistorted resolution; 00:26:01–00:27:41 clean-plate projection.
