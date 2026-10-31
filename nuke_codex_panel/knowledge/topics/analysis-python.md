---
id: "topics/analysis-python"
kind: "topic"
title: "Running analysis nodes from Python and reading results"
category: "scripting"
summary: "Which analysis nodes need nuke.execute (CurveTool), which fill knobs from a button (MatchGrade, BlinkScript) and which only run at render (SmartVector, STMap). Exact trigger, ROI, range and result-knob readback. Lens and projection analysis have their own topics."
aliases: ["CurveTool python", "autocrop python", "nuke.execute", "executeMultiple", "analyzeRefFrames", "BlinkScript recompile", "SmartVector write", "analysis button", "knob.execute"]
tags: ["python", "curvetool", "matchgrade", "blinkscript", "smartvector", "execute", "analysis"]
requires: ["fundamentals/time-sampling"]
related: ["topics/lens-calibration", "topics/projection-bake", "topics/optical-flow-retiming", "topics/color-management-correction"]
nodes: ["CurveTool", "MatchGrade", "BlinkScript", "SmartVector", "Crop", "Write"]
version: "Nuke 17.1 installed docs, shipped nukescripts source, plugin binary strings and live probes. CurveTool readback verified live; MatchGrade, BlinkScript and SmartVector names come from docs/binary and are not run. MatchGrade is NukeX/Studio."
source_ids: ["foundry-17.1"]
---
# Running analysis nodes from Python and reading results

## Applicability
Most nodes just render. A few compute data first, by three mechanisms:
1. **Executable node**: `nuke.execute(node, first, last, inc)` or `nuke.executeMultiple([nodes], ([first, last, inc],))` runs the node over frames and writes results into knobs (CurveTool, LensDistortion2, PointsTo3D, Reconcile3D).
2. **Analysis button**: `node['knob'].execute()` for named buttons (as `nukescripts/toolbars.py` does with `CurveTool['resetROI']`). Unnamed `Script_Knob` buttons are found by `label()`; those whose Tcl is `execute_panel this` are just the dialog form of `nuke.execute`, so call `nuke.execute` directly.
3. **Render-time only** (SmartVector, STMap, DustBust, Denoise): no result knobs for the render itself; evaluate through a Viewer or Write. For interactive DustBust points and Denoise2's optional noise-profile analysis, see topics/paint-cleanup.
Do not declare a path impossible because docs are silent: read the shipped source, then the live node's `allKnobs()` and button scripts.

## Workflow
### CurveTool (executable)
```python
ct = nuke.createNode("CurveTool", 'operation 0 ROI {0 0 input.width input.height} Layer rgba', False)
nuke.executeMultiple([ct], ([1001, 1100, 1],))
crop = nuke.createNode("Crop", "label AutoCrop", False)
crop['box'].copyAnimations(ct['autocropdata'].animations())
crop['indicators'].setValue(1)
nuke.delete(ct)
```
- `nukescripts.autocrop(first, last, inc, layer)` does this on selected nodes.
- `operation` values: `['Auto Crop', 'Avg Intensities', 'Exposure Difference', 'Max Luma Pixel']`; set by label. `ROI` is xyrt; `ct['resetROI'].execute()` resets it to the input; a flicker patch is `ct['ROI'].setValue((900, 500, 1100, 700))`.
- Results (animated): `autocropdata` BBox, `intensitydata` AColor, `maxlumapixdata` / `minlumapixdata` XY (plus `...value` knobs). Read `ct['intensitydata'].valueAt(f)`; link with `copyAnimations` or `CurveTool1.intensitydata`. The `Go!` button is `execute_panel this`.
- Live-verified: Constant color 0.2/0.4/0.6/1 set per component, Avg Intensities, ROI (0,0,16,16), `nuke.execute(ct, 1, 2)`: `intensitydata.valueAt(1)` and `valueAt(2)` = [0.2, 0.4, 0.6, 1.0]. Set Constant color per index, not via a bracket-list constructor string.
- Use: drive a Grade `multiply` from `intensitydata` to match flicker, or animate a Crop from Auto Crop.

### MatchGrade (NukeX)
Knobs: `matchGradeTask`, `analysisType` (Analyze Reference Frames / Auto-analyze Per Frame), `sourceRefFrames`, `targetRefFrames` with buttons `addSourceRefFrame`, `addTargetRefFrame` (and delete variants), `transform` (3D LUT / CDL), `prelut`, `lutres`, `iterations`, `analyzeRefFrames`; CDL results `slope`, `offset`, `power`, `saturation`. Confirm the button type in the live node before choosing `.execute()` vs `nuke.execute`.
```python
mg.setInput(0, source); mg.setInput(1, target)
mg['analysisType'].setValue('Analyze Reference Frames')
nuke.frame(1042); mg['addSourceRefFrame'].execute(); mg['addTargetRefFrame'].execute()
mg['analyzeRefFrames'].execute()
```
Per-frame mode needs no button. CDL results are meaningful only with `transform` CDL.

### BlinkScript
`b['kernelSource'].setValue(src); b['recompile'].execute()`. Other knobs: `kernelSourceFile`, `gpuName`, `useGPUIfAvailable`, `vectorize`. Compile errors appear in the editor and Script Editor output; compare the kernel's parameters/outputs after recompile with what the source declares. The kernel runs at render time.

### SmartVector
Knobs `vectorDetailReg`, `strengthReg`, `matteChannel`, `output`, `flickerCompensation`, button `export_write` (creates a Write with suitable EXR settings). Create it, set `file`, execute that Write over the shot range:
```python
sv['export_write'].execute()
w = nuke.selectedNode()
w['file'].setValue('/shots/sh010/smartvec/sh010_sv.%04d.exr')
nuke.execute(w, 1001, 1100, 1)
```

## Verify
- Compare each result with the expected value from the known input (CurveTool on a flat color must return that color on every executed frame) and confirm keys exist for every executed frame. Zero is a legitimate result for a black input.
- Re-run after changing input, ROI or range; old values stay otherwise.

## Pitfalls
- `nuke.execute` on a non-executable node (Merge, Grade) raises; use the node's button or just render.
- Replacing a CurveTool with an expression, or hand-typing analysis results, fakes a measurement.
- Render-only nodes need no analysis step.

## Sources
- Shipped `/opt/Nuke17.1v1/plugins/nukescripts/crop.py`, `toolbars.py`.
- NDK executable: `/opt/Nuke17.1v1/Documentation/NDKDevGuide/split-and-execute/executable.html`.
- Foundry Nuke 17.1 reference: image_nodes/curvetool.html, color_nodes/matchgrade.html, other_nodes/blinkscript.html, time_nodes/smartvector.html.
