---
id: "topics/luma-keying"
kind: "topic"
title: "Lumakeys"
category: "keying"
summary: "Pull a matte from brightness with Keyer's luminance operation, shape it with the range handles, add inclusion/garbage mattes, and handle the alpha-only output correctly."
aliases: ["luminance key", "luma key", "lumakey", "keyer node", "sky replacement key", "brightness matte"]
tags: ["keying", "luminance", "matte", "alpha", "keyer"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/color-spaces", "fundamentals/keying-conventions"]
related: ["topics/chroma-keying", "topics/combine-keys", "topics/addmix-keymix", "topics/rotoscoping-masking", "nodes/channelmerge", "nodes/copy"]
nodes: ["Keyer", "ChannelMerge", "Copy", "Premult", "Merge", "Keymix", "Roto"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions", "lesson-09", "lesson-10"]
---
# Lumakeys

## Applicability
Use when the wanted region differs from its surround mainly in brightness: bright sky, dark backing with a bright subject, highlight or shadow selections, fire/smoke-like elements. A lumakey cannot separate a dark subject area from a dark background; for coloured screens use topics/chroma-keying.

## Workflow
1. Connect Keyer to the image and view the alpha channel (Viewer `A` key).
2. Keep `operation` on luminance key, or choose the property that actually separates the region: red/green/blue, saturation, max or min keyer. Keyer also offers redscreen/greenscreen/bluescreen subtraction operations.
3. Set the range graph. Foundry's table: A is where keying starts, B to C is the length of the full effect, D is where the effect stops. Their overview also states values below A clip to black and above B to white. Move handles while watching alpha at the subject's edge, not the composite.
4. Add an inclusion (inner garbage) matte for dark or bright areas inside the subject that the luminance range cannot separate, and a garbage (outer) matte for unwanted bright areas. Brinkmann stresses that the key's value is a good edge; handle the interior and exterior with shapes. Studio policy (studio-conventions, project preference): run the luma key on a branch whose alpha you collect, assemble inclusion/holdout alpha with ChannelMerge (B = running matte, A = roto; union/max to include, `from` to hold out), and Copy the final alpha back to the retained RGB; see topics/combine-keys.
5. Output goes to `output` (default rgba.alpha). `combine` is replace by default; use intersect or union only to combine with an existing alpha on purpose. `invert` gives the opposite matte.
6. Keyer writes the matte but leaves RGB unchanged, so it suits the alpha-only branch. Foundry's own tutorial inserts a Premult after Keyer before the Merge. Premult only if the next operation expects premultiplied RGB (Merge over does); if the image is used as a Keymix A input with a mask, premultiplying first doubles the matte.
7. Animate range handles when the lighting drifts (Brinkmann).
8. Fire or glow with no source alpha (course practice, lessons 09-10; the plate's own alpha, if any, may cover only a small part):
   - Fix unwanted colour by painting into the colour channels (RotoPaint output set to rgba, painting black), not into alpha.
   - To get a matte, add contrast on a branch, view each candidate (red, luminance) as alpha, pick the cleanest and build an alpha-only branch; then Copy that alpha onto the retained RGB. Different channels give visibly different mattes, so compare them.
   - Emissive light often needs no matte: Merge plus is A + B and ignores alpha, so a fire meant to pass behind an occluder still shows through. Apply the assembled visibility matte (roto holdout built alpha-only with ChannelMerge `from`) to the fire RGB (Premult, RGB × alpha, or use it as the plus Merge's mask) before plus. ChannelMerge changes only alpha and Copy does not change RGB. Keep a pure-RGB analysis side for the final output so the matte is not premultiplied twice, and check whether the incoming RGB is already premultiplied.
   - A luma key can also drive a Grade or glow through its mask: key the brightness, then apply the effect only through that matte.

## Verify
- Brighten and darken the alpha view (Viewer gain/gamma) to find near-white and near-black impurities; Brinkmann notes the eye misses almost-white and almost-black.
- Composite over saturated mid-tone and bright backgrounds, at 100% zoom.
- Scrub the whole shot: edge crawl, flicker, grain-driven speckle.
- Sample pixels: the handles act on the values actually in the working space. Confirm that the values you need are inside the graph's range.

## Pitfalls
- Softening or eroding the matte to hide a poor key loses detail (Brinkmann); first retune the range.
- Dark regions inside a bright-keyed subject remain transparent without an inclusion matte.
- Forgetting `invert` or `replace` overwriting an upstream alpha.
- Keying a display-referred preview and then expecting the same thresholds on linear data.
- Painting corrections into alpha instead of RGB, or taking the plate's partial alpha as the fire matte.

## Sources
- Keyer: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/keyer.html
- Keyer nodes overview: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/keyer_nodes.html
- Premult: https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/premult.html
- Brinkmann 2e ch.6 "Keying Based on Luminance", "Garbage Mattes", "Checking the Solidity of your Matte".
- Studio policy: studio-conventions (teacher-supplied production conventions; project preferences, not universal Nuke facts).
- Lesson 09.srt (lesson-09; ASR, teaching-practice only): 00:02:42–00:03:18 paint in RGBA not alpha; 00:13:51–00:14:23 luma-driven mask; 00:17:59–00:19:21 channel-to-alpha (ASR sketchy; re-derived under current policy); 00:32:26–00:32:40 key then glow.
- Lesson 10.srt (lesson-10; ASR, teaching-practice only): 00:03:38–00:05:32 plus for additive light; 00:12:14–00:12:26 premultiply after the fire has an alpha.
