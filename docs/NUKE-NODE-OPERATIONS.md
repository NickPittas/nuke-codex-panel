# Nuke 17.1 node reference: operational accounting

Source: `/opt/Nuke17.1v1/Documentation/html/content/reference_guide/` (inventory `local://nuke-reference-inventory.json`, 27 directories, **541 HTML files**, no duplicates, none truncated). Every inventory file appears exactly once in the tables below. This is a documentation audit: it proves what the reference pages say, NOT that a node is licensed, installed or working in a running Nuke.

## Counting rules

- A "topic page" is one HTML file. Not every page is a node class: 32 files are category indexes, preface pages or menu/doc pages (class **non-node**), so 541 files − 32 non-node pages = **509 node/tool pages**. No node-class total is claimed.
- The same node class appears in several directories for different versions (`cara_vr*`, `ocula*`, `3d_nodes` vs `3dnew_nodes`, `Axis`, `Camera`, `ScanlineRender`, `DepthToPosition`), so page count is not distinct-class count and no distinct-class total is asserted.
- **ordinary**: scalar/enum/bool/string/XY(Z) knobs set by Python, compute automatic at render time, covered by generic knob-set + animation + `viewer-sampling` guidance. XY/position knobs and Viewer on-screen handles (Transform, Axis, Camera, Light, ParticleGravity/Vortex/Wind, centre/position indicators) are ordinary knobs, NOT special: set the knob.
- **specialised**: needs an explicit run/analysis/solve/bake/export action, Viewer picking, curve/shape/mesh editing, or file/session state. Kept as a small set of operational families (below).
- **Automatic render-time** (Kronos, OFlow, MotionBlur, VectorGenerator, SmartVector, Inference, ScanlineRender, RayRender, FieldRender, Upscale/Deblur, PoissonMesh, F_RigRemoval, F_DeFlicker2, O_* stereo nodes): the result computes when something downstream requests pixels; optional pre-computed inputs only. **Explicit button**: nothing happens until the knob button runs (`execute`, `startTraining`, `analyse`, `track`, `solve`, `Render` …).
- Availability: pages show NukeX/Studio, LABS, Beta and licence notes; those are documentation claims. Licensed runtime availability must be probed in the live Nuke (class exists, licence gate, GPU), never inferred from a page.

## Category counts (exact)

| directory | files | ordinary | specialised | non-node |
|---|---:|---:|---:|---:|
| `3d_nodes` | 58 | 50 | 7 | 1 |
| `3dnew_nodes` | 75 | 68 | 6 | 1 |
| `air_nodes` | 7 | 2 | 4 | 1 |
| `cara_vr` | 15 | 11 | 3 | 1 |
| `cara_vr2_0` | 18 | 13 | 4 | 1 |
| `cara_vr2_1` | 16 | 11 | 4 | 1 |
| `channel_nodes` | 7 | 6 | 0 | 1 |
| `color_nodes` | 42 | 39 | 2 | 1 |
| `deep_nodes` | 15 | 11 | 3 | 1 |
| `draw_nodes` | 18 | 14 | 3 | 1 |
| `field_nodes` | 35 | 32 | 2 | 1 |
| `filter_nodes` | 35 | 33 | 1 | 1 |
| `furnacecore_nodes` | 7 | 2 | 4 | 1 |
| `image_nodes` | 12 | 5 | 6 | 1 |
| `katana_nodes` | 3 | 2 | 0 | 1 |
| `keyer_nodes` | 12 | 5 | 6 | 1 |
| `merge_nodes` | 26 | 25 | 0 | 1 |
| `metadata_nodes` | 6 | 5 | 0 | 1 |
| `ocula4_0` | 15 | 13 | 1 | 1 |
| `ocula_nodes` | 14 | 12 | 1 | 1 |
| `other_nodes` | 22 | 19 | 1 | 2 |
| `particles_nodes` | 22 | 20 | 1 | 1 |
| `preface` | 2 | 0 | 0 | 2 |
| `time_nodes` | 20 | 19 | 0 | 1 |
| `toolsets_nodes` | 3 | 0 | 0 | 3 |
| `transform_nodes` | 27 | 17 | 9 | 1 |
| `views_nodes` | 9 | 7 | 0 | 2 |
| **core subtotal (20 dirs)** | 453 | 377 | 51 | 25 |
| **plugin annex subtotal (7 dirs)** | 88 | 64 | 17 | 7 |
| **TOTAL** | 541 | 441 | 68 | 32 |

Non-node pages beyond category indexes: `preface/getting_help`, `preface/reference_guide`, `other_nodes/all_plugins` (menu doc), `views_nodes/split_and_join` (OneView+JoinViews pattern doc), `toolsets_nodes/create`, `toolsets_nodes/delete` (ToolSet menu docs). `particles_nodes/particles_nodes_nukex.html`, `3dnew_nodes/usd3d_nodes.html` and `image_nodes/image_nodes.html` are the index pages of their directories.

## Canonical operational families (core, small set)

