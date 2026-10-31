# Proposal: first-party Nuke references for failed-tool-call recovery (REVIEW ONLY)

Status: research proposal. Nothing here is enabled, injected, or added to `nuke_codex_panel/knowledge/`. It is not a skill.
Sources: Foundry docs read on 2026-10-29. "17.1" URLs were fetched directly. Unversioned `/nuke/content/...` and `/developers/latest/...` URLs currently serve 17.1v2 (page chrome shows "Nuke 17.1v2 docs"), but "latest" will drift, so pin 17.1 URLs before relying on them.
Scope guard: no bouncing-ball recipe, no book content, no unofficial API. Nothing in this file is to be fed to models automatically. Any excerpt needs separate user approval first.
Evidence labels used below: **[read]** = stated on a Foundry/Anthropic/MCP page I fetched. **[trace]** = seen in a saved run. **[inferred]** = my extrapolation, not stated by a source.

## 0. Key finding from the saved traces (why docs alone are not enough)

The Luna clean run (`/tmp/nuke-ball-benchmark-CxRVRC/approved-luna-clean/events.jsonl`) shows the model was served `nodes/checkerboard` guidance saying "`color0`-`color3`, `format`". The runtime then rejected it:
`node CheckerBoard1 (CheckerBoard) has no knob 'color0'`, with `candidates: ["gl_color","tile_color"]` and a hint to use `inspect ... match=<text>`.

- The Foundry reference page documents `format`, `boxsize`, `color0..3`, `linecolor`, `centerline*`: https://learn.foundry.com/nuke/17.1/content/reference_guide/image_nodes/checkerboard.html
- The installed node class is `CheckerBoard`, and it lacks those knobs. The page does not name the script class. The existing corpus already says "CheckerBoard2 is commonly seen ... confirm with node.Class()" (`knowledge/nodes/checkerboard.md`). I did not verify this class-name theory against the install.
- Conclusion [inferred from one trace plus the page]: static docs described knobs the installed class did not have, so the runtime's own knob list must stay authoritative. Class/knob mismatches matter for any reference we point to, even though the background-scene fix (#1) is out of scope. A recovery message that lists the real knobs, ranked by relevance, is likely more useful than a page. The `candidates` list in the trace (`gl_color`, `tile_color`) did not contain the intended colour knobs, so it was not useful in that case.

## 1. Artist/task guidance suitable for OPTIONAL skills (short, generic, task-level)

