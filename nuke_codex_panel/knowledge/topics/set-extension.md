---
id: "topics/set-extension"
kind: "topic"
title: "Set extension"
category: "production-workflows"
summary: "Extend a plate with a matte painting or built environment by choosing 2D layering, projected cards, or geometry from the camera move and depth range, then masking, occlusion and integration checks."
aliases: ["set extension", "matte painting", "environment extension", "pan and tile", "digital set", "sky replacement", "projected matte painting", "billboard cards"]
tags: ["3d", "matte painting", "projection", "cards", "occlusion", "production"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/coordinates", "fundamentals/time-sampling", "fundamentals/graph-conventions", "fundamentals/quality-safeguards"]
related: ["topics/camera-projection", "topics/camera-tracking", "topics/texture-projection", "topics/geometric-primitives", "topics/rendering-3d", "topics/rotoscoping-masking", "topics/geometry-from-images", "topics/lens-distortion"]
nodes: ["Card", "GeoCard", "Camera", "CameraTracker", "Project3D", "Project3DShader", "TransformGeo", "GeoTransform", "ScanlineRender", "Roto", "Merge"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions"]
---
# Set extension

## Applicability
Use when part of the frame must become more set: a taller building, a skyline, a distant landscape, a missing ceiling. Choose the method from the camera and depth range; there is no universal recipe.
1. Locked-off or nearly static camera, far extension: 2D layers (painting plus Transform, Roto occluders, Merge). Brinkmann (Ch. 13 "Camera Movements") warns that a post-composite 2D pan lacks parallax; breaking the painting into layers moved by slightly different amounts can help.
2. Moving camera with a tracked solve and large extensions at a few distinct depths: place the painting on cards at appropriate distances and render them through the tracked camera (3D). Foundry describes the 3D workspace as suited to camera moves and set replacement, and pan-and-tile scenes of curved image planes.
3. Moving camera with real depth variation or near objects: project the plate or painting onto rough geometry from a matched camera (topics/camera-projection, topics/geometry-from-images). Parallax and disocclusion limits increase.
Choose one 3D generation: Classic Card/Scene/ScanlineRender or New 3D GeoCard/GeoScene/ScanlineRender2. Their materials, cameras and projection shaders are not interchangeable.

## Workflow
1. Establish the camera: CameraTracker solve (or imported FBX/Alembic/USD camera) with correct focal, film back and format; decide how lens distortion is handled (topics/lens-distortion).
2. Fix scale and position: Card `z` plus `lens_in_focal`/`lens_in_haperture` size a card to the field of view of the camera that took the image. A `look` input (TransformGeo) or `look at` (GeoTransform) can keep a distant painting plane facing the camera, Foundry's own matte-painting example.
3. For a still painting through a moving camera, apply it with Project3D/Project3DShader or directly on a card's `img`/`mat`; choose whether it is projected from a camera frame or mapped as UV.
4. Add masks and occluders: Roto or keys for foreground elements that must stay in front; Brinkmann Ch. 13 "Scale and Perspective" stresses isolating background objects to partially occlude a new element. Generate clean-plate and sky edges as needed (topics/rig-removal).
5. Integrate: color, atmosphere, depth of field, grain, motion blur and lens effects (Brinkmann Ch. 13 and Ch. 14). Render the 3D to 2D and composite over the plate with an alpha that matches the intended premult state.

## Verify
- Scrub the whole move: the extension must hold position relative to real-world features at the join and in parallax; look for sliding at horizon and edges.
- View the extension alone for stretch, holes and low resolution at the final frame size.
- Check alpha edges and occluders for chatter; check depth ordering of foreground elements.
- Compare perspective and scale to the plate (Brinkmann Ch. 2 "Perspective and the Camera").

## Pitfalls
- Flat cards are good only where parallax is small; near objects, strong lateral moves and wide lenses expose the flatness.
- Painting resolution must hold the framing and any push-in; resolution beyond frame is needed for camera moves.
- A bad solve slides the extension; it cannot be rescued by moving the card.
- Lighting, atmosphere and sharpness mismatches can hide in a single frame; judge integration on the moving sequence (Brinkmann Ch. 13 introduction).
- Time-varying elements in a still painting (clouds, water) need animation or planned treatment.
- Studio graph preference (`fundamentals/graph-conventions`): painting layers and rendered 3D enter as separate A branches of sequential Merges over the B background; each 3D/projection section lives in its own labelled Backdrop and reuses the single plate Read via Dots or PostageStamp.
- A large painting or transformed card can blow up the bbox; place any Crop after the compatible Transform/Reformat/CornerPin run (Crop does not concatenate) or rely on the Merge B-side bbox, and check memory at the largest frame (`fundamentals/quality-safeguards`).

## Sources
- Foundry 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/3d_compositing.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/projection_cameras.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/card.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/transformgeo.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geotransform.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/usd-3d-comp.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/cameratracker/camera_tracking.html
- Brinkmann 2e Ch. 2 "Perspective and the Camera"; Ch. 12 "Creating Elements"; Ch. 13 "Camera Movements", "Scale and Perspective"; Ch. 14 "Working with CG Elements".
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): sequential merges, backdrop separation, bbox containment.
