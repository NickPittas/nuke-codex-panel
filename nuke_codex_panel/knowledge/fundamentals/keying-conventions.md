---
id: "fundamentals/keying-conventions"
kind: "fundamental"
title: "Keying conventions: clean RGB, alpha-only keys"
category: "fundamentals"
summary: "Studio policy for keying: cleanup first, keep original and cleaned RGB intact, extract only alpha from any keyer, combine regional keys with ChannelMerge, Copy alpha back to retained RGB, then despill, edge treatment and matching premultiplication."
aliases: ["cleanup before keying", "keyer RGB contaminated", "alpha only key", "ChannelMerge instead of Keymix", "regional keys", "key stack", "copy alpha back", "despill after key", "multiple keyers", "matte assembly"]
tags: ["keying", "alpha", "channelmerge", "copy", "despill", "edge", "premult", "convention", "matte"]
requires: ["fundamentals/alpha-premultiplication"]
related: ["fundamentals/graph-conventions", "fundamentals/quality-safeguards", "topics/chroma-keying", "topics/combine-keys", "topics/addmix-keymix"]
nodes: ["ChannelMerge", "Copy", "Keylight", "Primatte", "IBK", "Keymix", "Premult", "Unpremult"]
version: "Studio policy dated 2026-10-28; ChannelMerge facts from Nuke 17.1 documentation."
source_ids: ["studio-conventions", "foundry-17.1", "brinkmann-2e", "lesson-12a", "lesson-13"]
---
# Keying conventions: clean RGB, alpha-only keys

## Applicability
Use for any green or blue screen, luma or colour key, or matte assembly. This is the studio's working policy (studio-conventions), not a Foundry requirement; keyer mechanics live in topics/chroma-keying.

## Workflow
1. Cleanup first: do shot-dependent RGB prep (degrain, plate fixes, rig or marker removal) before keying. Keep the original source and a deliberate cleaned RGB branch. Do not substitute the keyer's processed RGB for either. When grain makes hair detail indistinguishable from noise (lesson-12a), denoise a copy used only to generate alpha, then Copy that alpha onto the retained RGB so its texture stays; shot-dependent, not a rule to denoise every plate.
2. Use keyers (Keylight, Primatte, IBK or others) to extract only alpha. Keep the clean RGB branch separate and intact beside them.
3. Add regional keys where the shot needs them (hair, edges, shadows, transparency). A simple shot may need one keyer; do not require several, and do not assume one keyer solves every region.
4. Assemble the final alpha with scalar operations: key stacks, roto inclusion and holdouts, and ChannelMerge, preferred over Keymix for building matte alphas. Keep B as the base matte and A the incoming matte.
5. ChannelMerge (Foundry 17.1): choose A and B channels and the output channel (defaults to alpha); other channels pass from B, and with no A both channels come from B. Operations include union, plus, from (B-A), minus (A-B), multiply and max/min; bbox can be union, B side or A side. For holdouts of an incoming A from a B base use from; minus reverses operands. Multiply has a negative-value caveat in the docs.
6. Copy only the final alpha onto the retained RGB (the original or cleaned branch).
7. Then despill, treat edges, and premultiply as the input state requires (see fundamentals/alpha-premultiplication). Unpremult before colour work only on premultiplied input, and premultiply once. Keep despill minimal and masked to the edge zone (lesson-13): check it did not neutralise legitimate colours such as blue clothing, then compare edges over brighter, darker and single-channel views.
8. Capability notes for edge RGB (lesson-13, not the matte workflow): Merge has no edge-shaping curves, whereas AddMix has A and B lookup curves driven by alpha (topics/addmix-keymix, mind its premultiplication). Keymix mixes RGB through a mask, so a mild-despill branch and a stronger edge-despill branch can be blended through a core/edge mask. Matte assembly stays ChannelMerge.
9. Composite the result as a normal layer into the B trunk, one A per Merge (fundamentals/graph-conventions).

## Verify
- View RGB and alpha separately: the RGB should match the cleaned plate, not show keyer processing.
- Check holdouts subtract in the right direction, and key regions overlap without seams.
- Check Merge output edges for dark or bright fringes, then premultiplication state.
- Check frames with motion blur, hair and spill.
- Compare Copy output with its input RGB in an unmasked area.

## Pitfalls
- Passing a keyer's processed RGBA onward as the default final foreground.
- Using Keymix as a drop-in for ChannelMerge: it mixes masked RGBA, not channel arithmetic.
- Swapping minus and from, or using multiply on mattes with negative values.
- Premultiplying twice, or despilling before the alpha is final.
- Inventing a multi-keyer rig for a simple shot, or stacking premult operations blindly. The intent is to preserve original and cleaned RGB, not to apply a fixed Premult recipe.

## Sources
- studio-conventions: teacher-supplied Nuke production conventions, provided 2026-10-28 (user policy; no public URL).
- ChannelMerge: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/channelmerge.html
- Lessons 12a and 13 (lesson-12a, lesson-13; ASR, teaching-practice only): Lesson 12a.srt 00:44:12–00:45:35 key from a denoised copy, original noise kept; 00:45:50–00:46:10 core then edge key order; Lesson 13.srt 00:03:40–00:04:20 minimal masked suppression; 00:21:35–00:25:35 and 00:27:29–00:33:45 AddMix versus Merge edges, core/edge Keymix despill blend. Foundry 17.1 owns node facts.
- Brinkmann 2e, chapters on matte extraction and compositing.
