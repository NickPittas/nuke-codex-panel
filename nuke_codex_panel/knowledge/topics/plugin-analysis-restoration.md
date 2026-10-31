---
id: "topics/plugin-analysis-restoration"
kind: "topic"
title: "FurnaceCore analysis nodes: F_Align, F_Steadiness, F_ReGrain, F_WireRemoval (native Python)"
category: "tracking-warping-retiming"
summary: "Run FurnaceCore analysis from Python: F_Align and F_Steadiness GME analyse/clear/range with corner-pin readback, F_ReGrain grain analysis, F_WireRemoval on-screen wire set-up and tracking buttons. Button vs render behaviour, readbacks and licence caveats. Source-verified, not runtime-verified."
aliases: ["furnacecore", "f_align", "f_steadiness", "f_regrain", "f_wireremoval", "furnace analyse", "stabilise shot", "align two clips", "add grain", "remove wire", "wire removal tracker"]
tags: ["furnacecore", "stabilise", "align", "grain", "wire-removal", "script-knob", "analysis"]
requires: ["fundamentals/quality-safeguards", "fundamentals/time-sampling", "fundamentals/coordinates"]
related: ["topics/rig-removal", "topics/tracker", "topics/plugin-analysis-caravr", "topics/plugin-analysis-stereo"]
nodes: ["F_Align", "F_Steadiness", "F_ReGrain", "F_WireRemoval", "F_RigRemoval"]
version: "Nuke 17.1 HTML reference (furnacecore_nodes) and installed F_Furnace.ofx bundle; FurnaceCore needs NukeX/Studio licence."
source_ids: ["foundry-17.1"]
---
# FurnaceCore analysis nodes: F_Align, F_Steadiness, F_ReGrain, F_WireRemoval (native Python)

## Applicability
These FurnaceCore OFX nodes have explicit analysis or tracking buttons whose results become keyframed knobs. F_RigRemoval and F_DeFlicker2 have no analysis button (they compute while rendering), so they need only normal knob setting and Viewer review (topics/rig-removal).

Status: knob names and labels come from the installed HTML (`furnacecore_nodes/`); `/opt/Nuke17.1v1/plugins/F_Furnace.ofx.bundle` contains F_Align, F_Steadiness, F_ReGrain and F_WireRemoval. Not run in Nuke; licence and render-farm/headless behaviour are unverified.

## Workflow
### Fire buttons
```python
import nuke
def press(n, k):
    kn = n[k]; print(n.name(), k, kn.Class())   # 'Script'/'PyScript' = callback; 'Render' would be a render over a frame range
    try: kn.execute()                          # blocking; GUI session assumed: analysis updates timeline and Viewer when renderOn is True
    except Exception as e: return "%s.%s FAILED: %s" % (n.name(), k, e)
def corner_keys(n):   # readback: corner-pin keys written by analysis
    return {k: len(n[k].animation(0).keys()) if n[k].isAnimated() else 0 for k in ("pinBL", "pinBR", "pinTL", "pinTR")}
```
Enumeration values are UI labels; check `n[k].values()`. A silent return proves nothing: read keys and look at the Viewer.

### F_Align (source aligned to a reference)
```python
a = nuke.nodes.F_Align()
a.setInput(0, ref); a.setInput(1, src)          # docs list Ref then Src: confirm which input accepts which in the graph
a["range"].setValue("Specified Range"); a["start"].setValue(0)                          # Furnace start/stop are zero-based per the lockFrame note; confirm against the timeline
a["stop"].setValue(100)
a["rotate"].setValue(True); a["translate"].setValue(True); a["scale"].setValue(False); a["perspective"].setValue(False)
a["renderOn"].setValue(False)                   # faster; True redraws each analysed frame
print(press(a, "analyse")); print(corner_keys(a))
```
Use `Current Frame` to redo one bad frame; `clear` deletes all pin keys before a clean re-analysis; `invert` applies the inverse pin at render. `regionBL`/`regionTR` bound the analysed area (put it on stable features). Interrupting keeps keys already calculated. `accuracy`/`filtering` are tuning knobs.

