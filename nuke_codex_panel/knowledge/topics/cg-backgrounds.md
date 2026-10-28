---
id: "topics/cg-backgrounds"
kind: "topic"
title: "Adding a 3D background to a CG render"
category: "production-workflows"
summary: "Place a CG render in front of, or depth-sorted with, a background built from Nuke 3D geometry: match cameras and units, choose 2D merge, depth-aware ScanlineRender bg, or deep, and verify occlusion, depth cues and format."
aliases: ["3d background for cg", "cg over 3d environment", "scanlinerender bg input", "z blend", "depth composite cg", "environment behind cg element"]
tags: ["3d", "cg", "background", "depth", "integration", "production"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data", "fundamentals/coordinates"]
related: ["topics/rendering-3d", "topics/multipass-cg", "topics/motion-blur-depth-of-field", "topics/camera-projection", "topics/pointclouds-from-cg"]
nodes: ["ScanlineRender", "Scene", "GeoScene", "Camera", "Merge", "DepthToPoints", "GeoPoints"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-14"]
---
# Adding a 3D background to a CG render

## Applicability
Use when the CG element already exists as a rendered image (often EXR from another application) and the surrounding environment is built or projected in Nuke 3D (cards, simple geometry, projected paintings). Inputs you need: the CG's camera (position, rotation, lens, aperture, clip), frame range and time offset, world scale/axis convention, alpha state, and, for depth sorting, a depth channel whose representation (distance along Z vs ray distance, absolute vs reciprocal, units, no-object value) and space are established from the renderer or pass that produced it.

Choose a method:
1. 2D merge. If the CG is entirely in front, render the 3D background with the same camera and Merge the CG over it. Cheapest; no depth needed.
2. Depth-aware ScanlineRender. Connect the CG image to `bg`. Foundry documents that `bg` determines the output resolution and that, if it contains a depth channel, ScanlineRender considers it in Z-buffer and Z-blend calculations (both Classic and New ScanlineRender). The page does not state the expected depth encoding for `bg`; do not assume one. Classic controls: `ztest_enabled`, Z-blend mode/range.
3. Deep. Classic ScanlineRender outputs deep data when a Deep node is downstream. Foundry states New 3D integration with Deep nodes is currently limited, so check the installed node set.
4. Point/position geometry. CG position or depth passes can become point clouds (DepthToPoints, PositionToPoints map to GeoPoints in New 3D); see topics/pointclouds-from-cg.

## Workflow
1. Match cameras: import the CG camera (FBX/Alembic/USD through Camera), set matching lens/aperture and resolution; in New 3D check `world_to_meters`/Use Scene Scale because mismatched scene scale yields wrong lens-derived values.
2. Build the 3D background in the same generation as the render node: Classic Scene or New GeoScene. Use one scene tree per renderer.
3. Render the background alone through the shared camera and compare to the CG at keyframes: horizon, ground contact and scale must agree.
4. For depth sorting, establish what the CG depth channel actually holds (renderer/AOV docs, metadata, or a test). Foundry documents only ScanlineRender's own depth output: New ScanlineRender's `one_over_z` toggle outputs Nuke-style 1/Z when on (no-object 0) or absolute camera distance when off (no-object infinite). Whether and how to convert a foreign depth pass for `bg` is not documented on the pages cited here, so do not apply a reciprocal blindly. Prove it on the shot: place test cards in front of and behind a CG surface of known depth, check which pixels win, and if wrong take the conversion from the producing renderer's AOV documentation. Other depth consumers (ZDefocus, DepthToPoints, deep conversion) have their own documented input contracts.
5. After merge, add shared environment cues: atmosphere/haze, depth of field, motion blur and grain (Brinkmann, Ch. 13 "Scale and Perspective", "Motion Blur"; Ch. 14 "Working with CG Elements").
6. Grain match the CG separately from the plate (lesson-14, course practice for one shot). View one channel at a time (R, G, B), compare CG against plate at comparable black points, match grain size first, then irregularity and intensity, and apply it to the CG only through its alpha so the plate is not regrained. In that footage green grain was nearly invisible and blue was the noisiest; that is a property of the shot, not a universal ratio, so measure the actual plate.

## Verify
- Overlay the CG alpha edge over the background in the 2D Viewer; no halos from alpha-state mismatch.
- Place test cards in front and behind the CG subject at different depths; occlusion must follow depth in every frame.
- Output format equals the intended frame, since `bg` determines it.
- Scrub the shot; background parallax must agree with the camera move.

## Pitfalls
- The Classic/New ScanlineRender distinction is critical; Foundry warns the names match.
- Depth for antialiased/semi-transparent edges and motion blur is unreliable for depth tests; this is a limit of Z compositing rather than a node fault [INFERENCE from depth-sorting practice; test on the shot].
- Lighting, grade, lens distortion and grain of CG and 3D background differ; CG often needs black-level and grain matching (Brinkmann Ch. 14).
- A 3D background built from stills has parallax only where geometry exists; projection limits apply (topics/camera-projection).
- Overscan/format expansion on `bg` can change the render region (New `render_region_mode`).

## Sources
- Foundry 17.1: https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/scanlinerender.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/scanlinerender.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/usd-3d-comp.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/rendering-scanline.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/camera.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html
- Brinkmann 2e Ch. 13 "Additional Integration Techniques"; Ch. 14 "Working with CG Elements".
- Lesson 14.srt (lesson-14; ASR, teaching-practice only): 00:45:06–00:48:27 per-channel grain matching, size first, grain through alpha, blue noisiest.
