# Nuke Codex Panel — Implementation Plan

> **HISTORICAL design document.** It describes the earlier multi-harness (Codex/Claude/pi/OMP/opencode) design. The current product, *Nuke Pi*, is Pi-only; see [../README.md](../README.md) and [INSTALLATION.md](INSTALLATION.md). Nothing here is a runtime contract.

`nuke-codex-panel` is a dockable PySide6 panel for Foundry Nuke 17. It hosts agent harnesses (Codex, Claude, pi, OMP, opencode) inside Nuke, gives models bounded native actions and application-owned workflows backed by scoped advanced Python, and gives them immediate visual access to the Viewer, Node Graph, or complete interface.

## Design principles

- Ordinary work goes through bounded `nuke_action` steps and application-owned `nuke_workflow` families; `execute_python` is the advanced path. Panel-managed (guided) sidecars require a declared scope and refuse obvious graph building; unmanaged external clients keep the full unscoped profile. Scope checks are detection and steering, not a sandbox.
- Manual steering only: the user interrupts and steers (busy Send or `/btw`, pi/OMP); no timer ever interrupts a model.
- All Nuke and Qt work runs on Nuke's main thread. Network, process, and protocol I/O runs outside it.
- Visual verification is part of the normal agent loop, including before/after captures and multi-frame contact sheets.
- The installation is reversible: one development symlink, one `pluginAddPath` line, and one menu import line.
- Protocol and state logic remains testable without a Nuke installation.

## Process architecture

```text
Nuke (GUI process)
├── nuke_codex_panel.menu import
│   └── process-wide NukeBridgeServer (loopback only, ensure_bridge())
│       ├── discovery record, removed on Qt aboutToQuit
│       └── trust sources: weak references to open panels
├── Docked CodexPanelWidget(s)  (do not own the bridge)
│   ├── Codex / Claude / pi / OMP / opencode harnesses (nuke_codex_panel/harnesses/)
│   ├── capture controls and image history, chat persistence
│   └── each launches the bundled MCP server via harnesses/nuke_mcp.py, pinned to the shared bridge discovery record

External agents (Codex CLI, OpenCode, Claude, ...)
            │ MCP stdio
            ▼
   bundled MCP server (python -m nuke_codex_panel.mcp_server.server,
   or nuke-codex-mcp)
            │ authenticated localhost RPC
            ▼
   the same shared bridge
```

Panel backends and external agents launch the same bundled MCP server, which cannot import Nuke and forwards calls to the bridge inside Nuke. The bridge marshals execution to the Nuke main thread and returns structured tool or image results. It starts at GUI startup, independent of any pane, and survives pane close. Each harness client has a stable control id; the bridge's execution control (`bridge/control.py`) pauses, drains and fences old sidecar processes (control epoch) so manual steering can retire an old run safely.

The bridge publishes a per-process discovery record named `session-<pid>-<hex>.json` under `$XDG_RUNTIME_DIR/nuke-codex-panel-UID/` (with a temporary-directory fallback) containing the Nuke PID, loopback TCP endpoint, and a random session capability token. The directory and record are user-only (`0700`/`0600`), and sockets tolerate client disconnects. Panel-launched servers are pinned to the exact record via `NUKE_CODEX_BRIDGE_FILE`; external servers select the newest live Nuke unless pinned the same way. Stale fallback records are ignored when their PID is no longer alive. Nothing binds to a non-loopback interface; access is same-OS-user only.

Python approval is a Nuke dialog. A panel's Trusted session skips it only when exactly one live panel is registered, visible, and has it checked; that trust covers every caller of the shared bridge, including external agents. Multiple live panels always prompt, and hiding or closing a pane resets its trust (showing it again starts untrusted). Hiding or closing never stops the shared bridge.

The panel can also add a freshly captured PNG directly to `turn/start` as a Codex App Server `{ "type": "localImage", "path": "..." }` input. During a turn, MCP screenshot tools return image content blocks.

