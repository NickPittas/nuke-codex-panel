---
id: "topics/viewer-sampling"
kind: "topic"
title: "Viewer context and pixel sampling"
category: "interface"
summary: "Python recipe: read which node the Viewer shows (activeViewer, activeInput, input), its ROI in image pixels, then measure scene values with Node.sample; keeps screenshot/display colour apart from samples; knob values after manual picks."
aliases: ["activeViewer", "activeInput", "sample pixel", "pixel value", "read pixel", "colour picker", "color picker", "viewer roi", "Node.sample", "pixel info", "ctrl click viewer", "sample rgb", "image coordinates", "viewer process", "position pass", "XYZ_Knob", "XY_Knob"]
tags: ["viewer", "sample", "roi", "pixel", "python", "measurement", "picker"]
requires: ["fundamentals/coordinates", "fundamentals/color-spaces", "fundamentals/channels-data"]
related: ["nodes/viewer", "topics/channels", "topics/tracker", "topics/color-management-correction"]
nodes: ["Viewer"]
version: "Nuke 17.1 Python API reference (installed docs); source-verified, not runtime verified. Check installed build and licence."
source_ids: ["foundry-17.1"]
---
# Viewer context and pixel sampling

## Applicability
Use when a request depends on what the Viewer currently shows or on a measured pixel/region value: "sample here", "what is the colour at ...", "check the area I framed", "I just picked a point/colour". The Python API gives the Viewer window, its input and ROI, and `Node.sample`; it documents no cursor-position function, so never invent one. If the user needs an exact point, ask for or compute image-pixel coordinates; do not guess from a screenshot.

## Workflow
### 1. Find what the Viewer shows
```python
win = nuke.activeViewer()                 # ViewerWindow (UI panel), not the Viewer node; may be None headless
vnode = win.node()                        # the Viewer node
idx = win.activeInput()                   # primary input index; int, or None if no input active
src = vnode.input(idx) if idx is not None else None   # node actually displayed
wipe = win.activeInput(True)              # secondary (wipe) input index, or None
print(vnode.name(), idx, src.name() if src else None, win.view(), nuke.frame())
```
`activeInput` lives on the ViewerWindow, not the Viewer node. Record node, input, frame and view with any result. `win.activateInput(i)` switches the displayed input.

### 2. Read the ROI in image pixels
```python
roi = vnode.roi()             # dict with keys x, y, r, t (pixel space), or None without a window
on = vnode.roiEnabled()       # bool, or None without a window
```
This is the box the user framed (x,y bottom-left, r,t top-right; see fundamentals/coordinates). Check `on` before treating it as intentional. `vnode.setRoi({"x":..,"y":..,"r":..,"t":..})` sets it.

### 3. Sample scene values
`Node.sample(c, x, y, dx, dy, frame)`: `c` channel name (e.g. `rgba.red`); `x,y` centre in image pixels; `dx,dy` optional area size (omitted: the exact value of the pixel containing x,y, "impulse"; sizes below 1 give the same cubic-filtered result); `frame` optional frame. Integers are pixel corners: add .5 to hit a pixel centre. Returns one float per channel call; the image is computed, so avoid it in expressions.

Concrete RGB pixel at (960, 540) of the displayed input, then the ROI average:
```python
src = nuke.activeViewer().node().input(nuke.activeViewer().activeInput())
rgb = [src.sample(c, 960.5, 540.5) for c in ("rgba.red", "rgba.green", "rgba.blue")]
roi = nuke.activeViewer().node().roi()
cx, cy = (roi["x"] + roi["r"]) / 2.0, (roi["y"] + roi["t"]) / 2.0
avg = [src.sample(c, cx, cy, roi["r"] - roi["x"], roi["t"] - roi["y"]) for c in ("rgba.red", "rgba.green", "rgba.blue")]
print(rgb, avg)
```
Check names first: `src.channels()` (list of `layer.channel`). Another frame: pass `frame=` (documented) or set `nuke.frame(n)` before sampling and restore it. Sample the node whose output you care about (a node before the Viewer, not the Viewer itself). For Deep images use `deepSample`/`deepSampleCount`.

