---
id: "topics/output-execution"
kind: "topic"
title: "Executing disk-output nodes: Write, DeepWrite, WriteGeo, GeoExport, caches, LUTs, Encryptomatte, Profile"
category: "scripting"
summary: "Exact classes, file knobs and run method for file-writing nodes: nuke.execute for Write/DeepWrite/WriteGeo/GeoExport/FieldVolumeWrite/PrmanRender, cache_particles_panel for ParticleCache, buttons for GenerateLUT/GeoSequencer, Encryptomatte exportWrite, Profile timers."
aliases: ["nuke.execute write", "render write node python", "DeepWrite python", "WriteGeo execute", "GeoExport execute", "FieldVolumeWrite", "ParticleCache render", "cache_particles_panel", "GenerateLUT generate", "make LUT python", "Encryptomatte exportWrite", "GeoSequencer clip_generate_button", "PrmanRender RIB dump", "export cryptomatte exr", "Profile node python", "performanceInfo", "startPerformanceTimers"]
tags: ["python", "execute", "write", "deepwrite", "writegeo", "geoexport", "particlecache", "generatelut", "encryptomatte", "geosequencer", "prmanrender", "fieldvolumewrite", "profile"]
requires: ["fundamentals/time-sampling", "fundamentals/channels-data"]
related: ["nodes/write", "topics/analysis-python", "topics/camera-geometry-operations", "topics/3d-particles", "topics/alembic", "fundamentals/quality-safeguards"]
nodes: ["Write", "DeepWrite", "WriteGeo", "GeoExport", "GeoSequencer", "FieldVolumeWrite", "ParticleCache", "GenerateLUT", "CMSTestPattern", "Encryptomatte", "PrmanRender", "Profile"]
version: "Nuke 17.1v1 installed reference docs, Python Dev Guide, shipped nukescripts source (renderpanel.py, renderdialog.py) and plugin binary strings (embedded Encryptomatte script, Executable symbols). Static; nothing executed. NukeX/Studio, RenderMan 20 or earlier (PrmanRender) and LABS status (FieldVolumeWrite) apply."
source_ids: ["foundry-17.1"]
---
# Executing disk-output nodes: Write, DeepWrite, WriteGeo, GeoExport, caches, LUTs, Encryptomatte, Profile

## Applicability
Use when the user asks to render, export, cache, generate a file or time a script with one of these nodes. Paths, frame ranges, channels and file formats come from the user; never invent them, and ask if missing. Four kinds:
1. **Executable** (run with `nuke.execute`): Write, DeepWrite, WriteGeo, GeoExport, FieldVolumeWrite, PrmanRender (dumps RIB, not images).
2. **Button-only**: ParticleCache (its Render button runs a shipped function), GenerateLUT (`generate`), GeoSequencer (`clip_generate_button`).
3. **Creates a node, runs nothing**: Encryptomatte `exportWrite`.
4. **Measures, writes no file**: Profile (timers, not `nuke.execute`).
Execute/Render buttons backed by `execute_panel this` open a modal frame-range dialog; call `nuke.execute` instead. Ordinary nodes and other `reload` or dialog buttons are not part of this topic.
Saving the .nk script is separate (nuke.execute does not save it): use the user-approved path or the script's existing path, never one derived from a Read/media filename; if untitled with no approved destination, ask first (an explicit user instruction may allow beside the media).

## Workflow
Common run, shown with Write (`file` knob differs per node, e.g. FieldVolumeWrite `filename`; see below). Input connected, node enabled, path from the user, folder exists (Write: `create_directories`; else `os.path.isdir`), range from the user (or root `first_frame`/`last_frame` for "full range"):
```python
import os
n = nuke.toNode('Write1')
n['file'].setValue('/shots/sh010/out/sh010_v001.%04d.exr')
nuke.execute(n, 1001, 1100, 1)   # blocks; error or cancel raises RuntimeError
print([f for f in range(1001, 1101) if not os.path.isfile(n['file'].value() % f)])   # missing frames
```

### Write and DeepWrite
Write: `file`, `file_type`, `channels` (default rgb: alpha/AOVs need e.g. `rgba` or `all`), `colorspace`, `create_directories`, `first`/`last`/`use_limit`, `frame_mode`, `views`; `reading` passes the written file downstream. DeepWrite: deep input only, scanline EXR only, `channels` default rgba, `file_type` exr, `datatype` (16 bit half/32 bit float), `compression`, `metadata`; its Render button opens a dialog: use `nuke.execute(dw, first, last, 1)`.

### Encryptomatte export
`exportWrite` runs a shipped script: `nuke.nodes.Write()` wired to the Encryptomatte output, `channels`='all', `file_type`='exr', `datatype`='32 bit float', `metadata`='all metadata'. It sets no `file` and renders nothing.
```python
e = nuke.toNode('Encryptomatte1')
before = set(nuke.allNodes('Write'))
e['exportWrite'].execute()
w = (set(nuke.allNodes('Write')) - before).pop()
w['file'].setValue('/shots/sh010/mattes/sh010_crypto.%04d.exr')   # user path
nuke.execute(w, 1001, 1100, 1)
```
Preconditions: input 0 is the new matte, the unnamed input carries the existing Cryptomatte passes, `matteNameType` auto (source node name) or manual with non-empty `matteName` (empty: node does nothing), `mergeOperation` (default over), a layer on the Cryptomatte layer knob (`cryptoLayer` appears in the binary; confirm with `allKnobs()`). Read back: Read the EXR, confirm layer channels and `cryptomatte` metadata keys [INFERENCE from the Cryptomatte format].

