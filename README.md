# Nuke Pi

*Nuke Pi* is the visible product name; the repository, Python package (`nuke_codex_panel`) and install folder keep the internal name `nuke-codex-panel`.

A native, dockable agent client for Foundry Nuke. Models can use ordinary, authorized Nuke Python directly, with optional native actions and application-owned workflows, and visual context from the Viewer, Node Graph, and full interface.

The panel runs one agent backend: the **official Pi 1.4.0** coding agent (MIT, `@earendil-works/pi-coding-agent`) on an **official Node.js 26.12.0**, both installed privately by this project's installer under `runtime/pi/`. This is a customized distribution, not a fork: Pi itself is unmodified and this project adds its own extensions (`nuke-runtime.ts`, `auth-helper.mjs`, `credential-env.json`) and the Qt client. Other agent CLIs (Codex, Claude Code, OMP, opencode) are no longer supported by the panel. The model and thinking-level pickers are read live from Pi.

The chat streams answers token by token as Markdown bubbles (headings, lists, tables, quotes, links and code fences render without truncation). Model reasoning, replies, tool calls and delivered images appear as separate blocks **in the order they happen**. Every tool call is its own collapsible bubble with a title, status and elapsed time, formatted arguments and results, and error states; thinking blocks collapse too. Output follows the stream while you are at the bottom and holds your position while you read older content. Chat text scales with **A-** / **A+** / reset in the toolbar or the persistent `chat/font_size` setting (default 11, range 8–24). The panel and its popups use a dark, colorful theme scoped to this plug-in only; Nuke's own styling is never changed.

## Chats, context, and sessions

Chats are saved per project (in the app data dir, keyed by a hash of the script path, so nothing is written into project folders). When the panel opens, the previous conversation for that script is **continued automatically**: the stored Pi session is restored before the agent starts, with no resume question. Send stays disabled until the session is restored, Pi has acknowledged the model and effort, and the Nuke tools are confirmed ready. Resuming keeps the model's context across Nuke restarts. The session is a Pi session file (`--session-dir` + `--session-id`).

**New chat** archives the current transcript to `archive/` and starts with an empty model context. The context bar under the status line shows the current context-window usage (`context 60.0k / 200.0k (30%)`); hover it for the session breakdown (input / cached / output / cost) where the harness reports it.

## Pi runtime

| Item | Value |
|------|-------|
| Agent | official Pi 1.4.0 RPC (`dist/bundle/rpc-entry.js`) |
| Node | official Node.js 26.12.0, private copy |
| Location | `runtime/pi/` inside the installed plug-in (`node/`, `node_modules/`, `manifest.json`, `package.json`, `package-lock.json`, owned extensions, `third-party-notices/`) |
| Nuke tools | native MCP, private `mcp.json` under the per-user data dir, direct exposure plus `codemode` |

No global Node, global Pi, `PATH` lookup, `NUKE_PI_BIN` or QSettings fallback exists: a missing or inconsistent private runtime fails closed with a clear error, and ambient `PI_*`, `JITI_*` and provider-key environment variables are stripped. Only the explicit `builtin:mcp`/`codemode`/`tool-search` extensions plus the project-owned `nuke-runtime.ts` load; skills, prompts, context files, themes and autoload are off, and `--system-prompt` replaces Pi's default coding prompt with the shared Nuke guidance. Nuke tools are declared before the panel reports ready, including after steering renewal. Pi's native MCP request timeout (60 s default) is reset by progress notifications that the Nuke sidecar sends while a request is pending.

**Settings…** shows the private runtime path and status (read-only) and the font size. **Pi accounts…** opens the private account dialog: choose API key or Subscription/OAuth, then any provider from the pinned SDK's full dynamic catalog. SDK prompts (secret key, browser/headless/device select, authorization URL, device code, manual code) appear inline; you open any browser link yourself. Credentials are stored only in the private SDK store, never QSettings, chat, logs or ambient env, and never appear in argv. **Check** resolves credentials locally (and renews OAuth only if needed); **Logout** is local only. Changes reach a running chat through same-session idle renewal without aborting.

See [runtime/pi/README.md](runtime/pi/README.md) for what is pinned and verified.

