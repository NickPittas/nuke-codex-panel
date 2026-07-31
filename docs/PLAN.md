# Nuke Codex Panel — Implementation Plan

`nuke-codex-panel` is a dockable PySide6 panel for Foundry Nuke 17. It presents a native Codex conversation inside Nuke, exposes unrestricted Nuke Python execution as a first-class tool, and gives Codex immediate visual access to the Viewer, Node Graph, or complete interface.

## Design principles

- Python is Nuke's primary control surface. `execute_python` remains unrestricted; specialized tools exist for context, screenshots, recovery, and convenience.
- All Nuke and Qt work runs on Nuke's main thread. Network, process, and protocol I/O runs outside it.
- Visual verification is part of the normal agent loop, including before/after captures and multi-frame contact sheets.
- The installation is reversible: one development symlink, one `pluginAddPath` line, and one menu import line.
- Protocol and state logic remains testable without a Nuke installation.

## Process architecture

```text
Nuke
└── Docked CodexPanelWidget
    ├── Codex App Server client (JSON-RPC over stdio)
    ├── capture controls and image history
    └── in-Nuke bridge (loopback only)
            ▲
            │ authenticated localhost RPC
            ▼
      nuke-codex-mcp sidecar
            ▲
            │ MCP stdio
            ▼
      Codex App Server
```

The Codex App Server owns conversations, turns, streaming events, authentication, and approvals. It launches the MCP sidecar from its MCP configuration. The sidecar cannot import Nuke, so it forwards Nuke-specific calls to the bridge running inside Nuke. The bridge marshals execution to the Nuke main thread and returns structured tool or image results.

The bridge publishes a per-process discovery record under `$XDG_RUNTIME_DIR/nuke-codex-panel-UID/` (with a temporary-directory fallback) containing the Nuke PID, loopback TCP endpoint, and a random session capability token. The directory and record are user-only (`0700`/`0600`), and the panel pins its MCP sidecar to that exact record so concurrent Nuke sessions cannot be confused. Stale fallback records are ignored when their PID is no longer alive. Nothing binds to a non-loopback interface.

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

The later phases add `app_server/`, `bridge/`, `mcp_server/`, `tools/`, and Nuke stubs without changing the startup entrypoint.

## Core tool surface

The MCP surface deliberately stays small:

- `execute_python`: unrestricted Python in a persistent Nuke-aware namespace, with stdout, stderr, result representation, traceback, elapsed time, and optional undo grouping.
- `get_context`: script, frame, selection, active group, Viewers, formats, color management, node summaries, errors, and recent execution state.
- `capture_viewer`: capture what the artist sees; a later clean-frame mode captures the source without interface chrome.
- `capture_node_graph`: visible graph, selection, or complete graph.
- `capture_interface`: full Nuke main window or selected dock.
- `capture_frame_set`: multiple frames or a labeled contact sheet for temporal inspection.
- `create_checkpoint`, `restore_checkpoint`, and `undo`: recovery operations.

## Execution and recovery

- Requests enter through a Qt loopback bridge owned by Nuke's UI thread, so its callbacks execute directly on that thread.
- Python execution captures stdout and exceptions and serializes non-JSON results safely using `repr`.
- Mutation requests can be wrapped in a named Nuke undo group. Since not every Nuke or filesystem operation is undoable, checkpoints remain the stronger recovery mechanism.
- Exact Python is always visible in the activity log. Session modes are Ask, Auto-approve reads/captures, and Trusted session.
- No AST filtering, restricted builtins, or import blocking is used.
- Timeouts bound the bridge response but cannot forcibly interrupt Python already blocking Nuke's main thread. Long renders and analyses require cancellable Nuke task APIs rather than ordinary `exec`.

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

The bootstrap, capture foundation, App Server client, Nuke bridge, Python executor, and MCP sidecar are integrated. The next work is richer context, automatic visual verification, checkpoints/recovery, activity logging, and production hardening.
