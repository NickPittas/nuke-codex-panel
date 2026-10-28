---
id: "topics/addmix-keymix"
kind: "topic"
title: "Proper use of AddMix and Keymix"
category: "keying"
summary: "Keymix, AddMix and Merge over mechanics (matte source, unpremultiplied A, alpha lookup curves) and when each is an explicit choice; Keymix is not the default for assembling key mattes, where studio policy prefers ChannelMerge."
aliases: ["keymix", "addmix", "mix by matte", "merge through mask", "split keys", "keymix vs merge over", "keymix vs addmix"]
tags: ["keymix", "addmix", "mask", "premultiplication", "merge"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data", "fundamentals/keying-conventions", "fundamentals/graph-conventions", "fundamentals/quality-safeguards"]
related: ["topics/combine-keys", "topics/chroma-keying", "topics/luma-keying", "topics/rotoscoping-masking", "nodes/channelmerge"]
nodes: ["Keymix", "AddMix", "Merge", "Copy", "Premult", "Unpremult"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions", "lesson-10"]
---
# Proper use of AddMix and Keymix

## Applicability
Use when one image must replace another only where a matte says so. This topic teaches Keymix/AddMix mechanics; it is not the default key-matte assembly. Studio policy (studio-conventions; project preference, not Foundry law): assemble mattes alpha-only with ChannelMerge (topics/combine-keys), keep RGB separate, Copy the final alpha to it, and choose Keymix only deliberately. The three tools differ in where the matte comes from and what they assume about A:

| Node | Matte | Documented behaviour |
|---|---|---|
| Keymix | separate `mask` input or `maskChannel` (default rgba.alpha) | Aa + B(1-a) with a = mask; "for unpremultiplied images"; A is copied to B only where the mask is non-black |
| AddMix | A's own alpha | alpha of A indexes two lookup curves: the first multiplies A, the second multiplies B, results are added; it also premultiplies A |
| Merge over | A's own alpha | A + B(1-a); expects premultiplied A |

AddMix is not a synonym for over or a plain blend: its curves can shape how B and A weight against alpha. Keymix is not over with a mask on the side: it applies the mask as the alpha of A.

## Workflow
1. Name the matte: separate roto/key/gradient (Keymix), the element's own alpha with a shaped transition (AddMix), or already-premultiplied element with matching alpha (Merge over).
2. Keymix: connect A (new content), B (base), mask. Leave `channels` at all to take all channels from A, or restrict them; other channels pass from B. Set `maskChannel` explicitly, use `invert` for the opposite region, `mix` to dissolve, and `bbox` (union / B side / A side) to decide the output size; A or B outside a chosen box is clipped.
3. AddMix: A must include an alpha. If A is premultiplied, enable `premultiplied` (it divides A by alpha before the A curve) so you do not premultiply twice. Enable `nonlinear` only for HDR values that need the logarithmic remap. Edit the A and B LUT curves deliberately; `reset` returns them.
4. If A is a premultiplied CG render with its own alpha, Foundry advises against AddMix (detail can be lost by premultiplying twice). Use Merge over.
5. Typical deliberate Keymix uses: correct a region with a graded copy; replace specific channels through a matte; a soft-matte split of two tuned IBKGizmos is a Foundry-suggested option on its IBK page, but the studio default for regional keys is independent keyers on the same RGB with only alpha merged by ChannelMerge. Copy can do channel replacement through a mask too. ChannelMerge is a scalar channel operation, not a Keymix substitute.
6. Alpha out: Foundry states the Keymix result "contains no alpha channel", yet `channels` selectively copies and untouched channels come from B. Read the output alpha in the Viewer and set the alpha you need explicitly (Copy/Shuffle, or Merge) instead of assuming it is preserved or generated.
7. Merge operation choice (course practice, lesson-10): over needs a premultiplied A with a real alpha; light with no alpha (fire, glow) is a plus case. Read Foundry's formula in the operation menu; stencil (B(1-a)) and from (B-A) are different operations.
8. Alpha-only math (ChannelMerge policy): union (A+B-AB, default) combines mattes, multiply keeps the overlap, `from` holds out A; plus on alpha is rarely right.

## Verify
- Mask = 0 returns B; mask = 1 returns A (for Keymix); sample a mid-grey mask pixel and check Aa + B(1-a).
- Dark rim on a soft edge: the matte was applied twice (premultiplied A or AddMix on a premultiplied render). Bright rim: premultiplication missing upstream.
- View alpha/bbox of the output; confirm no clipped content and that the intended alpha exists.
- Merge difference against a one-frame offset shows what changed; it is a diagnostic only.

## Pitfalls
- Feeding a premultiplied A and the same alpha as `mask` to Keymix doubles the matte.
- Treating AddMix as a drop-in over/dissolve and changing curves unintentionally.
- Reversed polarity: by default A shows only where the mask is non-black; `invert` flips it to the non-white areas.
- Luminance or alpha of the mask above 1 or below 0: clamp it first (Brinkmann notes surprising results with superwhite masks).
- Plus on two alphas adds them (1 + 1 = 2): alpha above 1 overshoots later; sample where mattes overlap (lesson-10).

## Sources
- Keymix: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/keymix.html
- AddMix: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/addmix.html
- Merge (over, matte formulas): https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/merge.html
- Premult: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/premult.html
- Copy: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/copy.html ; IBKGizmo: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/ibkgizmo.html
- Brinkmann 2e ch.5 "Masks", "Compositing with Premultiplied Images".
- ChannelMerge: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/channelmerge.html
- Studio policy: studio-conventions (teacher-supplied production conventions; project preferences, not universal Nuke facts).
- Lesson 10.srt (lesson-10; ASR): 00:06:06–00:08:33 formulas, difference; 00:34:18–00:35:43 Keymix; 00:40:38–00:42:52 alpha union/plus.