| family | members (core) | mode | intended recipe |
|---|---|---|---|
| Execution / render / export | Write, DeepWrite, GenerateLUT, Encryptomatte (`exportWrite` creates a Write), WriteGeo, PrmanRender, FieldVolume/FieldVolumeWrite, ParticleCache, GeoExport, GeoSequencer; Profile uses performance timers, not writer execution | execute files or run specialised export/cache actions; Profile is a separate measurement path | `topics/output-execution` |
| Analysis, solve & dialog buttons | CurveTool, MatchGrade, UDIM Import, UnrealReader, Denoise (automatic render-time denoise; region/knob changes re-analyse; `analyze` and profile Import/Export are optional), LensDistortion, BlinkScript | deliberate analysis/compile or dialog; not every node needs `nuke.execute` | `topics/analysis-python`, `topics/lens-calibration`, `topics/paint-cleanup` |
| Viewer sampling & pickers | Viewer, Primatte, Ultimatte, Cryptomatte, IBKColor, IBKGizmo, DeepSample, DeepToPoints (+ shared eyedropper/curve-point sampling on Grade, ColorCorrect, KeyLight, ChromaKeyer, HSVTool, ColorLookup, HueCorrect, Sampler, GeoGrade: those stay ordinary) | Viewer-interactive | `topics/viewer-sampling`, `topics/picker-keyers` |
| Tracking, solve & match-move | Tracker, Stabilize2D, CornerPin2D, GridWarpTracker, PointsTo3D, Reconcile3D (explicit create-keyframes bake), CameraTracker | explicit track/solve/bake/export buttons + Viewer anchors | `topics/tracker-python`, `topics/projection-bake`, `topics/tracker`, `topics/camera-tracking` |
| Roto, paint & warp editing | Roto, RotoPaint, DustBust (Ctrl-click paint of clone points in the Viewer; paint editing, not a render/execute action), GridWarp, SplineWarp | Viewer shape/stroke/mesh editing | `topics/roto-python`, `topics/warp-operations`, `topics/paint-cleanup`, `topics/rotoscoping-masking`, `topics/spline-grid-warp` |
| Geometry / point-cloud / USD authoring & bake | EditGeo, GeoSelect, ModelBuilder, PointCloudGenerator, GeoCard (new shape/subdivide/handle-key buttons), GeoSelection (stored Viewer face/vertex selection), GeoGeneratePoints (`analyzeSequence`, `createGroup`, `bakeGroups`, `bakeMesh`), GeoImport (`updateLocalization`, `reload`) | Viewer picking + explicit bake/analyze/update buttons | `topics/camera-geometry-operations` |
| ML train / export / infer | CopyCat, BigCat, CatFileCreator (explicit); Inference (automatic render-time) | `startTraining`/`resumeTraining`/`createInference`/`createCatFileKnob`; `.cat` applied at render | `topics/ml-training` |

Notes: Kronos, OFlow, MotionBlur and the vector nodes are automatic render-time, so they are ordinary. ScanlineRender/GeoRender/SplatRender selection of delegate or output is knob choice, not an explicit run. Truelight is deprecated (superseded by Baselight). ReConverge needs an external disparity input. ParticleGravity/Vortex/Wind arrow handles just write force knobs.

## Plugin annex (kept separate)

Plugin analysis recipes: `topics/plugin-analysis-caravr` (CaraVR), `topics/plugin-analysis-stereo` (Ocula), `topics/plugin-analysis-restoration` (FurnaceCore). Plugin families are licence/plugin-gated (CaraVR, Ocula = licence; FurnaceCore = NukeX/Studio; Katana nodes need `NUKE_PATH` import), docs presence is not runtime availability.

| family | pages | mode |
|---|---|---|
| CaraVR rig solve | C_CameraSolver (`cara_vr`, `cara_vr2_0`, `cara_vr2_1`) | explicit match/solve/refine/export buttons |
| CaraVR stitch/warp | C_Stitcher (3 versions), C_GlobalWarp (2.0, 2.1) | explicit match/warp/key buttons |
| CaraVR tracker | C_Tracker (3 versions) | explicit auto-track/solve + user tracks |
| FurnaceCore GME | F_Align, F_Steadiness, F_ReGrain | explicit `analyse` button |
| FurnaceCore wire | F_WireRemoval | explicit tracker buttons + Viewer panel |
| Ocula solve | O_Solver (3.0), O_Solver (4.0) | explicit analyse/solve buttons |

Version variants stay accounted per file; recipes consolidate once per family. Automatic render-time plugin nodes (C_Blur, C_Bilateral, C_STMap, C_SphericalTransform, F_RigRemoval, F_DeFlicker2, O_DisparityGenerator, O_VerticalAligner, O_DisparityViewer, O_ColourMatcher, O_NewView, O_Retimer …, KatanaReader/Writer) are ordinary.

## Per-file accounting

Legend: ordinary = O; specialised = S (family; mode); non-node = N. All paths are relative to the reference_guide directory.


### `3d_nodes/` (58 files)