## Working with the panel

**Managed Pi models.** **Manage models…** opens the account's full available model catalog. Check the models to keep in the ordinary picker and Pi's model-cycling scope, then choose an explicit **Default model** from those checked. **Save** requires at least one model and a checked default; **Cancel** changes nothing. Preferences live in the private Pi `settings.json` (`enabledModels`, `defaultProvider`, `defaultModel`), not a second QSettings shortlist. Selecting all stores those exact models, rather than automatically allowing future additions. Previously saved models that are temporarily unavailable remain listed and retained, but cannot be picked as the default.

The configured default applies to fresh conversations. Continuing a saved conversation keeps its actual SDK model; if that model is no longer allowed, the panel asks for an explicit choice rather than silently substituting the default. Without a configured default or a human selection, a fresh conversation adopts Pi's actual model instead of guessing from catalog order. Model and effort changes must be acknowledged by the SDK before Send becomes ready, along with the current process's Nuke-tool check. The effort you selected is retained across resume and New Chat and verified against Pi's reported level; a mismatch blocks readiness and is reported, with no automatic retry or fallback to another effort. Saving a changed shortlist renews an idle Pi process safely so its native cycling scope matches the picker.

**Send while busy.** The Send box stays usable while the agent works. Sending a message during a run, or prefixing it with `/btw`, is a *manual intervention* (never an automatic one, and not a queued follow-up): the agent's old work is stopped safely and the **same conversation** continues with your message. Nothing ever interrupts a model on a timer; the status line shows received / waiting / delivered state and observational request and tool-time clocks. Cancel stops the run safely and delivers nothing.

- **Pi RPC steering.** The panel's Pi backend implements safe steering; `/btw` and busy Send both use it.
- **Sequence.** A bridge barrier refuses not-yet-started operations of the old run; a Nuke operation already executing cannot be preempted and is allowed to finish, and its result is returned before the run is aborted, so the transcript never records a completed change as aborted. The old agent and its MCP sidecar are permanently retired (a newer process lease `NUKE_CODEX_CONTROL_EPOCH` fences them), confirmed gone, and a replacement process resumes the same persisted session with the same model and effort. Pending forced-shutdown callbacks are cancelled when the old process exits and before a replacement starts, so they cannot terminate the resumed agent. Messages are delivered exactly once, in order; undelivered ones are handed back.
- **Latency.** Steering takes as long as the in-flight Nuke operation (render, capture, long Python) plus the agent/sidecar restart; a second Cancel skips waiting for the in-flight tool result. No generation timeout exists.
- **Not persisted → not resumable.** If the session cannot be resumed, steering and Cancel only stop the agent; it stays parked ("Stopped — use Reconnect") and nothing starts until you press **Reconnect**. A new chat always starts a fresh process.
- **Process ownership.** Each panel-launched MCP sidecar registers itself (control id, epoch, pid, OS process birth identity, executable) under the per-user runtime directory before serving. Before any signal the live process's identity and executable are re-read and compared with the registration, so a reused PID is never signalled; external clients' sidecars never register and are never touched. If identity cannot be verified, steering renewal reports the error and does not start the replacement agent. Linux uses `/proc` identity and pidfd, macOS uses libproc, Windows uses process handles with `TerminateProcess` (no graceful signal exists there, so TERM and KILL both terminate). This is implemented from source for all three; **only Linux has been natively exercised**, and the Windows and macOS paths are unverified.

Managed Pi checks that every bundled Nuke MCP tool is active before accepting a model turn, on both initial connection and steering renewal. Missing tools keep the panel not-ready; a startup failure is shown explicitly instead of allowing a text-only continuation. This readiness check does not interrupt a running model turn.

**New Chat** archives the current transcript and starts a fresh Pi process and session; it never reuses the old conversation. Only one visible, checked pane can hold Trusted Python.

## Python, optional actions and workflows

`execute_python` is the general-purpose path for Nuke work, including creating and connecting nodes, imports and runtime introspection. Two application-owned tools are also available when useful:

