---
id: "topics/combine-keys"
kind: "topic"
title: "How to merge multiple keys"
category: "keying"
summary: "Combine several mattes by deciding how their coverage overlaps (nested, independent or disjoint) and which areas are holdouts, then pick max, screen, plus, in/out/stencil or a soft spatial split accordingly."
aliases: ["combine mattes", "merge keys", "core and edge matte", "garbage matte", "holdout matte", "union of mattes", "split keys"]
tags: ["keying", "matte", "overlap", "holdout", "garbage"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data", "fundamentals/keying-conventions", "fundamentals/graph-conventions", "fundamentals/quality-safeguards"]
related: ["topics/chroma-keying", "topics/luma-keying", "topics/addmix-keymix", "topics/rotoscoping-masking", "nodes/channelmerge", "nodes/copy"]
nodes: ["ChannelMerge", "Copy", "Merge", "Keymix", "Keyer", "Keylight", "ChromaKeyer", "Shuffle", "Roto"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions", "lesson-12a"]
---
# How to merge multiple keys

## Applicability
Use when more than one matte exists for the same subject: core and edge/hair keys, a luma plus a chroma key, a garbage/holdout shape, per-region tuned keys. No single operator is correct for all; the choice follows how the coverage of the mattes overlaps and whether some area must be removed or forced solid.

## Workflow
1. Classify each matte's role: **core** (solid body), **edge/detail** (hair, motion blur), **inclusion** (force solid), **garbage/holdout** (force removed), **regional** (valid only in an area).
2. Studio policy default (studio-conventions, a project preference): keep RGB separate; key each region from the same original or cleaned RGB, collect only alpha, and assemble with ChannelMerge on a vertical B-base chain (B = running matte, A = next key, roto inclusion or holdout, one A per node, nested mini-trees). Copy the final alpha to the retained RGB afterwards; never carry keyer RGBA through the assembly (fundamentals/keying-conventions).
   Core and edge (lesson-12a, course practice): make the core hard and solid (no hair or motion blur) with blurred edges so the join is not a hard line; the edge key carries hair and motion-blur detail, with its garbage removed. To clean one region without losing edge detail elsewhere, use a roto-masked alpha-only Grade or blur, check the mask on moving frames, and Reformat the roto if its format differs from the plate.
3. Choose the operation from the overlap (documented Merge/ChannelMerge operations; ChannelMerge offers union, plus, max, min, in, out, stencil, from, minus):
- Nested coverage, or same pixels meant: `max` (max(A,B)); Foundry calls it a good way to combine mattes and bring hair detail through. `min` is the intersection counterpart.
- Independent partial coverage: ChannelMerge `union` (A+B-AB) or Merge `screen` (A+B-AB for values between 0 and 1; it falls back to max otherwise).
- Disjoint coverage: `plus` (A+B) is only exact when the shapes do not overlap; it can exceed 1.0 and Foundry advises against it for mattes.
- Holdout with B as the running matte: ChannelMerge `from` (B-A) removes the incoming A shape from B; `minus` is A-B and reverses the operands, so check which is the base. Merge equivalents: `stencil` B(1-a), `out` A(1-b); `in` (Ab) and `mask` (Ba) keep only the overlap. Confirm garbage does not remove semi-transparent edge.
- Touching shapes without a seam: conjoint-over or disjoint-over, which assume fully correlated or non-overlapping partial coverage (Foundry).
4. Regional keys (hair vs body tuned): default is independent keyers on the same RGB, each alpha limited by roto or a soft-edged matte and merged with ChannelMerge; a hard split shows the transition, a soft one hides it (Brinkmann). Keymix masks both alpha and RGB and stays an explicit, non-default option (topics/addmix-keymix).
5. Chained keyers (conditional, not the preferred hand-off): Keyer `combine` offers replace, intersect, union. ChromaKeyer: upstream `view` = intermediate result, downstream `inside mask` = source alpha, final result only last. Keylight: upstream View = Intermediate Result, downstream Source Alpha = Add To Inside Mask; `Combined Matte` shows the masks added.
6. After the final alpha, Copy it onto the retained RGB, then despill, edge treatment and premultiplication for the next Merge. If RGB was premultiplied by an earlier alpha, unpremult, adjust, re-premultiply with the final alpha (Foundry Premult). Brinkmann warns against changing only the alpha of a premultiplied image; the alpha-only edits here act on the separate matte.

## Verify
- View the combined alpha with high/low exposure; sample overlap pixels for each operator's expected value and flag values above 1.
- Toggle each input off; each should change only its own region.
- Check the split seam and every holdout edge, especially semi-transparent hair, over dark and light backgrounds; core and edge keys must not show a hard line or double edge.
- Scrub the animation: garbage tracked or animated shapes must not eat the subject.

## Pitfalls
- Defaulting to plus or max everywhere: both mis-handle some overlaps.
- Soft garbage that dims detail; hard garbage that leaves pops.
- Combining mattes but not the RGB they belong to.
- Over-processing matte (Brinkmann: edge softening is not a substitute for a good key).

## Sources
- Merge operations: https://learn.foundry.com/nuke/17.1/content/comp_environment/merging/merge_operations.html
- Merge reference: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/merge.html
- Keyer: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/keyer.html ; Keylight: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/keylight.html
- ChromaKeyer multi-pass: https://learn.foundry.com/nuke/17.1/content/comp_environment/keying_with_chromakeyer/multipass_keying.html
- Premult: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/premult.html
- Brinkmann 2e ch.6 "Matte Manipulations".
- Lesson 12a.srt (lesson-12a; ASR, teaching-practice only): 00:08:34–00:10:45 and 00:23:32–00:25:55 core versus edge, blurred core edge; 00:20:43–00:21:49 and 00:32:39–00:35:16 roto-masked alpha-only cleanup, Reformat; 00:26:13–00:27:45 roto patches.
- ChannelMerge: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/channelmerge.html
- Studio policy: studio-conventions (project preferences, not universal Nuke facts).
