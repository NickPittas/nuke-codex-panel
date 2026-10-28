---
id: "nodes/particleemitter"
kind: "node"
title: "ParticleEmitter"
category: "particles"
summary: "ParticleEmitter is the required source node of Nuke's built-in particle system (NukeX and Nuke Studio only). It emits points, edges or faces of geometry over time, optionally using image or geometry as the particle shape."
aliases: ["Particle Emitter", "particle system", "3D particles", "emit particles", "particles nodes"]
tags: ["particles", "emitter", "simulation", "fx"]
requires: ["fundamentals/time-sampling", "fundamentals/coordinates"]
related: ["topics/3d-particles", "topics/custom-particles", "nodes/particleexpression", "nodes/particlemotionalign", "nodes/particletogeo", "nodes/positiontopoints"]
nodes: ["ParticleEmitter", "ParticleExpression", "ParticleMotionAlign", "ParticleToGeo", "ParticleMerge"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# ParticleEmitter

## Purpose
Generates the particles that other Particle nodes (forces, drag, curves, expression, caching) then modify. It is documented in the particles node group as NukeX and Nuke Studio only. With no geometry on `emit`, particles travel along the y axis.

## Inputs
- `particle`: image or geometry used as the particle; a further input appears so representations can be mixed (a PositionToPoints cloud can also be used).
- `emit`: geometry to emit from; PositionToPoints clouds with normals work too.
- `merge`: another particle system, including another ParticleEmitter.

## Controls
Scripting names: `start_frame` (0, may be negative), `emit_from` (points, edges, faces), `emit_order`, `rate` (10 per frame), `rate_variation`, `lifetime` (10 frames), `halflife`, `velocity` (1 unit/frame), `rotation_velocity`, `size` (0.1), `mass`, `spread`, `transfer_velocity`, `color`, `color_from_texture`, `input_order`, `frame_advance`, `max_clip_length`, `seed`, `channels` (a, b labels), `selection_only` for GeoSelect-driven emission. Many attributes have `_variation` Gaussian ranges and optional texture-channel modulation (`rate_channel`, `lifetime_channel`, `velocity_channel`, `size_channel`, `mass_channel`).

## Verify
- Connect a Viewer, press play from `start_frame`, and watch the stream; check emit direction, rate and lifetime.
- Change `seed` to confirm randomness is intended.

## Pitfalls
- Negative `start_frame` pre-rolls; positive delays emission.
- Emission count is not a fixed guarantee: `emit_order` randomly uses `rate` (docs: exact number per frame), but uniformly emits from every vertex each frame and ignores `rate` (use `vertex_rate`, per vertex per frame), and in order emits from vertices in ascending order. `rate_variation` adds Gaussian randomness, and an enabled rate/vertex channel texture modulates the count (a rate channel below 1 lessens it).
- Colour of the emitter geometry only applies with `color_from_texture`.
- Particles are channel-tagged; downstream nodes use the `channels` knob to act on a or b.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particleemitter.html
- Group index: https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particles_nodes_nukex.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
