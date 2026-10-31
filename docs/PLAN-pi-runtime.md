# Plan: private official Pi runtime for the Nuke panel

**Status: F1 DONE / accepted (2026-10-30; live 19/19, 288 existing cases pass). F2 implemented, NOT ACCEPTED (human real API-key + subscription same-chat turns, actual OAuth refresh success/failure, logout without ambient fallback and private provenance are PENDING); F3 implemented and live-exercised in real Nuke after the whole-feature review batch, READY for user acceptance, NOT ACCEPTED (blocked-hook scenario source-reviewed only; optional web DEFERRED); F4-F6 not started.** Sections below describing TS-extension scope beyond `nuke-runtime.ts`, command UI, steering revalidation and distribution are still plan only. Evidence: F1 `/tmp/nuke-private-pi-f1-nRJLlM/`, F2 `/tmp/nuke-private-pi-f2-v0vdu8t2/batch-*.txt` (7 + 4 + 19 checks; offline SDK fixtures, not real auth); details in INTEGRATION-pi-runtime.md.

This file owns requirements, decisions, non-goals, scope and the research register. Companions (each is authoritative for its own content; do not restate them here):

- [ARCHITECTURE-pi-runtime.md](ARCHITECTURE-pi-runtime.md): module responsibilities, data/auth/session/environment flows, verified public Pi interfaces.
- [INTEGRATION-pi-runtime.md](INTEGRATION-pi-runtime.md): ordered feature tasks F1-F6, status, live acceptance, per-feature review workflow.

Earlier research stays as history: [RESEARCH-pi-durable.md](RESEARCH-pi-durable.md) (Durable vs plain Pi) and [RESEARCH-runtime-recovery-design.md](RESEARCH-runtime-recovery-design.md). Where they disagree with this plan, this plan wins.

Existing Pi extension candidates (web search/fetch, `/btw`, steering, official examples) and their REUSE/CUSTOMIZE/REFERENCE/DEFER/REJECT status live in [RESEARCH-pi-extensions.md](RESEARCH-pi-extensions.md). Source-read only, untested against Pi 1.4.0; no candidate is selected or installed by this plan.

## Goal

Replace the panel's dependence on the user's global Pi with a fresh **official Pi, installed privately inside the plugin**, so that runtime, configuration, accounts and Nuke-specific behaviour are reproducible and testable. Move mechanical prompt/skill reminders into trusted TypeScript code where a machine can enforce them. Keep the Qt UI and the working Pi RPC integration.

## Decisions