| file | class | family / note |
|---|---|---|
| `3d_nodes.html` | non-node / index | non-node: category index |
| `ambientocclusion.html` | ordinary |  |
| `applymaterial.html` | ordinary |  |
| `axis.html` | ordinary |  |
| `basicmaterial.html` | ordinary |  |
| `blendmat.html` | ordinary |  |
| `camera.html` | ordinary |  |
| `cameratracker.html` | specialised | Tracking, solve & match-move data; explicit button/execute; track/solve/export; NukeX |
| `card.html` | ordinary |  |
| `crosstalkgeo.html` | ordinary |  |
| `cube.html` | ordinary |  |
| `cylinder.html` | ordinary |  |
| `depthgenerator.html` | ordinary |  |
| `depthtopoints.html` | ordinary |  |
| `depthtoposition.html` | ordinary |  |
| `diffuse.html` | ordinary |  |
| `direct.html` | ordinary |  |
| `displacegeo.html` | ordinary |  |
| `displacement.html` | ordinary |  |
| `editgeo.html` | specialised | Geometry / point-cloud / USD authoring & bake; Viewer-interactive; Viewer vertex picking/align |
| `emission.html` | ordinary |  |
| `environment.html` | ordinary |  |
| `fillmat.html` | ordinary |  |
| `geoselect.html` | specialised | Geometry / point-cloud / USD authoring & bake; Viewer-interactive; Viewer vertex picking/align |
| `light.html` | ordinary |  |
| `loggeo.html` | ordinary |  |
| `lookupgeo.html` | ordinary |  |
| `mergegeo.html` | ordinary |  |
| `mergemat.html` | ordinary |  |
| `modelbuilder.html` | specialised | Geometry / point-cloud / USD authoring & bake; Viewer-interactive; Viewer vertex picking/align |
| `modifyrib.html` | ordinary |  |
| `normals.html` | ordinary |  |
| `phong.html` | ordinary |  |
| `point.html` | ordinary |  |
| `pointcloudgenerator.html` | specialised | Geometry / point-cloud / USD authoring & bake; explicit button/execute; bake buttons; NukeX |
| `poissonmesh.html` | ordinary |  |
| `positiontopoints.html` | ordinary |  |
| `prmanrender.html` | specialised | Execution / render / export (explicit); explicit button/execute; Execute button |
| `proceduralnoise.html` | ordinary |  |
| `project3d.html` | ordinary |  |
| `radialdistort.html` | ordinary |  |
| `rayrender.html` | ordinary |  |
| `readgeo.html` | ordinary |  |
| `reflection.html` | ordinary |  |
| `refraction.html` | ordinary |  |
| `relight.html` | ordinary |  |
| `scanlinerender.html` | ordinary |  |
| `scene.html` | ordinary |  |
| `specular.html` | ordinary |  |
| `sphere.html` | ordinary |  |
| `spot.html` | ordinary |  |
| `transformgeo.html` | ordinary |  |
| `transmission.html` | ordinary |  |
| `trilinear.html` | ordinary |  |
| `uvproject.html` | ordinary |  |
| `uvtile.html` | ordinary |  |
| `wireframe.html` | ordinary |  |
| `writegeo.html` | specialised | Execution / render / export (explicit); explicit button/execute; Execute button |

### `3dnew_nodes/` (75 files)

| file | class | family / note |
|---|---|---|
| `axis.html` | ordinary |  |
| `basicsurface.html` | ordinary |  |
| `camera.html` | ordinary |  |
| `constantshader.html` | ordinary |  |
| `depthtoposition.html` | ordinary |  |
| `directlight.html` | ordinary |  |
| `environmentlight.html` | ordinary |  |
| `fillshader.html` | ordinary |  |
| `geoactivation.html` | ordinary |  |
| `geobindmaterial.html` | ordinary |  |
| `geobreaklayer.html` | ordinary |  |
| `geocamera.html` | ordinary |  |
| `geocard.html` | specialised | Geometry / point-cloud / USD authoring & bake; explicit buttons; new shape / subdivide / handle key buttons |
| `geoclearmask.html` | ordinary |  |
| `geocollection.html` | ordinary |  |
| `geocolorspace.html` | ordinary |  |
| `geoconstrain.html` | ordinary |  |
| `geocube.html` | ordinary |  |
| `geocylinder.html` | ordinary |  |
| `geodeletepoints.html` | ordinary |  |
| `geodisklight.html` | ordinary |  |
| `geodisplace.html` | ordinary |  |
| `geodistantlight.html` | ordinary |  |
| `geodomelight.html` | ordinary |  |
| `geodrawmode.html` | ordinary |  |
| `geoduplicate.html` | ordinary |  |
| `geoeditcamera.html` | ordinary |  |
| `geoeditlight.html` | ordinary |  |
| `geoexport.html` | specialised | Execution / render / export (explicit); explicit button/execute; write/convert |
| `geofieldmesh.html` | ordinary |  |
| `geofieldset.html` | ordinary |  |
| `geofieldwarp.html` | ordinary |  |
| `geogeneratepoints.html` | specialised | Geometry / point-cloud / USD authoring & bake; explicit buttons; analyzeSequence, createGroup, bakeGroups, bakeMesh; NukeX |
| `geograde.html` | ordinary |  |
| `geoimport.html` | specialised | Geometry / point-cloud / USD authoring & bake; explicit buttons; Update (updateLocalization) and Reload |
| `geoinstance.html` | ordinary |  |
| `geomask.html` | ordinary |  |
| `geomerge.html` | ordinary |  |
| `geonoise.html` | ordinary |  |
| `geonormals.html` | ordinary |  |
| `geopointinstancer.html` | ordinary |  |
| `geopoints.html` | ordinary |  |
| `geopointstomesh.html` | ordinary |  |
| `geoprojectuv.html` | ordinary |  |
| `geopython.html` | ordinary |  |
| `georadialwarp.html` | ordinary |  |
| `georeference.html` | ordinary |  |
| `georender.html` | ordinary |  |
| `georenderproduct.html` | ordinary |  |
| `georendersetting.html` | ordinary |  |
| `georendervariable.html` | ordinary |  |
| `geoscene.html` | ordinary |  |
| `geoscope.html` | ordinary |  |
| `geoscript.html` | ordinary |  |
| `geoselection.html` | specialised | Geometry / point-cloud / USD authoring & bake; Viewer-interactive; stores Viewer face/vertex selection |
| `geosequencer.html` | specialised | Execution / render / export (explicit); explicit button/execute; write/convert |
| `geosphere.html` | ordinary |  |
| `geospherelight.html` | ordinary |  |
| `geotransform.html` | ordinary |  |
| `geotrilinearwarp.html` | ordinary |  |
| `geovalueclip.html` | ordinary |  |
| `geoviewscene.html` | ordinary |  |
| `geovisibility.html` | ordinary |  |
| `geoxform.html` | ordinary |  |
| `mergelayershader.html` | ordinary |  |
| `mtlxstandardsurface.html` | ordinary |  |
| `pointlight.html` | ordinary |  |
| `previewsurface.html` | ordinary |  |
| `project3dshader.html` | ordinary |  |
| `reflectivesurface.html` | ordinary |  |
| `scanlinerender.html` | ordinary |  |
| `splatrender.html` | ordinary |  |
| `spotlight.html` | ordinary |  |
| `usd3d_nodes.html` | non-node / index | non-node: category index |
| `wireframeshader.html` | ordinary |  |

