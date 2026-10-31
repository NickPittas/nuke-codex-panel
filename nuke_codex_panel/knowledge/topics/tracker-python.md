---
id: "topics/tracker-python"
kind: "topic"
title: "Tracker (Tracker4) through Python"
category: "tracking-warping-retiming"
summary: "Source-derived Python for the 2D Tracker: add_track + linkableKnobs diff, tracks table cells by flat column index, anchor placement, T/R/S, track buttons, error/key inspection, Transform and CornerPin2D exports. GUI-session only; every step has a failure check."
aliases: ["tracker python", "tracker4 python", "add_track", "linkableKnobs", "LinkableKnobInfo", "tracks table", "getValueAt tracks", "track_to_end", "key_track_all", "createCornerPin", "cornerPinOptions", "createTransformStabilize", "selected_tracks", "script knob execute", "track_x track_y python", "export tracker"]
tags: ["tracker", "tracking", "python", "table", "stabilize", "matchmove", "cornerpin", "export"]
requires: ["fundamentals/coordinates", "fundamentals/time-sampling"]
related: ["topics/tracker", "topics/matchmove", "topics/planar-tracking", "topics/camera-tracking", "topics/roto-python", "topics/analysis-python", "topics/viewer-sampling", "nodes/tracker", "nodes/cornerpin", "nodes/transform"]
nodes: ["Tracker", "CornerPin2D", "Transform"]
version: "Nuke 17.1 installed docs and shipped plugin source (Tracker4.so embedded scripts, nukescripts/cameratracker.py, caravr scripts); source-derived, NOT runtime verified."
source_ids: ["foundry-17.1"]
---
# Tracker (Tracker4) through Python

## Applicability
Use when a request needs the Tracker node driven from Python: create tracks, place anchors, set T/R/S, run the track, judge error, export Transform or CornerPin2D. There is no track-creation method: Foundry itself runs the `add_track` button (`Script_Knob.execute()`) and reads/writes the `tracks` table by flat column index. Source: installed docs, shipped `cameratracker.py` `exportTracker`, and the Python embedded in `Tracker4.so`; steps 1 and the track loop were exercised in native 17.1 (control panel initialised first). Run in a live GUI Nuke session, check every step as shown, and never report a track, key or export that the check did not show. Choosing what to track and judging quality: topics/tracker.

## Workflow
### 1. Create a track; success = a NEW linkable (diff, not a hardcoded count)
```python
trk = nuke.createNode("Tracker4", "", True)   # opens the control panel; or nuke.nodes.Tracker4(inputs=[src]) then trk.showControlPanel()
def snap(): return [(l.knob().name(), tuple(int(i) for i in l.indices())) for l in trk.linkableKnobs(nuke.KnobType.eXYKnob)]
before = snap(); nuke.frame(f0); trk["add_track"].execute()
new = [s for s in snap() if s not in before]
if not new: raise RuntimeError("add_track created no track; control panel not initialised (see Pitfalls)")
kn = trk["tracks"]; xi, yi = new[0][1]; base = xi - 2
C = dict(enable=0, name=1, x=2, y=3, off_x=4, off_y=5, T=6, R=7, S=8, error=9, err_min=10, err_max=11, pat_x=12, pat_y=13, pat_r=14, pat_t=15, srch_x=16, srch_y=17, srch_r=18, srch_t=19)
col = lambda k: base + C[k]
assert yi == col("y"), "column map differs: stop, do not write"
```
Flat index = row*31 + column (31 columns/row; stride = x index of track 2 minus track 1). `setValueAt(value, frame, col)`. Verified: `kn.setValueAt(3545.0, 1, 2); kn.setValueAt(1221.0, 1, 3)` placed the anchor at pixel (3545, 1221) for track 1; `trk["select_all"].execute()` selects rows; then `for _ in range(N): trk["track_next"].execute()`.

### 2. Place anchor, flags
**Numeric cells only.** `tracks.setValueAt`/`setValue` take numbers (x, y, offsets, flags, pattern/search boxes). NEVER write a track-name string into the `name` column; keep the auto-generated name. For a readable title set the ordinary Node `label` knob on the Tracker node. No track-renaming method is established here; leave the automatic name.
```python
nuke.frame(f0)
print([kn.getValueAt(f0, col(k)) for k in ("x","y","pat_x","pat_y","pat_r","pat_t","srch_x","srch_y","srch_r","srch_t")])   # read first
kn.setValueAt(px, f0, col("x")); kn.setValueAt(py, f0, col("y"))   # numbers only; image pixels, origin bottom-left
kn.setValue(True, col("T"))                      # R, S need >=2 tracks
print(kn.getValue(col("T")), kn.isAnimated(col("T")), kn.getNumKeys(col("x")))
```
Compare pattern/search values with x,y: the docs do not say if they are absolute or relative to the anchor; write them with the same convention at the same frame via `setValueAt`. The Foundry tutorial says adding a track creates a key at the current frame. `setValue` on a flag can create a key: if `isAnimated` is True, `kn.clearAnimated(col("T"))` and re-read (shipped does this for `enable`).

