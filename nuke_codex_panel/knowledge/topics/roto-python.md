---
id: "topics/roto-python"
kind: "topic"
title: "Roto and RotoPaint through Python"
category: "tracking-warping-retiming"
summary: "Runnable Python for Roto/RotoPaint curves: read the tree, create Bezier shapes, edit points and tangents, key points and transforms, read/write paint-stroke brush, clone-source and lifetime attributes, and what the API cannot do."
aliases: ["roto python", "curves knob", "rotopaint python", "create bezier", "shape control point", "tangent", "feather", "paint stroke", "clone source", "lifetime", "AnimAttributes", "AnimControlPoint", "nuke.rotopaint", "keyframe roto shape"]
tags: ["roto", "rotopaint", "python", "shape", "stroke", "animation", "paint"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["topics/rotoscoping-masking", "topics/spline-grid-warp", "topics/warp-operations", "topics/planar-tracking", "nodes/roto", "nodes/rotopaint"]
nodes: ["Roto", "RotoPaint", "PlanarTracker"]
version: "Nuke 17.1v1 installed Python API docs (nuke.rotopaint, nuke.curvelib); source-verified, not runtime verified. Check installed build."
source_ids: ["foundry-17.1"]
---
# Roto and RotoPaint through Python

## Applicability
Use when a request needs shapes or strokes created or edited by script: place a Bezier from measured points, move a point or tangent, key a point or shape transform, bake a shape path to a Tracker, or read or change brush, clone-source and lifetime attributes of a paint stroke. Drawing freehand by eye, choosing Viewer tool modes and interactive Layer/Shape selection tools remain manual. All curves live in one knob, `curves`, of Roto, RotoPaint (and SplineWarp3, same API).

## Workflow
### Clone-paint cleanup strategy
Remove an object in two stages, never one big distant stamp. Stage 1, perimeter: start at the edge from the sides whose lighting suits, with small overlapping strokes sourced from NEARBY on the matching side (above for top edge, below for bottom, left for left, right for right); then work inward, overlapping earlier strokes. If sides are lit differently, use only top+bottom, or the cleanest side(s), not all four mechanically. Match illumination and texture; many small local strokes beat one big patch. Review close and wide on clean Viewer frames, no overlays, for brightness lumps, gradient breaks, seams, smear, repetition, residual object. Object gone is not finished; fix and re-view.
Keep the default clone source; do not switch it to background (`bg`), so later strokes can sample already-painted areas.
Prerequisites: node exists, you hold its `curves` knob `K`, Python 3. Coordinates are image pixels in the node's format. Tangents and feather points are RELATIVE offsets (tangents from the center, feather tangents from the feather center). Call `K.changed()` after edits.
```python
import nuke, nuke.rotopaint as rp
n = nuke.toNode('Roto1') or nuke.createNode('Roto')
K = n['curves']
def walk(layer, d=0):
    for e in layer:                       # Layer yields Shape/Stroke/Layer
        print('  '*d + e.name, type(e).__name__)
        if isinstance(e, rp.Layer): walk(e, d+1)
walk(K.rootLayer)                          # also K.toElement('Layer1/Bezier1')
```
Create a Bezier:
```python
shape = rp.Shape(K)
for xy in [(100,100), (300,100), (300,300), (100,300)]:
    shape.append(xy)
shape.name = 'hero_mask'
K.rootLayer.append(shape); K.changed()
```
Edit a point and its tangents (no frame arg = constant value; use keys below for animation):
```python
p = shape[0]
p.center = rp.AnimControlPoint(120.0, 90.0, 1.0)
p.leftTangent = (-20.0, 0.0, 1.0); p.rightTangent = (20.0, 0.0, 1.0)
p.featherCenter = (0.0, 10.0, 1.0)
shape.insert(2, rp.ShapeControlPoint(K))   # remove(i) removes point with its tangents/feather
K.changed()
```
Animate (all times are float frames):
```python
p.center.addPositionKey(10.0, (130.0, 95.0, 1.0))
p.center.getPositionAnimCurve(0).addKey(20.0, 150.0)
print(p.center.getControlPointKeyTimes(), p.center.getPosition(10.0))
tr = shape.getTransform()                  # AnimCTransform
tr.addTranslationKey(10.0, 5.0, 8.0, 1.0)  # also addRotationKey/addScaleKey/addSkewXKey/addPivotPointKey (time,x,y,pressure)
shape.setVisible(1.0, True); K.changed()
```
Evaluate or bake: `c = shape.evaluate(0, f)` (0 main, 1 feather offset) then `c.getPoint(t)` (t 0..1); `stroke.evaluate(f)` for strokes. Long frame loops writing knobs (e.g. Tracker `setValueAt`) must run in a thread using `nuke.executeInMainThreadWithResult`, else Nuke freezes.

### Paint strokes
Strokes are `rp.Stroke(K)` with `AnimControlPoint` points; brush, clone source and lifetime are curves in `getAttributes()`, not node knobs. Constant names documented on `rp.AnimAttributes`: kBrushSizeAttribute, kBrushSpacingAttribute, kBrushTypeAttribute, kHardnessAttribute, kOpacityAttribute, kBuildUpAttribute, kSourceAttribute, kSourceTranslateXAttribute/YAttribute, kSourceRotateAttribute, kSourceScaleX/YAttribute, kSourceSkewX/YAttribute, kSourcePivotPointX/YAttribute, kSourceTimeOffsetAttribute, kSourceTimeOffsetTypeAttribute, kLifeTimeTypeAttribute, kLifeTimeMAttribute, kLifeTimeNAttribute, kWriteOnStartAttribute, kWriteOnEndAttribute, kVisibleAttribute.
```python
rn = nuke.toNode('RotoPaint1') or nuke.createNode('RotoPaint')
RK = rn['curves']
s = rp.Stroke(RK)
for xy in [(200,200), (260,230), (320,200)]: s.append(rp.AnimControlPoint(*xy))
s.name = 'clone_fix'
RK.rootLayer.append(s); RK.changed()
a = s.getAttributes()
A = rp.AnimAttributes
print(a.getValue(1.0, A.kBrushSizeAttribute), a.getValue(1.0, A.kSourceTimeOffsetAttribute),
      a.getValue(1.0, A.kLifeTimeTypeAttribute))      # read what the stroke actually holds
a.set(1.0, A.kOpacityAttribute, 0.8)                 # set(time, attr, value) keys; omit time for constant
RK.changed()
```
Verified in native 17.1 (RotoPaint on a 4096x2160 plate): `AnimAttributes` has NO `setValue`; edit an existing stroke by name with `a.set(time, attr, value)` (e.g. `s = [e for e in RK.rootLayer if e.name == 'clone_fix'][0]; a = s.getAttributes(); a.set(1.0, A.kSourceTranslateXAttribute, -300.0); RK.changed()`), then read back with `a.getValue(1.0, attr)`. Encodings: `kSourceAttribute` color=0, bg=2 (toolbar `toolbar_paint_source`: `color, fg, bg, bg 1, bg 2, bg 3`); `kLifeTimeTypeAttribute` all=0, from start=1, single=2, to end=3, range=4; for range M=end frame, N=start frame (`a.set(1.0, A.kLifeTimeTypeAttribute, 4.0); a.set(1.0, A.kLifeTimeMAttribute, 15.0); a.set(1.0, A.kLifeTimeNAttribute, 5.0)` = frames 5-15; out-of-range frames show the plate untouched). New strokes inherit toolbar knobs set before creation (`toolbar_paint_source`, `toolbar_paint_color`, `toolbar_brush_size`, `toolbar_brush_hardness`, `toolbar_source_transform_translate`, `toolbar_lifetime_type/start/end`), so set them first. Clone offset = kSourceTranslateX/Y (source = 'bg'); `a.set(1.0, A.kOpacityAttribute, 0.0)` hides a stroke. Animate with `t = s.getTransform(); t.addTranslationKey(1.0, 0.0, 0.0, 1.0); t.addTranslationKey(20.0, 150.0, 0.0, 1.0)`; read `t.evaluate(f, 'default').translation`. A shape POINT needs a start key, `p.center.addPositionKey(1.0, (x, y, 1.0))`, before the second. Repeated `nuke.sample` over a RotoPaint with a range-lifetime stroke while changing frames hung/crashed native Nuke: view frames through the Viewer.

## Verify
- Re-read through the API (`walk`, `getPosition`, `getValue`, `len(shape)`, key times); do not rely on `toScript()` text as a contract.
- Render or view `rotopaint`/`roto` alpha at a keyed and an in-between frame; the Viewer may need a refresh after scripted edits.

## Pitfalls
- Unsupported or undocumented: no Python call to draw by mouse; no stroke "render" button; no documented way to invoke PlanarTracker tracking (see topics/warp-operations).
- Forgetting `K.changed()`; treating tangents as absolute; running frame loops with knob writes on the main thread; inventing nonexistent methods such as `addPoint` on Shape (the documented call is `append`).
- Replacing native shapes with expressions or Grid/Checkerboard nodes; use real Roto shapes.

## Sources
- Nuke 17.1v1 Python Dev Guide rotopaint.html and _autosummary nuke.rotopaint.{Shape,Stroke,Layer,ShapeControlPoint,AnimControlPoint,AnimAttributes,AnimCTransform}: /opt/Nuke17.1v1/Documentation/PythonDevGuide/Nuke/
- Roto and RotoPaint: https://learn.foundry.com/nuke/17.1/content/reference_guide/draw_nodes/roto.html
