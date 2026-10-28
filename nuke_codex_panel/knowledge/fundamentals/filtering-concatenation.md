---
id: "fundamentals/filtering-concatenation"
kind: "fundamental"
title: "Filtering, resampling and concatenation"
category: "fundamentals"
summary: "Which operations resample pixels, which Nuke transforms concatenate into one filtering pass, what breaks the chain, and how to choose and verify a filter."
aliases: ["concatenation", "concatenate", "resampling", "filter", "soft image", "sharpness loss", "Lanczos", "Cubic", "Impulse", "stacked transforms"]
tags: ["filtering", "concatenation", "transform", "resampling", "sharpness", "quality"]
requires: ["fundamentals/coordinates"]
related: ["fundamentals/channels-data", "topics/matchmove", "topics/tracker"]
nodes: ["Transform", "Reformat", "CornerPin", "Tracker", "Crop", "STMap"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions"]
---
# Filtering, resampling and concatenation

## Applicability
Use when a transform chain looks soft, jittery, haloed or aliased, when stacking Transform, Reformat, CornerPin or Tracker nodes, or when choosing a filter. Resampling and concatenation are different: resampling is computing new pixel values from old ones; concatenation is Nuke merging adjacent transforms so resampling happens once.

## Workflow
1. Find every spatial resample in the chain: scales, rotations, translations by non-integer amounts, warps, Reformat, and any node with a filter control. A pure integer translation need not resample, and Impulse keeps original values.
2. Group adjacent concatenating nodes. Foundry lists, among nodes that concatenate: Transform, Tracker, CornerPin, Reformat, Card3D, Stabilize, Switch, Dot, NoOp and disabled nodes. Dot, Switch and disabled nodes do not break the chain; the guide says PostageStamp likewise passes concatenation through. Compatibility depends on node generation, settings and direction (some nodes only receive from upstream), so check the current page rather than assuming every transform-category node concatenates.
3. Nodes in a separate list only receive concatenation from upstream (for example GridWarp, SplineWarp, STMap, LensDistortion, IDistort), and a third list does not concatenate at all (for example Crop, PlanarTracker, AdjustBBox, BlackOutside, Mirror). Check the current list rather than recalling it, since it is versioned.
4. Remove or move non-concatenating nodes between transforms; otherwise each segment filters separately. When several concatenating nodes carry different filters, only the last node's filter is used. Crop does not concatenate and breaks a transform chain: place a required Crop after the compatible Transform/Reformat/CornerPin run, near the Merge, or let the Merge's B-side bbox contain the result instead (studio preference, `fundamentals/quality-safeguards`).
5. Choose the last filter deliberately. Foundry describes Impulse as no smoothing, Cubic (default) as some smoothing, Keys/Simon/Rifman as increasing sharpening, Mitchell as smoothing plus blur, Parzen as the most smoothing, and Lanczos/Sinc as sharpening good for scaling down. Brinkmann notes lower-quality filters are acceptable for previews if the final uses a better one.
6. Where a clamp control exists (Transform, Tracker, Reformat), use it for halos from sharpening filters.

## Verify
- Compare the chain against a single combined transform on a high-contrast edge and a fine pattern at 1:1 in the Viewer.
- Animate a sub-pixel move and watch for popping to whole pixels (a sign of an unsuitable filter).
- Check the edge in alpha as well as RGB for halos or ringing.

## Pitfalls
- Colour nodes do not concatenate: a Grade or other colour node placed between two Transforms is a non-concatenating node in the chain, so the adjacent transforms no longer merge and the image is filtered once per segment. Foundry's remark that 32-bit float avoids visible round-off explains why colour nodes need no concatenation; it does not permit placing them between transforms. The colour node itself does not spatially filter; move it before or after the transform group.
- Concatenation reduces generations of filtering; it does not make a scale-down sharp.
- Sharpening filters can overshoot, causing negative or super-white halos at edges.
- Brinkmann notes resampling behaviour changes with colour encoding; resample in the intended working space.
- Do not Crop away edges between transforms to save memory; it breaks concatenation and removes pixels later transforms or filters may need.

## Sources
- How Nodes Concatenate: https://learn.foundry.com/nuke/17.1/content/comp_environment/transforming_elements/node_concatenation.html
- Choosing a Filtering Algorithm: https://learn.foundry.com/nuke/content/comp_environment/transforming_elements/filtering_algorithm_2d.html
- Reformatting Elements: https://learn.foundry.com/nuke/17.1/content/comp_environment/reformatting_elements/reformatting_elements.html
- Brinkmann 2e, section "Filtering Algorithms" (Chapter 4) and "Linear versus Nonlinear when Compositing".
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): Crop placement near the Merge or B-side bbox.
