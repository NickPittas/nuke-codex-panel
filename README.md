# Nuke Codex Panel

A native, dockable agent client for Foundry Nuke, designed around unrestricted Nuke Python execution and immediate visual context from the Viewer, Node Graph, and full interface.

The panel talks to several agent harnesses — Codex, Claude Code, pi, OMP, and opencode — selectable from the Harness dropdown, with per-harness model and thinking-level pickers read live from the harness.

The chat streams answers token by token as Markdown bubbles. Model reasoning, replies, and tool calls appear as separate blocks **in the order they happen** — `reply → tool call → thinking → reply → tool call` — and thinking and tool blocks collapse when you click their header (a collapse choice sticks for later blocks of the same kind). Code blocks render in monospace, and the mouse wheel scrolls the chat from anywhere over it.

## Chats, context, and sessions

Chats are saved per project (in the app data dir, keyed by a hash of the script path, so nothing is written into project folders) and restored when the panel reopens. When a stored session exists the panel asks whether to **resume** it — resuming keeps the model's context across Nuke restarts:

| Harness | Session handle | Resumed via |
|---------|----------------|-------------|
| Codex | thread id | `thread/resume` |
| pi / OMP | session file | `--session-dir` + `--session-id` |
| opencode | session id | server-side sessions |
| Claude | session id | `--resume` (untested here) |

**New chat** archives the current transcript to `archive/` and starts with an empty model context. The context bar under the status line shows the current context-window usage (`context 60.0k / 200.0k (30%)`); hover it for the session breakdown (input / cached / output / cost) where the harness reports it.

## Harnesses

| Harness | Transport | Nuke MCP tools | Notes |
|---------|-----------|----------------|-------|
| Codex | `codex app-server` JSON-RPC | yes (injected config) | models + reasoning effort via `model/list` |
| Claude | `claude -p --output-format stream-json` | yes (`--mcp-config`) | thinking combo disabled (no CLI flag); adapter not yet smoke-tested |
| pi | `pi --mode rpc` | yes (`pi-mcp-adapter` + `~/.pi/agent/mcp.json`) | install the adapter once: `pi install npm:pi-mcp-adapter` |
| OMP | `omp --mode rpc` | yes (native `~/.omp/agent/mcp.json`) | thinking combo disabled (older RPC command set) |
| opencode | `opencode serve` HTTP + SSE | yes (`OPENCODE_CONFIG` overlay with allow-all permissions) | thinking maps to model variants |

Binary lookup probes in this order: the panel's **Settings…** dialog override (per harness, persisted in QSettings), then `NUKE_CODEX_BIN` / `NUKE_CLAUDE_BIN` / `NUKE_PI_BIN` / `NUKE_OMP_BIN` / `NUKE_OPENCODE_BIN`, then `PATH`, then common install locations. The Settings dialog shows the live detection result for each harness. Non-Codex harnesses register the bundled Nuke MCP server so `execute_python`, `get_nuke_context`, and `capture_nuke_screenshot` keep working; the sidecar auto-discovers the newest live Nuke session.

Adding another harness later: subclass `HarnessClient` in `nuke_codex_panel/harnesses/` and register it in `HARNESSES`.

## Requirements

- Foundry Nuke 17+ with PySide6.
- At least one authenticated harness CLI: `codex`, `claude`, `pi`, `omp`, or `opencode`.
- KDE Wayland capture currently requires `spectacle`; other desktops use the available Qt/OpenGL fallbacks.

## Codex setup

Install the CLI using npm:

```bash
npm install --global @openai/codex
```

Authenticate with a ChatGPT account in the browser flow, then verify the login:

```bash
codex login
codex login status
codex --version
```

