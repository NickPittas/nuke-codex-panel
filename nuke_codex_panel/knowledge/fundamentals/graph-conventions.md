---
id: "fundamentals/graph-conventions"
kind: "fundamental"
title: "Graph layout and B-pipe conventions"
category: "fundamentals"
summary: "Studio policy for readable top-to-bottom node graphs: vertical B trunk, one A per Merge, nested mini B-trees, room for branches, single Read reuse, Stamps or PostageStamp routing, separate 3D and projection backdrops."
aliases: ["B-pipe", "B pipe", "B trunk", "top to bottom graph", "one A per merge", "graph layout", "messy graph", "nested mini tree", "postage stamp reuse", "Stamps", "reuse Read", "backdrop sections", "3D backdrop"]
tags: ["graph", "layout", "merge", "B-pipe", "convention", "postagestamp", "dot", "backdrop", "projection", "organization"]
requires: ["fundamentals/node-selection"]
related: ["fundamentals/keying-conventions", "fundamentals/quality-safeguards", "topics/node-graphs", "topics/camera-projection", "topics/texture-projection"]
nodes: ["Merge", "Dot", "PostageStamp", "Backdrop", "Read"]
version: "Studio policy dated 2026-10-28; Foundry facts from Nuke 17.1 documentation."
source_ids: ["studio-conventions", "foundry-17.1"]
---
# Graph layout and B-pipe conventions

## Applicability
Use before building, extending or tidying any comp graph. The user's rule is "we ALWAYS use top-to-bottom B-pipe": for new and organized work this is REQUIRED, not an optional agent choice. Depart from it only when the user explicitly requests or agrees to a different layout. It is studio policy (source studio-conventions), not a Foundry engine constraint.

## Workflow
1. Put the background or base plate on a vertical trunk running top to bottom, entering each Merge at B. Each added layer enters at A from the left or the right, whichever keeps lines short and uncrossed.
2. Use one A layer per Merge. Chain separate sequential Merges down the trunk instead of one Merge with many A inputs.
3. Keep B as base and A as incoming inside every mini-tree, including matte assemblies (for example ChannelMerge, see fundamentals/keying-conventions). Never flip B and A to save space.
4. Leave vertical and lateral room so each A branch can hold its own complete nested B-pipe comp (its own base, cleanup, key or grade steps) read top to bottom, then feed the trunk at A.
5. Work in stage order: cleanup, then key, then layer comp. Each stage is a readable mini-tree.
6. Reuse one appropriate Read for a shot instead of duplicate Reads or long pipes across the graph. Branch from it, and route with Dots and Backdrops. If the Stamps plugin is installed (verify in the running session; do not install it), use it for named routing. A native PostageStamp is an alternative, and is not the same node as Stamps.
7. Native PostageStamp must have a real upstream connection; it shows a thumbnail and does not alter the image. It is not a disconnected source or an automatic cache. Dots and PostageStamp pass concatenation through per Foundry (see fundamentals/quality-safeguards).
8. Build projection and 3D work (cameras, cards, ScanlineRender, projection setups) in separate labelled Backdrops. Return a controlled 2D output (a rendered or projected result) to the trunk, with one named hand-off Dot.
9. Label Backdrops and Dots by purpose (for example "cleanup", "key", "3D projection", "output").

## Verify
- Trace each Merge: B shows the lower-priority base, A the incoming layer, and A has a single source.
- Read the graph top to bottom without following pipes backwards or across unrelated branches.
- Check each routed copy (Stamp or PostageStamp) really originates from the intended Read and the Read is not duplicated.
- Confirm Backdrop contents belong to one stage and the hand-off into the trunk is explicit.
- In the live script, inspect node inputs rather than trusting positions.

## Pitfalls
- Left-to-right chains with the background drifting sideways hide the B trunk.
- Many-input Merge or extra A ports make order and masks hard to read.
- Stacking branches too tightly leaves no room for the nested comp; spacing is part of the convention.
- Assuming PostageStamp is a magic source or equals the Stamps plugin.
- Nesting 3D nodes directly on the 2D trunk without a Backdrop.
- Treating existing graphs laid out differently as invalid Nuke: they work, but new or organized work follows the user's convention.

## Sources
- studio-conventions: teacher-supplied Nuke production conventions, provided 2026-10-28 (user policy; no public URL).
- PostageStamp: https://learn.foundry.com/nuke/17.1/content/reference_guide/other_nodes/postagestamp.html
- How Nodes Concatenate: https://learn.foundry.com/nuke/17.1/content/comp_environment/transforming_elements/node_concatenation.html
