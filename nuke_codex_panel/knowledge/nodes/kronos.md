---
id: "nodes/kronos"
kind: "node"
title: "Kronos"
category: "time"
summary: "Motion-vector retimer for slowing down or speeding up footage; NukeX and Nuke Studio only per the docs."
aliases: ["Kronos node", "optical flow retime", "slow motion retime", "oflow"]
tags: ["retime", "optical flow", "motion vectors", "slow motion"]
requires: ["fundamentals/time-sampling", "fundamentals/channels-data"]
related: ["nodes/timewarp", "nodes/vectorblur"]
nodes: ["Kronos"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Kronos

## Purpose
Source-documented: estimates motion, then interpolates along motion direction to generate any output time; includes render-time versus accuracy controls. Availability depends on licence and edition.

## Inputs
FgVecs and BgVecs (optional precomputed vector sequences, for example from VectorGenerator; BgVecs appears as an arrowhead), MoSrc (alternate motion source), Matte (optional foreground matte), and Source (the sequence to retime). Connecting Matte alone does nothing: the Matte Channel control (`matteChannel`, default None) must also select a source, otherwise the matte is ignored.

## Controls
Documented knobs: gpuName; useGPUIfAvailable (default enabled); input.first and input.last; resetInputRange; retimedChannels (default all); interpolation (default Motion); timing2 (default Output Speed); matteChannel (default None = no matte; options Source Alpha, Source Inverted Alpha, Matte Luminance, Matte Inverted Luminance, Matte Alpha, Matte Inverted Alpha; the matte marks the foreground for motion estimation); output (default Result; Matte/Foreground/Background views are only useful when a Matte Channel is used). Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Compare against TimeWarp/Frame interpolation, look for warped edges around fast occlusions, and test with and without a matte. When using a matte, choose the Matte Channel option matching where the foreground mask lives (Matte Alpha/Luminance from the Matte input, or Source Alpha) and check polarity: use the Inverted variant if the foreground is black; confirm with output set to Matte or Foreground. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: motion interpolation can smear or tear on occlusion; a foreground matte or alternate source may help per the docs, but only when Matte Channel is not None. Wrong polarity gives a wrong foreground/background split. Do not claim availability without checking the licence.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/time_nodes/kronos.html
