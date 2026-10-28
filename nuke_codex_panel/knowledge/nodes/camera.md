---
id: "nodes/camera"
kind: "node"
title: "Camera"
category: "3d-nodes"
summary: "Camera defines a viewing, render or projection camera in Nuke 3D. Classic 3D and New 3D both have a node named Camera with different wiring and knob names; check which one you have."
aliases: ["Camera node", "3D camera", "projection camera", "GeoCamera", "GeoEditCamera", "render camera"]
tags: ["camera", "projection", "focal length", "aperture", "classic 3d", "new 3d"]
requires: ["fundamentals/coordinates", "fundamentals/node-selection"]
related: ["topics/camera-projection", "topics/rendering-3d", "topics/camera-tracking", "nodes/scanlinerender", "nodes/project3d", "nodes/scene", "nodes/cameratracker", "nodes/axis"]
nodes: ["Camera", "GeoCamera", "GeoEditCamera", "ScanlineRender", "Project3D"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Camera

## Purpose
A Camera feeds a renderer (ScanlineRender cam input), a Scene or GeoScene (viewing camera choice in the Viewer), or a projector (Project3D / Project3DShader cam input). It can also read one camera per node from .fbx, .abc or .usd files.

Two systems share the name. Classic Camera comes from 3D > 3D Classic (green nodes); New 3D Camera comes from 3D > 3D. Foundry states the node is also named Camera in both, and that the New 3D one is the connector for nodes that take `cam`, `axis` or `look at` inputs. GeoCamera / GeoEditCamera instead create or edit USD camera prims directly and cannot feed every `cam` input.

## Inputs
- Classic: `axis` (parent Axis overrides the transform knobs) and `look` (Camera, Light or Axis to aim at).
- New 3D: `axis`, `scene` (imports scene data for Live Read) and `look at`.

## Controls
Classic names (UI / scripting): projection tab `project_mode` (perspective, orthographic, uv, spherical; default perspective), `focal` 50, `haperture` 24.576, `vaperture` 18.672, `near` 0.1, `far` 10000, `win_translate`, `win_scale`, `winroll`, `focal_point`, `fstop`; transform `translate`, `rotate`, `scaling`, `rot_order`, `xform_order`; file tab `read_from_file`, `file`, `frame_rate`; look tab `look_axis`, `look_strength`.

New 3D names differ: `projection_mode`, `focalLength`, Live Read `read_from_scene_link`, `source_prim_path`, `world_to_meters`, `use_scene_scale`, plus snapshot buttons that bake a frame or range.

## Verify
- Look through the camera in the 3D Viewer and compare with the plate.
- Confirm focal length and apertures use millimetres consistent with the source camera.
- For a CameraTracker camera, check it follows the footage by placing a test Card.

## Pitfalls
- Wrong menu: classic and New 3D nodes are not interchangeable in one scene.
- Near clipping must stay positive.
- A projection camera needs the original photograph's focal length and apertures, not the render camera's.
- Unlinking a CameraTracker camera cuts its expression link to the solve.

## Sources
- Classic: https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/camera.html
- New 3D: https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/camera.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/working-with-cameras.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/projection_cameras.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
