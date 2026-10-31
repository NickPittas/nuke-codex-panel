# Research: existing Pi extensions before custom building (2026-10-29)

Purpose: decide REUSE / CUSTOMIZE / REFERENCE / DEFER / REJECT for web search/fetch, `/btw`-style steering, and small Pi utilities, before any custom extension work. Plan linkage: [PLAN-pi-runtime.md](PLAN-pi-runtime.md), [ARCHITECTURE-pi-runtime.md](ARCHITECTURE-pi-runtime.md), [INTEGRATION-pi-runtime.md](INTEGRATION-pi-runtime.md).

## Evidence status

- **Source-read only.** Findings come from small read-only scout agents reading primary repos/docs and the installed Pi 1.4.0 tree (`~/.pi/agent/install/releases/1.4.0/node_modules/@earendil-works/pi-coding-agent/`). The scouts read the source files; the parent read only the READMEs of `nicobailon/pi-web-access` and `nicknisi/pi-extensions/packages/btw`, not their source.
- **Nothing here was installed, run, or tested against Pi 1.4.0 / our RPC / codemode / live Nuke.** Every compatibility statement is **UNTESTED**. Line numbers refer to the versions named and may drift.
- Popularity (stars, downloads) is not evidence of quality and is not used.
- Absence statements mean "not found among the reviewed candidates", not "none exists".
- Installation gates, in order: (a) source/license/pin/private-auth/cost review BEFORE any authorized private candidate installation; (b) the Pi 1.4 / RPC / codemode / live-Nuke feature gate in INTEGRATION BEFORE production adoption. **No installation is authorized now.**

## Reuse-first rule

1. Existing exact capability first: Pi 1.4 built-ins, our Nuke MCP (offline compositing knowledge, installed SDK docs), `SteeringController`.
2. Then a pinned, licensed, reviewed third-party package that matches the exact need.
3. Then a small adaptation of an official example.
4. Custom glue only for a measured gap.
A third-party extension MUST NOT bypass the graph/API gate, trust, or leases, or silently borrow global keys. Trusted curated extension set = pinned, licensed, reviewed; never global auto-discovery.

## 1. Web search / fetch

Installed Nuke facts (Foundry node/API behavior) come from Nuke MCP knowledge and installed SDK docs first; web is for primary-reference lookups not covered there. No new Foundry crawler or research-agent framework.

