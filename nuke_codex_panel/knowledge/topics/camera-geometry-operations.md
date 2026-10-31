---
id: "topics/camera-geometry-operations"
kind: "topic"
title: "Run camera solves, point-cloud bakes and geometry selection from Python"
category: "camera-tracking"
summary: "Exact Python for CameraTracker track/solve/cleanup/export, PointCloudGenerator bake limits, geometry-selection readback and one shared nuke.execute helper for disk-writing geometry nodes, with interactive-only boundaries stated."
aliases: ["script camera tracker", "solve camera python", "exportButton", "bakeGroups", "getGeoSelection", "nuke.execute WriteGeo", "GeoExport execute", "GeoSelect save selection"]
tags: ["cameratracker", "pointcloudgenerator", "geoselect", "geoselection", "writegeo", "geoexport", "execute", "python"]
requires: ["topics/camera-tracking", "fundamentals/coordinates"]
related: ["topics/pointcloud-meshing", "topics/geometry-from-images", "nodes/cameratracker", "nodes/pointcloudgenerator", "nodes/modelbuilder"]
nodes: ["CameraTracker", "PointCloudGenerator", "GeoGeneratePoints", "ModelBuilder", "GeoSelect", "GeoSelection", "WriteGeo", "GeoExport"]
version: "Nuke 17.1v1 installed docs and shipped nukescripts source (static, not runtime-verified). CameraTracker, PointCloudGenerator and ModelBuilder need NukeX/Studio; check licence and class."
source_ids: ["foundry-17.1"]
---
# Run camera solves, point-cloud bakes and geometry selection from Python

## Applicability
Use after deciding the shot suits a solve (topics/camera-tracking). Only knob names and calls shown by the installed docs and shipped plugins appear here. `execute()` exists on `Script_Knob`/`PyScript_Knob`, not the base `Knob`, so button calls are guarded and read back. Frame-range dialogs (Update Track, PointCloudGenerator Track Points) and Viewer vertex selection have no documented headless path: ask the user to click.

## Workflow
### CameraTracker: track and solve
```python
import nuke
ct = nuke.toNode('CameraTracker1')  # or nuke.createNode('CameraTracker', 'classic3D True', False) for classic nodes
assert ct.input(0), 'connect Source first'
def press(n, k):
    kn = n[k]
    if not hasattr(kn, 'execute'): raise RuntimeError(k + ' not scriptable; ask user to click it')
    kn.execute()
ct['cameraMotionLink'].setValue('Free Camera')
ct['focalLengthType'].setValue('Unknown Constant')
ct['filmBackSize'].setValue([36, 24]); ct['filmbackUnits'].setValue('mm')  # use real metadata values
ct['lensDistotionTypeLink'].setValue('Unknown Lens')  # sic; check .values() for exact label
press(ct, 'trackFeatures'); press(ct, 'solveCamera')
print(ct['solveRMSE'].value())  # px; docs: above ~1.0 refine
```
Also `numberFeatures`, `minTrackLength`, `trackRange` (+`trackStart`/`trackStop` when Custom), per-frame `solveError`. `clearTrack`/`resetSolve` only on request.

### Cleanup and refine
Raise `minLengthThreshold`; after a solve lower `maxRMSEThreshold` and `maxErrorThreshold`, then:
```python
press(ct, 'deleteRejectedTracks'); press(ct, 'updateSolve'); print(ct['solveRMSE'].value())
```
`updateTrack` opens a frame-range dialog; `refineSolve` uses `refineOptions` flags. Both interactive unless readback proves otherwise.

