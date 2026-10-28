---
id: "topics/multipass-cg"
kind: "topic"
title: "Multi-pass CG compositing"
category: "cg-channels"
summary: "Rebuild and adjust a CG render from its passes: classify passes per renderer, test the rebuild against the beauty, grade at pass level, and keep data passes out of colour operations."
aliases: ["render passes", "aovs", "beauty rebuild", "light passes", "diffuse specular reflection passes", "exr layers"]
tags: ["cg", "passes", "aov", "exr", "beauty", "plus"]
requires: ["fundamentals/channels-data", "fundamentals/alpha-premultiplication", "fundamentals/color-spaces"]
related: ["topics/channels", "topics/motion-blur-depth-of-field", "topics/cg-backgrounds"]
nodes: ["Shuffle", "Merge", "Grade", "Unpremult", "Premult", "Remove"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-14"]
---
# Multi-pass CG compositing

## Applicability
Use when a render arrives as several passes or EXR layers. Pass naming, which passes sum to the beauty, which are multiplied, and whether each pass carries its own alpha are renderer- and setup-dependent. The rebuild is therefore a hypothesis to test, never a recipe: do not add every layer in the file.

## Workflow
1. List layers (see topics/channels). Sort into: component passes (direct/indirect light, diffuse, specular, reflection, refraction, emission, per-light), utility passes (AO, shadow, masks, IDs), and data passes (depth, normals, position, vectors, uv).
2. Get the renderer's pass documentation or the artist's note on which components sum to beauty. If none exists, infer from names, then prove it in step 4.
3. Shuffle each candidate component into rgb on its own branch (data passes stay out). Read the premultiplied state: Foundry's rule of thumb is that most 3D renders are premultiplied and a black or very dark background suggests it; the Read `premultiplied` option corrects colour at partially transparent pixels during colourspace conversion.
4. Combine candidates with Merge `plus` (A+B). Compare to the rendered rgba with Merge `difference` (abs(A-B)) and amplify the result. A residual shows a missing, double-counted or non-additive pass. Treat plus as correct only for passes the renderer defines as additive; AO and filter/albedo-style passes are normally multiplied or applied separately, so test rather than assume. Course example (lesson-14, renderer-specific): a render's reflection, refraction and specular layers summed with plus matched the beauty on a wipe, and plus order did not matter. After plus or any Shuffle, restore the alpha: plus also adds each pass's alpha, which corrupts soft edges, and a Shuffle that drops alpha leaves the result without one. Copy back the original beauty alpha, or the alpha delivery needs.
5. Grade at the pass level. For a premultiplied pass, Foundry's pattern is Unpremult, correct, Premult. A pure gain commutes with premultiplication; offset, gamma and contrast do not. A pass sharing the main alpha may need no un/premult for gain only; verify at soft edges. Pass-level edits (reflections bluer, speculars bloomed) come first; the overall creative or integration grade goes after technical fixes, keying and alpha work. Lesson-14 gives this as a guideline, not a ban on a prep grade for a key or an exposure check.
6. Use utility mattes as masks (mask channel or Keymix) and keep data passes for ZDefocus, VectorBlur, relighting. Merge the rebuilt element over the background with its true alpha.
7. Remove unused layers before heavy nodes and before Write unless the delivery needs them.

## Verify
- With every pass at neutral settings, `difference` against the beauty is near zero everywhere, including soft edges and bright highlights (check at several exposures, in the working colourspace).
- Muting one pass changes only what it should (for example reflections only).
- Edges show no dark halo (double premultiplication) or bright fringe (missing premultiplication).

## Pitfalls
- Adding all layers: beauty plus its own components double-counts light.
- Merge `also merge` or Transform/Reformat filtering applied to depth, ID or vector layers; filtered or antialiased depth and IDs yield invalid in-between values.
- Colour-managing data passes read from file.
- Tinting a surface by grading the whole beauty also tints reflections; Brinkmann's car example separates reflections, grades the diffuse base through a paint mask, then adds reflections back.
- Passes with different premultiplication per layer in one file.
- Treating the lesson-14 pass set as universal: which layers exist, whether they sum to the beauty, and whether an empty pass is dropped depend on the renderer and setup.

## Sources
- Foundry 17.1 Channels: https://learn.foundry.com/nuke/17.1/content/comp_environment/channels/channels.html
- Merge operations: https://learn.foundry.com/nuke/17.1/content/comp_environment/merging/merge_operations.html
- Merge reference: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/merge.html
- Premult: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/premult.html
- Read: https://learn.foundry.com/nuke/17.1/content/reference_guide/image_nodes/read.html
- Brinkmann 2e ch.14 "Working with CG Elements" and "Multi-pass Rendering"; ch.5 "Compositing with Premultiplied Images".
- Lesson 14.srt (lesson-14; ASR, teaching-practice only): 00:10:40–00:14:19 AOV layers rebuild the beauty and wipe check; 00:14:25–00:16:45 plus merge order and alpha corruption; 00:17:01–00:17:35 pass-level grade; 00:20:10–00:20:17 speculars for highlight bloom; 00:24:01–00:24:55 grade after fixes as a guideline; 00:57:00–00:57:50 Shuffle dropped alpha. Foundry 17.1 owns node behaviour.
