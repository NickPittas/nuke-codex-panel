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

Binary lookup probes in this order: the panel's **Settings…** dialog override (per harness, persisted in QSettings), then `NUKE_CODEX_BIN` / `NUKE_CLAUDE_BIN` / `NUKE_PI_BIN` / `NUKE_OMP_BIN` / `NUKE_OPENCODE_BIN`, then `PATH`, then common install locations. The Settings dialog shows the live detection result for each harness. Every harness registers the same bundled Nuke MCP server, so all six tools (see [One application, one bundled MCP](#one-application-one-bundled-mcp)) are available to all five panel harnesses and to external MCP clients. The compact shared prompt is injected only by the five panel harnesses; external clients get the retrieval cue from the `execute_python` tool description. The sidecar auto-discovers the newest live Nuke session for the three live tools.

Adding another harness later: subclass `HarnessClient` in `nuke_codex_panel/harnesses/` and register it in `HARNESSES`.

## Requirements

- For the docked panel and the live Nuke tools: Foundry Nuke 17+ with PySide6.
- System Python 3 (3.11+) for the bundled MCP server. Alone it is enough for the three knowledge tools (no Nuke, Qt, bridge, network or PDF) and for registering external clients; no harness CLI needed. The live tools additionally need a running Nuke GUI session.
- For the docked panel: at least one authenticated harness CLI: `codex`, `claude`, `pi`, `omp`, or `opencode`. The Codex CLI install below is one option.
- The ChatGPT desktop app is optional and is not used by the Nuke panel.
- KDE Wayland capture currently requires `spectacle`; other desktops use the available Qt/OpenGL fallbacks.

The Codex harness launches `codex app-server` locally. Installing only the ChatGPT app does not guarantee that a `codex` executable is available to Nuke.

## Install Codex

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

## One application, one bundled MCP

This project is a single application containing the dockable panel and the MCP server used by external agents. There is no separate server project, second Nuke plugin, or separate virtual environment.

- Importing `nuke_codex_panel.menu` in a Nuke GUI session starts one process-wide, authenticated, loopback-only bridge. It starts at Nuke startup whether or not a Codex pane is open, and it stays running when a pane is closed. The pane does not own the bridge.
- All five harnesses (Codex, Claude, pi, OMP, opencode) launch the same bundled MCP server. The command and environment come from `nuke_codex_panel/harnesses/nuke_mcp.py` (`server_command()`, `server_environment(bridge_path)`), and panel instances are pinned to this Nuke's exact bridge discovery record. The package location, not the active project's working directory, determines `PYTHONPATH`. No global MCP registration is needed for panel-only use, and a panel's bridge pin is not written into persistent global client configuration; external registrations without a pin keep auto-discovering the newest live Nuke.
- External agents need only a registration pointing at the same bundled stdio server. They do not need a pane open.

### Tools

Three live tools talk to a running Nuke through the bridge, so a Nuke GUI session is required: `execute_python`, `get_nuke_context`, `capture_nuke_screenshot`. An explicit `NUKE_CODEX_BRIDGE_FILE` pin is optional; it only selects which session to use and fails closed if invalid.

Three read-only knowledge tools run directly in the stdio sidecar before bridge dispatch, so they work with Nuke closed or an invalid pin:

- `search_compositing_knowledge(query, limit=3 (1–8), kind=all|topic|fundamental|node)` returns metadata only (`id`, `title`, `kind`, `summary`, `requires`, `version`), never document bodies.
- `get_compositing_guidance(topic_id, section=overview|workflow|verify|pitfalls|full)` returns the chosen section of a router, fundamental or topic document (default `overview`) plus compact metadata and Sources. Prerequisite and related IDs are listed, not expanded recursively.
- `get_node_reference(node, section=overview|inputs|controls|verify|pitfalls|full)` resolves a node ID, title or alias and returns the chosen section with `runtime_verified: false`.

Returned content is capped at 6000 characters including citations, with a truncation flag and the list of available sections. Unknown IDs/nodes give an explicit error with at most three suggestions. Example: search `"keymix vs addmix"`, then `get_compositing_guidance("topics/addmix-keymix", "workflow")`.

The pack is 116 packaged Markdown documents under `nuke_codex_panel/knowledge/`: a router, 10 fundamentals, 38 topics (the full curriculum) and 67 node references. It is original, paraphrased guidance citing primary Foundry Nuke 17.1 documentation and Brinkmann's *The Art and Science of Digital Compositing* (2nd ed.) for concepts; there is no PDF dependency and no book text is shipped. Node references are static 17.1 documentation, not live-runtime verification of what your installed Nuke offers.

