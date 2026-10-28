---
id: "topics/custom-particles"
kind: "topic"
title: "Creating your own particles"
category: "planar-particles"
summary: "Customize particle behaviour with ParticleExpression for per-particle attribute maths or ParticleBlinkScript for compiled Blink kernels, after native emitter and force nodes fall short."
aliases: ["ParticleExpression", "ParticleBlinkScript", "custom particle behaviour", "particle blink kernel", "particle attributes", "particle op"]
tags: ["particles", "expression", "blink", "attributes", "per-particle", "age", "kernel"]
requires: ["topics/3d-particles", "fundamentals/channels-data"]
related: ["topics/geometry-animation-deformation", "topics/alembic"]
nodes: ["ParticleExpression", "ParticleBlinkScript", "ParticleEmitter", "ParticleToGeo"]
version: "Nuke 17.1 documentation; Particles nodes are NukeX/Studio only and classic 3D; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Creating your own particles

## Applicability
Use when ParticleEmitter and the native force nodes (gravity, wind, drag, turbulence, bounce, vortex, curve, look at) cannot give the behaviour. Try native nodes first; a custom expression replaces a native node only when the result needs maths those nodes lack (for example a procedural path or an attribute tied to age or id). Choose **ParticleExpression** for attribute maths, **ParticleBlinkScript** for kernels that need compiled logic. Classic 3D particles only.

## Workflow
1. Connect the node after ParticleEmitter (input `particles`). Limit the effect with Conditions where available (channels, age window, probability).
2. ParticleExpression: up to four temporary named expressions (name = expression, with a per-particle toggle) to reuse long sub-expressions; then expressions for color, opacity, size, mass, accel, force, pos, vel. Each has only on new, so the expression applies once at emission instead of every frame.
3. Expression values: scalar or 3D vector. A single number N written to a vector field (vel, accel) becomes (N, N, N); build vectors with v(x,y,z). Available names include age (frames), life (max lifetime), id, new, pos, vel, size, mass, opacity, color; plus math functions (sin, cos, pow, hypot, mag, norm, random, randomv, uniformsamplesphere). Not all normal Nuke expression functions exist, and some particle functions are not in normal expressions.
4. Example from the docs: pos expression `sin (age * 10) * 5` emits particles randomly on a single static line.
5. ParticleBlinkScript: write or load a kernel (kernel file `.rpp`), **Recompile** (errors display), **Create Knobs** for kernel parameters, and Publish to bundle as a group/gizmo; protect-kernel encodes it. Conditions tab: probability (0..1 chance a particle is affected), min/max age (normalized 0..1), seed, channels. Region tab confines the effect to a sphere, box, half-space or cylinder, optionally inverted.
6. Use ParticleToGeo to isolate or freeze channels and ParticleSpawn for secondary emitters when no maths is needed.

## Verify
- With a minimal expression or kernel, confirm the change only on the intended channel and age range; set the Viewer to the render camera and scrub.
- Compare random-seed variations; effects must not change on every playback unless intended.
- Test that only-on-new and per-particle settings behave as designed by looking at particles emitted before and after the node.
- Cache the result (topics/3d-particles) for farm renders.

## Pitfalls
- Re-evaluating long expressions each frame is slow at high particle counts; compute once on new or use temporary expressions.
- Vector versus scalar confusion: broadcasting N into every component moves particles diagonally.
- Particle expressions are not Expression-node expressions: test each function in the target field.
- Kernels run on every selected particle each step; define conditions to keep cost low, and check device/GPU availability on render machines [INFERENCE from the Blink design docs; verify on the installed build].
- Custom behaviour hides logic; document the intent in the node label.

## Sources
- Foundry Nuke 17.1: https://learn.foundry.com/nuke/17.1/content/comp_environment/particles/adjusting_particles_using_expressions.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particleexpression.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particleblinkscript.html
- https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particles_nodes_nukex.html (node list)
- https://learn.foundry.com/nuke/17.1/content/reference_guide/particles_nodes/particletogeo.html
