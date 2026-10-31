---
id: "topics/plugin-analysis-caravr"
kind: "topic"
title: "CaraVR rig solve, stitch and latlong track (native Python)"
category: "tracking-warping-retiming"
summary: "Operate CaraVR 2.1 analysis nodes from Python: C_CameraSolver rig match/solve/refine/export, C_GlobalWarp constraints, C_Stitcher keys and C_Tracker auto-track/solve/export, with button firing, readbacks and licence caveats. Source-verified, not runtime-verified."
aliases: ["caravr", "c_camerasolver", "c_stitcher", "c_globalwarp", "c_tracker", "360 stitch", "vr rig solve", "latlong stabilise", "panorama stitch", "multi camera rig"]
tags: ["caravr", "360", "stitch", "rig-solve", "latlong", "script-knob", "analysis"]
requires: ["fundamentals/quality-safeguards", "fundamentals/time-sampling", "fundamentals/coordinates"]
related: ["topics/camera-tracking", "topics/tracker", "topics/plugin-analysis-stereo", "topics/plugin-analysis-restoration", "topics/lens-distortion"]
nodes: ["C_CameraSolver", "C_Stitcher", "C_GlobalWarp", "C_Tracker", "C_ColourMatcher", "C_SphericalTransform"]
version: "Nuke 17.1 HTML reference (cara_vr2_1) and installed plugins/caravr scripts; check installed node generation and licence."
source_ids: ["foundry-17.1"]
---
# CaraVR rig solve, stitch and latlong track (native Python)

## Applicability
Multi-camera 360/VR rigs: solve camera geometry (C_CameraSolver), optionally line up overlaps (C_GlobalWarp), stitch to latlong (C_Stitcher) and stabilise or match-move in latlong space (C_Tracker). Not ordinary parameter nodes: each has run/solve buttons whose results are stored in knobs or exported nodes.

Status: knob names below are copied from the installed 17.1 HTML and scripts; not run in Nuke. Docs also describe CaraVR 1.0/2.0 generations, but the installed bundle (`/opt/Nuke17.1v1/plugins/caravr`) is 2.1 only, and its `menu.py` creates nodes as `C_CameraSolver2_1`, `C_Tracker2_1`, `C_Stitcher2_1`, `C_GlobalWarp2_1`, `C_ColourMatcher2_1` (doc titles drop the suffix). CaraVR is licence-gated (NukeX/Studio); a failing `createNode` means unavailable, so stop and report.

## Workflow
### Fire buttons and read back
```python
import nuke
def press(n, k):
    kn = n[k]; print(n.name(), k, kn.Class())   # 'Script'/'PyScript' = button callback; 'Render' = starts a render over a frame range
    try: kn.execute()                          # blocks; may open progress/dialogs, assume GUI Nuke
    except Exception as e: return "%s.%s FAILED: %s" % (n.name(), k, e)
```
A silent return proves nothing: always read the result knob, then Viewer overlay. Enumeration values are the UI labels; check `n[k].values()` before `setValue`.

### 1. C_CameraSolver
```python
reads = [nuke.toNode(x) for x in ("cam1", "cam2", "cam3")]   # pre-synchronised: no auto-sync
s = nuke.nodes.C_CameraSolver2_1()
for i, r in enumerate(reads): s.setInput(i, r)    # a new input appears per connection
print(s["numCameras"].value())                     # must equal len(reads)
s["rigPreset"].setValue("Custom")                  # preset rig: pick it, then press(s, "setupRig")
s["setCameras"].setValue(True)                     # unlocks the global lens knobs
s["rigLensType"].setValue("Fisheye"); s["rigFocalLength"].setValue(8)
s["rigSensorSize"].setValue([36, 24])
s["layoutType"].setValue("Spherical Layout"); s["orientationType"].setValue("Optimize per Camera")
s["focalLengthType"].setValue("Optimize Single"); s["lensDistortionType"].setValue("Optimize Single")
s["matchType"].setValue("Spherical")               # 'Rectified' default; FOV>180 needs Spherical
s["keyStep"].setValue(30)                          # default 500 gives one key on short clips
for k in ("addAllAnalysisKeys", "matchCameras", "solveCameras"): print(press(s, k))
print(s["solverRMSError"].value())                 # 0 = not solved yet, not perfect
```
Then lower `maxRMSEThreshold`, `press(s,"rejectMatches")`, `press(s,"refineCameras")`, re-read `solverRMSError`. `resetCameras` discards the solve; `importAllKeys` replaces existing keys. Stereo rigs: `stereoViewsInputSplitting`, `inputLeftViews`, `inputRightViews`, per-camera `outputView`. Export graph: set `exportMenu` (labels such as "Manual 2D Stitch", "Camera Ingest", "Contact Sheet"), snapshot `set(nuke.allNodes())`, `press(s,"exportButton")`, diff to find created nodes.

