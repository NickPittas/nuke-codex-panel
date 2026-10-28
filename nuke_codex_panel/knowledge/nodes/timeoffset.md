---
id: "nodes/timeoffset"
kind: "node"
title: "TimeOffset"
category: "time"
summary: "Shifts a clip forward or backward in time; may also reverse input."
aliases: ["TimeOffset node", "offset clip", "slip frames", "reverse"]
tags: ["time", "offset", "retime"]
requires: ["fundamentals/time-sampling"]
related: ["nodes/timewarp", "nodes/read"]
nodes: ["TimeOffset"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# TimeOffset

## Purpose
Source-documented: offset a clip backward or forward in time, such as to synchronize events. After offsetting adjust project frame range or Nuke holds first or last frame in empty frames.

## Inputs
One unnamed image sequence input.

## Controls
Documented knobs: Mode -> `rounding_mode` (default Whole frames); Time Offset (frames) -> `time_offset` (default 0); Reverse Input -> `reverse_input` (default off). The same page also lists geo path-mask controls, so some knobs target geometry workflows. Script class aliases in frontmatter are common names, not guaranteed UI names; verify with node.Class().

## Verify
Scrub at the head and tail, compare to the original frame numbers, and check project range. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
Conditional practice: sign convention should be tested on a numbered clip. Offset does not change the Read node's stored file range.

## Sources
- Foundry Nuke documentation: https://learn.foundry.com/nuke/17.1/content/reference_guide/time_nodes/timeoffset.html