1. **Official Pi, pinned, private.** Start at Pi 1.4.0 (the version verified so far). Install fresh from the official pinned source/lock **inside the plugin's own folder tree** (`~/.nuke/nuke-codex-panel/`), not as a sibling of the package `PROJECT_ROOT` and not under the user's global Pi directory; the exact subpath is owned by [ARCHITECTURE-pi-runtime.md](ARCHITECTURE-pi-runtime.md). Launch through private absolute Node and Pi entrypoints. Never copy the global `node_modules`, extensions, config or auth. No dependency on global Pi or `PATH`.
2. **No fork, no ACP, no Durable, no embedded-TUI dependency.** Reasons are in the research register.
3. **Keep Qt UI and Pi RPC; use the SDK selectively.** RPC has no auth commands, so a minimal SDK auth helper covers login, logout and status, reusing the pinned Pi. It is not a second assistant engine and not a parallel conversation. No full SDK frontend or worker rewrite unless a demonstrated need appears.
4. **Resource isolation.** Plugin-local runtime and agent resources; only the necessary native MCP, codemode and `tool_search` builtins plus the trusted curated extension set (decision 5). No discovery of global or project extensions, skills, prompt templates, `AGENTS.md` or `CLAUDE.md`; extensions load only by explicit private path. The model toolset is Nuke MCP, codemode/discovery and approved extension tools, including any approved web search/fetch tools as an auxiliary reference source (installed-API facts stay with the Nuke MCP knowledge and SDK docs); Pi's default `bash`/`read`/`edit`/`write` are not retained silently. This is toolset control, not an OS sandbox.
5. **Trusted curated extensions and own system prompt are in scope.** The extension set is curated and explicitly loaded: project-owned TypeScript plus any pinned, licensed, reviewed third-party upstream extension (used as-is or narrowly adapted), never arbitrary or auto-discovered ones. Extensions carry machine-enforceable tool/result orchestration and diagnostic commands. No extension may bypass the bridge's graph/API gates, trust or leases, or silently read global credentials or make hidden auxiliary model calls. The system prompt is ours: a small project-owned prompt replaces Pi's default coding prompt, which must not be retained by accident (F1/F3 verify what the first model request actually contains). The prompt plus the existing on-demand knowledge tools handle model judgment. No pile of prompts or skills, and no ready-made task recipes.
6. **Authority split.** Nuke Python execution, trust, graph inspection, API-recovery gates and leases stay in the existing bridge (`bridge/`, `mcp_server/`). The extension does not duplicate Nuke state or pre-validate arbitrary Python or compositing judgment.
7. **Per-user data directory** for config, auth and sessions, separate from installation, source and upgrades. Reuse existing appdata and chat-store conventions. No automated global imports and no global Pi/session migration unless the user asks.
8. **Accounts.** Qt UI (Settings → "Pi accounts…", any selected harness) supports API-key entry and subscription OAuth login, logout, cancel, error and status over the pinned SDK's full dynamic catalog (1.4.0 returned 41 API-key + 9 OAuth entries); no provider shortlist or hardcoded provider list. Real user consent only: no auto-consent, no key copying, the human opens any browser link. Secrets never reach the model, logs, traces, chat, QSettings, argv or inherited/global environment. Pi's default auth store is a JSON file (`0600` in a `0700` directory) and is not encrypted; use that existing store first with minimal permissions. An OS keyring is optional and deferred. SDK external-store choices (AWS profile, ADC) are used only when the user explicitly picks them. Check = local resolution plus OAuth renewal only if needed, not API validation or a forced refresh; refresh cannot be cancelled and close waits for SDK persistence. Logout removes the local credential only, no provider-side revocation. Credential changes reach the running RPC process by the existing same-session idle renewal, with no automatic abort or timer.
9. **Desktop environment.** Preserve `DISPLAY`, `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, DBus and `XAUTHORITY` for Pi children. Block ambient provider-credential fallback through verified auth-context or environment scoping, not by wiping the environment.
10. **Manual steering only.** No timer, deadline, automatic interrupt, retry or finish-up nudge ever acts on a model. Observational reporting clocks are separate. Existing `harnesses/base.py` 1000 ms process-stop escalation is process management, not model control.
11. **TUI scope.** Existing Qt chat stays. Pi commands reach it through `get_commands` and explicit RPC actions (F4); TUI-only custom views are declared unsupported rather than emulated. Real `InteractiveMode` exists publicly, but a PTY, image, keyboard and clipboard terminal widget would be new work and is not required here.
12. **Other harnesses and global config stay untouched.** Codex, Claude, OMP and OpenCode keep their current integration. Global Pi files are not edited as part of this plan.
13. **Reuse first, custom last.** Before building any custom behaviour (extension, command, steering, web, side-conversation), record in the feature's review what exact upstream capability was checked: Pi 1.4.0 built-ins/RPC, existing plugin code (e.g. `SteeringController`, leases, epochs), then [RESEARCH-pi-extensions.md](RESEARCH-pi-extensions.md). Reuse as-is where it fits; otherwise make the narrowest adaptation, and build small glue only for a measured gap. A candidate has two statuses. **Evaluation:** only after pin, license, code, private-auth, cost and no-hidden-model-call source review, and only in a later, explicitly user-authorized private evaluation install/load, may it run. **Accepted:** only after the full feature live Nuke gate does it enter production use or the normal allowlist. Source research alone authorizes neither. Research does not add features: no new timers, automatic side conversations or model-control behaviour, and the existing manual steering is not rebuilt or replaced.

## Non-goals

Forking Pi; ACP adoption; Pi Durable; a full SDK frontend; an embedded TUI renderer; an automatic updater; a new benchmark or replay framework; new Nuke-driving helpers; automatic graph dumps; OS-level sandboxing; claims that every Pi slash command maps to the Qt UI.

## Verified baseline (current global Pi, not the private install)

- Global `pi-mcp-adapter` removed with the official Pi command. `PiRpcClient._prepare_mcp` no longer installs it. OMP unchanged. Legacy global `nuke_mcp` registration removed at the user's approval; current `nuke` kept.
- Native Pi MCP, codemode and `tool_search` verified through actual SDK, stdio sidecar and real Nuke: 275 pytest in 9.78 s across 14 files, plus a 65.049 s MCP call past native 60 s idle timeout using standard token-bearing progress keepalives (not a model timer or retry). Proof: `/tmp/nuke-native-pi-HhQb4Y/pytest-output.txt`, `native-pi-smoke-context-fixed-output.txt`. Image forwarding used a fixture PNG only; no model-provider turn.
- Native codemode resolves MCP `isError` as a normal value, and images need explicit `image(block)` forwarding. Dependent mutations must await graph/context checks.
- Graph-inspection, API-error recovery and runtime-evidence gates, private generation delivery tokens and the manual-steering controller/lease exist and are verified in real Nuke (see [PLAN.md](PLAN.md) and [ORCHESTRATOR.md](../ORCHESTRATOR.md)). Steering evidence was gathered on the old global runtime, so it does not yet cover the private runtime.
- Not verified: any private installation, SDK auth helper, Nuke TypeScript extension, Qt command integration, or credential flow.

## Planned scope (details and order live in the integration plan)

| ID | Feature |
|---|---|
| F1 | Fresh private Pi plus native Nuke vertical slice, working without global Pi/`PATH`/settings/auth |
| F2 | Private accounts and model selection (API key, subscription OAuth, logout, RPC sees changes) |
| F3 | Own TypeScript Nuke extension and compact prompt for mechanical tool/error/image handling |
| F4 | Pi commands inside the existing Qt UI |
| F5 | Manual steering and session continuity on the private runtime |
| F6 | Clean cutover, distribution and full acceptance |

Delivery rule: complete each feature, run real Nuke scenarios, review the whole feature, fix the full defect batch, rerun, and only then add regression tests and advance. Workflow detail is in [INTEGRATION-pi-runtime.md](INTEGRATION-pi-runtime.md).

## Why RPC plus selective SDK

- The user's criterion is equal capability with the least implementation, maintenance and model cost, not architectural purity.
- RPC already carries prompt, steer, follow-up, abort, clear-queue, models, thinking, sessions, tree, fork and `get_commands`, and the Qt UI plus steering code are built on it.
- The gap is auth only, and the SDK covers it with a small helper. A full SDK frontend would reimplement working UI and steering without a demonstrated benefit.
- ACP was checked and does not reduce the work (below).

## Research register

Evidence is Pi 1.4.0 installed source/docs read read-only at `~/.pi/agent/install/releases/1.4.0/node_modules/@earendil-works/pi-coding-agent` (docs, `dist` types, sibling `pi-ai`) unless a URL is given. No global config, auth or database was read. Re-verify any signature against the pinned version before use.

| Topic | Finding | Source |
|---|---|---|
| Auth API | `ModelRuntime.login(provider, type, AuthInteraction)` and `logout` exist. `AuthInteraction` has `prompt` (text, secret, select, manual_code) and `notify` (auth_url, device_code, progress, info). Private `authPath`/`CredentialStore` are supported. | Pi 1.4.0 SDK types |
| RPC auth gap | RPC has no auth commands; auth needs the SDK. RPC has limited extension UI, no full custom TUI. | Pi 1.4.0 `rpc.md` / `rpc-commands.md` |
| Credential precedence | A stored credential owns its provider; environment keys apply only when nothing is stored and a failed refresh does not silently fall back. Shapes with `auth.json`. | pi-ai README (see section 6 of [RESEARCH-pi-durable.md](RESEARCH-pi-durable.md)) |
| Public hooks | Extension `tool_call` can block; `tool_result` can transform content, details, structuredContent and `isError`; nested codemode events carry `parentToolCallId`; `ExtensionToolContext.executeTool` runs normal validation and hooks (not every event context has it); `registerCommand`, `appendEntry` (non-model state); RPC `get_commands` and `prompt` run extension commands. | Pi 1.4.0 extension docs/types |
| Full TUI | `InteractiveMode` and an injectable `Terminal` are public, but the plugin has no PTY or terminal widget, and image/keyboard/clipboard fidelity is untested. | Pi 1.4.0 types; current repo |
| Desktop inheritance | Children must keep the user's display, DBus and runtime-dir variables; provider-credential isolation must be scoped, not an environment wipe. | Existing `harnesses/base.py` env handling; design decision 9 |
| ACP | Pi 1.4.0 has no native ACP. `Attamusc/pi-acp` wraps Pi RPC and assumes preconfigured auth, so it adds no auth or parity advantage. ACP v1 has its own authentication model. | <https://github.com/Attamusc/pi-acp>, <https://agentclientprotocol.com/protocol/v1/authentication> |
| Durable | Experimental, moving API, new storage with no Pi-session importer, no built-in MCP client, depends on `pi-codemode`; not needed for native MCP/codemode or one Nuke agent. Revisit only for durable queues, restart-surviving state or multi-client needs. | <https://earendil.com/posts/pi-durable/>, [RESEARCH-pi-durable.md](RESEARCH-pi-durable.md) |
| Native MCP/codemode | Proven end to end on the old global runtime (see baseline). Default native MCP idle timeout is 60 s with no supported JSON disable; progress keepalives from the owned sidecar cover it. | `/tmp/nuke-native-pi-HhQb4Y/` outputs |

## Superseded

- [RESEARCH-pi-durable.md](RESEARCH-pi-durable.md) short recommendation 2 and section 5/10 describe a long-term SDK/project-owned Node worker and interim global-CLI isolation flags. The current direction is the private install above with RPC retained, so read those as research only.
- The earlier global-adapter and global-agent-dir approach (`_agent_dir` defaulting to `~/.pi`) is the baseline this plan replaces, not the target.

## Open points the sources could not settle

- Resolved in F2 implementation: public SDK reload does not refresh a live RPC process's model snapshot (credential reads detect revisions but `get_available_models` is stale), so idle-process renewal is used. Providers/methods come from the live SDK catalog (50 entries). Whether the old `openai-codex` and `zai` IDs remain is not decided by F2 and needs no hardcoding (unresolved check 9 in [RESEARCH-pi-durable.md](RESEARCH-pi-durable.md)).
- How a reopened Pi session treats a dangling tool call with no stored result.
- Human availability for live account approval; if absent, F2 stays implemented but NOT ACCEPTED, not approved.
