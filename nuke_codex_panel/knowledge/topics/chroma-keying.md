---
id: "topics/chroma-keying"
kind: "topic"
title: "Chromakeyers"
category: "keying"
summary: "Choose and run Keylight, ChromaKeyer, IBK, Primatte or HueKeyer on screen footage, treating alpha, despilled RGB and edge colour as separate results before they are recombined."
aliases: ["green screen", "blue screen", "keylight", "chromakeyer", "ibk", "primatte", "despill", "spill suppression", "color difference key"]
tags: ["keying", "chroma", "despill", "screen", "alpha"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data", "fundamentals/keying-conventions", "fundamentals/graph-conventions", "fundamentals/quality-safeguards"]
related: ["topics/luma-keying", "topics/combine-keys", "topics/addmix-keymix", "nodes/channelmerge", "nodes/copy"]
nodes: ["Keylight", "ChromaKeyer", "IBKColor", "IBKGizmo", "Primatte", "HueKeyer", "Difference", "Merge"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions", "lesson-12a", "lesson-12b", "lesson-13"]
---
# Chromakeyers

## Applicability
Use for screen footage or any colour-defined region. A good key is three separate products: alpha (core plus edge), spill-removed foreground colour, and edge colour; keyers return them fused as RGBA. Studio policy (studio-conventions, a project preference): keep retained RGB separate and use keyers as alpha extractors (fundamentals/keying-conventions).

## Workflow
1. Cleanup first (studio-conventions): read the plate (screen purity, evenness, grain, spill, motion blur); do shot-dependent RGB prep and retain the original and a deliberate cleaned RGB branch. If grain makes hair indistinguishable from noise (lesson-12a), pull alpha from a denoised copy used only for the key, then Copy it onto the retained RGB so plate texture survives; a shot decision, not denoise-everything.
2. Pick a keyer by problem:
- Keylight: colour-difference keyer. Inputs Source, bg, InM (inside/holdout), OutM (outside/garbage). Pick `Screen Color` (also sets balance) from Source: view the node above Keylight, not the keyed output (lesson-12b). `Screen Gain` removes more screen colour; `Screen Balance` Foundry hints about 0.95 blue, 0.5 green; try 0.05/0.5/0.95 when unsure.
- ChromaKeyer: GPU-capable; `screen color`, matte controls (chroma gain, white/black point), `despill bias`, replace modes.
- IBKColor + IBKGizmo: a clean plate (IBKColor output into IBKGizmo `c`, or a shot clean plate) drives the key; suited to uneven screens.
- Primatte: incremental colour-volume sampling; HueKeyer: hue curve only; Difference: needs a clean plate of the background.
3. Alpha extraction: each regional keyer reads the same original or cleaned RGB; collect only its alpha. Keylight `View` = Screen Matte, Combined Matte or Status. Prefer garbage/inside mattes to overworking a key (Brinkmann); one keyer may suffice, none is assumed to solve every region. Harsh matte (lesson-12a/12b, Keylight 17.1): aggressive `Clip Black/White` or `Screen Dilate` hardens edges, `Clip Rollback` restores edge detail, `Screen Softness` softens a core/inside matte; if an impure screen makes the subject transparent, sample `Alpha Bias` from that foreground area. Core versus edge keys: topics/combine-keys.
4. Alpha assembly: ChannelMerge regional alphas, key stacks, roto inclusions and holdouts (B = running matte, `from` to hold out); see topics/combine-keys.
5. Copy the final alpha only onto the retained RGB (nodes/copy). Never pass a keyer's processed RGBA as the default final foreground.
6. Post-Copy on the retained RGB: despill, edge treatment, premultiplication for the next Merge, then the B trunk. Simple color-difference despill clamps the screen channel to the green value (bluescreen) where it exceeds it (Brinkmann). Keep suppression minimal and edge-masked (lesson-13): hue suppress or Keylight `Screen Balance` can hit legitimately coloured areas (blue clothing) or darken edges; check over bright, dark and single-channel views. Conditional: mild core despill plus stronger edge despill blended by a core/edge mask; Keymix suits that masked RGB blend but is not the alpha-assembly default.
Conditional in-keyer notes (not the default pre-Copy path): Keylight Despill Bias (sample skin/hair colours, Foundry), Screen/Inside Replace and ChromaKeyer despill/replace work inside the keyer. `Final Result` is premultiplied RGBA (Keylight `Unpremultiply Result`; ChromaKeyer `premultiply` can be off); IBKGizmo output is premultiplied. RGBA chaining: topics/combine-keys.

## Verify
- Alpha at high and low exposure: solid core, no screen-coloured holes, clean background.
- Despilled RGB where alpha is 1: no green/blue fringe in hair, no neutralised blue clothing.
- Composite over dark, light and mid-tone checks; step through motion-blurred frames; replace modes leave no rim.

## Pitfalls
- Taking despill and alpha from different keyers without fixing premultiplication: dark or bright edges.
- ChromaKeyer `premultiply` can be too aggressive on hair (Foundry).

## Sources
- Keylight: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/keylight.html
- ChromaKeyer: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/chromakeyer.html ; guide: https://learn.foundry.com/nuke/17.1/content/comp_environment/keying_with_chromakeyer/despill_controls.html and https://learn.foundry.com/nuke/17.1/content/comp_environment/keying_with_chromakeyer/multipass_keying.html
- IBKGizmo: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/ibkgizmo.html ; IBKColor: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/ibkcolor.html
- Primatte: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/primatte.html ; Difference: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/difference.html ; HueKeyer: https://learn.foundry.com/nuke/17.1/content/reference_guide/keyer_nodes/huekeyer.html
- Brinkmann 2e ch.6 "Procedural Matte Extraction"; ch.13 "Spill Suppression".
- Studio policy: studio-conventions (project preferences, not universal Nuke facts).
- Lessons 12a, 12b, 13 (lesson-12a, lesson-12b, lesson-13; ASR, teaching-practice only): Lesson 12a.srt 00:09:19–00:10:45 hard core; 00:40:57–00:45:35 noise vs edge detail, key on a denoised copy; Lesson 12b.srt 00:00:29–00:02:55 pick from source, gain/balance; 00:04:03–00:06:15 alpha bias, screen replace; Lesson 13.srt 00:00:57–00:04:20 minimal masked suppression; 00:25:35–00:33:45 mild-core/strong-edge blend.
