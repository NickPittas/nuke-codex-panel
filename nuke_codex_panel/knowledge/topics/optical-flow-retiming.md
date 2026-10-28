---
id: "topics/optical-flow-retiming"
kind: "topic"
title: "Retiming clips with optical flow"
category: "tracking-warping-retiming"
summary: "Retime with Retime, FrameBlend, OFlow or Kronos: pick the interpolation method, time mapping and vector inputs, and know where optical flow fails at occlusions, thin detail, transparency and missing motion blur."
aliases: ["kronos", "oflow", "slow motion", "speed ramp", "frame interpolation", "motion interpolation", "timewarp", "retime"]
tags: ["retime", "optical-flow", "kronos", "oflow", "motion-vectors", "slow-motion"]
requires: ["fundamentals/time-sampling", "fundamentals/channels-data", "fundamentals/filtering-concatenation"]
related: ["topics/motion-blur-depth-of-field", "topics/spline-grid-warp", "topics/keyframe-animation"]
nodes: ["Kronos", "OFlow", "Retime", "FrameBlend", "VectorGenerator", "TimeBlur"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-07"]
---
# Retiming clips with optical flow

## Applicability
Use when speed changes need new in-between frames. Simple duplicating or dropping frames (Retime) is cheap but jumpy; blending hides jumps with ghosting; optical flow estimates per-pixel motion and interpolates along it. Flow output is an estimate, not recovered reality. Kronos is NukeX/Nuke Studio only; Foundry recommends it over OFlow for its improved motion estimation. Check installed generation and licence.

## Workflow
1. Decide the time mapping:
- Constant: Kronos or OFlow `Timing` = Output Speed or Input Speed (values below 1 slow down; the default 0.5 is half speed).
- Variable: Input Speed keyframes are set against source frames and are easier to place but cannot be negative; Output Speed keyframes can be negative but moving one shifts all later frames.
- Mapping: `Frame` timing says "at output frame 100 show source frame 50"; set at least two keys.
- Retime node: speed, reverse, ranges, and a TimeWarp curve (slope down = slower, slope up = faster, dip = reverse); `shutter` or FrameBlend adds blending.
2. Preview with Method `Blend` while tuning curves; set `Motion` for the final. `Input Range` follows the Source at creation; press Reset when the source changes.
3. Supply good motion data. Kronos accepts FgVecs/BgVecs (for example from VectorGenerator), a cleaner `MoSrc` when the source is noisy, and a foreground matte. The `Matte` input is ignored while `Matte Channel` is None (default): set Source Alpha, Source Inverted Alpha, or Matte Alpha/Luminance (or their inverted forms) and check polarity by viewing `output` = Foreground/Background. OFlow cannot output vectors and has no such inputs.
4. Tune: Motion method Regularized (default for new nodes; older scripts default to Local), `Vector Detail` (1 = a vector per pixel; high values can pick up unwanted local motion), `Strength` or `Smoothness` (accuracy vs smoothness), Flicker Compensation for brightness changes (slower), resampling filter. `Overlay Vectors` shows red forward and blue backward vectors but is rendered into the output unless turned off.
5. Kronos only interpolates between existing frames; output length is (intervals / speed) + 1. At half speed it creates frames at 0.25 and 0.75 to avoid pulsing from reusing originals.
6. Blur: slow motion cannot invent real exposure; use `Shutter Time`/`Shutter Samples` (shutter 0.5 equals a 180-degree shutter) or topics/motion-blur-depth-of-field.

## Verify
- Compare Blend and Motion at fractional positions (for example frames 0.25 and 0.75) and at fast, overlapping action.
- Step frame by frame through every occlusion edge, thin object, fence/foliage pattern and transparent surface at 100% zoom.
- Confirm first/last frames, output length and that no overlay vectors are in the render.
- Play at speed; temporal artifacts hide in stills (Brinkmann).
- Wipe the retimed output against the source at several in-between positions for blurred or dissolving frames; if you paint or roto after the retime, those fixes belong on the retimed frames (course practice, lesson-07).

## Pitfalls
- Occlusion and disocclusion: flow cannot know what lay behind a mover (Brinkmann); expect smearing, doubled edges, or pixel dragging at foreground/background boundaries. Mitigate with a foreground matte (Kronos `Matte Channel` set, correct polarity), cleaner MoSrc, a different method, or paint/roto fixes.
- Repetitive texture, large displacement, motion blur in the source, flicker, grain, specular/water reflections, and transparency confuse estimation.
- Retiming across cuts or after temporal blur effects. Retiming a final composite bakes in each layer's flow errors; retiming layers separately can break edges. Test at the problem frames before choosing.
- Frame blending adds ghosts; Retime without blending repeats frames and strobes (Brinkmann).
- Optical flow creates frames that were never shot, and can leave blurs or dissolve-like transitions between source frames; decide whether the shot tolerates that before building work downstream, and correct it after the retime if it does not (lesson-07). The teacher's frame numbers are unreliable in the ASR and are not used here.

## Sources
- Kronos reference: https://learn.foundry.com/nuke/17.1/content/reference_guide/time_nodes/kronos.html
- Kronos guide: https://learn.foundry.com/nuke/17.1/content/comp_environment/kronos_motionblur/kronos.html ; Retiming a Sequence: https://learn.foundry.com/nuke/17.1/content/comp_environment/kronos_motionblur/retiming_sequence.html ; Refining the Results: https://learn.foundry.com/nuke/17.1/content/comp_environment/kronos_motionblur/refining_results.html
- OFlow Retiming: https://learn.foundry.com/nuke/17.1/content/comp_environment/temporal_operations/oflow_retiming.html ; OFlow reference: https://learn.foundry.com/nuke/17.1/content/reference_guide/time_nodes/oflow.html
- Simple Retiming: https://learn.foundry.com/nuke/17.1/content/comp_environment/temporal_operations/simple_retiming.html ; Interpolation: https://learn.foundry.com/nuke/17.1/content/comp_environment/temporal_operations/interpolation.html ; Warping Clips: https://learn.foundry.com/nuke/17.1/content/comp_environment/temporal_operations/warping_clips.html
- Brinkmann 2e ch.7 "Temporal Artifacts", "Changing the Length or Timing of a Sequence".
- Lesson 07.srt (lesson-07; ASR, teaching-practice only): 00:08:55–00:09:30 optical flow invents frames, blur/dissolve between frames.