Codex also supports device-code and API-key authentication; see the official [authentication documentation](https://developers.openai.com/codex/auth/).

Desktop-launched Nuke may have a smaller `PATH` than an interactive terminal. If the panel reports that Codex cannot be found, set `NUKE_CODEX_BIN` to the absolute path returned by:

```bash
command -v codex
```

For example, add it to the script or desktop entry that launches Nuke:

```bash
NUKE_CODEX_BIN=/home/USER/.npm-global/bin/codex /opt/Nuke17.0v4/Nuke17.0 --nukex
```

## Install the Nuke panel

Copy or clone this project, then link it into `~/.nuke`:

```bash
ln -s /absolute/path/to/nuke-codex-panel "$HOME/.nuke/nuke-codex-panel"
```

Nuke startup requires:

```python
# init.py
nuke.pluginAddPath("./nuke-codex-panel")

# menu.py
import nuke_codex_panel.menu
```

Restart Nuke, then open **Pane > Codex**. To uninstall the bootstrap, remove those two lines and the symlink.

## MCP installation

### Normal panel use: no manual MCP installation

The panel starts its own authenticated localhost bridge and injects the bundled `nuke` MCP server into its Codex App Server thread automatically. Users should not add another global MCP entry just to use the docked panel.

The automatic tools are:

- `execute_python`
- `get_nuke_context`
- `capture_nuke_screenshot`

Open the Codex pane before asking the model to use these tools. Python requests are confirmed inside Nuke unless **Trusted Python session** is enabled.

### Optional: expose Nuke to Codex CLI outside the panel

To let a separate Codex CLI session control the currently open Nuke panel, register the same stdio MCP sidecar globally:

```bash
codex mcp add nuke \
  --env PYTHONPATH="$HOME/.nuke/nuke-codex-panel" \
  -- /usr/bin/python3 -m nuke_codex_panel.mcp_server.server
```

Verify it with:

```bash
codex mcp get nuke --json
codex mcp list
```

For equivalent manual configuration, add this to `~/.codex/config.toml`:

```toml
[mcp_servers.nuke]
command = "/usr/bin/python3"
args = ["-m", "nuke_codex_panel.mcp_server.server"]
cwd = "/home/USER/.nuke/nuke-codex-panel"
startup_timeout_sec = 15
tool_timeout_sec = 300

[mcp_servers.nuke.env]
PYTHONPATH = "/home/USER/.nuke/nuke-codex-panel"
```

The longer tool timeout allows time for the in-Nuke Python confirmation dialog. This configuration is optional and does not replace the panel's automatic per-conversation setup. Remove the global entry with `codex mcp remove nuke` if it is no longer needed.

### Other local MCP-compatible LLM clients

An MCP client running on the same workstation can launch the bundled sidecar with configuration equivalent to:

```json
{
  "mcpServers": {
    "nuke": {
      "command": "/usr/bin/python3",
      "args": ["-m", "nuke_codex_panel.mcp_server.server"],
      "env": {
        "PYTHONPATH": "/home/USER/.nuke/nuke-codex-panel"
      }
    }
  }
}
```

The exact configuration filename and key names vary by client. The requirements are:

1. Use a local stdio MCP transport.
2. Put the project directory on `PYTHONPATH`.
3. Open **Pane > Codex** in Nuke first so the authenticated bridge is running.
4. Run the MCP client as the same operating-system user as Nuke.
5. Support MCP image content if screenshot tool results should reach the model visually.

The sidecar is not a standalone remote-control daemon. It discovers a live Nuke panel on localhost and cannot control Nuke when the pane is closed. If several Nuke sessions are open, the manually configured sidecar selects the most recently started live bridge; the docked panel avoids this ambiguity by pinning its own exact bridge file.

> **Security:** `execute_python` is intentionally unrestricted and can perform any action available to Nuke's Python process, including filesystem and subprocess operations. Keep per-request confirmation enabled unless the current client and conversation are trusted.

### Instructions for installation agents and LLMs

When installing this project for a user:

1. Do not modify or replace unrelated content in `~/.nuke/init.py` or `~/.nuke/menu.py`.
2. Ensure the project exists at the path used by `nuke.pluginAddPath`.
3. Confirm `codex --version` and `codex login status` outside Nuke.
4. Confirm Nuke can resolve the Codex binary; set `NUKE_CODEX_BIN` when necessary.
5. Do not globally register the MCP server for ordinary docked-panel use.
6. Register the stdio MCP entry only when the user explicitly wants an external Codex or other MCP client to control the open Nuke session.
7. Restart Nuke and verify **Pane > Codex**, connection status, Python approval, and all three capture targets.

## Current functionality

- Dockable PySide6 panel registration.
- Live Codex App Server connection using the existing local Codex authentication.
- Streaming conversation with cancellation and reconnect controls.
- Immediate Viewer, Node Graph, and full-interface PNG capture using KDE Spectacle compositor capture on Wayland, with validated Qt/OpenGL/widget fallbacks elsewhere.
- Captured images are attached as `localImage` inputs to the next prompt.
- Pending images have individual remove buttons and Clear All, and disappear automatically after Send.
- Captures are stored under `~/.cache/nuke-codex-panel/captures`; the panel does not rely on `/tmp` permissions.
- A small local MCP server exposes structured Nuke context, screenshots, and unrestricted `execute_python`.
- Python runs on Nuke's Qt main thread in a persistent namespace containing `nuke`, captures output/errors, reports node changes, and uses an undo group by default.
- Each Python request requires confirmation in Nuke. Enable **Trusted Python session** to run requests without that dialog for the current panel session.

After pulling or editing the integration code, close and reopen the Codex pane (or restart Nuke) so its Codex App Server thread is recreated with the Nuke MCP configuration.

## Smoke tests

```bash
python3 -m pytest -q
/opt/Nuke17.0v4/Nuke17.0 -t tests/nuke_smoke.py
/opt/Nuke17.0v4/Nuke17.0 -t tests/bridge_smoke.py
/opt/Nuke17.0v4/Nuke17.0 -t tests/app_server_smoke.py
/opt/Nuke17.0v4/Nuke17.0 -t tests/codex_tool_smoke.py
/opt/Nuke17.0v4/Nuke17.0 --tg tests/capture_wayland_smoke.py
```
