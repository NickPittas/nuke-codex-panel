---
id: "topics/color-management-correction"
kind: "topic"
title: "Nuke color management and color-correcting composites"
category: "color-roto"
summary: "Set up OCIO project color management, choose Read/Write transforms, then use Grade/ColorCorrect with sampled points and masks so elements match in the working space."
aliases: ["OCIO setup", "working space", "read colorspace", "ACES project nuke", "match foreground to background", "grade black point white point", "raw data read"]
tags: ["ocio", "colorspace", "grade", "colorcorrect", "working space", "matching", "aces"]
requires: ["fundamentals/color-spaces", "fundamentals/alpha-premultiplication", "fundamentals/channels-data"]
related: ["topics/color-and-roto", "topics/channels", "topics/chroma-keying"]
nodes: ["Read", "Write", "Grade", "ColorCorrect", "OCIOColorSpace", "Viewer"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-04"]
---
# Nuke color management and color-correcting composites

## Applicability
Use when starting a script, importing footage from different sources, or matching one element to another. Picking a transform is a data-interpretation decision; correcting is an image-editing decision. Decide the first before judging the second. Masked or isolated correction relationships are in `topics/color-and-roto`.

## Workflow
1. **Project settings.** Open Project Settings (press `S` in the Node Graph), Color tab. The *color management* dropdown selects OCIO or nuke-default. Any OCIO config except nuke-default switches to OCIO automatically. In OCIO mode Read and Write show the config's colorspaces, and the *working space* is the space Nuke uses internally, defaulting to the config's `scene_linear` role (ACEScg for the ACES configs). Choose a bundled config or a custom path. Preferences > Project Defaults > Color Management sets defaults for new projects.
2. **Read nodes.** Set the Read's colorspace to what the file actually contains, not to what looks right. The default is guessed from file type/header and may be wrong. The documentation states this control's label was updated but its scripting knob name remains `colorspace`. For non-colour data (normals, depth, position, mattes meant to stay numeric), enable *raw data* or choose a data/raw space so no transform is applied. The *premultiplied* option divides colour by alpha before the transform and multiplies after, which is needed for partially transparent renders.
3. **Write nodes** convert from working space to the delivery colorspace; verify the Write's colorspace and channels against the delivery spec rather than assuming the project default.
4. **Roles and looks.** Use OCIO roles (e.g. scene_linear, compositing_log, matte_paint) to reduce naming mistakes. In the ACES 1.3 configs shipped with 17.1, OCIOLookTransform applies the ACES 1.3 Reference Gamut Compression look for out-of-gamut values.
5. **Correct with the right tool.**
   - *Grade*: blackpoint/whitepoint define the source range; *lift* (knob `black`) and *gain* (`white`) map them to a target; also multiply, offset (`add`), gamma, clamps, `reverse`.
   - *ColorCorrect*: contrast, gamma, gain and offset with separate shadows, midtones and highlights ranges and saturation.
   - To match plates: sample the source's darkest/brightest points with Ctrl/Cmd+Alt+click (input) and the target's with Ctrl/Cmd+click (output) into blackpoint/whitepoint and lift/gain.
6. **Use mixes sparingly.** Mask, mix and (un)premult-by on the node let you limit or soften a correction. For corrections on premultiplied elements, set (un)premult by to `rgba.alpha` so the correction is applied as if before premultiplication.

## Verify
- Read nodes of different sources produce comparable neutrals/values when viewed through the same Viewer process; sample known grey/white patches.
- Data passes (depth, normals, positions) read with raw data or a data colorspace keep their numeric values; compare pixel values against the file's intended numbers.
- Viewer gain/gamma are display only; the clipping-warning stripes show pixels outside 0..1 but do not change values.
- Final judgement uses the same display transform on every shot.

## Pitfalls
- Changing the OCIO config updates default transforms; scripts relying on old colorspace names may need aliases (Nuke 14.1+ ACES configs add several).
- The `Video colorspace` option of Merge converts to the default 8-bit space before the composite; it changes blend results, so enable only deliberately.
- Grade's black clamp is on by default and its white clamp is off: confirm how negatives and super-whites are handled.
- Brinkmann (Chapter 3, Nonlinear Color Encoding; Chapter 4, Color Manipulations) explains why operator results differ between encodings; follow the Nuke documentation for the actual transforms.
- Course practice (lesson-04): Grade is the teacher's tool for matching black and white points between images; sample the target black and white and match them before look adjustments. Do not clamp blacks you need later. The lesson's keying-adjacent node choices follow the project's written conventions, not the older lesson.

## Sources
- Foundry Nuke 17.1, OCIO Color Management: https://learn.foundry.com/nuke/17.1/content/comp_environment/configuring_nuke/using_ocio_config_files.html
- Foundry Nuke 17.1, Read: https://learn.foundry.com/nuke/17.1/content/reference_guide/image_nodes/read.html
- Foundry Nuke 17.1, Grade: https://learn.foundry.com/nuke/17.1/content/reference_guide/color_nodes/grade.html
- Foundry Nuke 17.1, ColorCorrect: https://learn.foundry.com/nuke/17.1/content/reference_guide/color_nodes/colorcorrect.html
- Foundry Nuke 17.1, Using the Viewer Controls: https://learn.foundry.com/nuke/17.1/content/getting_started/using_interface/using_viewer_controls.html
- Brinkmann 2e, Chapter 3 (Nonlinear Color Encoding), Chapter 4 (Color Manipulations).
- Lesson 04 c.srt (lesson-04, ASR transcript, teaching-practice only): 00:07:23–00:09:35 Grade black/white point matching; 00:13:54–00:15:51 Clamp caution.
