---
id: "topics/motion-blur-depth-of-field"
kind: "topic"
title: "Motion blur and depth of field"
category: "cg-channels"
summary: "Add or match motion blur (VectorBlur, MotionBlur2D/3D, TimeBlur, transform shutter) and defocus (ZDefocus) with the depth and vector conventions checked first."
aliases: ["vectorblur", "zdefocus", "motion vectors", "depth map convention", "defocus", "dof", "shutter", "bokeh"]
tags: ["motion-blur", "dof", "depth", "vectors", "shutter"]
requires: ["fundamentals/channels-data", "fundamentals/time-sampling", "fundamentals/filtering-concatenation"]
related: ["topics/multipass-cg", "topics/channels", "topics/matchmove"]
nodes: ["ZDefocus", "VectorBlur", "MotionBlur2D", "MotionBlur3D", "TimeBlur", "Transform", "Tracker"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-14"]
---
# Motion blur and depth of field

## Applicability
Use to (a) defocus a layer from a depth channel, (b) add motion blur to a moved or CG element, (c) match blur already in the plate. Both depend on data channels whose convention you must establish before turning knobs.

## Workflow
**Depth of field (ZDefocus)**
1. The `image` input must carry the depth channel (default `depth.Z`, knob `z_channel`). The optional `filter` input is the aperture/bokeh shape.
   No depth channel (lesson-14, course render): the depth-driven ZDefocus pipeline cannot be assumed, so ask the CG team for a depth pass or choose another route, such as a mask-limited or hand-matched defocus, and label it manual. Missing depth rules out ZDefocus on that render; it does not mean depth is the only way to get defocus.
2. Set `math` to the depth convention of the source. Documented options: direct, depth (distance), far=0 (1/distance; Nuke and RenderMan), far=1 (OpenGL near 0, far 1), -direct, -depth, far=-0 (Maya-style -1/distance), far=-1. A wrong choice inverts or flattens the blur.
3. Switch `output` to focal plane setup: red is in front of the focus zone, green inside, blue behind. Set `focus plane` (or the Viewer focal point), `size`, `maximum`, `depth of field`; return to result.
4. Foundry says the depth map should not be antialiased (edge pixels get in-between depths). `fill foreground` can reconstruct revealed foreground edges but may invent content; toggle by the artefact seen.

**Motion blur**
- Render-time blur is correct when available; do not add 2D blur on top.
- VectorBlur needs u,v channels in `uv channels`. Pick the matching `mv presets` for the producing renderer; for vectors read from file use Read raw data and `uv offset` per docs (-0.5 or -127/255); unpremultiply vectors where possible or set the uv alpha. `motion amount` scales the vector; the docs give 0.5 for a standard shutter.
- No vectors: MotionBlur2D reads a Transform/Tracker through `2D transf`, MotionBlur3D reads a camera (optional Z channel), each emitting UVs for VectorBlur. Transform and Tracker also have their own `motionblur` and `shutter`.
- TimeBlur averages samples over the shutter and suits tracked garbage mattes (Foundry).
- Match plate shutter: 0.5 frame is a 180-degree shutter.

## Verify
- In focal plane setup, the in-focus region sits on the subject you expect; swap `math` and see which one makes near/far correct.
- Step two frames: blur streaks align with the on-screen direction of travel; if not, test `invert uv` or the preset. Note `invert uv` only shows when the shutter is off-centre.
- Edges: no halos where defocused foreground meets sharp background; no tearing holes (try `normalize`).
- Compare blur length against a moving object already in the plate.

## Pitfalls
- Filtering or blurring depth/vectors (Brinkmann: averaged depth moves surfaces to false positions); 8-bit depth bands.
- Z compositing and ZDefocus misbehave with transparency, antialiased edges and motion blur; live action has no true depth unless assigned.
- Post-process blur loses blown-out highlights that a real exposure keeps (Brinkmann); changing the direction of a plate's existing blur creates a visible mismatch.
- MotionBlur (Kronos-based) is NukeX/Studio; check licence.

## Sources
- ZDefocus: https://learn.foundry.com/nuke/17.1/content/reference_guide/filter_nodes/zdefocus.html
- VectorBlur: https://learn.foundry.com/nuke/17.1/content/reference_guide/filter_nodes/vectorblur.html
- MotionBlur2D: https://learn.foundry.com/nuke/17.1/content/reference_guide/filter_nodes/motionblur2d.html
- MotionBlur3D: https://learn.foundry.com/nuke/17.1/content/reference_guide/filter_nodes/motionblur3d.html
- TimeBlur: https://learn.foundry.com/nuke/17.1/content/reference_guide/time_nodes/timeblur.html
- Tracker (motion blur knobs): https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/tracker.html
- Brinkmann 2e: ch.14 "Z-Depth Compositing"; ch.4 "Motion Blur"; ch.13 "Motion Blur"; ch.2 "Focus and Depth of Field".
- Lesson 14.srt (lesson-14; ASR, teaching-practice only): 00:09:10–00:09:35 no depth channel on that render, so focus is handled another way; 00:10:12–00:10:40 extra layers requested from CG. Foundry 17.1 owns ZDefocus behaviour.