### WriteGeo, GeoExport, FieldVolumeWrite
- WriteGeo: `file`, `file_type` (none/abc/fbx/obj; abc and fbx need a Scene input), abc `writeGeometries`, `writePointClouds`, `writeCameras`, `writeAxes`, `storageFormat` (HDF/Ogawa); fbx adds `writeLights`, `asciiFileFormat`, `animateMeshVertices`; `use_limit`/`first`/`last`. `nuke.execute(wg, 1001, 1100, 1)`.
- GeoExport (USD stage): `file`, `file_type` (abc default, fbx, obj, ply, splat, spz, usd, usda, usdc), `stitched_export`, `export_method` ('Flatten All' or 'Flatten Sublayers, Keep References', default), `usd_file_format` ASCII/Crate, abc `bake_xform_ops`, ply/spz spherical harmonics (name has a space in docs: `allKnobs()`). Only the graph below the lowest GeoBreakLayer exports; a PLY cannot mix meshes and splats.
- FieldVolumeWrite (LABS): file knob is `filename` (not `file`); `voxel_size` (0.01), `grid_type` (Float), `grid_name`, `bounds_specifier` (Field/Custom); Executable: `nuke.execute` over the user's range.

### ParticleCache: compute vs write
Render writes `.nkpc` files; with `particle_cache_read_from_file` off the system is still simulated live, on it reads the files. The Render button runs `nukescripts.cache_particles_panel`: sets `particle_cache_render_in_progress`, disables Undo, runs `nuke.executeMultiple` over root first_frame − `particle_cache_padding` to last_frame + padding (default 1).
```python
import nukescripts
pc = nuke.toNode('ParticleCache1')
pc['file'].setValue('/cache/sh010/parts.####.nkpc')   # user path
nukescripts.cache_particles_panel(pc)                 # root range; ask before changing the project range
print(pc['particle_cache_render_in_progress'].value())  # must be 0 afterwards
```
For playback from cache (only if wanted), set `particle_cache_read_from_file` True. "Particle cache data not found": raise `particle_cache_padding`, re-render. Node must be at the bottom of one particle stream. A custom range via `executeMultiple` bypasses the flag handling: unsupported unless accepted.

### GenerateLUT
Chain: `CMSTestPattern` (`cube_size`, default 32; sets the 3D LUT size) → the user's colour nodes → GenerateLUT. Knobs: `file`, `file_type` (auto from .3dl/.blut/.cms/.csp/.cub/.cube/.vf), `lut1d`, `style1d`, .3dl `bitdepth_id`, `output_bitdepth_id`, `clamp_output`, `format_3dl_id`. Press `n['generate'].execute()`; check the file exists and is non-empty.

### GeoSequencer (converter, not Executable)
No `nuke.execute`. Set `convert_method` (PLY/SPLAT, time-sampled USD, or non-time-sampled USD sequence), `convert_source_files`, `sequence_files` (`name.###.usdc`, dots required), `output_file`, `range_first`/`range_last`, `conversion_primitive_path` (valid prim path, default /root); then `n['clip_generate_button'].execute()`. With `create_import_after_generation` on, a GeoImport is added: find it by diffing `nuke.allNodes('GeoImport')`.

### PrmanRender
Execute dumps RIB to `file` (use `####`); needs licensed RenderMan Pro Server 20 or earlier; `nuke.execute(pr, first, last, 1)`. For images, execute a Write downstream.

### Profile (not a writer)
Knobs `channels`, `frame_range`, `open_profile_panel` (GUI pane shows results; no documented script readback). For scripted numbers: `nuke.startPerformanceTimers()`, `nuke.resetPerformanceTimers()`, render the user's frames, then `n.performanceInfo(nuke.PROFILE_ENGINE)` (also `_STORE`, `_VALIDATE`, `_REQUEST`): `callCount`, `timeTakenWall`, `timeTakenCPU` in µs; then `nuke.stopPerformanceTimers()`.

## Verify
Check files exist, are non-empty and cover the whole range; for images/EXR open a Read and compare channels, format and colorspace; for geometry or USD read back with ReadGeo/GeoImport; for a LUT compare the header size with `cube_size`; for caches confirm the render flag cleared. Report exceptions verbatim.

## Pitfalls
- Unsupported or unverified: headless behaviour of `generate` and `clip_generate_button` (not run); ParticleCache over a non-root range; image output from PrmanRender itself; Profile pane results by script; GeoSequencer source-file knob format beyond the docs; deriving paths, ranges or channels the user did not give.
- `nuke.execute` on a node without Executable (Merge, Grade, GeoSequencer) raises.
- Save destination: do not invent a .nk path from media names; use the approved or existing script path, or ask.
- Do not reuse a path that already holds the user's files without confirming it.
- Rendering at proxy scale writes proxy output; check `nuke.root().proxy()`.
- Licence, class and LABS status must be confirmed on the user's build.

## Sources
- /opt/Nuke17.1v1/Documentation/html/content/reference_guide/ pages: write, profile, deepwrite, writegeo, prmanrender, geoexport, geosequencer, fieldvolumewrite, particlecache, generatelut, cmstestpattern, encryptomatte
- /opt/Nuke17.1v1/plugins/nukescripts/{renderpanel,execute,renderdialog}.py; strings of Encryptomatte.so, libDDImage.so, GenerateLUT.so, GeoSequencer.so
- Python Dev Guide: performance.html, nuke.execute
