---
id: "topics/picker-keyers"
kind: "topic"
title: "Viewer-picker keyers through Python: Primatte, Ultimatte, Cryptomatte"
category: "keying"
summary: "What Python can and cannot do for Primatte, Ultimatte and Cryptomatte: scriptable knobs (mode, Auto-Compute, screen_color, matteList, clearMatteList, matteOutput) versus Viewer-only picks, with read-back checks and honest limits."
aliases: ["primatte python", "primatte operation", "primatte samples", "primatte auto-compute", "ultimatte python", "ultimatte screen color", "ultimatte overlay pickers", "cryptomatte python", "cryptomatte matteList", "pickerAdd", "pickerRemove", "clearMatteList", "cryptomatte id", "encryptomatte", "crypto matte list", "viewer picker keyer"]
tags: ["keying", "primatte", "ultimatte", "cryptomatte", "python", "viewer-picker", "matte"]
requires: ["fundamentals/alpha-premultiplication", "fundamentals/channels-data", "fundamentals/keying-conventions"]
related: ["topics/chroma-keying", "topics/analysis-python", "topics/viewer-sampling", "topics/combine-keys", "nodes/primatte", "nodes/keylight", "nodes/channelmerge", "nodes/copy"]
nodes: ["Primatte", "Ultimatte", "Cryptomatte", "Encryptomatte", "Grade", "Copy"]
version: "Nuke 17.1v1 installed docs (keyer_nodes, comp_environment/cryptomatte) and strings of plugins/Primatte.so, Ultimatte.so, Cryptomatte.so; source-derived, NOT runtime verified. Primatte/Ultimatte may need a licence."
source_ids: ["foundry-17.1"]
---
# Viewer-picker keyers through Python: Primatte, Ultimatte, Cryptomatte

## Applicability
Use when Primatte, Ultimatte or Cryptomatte must be created, configured or driven from Python. They are mainly Viewer-pick tools (Ctrl/Cmd+click, Ctrl/Cmd+Shift+drag). Foundry documents no Python call that performs a pick, and the installed Nuke ships no `cryptomatte_utilities` module. Set documented knobs, read them back, and say plainly which picks the user must make in the Viewer. Never invent a pick API or an ID-to-colour conversion.

## Workflow
### Primatte
```python
assert src is not None and nuke.exists(src.fullName()), "source node missing"
p = nuke.nodes.Primatte()                           # nuke.nodes does not auto-connect
print(p.maxInputs())   # maxInputs, not inputs(): inputs() counts only connected slots; Node.inputLabel does not exist in Python
p.setInput(0, src)     # confirm which port is "fg" with nuke_action inspect (ports) before relying on the index; stop if unsure
print(p["algorithm"].values(), p["mode"].values())               # use exact labels
nuke.show(p); nuke.connectViewer(0, p)
p["Auto-Compute"].execute()          # buttons "Auto-Compute", "Reset"; only after fg is connected
p["mode"].setValue("Clean BG Noise") # the OPERATION menu is knob `mode`
```
- `mode` labels: Smart Select BG Color (default), Clean BG Noise, Clean FG Noise, Matte Sponge, Make FG Trans., Restore Detail, Spill Sponge, Spill(-), Spill(+), Matte(-), Matte(+), Detail(-), Detail(+), Fine Tuning Sliders, 3D Sample, Simple Select BG Color. Arrow buttons run `knob mode [expression clamp(mode+1,0,15)]`.
- Samples: no supported Python pick call was verified here; this recipe uses a manual Viewer pick (Ctrl/Cmd+click or Ctrl/Cmd+Shift+drag with the `currentColor` eyedropper pushed in). Whether setting `currentColor` triggers a native sample callback is unknown; untested, do not rely on it. Setting `mode` alone is not a pick. Tell the user which operation and region (Clean BG Noise on grey in the screen; Clean FG Noise on grey inside the subject; Spill Sponge on tinted foreground).
- Other knobs: `graintype`, `graintolerance`, `adjustLighting`, `lightingSPoly`, `lightingGridSize`, `hybridRender`, `hybridErode`, `hybridBlurRadius`, fine tuning `spill` `matte` `detail`, `spillProcess`, `replaceColor`, `defocus`, `output_mode`, `output`, `crop`, `mask`, `invert_mask`.
- Primatte works in sRGB; for premultiplied/unpremultiplied output add Colorspace nodes per the Foundry note. Studio policy: Copy its alpha to retained RGB.