The teacher-supplied production conventions are encoded as three fundamentals: `fundamentals/graph-conventions`, `fundamentals/keying-conventions` and `fundamentals/quality-safeguards`, cited to the `studio-conventions` source. For this course's work they are required, not optional agent style, but they are the teacher's project/studio requirements, not universal Nuke engine constraints; Foundry-documented behaviour stays in the node references and is cited separately. The shared prompt (all five harnesses) and the external `execute_python` description tell models to call `get_compositing_guidance(..., section="workflow")` for the graph and quality conventions before building or organizing any graph, and for the keying conventions before keying, even with familiar nodes; everything else stays on-demand.

The teacher's lesson transcripts are now integrated: the pack uses selected original paraphrases (no transcript text is shipped) with citations by lesson filename and timecode range, and all 15 lessons are recorded in the source metadata. The transcripts may contain transcription errors and the video context was not verified, so they are teaching evidence, not video-validated facts. The pack has no dependency on the transcript files or their mount. Where an older lesson example differs from the currently written conventions, the written conventions take precedence. Common student mistakes are already encoded as pitfalls and safeguards. Raw teacher `.nk` example files are still to come.

Editing the pack: each document starts with frontmatter of one JSON-valued key per line (a YAML subset: `id`, `kind`, `title`, `category`, `summary`, `aliases`, `tags`, `requires`, `related`, `nodes`, `version`, `source_ids`; all required). `id` equals the path under `knowledge/` without `.md`; directories are flat (`fundamentals/`, `topics/`, `nodes/`), and required section headings differ by kind (topics/fundamentals: Applicability, Workflow, Verify, Pitfalls, Sources; nodes: Purpose, Inputs, Controls, Verify, Pitfalls, Sources). The one exception is the router `SKILL.md`: its `id` is `overview` and it also carries `name` and `description`. Well-formed new files are indexed automatically; the corpus is cached once per sidecar process, so restart the sidecar (restart Nuke or the external client) after edits, and rebuild/reinstall the wheel if you use an installed copy. Raw teacher `.nk` examples may later refine the content; none are required now, and the pack does not train or fine-tune any model.

### Approval and trust

Python requests are confirmed in a Nuke dialog, whether or not a pane is open. If no trust applies, every request falls back to this dialog; denial prevents the mutation.

**Trusted Python session** applies only when exactly one live pane is registered, that pane is visible, and its checkbox is checked. Trust then applies to every caller of the shared bridge, including external agents. With multiple live panes (even if one is hidden), requests always prompt. Hiding or closing the pane resets trust; showing it again starts untrusted. The shared bridge keeps running and stays reachable by external agents without any pane.

### Optional: external agents

An external stdio server needs a registration in the client. It runs as the same OS user as Nuke and finds the bridge through a local discovery record. With several Nuke sessions it selects the newest live one; to pin a specific session, set `NUKE_CODEX_BRIDGE_FILE` to that session's discovery record (under `$XDG_RUNTIME_DIR/nuke-codex-panel-UID/`). A pinned record whose Nuke is gone is an error, not a fallback.

**Codex CLI:**

```bash
codex mcp add nuke \
  --env PYTHONPATH="$HOME/.nuke/nuke-codex-panel" \
  -- /usr/bin/python3 -m nuke_codex_panel.mcp_server.server
codex mcp get nuke --json
```

Equivalent `~/.codex/config.toml`:

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

The longer tool timeout allows time for the Python confirmation dialog. Remove with `codex mcp remove nuke`.

