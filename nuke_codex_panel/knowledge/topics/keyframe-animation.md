---
id: "topics/keyframe-animation"
kind: "topic"
title: "Keyframe animation: values, interpolation and timing"
category: "animation"
summary: "How to decide where keys go, which interpolation to use, how curves behave between and beyond keys, and how time nodes and sampling affect animated values."
aliases: ["interpolation", "smooth vs linear keys", "curve overshoot", "ease in out", "animate brightness over time", "extrapolation", "animation curve shape"]
tags: ["animation", "curves", "interpolation", "keys", "timing", "motion"]
requires: ["fundamentals/time-sampling", "fundamentals/coordinates"]
related: ["topics/interface-keyframes", "topics/rotoscoping-masking", "topics/optical-flow-retiming"]
nodes: ["Roto", "TimeOffset", "Transform"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-11"]
---
# Keyframe animation: values, interpolation and timing

## Applicability
Use when the question is *what* the animation should be: key placement, curve shape, whether values stay in range, and how time operators change what is seen. Pressing buttons to create, move or delete keys is `topics/interface-keyframes`. An animated knob is a function of frame number: keys are samples, interpolation fills the frames between.

## Workflow
1. **Start with the fewest keys that state the intent.** Brinkmann's example (Chapter 7, Keyframing) keys an element's brightness at the first and last frames; linear interpolation puts the midpoint exactly halfway, and checking a mid-frame shows the intent is not linear (the subject enters the lit room late). Add keys where the *behaviour* changes, then inspect between keys.
2. **Subdivide from the largest error.** The same logic appears in Brinkmann's rotoscoping chapter (Chapter 6): inspect the frame halfway between two keys, correct it, repeat. Use coarse intervals first for organic motion, then halve.
3. **Pick interpolation per purpose** (Curve Editor right-click > Interpolation, per Foundry 17.1):
   - *Constant*: holds the value after each key (switches, on/off).
   - *Linear*: straight segments, sharp changes at keys.
   - *Smooth*: tangents follow neighbours but become horizontal at extremes, so the curve does not exceed key values. Good for knobs with a valid range such as mix or opacity.
   - *Catmull-Rom*: documented to possibly exceed key values; avoid on bounded knobs unless checked.
   - *Cubic*: continuous second derivative for smooth motion; inspect for overshoot.
   - *Horizontal*/*Break*: ease at a key, or edit each side's tangent independently for a hit or stop.
   Use *Before*/*After* (constant or linear) on the first/last key for behaviour outside the keyed range.
4. **Edit the curve, not only the keys.** Tangent handles shape acceleration; Filter smooths noisy curves; Loop repeats a segment; Reverse and Negate derive a curve; an expression can modify a curve (Curve Editor expression field). These are legitimate when a derived relationship matters, but a hand-keyed curve is easier for others to adjust.
   Tracker jitter (course practice, lesson-11): when a tracked curve has isolated spikes or jumps, select only the keys around the problem on both X and Y, filter, and compare; repeat on that span if needed. Sometimes a spike is real motion or detail the track must keep, so do not smooth a whole curve by default. If a key is clearly wrong, move it into line with its neighbours first and then filter. Check the filtered track against the plate before accepting it.
5. **Respect time.** Key times are in script frames at the animated node. Frame Snap rounds dragged keys to integer frames; sub-frame keys are possible when snap is off, which matters for retimes. Time nodes downstream change when an animated value is seen, so verify the animation at the Viewer input that matters.

## Verify
- Open the Curve Editor with the knob's curve selected; confirm no overshoot beyond intended limits (mix outside 0..1, negative sizes).
- Step through key frames and the frames halfway between each key pair.
- Check frames before the first and after the last key, which use the extrapolation setting.
- For motion, view the whole range at playback speed once: jitter or pops often hide at the frame that looks correct when stopped.

## Pitfalls
- Default interpolation is not a creative choice; re-check it after dragging keys.
- Interpolation acts on the knob value, not on perceived brightness, so equal steps in the knob are not equal steps on screen; judge the result visually at several frames.
- Animating brightness of an element to fake lighting change is common but not ideal, as Brinkmann says in the same example; prefer matching the source light if a choice exists.
- Keys driven by a Tracker link or expression are not hand-editable keys.
- Baking a key on every frame (Curve Editor *Generate*) removes procedural interpolation; later edits become point-by-point and cause jitter (lesson-11). Keep a copy of the unbaked curve or the tracker data when you may revise it. Key spacing sets speed, so retime by moving or scaling keys, not by adding more.

## Sources
- Foundry Nuke 17.1, Animating Parameters (Curve Editor, interpolation types, Before/After, Loop, Reverse, Negate, Frame Snap): https://learn.foundry.com/nuke/17.1/content/getting_started/using_interface/animating_parameters.html
- Foundry Nuke 17.1, Animating Strokes/Shapes: https://learn.foundry.com/nuke/17.1/content/comp_environment/rotopaint/animating_strokes_shapes.html
- Brinkmann 2e, Chapter 7 Time and Temporal Manipulations (Keyframing); Chapter 9 Interface Interactions (Curve Editors); Chapter 6 Matte Creation (Rotoscoping).
- Lesson 11.srt (lesson-11; ASR, teaching-practice only): 00:07:45–00:09:52 key spacing sets speed; 00:22:43–00:24:03 Generate bakes keys; 00:24:13–00:24:55 and 00:27:38–00:31:10 filter spikes on selected keys, with 00:30:15–00:30:23 saying small errors may be detail to keep. Interpolation behaviour is defined by Foundry 17.1.
