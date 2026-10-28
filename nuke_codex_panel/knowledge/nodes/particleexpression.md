---
id: "nodes/particleexpression"
kind: "node"
title: "ParticleExpression"
category: "particles"
summary: "ParticleExpression sets particle attributes with expressions that may return vectors. Prefer the dedicated Particle force and shape nodes first, and use expressions when no native node expresses the behaviour."
aliases: ["Particle Expression", "particle expressions", "custom particle behaviour"]
tags: ["particles", "expression", "velocity", "custom"]
requires: ["fundamentals/time-sampling", "fundamentals/coordinates"]
related: ["topics/custom-particles", "topics/3d-particles", "nodes/particleemitter", "nodes/particlemotionalign", "nodes/particletogeo"]
nodes: ["ParticleExpression", "ParticleEmitter", "ParticleGravity", "ParticleDrag"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# ParticleExpression

## Purpose
Adjusts a running particle system through expressions on color, opacity, size, mass, acceleration, force, position, velocity, frame and channels. Syntax resembles Nuke expressions but some functions differ or are unavailable. Unlike the Expression node it can return a 3D vector; a single number in a vector field becomes that value on every component.

## Inputs
- `particles`: the particle system to alter.

## Controls
Scripting names: `colexpr`, `opacity_expr`, `sizeexpr`, `massexpr`, `accelexpr`, `forceexpr`, `posexpr`, `velexpr`, `frameexpr`, `channelsexpr`; each has an "only on new" flag (e.g. `sizeexpr_onlynew`). `new_channels` sets the channels assigned when `channelsexpr` is true; if none is selected, matching particles are deleted.

Temporary variables: `temp_name0..3` with `temp_expr0..3` and per-particle toggles `temp_expr0_pp`.. for long expressions reused in several fields.

Conditions tab: `probability`, `min_age`, `max_age` (age is lifetime normalized 0-1), `seed`, `channels`; Region tab: `region`, `region_invert`.

## Verify
- Test one attribute at a time and play from the emitter's start.
- Use `only on new` to separate birth values from per-frame updates.
- Confirm that scalar returns behave as intended in vector fields.

## Pitfalls
- Known Particle nodes (gravity, drag, speed limit, point force, curve) are more readable than expressions; the group index lists them.
- Expressions copied from normal Nuke may fail.
- `channelsexpr` with no destination deletes particles.

## Sources
- https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particleexpression.html
- Group index: https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particles_nodes_nukex.html
- Static documentation facts only (runtime_verified false): the docs header reads Nuke 17.1v2, so confirm the installed build, node class and licence in the running app.
