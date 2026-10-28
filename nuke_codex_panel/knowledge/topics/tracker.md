---
id: "topics/tracker"
kind: "topic"
title: "The Tracker node"
category: "tracking-warping-retiming"
summary: "Place, calculate and judge 2D tracks with Nuke's Tracker: feature choice, pattern/search areas, auto vs keyframe tracking, direction, reference frame, and stabilize vs match-move output."
aliases: ["2d tracker", "track anchors", "pattern and search area", "stabilize", "reference frame", "track_x", "track_y", "auto track", "keyframe track"]
tags: ["tracking", "tracker", "stabilize", "matchmove", "reference-frame"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling", "fundamentals/filtering-concatenation"]
related: ["topics/matchmove", "topics/planar-tracking", "topics/camera-tracking", "topics/spline-grid-warp"]
nodes: ["Tracker", "CornerPin2D", "Transform", "Stabilize2D"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-05"]
---
# The Tracker node

## Applicability
Use for 2D point/pattern tracks that give translation, rotation, scale (and with four points a corner pin) in the image plane. Parallax from a moving 3D camera needs topics/camera-tracking; a flat moving surface may be better with topics/planar-tracking.

## Workflow
1. Connect Tracker to the clip to track. Play it several times: find occlusions, blur, out-of-frame moves and lighting shifts. Boost feature contrast in a branch if needed (blur or a clean channel against grain); disable that branch afterwards (Foundry, Brinkmann).
2. Choose features that stay visible, keep their shape, and move with the target surface: choose the target's own attachment point or something rigidly next to it. Prefer patterns distinctive along every axis; a straight edge slides along itself (Brinkmann). Features at different depths give different motion.
3. Add anchors. Each has a pattern (the pixels compared across frames) and a search area (where it may reappear next frame); large search areas cost time. Use more anchors in noisy or distorted areas and average.
4. Per track, set which of T, R, S it outputs. This differs from Settings `warp type` (translate, translate/rotate, translate/scale, translate/rotate/scale, affine), which defines pattern recognition; translation-only matching loses patterns that rotate or scale.
5. Calculate. The `transform` control must be `none` while tracking. Step a few frames first to confirm anchors stick; auto-track grabs the reference pattern on the first frame by default. Track backward when the feature is clearer late in the clip. Settings include `max iterations`, `epsilon`, `max_error`, `predict track`, and pattern-grab mode (first frame, every frame, every n frames, error thresholds). After a failed predicted track use Clear Forward before retracking.
6. Difficult or changing patterns: keyframe tracking compares against the two nearest keyframes. For occlusion, Ctrl/Cmd-drag the anchor to an offset feature that stays at constant distance; the offset is recorded.
7. Apply: `transform` = stabilize or stabilize 1pt (inverse: tracked points stay fixed), match-move or match-move 1pt (the image follows the tracked motion), remove or add jitter. `reference frame` is the identity frame; set it to the frame where the result should be unmoved.

## Verify
- Step and scrub with overlays on: the anchor stays on the same detail, at sub-pixel level when zoomed.
- Inspect track_x/track_y curves for jumps (Brinkmann); several nearby tracks should agree.
- Apply stabilize and flip between reference frame and distant frames: the feature must not move. Check the final result, not only the graph.
- track_x/track_y are anchor-centre coordinates in the tracked image's pixels (Foundry). If you apply them to an element in a different format, or after a Reformat/proxy change, confirm the alignment explicitly (see fundamentals/coordinates).

## Pitfalls
- Leaving `transform` active during tracking; forgetting to deselect finished tracks before retracking others.
- One point cannot carry rotation or scale; four points on a plane can feed a corner pin.
- Tracking motion-blurred, occluded or lighting-changed frames without offsets or manual keys.
- Filtering twice (stabilize then match-move) softens the image; choose `filter` and `clamp` consciously; `black outside` also adds a solid alpha if the input has none.
- Course practice (lesson-05 example): if brightness changes inside the pattern make the tracker slip, enable luminance compensation (verify the knob in 17.1); use the show-error overlay and fix red-flagged frames with corrective keys, then re-check overlays.

## Sources
- Tracking and Stabilizing: https://learn.foundry.com/nuke/17.1/content/comp_environment/tracking_stabilizing/tracking_stabilizing.html
- Adding Track Anchors: https://learn.foundry.com/nuke/17.1/content/comp_environment/tracking_stabilizing/adding_track_anchors.html
- Automatic Tracking: https://learn.foundry.com/nuke/17.1/content/comp_environment/tracking_stabilizing/automatic_tracking.html
- Keyframe Tracking: https://learn.foundry.com/nuke/17.1/content/comp_environment/tracking_stabilizing/keyframe_tracking.html
- Tracker reference: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/tracker.html
- Brinkmann 2e ch.8 "Tracking an Element into a Plate", "Human Intervention", "Using Tracking Curves Manually".
- Lesson 05.srt (lesson-05, ASR transcript, teaching-practice only): 00:01:50–00:03:42 luminance changes and show-error markers; 00:03:42–00:07:01 corrective keyframes.
