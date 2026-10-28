---
id: "nodes/timewarp"
kind: "node"
title: "TimeWarp"
category: "time"
summary: "Re-times a clip by choosing which input frame appears at each output frame."
aliases: ["TimeWarp node", "retime", "speed ramp", "slow motion"]
tags: ["retime", "time", "speed", "curve"]
requires: ["fundamentals/time-sampling"]
related: ["nodes/timeoffset", "nodes/kronos"]
nodes: ["TimeWarp"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# TimeWarp

## Purpose
Source-documented: slow down, speed up or reverse selected frames without necessarily altering overall length. See OFlow, Retime and Kronos for alternatives.

## Inputs
One unnamed sequence input.

## Controls
Documented knobs: input frame -> `lookup` (default 1); input length -> `length`; filter -> `filter` (default box); the docs describe a curve editor and a set to df/dt helper. Connecting TimeWarp automatically keyframes frame 1 as first frame. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Check the lookup curve in the Curve Editor, scrub for duplicate or skipped frames, and inspect motion smoothness. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: simple frame-lookup retiming does not synthesize in-between motion; fractional frames follow the filter. Use Kronos for motion-vector interpolation when appropriate.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/time_nodes/timewarp.html
