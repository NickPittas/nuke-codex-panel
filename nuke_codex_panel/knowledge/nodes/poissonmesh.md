---
id: "nodes/poissonmesh"
kind: "node"
title: "PoissonMesh"
category: "point-clouds"
summary: "PoissonMesh reconstructs a mesh from a dense point cloud using Poisson surface reconstruction (NukeX and Nuke Studio). New 3D counterpart: GeoPointsToMesh."
aliases: ["Poisson Mesh", "point cloud to mesh", "GeoPointsToMesh", "Poisson surface reconstruction"]
tags: ["mesh", "poisson", "point cloud", "surface"]
requires: ["fundamentals/coordinates"]
related: ["topics/pointcloud-meshing", "topics/geometry-from-images", "nodes/pointcloudgenerator", "nodes/modelbuilder"]
nodes: ["PoissonMesh", "GeoPointsToMesh", "PointCloudGenerator", "ModelBuilder"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# PoissonMesh

## Purpose
Turns a dense point cloud into a usable 3D mesh, e.g. for modelling or approximate set geometry. Based on Poisson Surface Reconstruction (Kazhdan, Bolitho, Hoppe). The classic page documents the dense cloud from PointCloudGenerator as the input; GeoPointsToMesh uses the geometry normals of its input.

## Inputs
- Unnamed: the PointCloudGenerator (classic) or scene stage (GeoPointsToMesh).

## Controls
Classic scripting names: `useSelection` (use GeoSelect flags upstream), `useFiltering` (keep faces whose normals are similar to the input), `depth` (8), `scale` (1.25), `solverDivide` (8), `isoDivide` (8), `samplesPerNode` (1; small for clean data, larger for noisy), `confidence` (use normal size as confidence; slower).

GeoPointsToMesh: `prim_path`, `mask_patterns`, `use_selection`, `use_filtering`, `depth` (integer, maximum 10 because each step raises solver memory), `scale`, `solver_divide`.

## Verify
- Inspect the mesh from several angles against the footage through the solved camera.
- Compare density and holes with the cloud; adjust depth in steps.

## Pitfalls
- Higher depth means more memory and time.
- Noisy clouds need larger `samplesPerNode`.
- Clean rejected points before meshing; mesh quality follows the cloud.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3d_nodes/poissonmesh.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/3dnew_nodes/geopointstomesh.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