### `air_nodes/` (7 files)

| file | class | family / note |
|---|---|---|
| `air_nodes.html` | non-node / index | non-node: category index |
| `bigcat.html` | specialised | ML train / export / infer; explicit button/execute; training/export buttons |
| `catfilecreator.html` | specialised | ML train / export / infer; explicit button/execute; training/export buttons |
| `copycat.html` | specialised | ML train / export / infer; explicit button/execute; training/export buttons |
| `deblur.html` | ordinary |  |
| `inference.html` | specialised | ML train / export / infer; automatic render-time; applies .cat at render; no train buttons |
| `upscale.html` | ordinary |  |

### `cara_vr/` (15 files)

| file | class | family / note |
|---|---|---|
| `c_alphagenerator.html` | ordinary |  |
| `c_bilateral.html` | ordinary |  |
| `c_blender.html` | ordinary |  |
| `c_blur.html` | ordinary |  |
| `c_camerasolver.html` | specialised | Plugin analysis (annex); explicit button/execute + Viewer; CaraVR family |
| `c_colourmatcher.html` | ordinary |  |
| `c_disparitygenerator.html` | ordinary |  |
| `c_generatemap.html` | ordinary |  |
| `c_metadatatransform.html` | ordinary |  |
| `c_rayrender.html` | ordinary |  |
| `c_sphericaltransform.html` | ordinary |  |
| `c_stitcher.html` | specialised | Plugin analysis (annex); explicit button/execute + Viewer; CaraVR family |
| `c_stmap.html` | ordinary |  |
| `c_tracker.html` | specialised | Plugin analysis (annex); explicit button/execute + Viewer; CaraVR family |
| `caravr_nodes.html` | non-node / index | non-node: category index |

### `cara_vr2_0/` (18 files)

| file | class | family / note |
|---|---|---|
| `c_alphagenerator2_0.html` | ordinary |  |
| `c_bilateral2_0.html` | ordinary |  |
| `c_blender2_0.html` | ordinary |  |
| `c_blur2_0.html` | ordinary |  |
| `c_camerasolver2_0.html` | specialised | Plugin analysis (annex); explicit button/execute + Viewer; CaraVR family |
| `c_colourmatcher2_0.html` | ordinary |  |
| `c_disparitygenerator2_0.html` | ordinary |  |
| `c_disparitytodepth2_0.html` | ordinary |  |
| `c_generatemap2_0.html` | ordinary |  |
| `c_globalwarp2_0.html` | specialised | Plugin analysis (annex); explicit button/execute + Viewer; CaraVR family |
| `c_newview2_0.html` | ordinary |  |
| `c_rayrender2_0.html` | ordinary |  |
| `c_sphericaltransform2_0.html` | ordinary |  |
| `c_stereocolourmatcher2_0.html` | ordinary |  |
| `c_stitcher2_0.html` | specialised | Plugin analysis (annex); explicit button/execute + Viewer; CaraVR family |
| `c_stmap2_0.html` | ordinary |  |
| `c_tracker2_0.html` | specialised | Plugin analysis (annex); explicit button/execute + Viewer; CaraVR family |
| `caravr_nodes.html` | non-node / index | non-node: category index |

### `cara_vr2_1/` (16 files)

| file | class | family / note |
|---|---|---|
| `c_alphagenerator2_1.html` | ordinary |  |
| `c_bilateral2_1.html` | ordinary |  |
| `c_blender2_1.html` | ordinary |  |
| `c_blur2_1.html` | ordinary |  |
| `c_cameraingest2_1.html` | ordinary |  |
| `c_camerasolver2_1.html` | specialised | Plugin analysis (annex); explicit button/execute + Viewer; CaraVR family |
| `c_colourmatcher2_1.html` | ordinary |  |
| `c_disparitygenerator2_1.html` | ordinary |  |
| `c_generatemap2_1.html` | ordinary |  |
| `c_globalwarp2_1.html` | specialised | Plugin analysis (annex); explicit button/execute + Viewer; CaraVR family |
| `c_rayrender2_1.html` | ordinary |  |
| `c_sphericaltransform2_1.html` | ordinary |  |
| `c_stitcher2_1.html` | specialised | Plugin analysis (annex); explicit button/execute + Viewer; CaraVR family |
| `c_stmap2_1.html` | ordinary |  |
| `c_tracker2_1.html` | specialised | Plugin analysis (annex); explicit button/execute + Viewer; CaraVR family |
| `caravr_nodes.html` | non-node / index | non-node: category index |

### `channel_nodes/` (7 files)

| file | class | family / note |
|---|---|---|
| `addchannels.html` | ordinary |  |
| `channel_nodes.html` | non-node / index | non-node: category index |
| `channelmerge.html` | ordinary |  |
| `copy.html` | ordinary |  |
| `remove.html` | ordinary |  |
| `shuffle.html` | ordinary |  |
| `shufflecopy.html` | ordinary |  |

