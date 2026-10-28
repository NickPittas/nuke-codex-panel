---
id: "fundamentals/alpha-premultiplication"
kind: "fundamental"
title: "Alpha and premultiplication"
category: "fundamentals"
summary: "How to decide whether an image is premultiplied, where Premult and Unpremult belong, and how to spot double-premultiply and fringe errors."
aliases: ["premult", "unpremult", "premultiplied", "straight alpha", "black fringe", "dark edges", "double premultiply"]
tags: ["alpha", "premultiplication", "merge", "fringing", "edges"]
requires: []
related: ["fundamentals/color-spaces", "fundamentals/channels-data", "topics/chroma-keying", "topics/color-and-roto"]
nodes: ["Premult", "Unpremult", "Merge", "Roto", "Copy"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-04"]
---
# Alpha and premultiplication

## Applicability
Use whenever RGB and alpha are combined, merged, keyed, graded, or exported. Premultiplied means RGB was already multiplied by alpha; unpremultiplied (straight) means it was not. Which state an image is in is a fact about the file or node, not a default.

## Workflow
1. Determine the state of each input. Rendered CG is typically premultiplied; Foundry notes a black or very dark background suggests it may be. Keyer outputs and shapes vary, so check the node. A Read node has a premultiplied checkbox for declaring file state.
2. Merge expects premultiplied inputs for most operations (over is A + B(1-a)). The matte operation is the documented exception and takes unpremultiplied inputs.
3. To grade premultiplied footage: Unpremult, correct, Premult. Alternatively use a node's own (un)premult by control set to the alpha channel (OCIOColorSpace documents this), which is equivalent for a single node.
4. Premult unpremultiplied elements before they enter Merge. Premult's multiply channels default to rgb, so alpha is not squared by default.
5. A Roto premultiply control set to rgba premultiplies alpha against itself; set it to rgb unless that is intended.

## Verify
- Over a contrasting background (bright and dark), view RGB and alpha separately at the soft edge.
- Dark halos at soft edges suggest double premultiply; bright or additive-looking edges suggest missing premultiply. Brinkmann describes both as classic symptoms.
- Only when the straight (unpremultiplied) RGB is known to lie in 0-1 does premultiplied RGB stay at or below alpha; HDR straight values above 1 legitimately give premultiplied RGB above alpha (straight 4 with alpha 0.5 gives 2). Use that check conditionally. A raised black level outside the matte (RGB non-zero where alpha is 0) brightens the background after Merge, whatever the range.

## Pitfalls
- Unpremult divides by alpha: where alpha is 0 the colour is undefined, so keep corrections limited to meaningful pixels.
- Grading premultiplied RGB without unpremultiplying breaks the RGB/alpha relationship in soft areas.
- Colour space and alpha interact: premultiply in the working space, not on display-encoded data.
- Never assume a state from the file extension alone.
- Course example (lesson-04): colour-correct before premultiplying, or wrap an extreme correction in Unpremult then Premult as separate nodes; correcting premultiplied edges can tint them. Premultiply foreground before Merge when not already premultiplied.

## Sources
- Premult: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/premult.html
- Merge: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/merge.html
- OCIOColorSpace (unpremult control): https://learn.foundry.com/nuke/17.1/content/reference_guide/color_nodes/ociocolorspace.html
- Roto (premultiply control): https://learn.foundry.com/nuke/17.1/content/reference_guide/draw_nodes/roto.html
- Brinkmann 2e, section "Compositing with Premultiplied Images" (Chapter 5), theory only.
- Lesson 04 c.srt (lesson-04, ASR transcript, teaching-practice only): 00:58:02–01:00:27 correct before premult, separate Unpremult/Premult nodes.
