---
id: "topics/paint-cleanup"
kind: "topic"
title: "Dust and noise cleanup through Python: DustBust and Denoise"
category: "production-workflows"
summary: "DustBust dust points are Viewer-created (Ctrl/Cmd+click) in a custom points knob; scriptable knobs are frame_offset, edge_hardness, view_source, enable, mask. Denoise noise analysis is scriptable: analysisRegion, analysisFrame, analyze, lockNoiseAnalysis, analysisFile."
aliases: ["dustbust", "dust bust python", "dust points", "remove dirt scratches", "denoise python", "denoise analyze", "analysisRegion", "analyze noise", "noise analysis", "lockNoiseAnalysis", "film dirt cleanup", "scratch removal"]
tags: ["cleanup", "dustbust", "denoise", "paint", "grain", "python", "scratches"]
requires: ["fundamentals/channels-data", "fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["topics/rig-removal", "topics/analysis-python", "topics/viewer-sampling", "topics/chroma-keying", "topics/roto-python", "nodes/rotopaint"]
nodes: ["DustBust", "Denoise2", "RotoPaint"]
version: "Nuke 17.1v1 installed docs (draw_nodes/dustbust, filter_nodes/denoise) and strings of plugins/DustBust.so, Denoise2.so; source-derived, NOT runtime verified. Denoise is NukeX/Studio, may need a licence."
source_ids: ["foundry-17.1"]
---
# Dust and noise cleanup through Python: DustBust and Denoise

## Applicability
Use to remove dirt or scratches from scanned frames (DustBust) or reduce sensor/film noise (Denoise, class `Denoise2`). Correction of earlier guidance: Denoise analysis is NOT UI-only; it has named knobs and a button. DustBust points, by contrast, are created by Viewer clicks into a custom knob with no documented Python write route. Large or irregular damage and rig removal belong to RotoPaint (topics/rig-removal, nodes/rotopaint).

## Workflow
### DustBust
```python
assert src is not None and nuke.exists(src.fullName()), "source node missing"
d = nuke.nodes.DustBust(); d.setInput(0, src)   # nuke.nodes does not auto-connect to the selection
d["frame_offset"].setValue(1)      # 0 = same frame; animatable, one value for all points on a frame
d["edge_hardness"].setValue(0.5)   # all points on that frame
d["view_source"].setValue(False)   # True shows the clone source for current points
d["enable"].setValue(1)            # 0-1 effect intensity, not a mere checkbox
nuke.show(d); nuke.connectViewer(0, d)
print(d["points"].toScript())      # serialized state after the user's picks
```
- Documented knobs: `enable`, `view_source`, `frame_offset` (1), `edge_hardness` (0.5), output mask checkbox + `maskchannel` (none).
- Dust points: Foundry docs say Ctrl/Cmd+click in the Viewer; the plugin tooltip says alt+ctrl+click. The clone source can differ per point. The data is the custom `Dust_Knob` named `points`. The plugin parses it as points of exactly 3 numbers each (error text "point %d has %d numbers, should have 3"); what the three numbers mean is NOT documented. So: do not generate `points` blindly. Procedure: have the user click one dust spot, print `d["points"].toScript()`, record the format, and only reuse that observed shape; if no pick exists say the points must be placed in the Viewer.
- Viewer paint workflow: view the DustBust output at 1:1, step frames, set `frame_offset` so the source frame is clean (try 1 then -1; animate it where the neighbour is dirty too), Ctrl/Cmd+click each dust spot, toggle `view_source` to check the source patch, soften with `edge_hardness`.

### Denoise (Denoise2)
```python
# prerequisite: src is an existing, connected image node. Example values below are NOT shot defaults.
src = nuke.selectedNode()
f = 1001; x, y, r, t = 128, 128, 256, 256       # example frame and flat-area ROI (xyrt, 128x128); replace with the shot's own
assert src is not None and nuke.exists(src.fullName()), "source node missing"
dn = nuke.nodes.Denoise2(); dn.setInput(0, src)
print(dn["profile"].values(), dn["output"].values(), dn["analysisRegion"].value())
dn["lockNoiseAnalysis"].setValue(False)            # unlock BEFORE moving the region, else no re-analysis
nuke.frame(f); dn["analysisFrame"].setValue(f)
dn["analysisRegion"].setValue((x, y, r, t))      # image pixels; flat, detail-free area, >= 80x80
dn["analyze"].execute()                           # explicit re-analysis (button)
print(dn["lockNoiseAnalysis"].value(), dn["analysisRegion"].value(), dn["amount"].value())
```
- Knobs: `type` (Digital...), `model` (Modulated), `profile` (Constant/Automatic), `amount` (1), `rolloff` (2), `smoothness` (1), `lumablend` (0.7), `preserve_edges`, `lift_blacks`, `output` (Result...), `useGPUIfAvailable`, temporal controls, `analysisRegion`, `analysisFrame`, `analyze`, `lockNoiseAnalysis`, `analysisFile` (export/import profile).
- Auto-analysis: by default any change of the analysis box re-analyses. Because `lockNoiseAnalysis` is on after Import, set it False first or the region change has no effect; call `analyze.execute()` after a frame change without region change. A region under 80x80 means no denoise (plugin text: "Please expand the analysis region").
- Optional: `analysisFile` path then Export/Import buttons (Constant saves only analysis controls; Automatic also the noise profile); Noise input analyses another image. Automatic profile uses `profile` frame; scrub there and press recalculate.
- Keying: denoised copy for the key, retain original noise in the comp (topics/chroma-keying).

## Verify
- DustBust: view output and `view_source` on affected frames; `points` printout non-empty; step neighbours for pops.
- Denoise: `analysisRegion` read back; box away from edges; compare Result against source in a flat area; if nothing changes check region size and `lockNoiseAnalysis`.
- Render-time only: judge through a Viewer or Write (topics/analysis-python).

## Pitfalls
- Writing guessed `points` text; claiming dust points were placed without a printout.
- Using `enable` as a bool-only switch; it is a 0-1 intensity.
- Constant `frame_offset` across a clip when neighbour frames also have dirt.
- Analysis box on texture, edge or shadow; region left locked.

## Sources
- Foundry 17.1 docs: draw_nodes/dustbust, filter_nodes/denoise (Noise Analysis section).
- Strings of /opt/Nuke17.1v1/plugins/DustBust.so (Dust_Knob, points) and Denoise2.so (DenoiseAnalysisKnob, analysisRegion, analyze).
