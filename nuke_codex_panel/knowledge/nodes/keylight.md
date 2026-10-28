---
id: "nodes/keylight"
kind: "node"
title: "Keylight"
category: "keying"
summary: "Colour-difference keyer for blue or green screen with screen colour, matte, despill and optional garbage and holdout masks."
aliases: ["Keylight node", "green screen key", "blue screen key", "color difference keyer"]
tags: ["key", "chroma", "despill", "matte"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/color-spaces"]
related: ["nodes/primatte", "nodes/keyer", "nodes/ibkgizmo", "topics/combine-keys", "nodes/channelmerge", "nodes/copy"]
nodes: ["Keylight"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# Keylight

## Purpose
Source-documented: an industry-proven colour-difference keyer. Choose a screen colour from Source, judge with View, use Despill Bias for skin tones and the Screen Matte parameters to improve the matte.

## Inputs
bg (optional background), OutM (outside mask or garbage matte), InM (inside mask or holdout matte), Source (foreground to key).

## Controls
Documented knobs: View -> `show` (default Final Result); Unpremultiply Result -> `unPreMultiply` (default enabled); Screen Color -> `screenColor`; Screen Gain -> `screenGain` (default 1); Screen Balance -> `screenBalance` (default 0.5); Alpha Bias -> `alphaBias`; Despill Bias. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View alpha, source and final result, inspect edges against both a bright and dark background, and review spill. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: results depend on a good screen colour pick and plate quality. Check premultiplication of the result before merging. Keylight, Primatte and IBK have different workflows. Studio policy (studio-conventions; project preference, not a Foundry rule): use Keylight as an alpha extractor on the same original or cleaned RGB as other regional keyers, merge alphas with nodes/channelmerge, Copy the final alpha onto the retained RGB, then despill, edge treatment and premultiplication; do not pass its processed RGBA as the default final foreground, and do not assume one keyer covers every region (fundamentals/keying-conventions).

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/keylight.html
- Studio policy: studio-conventions (teacher-supplied production conventions; project preferences, not universal Nuke facts).