### 4. Screenshot vs measurement
A screenshot or Viewer capture is written through the Viewer pipeline (`viewerProcess`, gain, gamma, input process): display-referred appearance. `Node.sample` returns the values computed at the sampled node, before the Viewer's display steps (scene values; floats can exceed 1 or be negative). They differ by design; never compare or "correct" one with the other. Use screenshots to judge looks and samples to measure; to inspect the display transform read `vnode["viewerProcess"].value()`, `vnode["gain"].value()`, `vnode["gamma"].value()`.

### Detail inspection with the panel tools
Use the panel's native Viewer framing rather than adding QC Crop/Reformat nodes just to inspect a small area. `nuke_action` `view`/`render` and `capture_nuke_screenshot(target="viewer")` accept `zoom` (a percentage such as `100`, or `"fit"`), `center=[x,y]`, or `region=[x0,y0,x1,y1]`. These are source-image coordinates with a bottom-left origin; do not use screenshot coordinates. `region` cannot be combined with `zoom` or `center`.

For example, `capture_nuke_screenshot(target="viewer", frame=1, region=[3345,1021,3745,1421])` frames that image area in the existing Viewer. It returns the Viewer-sized image, not an exact region-sized raster, and may show surrounding context. Read the returned zoom and requested-center metadata. Framing persists, while temporary render settings are restored. For tracked paint, use the tracked location at each requested frame; a fixed region does not follow the track. `nuke.zoom()` controls the Node Graph, not this Viewer framing.

### 5. After a manual pick or point operation
The user's pick lands in knobs on a node. Find it (selected node, `nuke.selectedNode()`, or known name), then read it: `k = n["knobname"]; k.Class(); k.value()` (array, colour, XY and XYZ knobs: `k.value(i)` per index; whole array: `[k.getValue(i) for i in range(k.arraySize())]`, since `k.array()` is invalid for animated or ValueProvider-backed knobs). A colour or position in a knob is node data, not a pixel sample; to confirm it, sample the same coordinates. Animated knobs or a specified frame: `k.valueAt(frame, i)`.

### 6. Position/XYZ passes
Do not guess channel names. List candidates: `sorted({c.split(".")[0] for c in src.channels()})`, then `[c for c in src.channels() if c.startswith("<layer>.")]` and sample the names found. Position data is non-colour (see fundamentals/channels-data); values are whatever coordinate space the renderer wrote, not Nuke world units unless verified.

## Verify
- Re-read `nuke.frame()`, input and `roi()` just before sampling; the user may have moved them.
- Sample a known reference (Constant, grey card) to confirm the expected value and the .5 pixel-centre convention.
- Check coordinates fall inside `src.bbox()` and the format before trusting a value; do not assume what lies outside the bbox.
- Report channel, coordinates, area, frame and which node was sampled.

## Pitfalls
- Confusing ViewerWindow (`nuke.activeViewer()`) with the Viewer node; calling `activeInput` on the node fails.
- `roi()`/`roiEnabled()` are None when the Viewer has no window; `activeViewer()` can be None.
- Treating screenshot pixel positions as image coordinates (zoom, pan, pixel aspect, proxy) or its colours as scene values.
- Assuming `rgba.*` exists; masks and data layers use other names; verify with `channels()`.
- One-pixel `sample` without .5 lands on a corner; averaged areas are filtered, not exact box means.
- Treating XY/XYZ knob values as image channels, or sampling a vector/position pass after filtering/transforms without checking.

## Sources
- nuke.activeViewer: /opt/Nuke17.1v1/Documentation/PythonDevGuide/Nuke/_autosummary/nuke.activeViewer.html
- nuke.ViewerWindow (activeInput, activateInput, node, view): .../nuke.ViewerWindow.html
- nuke.Viewer (roi, roiEnabled, setRoi, channels): .../nuke.Viewer.html
- nuke.Node (sample, deepSample, input, channels): .../nuke.Node.html; deprecated module form .../nuke.sample.html
- nuke.XY_Knob / nuke.XYZ_Knob: .../nuke.XY_Knob.html, .../nuke.XYZ_Knob.html
- Viewer node reference: https://learn.foundry.com/nuke/17.1/content/reference_guide/image_nodes/viewer.html