### `color_nodes/` (42 files)

| file | class | family / note |
|---|---|---|
| `add.html` | ordinary |  |
| `clamp.html` | ordinary |  |
| `cliptest.html` | ordinary |  |
| `cmstestpattern.html` | ordinary |  |
| `color_nodes.html` | non-node / index | non-node: category index |
| `colorcorrect.html` | ordinary |  |
| `colorlookup.html` | ordinary |  |
| `colormatrix.html` | ordinary |  |
| `colorspace.html` | ordinary |  |
| `colortransfer.html` | ordinary |  |
| `crosstalk.html` | ordinary |  |
| `exposure.html` | ordinary |  |
| `expression.html` | ordinary |  |
| `gamma.html` | ordinary |  |
| `generatelut.html` | specialised | Execution / render / export (explicit); explicit button/execute; execute() writes LUT |
| `grade.html` | ordinary |  |
| `histeq.html` | ordinary |  |
| `histogram.html` | ordinary |  |
| `hsvtool.html` | ordinary |  |
| `huecorrect.html` | ordinary |  |
| `hueshift.html` | ordinary |  |
| `invert.html` | ordinary |  |
| `log2lin.html` | ordinary |  |
| `matchgrade.html` | specialised | Analysis, solve & dialog buttons; explicit button/execute; analyzeRefFrames; NukeX/Studio |
| `mincolor.html` | ordinary |  |
| `multiply_color.html` | ordinary |  |
| `ociocdltransform.html` | ordinary |  |
| `ociocolorspace.html` | ordinary |  |
| `ociodisplay.html` | ordinary |  |
| `ociofiletransform.html` | ordinary |  |
| `ociologconvert.html` | ordinary |  |
| `ociolooktransform.html` | ordinary |  |
| `ocionamedtransform.html` | ordinary |  |
| `ploglin.html` | ordinary |  |
| `posterize.html` | ordinary |  |
| `rolloffcontrast.html` | ordinary |  |
| `sampler.html` | ordinary |  |
| `saturation.html` | ordinary |  |
| `softclip.html` | ordinary |  |
| `toe.html` | ordinary |  |
| `truelight.html` | ordinary |  |
| `vectorfield.html` | ordinary |  |

### `deep_nodes/` (15 files)

| file | class | family / note |
|---|---|---|
| `deep_nodes.html` | non-node / index | non-node: category index |
| `deepcolorcorrect.html` | ordinary |  |
| `deepcrop.html` | ordinary |  |
| `deepexpression.html` | ordinary |  |
| `deepfromframes.html` | ordinary |  |
| `deepfromimage.html` | ordinary |  |
| `deepmerge.html` | ordinary |  |
| `deepread.html` | ordinary |  |
| `deeprecolor.html` | ordinary |  |
| `deepreformat.html` | ordinary |  |
| `deepsample.html` | specialised | Viewer sampling & picker workflows; Viewer-interactive; Viewer pos inspection / 3D view output |
| `deeptoimage.html` | ordinary |  |
| `deeptopoints.html` | specialised | Viewer sampling & picker workflows; Viewer-interactive; Viewer pos inspection / 3D view output |
| `deeptransform.html` | ordinary |  |
| `deepwrite.html` | specialised | Execution / render / export (explicit); explicit button/execute; execute |

### `draw_nodes/` (18 files)

| file | class | family / note |
|---|---|---|
| `dither.html` | ordinary |  |
| `draw_nodes.html` | non-node / index | non-node: category index |
| `dustbust.html` | specialised | Roto, paint & warp editing; Viewer-interactive; Ctrl-click paint of clone points (paint, not render/execute) |
| `flare.html` | ordinary |  |
| `glint.html` | ordinary |  |
| `grain.html` | ordinary |  |
| `grid.html` | ordinary |  |
| `lightwrap.html` | ordinary |  |
| `markerremoval.html` | ordinary |  |
| `noise.html` | ordinary |  |
| `radial.html` | ordinary |  |
| `ramp.html` | ordinary |  |
| `rectangle.html` | ordinary |  |
| `roto.html` | specialised | Roto, paint & warp editing; Viewer-interactive; shape/stroke/point editing |
| `rotopaint.html` | specialised | Roto, paint & warp editing; Viewer-interactive; shape/stroke/point editing |
| `scannedgrain.html` | ordinary |  |
| `sparkles.html` | ordinary |  |
| `text.html` | ordinary |  |

### `field_nodes/` (35 files)

