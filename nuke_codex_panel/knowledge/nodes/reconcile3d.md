---
id: "nodes/reconcile3d"
kind: "node"
title: "Reconcile3D"
category: "tracking-3d"
summary: "Reconcile3D projects a 3D point through a camera into 2D screen position, to lock a photographed plate to a 3D scene or track. It outputs XY and keyframes, and can apply the resulting transform."
aliases: ["Reconcile 3D", "3D point to 2D", "project 3D point to screen", "lock plate to 3D"]
tags: ["reconcile", "camera", "track", "2d position"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["topics/matchmove", "topics/camera-tracking", "topics/rig-removal", "nodes/camera", "nodes/axis", "nodes/tracker", "nodes/pointsto3d"]
nodes: ["Reconcile3D", "CameraTracker", "Axis", "Tracker"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Reconcile3D

## Purpose
Turns a 3D point into x,y coordinates in the camera. The point comes from its own fields or the optional Axis, passes through the camera, and the result goes to the XY output. Foundry describes this as a way to lock a photographed plate to a 3D scene or track.

## Inputs
- `axis`: point control coordinates are relative to this optional input.
- `cam`: the viewing camera, e.g. from CameraTracker or a third-party package.
- `img`: the image where the 3D point is positioned; its format sets the output resolution.

## Controls
Scripting names: `point` (3D point xyz), `output` (XY), `outputxyz` (absolute 3D point), `calc_output` (live updates), a "create keyframes" action over a frame range, `track` (point of interest in the image), `offset`, `stabilize` (reverses the transform), `filter` (Parzen), `clamp`, `black_outside`, `motionblur`, `shutter`, `shutteroffset`.

By default the transform moves the track point to the projected 3D point, moving the plate to match the 3D scene; `stabilize` moves the projected point to the track point instead, removing 3D motion.

## Verify
- Compare the output XY with the visible feature in the plate across frames.
- Check units: image pixels, with the format from `img`.

## Pitfalls
- The point must be in front of the camera or it evaluates incorrectly.
- Output size depends on the `img` format, not the project.
- Live calculation is off until enabled.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/reconcile3d.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