## Initial package layout

```text
nuke-codex-panel/
├── docs/PLAN.md
├── README.md
├── pyproject.toml
├── nuke_codex_panel/
│   ├── __init__.py
│   ├── menu.py
│   ├── panel.py
│   ├── ui/panel_widget.py
│   └── capture/widgets.py
└── tests/
```

The later phases added `harnesses/` (which replaced the earlier `app_server/` backends), `bridge/`, `mcp_server/`, `tools/`, and Nuke stubs without changing the startup entrypoint.

## Core tool surface

The MCP surface: five live bridge tools, three offline knowledge tools and two installed-API documentation tools.

- `nuke_action`: one bounded native step per call (create one node with knobs/inputs, set, inspect, connect, swap, layout, project, sample, render, animate, Roto shapes, node-internal Python), reporting observed state.
- `nuke_workflow`: application-owned per-client workflow state (families 2d, keying, cleanup, projection; composable) with current-step guidance and review evidence.
- `execute_python`: Python in a persistent Nuke-aware namespace with stdout, stderr, result, traceback, elapsed time and undo grouping; scoped advanced use in the guided profile, unscoped in the full profile.
- `get_nuke_context`: script, frame, selection, active group, Viewers, formats, color management, node summaries (`include_nodes=true` adds nodes and indexed connections), errors, and recent execution state.
- `capture_nuke_screenshot`: `target` viewer (optionally a frame), nodegraph (visible, selection or all scope) or interface; Viewer captures wait for the existing Viewer's synchronous render.
- Two independent guards sit in front of Python: the graph-inspection checkpoint (requires `get_nuke_context(include_nodes=true)` plus an all-scope nodegraph capture at the current revision) and the API-error recovery gate. Workflow state in `nuke_workflow` is separate and tracks steps and delivered render evidence.
- Checkpoint/restore and a dedicated contact-sheet tool are planned, not landed.

## Execution and recovery

- Requests enter through a Qt loopback bridge owned by Nuke's UI thread, so its callbacks execute directly on that thread.
- Python execution captures stdout and exceptions and serializes non-JSON results safely using `repr`.
- Mutation requests can be wrapped in a named Nuke undo group. Since not every Nuke or filesystem operation is undoable, checkpoints remain the stronger recovery mechanism.
- Exact Python is always visible in the activity log. Session modes are Ask, Auto-approve reads/captures, and Trusted session.
- Full profile: no AST filtering, restricted builtins or import blocking. Guided profile: a static screen and declared scope steer models and report outside changes after the fact; they do not prevent or roll back anything.
- Timeouts bound the bridge response but cannot forcibly interrupt Python already blocking Nuke's main thread. Screenshot requests are the exception: they have no response deadline and end in a finished synchronous render/capture or an explicit error, never a timeout that falls back to stale pixels. Long renders and analyses require cancellable Nuke task APIs rather than ordinary `exec`.

## Screenshot behavior

Every capture records target, frame, Viewer input, proxy state, resolution, display transform when available, selection, timestamp, and image path.

- Viewer display capture preserves the Viewer process, overlays, wipes, and masks. On KDE Wayland it uses Spectacle's compositor-authorized full-desktop capture and crops to the target widget, because Qt screen grabs are blacked out by KWin. Spectacle runs behind a nested Qt event loop rather than a blocking process wait, allowing Nuke's embedded Viewer and DAG surfaces to keep repainting during capture. Other sessions use validated screen, OpenGL framebuffer, and widget fallbacks; uniformly black compositor-denied images are never accepted as successful captures.
- Clean-frame capture provides pixels without interface chrome.
- Node Graph capture supports visible, selected, and all-node scopes while restoring the artist's previous zoom and pan.
- Full-interface capture grabs the Nuke top-level window, including panels and error dialogs.
- Contact sheets and several separate frame images provide temporal evidence.
- The UI maintains labeled thumbnails, pin/unpin context, before/after comparison, and a one-click "Capture and ask" action.