### 2. C_ColourMatcher then C_GlobalWarp / C_Stitcher
Chain solver -> C_GlobalWarp2_1 (optional) -> C_Stitcher2_1 (colour matching may sit between; its keys can be imported).
```python
w = nuke.createNode("C_GlobalWarp2_1"); w.setInput(0, s)
w["keyStep"].setValue(30)
for k in ("addAllAnalysisKeys", "match", "warp"): print(press(w, k))
print(w["matchError"].value(), w["warpThreshold"].value())
st = nuke.createNode("C_Stitcher2_1"); st.setInput(0, w)   # or s; needs solver metadata upstream
st["inputProjectionType"].setValue("Default (source)")
st["keyStep"].setValue(30); print(press(st, "addAllStitchKeys"))
st["blendType"].setValue("Multi-Band"); st["enableWarps"].setValue(True)
```
The docs list the same scripting name `match` for both Match and Match New, and give no names for the second Warp/Reset pair: print `w.knobs().keys()` and use only names present. Constraints (`addConstraint`, `trackConstraints`, `exportConstraints` to OneView/C_Tracker) are Viewer-drawn; draw them in the UI. C_Stitcher has no solve button: vectors compute at render, so judge it by viewing keyframes. `enableStereo`, `eyeSeparation`, `exportMenu` (STMaps/PPass) exist.

### 3. C_Tracker (latlong)
```python
t = nuke.createNode("C_Tracker2_1"); t.setInput(0, st)      # or the source latlong
t["trackRange"].setValue("Input"); t["trackingSpace"].setValue("LatLong")
t["solveType"].setValue("Auto-tracks")                       # 'User tracks' / 'Combined' need Viewer tracks
for k in ("autoTrack", "solveButton"): print(press(t, k))
print(t["solveRMSError"].value(), t["validationErrorThreshold"].value())
```
Tune `validationErrorThreshold`, `press(t,"deleteOutliers")`, re-`solveButton`. Export with `exportMenu` "C_SphericalTransform (Stabilise)" (or Match-move, or the Metadata only variants; the first menu label is misspelled in the docs, so use `values()`), then `exportButton`. `linkOutput` keeps exports linked to later solves. User tracks live in the `tracks` table knob and are normally placed in the Viewer.

## Verify
- `numCameras`, `solverRMSError`, `matchError`, `solveRMSError` are nonzero after their steps; compare to the thresholds you set.
- View `C_CameraSolver` with `cameraViewsProjectionType` Latlong, then stitched output at stitch keys and between them; look at seams, poles, ghosting.
- After `exportButton`, the diffed node set exists and cameras/transform values are linked, not baked.
- Tracker: Viewer tracks are mostly valid after `deleteOutliers`; stabilised output holds the horizon.

## Pitfalls
- Wrong class name (`C_Tracker` without `2_1`) or no licence gives a createNode error, not a bad solve.
- `execute()` reports no failure for many plugin buttons; no progress or still-zero error means it did nothing or needs the Viewer/GUI. Do not call this headless-safe; background `nuke -t` is unverified.
- Solving with unsynchronised Reads, too few keys, or Match on the wrong `matchType` yields large RMS; fix inputs rather than raising `maxRMSEThreshold`.
- Importing keys, `deleteAllAnalysisKeys`, `resetCameras` destroy work; snapshot values first and never loop-press them.
- Stereo auto-stitch needs more camera overlap than mono.
- Do not claim stitch quality from knob values alone.

## Sources
- Foundry 17.1 reference: cara_vr2_1/c_camerasolver2_1, c_globalwarp2_1, c_stitcher2_1, c_tracker2_1 (local HTML under /opt/Nuke17.1v1/Documentation).
- Installed /opt/Nuke17.1v1/plugins/caravr/menu.py (class names with 2_1).