| file | class | family / note |
|---|---|---|
| `field_nodes.html` | non-node / index | non-node: category index |
| `fieldattract.html` | ordinary |  |
| `fieldcellnoise.html` | ordinary |  |
| `fieldconstant.html` | ordinary |  |
| `fieldcrop.html` | ordinary |  |
| `fieldcurves.html` | ordinary |  |
| `fielddeform.html` | ordinary |  |
| `fieldfractal.html` | ordinary |  |
| `fieldgrid.html` | ordinary |  |
| `fieldimage.html` | ordinary |  |
| `fieldinvert.html` | ordinary |  |
| `fieldlookat.html` | ordinary |  |
| `fieldmath.html` | ordinary |  |
| `fieldmerge.html` | ordinary |  |
| `fieldmix.html` | ordinary |  |
| `fieldnoise.html` | ordinary |  |
| `fieldposition.html` | ordinary |  |
| `fieldradial.html` | ordinary |  |
| `fieldramp.html` | ordinary |  |
| `fieldrender.html` | ordinary |  |
| `fieldshape.html` | ordinary |  |
| `fieldshapemodify.html` | ordinary |  |
| `fieldshapetodensity.html` | ordinary |  |
| `fieldshapetoposition.html` | ordinary |  |
| `fieldsurface.html` | ordinary |  |
| `fieldswizzle.html` | ordinary |  |
| `fieldtransform.html` | ordinary |  |
| `fieldtrilinearwarp.html` | ordinary |  |
| `fieldvolume.html` | specialised | Execution / render / export (explicit); file IO / explicit write; OpenVDB |
| `fieldvolumewrite.html` | specialised | Execution / render / export (explicit); file IO / explicit write; OpenVDB |
| `fieldvortex.html` | ordinary |  |
| `fieldvortexring.html` | ordinary |  |
| `fieldwarp.html` | ordinary |  |
| `imagefield.html` | ordinary |  |
| `particlefieldforce.html` | ordinary |  |

### `filter_nodes/` (35 files)

| file | class | family / note |
|---|---|---|
| `bilateral.html` | ordinary |  |
| `blur.html` | ordinary |  |
| `bokeh.html` | ordinary |  |
| `bumpboss.html` | ordinary |  |
| `convolve.html` | ordinary |  |
| `defocus.html` | ordinary |  |
| `degrainblue.html` | ordinary |  |
| `degrainsimple.html` | ordinary |  |
| `denoise.html` | specialised | Analysis, solve & dialog buttons; automatic render-time denoise, analysis re-runs automatically on box/knob change; optional `analyze` button and profile Import/Export |
| `dirblur.html` | ordinary |  |
| `dropshadow.html` | ordinary |  |
| `edgeblur.html` | ordinary |  |
| `edgedetect.html` | ordinary |  |
| `edgeextend.html` | ordinary |  |
| `emboss.html` | ordinary |  |
| `erode_blur.html` | ordinary |  |
| `erode_fast.html` | ordinary |  |
| `erode_filter.html` | ordinary |  |
| `filter_nodes.html` | non-node / index | non-node: category index |
| `glow.html` | ordinary |  |
| `godrays.html` | ordinary |  |
| `inpaint.html` | ordinary |  |
| `laplacian.html` | ordinary |  |
| `levelset.html` | ordinary |  |
| `matrix.html` | ordinary |  |
| `median.html` | ordinary |  |
| `motionblur.html` | ordinary |  |
| `motionblur2d.html` | ordinary |  |
| `motionblur3d.html` | ordinary |  |
| `sharpen.html` | ordinary |  |
| `soften.html` | ordinary |  |
| `vectorblur.html` | ordinary |  |
| `volumerays.html` | ordinary |  |
| `zdefocus.html` | ordinary |  |
| `zslice.html` | ordinary |  |

### `furnacecore_nodes/` (7 files)

| file | class | family / note |
|---|---|---|
| `f_align.html` | specialised | Plugin analysis (annex); explicit button/execute; GME analyse button |
| `f_deflicker2.html` | ordinary |  |
| `f_regrain.html` | specialised | Plugin analysis (annex); explicit button/execute; GME analyse button |
| `f_rigremoval.html` | ordinary |  |
| `f_steadiness.html` | specialised | Plugin analysis (annex); explicit button/execute; GME analyse button |
| `f_wireremoval.html` | specialised | Plugin analysis (annex); explicit buttons + Viewer; wire tracker |
| `fc_nukex.html` | non-node / index | non-node: category index |

### `image_nodes/` (12 files)

| file | class | family / note |
|---|---|---|
| `checkerboard.html` | ordinary |  |
| `colorbars.html` | ordinary |  |
| `colorwheel.html` | ordinary |  |
| `constant.html` | ordinary |  |
| `curvetool.html` | specialised | Analysis, solve & dialog buttons; explicit button/execute; analysis buttons -> animation curves |
| `image_nodes.html` | non-node / index | non-node: category index |
| `profile.html` | specialised | Execution / render / export (explicit); explicit button/execute; Profile pane run; render hooks |
| `read.html` | ordinary |  |
| `udim_import.html` | specialised | Analysis, solve & dialog buttons; explicit button/execute; dialog creates Read+UVTile trees |
| `unrealreader.html` | specialised | Analysis, solve & dialog buttons; explicit button/execute; live Unreal session buttons/layer picker |
| `viewer.html` | specialised | Viewer sampling & picker workflows; Viewer-interactive; Viewer itself |
| `write.html` | specialised | Execution / render / export (explicit); explicit button/execute; render via nuke.execute; proxy caveat |

### `katana_nodes/` (3 files)

| file | class | family / note |
|---|---|---|
| `katana-nodes.html` | non-node / index | non-node: category index |
| `katanareader.html` | ordinary |  |
| `katanawriter.html` | ordinary |  |

### `keyer_nodes/` (12 files)

| file | class | family / note |
|---|---|---|
| `chromakeyer.html` | ordinary |  |
| `cryptomatte.html` | specialised | Viewer sampling & picker workflows; Viewer-interactive; picker/sponge workflows |
| `difference.html` | ordinary |  |
| `encryptomatte.html` | specialised | Execution / render / export (explicit); explicit button/execute; exportWrite creates Write |
| `huekeyer.html` | ordinary |  |
| `ibkcolor.html` | specialised | Viewer sampling & picker workflows; Viewer-interactive; picker/sponge workflows |
| `ibkgizmo.html` | specialised | Viewer sampling & picker workflows; Viewer-interactive; picker/sponge workflows |
| `keyer.html` | ordinary |  |
| `keyer_nodes.html` | non-node / index | non-node: category index |
| `keylight.html` | ordinary |  |
| `primatte.html` | specialised | Viewer sampling & picker workflows; Viewer-interactive; picker/sponge workflows |
| `ultimatte.html` | specialised | Viewer sampling & picker workflows; Viewer-interactive; picker/sponge workflows |

