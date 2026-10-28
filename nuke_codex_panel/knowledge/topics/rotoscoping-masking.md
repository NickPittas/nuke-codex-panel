---
id: "topics/rotoscoping-masking"
kind: "topic"
title: "Rotoscoping and masking operations"
category: "color-roto"
summary: "Draw, animate and output roto shapes with the Roto node, then apply them as mattes or mask inputs; covers output channel, premultiply, clip-to, inject/invert, lifetime and motion blur."
aliases: ["roto", "rotoscope", "bezier shape", "garbage matte", "circle mask", "mask input", "feather roto", "roto vs rotopaint"]
tags: ["roto", "mask", "matte", "bezier", "feather", "alpha", "keyframes"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data", "fundamentals/coordinates", "fundamentals/quality-safeguards"]
related: ["topics/color-and-roto", "topics/interface-keyframes", "topics/keyframe-animation", "topics/planar-tracking"]
nodes: ["Roto", "RotoPaint", "Merge", "Grade", "Tracker"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions", "lesson-06", "lesson-07"]
---
# Rotoscoping and masking operations

## Applicability
Use to create hand-drawn mattes: element extraction, garbage mattes, regional masks and protecting areas from an operation. Prefer the native Roto node for shapes (circles, rectangles, Beziers, B-splines) rather than synthetic expression mattes, which lack editable, animatable shapes. Use RotoPaint when painting, cloning or rig removal is also required; Roto is the focused choice for shapes only. Hotkeys are 17.1 documentation defaults and may be rebound.

## Workflow
1. **Create and connect.** `O` in the Node Graph creates Roto. Connect the plate to `bg` so format and bbox come from the plate; with no input it uses `root.format`. The `mask` input is a separate, optional limiting image.
2. **Draw by part.** Brinkmann (Chapter 6) advises separate shapes for independently moving parts (e.g. arm and body) instead of one complex outline, and loose overlaps are fine where another shape already covers. In Nuke, click to place points (drag to pull Bezier handles), Return closes, Esc leaves open, Z smooths a point, Shift+Z cusps, Delete removes, Ctrl/Cmd+Alt+click adds a point, E / Shift+E adds or removes point feather.
3. **Key by intervals.** Cue a frame, move the shape or points; autokey creates keys. Work coarse (every 10-20 frames for organic motion), then check midpoints and halve, as in Brinkmann's interval method. For rigid plate motion, link the shape's translate/transform to a Tracker or use the Tracking tab.
4. **Set output and edge behaviour.** `output` defaults to `alpha` for all shapes in the node. `replace` clears the target channels first, which discards an incoming alpha. `premultiply` multiplies chosen input channels by the matte; `rgba` includes alpha squared, so `rgb` is usually intended. `clip to` defaults to `format`; use `bbox`, `union` or `intersect` as needed. Feather softens edges (positive outward, negative inward), with feather type controlling falloff shape. Shape `opacity`, `visible`, `locked`, `lifetime` and blend mode apply per shape.
5. **Use the matte.**
   - As alpha: Merge the premultiplied element over a background.
   - As a mask: connect Roto to another node's `mask` input, or pick a channel in its mask menu. Default behaviour limits the effect to non-black areas; `invert` limits to non-white; `inject` copies to `mask.a` for later reuse; `fringe` limits to the edge; `mix` dissolves.
6. **Motion blur** is enabled per shape (*shape*) or for all shapes (*global*); set samples, shutter and shutter offset to match the plate.

## Verify
- Press A over the Viewer to inspect alpha, M for red overlay, then step the full range at fine and coarse intervals.
- Check shape lifetime covers every frame it should and nothing outside.
- Matte edges against the plate at zoom; look for chatter between keys (a curve overshoot in the Curve Editor is the usual cause).
- Confirm the matte is within 0..1 and format/bbox match the downstream node.

## Pitfalls
- Disconnect or toggle the mask while editing; a matte can hide the detail you are tracing.
- If an unconnected external mask connector is missing, set the `mask` control to `none` to expose it; after connecting the mask, select its intended channel.
- `replace` is disabled by default: with a plate on `bg`, shapes draw into the plate's existing alpha. Enable it only when the matte should contain just the new shapes; leave it off when deliberately combining with an incoming alpha.
- Changing the output channel changes it for all shapes in the Roto.
- Interpolating point positions between distant keys shrinks a rotating shape (Brinkmann, Chapter 6); add keys at the turning frames.
- Expression-generated placeholders are acceptable only when geometry is truly procedural; they are not roto.
- Keys on every frame can create jitter and a heavy curve. Studio preference: place keys at meaningful poses and occlusion changes, inspect interpolation in the Curve Editor, and add keys only where the shape needs them; per-frame keys are justified for genuinely rapid change. Deliberate placement is the rule, not a numeric ban (`fundamentals/quality-safeguards`).
- Set the project/root format before drawing; a wrong or unset format yields wrong roto extents, and a `bg` plate sets them as above.
- Matte assemblies keep the B-base/A-incoming structure; combining roto mattes into a key is covered in `topics/combine-keys`.
- Course practice (lessons 06-07): a rough first roto is enough to decide what is needed; then be precise where downstream depends on the edge, such as a foreground part kept in front. Where a keyer's edge fails, an animated inclusion roto can hold a solid core; union it into the alpha branch.

## Sources
- Foundry Nuke 17.1, Roto: https://learn.foundry.com/nuke/17.1/content/reference_guide/draw_nodes/roto.html
- Foundry Nuke 17.1, Animating Strokes/Shapes: https://learn.foundry.com/nuke/17.1/content/comp_environment/rotopaint/animating_strokes_shapes.html
- Foundry Nuke 17.1, Calling Channels (Selecting Masks): https://learn.foundry.com/nuke/17.1v1/content/comp_environment/channels/calling_channels.html
- Brinkmann 2e, Chapter 6 Matte Creation and Manipulation (Rotoscoping; Garbage Mattes); Chapter 5 (Masks).
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): keyframe placement, root format check, matte-assembly layout.
- Lesson 06.srt (lesson-06; ASR) 00:45:04–00:49:06; Lesson 07.srt (lesson-07) 00:13:00–00:13:26, 00:36:20–00:36:40.
