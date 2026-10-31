---
id: "topics/projection-bake"
kind: "topic"
title: "Calculating PointsTo3D and baking Reconcile3D from Python"
category: "camera-tracking"
summary: "PointsTo3D Calculate and Reconcile3D create keyframes are unnamed Script_Knobs whose Tcl is execute_panel this; script them with nuke.execute on the node and read point3d, output and outputxyz."
aliases: ["PointsTo3D calculate", "Reconcile3D bake", "create keyframes", "point3d python", "reconcile 3D to 2D"]
tags: ["pointsto3d", "reconcile3d", "execute", "bake", "python", "point3d"]
requires: ["topics/camera-tracking"]
related: ["topics/analysis-python", "topics/camera-projection", "topics/matchmove"]
nodes: ["PointsTo3D", "Reconcile3D"]
version: "Nuke 17.1 live-probed knob names and button scripts (NukeX/Studio). Reconcile3D nuke.execute bake verified live; PointsTo3D nuke.execute not yet recorded."
source_ids: ["foundry-17.1"]
---
# Calculating PointsTo3D and baking Reconcile3D from Python

## Applicability
Use to compute a 3D point from tracked 2D parallax (PointsTo3D) or bake a 3D point's screen position over a range (Reconcile3D), with a solved camera connected.

## Workflow
Buttons are unnamed `Script_Knob`s (`name()` is empty), so `node['Calculate']` fails. Both compute buttons run Tcl `execute_panel this`, i.e. the dialog form of `nuke.execute`; call it directly. Both nodes also carry `beforeRender` / `afterRender` callbacks.
- PointsTo3D: the three `set frame` buttons are `knob ref_timeA [frame]` (B, C alike), so set the knobs directly. `generate axis` (`gen_axis`) copies `point3d` into an Axis.
```python
p = nuke.createNode("PointsTo3D", "", False)
p.setInput(0, plate); p.setInput(1, cam)
p['ref_timeA'].setValue(1001); p['ref_timeB'].setValue(1040); p['ref_timeC'].setValue(1080)
# set pointA/B/C to the same feature in each of those frames, and cameraMovType
nuke.execute(p, 1001, 1001)
xyz = p['point3d'].value()          # lowercase; 2D result in point2d
```
- Reconcile3D: knobs `point` (3D input), `calc_output`, `output` (XY), `outputxyz`, `track`, `offset`, `apply_transform`, `stabilize`. Bake with:
```python
nuke.execute(rec, 1001, 1100, 1)
xy = [rec['output'].valueAt(f) for f in (1001, 1050, 1100)]
```

## Verify
- Compare with known data: project `point3d` back through the same camera and compare to the tracked 2D point on the A/B/C frames; Reconcile3D `outputxyz` should equal `point` transformed by the optional `axis` input; `output` is its camera-projected image position.
- Reconcile3D verified live: 2048x1556 Constant on input 0, default Camera on input 1, `point` (0, 0, -10), `nuke.execute(rc, 1, 2)` gives `output.valueAt(1)` and `valueAt(2)` = [1024, 778] (image centre) and `output.isAnimated()` is True.
- Confirm keys exist at each executed frame. Zero is legitimate only when the true result is zero.

## Pitfalls
- PointsTo3D needs real camera parallax between ref frames and the same feature in all three.
- Do not create keys by script as a substitute for the execute; failed bake means report it.
- The output knob name is `point3d` (lowercase), though docs spell it otherwise.

## Sources
- Live Nuke 17.1 knob list and Script_Knob values for PointsTo3D and Reconcile3D.
- Foundry Nuke 17.1: reference_guide/transform_nodes/pointsto3d.html and reconcile3d.html.
