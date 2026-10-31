---
id: "topics/plugin-analysis-stereo"
kind: "topic"
title: "Ocula stereo solve and vertical alignment (native Python)"
category: "tracking-warping-retiming"
summary: "Operate Ocula 4.0 O_Solver analysis keys and feature matches, then O_VerticalAligner analysis and corner-pin/camera export, from Python with button firing, ordered prerequisites and readback limits. Source-verified from HTML only; Ocula was not found in this install."
aliases: ["ocula", "o_solver", "o_verticalaligner", "stereo alignment", "stereo camera solve", "vertical disparity", "stereo rig solve", "left right alignment"]
tags: ["ocula", "stereo", "solver", "vertical-alignment", "script-knob", "analysis"]
requires: ["fundamentals/quality-safeguards", "fundamentals/time-sampling", "fundamentals/channels-data"]
related: ["topics/plugin-analysis-caravr", "topics/camera-tracking", "topics/optical-flow-retiming"]
nodes: ["O_Solver", "O_VerticalAligner", "O_DisparityGenerator"]
version: "Nuke 17.1 HTML reference (ocula4_0, ocula_nodes 3.0); Ocula is a separate licensed plug-in and was not found under /opt/Nuke17.1v1/plugins."
source_ids: ["foundry-17.1"]
---
# Ocula stereo solve and vertical alignment (native Python)

## Applicability
Use for a stereo pair that needs its camera relationship solved (O_Solver) and then aligned (O_VerticalAligner), or whose aligned disparity needs O_Solver. The documentation is installed, but a filename search found no Ocula plug-in files under `/opt/Nuke17.1v1` (CaraVR and FurnaceCore bundles were present). So availability, licence and exact class names (`O_Solver`, possibly with a `4_0` suffix) are unverified here. Knob names below come from the Ocula 4.0 HTML (`o_solver4_0.html`, `o_verticalaligner4_0.html`); not runtime-verified. Ocula 3.0 pages differ (no `analyseSequence`/`analyseNominated`; extra `numberFeatures`, `featureThreshold`, `featureSeparation`, `alignmentMethod`).

## Workflow
### 0. Discover and fire buttons
```python
import nuke
def make(names):
    for c in names:
        try: return getattr(nuke.nodes, c)()
        except Exception: pass
    raise RuntimeError("none of %s can be created: Ocula missing or unlicensed" % (names,))
def press(n, k):
    kn = n[k]; print(n.name(), k, kn.Class())   # 'Script'/'PyScript' = callback button; 'Render' = renders a frame range
    try: kn.execute()                          # blocks; may open dialogs: assume GUI Nuke, headless unverified
    except Exception as e: return "%s.%s FAILED: %s" % (n.name(), k, e)
```
Stop and report if `make` raises. Enumeration values are UI labels; confirm with `n[k].values()`.

### 1. O_Solver (before anything that needs alignment)
Inputs: `Source` stereo pair (required), optional pre-tracked stereo `Camera`, optional `Ignore` mask.
```python
src = nuke.toNode("stereoRead")                    # must carry two views, e.g. left and right
sol = make(["O_Solver4_0", "O_Solver"]); sol.setInput(2, src)   # input order Camera, Ignore, Source per docs: verify with sol.input(2)
print(sol["viewPair"].value())                     # confirm the two views are left and right
sol["ignore"].setValue("None")                     # or Source Alpha / Mask Alpha with the Ignore input
sol["displayType"].setValue("Keyframe Matches")
press(sol, "deleteAnalysisKeys")                   # only on a fresh, intentional re-solve
root = nuke.root()
for f in (1, 50, 100):                             # keys at lens/convergence changes; one is enough for a static rig
    root["frame"].setValue(f); print(press(sol, "addAnalysisKey"))   # acts on the current frame
sol["singleSolve"].setValue(True)                  # only for rigs that do not change over time
print(sol["analysisKeyframe"].value())
```
`analyseSequence` auto-keys alignment changes but may be slow; `analyseNominated` keys the frames named in the Render dialog, so it may open a UI dialog: use manual `addAnalysisKey` in scripts. Solves between keys are interpolated. Review: `displayType` "Preview Alignment" draws aligned matches; `alignmentError` (pixels) highlights vertical errors above the threshold; `offset` exaggerates disparity. On the current frame, `resetFrame` re-analyses, `deleteAutoMatches` and `deleteUserMatches` clear matches. Matches are drawn/edited in the Viewer; no numeric RMS knob is documented, so quality is judged in the Viewer.

### 2. O_VerticalAligner (O_Solver must be upstream)
Local alignment and Fix Offset also need an upstream O_DisparityGenerator.
```python
va = make(["O_VerticalAligner4_0", "O_VerticalAligner"]); va.setInput(0, sol)
va["alignWhat"].setValue("Both Views")             # 'Left to Right' / 'Right to Left' also zoom both views if scaleToFit
va["alignmentType"].setValue("Full")               # Custom enables alignCamera/alignScale/alignShift/alignRotate/alignPerspective/alignVerticalSkew
va["localAlignment"].setValue(False)               # analyse cannot run with local alignment on
print(press(va, "analyse"))
print([va[k].value() for k in ("pinBL", "pinBR", "pinTR", "pinTL")])
print(va["transformMatrix"].toScript())            # one matrix per view, filled by analyse
press(va, "createPin")                             # or createCamera/createRig, which need a Camera on O_Solver
```
`analyse` and the Create buttons work in global methods except Vertical Skew. Pre-blur (`disparityBlurSize`) and `localCorrection` only affect Local mode. `scaleToFit`, `calculateScale`, `lockScale` fix black edges; `fixParallax`, `fixPoint`, `lockOffset` preserve parallax.

## Verify
- `analysisKeyframe` shows the keys you added; Viewer matches cover the image evenly, not clustered.
- In Preview Alignment, matches are horizontal with small vertical error at each key and between keys.
- `pinBL...pinTL` and `transformMatrix` changed from defaults after `analyse`; the created CornerPin/Camera nodes exist.
- View the aligned pair (anaglyph or wipe): features sit on the same scanlines; compare against the original.

## Pitfalls
- Absent plug-in, unlicensed install, or a missing `4_0` suffix looks like a createNode error, not an alignment failure.
- `singleSolve` with jitter or convergence changes gives worse results; use per-key solves.
- `execute()` on a button that needs the Viewer or a dialog returns silently: confirm state changed.
- Analysis keys are per frame: if the script frame is wrong, the key lands wrong. Read `root["frame"]` first.
- Do not assert headless success; analysis frames render the whole upstream tree at each key.

## Sources
- Foundry 17.1 reference: ocula4_0/o_solver4_0, ocula4_0/o_verticalaligner4_0, ocula_nodes/o_solver (local HTML under /opt/Nuke17.1v1/Documentation).