- `nuke_action` runs one native step per call and reads the state back: `create` (one visible node, configured in the same call; a failed configuration removes it again), `set`, `inspect`, `connect`, `swap`, `select`, `delete`, `layout`, `project`, `sample`, `render`, `view`, `animate`, Roto/RotoPaint `shape` / `shape_style` / `shape_key`, and `internal_python` (ordinary authorized Python with optional node/Roto bindings, not a node-scoped sandbox). Real classes, knobs, enum labels and ports are used; failures return the actual candidates. The existing Viewer is reused, never added. Free-form knob expressions need user approval. All shape work starts in Roto/RotoPaint.
- `nuke_workflow` keeps application-owned, per-client state: `begin` (families `2d`, `keying`, `cleanup`, `projection`; workflows compose via `nested=true` inside a step), `current`, `bind`, `review`, `advance`, `finish`, `abandon`. The permanent prompt stays small; each step states what it still needs plus focused guidance from the knowledge pack. Only the `2d` family carries the background-first rule: project size/fps → background work and render review → Merge Over with the background on B (input 0) and a graph check → foreground work and review → foreground on A (input 1) → layout (B trunk vertical, A to the side) → composite review (several frames, including the last, for animation) → the merge becomes the next background. The other families follow their own plate/key/3D structure; none of these rules applies universally.
- **Evidence.** A render counts as reviewed only after the image was actually *delivered* to the model; prose accepting or rejecting it is separate. A stale revision or an outside edit invalidates earlier evidence.
- **Authorized Python.** There is no guided/full Python profile, declared node scope, static graph-construction restriction, or mandatory inspection/documentation sequence. Python executes inside Nuke and is not an OS sandbox. Trust, per-call approval, process leases and manual-steering barriers still apply. Runtime failures preserve partial Python changes rather than automatically undoing or replaying them.
- **Plate-led tracking guidance.** For a new plate-led task, compare the primary Read's format, pixel aspect, file frame rate and range with Root; preserve established project settings unless a change is authorized. Reuse unchanged context and already-viewed representative frames, refreshing after relevant changes or uncertainty rather than repeating whole review passes. The on-demand Tracker recipe covers numeric table cells, track-creation evidence and a planned first/last/problem-frame review. Save the `.nk` to its existing path or an explicitly approved destination, never a path invented from the media filename; ask for a destination when an untitled script has none. These are working guidelines, not Python restrictions, capture limits or image caching.

Read/DeepRead `file` assignments use Nuke's native file-loading path, which initializes the source range and format. File loading runs before explicit knob overrides, so a requested trim is preserved regardless of JSON key order. Create, set, and inspect report the configured frame range and format dimensions, including unnamed formats; Write output paths retain ordinary assignment semantics. Nuke's automatic first-Read project-range initialization is declared only when no other stable Root settings changed.

If a later knob fails during Read creation, removing the new node does not undo Nuke's project-range initialization. The failure reports `node_removed` separately from `rolled_back`, preserves the Root changes, and asks the caller to inspect Project Settings before proceeding.


## Requirements

