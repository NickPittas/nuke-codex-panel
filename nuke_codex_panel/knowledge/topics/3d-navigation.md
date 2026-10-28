---
id: "topics/3d-navigation"
kind: "topic"
title: "Navigating Nuke's 3D workspace"
category: "3d-basics"
summary: "How to enter the 3D Viewer, move the view without moving scene data, look through cameras, and read world/object/screen transform spaces. Separates Classic 3D from the New 3D System."
aliases: ["3d viewer", "viewer 3d mode", "look through camera", "orbit pan dolly", "3d navigation", "transform space"]
tags: ["3d", "viewer", "camera", "navigation", "coordinates"]
requires: ["fundamentals/coordinates"]
related: ["topics/geometric-primitives", "topics/rendering-3d", "topics/camera-projection", "topics/camera-tracking"]
nodes: ["Viewer", "Camera", "Scene", "GeoScene", "ScanlineRender", "Axis"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# Navigating Nuke's 3D workspace

## Applicability
Use when inspecting, placing or debugging any 3D setup. First decide which system the scene uses: Classic 3D nodes (green, menu 3D > 3D Classic, Scene node) or New 3D System nodes (colored, menu 3D > 3D, mostly `Geo*`, GeoScene). The Viewer 3D mode works for both but draws them with different back ends: Classic uses the "Nuke" renderer, New 3D uses Hydra; the Viewer renderer knob defaults to GL, which covers both. Do not mix the two node families in one scene tree.

## Workflow
1. Hover the Viewer and press Tab or V (Classic doc) / V (New doc), or use the view dropdown, to toggle 2D/3D. 3D shows scene data; 2D shows the render node's output.
2. Built-in views (used when no camera is selected): right X, left Shift+X, top C, bottom Shift+C, front Z, back Shift+Z, three-quarter perspective V. F fits the whole scene.
3. Default Nuke scheme: Alt+middle-drag dolly, Alt+left-drag pan, Ctrl/Cmd+left-drag tilt/spin, Ctrl/Cmd+Shift+left-drag roll. Preferences > Panels > Viewer Handles > 3D control type (Nuke, Maya, Houdini, Lightwave, Modo) remaps these, and also remaps pan/zoom in the node graph and 2D Viewers.
4. To look through a camera or light: pick it in the dropdown at the top right of the 3D Viewer, or select a Camera and press H (Classic doc). The lock button (Ctrl/Cmd+L) ties the view to the selected camera or light. Ctrl/Cmd+click on it enters interactive mode, where +/- change that object's translate instead of zooming.
5. Transform handles use the Viewer's transform space (`viewerTransformSpace`): object (relative to the object's own orientation), screen (flat to the monitor, no Z translation) or world (scene XYZ axes). The mini axes bottom-left always show world axes.
6. The render camera is the node wired to the render node's `cam` input. The Viewer's look-through camera is only a viewing choice.

## Verify
- The viewing-camera dropdown names the camera you intended, and the render node's `cam` input names the camera you intend to render.
- Toggle to 2D: the render node output shows the framing seen through the render camera.
- Before typing translate values on a rotated object, confirm the Viewer transform space: X in object space can be Z in world space.

## Pitfalls
- Everything open in the Properties Bin appears in the 3D Viewer even when not wired to the Scene/GeoScene feeding the render node (Classic doc); a visible object may not render.
- Cameras appear in the viewing dropdown only if they are in the current data stream or their panel has been opened.
- Navigation keys only move the viewport. Interactive camera mode edits the selected camera or light's real values.
- Camera-space and image-space numbers differ from world numbers: the default render camera sits at the origin facing negative Z, and render pixels come from the output format, not from scene units.
- Scene units are not meters unless the scene says so (New 3D Camera `world_to_meters`, Use Scene Scale).
- Moving the camera changes perspective relations; changing only the lens at one position changes framing (Brinkmann, Ch. 2 "Perspective and the Camera", "Motion Parallax").
- A shortcut documented here may be remapped by the 3D control type preference; confirm in the running UI before scripting expectations.

## Sources
- Foundry Nuke 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/using_3d_viewer.html (Classic Using the 3D Viewer)
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/viewing-scene.html (New 3D Viewing Your Scene)
- https://learn.foundry.com/nuke/17.1/content/comp_environment/3d_compositing/setting_up_scene.html (Classic Setting Up a Scene)
- https://learn.foundry.com/nuke/17.1/content/reference_guide/image_nodes/viewer.html (viewerTransformSpace)
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/usd-3d-comp.html (two systems)
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/camera.html (New 3D Camera)
- Brinkmann, The Art and Science of Digital Compositing 2nd ed., Ch. 2 "Depth, Distance, and Perspective".
