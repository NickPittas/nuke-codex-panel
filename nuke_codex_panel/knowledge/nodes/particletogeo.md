---
id: "nodes/particletogeo"
kind: "node"
title: "ParticleToGeo"
category: "particles"
summary: "ParticleToGeo turns particles into geometry and controls them by channel, including freezing selected particles at a given frame. NukeX and Nuke Studio particle node."
aliases: ["Particle To Geo", "freeze particles", "particles to geometry", "sprite alignment"]
tags: ["particles", "geometry", "channels", "freeze"]
requires: ["fundamentals/time-sampling", "fundamentals/channels-data"]
related: ["topics/3d-particles", "topics/custom-particles", "nodes/particleemitter", "nodes/particlemotionalign"]
nodes: ["ParticleToGeo", "ParticleEmitter"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# ParticleToGeo

## Purpose
Isolates particles by channel at any point in the graph, freezes particles in selected channels, and aligns sprite particles. Useful for freezing some particles while others emit normally, or applying an effect to only one channel.

## Inputs
- `particles`: the particle system to convert.

## Controls
Scripting names: `render_mode`, `channels` (default all; a, b labels set in ParticleEmitter), `align` (none, spin, velocity), `use_frame` ("specify frame") and `frame` (default 50; freezes the selected channels' particles at that simulation frame).

## Verify
- Emit into channels a and b, then freeze only a; b must keep moving.
- Confirm `align` choice: spin follows rotation, velocity follows motion.

## Pitfalls
- `frame` does nothing unless `use_frame` is enabled.
- It operates on the system's channels, so the emitter's `channels` assignment must be right first.
- `frame` is a simulation frame; compare it with the emitter's `start_frame`.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particletogeo.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
