# ORCHESTRATOR.md — Nuke Codex Panel

Repo brief
- Foundry Nuke agent panel (`~/.nuke/nuke-codex-panel`): dockable PySide6 chat client for Codex / Claude Code / pi / OMP / opencode harnesses. Pure-python package (`nuke_codex_panel/`), Python 3.11 under Nuke 17.1; no build step; symlinked into `~/.nuke` and registered via `menu.py` → `panel.py` → `ui/panel_widget.py`.
- Runtime: harnesses are subprocesses speaking JSONL (codex app-server, `claude -p stream-json`, pi/omp `--mode rpc`, opencode serve+SSE). Nuke MCP sidecar (`harnesses/nuke_mcp.py` + `mcp_server/server.py`) gives each agent `execute_python` / `get_nuke_context` / `capture_nuke_screenshot` through a Qt TCP bridge (`bridge/server.py`) authenticated by a discovery file in `$XDG_RUNTIME_DIR/nuke-codex-panel-<uid>/session-<pid>-<hex>.json` (unique per panel instance since 8fd9ce3).
- Tests: smoke scripts run inside a live Nuke GUI (they `import PySide6`, which only exists in Nuke's process): `tests/chat_render_smoke.py`, `tests/chat_scroll_smoke.py` (added 8fd9ce3), `tests/*_smoke.py`, plus pytest-style `tests/test_*.py`. CI = N/A; verification is in-Nuke.
- Env: Nuke usually launched via `ghostty -e /opt/Nuke17.1v1/Nuke17.1 --nukex` from Omarchy desktop entry `~/.local/share/applications/nuke17-nukex.desktop`. Machine facts: `claude` lives ONLY at `~/.local/share/mise/shims/claude` (mise-managed; NOT in npm-global). `codex`/`pi`/`omp`/`opencode` at `~/.npm-global/bin`. MCP access to the live panel: pi `nuke` MCP server (execute_python) — requires a valid bridge discovery file.

Decision log (append-only)
- 2026-10-28 Claude deadlock fix (8fd9ce3): claude's stream-json emits `init` only when the FIRST user message is processed; panel gated Send on init → deadlock. ClaudeClient now announces static KNOWN_MODELS and readiness at process start (`_on_started`); send triggers init. Verified live: pi→claude switch, send, stream, turn completes.
- 2026-10-28 Scroll pinning (8fd9ce3): BubbleText refit moved from `contentsChanged` (pre-layout `document.size()` → height wobble → chat jumping) to `documentLayout().documentSizeChanged` (post-layout). Bottom re-pin only when user is within 40px of the bottom; `_render_section` no longer scrolls (height_changed signal → `_stick_if_pinned`). Verified: `tests/chat_scroll_smoke.py` (constrained viewport via `setFixedSize` — top-level windows auto-grow and defeat the test).
- 2026-10-28 Rediscovery of binary resolution: `resolve_binary` now also probes per-user dirs (`~/.local/share/mise/shims`, `~/.npm-global/bin`, `~/.local/bin`, `~/.bin`) after PATH — desktop-launched Nuke may have a minimal PATH (README already warns; user hit this with Claude before mise shims were on PATH).
- 2026-10-28 Bridge discovery filenames are per-panel-instance (`session-<pid>-<hex>.json`) + stale-prune; a shared `session-<pid>.json` let one panel's `stop()` delete the other's record, bricking the MCP sidecar (also broke the orchestrator's own MCP link mid-session).
- 2026-10-28 Teardown noise: `errorOccurred(Crashed)` suppressed when the QProcess already exited (NotRunning); `finished()` reports real exits.

Active task ledger
- All items of user report fixed + committed (8fd9ce3): (1) Claude not opening on select; (2) stream scroll jumping; (3) stale model dropdown on harness switch + forced Reconnect; (4) bridge discovery collision. Live-verified in the user's docked Nuke via in-memory module reload; user's Nuke restart loads files durably.

Open questions
- Claude `--resume` round-trip (resume keeps context across Nuke restarts) validated shell-side only; panel-side needs a session with a completed turn, then Reconnect → verify context carries.
- `--model opus` auto-pick displays but does not relaunch on the very first connection (pre-existing: model only applies on user pick/restart); claude's default is opus-class so cosmetically consistent. Leave unless user objects.