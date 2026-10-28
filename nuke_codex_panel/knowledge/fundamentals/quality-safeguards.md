---
id: "fundamentals/quality-safeguards"
kind: "fundamental"
title: "Quality safeguards: format, bbox, Crop, roto and paint"
category: "fundamentals"
summary: "Preflight checks: set root and background format, contain bboxes at the Merge, place Crop after compatible transform runs, avoid giant bboxes and out-of-memory, place roto keys deliberately, and split large RotoPaint work."
aliases: ["bbox out of memory", "giant bbox", "OOM", "root format", "project format", "roto jitter", "hundreds of strokes", "Crop breaks concatenation", "bbox containment", "monolithic RotoPaint", "wrong format", "preflight"]
tags: ["bbox", "format", "crop", "concatenation", "memory", "roto", "paint", "quality", "convention", "safeguard"]
requires: ["fundamentals/filtering-concatenation"]
related: ["fundamentals/graph-conventions", "fundamentals/keying-conventions", "topics/rotoscoping-masking", "topics/tracker"]
nodes: ["Merge", "ChannelMerge", "Crop", "Transform", "Reformat", "CornerPin", "Roto", "RotoPaint", "Dot", "PostageStamp"]
version: "Studio policy dated 2026-10-28; concatenation facts from Nuke 17.1 documentation."
source_ids: ["studio-conventions", "foundry-17.1", "lesson-10"]
---
# Quality safeguards: format, bbox, Crop, roto and paint

## Applicability
Use before and during any comp: when setting up a script, merging transformed or cornerpinned elements, seeing slow or out-of-memory renders, softness after transforms, roto jitter or heavy paint nodes. The checks are studio policy (studio-conventions); the concatenation facts are Foundry's.

## Workflow
1. Set up the project format correctly, then inspect the actual format of each input and node. A connected Roto inherits the plate's format and a Tracker works on the plate's pixels; Reformat may have its own explicit format, box or scale; the root format applies only where a node uses it (an unconnected Roto, or Reformat set to root). Changing the root does not fix a mismatched branch. A format is not itself a crop.
2. Contain composited bboxes to the background size. Prefer the Merge or ChannelMerge bbox set to the B side, or crop A to the background window immediately before the merge. Then check B's actual bbox, which may not equal the format.
3. Check all relevant frames, transformed or cornerpinned outliers, and memory footprint. Clipping at the B side does not retroactively make upstream work cheap or safe, so inspect the bbox before the merge too.
   Course practice (lesson-10): a Merge's union bbox can expand the data window and the cost of downstream filters such as Blur. Inspect the actual bbox/ROI and B-side setting after each merge; it is not always the combined bbox regardless of settings.
4. Do not crop away edges needed earlier by transforms or filters.
5. Concatenate compatible transform chains. Foundry 17.1 states Crop does not concatenate and breaks the chain, while Transform, Reformat and CornerPin concatenate; generation, settings and directional limits still matter, and not every transform-category node concatenates. Grade and other colour nodes interrupt it. Dots and PostageStamp pass it through. Put any required Crop after the compatible run, near the merge, or use the merge bbox to avoid Crop.
6. Roto keys: pick meaningful poses and occlusion changes, inspect interpolation, and add keys only where needed. Per-frame keys are justified for rapid change; the principle is deliberate placement, not a ban.
7. Paint: avoid one monolithic RotoPaint with hundreds of strokes. Split by logical task, region or time range into separate nodes. There is no fixed stroke limit.

## Verify
- Viewer bbox and format at the Merge, on first, middle, last and extreme-transform frames.
- Memory use stays reasonable after CornerPin or Transform.
- Compare chain output with a single combined transform on an edge.
- Scrub roto at sub-frame steps for wobble.
- Each paint node maps to one named task.

## Pitfalls
- A format mistaken for a crop, or an unset root format.
- Huge bbox or OOM after CornerPin or Transform with extreme points.
- Crop in the middle of transforms causing extra filtering.
- Assuming B-side bbox saves upstream cost.
- Keys on every frame causing jitter without need.
- Treating this policy as Foundry law.

## Sources
- studio-conventions: teacher-supplied Nuke production conventions, provided 2026-10-28 (user policy; no public URL).
- How Nodes Concatenate: https://learn.foundry.com/nuke/17.1/content/comp_environment/transforming_elements/node_concatenation.html
- ChannelMerge: https://learn.foundry.com/nuke/17.1/content/reference_guide/channel_nodes/channelmerge.html
- Lesson 10.srt (lesson-10; ASR, teaching-practice only): 00:08:50–00:09:46 merge result bbox and downstream cost.
