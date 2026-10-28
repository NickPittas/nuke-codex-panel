---
id: "topics/color-and-roto"
kind: "topic"
title: "Color correction and rotoscoping together"
category: "color-roto"
summary: "How rotoscoped mattes and color operators combine: choosing between mask input, Merge, and premultiplied isolation; keeping alpha, bbox, format and time correct across the pair."
aliases: ["color correct through roto", "grade with roto mask", "isolate element for correction", "roto before or after color", "garbage matte then grade"]
tags: ["roto", "mask", "grade", "color", "alpha", "premult", "workflow"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data", "fundamentals/color-spaces", "fundamentals/keying-conventions", "fundamentals/quality-safeguards"]
related: ["topics/color-management-correction", "topics/rotoscoping-masking", "topics/node-graphs", "nodes/channelmerge"]
nodes: ["Roto", "Grade", "ColorCorrect", "Merge", "Premult", "Unpremult"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions", "lesson-14"]
---
# Color correction and rotoscoping together

## Applicability
Use when a correction must affect only part of an image, or an element is isolated by hand-drawn shapes before grading. This covers how the two disciplines hand data to each other; shape craft is `topics/rotoscoping-masking` and colour pipeline/operators are `topics/color-management-correction`.

## Workflow
1. **Decide the relationship first.**
   - *Limit an operator* to a region: connect Roto to the operator's `mask` input (Grade, ColorCorrect, Blur and similar). The operator is applied at full strength through the matte, with the unmasked part unchanged. Brinkmann (Chapter 5, Masks) frames this as a matte used as a control image, equivalent to applying the effect everywhere and mixing back with the original.
   - *Isolate an element* for layering: put the matte into the element's alpha (Roto output defaults to alpha), premultiply, correct, and Merge over the background.
2. **Wire the mask.** Plug the Roto into the correction node's `mask` input, or point the node's mask control at a channel. The default is the mask input's alpha; choose another channel from the mask menu. `invert` flips it and also affects injected masks. `inject` copies the mask to `mask.a` so later nodes can reuse it. `fringe` applies the effect only at the mask edge; `mix` dissolves the correction.
3. **Keep the roto's context correct.** Connect the plate to the Roto's `bg` input so its format and bbox follow the plate. With no input it outputs `root.format`. Choose *clip to*: format restricts to the frame, bbox to the incoming bbox, union/intersection combine them. **Incoming alpha:** Roto's `replace` is disabled by default, so with the plate on `bg` the shapes are drawn into the incoming alpha rather than replacing it; if the plate's alpha is opaque the output alpha will not be an isolated shape matte. When the matte must contain only the new shapes, enable `replace` (existing channels are cleared to black before drawing) or leave `bg` unconnected and take the format from `root.format`. When the shapes are meant to combine with the existing alpha, leave `replace` off.
4. **Mind alpha state.** Roto's `premultiply` multiplies the chosen input channels by the shape matte; `rgba` multiplies alpha by itself, so use `rgb` unless that is intended. When grading an already premultiplied element, use the Grade/ColorCorrect (un)premult-by option with `rgba.alpha`, or Unpremult before and Premult after. Merge expects premultiplied inputs for most operations.
5. **Order operations deliberately.** Roto first, correction through mask: edits stay in the original plate. Correction first, roto after: the matte need not track grade changes but shapes see the corrected image. Garbage mattes (Brinkmann, Chapter 6, Matte Manipulations) are loose shapes that remove unwanted areas before a finer extraction. Studio policy (studio-conventions, project preference): cleanup before keying; roto inclusions/holdouts join a key's alpha via ChannelMerge (A = roto on a B-base chain; `from` holds out) and only the final alpha is Copied to the retained RGB. Keep roto keys to meaningful poses and occlusion changes and inspect interpolation (fundamentals/quality-safeguards). Put the final creative or integration grade after cleanup, key, roto and alpha fixes (lesson-14 guideline; a prep grade for a key or inspection is still fine) and verify black and white points with Pixel Analyzer min/max readings.

## Verify
- A key to alpha: view the matte; white is full effect, black none, grey partial. Check at several frames and edges.
- Toggle the correction node: only the masked region changes.
- Info bar: format and bbox at Roto and at the correction node should match the plate unless a crop is intended.
- Isolated-matte check: view the Roto output alpha with the plate connected; if it is not black outside the shapes, the incoming alpha is passing through (see `replace` above).
- Matte values stay within 0..1 (Brinkmann: superwhite masks give surprising results).

## Pitfalls
- If an unconnected external mask connector is missing, set the node's `mask` control to `none` to expose it; after connecting the mask, select its intended channel (Foundry, Selecting Masks).
- Masked correction on edge pixels of a premultiplied element tints the fringe if unpremultiplied handling is skipped.
- Roto animation that ends before the shot's frame range leaves later frames unmasked; check the shape lifetime.
- Roto `output` (default alpha) applies to all shapes; if you change it, select the same channel in the correction node's mask menu.

## Sources
- Foundry Nuke 17.1, Roto: https://learn.foundry.com/nuke/17.1/content/reference_guide/draw_nodes/roto.html
- Foundry Nuke 17.1, Calling Channels (Selecting Masks): https://learn.foundry.com/nuke/17.1v1/content/comp_environment/channels/calling_channels.html
- Foundry Nuke 17.1, Grade: https://learn.foundry.com/nuke/17.1/content/reference_guide/color_nodes/grade.html
- Foundry Nuke 17.1, Merge: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/merge.html
- Brinkmann 2e, Chapter 5 (Masks; Compositing with Premultiplied Images); Chapter 6 (Rotoscoping; Matte Manipulations).
- Studio policy: studio-conventions (project preferences, not universal Nuke facts).
- Lesson 14.srt (lesson-14; ASR, teaching-practice only): 00:24:01–00:24:55 grade after fixes, keying and alpha work, given as guidelines; 00:26:00–00:26:50 waveform and Pixel Analyzer readings.
