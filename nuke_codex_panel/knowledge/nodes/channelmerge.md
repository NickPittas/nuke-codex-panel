---
id: "nodes/channelmerge"
kind: "node"
title: "ChannelMerge"
category: "channels"
summary: "Combines one channel from input A with one channel from input B into a chosen output channel (alpha by default), copying every other channel unchanged from B; the native node for assembling alpha-only mattes."
aliases: ["ChannelMerge node", "channel merge", "merge alpha", "matte assembly", "combine alpha only", "alpha union"]
tags: ["channels", "alpha", "matte", "merge", "keying"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data", "fundamentals/graph-conventions", "fundamentals/keying-conventions"]
related: ["nodes/copy", "nodes/keymix", "nodes/merge", "topics/combine-keys", "topics/addmix-keymix", "fundamentals/quality-safeguards"]
nodes: ["ChannelMerge"]
version: "Nuke 17.1 documentation; static reference, not runtime verified. Check installed node generation and licence."
source_ids: ["foundry-17.1", "studio-conventions"]
---
# ChannelMerge

## Purpose
Source-documented: merges one channel from each input and saves the result in the selected output channel. All other channels are copied unchanged from B. With no A connected, both channels are taken from B. By default it combines the inputs' alphas (A, B and output are all `rgba.alpha`, operation `union`), so an alpha-only matte can be built without touching RGB. Studio policy (studio-conventions, not a Foundry rule): prefer it over Keymix for assembling key mattes; see fundamentals/keying-conventions.

## Inputs
A (optional; supplies the A channel), B (base: supplies the B channel and every other channel passed through), mask (optional; by default limits the merge to non-black mask areas). Keep the B-base/A-incoming layout of fundamentals/graph-conventions: the running matte on B, each new matte or roto on A, one A per node.

## Controls
Documented knobs: `A` (default rgba.alpha), `B` (default rgba.alpha), `output` (default rgba.alpha), `operation` (default union), `bbox` (default union; B side clips A data outside B's box, A side clips B), mask channel `maskChannelInput` (default none), `inject`, `invert_mask`, `fringe`, `mix` (1 = full effect, 0 = original B).
Operations as documented: union A+B-AB; plus A+B; from B-A; minus A-B; multiply AB; max; min; in Ab; out A(1-b); stencil B(1-a); xor A+B-2AB; also absminus, divide, b if not a.
- Add a region to the running matte: union (independent partial coverage) or max (nested/same coverage). plus is exact only for disjoint shapes and can exceed 1.
- Hold out incoming A from the B-base matte: `from` (B-A), because B is the base. `minus` is A-B and reverses the operands; a base-on-B graph that picks it removes the base from the new shape instead.
- Inputs here are single channels read as values; `in`/`out`/`stencil` use alpha of the other input as documented, so choose the channel selectors deliberately.

## Verify
View the output alpha at high and low exposure; sample overlap pixels and compare with the formula of the chosen operation. Confirm RGB is untouched (it passes from B) and that values stay in 0..1. Check `bbox` against the background window. Runtime verified: false; availability, knobs and defaults may differ in the installed build.

## Pitfalls
- It is not a drop-in for Keymix: Keymix mixes A's RGBA into B through a mask, ChannelMerge computes a scalar from two channels. Do not treat either as an alias of the other; the class name is ChannelMerge only.
- Plain `minus`/`from` swapped, giving the inverse hold-out.
- `multiply` and similar scalar operations misbehave on negative values (documented caveat); keep mattes clamped.
- Output RGB comes from B; after taking the final alpha, Copy that alpha onto the retained clean RGB (nodes/copy), then despill, edge treatment and the premultiplication state the next Merge expects.

## Sources
- ChannelMerge: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/channelmerge.html
- Studio policy: studio-conventions (teacher-supplied production conventions; project preference, not Foundry documentation).
