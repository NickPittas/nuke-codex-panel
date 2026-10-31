---
id: "topics/warp-operations"
kind: "topic"
title: "SplineWarp, GridWarp and PlanarTracker operations through Python"
category: "tracking-warping-retiming"
summary: "Python for SplineWarp A/B shape assignment and defaultJoin correspondence points with readback, plus a discovery-first procedure for GridWarp3/GridWarpTracker and PlanarTracker (no documented mesh or tracking API) and an explicit list of unsupported operations."
aliases: ["splinewarp python", "setAB", "defaultJoin", "correspondence points", "gridwarp python", "gridwarptracker python", "planartracker python", "warp mesh", "grid points python", "morph python", "execute tracking", "SplineKnob"]
tags: ["warp", "splinewarp", "gridwarp", "planartracker", "python", "morph", "correspondence"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["topics/spline-grid-warp", "topics/roto-python", "topics/planar-tracking", "topics/tracker", "nodes/splinewarp", "nodes/gridwarp", "nodes/planartracker"]
nodes: ["SplineWarp", "GridWarp", "GridWarpTracker", "PlanarTracker", "Roto"]
version: "Nuke 17.1v1 installed Python API docs and plugin binaries plus a live NukeX 17.1v1 probe (node creation, knob names, scripts, SplineWarp join); tracking execution not run. Check installed build and licence."
source_ids: ["foundry-17.1"]
---
# SplineWarp, GridWarp and PlanarTracker operations through Python

## Applicability
Use when a warp or planar track must be set up or inspected by script. Documented and scriptable: SplineWarp shapes, A/B channel assignment, joining A to B with correspondence points, reading points back. No vertex/mesh API exists for GridWarp3/GridWarpTracker grids; tracking is via the nodes' own buttons, with licence checks kept. Do not guess APIs for those; follow the discovery steps and, if nothing supported is found, tell the user the manual Viewer step.

## Workflow
### SplineWarp A/B correspondence
Prerequisites: SplineWarp3 node (class name may differ; check `n.Class()`), A and B inputs connected, shapes live in `curves` (a `SplineKnob`). Coordinates are image pixels. Python 3.
```python
import nuke, nuke.splinewarp as sw
n = nuke.toNode('SplineWarp3') or nuke.createNode('SplineWarp3')
K = n['curves']                              # SplineKnob (is a CurveKnob; rootLayer, toElement work as in Roto)
def poly(name, pts):
    s = sw.Shape(K)                          # docs: Roto or SplineWarp shape
    for xy in pts: s.append(xy)
    s.name = name
    K.rootLayer.append(s)
    return s
a = poly('src_outline', [(100,100), (300,100), (300,300), (100,300)])
b = poly('dst_outline', [(110,90), (320,100), (310,320), (100,290)])
K.setAB(a, 'A'); K.setAB(b, 'B')             # 'A' or 'B' only; getAB returns 'A'|'B'|'UNDEFINED'
cp = K.defaultJoin(a, b)                     # -> CorrespondencePoints
K.changed()
print(K.getAB(a), K.getAB(b))
cp = K.getCorrespondencePoints('src_outline')  # path to the element in the tree; re-read after join
print(cp.getNumPoints())
for i in range(cp.getNumPoints()):
    print(i, cp.getPointValues(nuke.frame(), i))   # (t_src, t_dest), t in 0..1 along each curve
```
Refine a pairing: `cp.addPoint(time, t_src, t_dest)` (not animated; docs say animation must be set separately), `cp.modifyPoint(time, index, which, t)` (which 0=source, 1=dest), `cp.removePoint(index)`, `cp.reset()`, `cp.getAnimCurve(index, which)`. Call `K.changed()` after edits and read back again. Animate a shape exactly as in topics/roto-python (point `addPositionKey`, `getTransform().add*Key`). If the join result reads back empty, stop and report it; the manual route is joining the A and B shapes in the Viewer (SplineWarp Foundry docs describe the Join workflow).

### GridWarpTracker (live-probed Nuke 17.1v1)
No vertex API: `ControlPointCollection_Knob` has only generic Knob methods (`toScript`, `fromScript`, `setValue`, `getValue`, `getValueAt`, `setValueAt`...). Grid knobs: `from_base_grid`, `to_base_grid`, `from_baked_grid`, `to_adjustment1_grid`..`to_adjustment6_grid`, `to_baked_grid` (plus `triangularGrid2DKnob`, Boolean `grids_manually_moved`). `toScript()` prints a text grid (header like `1 5 5 4 1 0`, then per-point `{ {2 x y} { tangent offsets } }`); use it to snapshot/restore (`k.fromScript(text)`) a whole grid, never to hand-edit vertices or claim a mesh API. Shape grids manually in the Viewer.
Tracking buttons are PyScript_Knobs: `executeTrackToStart`, `executeTrackPrev`, `executeTrackNext`, `executeTrackToEnd`, `executeTrackToStartRange`, `executeTrackToEndRange`; Script_Knobs `clear`, `clearBwd`, `clearFwd`. The shipped `executeTrackToEnd` script runs `node['licenseCheckTrigger'].execute()`, reads `licenseCheckResult`, then requires `node.input(2)` (a SmartVector) and `node['selectionCount'].getValue() > 0` (selected grid; selecting is manual), calls `smartVectorInput.forceValidate()`, sets `executeFrom`=current frame, `executeTo`=SmartVector `lastFrame()`, `executeStep`=1, and runs `nuke.execute(node, nuke.FrameRanges([nuke.FrameRange(first, last, 1)]))`, then `nuke.frame(last)` on success. Prefer calling the shipped button so these checks are never bypassed:
```python
g = nuke.toNode('GridWarpTracker1')
print(g.input(2), g['selectionCount'].getValue())   # need SmartVector and >0 before pressing
g['executeTrackToEnd'].execute()     # nuke.message boxes appear if a check fails; read the node afterwards
print(g['to_baked_grid'].toScript()[:300])           # tracking result readback
```
Not verified: that `execute()` of this button completes tracking headless; confirm by comparing grid text before and after. Use `nuke.execute` directly only with the same checks and the knob values above.

### PlanarTracker (live-probed)
Roto-based; `nuke.nodes.PlanarTracker()` works (NukeX). Knobs: Script_Knobs `trackToStart`, `trackPrev`, `trackNext`, `trackToEnd`, `clearAll`, `clearBkwd`, `clearFwd`, `gotoReferenceFrame`, `setCurrentFrameToReferenceFrame`, `setImageSizedPlanarSurface` (their scripts read empty, handled natively; `knob.execute()` result unverified); PyScript_Knobs `trackToStartRange`, `trackToEndRange` which open a modal `nukescripts.ExecuteDialog` (frame range + direction) then write a `helper` knob vector `[first, last, direction(1/-1), executeFlag 1]`, direction pre-set at index 2. Do NOT assume writing `helper` starts tracking; verify keys appear. Range buttons need the GUI dialog; in headless or script use, ask the user to press Track.
Export buttons are PyScript_Knobs: `createPinRelative`, `createPinAbsolute`, `createPinStabilize`, `createTracker`, the `...Baked` variants (`createPinRelativeBaked`, `createPinAbsoluteBaked`, `createPinStabilizeBaked`, `createTrackerBaked`), and `createPin` (reads `createPinOptions`). These create CornerPin2D/Tracker nodes; run `plan['createPinRelativeBaked'].execute()` then find the new node and check its knobs. Add shapes via topics/roto-python (shapes sit in a PlanarTrackLayer).

## Verify
- SplineWarp: `getAB` for both shapes, `getNumPoints() > 0`, then view output at A-only, B-only, and mid-keyframes; check the warp at 100% on both ends.
- Grid/Planar: print the real knob list and values before and after; confirm key counts and a visibly tracked frame range (sample a Tracker/CornerPin output) rather than assuming a button press worked.

## Pitfalls
- Unsupported: scripting grid vertices or subdivisions; bypassing GridWarpTracker licence/SmartVector/selection checks; assuming PlanarTracker `trackToEnd` or `helper` writes run tracking; mouse-drawn joins as a documented Python call; enum values for blend/lifetime attributes.
- Names above come from a live Nuke 17.1v1 probe; still check `n.knobs()` on the user's build and licence. Module absence is not knob absence.
- Moving both source and destination; forgetting `K.changed()`; calling join before both shapes are in the tree and assigned A/B.

## Sources
- Nuke 17.1v1 Python Dev Guide: nuke.splinewarp.SplineKnob, nuke.curvelib.CorrespondencePoints, nuke.rotopaint pages: /opt/Nuke17.1v1/Documentation/PythonDevGuide/Nuke/_autosummary/
- Live Nuke 17.1v1 knob and script probe of PlanarTracker, GridWarpTracker and SplineWarp3 (sw.Shape, setAB, defaultJoin returned 4 correspondence points).
- Tracking a Plane: https://learn.foundry.com/nuke/17.1/content/comp_environment/planartracker/tracking_plane.html
