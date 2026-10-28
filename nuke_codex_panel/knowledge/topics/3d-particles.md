---
id: "topics/3d-particles"
kind: "topic"
title: "Using Nuke's 3D particle system"
category: "planar-particles"
summary: "Build particle effects from a ParticleEmitter, force nodes and a render through the classic 3D system. Covers emission, per-particle attributes, channels, simulation steps, caching and the limits of particles in the new 3D system."
aliases: ["ParticleEmitter", "Nuke particles", "snow rain smoke particles", "particle forces", "particle cache", "emit from geometry"]
tags: ["particles", "particleemitter", "channels", "forces", "cache", "classic-3d", "sprites"]
requires: ["fundamentals/time-sampling", "fundamentals/coordinates", "fundamentals/channels-data"]
related: ["topics/custom-particles", "topics/rendering-3d", "topics/geometric-primitives", "topics/motion-blur-depth-of-field", "topics/alembic"]
nodes: ["ParticleEmitter", "ParticleExpression", "Scene", "ScanlineRender", "Card", "PositionToPoints"]
version: "Nuke 17.1 documentation; Particles nodes are NukeX/Studio only and classic 3D; new 3D integration is limited; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# Using Nuke's 3D particle system

## Applicability
Use for snow, rain, dust, sparks, fog cards, debris and simple light trails that must live in 3D, be lit/shaded and seen through a camera. The particle node set belongs to the **classic** 3D system (Scene, ScanlineRender classic). It needs NukeX or Studio. It is a compositor-grade system, not a fluid, rigid-body or smoke solver; for those, render in a DCC.

## Workflow
1. Minimum setup: ParticleEmitter into a Viewer; add a Scene and classic ScanlineRender with a Camera to render to 2D.
2. Inputs: **emit** (geometry or a PositionToPoints cloud as the source; if absent, particles fly along y from the origin), **particle** (image or geometry shown for each particle; more numbered inputs add random variety) and **merge** (another particle system).
3. Emission: emit from (points, edges, faces, bbox), emit order, rate (exact particles per frame), rate variation, only emit from selected (GeoSelect). A texture channel (rate, lifetime, velocity, size, mass channel) can modulate values from the emitter texture.
4. Lifespan and look: max lifetime and range, start at (negative values pre-roll so snow is already falling), velocity and range, size, mass (matters only when forces are applied), spread, color, color from texture, random seed (varies all range controls).
5. Channels: particles live in channel a, b etc.; force and filter nodes can target specific channels, so use separate channels for separate behaviours.
6. Shape the motion with force nodes (ParticleGravity, Wind, Drag, Turbulence, Bounce, Vortex, PointForce, SpeedLimit); ParticleSettings steps per frame increases simulation substeps (use the lowest value that removes jagged motion).
7. Rotation velocity applies to geometry particles; the docs state sprite rotation is not currently supported.
8. Freeze or isolate by channel with ParticleToGeo; spawn secondary emitters with ParticleSpawn.
9. Cache with ParticleCache at the very end of a single (or merged) particle stream, set a file ending in .nkpc with a frame variable and padding (extra frames for motion blur), Render, then read from file. It does not replace the live graph; upstream changes are flagged.

## Verify
- Play from the start frame with the Viewer in 3D and through the render camera.
- Check particle count, size and speed at the first rendered frame, after a long pre-roll, and at the last frame.
- Re-render the cache from scratch and compare a middle frame, to confirm the cache matches live.
- Render the beauty and check depth, shadows and motion blur settings of the render node.

## Pitfalls
- New 3D system: only limited integration. Particles can feed GeoPoints (a points prim that cannot be textured or oriented) or the LABS GeoPointInstancer (instances real geometry, or camera-facing quads needing a real camera; no particle textures or animated textures).
- A Particle cache complaining "Particle cache data not found" usually needs larger padding.
- ParticleCache cannot sit mid-chain or under a Scene joining two separate streams.
- Particles are simulated: scrubbing or distributed renders must agree on seed, steps and start frame; cache for farms.
- Large rate and lifetime values are slow; keep counts low and use sprites for distant elements.

## Sources
- Foundry Nuke 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/particles/creating_3d_particles.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/particles/connecting_particle_nodes.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/particles/emitting_particles.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/particles/modifying_particle_movement.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/particles/adjusting_particle_settings.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/particles/caching_particles.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particles_nodes_nukex.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particleemitter.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particletogeo.html
- https://learn.foundry.com/nuke/17.1/content/comp_environment/usd-3d-comp/usd-3d-comp.html (particle limits in new 3D)
- Brinkmann 2e, ch. 12 "Creating Elements" and ch. 14 "Working with CG Elements" (when to produce or modify elements in 3D versus 2D).
