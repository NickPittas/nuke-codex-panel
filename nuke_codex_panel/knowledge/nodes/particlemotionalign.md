---
id: "nodes/particlemotionalign"
kind: "node"
title: "ParticleMotionAlign"
category: "particles"
summary: "ParticleMotionAlign realigns particles along their direction of motion, for streaks, arrows or instanced geometry that should face where it travels. NukeX and Nuke Studio particle node."
aliases: ["Particle Motion Align", "align particles to velocity", "orient particles"]
tags: ["particles", "alignment", "velocity", "motion"]
requires: ["fundamentals/coordinates"]
related: ["topics/3d-particles", "topics/custom-particles", "nodes/particleemitter", "nodes/particletogeo"]
nodes: ["ParticleMotionAlign", "ParticleEmitter", "ParticleToGeo"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# ParticleMotionAlign

## Purpose
Rotates every particle so it aligns with its direction of movement. Place it in the particle stream after the emitter and forces.

## Inputs
- `particles`: the particle system to align.

## Controls
Scripting names: `render_mode`; Conditions tab `probability` (default 1), `min_age` (0), `max_age` (1), `seed`, `channels` (default all); Region tab `region`, `region_invert`. Age is normalized lifetime between 0 and 1.

## Verify
- Use an obviously directional particle shape (a thin card or small cone) and watch it follow the path.
- Re-check after adding force nodes; place MotionAlign after nodes that change velocity [inference].

## Pitfalls
- It aligns only; spin or sprite alignment at the geometry conversion step is a separate ParticleToGeo `align` option.
- Region and condition filters can leave some particles unaligned by design.
- No guaranteed behaviour was verified for a particular geometry's forward axis; test.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particlemotionalign.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