### 3. Settings, selection, run
```python
trk["transform"].setValue("none"); trk["hide_progress_bar"].setValue(True)   # transform must be none while tracking
print(trk["warp"].values(), trk["transform"].values())      # set labels from these lists
trk["reference_frame"].setValue(ref)
trk["select_all"].execute(); print(trk["selected_tracks"].getText())   # "0,1,.." zero-based rows; must be non-empty
nuke.frame(f0); n0 = kn.getNumKeys(col("x")); trk["track_to_end"].execute()
print(n0, kn.getNumKeys(col("x")))                        # success = more keys, measured not assumed
```
Button knob names (Tracker4.so; no shipped Python calls them): `track_to_start`, `track_prev`, `track_next`, `track_to_end`, `key_track_current`, `key_track_all`, `track_stop`, `clear_fwd`, `clear_bkwd`, `clear_all`, `track_reset`; `track_fwd_range`/`track_bkwd_range` open a range panel, avoid. Disabled tracks are ignored.

### 4. Inspect error and key span
Plan ONE representative set (first, last, worst-error and biggest-jump frames) from this analysis, view those frames once, reuse already-viewed unchanged results, and add frames only if still uncertain. No fixed capture limit; do not skip quality checks.
```python
import math
ks = [kn.getKeyTime(i, col("x")) for i in range(kn.getNumKeys(col("x")))]
P = [(t, kn.getValueAt(t, col("x")), kn.getValueAt(t, col("y")), kn.getValueAt(t, col("error"))) for t in ks]
J = sorted(((math.hypot(b[1]-a[1], b[2]-a[2]), b[0]) for a, b in zip(P, P[1:])), reverse=True)[:5]
print(ks[0], ks[-1], len(ks), max(p[3] for p in P), J)
```
Report span, gaps, peak error frame and biggest jumps.

### 5. Export (set tracker `transform` to stabilize or match-move first)
`cornerPinOptions` index runs the knob: 0 `createPinUseCurrentFrame`, 1 `createPinUseReferenceFrame`, 2/3 same `...Baked`, 4 `createTransformStabilize`, 5 `createTransformMatchMove`, 6/7 `...Baked`. `createCornerPin` dispatches on the index; you may execute the specific knob directly.
```python
names = {n.name() for n in nuke.allNodes()}
trk["cornerPinOptions"].setValue(1); trk["createCornerPin"].execute()
out = [n for n in nuke.allNodes() if n.name() not in names]   # exports are created UNCONNECTED
```
CornerPin2D needs exactly 4 selected tracks (else `nuke.critical` modal dialog: check `selected_tracks` first); corners are ordered by angle about the centroid, so check `to1..to4`. Unbaked: `from1..4` = `Tracker.tracks.N.track_x(frame)` expressions (N = row+1), `to1..4` live `tracks.N.track_x/y`. Transform exports are named `Transform_Stabilize1`/`Transform_MatchMove1` and link `translate`, `rotate`, `scale`, `center`, `filter`; baked copies keys. Wire `out[0].setInput(0, plate)`.

## Verify
- A new linkable and key counts printed after each step; never infer from `execute()` returning.
- Export: `out` non-empty, class right, `to1.isAnimated()` or expressions evaluate; scrub reference vs distant frames (topics/tracker Verify).

## Pitfalls
- `add_track` is a silent no-op (0 tracks, ~0 ms) while the node's control panel was never initialised: call `trk.showControlPanel()` (or `nuke.show(trk)`; `createNode("Tracker4")` opens it itself) BEFORE `add_track`. No Viewer connection is needed. Verified in native 17.1: 1 track, ~5 ms. Proof of creation is the `linkableKnobs` before/after diff in step 1; no other probe needed.
- Nonexistent probes: `Tab_Knob.isCommand` and `Knob.getNumRows` (the tracks table has no row-count method; derive rows from the linkable diff/stride). Do not call them.
- Wrong `transform` while tracking; hardcoded 31 or index 2/3 without the `assert`; reading a table cell outside the key span.
- `track_to_end` ignores the Root frame range and tracks to the clip end (171 frames took 8.5 s). To stay inside a range run `trk["track_next"].execute()` in a bounded `for` loop (~67 ms/frame).
- `warp` (and other tab-entry enums): native `trk["warp"].setValue("srt")` (token) or the full entry works; the display label alone logs "Bad value" and is ignored. `value()` reads the token back.

## Sources
- Tracker reference: https://learn.foundry.com/nuke/17.1/content/reference_guide/transform_nodes/tracker.html
- /opt/Nuke17.1v1/plugins/nukescripts/cameratracker.py:625-728; plugins/caravr/SightReprojectWorkflows2_1.py:113-159; GlobalWarpExport2_1.py; strings of plugins/Tracker4.so