### CameraTracker export
The shipped `exportMenu` entries are `nukescripts.cameratracker` functions that `exportButton` runs. Call them directly:
```python
import nukescripts.cameratracker as nct
for n in nuke.selectedNodes(): n['selected'].setValue(False)  # createNode auto-connects to selection
ct['linkOutput'].setValue(True)  # linked expressions; False bakes values
cam = nct.createCamera(ct)       # returns the Camera
scene, cam, cloud = nct.createScene(ct)  # returns [scene, camera, pointCloud]
```
Also `createPointCloud`, `createCameraRig`, `createCameraSet`, `createCards`, `createLensDistortion`, `createUndistortion`, `createEverything`. Button route: `ct['exportMenu'].setValue('Camera'); press(ct, 'exportButton')` (then find the new node). Shipped code selects classic (Camera3, Scene, CameraTrackerPointCloud) or new 3D (Camera4, GeoScene, GeoCameraTrackerPoints) from `ct.knob('classic3D')`; the docs table calls this switch `new3D`.

### PointCloudGenerator (GeoGeneratePoints in new 3D)
Connect the solved Camera and the Source by input label; read `pcg.input(i)` back. Scriptable values: `pointSeparation`, `matchThreshold`, `frameSpacing`, `minTriAngle`, `densityThreshold`, `samplesPerNode`; try `press(pcg, 'analyzeSequence')` or `addAllKeyframes`. `track` shows a frame-range dialog, and `createGroup`/`groups` come from Viewer vertex selection, so `bakeGroups` and `bakeMesh` (which act on selected groups) are interactive; no headless group creation is documented. Mesh without groups: PoissonMesh (topics/pointcloud-meshing).

### Geometry selection
```python
for it in nuke.getGeoSelection():  # new 3D: nuke.GeoSelectionItem list
    print(it.getPath(), it.getVertices(), it.getVertexWeights())
f = nuke.frame(); stage = nuke.activeViewer().node().getStage(nuke.OutputContext(f), [f])
pts = it.getWorldPoints(stage, f)  # Vector3 list (as shipped geosnap3d)
nuke.toNode('GeoSelect1')['save_selection'].execute()  # + restore_selection; GeoSelection has both
import nukescripts.geosnap3d as g3; g3.geo_to_selection(axis, [f], True, False, False)  # snap Axis to selection
```
Classic nodes with a `geo_select` knob: `n['geo_select'].getSelection()`, `.getGeometry()`. `nuke.GeoSelection().selectVertices(path, verts, weights)` then `nuke.setGeoSelection(sel)` / `nuke.clearGeoSelection()` are documented signatures only; read `getGeoSelection()` back. ModelBuilder has `createCard/createCube/createSphere` and `bake` + `bakeMenu` buttons, but bake needs a tree selection and Align-mode dragging is Viewer-only.

### Shared execute for disk-writing geometry nodes
```python
def run_write(node, first, last, incr=1):
    n = nuke.toNode(node) if isinstance(node, str) else node
    nuke.execute(n, int(first), int(last), int(incr))  # errors/cancel raise
```
WriteGeo: `file`, `file_type`, `use_limit`, `first`. GeoExport: `file_type`, `file`, `stitched_export`, `export_method`. Both document button `Execute` (capital E): `n['Execute'].execute()` is the fallback. Check the file exists and is non-empty.

## Verify
Read back `solveRMSE`, the created Camera's expression/keys, new node names and exported file size; place a Card at a solved point and scrub. Print selection items before acting.

## Pitfalls
- `AttributeError` on `execute` means ask for the click; do not retry loops.
- Never clear tracks/solve or overwrite an export unasked.
- Static docs, not runtime proof: confirm licence and classes with `nuke.exists`/`nuke.createNode` errors.

## Sources
- /opt/Nuke17.1v1/Documentation/html/content/reference_guide/3d_nodes/{cameratracker,pointcloudgenerator,geoselect,modelbuilder,writegeo}.html; 3dnew_nodes/{geoselection,geogeneratepoints,geoexport}.html
- /opt/Nuke17.1v1/plugins/nukescripts/{cameratracker,geosnap3d,modelbuilder}.py; Python API: nuke.execute, nuke.getGeoSelection, nuke.GeoSelection, Script_Knob