**OpenCode** (native format, `~/.config/opencode/opencode.json`; `command` is one array and variables go under `environment`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "nuke": {
      "type": "local",
      "command": ["/usr/bin/python3", "-m", "nuke_codex_panel.mcp_server.server"],
      "environment": { "PYTHONPATH": "/home/USER/.nuke/nuke-codex-panel" },
      "timeout": 300000,
      "enabled": true
    }
  }
}
```

**Claude and other MCP clients** (generic `mcpServers` stdio shape; exact file and key names vary by client):

```json
{
  "mcpServers": {
    "nuke": {
      "command": "/usr/bin/python3",
      "args": ["-m", "nuke_codex_panel.mcp_server.server"],
      "env": { "PYTHONPATH": "/home/USER/.nuke/nuke-codex-panel" }
    }
  }
}
```

Claude Code can register the same entry for all projects with `claude mcp add --scope user nuke --env PYTHONPATH="$HOME/.nuke/nuke-codex-panel" -- /usr/bin/python3 -m nuke_codex_panel.mcp_server.server` (the default scope is local to the current project).

Requirements: local stdio transport, project directory on `PYTHONPATH` (no `pip install` needed), same OS user as Nuke, and MCP image-content support if screenshots should reach the model visually. External MCP-only use needs system Python only for the knowledge tools; the live tools also need a Nuke GUI session. Neither needs the Codex CLI.

### Optional: console entry point

To get a `nuke-codex-mcp` command instead of the module form, install this same project (not a separate server) with uv:

```bash
uv tool install /absolute/path/to/nuke-codex-panel
```

Then register `nuke-codex-mcp` as the `command` with no `args` and no `PYTHONPATH`. This is optional; the module form above works without it.

### Migrating from the old `nuke_mcp` plugin

The unified server replaces the separate `nuke_mcp` startup. To migrate, remove (do not delete the old folder itself) these entries:

1. In `~/.nuke/menu.py` (or `init.py`), remove the `import nuke_mcp_addon` line and any `nuke_mcp` `pluginAddPath`.
2. In each client config, remove the old `nuke_mcp` entry (for OpenCode, the `mcp.nuke_mcp` block pointing at `nuke_mcp/.venv/bin/python` and `nuke_mcp/main.py`; for Codex, `codex mcp remove` any old entry), then add one of the registrations above.
3. Ensure the panel's two startup lines are present, restart Nuke, and confirm there is a single bridge.

Leave `~/.nuke/nuke_mcp/` on disk; it is simply no longer loaded.

> **Security:** `execute_python` is intentionally unrestricted and can perform any action available to Nuke's Python process, including filesystem and subprocess operations. Keep per-request confirmation enabled unless the caller and conversation are trusted.

### Instructions for installation agents and LLMs

When installing this project for a user:

1. Do not modify or replace unrelated content in `~/.nuke/init.py` or `~/.nuke/menu.py`.
2. Ensure the project exists at the path used by `nuke.pluginAddPath`, with the two startup lines present.
3. Confirm `codex --version` and `codex login status` outside Nuke; set `NUKE_CODEX_BIN` if Nuke cannot resolve Codex.
4. Do not globally register the MCP server for panel-only use.
5. Register the stdio entry only when the user wants an external agent; do not install a second Nuke plugin.
6. If `nuke_mcp` is present, follow the migration steps; never delete its folder.
7. Restart Nuke and verify the bridge is reachable without a pane, then **Pane > Codex**, Python approval, and all three capture targets.

## Current functionality

- Dockable PySide6 panel registration.
- Live connection to the selected harness using its existing local authentication.
- Streaming conversation with cancellation and reconnect controls.
- Immediate Viewer, Node Graph, and full-interface PNG capture using KDE Spectacle on KDE Wayland, `grim` on wlroots compositors (Hyprland/Sway), with validated Qt/OpenGL/widget fallbacks elsewhere.
- Captured images are attached as `localImage` inputs to the next prompt.
- Pending images have individual remove buttons and Clear All, and disappear automatically after Send.
- Captures are stored under `~/.cache/nuke-codex-panel/captures`; the panel does not rely on `/tmp` permissions.
- A small local MCP server exposes structured Nuke context, screenshots, unrestricted `execute_python`, and three read-only compositing knowledge tools (see [Tools](#tools)).
- Python runs on Nuke's Qt main thread in a persistent namespace containing `nuke`, captures output/errors, reports node changes, and uses an undo group by default.
- Each Python request requires confirmation in Nuke. Enable **Trusted Python session** to run requests without that dialog for the current panel session.

After pulling or editing the integration code, restart Nuke so the process-wide bridge and the panel's harness processes pick up the new code.

## Smoke tests

Run from the project root with `NUKE_BIN` set to your Nuke executable (any path; nothing below depends on a specific version):

```bash
export NUKE_BIN=/path/to/Nuke17.x
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

# No model turns
python3 -m pytest -q
"$NUKE_BIN" --safe --tg tests/shared_bridge_smoke.py   # prints NUKE_CODEX_SHARED_BRIDGE_OK on success
"$NUKE_BIN" --safe -t tests/nuke_smoke.py
"$NUKE_BIN" --safe -t tests/bridge_smoke.py
"$NUKE_BIN" --safe --tg tests/capture_wayland_smoke.py

# Optional: these start real model turns and need an authenticated Codex CLI
"$NUKE_BIN" --safe -t tests/app_server_smoke.py
"$NUKE_BIN" --safe -t tests/codex_tool_smoke.py
```

Verified so far on one workstation (Nuke 17.1, `--safe --tg`): external stdio clients reaching the shared bridge, bridge survival across pane hide/show/close, a denied Python request from a hidden pane creating no node, trust reset on hide and close (showing the same pane stays untrusted), and close/reopen and shutdown checks. No full model conversation through every backend has been verified.
