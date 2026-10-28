---
id: "nodes/keyer"
kind: "node"
title: "Keyer"
category: "keying"
summary: "Simple luminance, channel, screen, saturation or min/max keyer with a range graph."
aliases: ["Keyer node", "luminance key", "luma key", "range key"]
tags: ["key", "luma", "range", "matte"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data"]
related: ["nodes/keylight", "topics/luma-keying"]
nodes: ["Keyer"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# Keyer

## Purpose
Source-documented: access to simple keyers based on red, green or blue channels, red/green/bluescreen, luminance (default), saturation, or maximum and minimum values. View alpha and use the range graph A/B handles for low and high values, with C/D for shifting the center for high values.

## Inputs
One unnamed image input.

## Controls
Documented knobs: input (default rgb); output channel (default rgba.alpha); combine (default replace); invert; operation (default luminance key); range with A and B handles. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
View alpha, scrub tonal extremes, compare against a grade-based matte and inspect edge falloff. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: simple keys can pick up unwanted areas of similar value; clamp and combine with masks. The docs only describe the keyer ranges; do not assume a screen-key quality equal to Keylight.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/keyer.html