### `merge_nodes/` (26 files)

| file | class | family / note |
|---|---|---|
| `absminus.html` | ordinary |  |
| `addmix.html` | ordinary |  |
| `blend.html` | ordinary |  |
| `contactsheet.html` | ordinary |  |
| `copybbox.html` | ordinary |  |
| `copyrectangle.html` | ordinary |  |
| `dissolve.html` | ordinary |  |
| `in.html` | ordinary |  |
| `keymix.html` | ordinary |  |
| `layercontactsheet.html` | ordinary |  |
| `matte.html` | ordinary |  |
| `max.html` | ordinary |  |
| `merge.html` | ordinary |  |
| `merge_nodes.html` | non-node / index | non-node: category index |
| `mergeexpression.html` | ordinary |  |
| `min.html` | ordinary |  |
| `multiply_merge.html` | ordinary |  |
| `out.html` | ordinary |  |
| `plus.html` | ordinary |  |
| `premult.html` | ordinary |  |
| `screen.html` | ordinary |  |
| `switch.html` | ordinary |  |
| `timedissolve.html` | ordinary |  |
| `unpremult.html` | ordinary |  |
| `variableswitch.html` | ordinary |  |
| `zmerge.html` | ordinary |  |

### `metadata_nodes/` (6 files)

| file | class | family / note |
|---|---|---|
| `addtimecode.html` | ordinary |  |
| `comparemetadata.html` | ordinary |  |
| `copymetadata.html` | ordinary |  |
| `metadata_nodes.html` | non-node / index | non-node: category index |
| `modifymetadata.html` | ordinary |  |
| `viewmetadata.html` | ordinary |  |

### `ocula4_0/` (15 files)

| file | class | family / note |
|---|---|---|
| `o_colourmatcher4_0.html` | ordinary |  |
| `o_depthtodisparity4_0.html` | ordinary |  |
| `o_disparitygenerator4_0.html` | ordinary |  |
| `o_disparitytodepth4_0.html` | ordinary |  |
| `o_disparityviewer4_0.html` | ordinary |  |
| `o_focusmatcher4_0.html` | ordinary |  |
| `o_interaxialshifter4_0.html` | ordinary |  |
| `o_multisample4_0.html` | ordinary |  |
| `o_newview4_0.html` | ordinary |  |
| `o_occlusiondetector4_0.html` | ordinary |  |
| `o_retimer4_0.html` | ordinary |  |
| `o_solver4_0.html` | specialised | Plugin analysis (annex); explicit button/execute; Ocula solve |
| `o_vectorgenerator4_0.html` | ordinary |  |
| `o_verticalaligner4_0.html` | ordinary |  |
| `ocula_nodes.html` | non-node / index | non-node: category index |

### `ocula_nodes/` (14 files)

| file | class | family / note |
|---|---|---|
| `o_colourmatcher.html` | ordinary |  |
| `o_depthtodisparity.html` | ordinary |  |
| `o_disparitygenerator.html` | ordinary |  |
| `o_disparitytodepth.html` | ordinary |  |
| `o_disparityviewer.html` | ordinary |  |
| `o_focusmatcher.html` | ordinary |  |
| `o_interaxialshifter.html` | ordinary |  |
| `o_newview.html` | ordinary |  |
| `o_occlusiondetector.html` | ordinary |  |
| `o_retimer.html` | ordinary |  |
| `o_solver.html` | specialised | Plugin analysis (annex); explicit button/execute; Ocula solve |
| `o_vectorgenerator.html` | ordinary |  |
| `o_verticalaligner.html` | ordinary |  |
| `ocula_nodes.html` | non-node / index | non-node: category index |

### `other_nodes/` (22 files)

| file | class | family / note |
|---|---|---|
| `all_plugins.html` | non-node / index | non-node: menu doc |
| `annotations.html` | ordinary |  |
| `assert.html` | ordinary |  |
| `audioread.html` | ordinary |  |
| `backdrop.html` | ordinary |  |
| `blinkscript.html` | specialised | Analysis, solve & dialog buttons; explicit button/execute; kernel compile/run |
| `burnin.html` | ordinary |  |
| `diskcache.html` | ordinary |  |
| `dot.html` | ordinary |  |
| `group.html` | ordinary |  |
| `input.html` | ordinary |  |
| `link.html` | ordinary |  |
| `livegroup.html` | ordinary |  |
| `liveinput.html` | ordinary |  |
| `noop.html` | ordinary |  |
| `other_nodes.html` | non-node / index | non-node: category index |
| `output.html` | ordinary |  |
| `postagestamp.html` | ordinary |  |
| `precomp.html` | ordinary |  |
| `root.html` | ordinary |  |
| `stickynote.html` | ordinary |  |
| `variablegroup.html` | ordinary |  |

### `particles_nodes/` (22 files)

