---
id: "fundamentals/coordinates"
kind: "fundamental"
title: "Coordinates, formats and bounding boxes"
category: "fundamentals"
summary: "Pixel-space conventions, format versus bounding box, pixel aspect, and the separate 3D spaces (object, screen, world) to check before positioning anything."
aliases: ["format", "bbox", "bounding box", "resolution", "pixel aspect", "origin", "overscan", "world space", "screen space"]
tags: ["coordinates", "format", "bbox", "transform", "pixel-aspect", "3d-space"]
requires: []
related: ["fundamentals/filtering-concatenation", "topics/node-graphs", "topics/3d-navigation", "topics/camera-projection"]
nodes: ["Reformat", "Crop", "Transform", "Viewer", "Roto", "CheckerBoard"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "studio-conventions"]
---
# Coordinates, formats and bounding boxes

## Applicability
Use when positioning elements, choosing output size, cropping, tracking, drawing shapes, or mixing 2D and 3D. Positions only mean something relative to a named space.

## Workflow
1. 2D pixel space: Foundry's format and Crop controls list x (left), y (bottom), r (right), t (top), and CheckerBoard counts boxes from the bottom-left corner. [INFERENCE] The origin is therefore bottom-left with y increasing upward; confirm by sampling a known pixel in the Viewer.
2. Separate three things: the format (nominal frame, resolution and pixel aspect), the bounding box (the area Nuke considers valid image data), and what is visible in the Viewer. Overscan lives in the bounding box beyond the format; enable the Viewer's show overscan to see it.
3. Choose the output frame with Reformat (to format, to box, or scale, with a resize type such as fit, fill, width, height or distort). Put it where the output size should be set, typically just before Write, and check that pixel aspect matches the delivery format.
4. Control bbox growth: Merge sets bbox to union by default, and transforms can enlarge it. Format is not a crop: establish the actual root/background format first, then contain the comp with the Merge's B-side bbox, or Crop the incoming A to the background window immediately before the Merge (studio preference, `fundamentals/quality-safeguards`). The B bbox is the actual background's, which is not necessarily the format. Use Crop, AdjBBox, CopyBBox or BlackOutside when you need a smaller area. After AdjBBox or CopyBBox, content outside the new bbox is replicated at the edges unless BlackOutside follows.
5. Mixing 2D and 3D: 3D positions are in world, object or screen space (Viewer transform space), and a 2D pixel coordinate becomes meaningful in 3D only through a camera's projection. Identify whether the script uses classic or new 3D system nodes first; they are distinct systems with different Viewer behaviour.

## Verify
- View format and bbox boundaries with the Viewer overlays or the Node Graph bbox warning preference; compare size at Write.
- Place a known marker at an exact coordinate and check where it lands, including with non-square pixels.
- For 3D, check axis direction in the Viewer's mini axes, which always show world space.

## Pitfalls
- A big bbox from an unbounded generator or a transform slows everything even when the result looks identical.
- Viewer ignore pixel aspect draws square pixels, so a stretched look can be display rather than data.
- Control values (centres, translations) are in the units of their own space; read the control's documented space instead of assuming pixels or normalised values.
- Coordinates from another application (top-left origin, 0-1 UV, centre-origin) need conversion; do not copy numbers across unchanged.
- Set root/project format deliberately (studio preference), but do not assume everything depends on it. A connected Roto inherits its input's format (its own format control only applies with no input); Tracker works in the plate's pixel coordinates; Reformat uses root.format only when its output format is left at the default, otherwise its explicit format, box or scale. Inspect the actual format at each relevant input/node: a wrong root does not necessarily break a correct plate branch, and changing root does not fix mismatched inputs.
- B-side or merge-time clipping does not make upstream work cheap or safe: a CornerPin/Transform outlier can still allocate a huge bbox earlier. Check all relevant frames, and keep image edges that earlier transforms or filters need.

## Sources
- Reformatting Elements: https://learn.foundry.com/nuke/17.1/content/comp_environment/reformatting_elements/reformatting_elements.html
- Adjusting the Bounding Box: https://learn.foundry.com/nuke/17.1/content/comp_environment/reformatting_elements/adjusting_bbox.html
- Merge (set bbox to): https://learn.foundry.com/nuke/17.1/content/reference_guide/merge_nodes/merge.html
- Viewer: https://learn.foundry.com/nuke/content/reference_guide/image_nodes/viewer.html
- CheckerBoard: https://learn.foundry.com/nuke/content/reference_guide/image_nodes/checkerboard.html
- Brinkmann 2e, aspect ratio and pixel aspect discussion in the image representation chapters (theory).
- Studio conventions (teacher-supplied, 2026-10-28; project preferences, not universal Nuke facts): format versus bbox containment at the Merge.