### pi-web-access (nicobailon) — CUSTOMIZE: best candidate, as a separate MCP server, config-restricted
- Source: https://github.com/nicobailon/pi-web-access, v0.46.0, MIT. Its `package.json` dev dependency (1.0.4) and `peerDependencies` (`*`) only DECLARE a Pi version; they are not proof of testing. Our 1.4.0 is **UNTESTED**.
- Large surface (providers, curator, video, summaries). Extension path with default auto-routing may use Pi/Codex auth and helper summary models, and auto-clones GitHub URLs. Do **not** adopt that path blanket.
- Standalone MCP path (`bin: pi-web-access-mcp` → `dist/mcp-cli.js`, MCP SDK 1.32.1), per scout source read of [`web-tool-core.ts`](https://github.com/nicobailon/pi-web-access/blob/main/web-tool-core.ts), [`exa.ts`](https://github.com/nicobailon/pi-web-access/blob/main/exa.ts), [`utils.ts`](https://github.com/nicobailon/pi-web-access/blob/main/utils.ts), [`github-extract.ts`](https://github.com/nicobailon/pi-web-access/blob/main/github-extract.ts), [`package.json`](https://github.com/nicobailon/pi-web-access/blob/main/package.json) (main branch links; scout read v0.46.0, so line numbers may drift):
  - `createStandaloneWebToolCore()` has no extension context, curator or summaries, so no auxiliary Pi/curator/summary model calls. With explicit Exa and plain fetch this profile does not use the Pi helper LLM; other search providers may invoke hosted models themselves. `fetch_content` `answer` mode is rejected over MCP. Proposed UNTESTED profile: `readable`/`raw` fetch only; the claim that other fetch modes are disabled by configuration is unverified. Cloudflare `extract` is not a default mode.
  - Pi-bound credentials (ChatGPT/Codex sign-in, Pi model credentials) are refused in standalone mode rather than borrowed.
  - `@earendil-works/pi-*` imports are type-only in this path, so Pi SDK version drift matters only for the extension install path.
  - Config/cache root honors `PI_CODING_AGENT_DIR` first, then XDG, then `~/.pi` → set it to a plugin-private directory. Standalone results are in-memory and bounded.
  - `githubClone.enabled: false` disables autoclone (default true; default clone path `/tmp/pi-github-repos`). Individual tools are config-disableable.
  - `{"provider":"exa"}` pins one provider with no auto-chain. Exa keyless goes to remote `https://mcp.exa.ai/mcp`, so queries leave the machine. This is an external service: **no guarantee of free, unlimited or private**. An `exaApiKey` switches to the direct API.
  - Candidate config (UNTESTED, from scout source read): `{"provider":"exa","githubClone":{"enabled":false},"tools":{"sourceCheck":{"enabled":false}}}`, `readable` fetch, optional `cache:"off"`, env `PI_CODING_AGENT_DIR=<plugin-private dir>`. With clone off, GitHub URLs fall back to the GitHub API view. Exa keyless rate limits are unknown; no price guarantee.
- Delivery shape: an **additional, separate native Pi MCP server** (own stdio process, own env/config) next to the Nuke MCP. It is NOT a web proxy inside the Nuke Python MCP sidecar. Choose MCP **or** extension, never both (duplicate tools).
- Adoption conditions: provider pinned, readable/plain fetch only, private config/cache/auth, no hidden auxiliary model calls, no browser cookies, no global credential reads, GitHub clone off. Allowlist must permit selected web search/fetch alongside Nuke MCP/codemode/discovery (user approved web search as an auxiliary tool as needed). Model tools are not Nuke-only while this is enabled; default host coding tools stay disabled (not implied).
- Before any install: the review gate in Evidence status. Network scope to require, not assume: search requests go only to the chosen provider; page fetch goes only to the explicitly requested public URLs; no hidden credential, helper-model or other destinations. Verify by code review and an actual Pi 1.4 native-MCP + codemode run.

### pi-websearch (code-yeongyu) — DEFER
- Source: https://github.com/code-yeongyu/pi-websearch
- MIT, search-only, no fetch. Default native route assumes a `senpi` fork; fallback route exists, so "fork-route gap" is a limitation, not a universal break. Adds nothing over pi-web-access's pinned configuration; revisit only if its fallback is shown sufficient.

## 2. `/btw` and manual steering

Existing semantics (installed Pi 1.4.0 docs/source, UNTESTED by us for this research): RPC/SDK `steer` queues for the next turn boundary and does not interrupt thinking or a running tool; `follow_up` queues until idle; `abort` is a true interrupt and keeps history (`agent_settled {aborted:true}`); `clear_queue` returns queued text, and the documented Esc recipe is `clear_queue` → `abort` → restore (`docs/rpc-commands.md` ~107-128). `abort` cannot undo or stop an already-dispatched native Nuke call. The official `examples/extensions/send-user-message.ts` README labels `/steer` as interrupting; the code actually queues. Do not copy that claim.

### Built-in RPC steer/follow_up/abort/clear_queue + our `SteeringController`/leases/epochs — REUSE
- Our controller (`harnesses/intervention.py`, `harnesses/pi_rpc.py`, `bridge/control.py`) adds process renewal, per-process epochs, sidecar retirement, fencing and drain. No reviewed extension provides these. Do not rebuild or replace with a weaker extension.

### @nicknisi/pi-btw 0.3.0 — REFERENCE (optional pattern, not in current scope)
- https://github.com/nicknisi/pi-extensions/tree/main/packages/btw, MIT, 727-line `index.ts` read by the scout (parent read the README only). Off-context side conversation: one-off model call over a branch snapshot, `ctx.ui.custom()` overlay (TUI-only), non-model custom entry persistence; "promote" sends `deliverAs:"steer"` (queues, no abort); fork copies `SessionManager` internals (fragile).
- It is **not** a replacement for manual interrupt. Candidate only for future off-context Q&A.
- Cost/privacy: separate model calls cost tokens and need a provider; per source it may fall back to the current (possibly expensive) model if the cheap one is unresolved; private config path and global PATH concerns apply. Does not fit our RPC/Qt UI without adaptation.
- No automatic addition. Revisit only on explicit request.

### pi-interrupt-steer 0.1.0 (ezoushen) — REJECT as drop-in
- https://github.com/ezoushen/pi-extensions/tree/main/extensions/interrupt-steer, MIT. Real abort, but TUI shortcut/editor only, fixed 5 s idle and 60 s acceptance deadlines, no Nuke drain/fencing/renewal. Idea worth keeping: confirm the replacement message actually started before clearing input; our intervention lifecycle already covers it.

### pi-queue-steer-factory 0.17.11 — REJECT / DEFER as dependency
- https://github.com/monotykamary/pi-queue-steer-factory, MIT, tested with Pi 1.3.0 (1.4 UNTESTED). Queue ownership is TUI-only; RPC input passes through. Headless `QueueController` export is not evidence of drop-in use; scope far exceeds needs. Its `/pause` (drain at tool boundary) matches what our controller already does.

Conclusion: among the reviewed, none is a safe full Nuke manual-steering solution. No automatic timers, finish-up nudges or deadlines are introduced.

## 3. Small utilities (official Pi 1.4.0 examples, MIT; extension examples: https://github.com/earendil-works/pi/tree/main/packages/coding-agent/examples/extensions; SDK examples under `packages/coding-agent/examples/` in the same repo, including the auth sample; scout read the installed 1.4.0 copies)

| Item | Verdict | Note |
|---|---|---|
| [`rpc-demo.ts`](https://github.com/earendil-works/pi/tree/main/packages/coding-agent/examples/extensions), `examples/rpc-extension-ui.ts` (same repo `packages/coding-agent/examples/`) | REFERENCE | Map of `ctx.ui` methods that cross RPC (`select/confirm/input/notify/setStatus/setWidget/setTitle/setEditorText`). Check Qt responder coverage; do not install the TUI client. |
| `provider-payload.ts` (examples/extensions) | REFERENCE (only for a targeted debug gap) | Logs raw payloads and headers with no redaction; credentials risk. No default full request logging. |
| `permission-gate.ts`, `protected-paths.ts` (examples/extensions) | REFERENCE | Only if a gap appears that the Nuke bridge trust/lease checks do not already guard. Note `ctx.hasUI` is true in RPC only when the client answers UI requests. |
| `shutdown-command.ts`, `session-name.ts` (examples/extensions) | REFERENCE | Tiny idioms, only if an existing SDK/RPC action lacks one. |
| Auth packages | NONE adopted | Reuse `ModelRuntime`/`AuthInteraction` SDK auth. RPC has no native `/login`; do not claim it. |
| Session export | REUSE SDK | `exportSessionToJsonl` exists; HTML export is TUI-renderer-based. Not a new feature merely because an example exists. |
| `truncated-tool.ts`, summarize/todo/games/etc. | REJECT | No Nuke relevance; truncation utilities importable directly. |

## Plan impact

- F1-F6 order unchanged; no new features. Before building any extension for a feature, check this doc and record REUSE/CUSTOMIZE/REFERENCE/DEFER/REJECT, then build the smallest glue for a measured gap.
- Web: if the web feature is taken up, start from the pi-web-access standalone MCP configuration above, gated by the live-Nuke workflow.