- Foundry Nuke 17+ with PySide6 for the docked panel and live tools.
- A standalone Python 3.11+ (not Nuke's Python) to run the installer; its path is recorded in the install receipt and used to launch the bundled stdio MCP server (the knowledge tools need no Nuke).
- Network access to nodejs.org and registry.npmjs.org during installation only.
- Supported installer platforms: **Linux x64, Windows x64, macOS Intel (x64) and macOS Apple Silicon (arm64)**. **Native verification so far is Linux only**; Windows and macOS support is implemented from the pinned manifest but has not been natively verified (see [Verification status](#verification-status)).
- KDE Wayland capture currently requires `spectacle`; wlroots uses `grim`; other desktops use the available Qt/OpenGL fallbacks.

## Install

Full instructions: [docs/INSTALLATION.md](docs/INSTALLATION.md). The official distribution is the **source tree / sdist plus `install.py`**; a bare `pip install` of the wheel is not a complete installation because the pinned runtime assets are not in the wheel. From the unpacked source, using a standalone Python 3.11+:

```bash
python3 install.py --target ~/.nuke/nuke-codex-panel --nuke-dir ~/.nuke
```

Windows: `py -3 install.py --target "%USERPROFILE%\.nuke\nuke-codex-panel" --nuke-dir "%USERPROFILE%\.nuke"`.

| Option | Meaning |
|--------|---------|
| `--target PATH` | install location (default `~/.nuke/nuke-codex-panel`) |
| `--nuke-dir PATH` | Nuke user directory holding `init.py`/`menu.py` (default `~/.nuke`) |
| `--no-register` | install without touching `init.py`/`menu.py` (for a temporary or test install) |
| `--check` | read-only: verify an existing install (runtime, hashes, Node, licenses, recorded Python) and, unless `--no-register` is also given, the registration; no network |

The installer downloads the official Node archive for your platform (keys `linux-x64`, `win-x64`, `darwin-x64`, `darwin-arm64`) and checks its sha256 against the pinned manifest, then installs the pinned Pi with that private Node (`npm ci --ignore-scripts` against the lockfile, isolated config and cache), stages the owned extensions, and copies the upstream license/notice files (index: `runtime/pi/third-party-notices/index.json`). It stages into a temporary location and activates atomically, so a failed install leaves a working install and your Pi accounts intact; provenance is written to `runtime/pi/install-state.json`. Registration adds a managed block, delimited by `# >>> Nuke Codex Panel >>>` / `# <<< Nuke Codex Panel <<<`, to `init.py`/`menu.py` only after the install is verified, is idempotent, preserves unrelated content and keeps a one-time backup `<file>.nuke-codex-panel.bak-<UTC timestamp>`. Exit codes: 0 ok, 1 failure, 2 usage. `--check` needs no network, and `install.py` is also copied into the target so you can re-run `--check` there.

The registration equals:

```python
# init.py
nuke.pluginAddPath("./nuke-codex-panel")

# menu.py
import nuke_codex_panel.menu
```

Restart Nuke, then open **Pane > Nuke Pi** and sign in with **Pi accounts…**. To uninstall, remove the managed block from `init.py`/`menu.py` and delete the target folder (private Pi accounts live outside the install and are kept).

## One application, one bundled MCP

This project is a single application containing the dockable panel and the MCP server used by external agents. There is no separate server project, second Nuke plugin, or separate virtual environment.

- Importing `nuke_codex_panel.menu` in a Nuke GUI session starts one process-wide, authenticated, loopback-only bridge. It starts at Nuke startup whether or not a Nuke Pi pane is open, and it stays running when a pane is closed. The pane does not own the bridge.
- Pi launches the bundled MCP server. The command and environment come from `nuke_codex_panel/harnesses/nuke_mcp.py` (`server_command()`, `server_environment(bridge_path)`), and the panel is pinned to this Nuke's exact bridge discovery record. The package location, not the active project's working directory, determines `PYTHONPATH`. A panel's bridge pin is not written into persistent configuration; an external stdio entry without a pin keeps auto-discovering the newest live Nuke.
- External MCP clients (optional) can launch the same stdio entry point (`<standalone python> -m nuke_codex_panel.mcp_server.server`). This project provides no config writer or install instructions for any specific external agent product.

### Tools

Five live tools talk to a running Nuke through the bridge, so a Nuke GUI session is required: `nuke_action`, `nuke_workflow`, `execute_python`, `get_nuke_context`, `capture_nuke_screenshot`. Panel-managed and external sidecars expose the same unrestricted, authorized Python interface. An explicit `NUKE_CODEX_BRIDGE_FILE` pin is optional; it only selects which session to use and fails closed if invalid.

Three read-only knowledge tools run directly in the stdio sidecar before bridge dispatch, so they work with Nuke closed or an invalid pin:

- `search_compositing_knowledge(query, limit=3 (1–8), kind=all|topic|fundamental|node)` returns metadata only (`id`, `title`, `kind`, `summary`, `requires`, `version`), never document bodies.
- `get_compositing_guidance(topic_id, section=overview|workflow|verify|pitfalls|full)` returns the chosen section of a router, fundamental or topic document (default `overview`) plus compact metadata and Sources. Prerequisite and related IDs are listed, not expanded recursively.
- `get_node_reference(node, section=overview|inputs|controls|verify|pitfalls|full)` resolves a node ID, title or alias and returns the chosen section with `runtime_verified: false`.

Returned content is capped at 6000 characters including citations, with a truncation flag and the list of available sections. Unknown IDs/nodes give an explicit error with at most three suggestions. Example: search `"keymix vs addmix"`, then `get_compositing_guidance("topics/addmix-keymix", "workflow")`.

Two installed-API documentation tools also run in the sidecar (their filesystem index/search/read work happens in the sidecar process, never on Nuke's GUI thread), but they locate the running Nuke's own `Documentation` directory through the bridge (`Path(nuke.env["ExecutablePath"]).parent / "Documentation"` plus the Nuke version), so they need a live Nuke session:

- `search_nuke_api_docs(query, limit=5 (1–8))` searches the installed documentation (Python API symbols, node and knob documentation) and returns compact matches with opaque `id`s.
- `read_nuke_api_doc(doc_id)` returns one entry by an id a search returned.

Failures are explicit (bridge unavailable, missing Documentation directory, bad id); an empty search returns no results. Documentation and compositing guidance are available on demand, not a prerequisite for executing Python or repairing a failed call.

The pack is 116 packaged Markdown documents under `nuke_codex_panel/knowledge/`: a router, 10 fundamentals, 38 topics (the full curriculum) and 67 node references. It is original, paraphrased guidance citing primary Foundry Nuke 17.1 documentation and Brinkmann's *The Art and Science of Digital Compositing* (2nd ed.) for concepts; there is no PDF dependency and no book text is shipped. Node references are static 17.1 documentation, not live-runtime verification of what your installed Nuke offers.

The teacher-supplied production conventions are encoded as three fundamentals: `fundamentals/graph-conventions`, `fundamentals/keying-conventions` and `fundamentals/quality-safeguards`, cited to the `studio-conventions` source. They are teacher/project requirements, not universal Nuke engine constraints. The shared system prompt in `harnesses/nuke_mcp.py` is deliberately compact: tool roles, the know-the-graph and delivered-image rules, and a short list of studio rules (Roto/RotoPaint first for every shape, native nodes over stand-in expressions, keep project format, readable top-to-bottom graphs, contained bounding boxes, concatenation, separate 3D/projection branches). Family-specific rules (for example background-first/Over/B-A ordering) are delivered by `nuke_workflow` at the step that needs them, and the full conventions live in the knowledge pack, retrieved on demand. Following the detailed conventions therefore depends on workflow guidance or retrieval, not on a universal prompt. This is the teacher's studio workflow, not a claim that Nuke has no image generators.

`execute_python` detects graph changes internally, including connections, layout, knobs, animation, root settings, and nested nodes, and `nuke_action` returns the observed state of what it changed. Results report compact change metadata rather than automatically attaching the graph. Failed operations preserve partial changes, stdout, stderr and traceback. Execution, node, transport and capture failures are returned to the model as errors. The model can inspect the relevant graph state or rendered frames when needed without a forced capture/context loop after every mutation.

**Inspection and image freshness.** Graph revisions and per-client delivered evidence remain available as informational metadata and for optional workflow review. Actual or uncertain changes invalidate earlier graph/image evidence; context and captures do not grant authorization or prove model comprehension. Neither a graph screenshot nor a context call is required before the first or next Python execution. All-scope images frame the root graph; context includes nested nodes and indexed connections.

Root GSV fingerprints include sets, values, declared types, and list options, rather than the inspector's tab-presentation serialization. Presentation-only changes do not invalidate graph evidence; actual GSV and project-setting changes still do.

**API error recovery.** `execute_python` and `internal_python` retain structured failures and runtime-tracked `api_errors`, including errors the script caught itself. Receiver/member-grounded `runtime_evidence` reports what the running Nuke exposes at the failure: controls, choices, members, callable details where available, explicit unknowns and truncation. It does not re-run expressions, evaluate properties or prove that the next call is valid. There is no API-recovery gate, generation-bound documentation ticket or required search/read sequence. The model can repair immediately from the reported state, or consult runtime introspection, installed API documentation and the knowledge pack when useful.

**Inline delivered images.** The shared MCP sidecar notifies the panel when it assembles an image response, using a unique delivery id and SHA-256 of the same PNG bytes sent in the MCP image block. The panel verifies and stores that image as a persistent inline chat preview outside collapsed tool output; clicking opens full resolution. It never recaptures a substitute image. Separate deliveries remain separate previews even when their bytes match. The path is shared by all panel harnesses, with control identity and process-epoch checks to reject foreign or retired deliveries.

**Failure reports.** Both `execute_python` and `internal_python` precompile every original code unit before any mutation, Undo group or namespace binding; raw last-expression result behaviour is unchanged. A failed run returns a structured `failure` with `phase` (`syntax`, `compile`, `setup` or `runtime`), `executed`, `exception_type`, `message`, `location`, `frames` and `effects` (graph delta via the existing `graph_changed`/`added_nodes`/`removed_nodes`/`modified_nodes` fields, plus listed unknowns). Partial changes from a runtime failure are preserved: nothing is automatically undone, replayed or split into smaller scripts.

All-scope graph capture temporarily activates the root Node Graph even when its tab is hidden, then restores the original tab, group, view, and selection. A visible-scope request refuses a hidden DAG instead of capturing another panel. Node Graph capture prefers its native QOpenGLWindow framebuffer and retains blank-image and all-scope completeness checks.

Bridge requests are serialized even during nested Qt event loops. Screenshot requests have no response deadline: `capture_nuke_screenshot(target="viewer", frame=N)` waits for the existing Viewer's synchronous render to complete, without a settling delay or stale-image fallback. Failed renders and errors in the displayed upstream tree are explicit errors, even if Nuke wrote an error-plate image. Metadata identifies the requested/rendered frame, Viewer inputs and process, timestamp, actual viewport-image dimensions, and separate project-format dimensions. Full-interface captures also wait for the active Viewer render, but remain UI-only screenshots—not certified frame-pixel evidence. Capture restores its temporary Viewer file setting and graph view/selection; genuine edits made during rendering retain their unsaved state.

The panel's Viewer button uses the same synchronous image-render path. These are viewport renders rather than full-interface screenshots; the framing interface adds no controls for Roto or Tracker overlays.

**Viewer detail inspection.** `nuke_action` `view` and `render`, and `capture_nuke_screenshot(target="viewer")`, accept `zoom` (a positive percentage or `"fit"`), `center=[x,y]`, or `region=[x0,y0,x1,y1]`. Coordinates are source-image pixels with Nuke's bottom-left origin, not screenshot pixels or the project format. `region` is mutually exclusive with `zoom`/`center` and frames the box in the existing Viewer; the PNG remains viewport-sized and can include surrounding context. Framing persists for inspection and creates no QC Crop/Reformat nodes. The metadata reports the actual zoom and labels the requested center explicitly; it is not a pan readback. A fixed region does not follow tracked motion: request the appropriate coordinates for each frame. Centered/region navigation currently requires a device-pixel ratio of 1 and fails clearly otherwise.

During a Viewer render, an enabled ROI is temporarily disabled so unrefreshed pixels outside it cannot count as frame evidence, then restored. Navigated captures also temporarily disable Capture-resize and restore its setting, so the output matches the viewport rather than an enlarged canvas.

The teacher's lesson transcripts are now integrated: the pack uses selected original paraphrases (no transcript text is shipped) with citations by lesson filename and timecode range, and all 15 lessons are recorded in the source metadata. The transcripts may contain transcription errors and the video context was not verified, so they are teaching evidence, not video-validated facts. The pack has no dependency on the transcript files or their mount. Where an older lesson example differs from the currently written conventions, the written conventions take precedence. Common student mistakes are already encoded as pitfalls and safeguards. Raw teacher `.nk` example files are still to come.

Editing the pack: each document starts with frontmatter of one JSON-valued key per line (a YAML subset: `id`, `kind`, `title`, `category`, `summary`, `aliases`, `tags`, `requires`, `related`, `nodes`, `version`, `source_ids`; all required). `id` equals the path under `knowledge/` without `.md`; directories are flat (`fundamentals/`, `topics/`, `nodes/`), and required section headings differ by kind (topics/fundamentals: Applicability, Workflow, Verify, Pitfalls, Sources; nodes: Purpose, Inputs, Controls, Verify, Pitfalls, Sources). The one exception is the router `SKILL.md`: its `id` is `overview` and it also carries `name` and `description`. Well-formed new files are indexed automatically; the corpus is cached once per sidecar process, so restart the sidecar (restart Nuke or the external client) after edits, and rebuild/reinstall the wheel if you use an installed copy. Raw teacher `.nk` examples may later refine the content; none are required now, and the pack does not train or fine-tune any model.

### Approval and trust

Python requests are confirmed in a Nuke dialog, whether or not a pane is open. If no trust applies, every request falls back to this dialog; denial prevents the mutation.

**Trusted Python session** applies only when exactly one live pane is registered, that pane is visible, and its checkbox is checked. Trust then applies to every caller of the shared bridge, including external agents. With multiple live panes (even if one is hidden), requests always prompt. Hiding or closing the pane resets trust; showing it again starts untrusted. The shared bridge keeps running and stays reachable by external agents without any pane.

### Optional: external stdio entry point

The stdio server remains a standard-library MCP entry point that any MCP-capable client can launch; configuring such clients is outside this project. It runs as the same OS user as Nuke and finds the bridge through a local discovery record in the per-user runtime directory: Linux `$XDG_RUNTIME_DIR/nuke-codex-panel-<uid>` (0700), macOS `<user temp dir>/nuke-codex-panel-<uid>` (0700), Windows `%LOCALAPPDATA%\NukePi\runtime` with an owner-only access list that is validated on each use. With several Nuke sessions it selects the newest live one; to pin a specific session, set `NUKE_CODEX_BRIDGE_FILE` to that session's discovery record. A pinned record whose Nuke is gone is an error, not a fallback.

Generic launch parameters: command = a standalone Python 3.11+ (the panel uses the interpreter recorded by the installer), args `-m nuke_codex_panel.mcp_server.server`, working environment `PYTHONPATH=<install target>`. Requirements: local stdio transport, same OS user as Nuke, a client timeout long enough for the Python confirmation dialog, and MCP image-content support if screenshots should reach the model visually. The knowledge tools need no Nuke; the live tools also need a Nuke GUI session.

### Optional: console entry point

To get a `nuke-codex-mcp` command instead of the module form, install this same project (not a separate server) with uv:

```bash
uv tool install /absolute/path/to/nuke-codex-panel
```

Then register `nuke-codex-mcp` as the `command` with no `args` and no `PYTHONPATH`. This is optional; the module form above works without it.

### Moving from the old `nuke_mcp` plugin

If an older `nuke_mcp` plugin is loaded, remove its `import nuke_mcp_addon` line and any `nuke_mcp` `pluginAddPath` from `~/.nuke/menu.py`/`init.py`, then install as above and confirm there is a single bridge. Leave `~/.nuke/nuke_mcp/` on disk; it is simply no longer loaded.

> **Security:** `execute_python` can perform any action available to Nuke's Python process, including filesystem and subprocess operations; it is not an OS sandbox. Keep per-request confirmation enabled unless the caller and conversation are trusted.

### Instructions for installation agents and LLMs

1. Do not modify or replace unrelated content in `~/.nuke/init.py` or `~/.nuke/menu.py`; use `install.py`, which only edits its own managed block.
2. Run `python3 install.py --target PATH --nuke-dir PATH` (Windows: `py -3`). Use `--no-register` for a temporary install and `--check` to verify without changes. Do not copy or read the user's existing Pi/auth files.
3. Do not hand-install Node or Pi, do not use a global Node/Pi, and do not configure other agent CLIs.
4. Do not register the MCP server globally for panel-only use.
5. If `nuke_mcp` is present, follow the migration note; never delete its folder.
6. Restart Nuke and verify the bridge is reachable without a pane, then **Pane > Nuke Pi**, Pi account sign-in, Python approval, and all three capture targets.

## License

This project is MIT licensed (see [LICENSE](LICENSE)), including its owned Pi extensions. It is a customized distribution, not a fork: official Pi (MIT, Earendil Works / Mario Zechner) and official Node.js (MIT with bundled third-party notices) are downloaded unmodified at install time and keep their own licenses. This project does not relicense them or their transitive dependencies. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); the installer copies the actual upstream license/notice texts into `runtime/pi/third-party-notices/`.

## Current functionality

- Dockable PySide6 panel registration.
- Live connection to the private Pi runtime using accounts you add in **Pi accounts…**.
- Streaming conversation with cancellation and reconnect controls.
- Viewer PNG capture uses the existing Viewer's synchronous render; Node Graph capture prefers its native OpenGL framebuffer. Full-interface capture uses KDE Spectacle on KDE Wayland, `grim` on wlroots compositors (Hyprland/Sway), or validated Qt/widget fallbacks.
- Captured images are attached as `localImage` inputs to the next prompt.
- Pending images have individual remove buttons and Clear All, and disappear automatically after Send.
- Captures are stored under `~/.cache/nuke-codex-panel/captures`; the panel does not rely on `/tmp` permissions.
- A small local MCP server exposes bounded `nuke_action` / `nuke_workflow`, structured Nuke context, screenshots, unrestricted authorized `execute_python`, three read-only compositing knowledge tools and two installed-API documentation tools (see [Tools](#tools)).
- Python runs on Nuke's Qt main thread in a persistent namespace containing `nuke`, precompiles all code before mutating anything, captures output/errors (structured `failure` on error), reports node changes, and uses an undo group by default.
- Each Python request requires confirmation in Nuke. Enable **Trusted Python session** to run requests without that dialog for the current panel session.

After pulling or editing the integration code, restart Nuke so the process-wide bridge and the panel's Pi processes pick up the new code.

## Verification status

"Verified" means actually exercised in real Nuke 17.1.

| Platform | Status |
|----------|--------|
| Linux x64 | exercised natively (see below) |
| Windows x64 | implemented; **not natively verified** |
| macOS Intel / Apple Silicon | implemented; **not natively verified** |

**What was exercised on Linux x64** (Nuke 17.1 `--safe` on a private display, from an installed copy in a temporary location rather than the checkout; the maintainer's real startup files were not modified):

- **Installer:** a copy install with `--no-register` downloaded the pinned Node 26.12.0 and Pi 1.4.0 and ran `npm ci`; `--check` passed on the installed target and on the repository checkout (manifest schema 2 with all four platform pins, 120 unique installed packages, 135 referenced notice files present, nested notices included). Registration into an owned Nuke user directory wrote one managed block and was idempotent on rerun; `--check` on a missing target exits 1 with a clear list. An in-place install adopted an existing runtime without altering the user's `init.py`/`menu.py`.
- **Conversation:** one real read-only Pi turn (about 87 s) with tool calls, image captures and a long Markdown reply: no clipped text, Markdown references and tables rendered, tool calls shown as separate collapsible cards with formatted arguments and results, correct status, font sizes 8/11/12/24, Nuke's own UI unstyled, chat persistence and automatic continuation after reopening the project without a question.
- **Responsiveness:** Nuke UI timers recorded 8308 samples with a maximum of 87.6 ms (none over 100 ms) across the installed exercise.

**Not verified:** Windows and macOS; backup creation of pre-existing `init.py`/`menu.py`; long-history load time; remote or file Markdown images; a second New Chat during streaming; mid-stream abort. This is a narrow exercise on one workstation, not a claim that every feature or every later source change was proven, and not a complete clean pass.

**Third-party notices:** two published packages, `data-uri-to-buffer` 4.0.1 and `proxy-agent-negotiate` 1.1.0, declare MIT in their `package.json` but ship no license file or copyright notice anywhere upstream; the installer reports them as warnings and no license text has been invented. The notice inventory and texts are provided as a good-faith record of what the upstream packages supplied; this is not legal advice or a guarantee that all upstream gaps are resolved.

Earlier native checks (shared bridge across pane hide/show/close, trust reset, a controlled Pi steering run, API-error recovery) predate the Pi-only cutover and are historical. The repository's `tests/` suite runs inside Nuke (`python3 -m pytest -q` for the offline part; the `*_smoke.py` scripts under `"$NUKE_BIN" --safe --tg`); run it yourself and avoid real accounts unless you intend to use them.