### F_Steadiness (single clip)
```python
s = nuke.nodes.F_Steadiness(); s.setInput(0, src)
s["mode"].setValue("Smooth"); s["smooth"].setValue(10)      # or Incremental Lock / Absolute Lock with lockFrame
s["range"].setValue("Source Clip Range"); s["renderOn"].setValue(False)
print(press(s, "analyse")); print(corner_keys(s))
s["autoScale"].setValue(1)                      # 1 fills black edges by scaling up
```
Lock modes: lock frame 0 is NukeX frame 1, so lock on viewer frame 3 means `lockFrame`=2. Placing the analysis box on the area to hold is recommended. The plug-in description warns Incremental Lock does not work on a render farm; analyse locally. Range options here are only Specified and Source Clip.

### F_ReGrain
Only From Grain Clip uses analysis; Preset Stock needs no button.
```python
g = nuke.nodes.F_ReGrain()
g.setInput(0, grain_clip); g.setInput(1, src)    # docs list Grain then Src; verify connections
g["grainType"].setValue("From Grain Clip")
g["regionBL"].setValue([100, 100]); g["regionTR"].setValue([300, 300])   # detail-free grain-only area
g["frame"].setValue(1); g["grainColourSpace"].setValue("sRGB")
print(press(g, "analyse"))                       # also after replacing the grain clip with the same region
g["output"].setValue("Grain Plate")              # test image; switch to "Result" after checking
```
`useResponse` enables `sample` (accumulates on each press) and `reset`; `amount`, `size`, per-channel `process*`/`*Amount`/`*Size` and gains tune the result.

### F_WireRemoval (interactive tracker)
```python
w = nuke.nodes.F_WireRemoval(); w.setInput(1, src)   # docs list CleanPlate then Source; verify which index is Source; CleanPlate optional
w["output"].setValue("Source"); w["showUI"].setValue(True); w["wireType"].setValue("Three Points")
for k, xy in (("point1", [200, 100]), ("point3", [400, 300]), ("point5", [600, 500])):
    w[k].setValue(xy)                           # place on the wire at the current frame
root = nuke.root(); root["frame"].setValue(1); press(w, "setUserKeyFrame")
w["range"].setValue("Source Clip Range"); press(w, "smartTrack")   # or stepFwd/trackFwd/trackBwd
w["repairMethod"].setValue("Spatial"); w["output"].setValue("Repair")
```
Other buttons: `snapToWire`, `deleteTrackKey*`, `deleteAllTrackKeys`, `deleteAll`, `deleteUserKeyFrame`. `Clean Plate` repair needs the CleanPlate input. Check start/end, width knobs (`startWidth`, `endWidth`, `overallWidth`) and `Repair Matted` or `Wire Matte` for downstream paint.

## Verify
- `corner_keys` is nonzero for F_Align/F_Steadiness over the analysed range; pin knobs differ per frame.
- Wipe/play: Align holds features; Steadiness removes unwanted jitter without a visible crop edge pop; ReGrain `Grain Plate` inner patch indistinguishable from outer; wire repair holds on every frame, including motion-blurred frames.

## Pitfalls
- Button `execute()` may be GUI-bound: analysis and wire tracking operate with the Viewer/timeline; headless is unverified.
- Re-analysis overwrites or conflicts with old keys: run `clear` first unless intentionally filling a range.
- Frame numbering is offset by one for lock-frame fields.
- Wire points left from another frame give a bad track; set user key frames on difficult frames.
- F_RigRemoval/F_DeFlicker2 have no run button: do not search for one.

## Sources
- Foundry 17.1 reference: furnacecore_nodes/f_align, f_steadiness, f_regrain, f_wireremoval (local HTML under /opt/Nuke17.1v1/Documentation); installed F_Furnace.ofx plug-in description for F_Steadiness farm warning.
