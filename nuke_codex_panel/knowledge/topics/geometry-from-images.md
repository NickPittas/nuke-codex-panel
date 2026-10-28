---
id: "topics/geometry-from-images"
kind: "topic"
title: "Modeling 3D geometry from a 2D scene"
category: "advanced-3d"
summary: "Build proxy geometry for a shot by aligning shapes to footage with ModelBuilder using a solved camera. Single-view alignment is under-constrained, so use several frames or reference points to pin position, rotation and scale."
aliases: ["ModelBuilder", "model from plate", "proxy geometry", "build geo from footage", "align cards to footage", "photogrammetry-lite", "projection geometry"]
tags: ["modelbuilder", "camera", "parallax", "projection", "proxy-geo", "uv"]
requires: ["topics/camera-tracking", "fundamentals/coordinates"]
related: ["topics/camera-projection", "topics/set-extension", "topics/pointcloud-meshing", "topics/geometric-primitives", "topics/texture-projection"]
nodes: ["ModelBuilder", "Camera", "PointCloudGenerator", "Project3D", "ApplyMaterial", "Card"]
version: "Nuke 17.1 documentation; ModelBuilder creation needs NukeX/Studio (results usable in Nuke); no equivalent new-3D node is listed in the classic-to-new guide; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# Modeling 3D geometry from a 2D scene

## Applicability
Use when you need approximate surfaces under a projected plate (set extension, relighting, clean-up, shadows). Requires a solved, changing camera and the footage it came from (topics/camera-tracking). One image cannot define depth: a pixel marks a ray, not a point. Camera movement (parallax) between frames resolves position; without parallax or known sizes, geometry placement is a guess. Without a camera or source, ModelBuilder can still edit shapes but cannot align them.

## Workflow
1. Connect ModelBuilder: src (plate), cam (solved Camera), optional geo (reference point cloud, e.g. PointCloudGenerator), optional tex. Lock the Viewer to the input camera; align handles appear only then.
2. Create a starting shape in the toolbar (Point, Card, Cube, Sphere, Cone, Cylinder, Polygon) matching the real object: a card for a wall, a cube for a building. Click empty space to place at the Distance value (no fixed units; larger is farther), Shift-click to snap to existing geometry, drag to scale. With a reference cloud, select vertices first in Edit Mode so the shape is born aligned.
3. Align mode: drag vertices to the feature positions on the plate. **Object transform** keeps polygons flat and angles intact; **Vertex position** is flexible but can make non-planar faces.
4. Move the same vertex on a second frame: a line shows where the point must lie along its ray from the first frame. Place it along that line; then a few more vertices to lock rotation and scale. Keyed vertices turn purple.
5. Scrub and correct drifting vertices at further frames.
6. Edit shapes (extrude, merge faces and so on) to refine the model, keep display on wireframe or solid+wireframe while aligning.
7. Texture: if geometry matches the plate, project the plate; use bake Projection to create Project3D with a FrameHold locked to the texture frame (that is the 'frozen' camera and image), then ApplyMaterial. For added elements not in the footage, supply a separate texture and use UV unwrapping. Bake Selected geometry splits shapes into geometry nodes for different treatment.

## Verify
- Scrub the entire range and from the first frame: vertices stay on features with no sliding, and the shape sits correctly in the 3D Viewer relative to the point cloud and ground.
- Project the plate from the texture frame; at other frames the projection should not swim except where geometry is wrong (parallax errors show first at depth edges).
- Silhouette tests: view from a side camera; a card that should be a box will reveal itself.

## Pitfalls
- Rays, not points: placing vertices at one frame only gives a shape that is right from that angle only.
- Hidden or unseen surfaces have no data; projected texture streaks on faces seen at grazing angles.
- Scale depends on the camera solve scale; align it to a known measurement first.
- Vertex editing can break planarity, wrecking perspective on windows and walls.
- ModelBuilder has no new-3D equivalent in the classic-to-new guide. Bake to geometry nodes; verify separately that the result works in the target 3D system.
- Poisson or dense-cloud meshes are alternatives for organic scenes (topics/pointcloud-meshing), while hard-surface proxies suit ModelBuilder.

## Sources
- Foundry Nuke 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/modelbuilder/creating_3d_models.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/modelbuilder/creating_shapes.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/modelbuilder/positioning_shapes.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/modelbuilder/applying_textures.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/modelbuilder/exporting_separate_geo_nodes.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/modelbuilder.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html (no ModelBuilder equivalent)
- Brinkmann 2e, ch. 14 "3D Compositing" (cards in a 3D environment, depth ordering, camera as viewpoint).
