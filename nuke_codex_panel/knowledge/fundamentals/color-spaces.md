---
id: "fundamentals/color-spaces"
kind: "fundamental"
title: "Color spaces and working space"
category: "fundamentals"
summary: "Project working space, Read/Write colorspace, display transform and data images: what to check before grading, merging, or exporting."
aliases: ["linear", "gamma", "OCIO", "colorspace", "working space", "scene linear", "ACEScg", "sRGB", "log"]
tags: ["color", "ocio", "linear", "display", "read", "write"]
requires: []
related: ["fundamentals/channels-data", "fundamentals/alpha-premultiplication", "topics/color-management-correction"]
nodes: ["Read", "Write", "OCIOColorSpace", "Viewer", "Grade"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e"]
---
# Color spaces and working space

## Applicability
Use before grading, merging, blurring, keying, or writing images from mixed sources (camera log, display-referred video, CG, textures, data passes). Each stage should be known to be in a specific colorspace.

## Workflow
1. Read the project colour management: Project Settings > Color. It is either the Nuke native (nuke-default) set or OCIO with a chosen config. Under OCIO, the working space defaults to the config's scene linear role; it can be changed, so read it rather than assuming linear.
2. Set each Read node's colorspace to the real encoding of the file. Under OCIO, Read converts into and Write converts out of the working space, so no extra conversion node is needed for ordinary file input and output.
3. Use OCIOColorSpace (input to output colorspace) only for deliberate in-graph conversions, for example into a log space for a grade and back (its swap control exists for this). Keep the pair matched.
4. Judge appearance through the Viewer's view transform. That is a display step, not a change to the pixels.
5. Treat data images (normals, depth, position, IDs, masks) as non-colour: do not run colour conversions or display transforms on them; see the channels document.

## Verify
- Sample pixel values at known references (a grey card, a constant) to confirm the expected range.
- Compare viewer clip_warning (exposure) before and after a conversion: out-of-range values should match intent.
- Round-trip a test frame through Read and Write and compare.

## Pitfalls
- A wrong Read colorspace corrupts every downstream grade silently; the result still looks plausible.
- Brinkmann shows grading, blurring and merging behave differently on nonlinear data; the effect is strongest on midtones and soft edges. Foundry notes some operations may work better in non-linear spaces such as log, so linear is a default to check, not a law.
- A converting node placed twice, or Read and an OCIOColorSpace both converting, double-applies the transform.
- Names of colorspaces differ between configs; enumerate the installed config instead of typing names from memory.

## Sources
- OCIO Color Management: https://learn.foundry.com/nuke/17.1/content/comp_environment/configuring_nuke/using_ocio_config_files.html
- OCIOColorSpace: https://learn.foundry.com/nuke/17.1/content/reference_guide/color_nodes/ociocolorspace.html
- Viewer: https://learn.foundry.com/nuke/content/reference_guide/image_nodes/viewer.html
- Brinkmann 2e, section "Linear versus Nonlinear when Compositing" (Figures 14.13-14.14), theory only.