### Ultimatte (inputs hm, gm, bg, cp, fg)
```python
assert src is not None and nuke.exists(src.fullName()), "source node missing"
u = nuke.nodes.Ultimatte()                          # no auto-connect to the selection
print(u.maxInputs(), u["overlay_mode"].values(), u["output_mode"].values())   # Node.inputLabel does not exist in Python
u.setInput(4, src)                                   # port order hm, gm, bg, cp, fg: fg is index 4; confirm with nuke_action inspect ports
u["overlay_mode"].setValue("screen"); u["output_mode"].setValue("composite")
print(u["screen_color"].value())     # default 0; compare after the user's screen pick
```
- Knobs: `screen_color`, `overlay_mode` (off/screen/subject), `overlay_mono`, `overlay_color`, `output_mode`; `brights` `darks` `edge_kernel` `warm` `cool`; enables `film` `screen_correct` `shadow` `spill_suppression` `cleanup` `color_conformance`; `screen_tolerance` `screen_shrink` `screen_orphans`; `shadows_*`; `spill_*`; `cleanup_*`; `color_*`; `film_*`; `reset` buttons.
- Picks happen in the Viewer toolbar (screen, overlay add/remove, matte +/-, hold shadow, remove noise, spill, match). No documented knob holds the keep/remove lists and no documented Python call adds to them; plugin strings `setBGSample`/`setFGSample` are internal and undocumented: do not call them. Plan: enable sections, set `overlay_mode`, ask the user to pick, then read `screen_color` back. If an overlay pick shows no change, Undo or Screen Correct `reset` (keep/remove conflict).

### Cryptomatte (selection is text, so scriptable)
```python
assert read is not None and nuke.exists(read.fullName()), "source node missing"
c = nuke.nodes.Cryptomatte(); c.setInput(0, read)
print(c["cryptoLayerChoice"].values(), c["manifestSource"].values())
c["cryptoLayerChoice"].setValue(c["cryptoLayerChoice"].values()[0])
c["matteList"].setValue("bunny\nscorpion*\n-scorpion1")   # one entry per line
c["matteOutput"].setValue("rgba.alpha"); print(repr(c["matteList"].value()))
# Optional separate reset (NOT part of the main recipe, it deselects everything): c["clearMatteList"].execute()
```
- Matte List: names, `*` wildcard, `-name` exclusion, `*` alone = all. Names come from the manifest JSON (`"bunny": "13851a76"`, embedded in EXR metadata or sidecar via `sidecarFilepath`); read it only to look up names.
- ID encoding is internal (MurmurHash3_32, uint32_to_float32, the only supported pair); do not hand-convert. Missing manifest shows `<float>` entries.
- `pickerAdd`/`pickerRemove` are eyedropper swatches documented for Viewer clicks; no Python use is verified here. Remove deletes only exact ID lines, not wildcards. Use `matteList` from Python.
- Native plugin lacks gizmo knobs `matteOnly`, `previewMode`, `singleSelection`. Use the matte: `Grade` mask input = Cryptomatte. `Encryptomatte` upstream adds a matte; Write all channels, exr, 32-bit, all metadata.

## Verify
- Class of the created node is right; licence or creation errors reported, not faked.
- Primatte/Ultimatte: view alpha and composite; state which picks were not made.
- Cryptomatte: `matteList` reads back as set; matte channel non-empty where expected (a name absent from the manifest gives an empty matte).

## Pitfalls
- Claiming a Primatte/Ultimatte pick from Python; setting `mode` is not a pick.
- Wrong knob names: Primatte operation is `mode`; Cryptomatte layer is `cryptoLayerChoice`.
- Auto-Compute without a connected fg: `primatte error: autodetection failed`.
- Half-float or rgba-only Cryptomatte data loses the layers.

## Sources
- Foundry 17.1 docs: keyer_nodes/primatte, ultimatte, cryptomatte; comp_environment/cryptomatte/keying_with_cryptomatte.
- Strings of /opt/Nuke17.1v1/plugins/Primatte.so, Ultimatte.so, Cryptomatte.so; Encryptomatte in toolbars.py.
