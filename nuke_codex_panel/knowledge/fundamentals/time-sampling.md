---
id: "fundamentals/time-sampling"
kind: "fundamental"
title: "Time, frame ranges and temporal sampling"
category: "fundamentals"
summary: "Frame-number conventions, offsets versus retimes, whole versus fractional times, shutter and motion blur sampling, and how to check time-based results."
aliases: ["frame range", "retime", "time offset", "frame hold", "shutter", "motion blur samples", "fps", "fractional frames", "slip"]
tags: ["time", "retime", "offset", "shutter", "frames", "motion-blur"]
requires: []
related: ["fundamentals/filtering-concatenation", "topics/optical-flow-retiming", "topics/motion-blur-depth-of-field", "topics/keyframe-animation"]
nodes: ["TimeOffset", "Retime", "Kronos", "Roto", "Viewer"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-03"]
---
# Time, frame ranges and temporal sampling

## Applicability
Use for retiming, syncing plates, holding frames, setting ranges, sampling past or future frames (clone sources, motion blur), or judging motion quality. Distinguish three things: which frame is evaluated, what range the script and Viewer play, and how time is sampled between frames.

## Workflow
1. Read the ranges: the script (Project Settings) range, each Read's own first and last frame, and the Viewer's frame_range (which can be locked). They are independent; do not assume one from another.
2. Offset or retime? TimeOffset moves a clip earlier or later without changing speed; positive time_offset adds frames at the head, negative subtracts. Its mode (rounding_mode) is whole frames (times rounded down) or fractional time (exact times, possibly between frames). Retime changes speed and works by dropping or duplicating frames; raising its shutter enables frame blending. OFlow or Kronos (NukeX licence) interpolate instead of copying.
3. After an offset, set the script range to the new output range; otherwise Nuke holds the first or last frame to fill empty frames.
4. For per-frame sampling controls state which frame convention applies. Roto's clone time offset is relative (-1 is the previous frame) or absolute (1 is the clip's first frame). Roto motion blur shutter offset is centred, start, end or custom, with shutter measured in frames (0.5 is half a frame).
5. Match shutter and offset to the plate's motion blur. Viewer shutter angle (default 180) is for exposure display and is not a substitute for node motion blur settings.

## Verify
- Step frame by frame through the head, middle and tail, noting source frame numbers at each (a frame-number overlay or sampled marker works).
- Look for duplicated frames (stutter), held tail frames, or double-speed jumps after a retime.
- Compare moving edges against the plate to see whether motion blur direction and amount match.

## Pitfalls
- Frame-number base differs by source: file frame numbers, script frames and zero- or one-based tool conventions do not necessarily agree; check with a known frame.
- Whole-frame mode rounds down, so fractional-looking offsets silently snap.
- Frame-blended and interpolated retimes change image content, so they affect grain, edges and keying differently from simple frame duplication.
- Interlaced material has two fields per frame; Brinkmann covers field handling separately before any retime.
- Time operations sit upstream of everything they feed; adding one late can desync tracking data and shapes keyed to the old timing.
- Frame rate (lesson-03 teaching example): a clip shot at high fps for slow motion is meant to play at the delivery rate, so check the Read/project fps against the delivery fps before retiming or syncing; a mismatch changes speed, not just metadata.

## Sources
- TimeOffset: https://learn.foundry.com/nuke/17.1/content/reference_guide/time_nodes/timeoffset.html
- Simple Retiming: https://learn.foundry.com/nuke/17.1/content/comp_environment/temporal_operations/simple_retiming.html
- Roto (clone time offset, motion blur): https://learn.foundry.com/nuke/17.1/content/reference_guide/draw_nodes/roto.html
- Viewer: https://learn.foundry.com/nuke/content/reference_guide/image_nodes/viewer.html
- Brinkmann 2e, section "Time and Temporal Manipulations" (theory).
- Lesson 03 Final.srt (lesson-03, ASR transcript, teaching-practice only): 00:30:02–00:34:48 fps standards and slow motion by recording high fps.