Routine captures are resized to a configurable long edge for responsiveness; original-resolution files can be retained when requested. Capture files use a per-session temporary directory with explicit retention limits and cleanup on normal panel shutdown and next startup.

## Phases

1. **Bootstrap:** Git repository, package skeleton, dockable placeholder panel, reversible symlink/startup configuration, and import tests.
2. **Capture foundation:** OpenGL-aware Viewer readback, Node Graph and Foundry-main-window capture, non-black validation, visible history, and temporary-file lifecycle.
3. **Nuke bridge and Python:** persistent namespace, main-thread dispatcher, structured results, undo groups, context snapshots, and checkpoints.
4. **Codex App Server client:** process lifecycle, initialize/thread/turn JSON-RPC, streaming deltas, cancellation, approvals, and direct `localImage` inputs.
5. **MCP sidecar:** the small tool registry above, runtime-record discovery, authenticated Unix-socket/loopback transport, MCP image results, and Codex configuration.
6. **Verification loop:** automatic optional before/after captures, node-graph diffs, contact sheets, and recovery controls.
7. **Production hardening:** reconnects, logging, configuration UI, installation scripts, Nuke-version compatibility, documentation, and packaging.

## MVP acceptance criteria

1. Nuke shows a dockable, layout-restorable **Codex** panel after the two startup lines are loaded.
2. The panel streams a Codex turn and can cancel it without blocking the Nuke UI.
3. Codex can inspect structured state and run arbitrary Nuke Python on the main thread after the configured approval flow.
4. Viewer, Node Graph, and full-interface screenshots reach the active Codex turn and display in the panel's history.
5. A modification can be evaluated from before/after screenshots and a structured graph diff.
6. Undo and checkpoint recovery are exposed without restricting Python.
7. Protocol, installation, result-envelope, and capture-selection tests pass outside Nuke; an in-Nuke smoke checklist validates the real widgets and Viewer behavior.

## Test strategy

- Keep imports of `nuke`, `nukescripts`, and PySide6 behind host adapters or runtime entrypoints.
- Use a fake Nuke module for graph, selection, frame, undo, checkpoint, and main-thread tests.
- Test App Server JSON-RPC against a local fake subprocess emitting JSONL.
- Test the MCP sidecar independently from the in-Nuke bridge.
- Run Qt capture tests offscreen when PySide6 is available; otherwise skip them explicitly.
- Test installation against a temporary `.nuke` directory and require byte-exact preservation of unrelated startup content.
- Perform a real Nuke smoke test for docking, reload behavior, Viewer capture, Node Graph targeting, and full-window capture.

## Current milestone

Bootstrap, capture foundation, harness clients, Nuke bridge, Python executor, MCP sidecar, knowledge pack, graph-inspection and API-recovery gates are integrated. The manual steering (`harnesses/intervention.py`, pi/OMP), bounded `nuke_action` and application-owned `nuke_workflow` implementation has landed. Native verification is ongoing: a full native pytest run passed after fixes, a real GUI/MCP 2d pass exposed a Roto output knob setter bug that is now fixed with new native regressions awaiting re-run. Not yet verified: the steering UI, all four workflow families, and actual model/benchmark behaviour. Historical benchmark entries elsewhere describe the earlier unrestricted-Python profile. Later work: richer automatic visual verification, checkpoints/recovery, activity logging, production hardening.

## Next direction: private Pi runtime

Current direction is a fresh official Pi installed privately inside the plugin, with the existing Pi RPC and Qt UI retained. Design only, not implemented. Requirements and decisions are in [PLAN-pi-runtime.md](PLAN-pi-runtime.md); architecture is in [ARCHITECTURE-pi-runtime.md](ARCHITECTURE-pi-runtime.md); ordered feature tasks, live acceptance and the per-feature review workflow are in [INTEGRATION-pi-runtime.md](INTEGRATION-pi-runtime.md).
