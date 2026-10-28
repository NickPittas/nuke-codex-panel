---
id: "topics/pointcloud-meshing"
kind: "topic"
title: "Converting point clouds to meshes"
category: "camera-tracking"
summary: "Turn a dense, filtered point cloud with normals into a Poisson mesh for projection or modelling. A sparse CameraTracker cloud or a raw point set is not automatically a usable mesh."
aliases: ["PoissonMesh", "dense point cloud", "PointCloudGenerator mesh", "GeoPointsToMesh", "mesh from points", "bake groups to mesh"]
tags: ["pointcloudgenerator", "poisson", "mesh", "normals", "dense-tracking", "projection"]
requires: ["topics/camera-tracking", "fundamentals/coordinates"]
related: ["topics/camera-projection", "topics/set-extension", "topics/pointclouds-from-cg", "topics/geometry-from-images"]
nodes: ["PointCloudGenerator", "PoissonMesh", "Project3D", "ApplyMaterial", "PositionToPoints"]
version: "Nuke 17.1 documentation; analysis nodes are NukeX/Studio only; classic PointCloudGenerator/PoissonMesh vs new-3D GeoGeneratePoints/GeoPointsToMesh; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# Converting point clouds to meshes

## Applicability
Use when you need approximate surfaces (projection targets, shadow catchers, layout) from a shot. Inputs: a solved camera (CameraTracker or imported), the Source footage it was solved from, and a **dense** cloud with normals. The sparse CameraTracker point cloud has no normals and too few points; it is a layout reference, not mesh input. Poisson reconstruction yields a smooth, closed-ish blobby surface; it will not reproduce hard edges, thin objects or moving, reflective or textureless regions.

## Workflow
1. Classic system: PointCloudGenerator with inputs Source, Camera, optional Mask (matte moving objects). New 3D: GeoGeneratePoints (its inputs match; it carries a prim path).
2. **Analyze Sequence** to set keyframes (large enough baseline to triangulate); add/delete keyframes by hand if needed; check Calculated Accuracy per frame.
3. **Track Points** over chosen frame ranges. Point Separation (px) sets density; lower is denser and slower. Track Threshold terminates unreliable tracks.
4. Filter: keep Display rejected points on, raise Angle Threshold (docs: below 5 degrees is likely wrong) and Density Threshold, then **Delete Rejected Points**. Compare cloud to plate with a Viewer wipe.
5. Optionally create Groups (vertex selection) around one object or surface.
6. Mesh, either way:
   - PoissonMesh connected to the PointCloudGenerator (classic), or GeoPointsToMesh (new 3D, NukeX).
   - Or **Bake Selected Groups to Mesh** on the generator (the baked mesh is not editable).
7. Tune only what you need: Depth (default 8, max 10; each step multiplies memory by 8), Scale, Solver Divide/Iso Divide for memory, Samples per Node (1-5 clean, 15-20 noisy), Confidence, Use Selection and Filtering.
8. Texture: Project3D on the plate into ApplyMaterial mat, mesh into the other ApplyMaterial input (new 3D uses Project3DShader/GeoBindMaterial).

## Verify
- Overlay the mesh in the 3D Viewer locked to the solved camera; silhouette should follow the plate at several frames.
- Check holes, floating islands and stretched triangles from isolated points; delete or group them out.
- Render a Project3D texture and scrub: texture should not slide on the mesh.

## Pitfalls
- A sparse cloud, a cloud without normals or wrong normals gives garbage. PoissonMesh is documented for PointCloudGenerator input; other clouds (for example PositionToPoints) are not covered by that page, so test them.
- Foundry notes PoissonMesh works only in NukeX because its mesh data is not stored in the node; bake or export the mesh before handing the script to plain Nuke [INFERENCE: confirm on the installed licence].
- Mesh quality depends on camera-track quality; fix the solve first.
- Mesh export needs the camera too (FBX) for any later projection.
- Classic and new nodes do not mix: a classic mesh needs a classic Scene/ScanlineRender.

## Sources
- Foundry Nuke 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/point_clouds_meshes/using_poissonmesh.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/poissonmesh.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/pointcloudgenerator.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/point_clouds_meshes/tracking_dense_point_cloud.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/point_clouds_meshes/filtering_your_point_cloud.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/point_clouds_meshes/connecting_pointcloudgenerator.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/point_clouds_meshes/adding_texture_poissonmesh.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/point_clouds_meshes/creating_mesh_point_cloud.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geogeneratepoints.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geopointstomesh.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/nodes_classic_to_new.html (classic/new equivalents)
- Brinkmann 2e, ch. 14 "3D Compositing" (2.5D/3D compositing context).