| Topic | What Foundry says | Source |
|---|---|---|
| Merge A/B meaning | B is the lower/background layer, A the upper/foreground. Default op `over` layers A over B by A's alpha. More A inputs (A2, A3...) stack on top, B stays at the bottom. `mask` is a separate optional third input, not A/B. | Merge ref https://learn.foundry.com/nuke/content/reference_guide/merge_nodes/merge.html ; walkthrough https://learn.foundry.com/nuke/content/comp_environment/merging/merges.html |
| Roto / RotoPaint basics | [read] Roto is for Bezier and B-spline shapes. It has `bg` and optional `mask` inputs, and `output` defaults to `alpha`. Shapes live in the `curves` shape list, each with its own transform (translate/rotate/scale/center). (The page's Lifetime-tab default of "single frame" is omitted on purpose: I did not verify whether it applies to shapes only or also to paint strokes, and it is not needed for this task.) | https://learn.foundry.com/nuke/17.1/content/reference_guide/draw_nodes/roto.html |
| Shape animation (GUI model) | Autokey is on by default. Changing a point or attribute at a new frame creates a key. With autokey off you can only edit at an existing key, or set one via set key > all / spline / transform / attributes. Keys on spline, transform and attributes are separable. | https://learn.foundry.com/nuke/17.1/content/comp_environment/rotopaint/animating_strokes_shapes.html |
| Interpolation between keys (ordinary knob curves only) | [read] The Curve Editor offers these interpolation types: Constant (holds the value after each point), Linear (straight lines between keys, sharp changes at keys), Smooth (tangent slopes set from neighbouring keys but clamped so the curve does not exceed key values), Catmull-Rom (like smooth but the curve can exceed key values) and Cubic (continuous second derivative). Before/After set constant or linear behaviour beyond the first/last key. `AnimationKey` documents SMOOTH as the default interpolation for the Python key class. This applies to ordinary knob curves. I make no claim here about Roto shape or transform curves, and no recommendation about which type to use. | https://learn.foundry.com/nuke/content/getting_started/using_interface/animating_parameters.html (Curve Editor > "Interpolating Parts of a Curve") ; https://learn.foundry.com/nuke/developers/17.1/pythondevguide/_autosummary/nuke.AnimationKey.html |
| Animate a normal parameter | Keys: animation button > Set key, change the value at another frame, then scrub to preview. Keys show in the Dope Sheet and Curve Editor. | same Animating Parameters page |
| Review / frame evidence | Scrub or jump to specific frames, view single channels (A for alpha), sample pixels with the Viewer info bar, use Flipbook or Capture for motion review. The Viewer caches displayed frames, so a stale cache is a real possibility. | https://learn.foundry.com/nuke/content/getting_started/using_interface/using_viewer_controls.html ; https://learn.foundry.com/nuke/content/comp_environment/rendering/flipbooking_sequences.html |
| Video walkthrough | Foundry's "Step Up to Nuke" Rotoscoping tutorial is embedded on the Roto page (Vimeo: https://vimeo.com/62691887). It covers draw, close, keyframe at multiple frames, per-shape ops, feather per point, and wiring Roto to the Merge `mask` input. Its transcript is on the Roto page. The Merge page embeds "Constructing Node Networks" (https://vimeo.com/62691396), which says "B is the lower layer, A the upper layer". | Roto and Merge reference pages above |

Generic application (no page stuffing):
- Keep each excerpt to 2-4 sentences with one URL, as in Section 4.
- If any selection is ever approved, choose by purpose or by the kind of reference need (for example "what do A and B mean", "how do Roto keys work", "how do I review motion"), not by failure type. Validation errors, such as an unsupported field like `interpolation` on `shape_key`, a missing argument, or an invalid port, are contract problems. They are answered by the tool's own contract and runtime metadata (accepted fields, values, a corrected shape), not by a task page. There is no failure-to-article mapping in this proposal, automatic or otherwise.
- Not preloaded and not automatic. Any surfacing needs user approval first. If approved, at most one short excerpt plus its URL.
- Note: the existing `knowledge/topics/keyframe-animation.md`, `rotoscoping-masking.md`, `nodes/merge.md`, `nodes/roto.md` and `nodes/viewer.md` already cover much of this. Compare against them before adding anything, because the gap may be selection and delivery rather than content.

## 2. Python API references, only when direct Python is actually needed

Foundry's developer docs are API signatures. They are not task docs, and they are version-pinned. Point to them only for `execute_python` needs, not for artist-level tool calls.

- Node inputs by index. `Node.setInput(i, node)`, `Node.input(i)`, `canSetInput(i, node)`, `connectInput(i, node)`, `inputs()`, `maxInputs()`, `minInputs()`: https://learn.foundry.com/nuke/developers/17.1/pythondevguide/_autosummary/nuke.Node.html. [read] The Getting Started guide's Merge example says "A and B inputs (numbers 1 and 0)" with `nuke.nodes.Merge(inputs=[r2, r1])`, so for that Merge example B is index 0 and A is index 1: https://learn.foundry.com/nuke/developers/latest/pythondevguide/basics.html. This is about Foundry's generic Merge. How the panel's own `port` argument handles A/B is a property of this tool and the installed class, and is covered in Section 3.
- Knob discovery. `Node.knobs()` (dict), `allKnobs()`, `Node.knob(name)`, `Node.Class()`, `Node.help()`, `hasError()/treeHasError()` (same Node page). Docs describe the API only. They do not say which knobs a given installed class has.
- Ordinary knob animation. `setAnimated()`, `setValue`, `setValueAt(value, frame[, channel])`, `isAnimated()`, `animation(i)`, `animations()`, `curve.keys()` with `key.x/.y`: https://learn.foundry.com/nuke/developers/latest/pythondevguide/animation.html. `AnimationKey(x, y, interpolation=nuke.SMOOTH, extrapolation=nuke.CONSTANT)`, with interpolation values USER_SET_SLOPE / CONSTANT / LINEAR / SMOOTH / CATMULL_ROM / CUBIC, plus `lslope`, `rslope`, `la`, `ra`: https://learn.foundry.com/nuke/developers/17.1/pythondevguide/_autosummary/nuke.AnimationKey.html. This covers ordinary knob curves.
- Roto/RotoPaint shapes. Access via the node's `curves` knob: `cKnob.rootLayer`, `toElement('Layer1/Brush1')`, and the `nuke.rotopaint` module (`Shape`, `Stroke`, `Layer`, `ShapeControlPoint`, `AnimControlPoint`): https://learn.foundry.com/nuke/developers/17.1/pythondevguide/rotopaint.html. `Shape` has `getTransform()`, `getAttributes()`, `evaluate(curveNum, time)` (0 main curve, 1 feather offset), and `setVisible(time, bool)`: https://learn.foundry.com/nuke/developers/17.1/pythondevguide/_autosummary/nuke.rotopaint.Shape.html.
  - The Roto guide's code samples are Python 2 era (`print shape.name`, `raise TypeError, '...'`) and not directly runnable on 17.1.
  - Gap: I did not find or read a first-party page showing how to set per-key interpolation on shape or transform keys through `nuke.rotopaint` / `_curvelib`. The `AnimationKey` doc covers ordinary knob curves. I did not read the `AnimCTransform` or `AnimControlPoint` pages. Do not infer this API from `AnimationKey`. The runtime's own `help()` and live probing are the authority here.
- Rendering. [read] The `nuke.render` page documents `nuke.execute(nameOrNode, start, end, incr, views, continueOnError)` as executing a named Write node over frames, with a GUI progress meter and a 'cancelled' error: https://learn.foundry.com/nuke/developers/17.1/pythondevguide/_autosummary/nuke.render.html. That page says nothing about other render APIs. Do not generalise it: the panel's existing Viewer capture, which uses `executeMultiple` on the existing Viewer, worked in past real native runs (per Main), and I did not inspect that path.
- Creation. `nuke.createNode` is for the GUI (auto-connects to the selection, opens the panel). `nuke.nodes.<Class>(knob=value, inputs=[...])` is for scripting (no auto-connect, no defaults). Source: basics.html above.

## 3. Runtime/tool-contract details that external docs cannot authoritatively supply

These must be driven by the runtime and schema, never by pages:
1. Which knobs exist on the installed class, with exact names and types. Example: `CheckerBoard` lacks `color0` (Section 0). Use a runtime knob listing, and rank candidates by name similarity and semantics.
2. The tool's own parameters, which are class-specific and tool-defined. Per Main, the current `_port` already accepts A/B for the actual Merge class (`Merge2`), and the create route passes keys through it, so I withdraw my earlier blanket "`port` must be an index, not A/B". That wording came from the observed-rejects list in my assignment, not from a trace I read, and it likely describes one situation only. Runtime input metadata for the specific node class must be authoritative for what a port accepts. The other items come from the same assignment list [not independently verified by me]: `shape_key` does not take `interpolation`, and the review step demanded frames, prose of at least 6 words, an animated review over at least 2 distinct frames including frame 100, and role bind/step sequencing. Foundry cannot know any of these. They belong in the tool schema and in the error text, with the accepted values listed.
3. Partial-mutation state: after a failed multi-step call, what was applied. This must come from the tool's `graph_changed` and result data, never from docs. Do not auto-retry a partially applied mutation.
4. Whether a correction is unambiguous, for example mapping `A`/`B` to input indices. Docs can explain what A and B mean (Merge B = lower layer, A = upper). [inferred] Only the tool can apply a mapping, and only after verifying the node's actual input labels or `maxInputs` at runtime, for that class. Otherwise ask the model to choose.
5. Frame and render evidence: whether a Viewer render completed, was cached, or failed. Foundry only describes that the Viewer caches frames.
6. Class-name aliasing between doc page names and installed script classes (for example CheckerBoard vs CheckerBoard2).
7. Roto API coverage and per-key interpolation on the actual install (see the gap in Section 2).

What can help models vs. what the runtime must do:
- Docs can help: the conceptual layer in Section 1. A/B layering, shape and keyframe workflow, what interpolation modes mean, the review checklist.
- The runtime or schema must do: knob truth, parameter names/values, error enums, partial-apply state, suggested correction candidates, and frame/render evidence.

## 4. Proposed short excerpts (NOT enabled; each would be shown only on its matching failure class)

1. Merge inputs.
   "A Merge's B input is the background (lower layer) and A is the foreground (upper layer). Extra foregrounds attach as A2, A3... and stack above A. `mask` is separate. In Foundry's Python example, B is input 0 and A is input 1. For this tool, use whatever the node's runtime input metadata says."
   Sources: https://learn.foundry.com/nuke/content/reference_guide/merge_nodes/merge.html ; https://learn.foundry.com/nuke/developers/latest/pythondevguide/basics.html
2. Roto keys.
   "Roto/RotoPaint shapes carry separate spline, transform and attribute keys. With autokey on, edits at a new frame add keys. With it off, you can only edit at an existing key, or set one explicitly (set key > all / spline / transform / attributes). Moving the whole shape is normally a transform key, not edits to every point."
   Source: https://learn.foundry.com/nuke/17.1/content/comp_environment/rotopaint/animating_strokes_shapes.html
3. Interpolation.
   "In Foundry's Curve Editor documentation for ordinary knob curves, the interpolation types are Constant, Linear, Smooth, Catmull-Rom and Cubic, and Before/After control behaviour beyond the first and last key. Whether and how these apply to Roto shape or transform curves is not covered by the sources read."
   Sources: https://learn.foundry.com/nuke/content/getting_started/using_interface/animating_parameters.html ; https://learn.foundry.com/nuke/developers/17.1/pythondevguide/_autosummary/nuke.AnimationKey.html (ordinary knob curves only)
4. Review evidence.
   "Judge motion from more than one frame, including the last. Check the alpha (press A in the Viewer) when the matte matters. The Viewer caches frames it has displayed, so confirm the displayed frame is current. Flipbook or Capture are the first-party ways to review motion."
   Sources: https://learn.foundry.com/nuke/content/getting_started/using_interface/using_viewer_controls.html ; https://learn.foundry.com/nuke/content/comp_environment/rendering/flipbooking_sequences.html
5. (Optional) Knob discovery.
   "Reference pages list knobs for the documented node, not necessarily the installed class. If a knob is rejected, list the installed node's real knobs and map by meaning. Do not guess aliases."
   Source: Section 0 evidence plus https://learn.foundry.com/nuke/developers/17.1/pythondevguide/_autosummary/nuke.Node.html (`knobs()`, `Class()`).

## 5. Version and access limitations

- All pages fetched fine without login. Search snippets were used only to find URLs. Claims above come from the fetched pages.
- The unversioned `/nuke/content/` and `/developers/latest/` paths float with releases. They rendered as 17.1v2 today. The Roto, RotoPaint, CheckerBoard and Python-guide pages were fetched via explicit `17.1` URLs where one existed. `animating_parameters`, the Merge reference, the Merge walkthrough, flipbooking and Viewer controls were fetched unversioned.
- The Roto reference shows UI/knob tables. I did not verify these against the installed 17.1v1 build (the user runs `/opt/Nuke17.1v1`). The doc build is 17.1v2. Any per-knob detail must still be checked at runtime.
- The Roto "Python guide" page has Python 2 snippets. The 17.1 `Shape` page documents creation via `_curveknob.Shape(...)`, while the guide says `nuke.rotopaint`. Reconcile on the install, because this doc set is inconsistent about module paths.
- Gaps not covered by first-party docs I read: shape/transform key interpolation through the Python Roto API, and the `_curvelib.AnimCurve` surface mentioned in project memory.
- The Foundry video transcripts exist on the doc pages, but the video content itself was not watched.

## 6. Tool-error design (small first-party note)

- Anthropic: error responses should "clearly communicate specific and actionable improvements, rather than opaque error codes or tracebacks", and can "give examples of correctly formatted tool inputs". Tool responses should be context-efficient (truncate, filter, paginate with steering text). https://www.anthropic.com/engineering/writing-tools-for-agents
- Anthropic API docs: return failures with `is_error: true` and write instructive messages that say "what went wrong and what Claude should try next" (their example is a rate-limit message with a retry time). https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
- MCP spec: tool execution errors, including input validation, are returned in the result with `isError: true`, carry "actionable feedback that language models can use to self-correct", and clients SHOULD pass them to the model. https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- Reading for this project: the recovery payload should hold the specific failing argument, the accepted values or real candidates taken from the live tool contract, one corrected-shape example, and the `graph_changed` state. Broad API pages are not the recommended mechanism. At most, add one short pointer.
- I did not find OpenAI tool-authoring text in this pass, so I make no OpenAI claim.

## 7. Caveat: gate behavior vs. proactive steering

The following was verified by the parent (Main) from source and is relayed here as parent-verified review. I did not read this code myself:
- `bridge/server.py` `_execute_action` does process internal Python `api_errors`.
- Native internal Python returns tracker results before they reach the bridge.
- Ordinary guided validation errors (for example an unsupported field or invalid port) do not trigger the SDK documentation gate.

SDK/API pages are relevant to actual Nuke API errors from executed Python, including internal_python. Ordinary guided validation is tool-contract recovery, not an API-page or task-page matter. This research is not enabled anywhere, and nothing in it is an automatic failure-to-article mapping. Optional proactive steering (tool descriptions or short excerpts, Section 4) would be a separate decision needing user approval.
