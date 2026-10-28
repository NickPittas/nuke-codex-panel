---
id: "topics/interface-keyframes"
kind: "topic"
title: "Creating and editing keyframes in the interface"
category: "interface"
summary: "The mechanics of setting, finding, moving and deleting keys with the animation menu, Viewer timeline, Dope Sheet and Curve Editor, including RotoPaint/Roto autokey behaviour."
aliases: ["set key", "animation button", "dope sheet", "curve editor", "delete keyframe", "autokey", "paste keyframes", "move keys in time"]
tags: ["keyframes", "dope sheet", "curve editor", "autokey", "timeline"]
requires: ["fundamentals/time-sampling", "fundamentals/node-selection"]
related: ["topics/keyframe-animation", "topics/interface-navigation", "topics/rotoscoping-masking"]
nodes: ["Roto", "RotoPaint", "TimeOffset", "Tracker"]
version: "Nuke 17.1 documentation; check installed node generation and licence."
source_ids: ["foundry-17.1", "brinkmann-2e", "lesson-11"]
---
# Creating and editing keyframes in the interface

## Applicability
Use for the operational question "how do I put a key here, find it, move it, or remove it". Whether the interpolation, spacing and values are good is `topics/keyframe-animation`. Keys live on knobs of a node; the frame number belongs to the script's time at that node. Shortcuts are 17.1 documentation defaults; studios can rebind them.

## Workflow
1. **Set a key.** Cue a frame in the Viewer, click the animation button beside the knob, choose *Set key*. The field turns blue and Nuke is now in autokey mode for that knob: changing the value at another frame creates another key. Right-clicking the properties panel and choosing *Set key on all knobs* keys a whole node.
2. **Find keys.** The scrub bar marks keyed frames in blue; the Viewer's previous/next keyframe buttons jump between them.
3. **Remove keys.** At the key's frame choose *Delete key* from the animation menu for one key, or *No animation* (confirmation dialog) to remove the animation; the static value becomes the value at the current frame.
4. **Dope Sheet** (tab, or right-click the Node Graph title bar > Windows > Dope Sheet). It lists nodes with open panels (or those with the *dope sheet* option / Alt+D) and their animated knobs. Marquee-select keys, move them by typing an offset in the Move field (keys cannot be moved past other keys), copy/paste with Ctrl/Cmd+C/V (pasted relative to the current frame; use Edit > Paste > Paste Absolute to keep source frames), add keys with Ctrl/Cmd+Alt+click, delete with Delete/Backspace.
5. **Curve Editor** (animation menu > Curve Editor). X is time in frames, Y is the knob value. Click a curve to select it, drag points, Ctrl/Cmd+drag for free movement, double-click a value to type it, and use Edit > Generate for regularly spaced keys (this bakes a key on every frame, see Pitfalls). Frame Snap rounds key time to integer frames; hold Shift to move off-frame.
6. **Roto/RotoPaint shapes.** Autokey is on by default in the tool settings: editing a shape at a new frame creates a key. With autokey off, create keys with right-click > set key > all, spline, transform or attributes; points can only be edited at an existing key.

## Verify
- The scrub bar has blue marks exactly where intended, and the node's animation indicator is present.
- Scrub across the range; values change only between the intended keys.
- If a TimeOffset, Retime, TimeWarp, FrameRange, AppendClip or TimeClip lies between the animated node and the active Viewer input, the Dope Sheet shows keys where their effect appears, shifted by that node (a 5-frame TimeOffset moves keys at 0/10/20/30 to 5/15/25/35). The key itself is still stored at its original frame.

## Pitfalls
- A knob receiving an expression or a clone link is not animated by hand; check the node indicators.
- If one animated node reaches the Viewer by several paths, the Dope Sheet shows it several times; editing one edits all.
- Moving or pasting keys in the Dope Sheet changes script time on that knob, not the image clip; repositioning clips uses Read/TimeClip/TimeOffset bars.
- Brinkmann, Chapter 7 (Keyframing) and Chapter 9 (Curve Editors), define the same concept of keys plus interpolation that this interface exposes.
- Course practice (lesson-11, historical ASR): every Roto shape has its own keys and its own key range, so place keys per shape where that shape's motion changes rather than on one shared cadence. *Generate* turns interpolation into a key per frame; afterwards each point is a manual sample and moving one distorts the curve. Use it only when per-frame values are wanted, not to make editing easier. Key spacing sets speed: closer keys play faster, scaled-out keys slower.

## Sources
- Foundry Nuke 17.1, Animating Parameters (animation menu, Dope Sheet, Curve Editor): https://learn.foundry.com/nuke/17.1/content/getting_started/using_interface/animating_parameters.html
- Foundry Nuke 17.1, Animating Strokes/Shapes: https://learn.foundry.com/nuke/17.1/content/comp_environment/rotopaint/animating_strokes_shapes.html
- Foundry Nuke 17.1, Using the Viewer Controls (keyframe buttons): https://learn.foundry.com/nuke/17.1/content/getting_started/using_interface/using_viewer_controls.html
- Brinkmann 2e, Chapter 7 Time and Temporal Manipulations (Keyframing); Chapter 9 (Curve Editors).
- Lesson 11.srt (lesson-11; ASR, teaching-practice only): 00:02:39–00:03:04 per-shape keys; 00:08:36–00:09:52 key spacing sets speed; 00:22:43–00:24:03 Generate bakes a key per frame. Foundry 17.1 remains authoritative for menus and shortcuts.