| file | class | family / note |
|---|---|---|
| `particleblinkscript.html` | ordinary |  |
| `particlebounce.html` | ordinary |  |
| `particlecache.html` | specialised | Execution / render / export (explicit); explicit button/execute; sim bake .nkpc |
| `particlecurve.html` | ordinary |  |
| `particledirectionalforce.html` | ordinary |  |
| `particledrag.html` | ordinary |  |
| `particleemitter.html` | ordinary |  |
| `particleexpression.html` | ordinary |  |
| `particlegravity.html` | ordinary |  |
| `particleinfo.html` | ordinary |  |
| `particlelookat.html` | ordinary |  |
| `particlemerge.html` | ordinary |  |
| `particlemotionalign.html` | ordinary |  |
| `particlepointforce.html` | ordinary |  |
| `particles_nodes_nukex.html` | non-node / index | non-node: category index |
| `particlesettings.html` | ordinary |  |
| `particlespawn.html` | ordinary |  |
| `particlespeedlimit.html` | ordinary |  |
| `particletogeo.html` | ordinary |  |
| `particleturbulence.html` | ordinary |  |
| `particlevortex.html` | ordinary |  |
| `particlewind.html` | ordinary |  |

### `preface/` (2 files)

| file | class | family / note |
|---|---|---|
| `getting_help.html` | non-node / index | non-node: preface page |
| `reference_guide.html` | non-node / index | non-node: preface page |

### `time_nodes/` (20 files)

| file | class | family / note |
|---|---|---|
| `add_32_pulldown.html` | ordinary |  |
| `appendclip.html` | ordinary |  |
| `frameblend.html` | ordinary |  |
| `framehold.html` | ordinary |  |
| `framerange.html` | ordinary |  |
| `kronos.html` | ordinary |  |
| `notimeblur.html` | ordinary |  |
| `oflow.html` | ordinary |  |
| `remove_32_pulldown.html` | ordinary |  |
| `retime.html` | ordinary |  |
| `smartvector.html` | ordinary |  |
| `temporalmedian.html` | ordinary |  |
| `time_nodes.html` | non-node / index | non-node: category index |
| `timeblur.html` | ordinary |  |
| `timeclip.html` | ordinary |  |
| `timeecho.html` | ordinary |  |
| `timeoffset.html` | ordinary |  |
| `timewarp.html` | ordinary |  |
| `vectorgenerator.html` | ordinary |  |
| `vectortomotion.html` | ordinary |  |

### `toolsets_nodes/` (3 files)

| file | class | family / note |
|---|---|---|
| `create.html` | non-node / index | non-node: ToolSet menu doc |
| `delete.html` | non-node / index | non-node: ToolSet menu doc |
| `toolsets_nodes.html` | non-node / index | non-node: category index |

### `transform_nodes/` (27 files)

| file | class | family / note |
|---|---|---|
| `adjustbbox.html` | ordinary |  |
| `blackoutside.html` | ordinary |  |
| `camerashake.html` | ordinary |  |
| `card3d.html` | ordinary |  |
| `cornerpin2d.html` | specialised | Tracking, solve & match-move data; explicit button + Viewer; tracking/solve data |
| `crop.html` | ordinary |  |
| `gridwarp.html` | specialised | Roto, paint & warp editing; Viewer-interactive; mesh/shape editing |
| `gridwarptracker.html` | specialised | Tracking, solve & match-move data; explicit button + Viewer; tracking/solve data |
| `idistort.html` | ordinary |  |
| `lensdistortion.html` | specialised | Analysis, solve & dialog buttons; explicit button/execute; grid/line detection; NukeX |
| `mirror.html` | ordinary |  |
| `pointsto3d.html` | specialised | Tracking, solve & match-move data; explicit button + Viewer; tracking/solve data |
| `position.html` | ordinary |  |
| `reconcile3d.html` | specialised | Tracking, solve & match-move data; explicit button/execute; create-keyframes bake (`nuke.execute`) |
| `reformat.html` | ordinary |  |
| `sphericaltransform.html` | ordinary |  |
| `splinewarp.html` | specialised | Roto, paint & warp editing; Viewer-interactive; mesh/shape editing |
| `stabilize.html` | specialised | Tracking, solve & match-move data; explicit button + Viewer; tracking/solve data |
| `stmap.html` | ordinary |  |
| `tile.html` | ordinary |  |
| `tracker.html` | specialised | Tracking, solve & match-move data; explicit button + Viewer; tracking/solve data |
| `transform.html` | ordinary |  |
| `transform_nodes.html` | non-node / index | non-node: category index |
| `transformmasked.html` | ordinary |  |
| `tviscale.html` | ordinary |  |
| `vectorcornerpin.html` | ordinary |  |
| `vectordistort.html` | ordinary |  |

### `views_nodes/` (9 files)

| file | class | family / note |
|---|---|---|
| `anaglyph.html` | ordinary |  |
| `joinviews.html` | ordinary |  |
| `mixviews.html` | ordinary |  |
| `oneview.html` | ordinary |  |
| `reconverge.html` | ordinary |  |
| `shuffleviews.html` | ordinary |  |
| `sidebyside.html` | ordinary |  |
| `split_and_join.html` | non-node / index | non-node: doc page (OneView+JoinViews) |
| `views_nodes.html` | non-node / index | non-node: category index |

## Coverage proof

- Inventory: 27 directories, 541 files, 0 duplicates.
- Table rows: 541, each (directory, file) once (compared programmatically against the inventory; set difference empty both ways).
- Class totals: ordinary 441 + specialised 68 + non-node 32 = 541; unresolved gaps: none.
- Evidence basis: classes rest on the prior five audits plus the explicit controls/buttons of the pages checked for each specialised row (including a re-read of the 3dnew USD rows); "ordinary" means no explicit run/bake/pick action was found. This is not a claim that every one of the 541 pages was read line by line.
