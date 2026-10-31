---
id: "topics/lens-calibration"
kind: "topic"
title: "Running LensDistortion2 detect and solve from Python"
category: "camera-tracking"
summary: "Scripted LensDistortion2 calibration: detect is a PyScript that calls nuke.execute on the node with FrameRanges and keyframes; solveDistortion is a script button. Exact recipe, detection settings and result knobs."
aliases: ["lens detect python", "solveDistortion", "LensDistortion2 detect", "lens calibration script", "scripted lens solve"]
tags: ["lensdistortion2", "detect", "solveDistortion", "execute", "python", "calibration"]
requires: ["topics/lens-distortion"]
related: ["topics/lens-distortion", "topics/analysis-python", "topics/camera-tracking"]
nodes: ["LensDistortion"]
version: "Nuke 17.1 live-probed knob scripts (NukeX/Studio). detect script and knob classes probed; a full detect+solve result on a real grid has not been recorded here."
source_ids: ["foundry-17.1"]
---
# Running LensDistortion2 detect and solve from Python

## Applicability
Use when the user wants the Analysis tab Detect and Solve driven by script on a grid or chart plate (see topics/lens-distortion for the comp strategy). The class is `LensDistortion2`. `detect` is a `PyScript_Knob`; `solveDistortion`, `deleteOutliers`, `resetDistortion` are `Script_Knob`s; `licenseCheckTrigger` is a PyScript.

## Workflow
The `detect` knob's own script (read live from Nuke 17.1) is the recipe:
```python
node = nuke.thisNode()
node['licenseCheckTrigger'].execute()
if bool(node['licenseCheckResult'].getValue()):
    node['preview'].setValue(0)
    keys = node['keyFrame']
    thisFrame = nuke.frame()
    if int(node['detectionFrameType'].getValue()) == 0:        # Current Frame
        keys.setKeyAt(thisFrame)
        nuke.execute(node, nuke.FrameRanges([thisFrame]))
    else:                                                       # Every N Frames
        spacing = int(node['detectionFrameSpacing'].getValue())
        frames = sorted(set(list(range(thisFrame, node.firstFrame() - 1, -spacing)) +
                            list(range(thisFrame, node.lastFrame() + 1, spacing))))
        for i in frames: keys.setKeyAt(i)
        nuke.execute(node, nuke.FrameRanges(frames))
```
So LensDistortion2 is executed with `nuke.execute`. Scripted use:
```python
ld = nuke.createNode("LensDistortion2", "", False)
ld.setInput(0, grid_read)
ld['detectionFrameType'].setValue(1)           # Every N Frames
ld['detectionFrameSpacing'].setValue(10)
nuke.frame(1001)
ld['detect'].execute()
ld['solveDistortion'].execute()
rms = ld['solveError'].value()
```
- The anchor is `nuke.frame()`; for Every N Frames it spreads both directions to the node's first/last frame.
- Result knobs: `distortionNumerator0..3`, `distortionDenominator0..3` (plus X/Y/T/U variants), `centre`, `solveError`. Tune with `detectionThreshold`, `deleteOutliers`, `deleteAllKeys`; `resetDistortion` clears the solve.
- Distortion applies at render via `output` (Undistort / Redistort / STMap). Copy the solved node and change `output`; do not re-solve.

## Verify
- Read `solveError` and a coefficient after solve and compare with their values before detect; unchanged values mean detection or solve did not run (license, no grid found).
- Keys exist on `keyFrame` for each detected frame; undistorted grid lines are straight.

## Pitfalls
- Do not type coefficients to cover a failed analysis.
- Run detect on the same format/lens as the shot plate.
- Do not re-solve the redistort node.

## Sources
- Live Nuke 17.1 `LensDistortion2` knob scripts (`detect`, button classes).
- Foundry Nuke 17.1: reference_guide/transform_nodes/lensdistortion.html; comp_environment/lens_distortion/analyzing_distortion_grid.html.
