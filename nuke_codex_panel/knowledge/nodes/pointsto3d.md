---
id: "nodes/pointsto3d"
kind: "node"
title: "PointsTo3D"
category: "tracking-3d"
summary: "PointsTo3D calculates the 3D position of a 2D feature from two or three points marked at different frames through a tracked camera. Foundry documents it in the Transform nodes group."
aliases: ["Points To 3D", "2D point to 3D", "triangulate point", "locator from track"]
tags: ["triangulation", "camera", "point", "locator"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["topics/camera-tracking", "topics/matchmove", "nodes/cameratracker", "nodes/camera", "nodes/reconcile3d"]
nodes: ["PointsTo3D", "CameraTracker", "Axis"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# PointsTo3D

## Purpose
Finds a single 3D point from parallax: mark the same feature at different frames and it solves its position. Useful for placing an Axis or locator at a real scene feature.

## Inputs
- `cam`: a camera whose motion matches the footage (CameraTracker output or imported camera).
- `img`: the sequence containing the 2D point.

## Controls
Scripting names: `cameraMovType` (default free move; there is also a nodal mode; its details were not read for this reference), `pointA/B/C` (2D point xy), `ref_timeA/B/C` (the frame each point is set at; leaving C at 0 omits it), `point3D` (result), `point2D`, plus a Calculate button and a generate-axis action for free move.

Workflow in the docs: put A on the feature at one frame and set frame; change to a different camera angle, mark B and set frame; do the same for C; calculate.

## Verify
- Look at the projected 2D marker through the camera at other frames.
- Create an Axis from the result and check it sticks.

## Pitfalls
- Free move needs real camera translation; a nodal pan has no parallax.
- Pick frames with a large angular change.
- Re-mark if the camera is later re-solved.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/pointsto3d.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
