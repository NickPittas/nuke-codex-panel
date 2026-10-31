# Research: Pi Durable vs. plain Pi SDK/RPC for the Nuke panel

Researched 2026-10-29 from web sources only (no clone, install, run, upstream code execution, or local credentials).
Scope: advice/design input. Nothing here is implemented or approved.

> **Superseded direction (2026-10-29):** the current plan is a fresh official Pi installed privately in the plugin, keeping the existing Pi RPC and Qt UI, with a selective SDK auth helper. Not a project-owned SDK worker, global-CLI flag hardening, or Durable. See [PLAN-pi-runtime.md](PLAN-pi-runtime.md). The recommendation, section 5/10 direction text and checks below are research input only; the primary facts stay valid.

## Evidence labels

| Label | Meaning |
|---|---|
| **BLOG** | Promise in the Earendil announcement. Not proof. |
| **README / DOC** | Package or docs statement on `main`. Still prose. |
| **SPEC** | `packages/durable/docs/spec.md` on `main`, marked normative by its authors. |
| **SRC** | Read directly in a source file on `main`. |
| **NPM** | npm registry metadata. |
| **INFERENCE** | My reasoning from the above. Not observed. |
| **UNKNOWN** | Not found in what I read. Needs an acceptance check. |

Primary sources:

- Blog: <https://earendil.com/posts/pi-durable/>
- README: <https://github.com/earendil-works/pi/blob/main/packages/durable/README.md>
- SPEC: <https://github.com/earendil-works/pi/blob/main/packages/durable/docs/spec.md>
- CHANGELOG: <https://github.com/earendil-works/pi/blob/main/packages/durable/CHANGELOG.md>
- `package.json`: <https://github.com/earendil-works/pi/blob/main/packages/durable/package.json>
- Task source: <https://github.com/earendil-works/pi/blob/main/packages/durable/src/harness/tool.ts>
- npm: <https://registry.npmjs.org/@earendil-works/pi-durable>
- Plain Pi SDK/RPC docs: <https://github.com/earendil-works/pi/tree/main/packages/coding-agent/docs> (`sdk.md`, `rpc.md`, `rpc-commands.md`, `cli.md`, `configuration.md`, `mcp.md`, `session-format.md`)
- Resource loader source: <https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/resource-loader.ts>
- Provider/auth: <https://github.com/earendil-works/pi/tree/main/packages/ai> (README), `packages/coding-agent/src/core/model-runtime.ts`

## Recommendation (short)

1. **Do not make Pi Durable the panel's primary harness now.** It is explicitly experimental and its API is moving fast (five minor releases in three weeks; `main` already ahead of 1.4.0). It is *not* wrong because of its replay feature: it defaults to no replay and offers a genuine durable-state model that the plain SDK lacks. The cost is adoption risk: a new storage format with no importer from Pi sessions, an MCP/auth adapter to write, and a worker to maintain.

### Source baseline: `main` vs installed Pi 1.4.0

- Everything above and below that cites `main` (README, SPEC, docs, source) describes the GitHub `main` branch on 2026-10-29. `main` is ahead of the 1.4.0 packages (see section 2).
- Per a local scout (not web research): the installed `pi` is a managed launcher at `~/.local/bin/pi` resolving through `~/.pi/agent/install/current-version` to `@earendil-works/pi-coding-agent` 1.4.0 (Node ≥ 22.19). Native MCP, `codemode` and `tool_search` exist in 1.4.0. `-ne`, `-ns`, `-np`, `-nc/--no-context-files` and `--no-mcp` exist there; `--no-mcp` only disables the built-in `mcp` extension. **Update 2026-10-29:** the global `pi-mcp-adapter` extension was removed (it replaced native MCP) and the panel no longer installs or requires it; `~/.pi/agent/mcp.json` is unchanged, so the `nuke` registration is read by native MCP (default `codemode` exposure, tools named `mcp__nuke__*`).
- The OMP binary is a compiled build of unknown exact version and was not launched. Do not assume Pi flags or RPC behaviour apply to it.
- Rule: before relying on any flag, SDK option or RPC field, verify it against the installed 1.4.0 package (or the pinned version you adopt), not `main`.
2. **Lower-risk path: plain Pi with explicit project ownership.** Near term, keep the current RPC child on **native Pi MCP** (no extension) and, optionally, harden it with the isolation flags that exist in the *installed* Pi (see baseline below) together with a project-owned `PI_CODING_AGENT_DIR`/`--session-dir`. Note `-ne` would also disable built-in MCP unless re-allowed with `-e builtin:mcp`. A plain SDK in a project-owned Node worker is a possible long-term option for stricter isolation, but it is **not required** for native MCP/codemode. Keep the dependency-free Python MCP server.
3. **Revisit Durable as a flagged prototype** when durable queued input, restart-surviving transcripts and task state, multi-client attach/watch, typed documents (e.g. a Nuke-script-state document), or surviving worker crashes become real requirements. Pin exact versions; treat every upgrade as a migration. It adds a project-owned TypeScript sidecar that the project must build, test and maintain.
4. Keep the **framework choice** (Pi RPC vs SDK vs Durable) separate from the **ownership choice** (project-owned Node worker vs Python-only wheel). Both Pi RPC and Durable need a Node process. A Python-only wheel is packaging work, not a reason to pick either.

**Qualification:** this recommendation weighs maturity, migration cost and ownership, not a defect in Durable. Durable defaults to no replay (`replay` omitted means `unsafe`) and provides real durable state (see section 10). Its crash-safety semantics are compatible with the panel's no-replay rule; the open question is whether that state is worth a new store, a new sidecar and version churn.

### Does Durable add value for MCP/codemode or the single Nuke agent? No.

- **MCP and codemode:** ordinary Pi 1.4.0 already provides native MCP, `codemode` and `tool_search`, so Durable is not needed for them. Durable (which depends on `pi-codemode`, per the earlier research) adds durable orchestration on top, not an MCP client: it has no built-in MCP client, so Nuke's stdio server would still need its own bridge integration (see section 7).
- **What Durable actually adds:** structured persistent queues/tasks, restart-surviving transcripts and state, and multi-client attach/watch. One interactive Nuke agent driven by the panel does not need these.
- **Safety:** Durable does not make external Nuke effects exactly-once. It only avoids auto-replay by default; a mutation that may have partly run is reported, not rerun. The panel's own no-replay and bridge fencing already provide that behaviour.
- Nothing here argues for an SDK rewrite to get native MCP. Revisit Durable only if the queue/task/multi-client requirements above become real.

## 1. Blog promise vs code-verified vs unknown

| Topic | Blog says | Verified in README/SPEC/SRC | Unknown |
|---|---|---|---|
| Status | "experimental new package" | README: "**Experimental.** The API changes without notice between releases." | none |
| Embedding | Node/TS library; `Harness.open(storage, {models, registry, env}, ctx)` | Same API in README Quick Start; SPEC §2.2 `HarnessOptions` (`models`, `registry`, `settings`, `env`, `readOnly`, `now`, `setTimer`, `onWake`, `onReport`, `telemetry`, `identity`) | Python or non-Node embedding is not offered |
| Crash recovery | "A tool call that was cut off reruns if it is safe to; otherwise the model is told it was interrupted"; "A model request that was cut off is sent again" | Tool rule is code-verified (§3 below). **The model-request claim is stale**: CHANGELOG (Unreleased) says an in-flight request at host death is now a *failed attempt under `settings.retry`*, not a resend; only a clean `close()` resends | Behavior of released 1.4.0 vs `main` for this exact point (1.4.0 changelog does not mention it; Unreleased does) |
| Steering | "Any client can steer a running conversation"; message "joins the running work after the current tool calls" | SPEC §6 boundary table: steer placed at `postTools` or `final`, never mid-model-stream or mid-tool | Nothing preempts thinking; see §5 |
| Exactly-once | "A `requestId` makes a submission exactly-once" | SPEC/README: `requestId` dedupes the *submission*. Tool effects are not made exactly-once (SPEC §7.3: "a replay-safe tool with external effects still needs its own idempotency") | none |
| Reference app | Links to `coding-agent/src/experimental/durable` at tag `v1.0.0` | On `main`, `packages/coding-agent/src/experimental/` now holds only `source-resolver.ts`; the demo apps are gone from `main` | Contents at tag `v1.0.0` not read |
| Size | ~15,000 lines (no tests) | not independently measured | n/a |

Blog code samples use a model ID (`gpt-6.1-sol`) that is not in the README's quick start (`gpt-6-sol`). Treat blog snippets as illustrative.

## 2. Version, runtime, license, dependencies

- **Version (NPM):** `latest` is `1.4.0`, published 2026-10-21. History shows 0.0.1 on 2026-09-19, `1.0.0` on 2026-10-01, then 1.1.0 (10-07), 1.2.0 (10-12), 1.3.0 (10-15), 1.4.0 (10-21): five minor releases in three weeks.
- **`main` is ahead of 1.4.0 (CHANGELOG "Unreleased"):** a long list of breaking changes (watch API, `watchEvents()` removed, `Storage.commit(writes, adopt, ctx)` signature, `pi.live` document v1→v3, `onReport` shape, `SessionEnd` tag, `subscribeCommits` → `observeCommits`, task parking removed, etc.). The README I read is `main`'s, not necessarily the 1.4.0 tarball's. **Read the published tarball's README/types, not `main`, before relying on any signature.**
- **Runtime (SRC `package.json`):** `engines.node >= 22.19.0`. Bun and Cloudflare Durable Objects are described for the portable SQLite/JSONL cores. There is no Python API.
- **License (SRC):** MIT for `pi-durable`; `pi-coding-agent` also MIT. Licenses of transitive dependencies were not audited.
- **Dependencies (SRC, `main`):** `@earendil-works/chord`, `pi-ai`, `pi-codemode`, `pi-telemetry` (all exact `1.4.0`), `@silvia-odwyer/photon` `0.3.3`, `diff` `8.0.4`, `typebox` `1.3.27`. README adds that the package root loads TypeBox "about 23 MB of peak RSS unbundled".
- **Not a dependency:** `pi-mcp`, `pi-coding-agent`, `pi-agent-core`.
- **Downgrade lock (CHANGELOG 1.4.0):** opening SQLite storage migrates it to schema v2; a migrated database cannot be opened by 1.3.0 or earlier. Rollback past a release is not supported.

## 3. Crash recovery, replay, and dispatched remote mutations

This is the most important area for the panel (Nuke mutations must never auto-replay).

**Code-verified (SRC `harness/tool.ts`, SPEC §5.2, §8.4):**

1. Every tool call is a durable `pi.tool` task. In phase `call` it resolves the tool, validates, runs `beforeTool` hooks, then **commits intent** (`{phase:"execute", arguments, replay}`) *before* running `execute()`.
2. After a crash, a task in phase `execute` reruns **only if both the stored policy and the current declaration are `replay: "safe"`**. Otherwise it commits an error result `Tool X was interrupted and may have partially run` built from the slot's durable partial output and ends `failed`.
3. `replay` is **unsafe by default** when omitted (SPEC §7.3). A current `unsafe` declaration vetoes a stored `safe`; a current `safe` never upgrades stored `unsafe`. A tool that no longer resolves is `unsafe`.
4. A crash *before* the intent commit (still phase `call`) reruns the `call` phase from the top, including `beforeTool` hooks. No tool effect has started yet, but hooks must be idempotent or use memos (README, SPEC §7.3).
5. A task cut off `settings.restartLimit` times (default 5) ends with a `restart_limit` error result instead of rerunning.
6. Replay-safe callers that use `api.executeTool()` get nested calls reattached by key, but "a replay-safe tool with external effects still needs its own idempotency" (SPEC §7.3).

**Consequence for dispatched remote mutations (INFERENCE from the above):**

- With the default `unsafe` policy the *harness* dispatches at most once. The effect happened zero or one times, and the model is told "may have partially run". The harness cannot know which.
- `requestId` dedupes only the *user submission*, not the Nuke effect.
- Streamed tool output is stored *deferred*: SPEC §4.1 / README say a crash can lose up to about `persistWithinMs` (default 1000 ms) of streamed output. The "interrupted" result may therefore miss the last second of partial output. A tool that needs a reliable record of "I dispatched op X" should record it in a memo or `api.commit()` (immediate commit) **before** calling the bridge. [INFERENCE: memo/commit are non-deferred; README says deferral is opt-in via `persistence: {kind:"deferred"}`.]
- To tell "did it land?" after an interruption, the Nuke bridge needs its own operation-id journal and a read-only reconciliation tool. Durable does not provide this. [INFERENCE]

**Abort vs. in-flight remote effect (SPEC §5.4, §8.4):** abort marks the task; the run invocation may not commit after the mark; the abort handler commits an `aborted` result from the slot's partial output. The tool only stops if its code honors the invocation signal/context. An abort does **not** reach into Nuke. A dispatched mutation can still complete after abort, while the transcript says "aborted". Same reconciliation need as above.

**Generation recovery (SPEC §8.3, CHANGELOG Unreleased):** a model request in flight at host death is a failed attempt: partial answer kept as an aborted entry, backoff, then retry or `runFailure: interrupted`. Not tied to tool replay.

**Plain Pi:** no durable task machinery. The blog states the contrast directly: if Pi dies "you look at what happened and tell it to continue". Pi never auto-replays a tool, which already satisfies "never replay mutations". **UNKNOWN:** how the Pi session context treats a tool call with no stored result when the session is reopened (my pi-ai README search found no orphan-result handling). Durable's SPEC §2.1 explicitly synthesizes missing tool results; plain Pi's behavior must be tested.

## 4. Abort vs. steer (manual intervention requirement)

| | Pi Durable | Plain Pi (SDK/RPC) |
|---|---|---|
| Steer | `submit({type:"input", whenBusy:"steer"})`; placed at `postTools` boundary (after current tool round), joins the run (SPEC §6). `whenIdle:"reject"` makes it steer-or-fail. | `steer`/`prompt` with `streamingBehavior:"steer"`: "delivered after the current assistant turn finishes executing its tool calls, before the next LLM call" (`rpc-commands.md`) |
| Follow-up | Placed at `final` boundary | Same |
| Preempt thinking / abort current tool | `conversation.abort()`: withdraws queued inputs, aborts the task tree, waits for idle; streamed partial becomes an aborted assistant entry | `abort`: "Abort the current operation and wait for the session to become idle"; RPC advises `clear_queue` before `abort` because abort otherwise continues queued messages |
| Same conversation after abort | Yes (transcript is committed entries) | Yes (session file) |

Neither product offers a *mid-generation soft steer*. Both implement "wait for tools, then inject". The panel's existing renew/fence logic is its own mechanism on top of Pi; Durable would not replace it. [INFERENCE; user's parent notes agree]

## 5. Embedding interface and isolation / discovery

**Durable (SPEC §7.1, §2.2, README):**

- Explicit, application-owned `Registry` (`createRegistry()`, `install`, `uninstall`). Registry is process-local, not persisted; conversations store extension *names*.
- **No global discovery.** Durable does not read `~/.pi`, `.pi`, AGENTS.md, skills, prompt templates or `mcp.json`. Prompt sections that load context files or skills are extension code the host writes (README `ProjectContext` example; SPEC example `ContextFiles`/`Skills` are illustrative and not exported by `package.json`). Tools are only what you install (`CodingTools` is opt-in: "nothing installs them automatically", SPEC §7.3).
- `env` is explicit (`NodeExecutionEnv` or a remote `ExecutionEnv`).
- `HarnessOptions.identity` defaults to `{attribution: PI_ATTRIBUTION}` which names pi to OpenRouter/NVIDIA/OpenCode. Override with your own or `{attribution:null}`.
- Isolation is therefore by construction, but you must also reimplement anything you used from Pi's resource model (skills, prompt templates, context files, trust, packages).

**Plain Pi SDK (DOC `sdk.md`, SRC `resource-loader.ts`, example `12-full-control.ts`):**

- Default `createAgentSession()` "uses the working directory, discovered resources, stored settings, and configured credentials" (shared global state).
- Fully isolated: supply `resourceLoader` returning empty extensions/skills/prompts/themes/agents files; `modelRuntime` with explicit `authPath`/`modelsPath`; `SettingsManager.inMemory`; `SessionManager.inMemory` or custom; explicit `agentDir`.
- `DefaultResourceLoader` options verified in source: `noExtensions`, `noSkills`, `noPromptTemplates`, `noThemes`, `noContextFiles`, `disabledBuiltinExtensions` (e.g. `mcp`), `additional*Paths`, `extensionFactories`, `systemPrompt`, `appendSystemPrompt`, `agentDir`.
- SDK sessions do **not** load the CLI's built-in codemode, tool_search and MCP extensions; add `createMcpExtension()` etc. yourself (DOC `sdk.md`).

**Plain Pi CLI/RPC (DOC `cli.md`, `configuration.md`, `security.md`):**

- Flags in the **`main` docs**: `-ne/--no-extensions`, `-ns/--no-skills`, `-np/--no-prompt-templates`, `-nc/--no-context-files`, `--no-themes`, `--no-mcp`, `--session-dir`, `--no-session`, `--offline`, `-a/-na` (project trust). Per the scout's source read of the installed 1.4.0, `-ne`, `-ns`, `-np`, `-nc` and `--no-mcp` all exist (`-nc` in parser lines 196-199, applied at resource-loader line 466). Explicit `-e/--skill/--prompt-template` paths still load under the `--no-*` flags.
- Agent dir via `PI_CODING_AGENT_DIR`. Global `mcp.json`, `settings.json`, `auth.json`, extensions, skills, prompts all live under it.
- Context files (`AGENTS.md`, `CLAUDE.md`) load **regardless of project trust**; `-nc` is required to suppress them (in the installed 1.4.0 it suppresses both global and project context files). `-ne` disables all extensions, including built-in MCP unless explicitly re-allowed with `-e builtin:mcp`.
- Main parent finding (not from web): the panel's `PiRpcClient` passes none of these isolation flags and `_prepare_mcp` writes the global `mcp.json` (it no longer installs any Pi extension). So the current setup is exposed to the user's global Pi extensions/skills/prompts. This is a configuration gap, not a Pi limitation.
- **Caution on flags (installed 1.4.0, per scout):** `--no-mcp` only adds `disabledBuiltinExtensions: ['mcp']`; it disables native MCP for that run. `-ne` disables all discovered/configured extensions, including built-in MCP unless re-allowed with `-e builtin:mcp`. Isolation and tool availability must be designed together.
- **Replacement behaviour.** `mcp.md` says an installed extension that registers `/mcp` (e.g. `pi-mcp-adapter`) replaces built-in MCP, so native MCP needs such an extension to be absent. It was removed from this machine on 2026-10-29.
- **Direction (user-stated preference, now incorporated):** a plain SDK, project-owned Node worker with an explicit `ResourceLoader`, explicit `ModelRuntime`/auth paths, explicit tool set and project-owned session storage would give stricter control than a global `pi` CLI plus flags. Global-CLI flags are an acceptable interim hardening step; the SDK is optional, not needed for MCP.

## 6. Provider/auth compatibility

- **Durable takes a pi-ai `Models`** (README, SPEC §2.2); credentials come from a `CredentialStore` you inject (pi-ai README). The default store is in-memory. pi-ai says its API-key credential shape "use[s] the same discriminator as pi's `auth.json`".
- **`ModelRuntime` implements `Models`** (SRC `model-runtime.ts`: `export class ModelRuntime implements Models`, defaults to `DefaultAuthStorage` at `authPath`, reads `models.json`). **INFERENCE (type-level only):** a `ModelRuntime` could be passed as Durable's `models`, which would reuse Pi's existing `auth.json` and `models.json`. This pulls `pi-coding-agent` (TUI, resource code) into the worker and has **not** been verified at runtime.
- **Stored credential owns its provider**: environment variables are only consulted when nothing is stored, and a failed refresh never falls back silently to an env key (pi-ai README). Matters when mixing `auth.json` and env keys.
- **Providers named in docs:** ZAI Coding Plan (`ZAI_API_KEY`), "OpenAI Codex (legacy)" (OAuth), and "Sign in with ChatGPT" on the OpenAI provider. The panel's memory records models as `zai/glm-5.3-flash` and `openai-codex/gpt-6-luna`. Whether the `openai-codex` provider ID and `gpt-6-luna` still exist in the 1.4.0 catalog is **UNKNOWN**; blog/README samples use provider `openai` with `gpt-6*` IDs.
- **OAuth refresh** runs under a credential-store lock (pi-ai). Two processes sharing one `auth.json` (a Pi child plus a Durable worker) is a **UNKNOWN** to test.
- Plain Pi uses `auth.json`/`models.json` natively. No adaptation.

## 7. MCP

- **Durable: no built-in MCP.** SPEC §7.3 and README only mention "an MCP bridge" as something a tool *could* be (`api.executeTool`, `callers:["tools"]`, `deferred`, `tool_search`, codemode namespaces like `mcp__github__`). Durable has no MCP dependency.
- **`@earendil-works/pi-mcp`** is a standalone client (README): stdio + Streamable HTTP, protocol `2025-11-25` (accepts older), OAuth helper, `toLlmContent(result)` → pi-ai `TextContent`/`ImageContent`. It does not depend on pi packages. The shown wrapper targets `pi-agent-core`'s `AgentTool`, **not** Durable's `defineTool`, so **an adapter is required** (map MCP tool → `defineTool`, choose `replay`, map `isError`, map `structuredContent`, abort via signal).
- **Plain Pi:** MCP is built in for the CLI (`mcp.md`): `~/.pi/agent/mcp.json`, `.pi/mcp.json` (trust-gated), `pi mcp add`, exposure modes `codemode` (default) / `deferred` / `direct` / `hidden`. For SDK use, add `createMcpExtension()`. An installed extension that registers `/mcp` (e.g. `pi-mcp-adapter`) replaces the built-in support.
- `mcp.md` also states: "Tool calls are not retried because the server may already have performed them" (only list/read are). That is consistent with the no-replay requirement.
- The panel's dependency-free Python MCP server needs no change under either option; under Durable you would call it through `pi-mcp` (stdio) from a Node `defineTool`, or have the tool talk to the bridge directly.

## 8. Images and tool-result serialization

**Durable (README, SPEC §7.3, §8.4):**

- `ToolExecutionResult` has three channels: `output` (`ToolResultMessage["content"]`, so text and image blocks, for the model), `structuredOutput` (for programs calling the tool), `details` (for UIs). Only `output` and `details` go in the transcript. `structuredOutput` must be strict JSON.
- Images are stored inline in transcript entries (base64 `ImageContent`). A nested call's stored result keeps no `output`, so "an image ... is stored once". `read` returns an image as one block with limits from the model's `inputLimits.images.resize` (default 2000×2000 px / 4.5 MB base64); without an image processor it only passes PNG/JPEG/GIF/WebP within limits. A model without image input gets a placeholder (pi-ai).
- Default output limits: 50 KiB / 2000 lines, `retain:"head"`.
- Documents/slots reject non-finite numbers: a CHANGELOG fix mentions "Value contains a non-finite number". Nuke tools that return NaN/Infinity in `details` must sanitize. [INFERENCE for the Nuke case]

**Plain Pi:** prompt/steer accept `images: [{type:"image", data, mimeType}]` (`rpc-commands.md`); tool results are `{type:"text"|"image"}` blocks (`session-format.md`, `message-types.md`); MCP image blocks pass through.

**UNKNOWN for both:** storage growth and compaction behavior with many Nuke screenshots; whether the chosen provider/model accepts tool-result images.

## 9. Resume, compaction, session migrations

**Durable:**

- Resume: reopen same storage, `harness.resume()`. One process owns a storage; no cross-process locking (README, SPEC §12). `readOnly:true` viewers exist.
- Compaction: a task. Background summary starts `backgroundTokens` before the blocking threshold, placed at the next turn boundary; originals stay in storage; overflow triggers compact-and-retry once; summarization spend counts in `pi.usage`. A manual compact is `root.compact()`. A failed blocking compaction fails the generation with `model_error`. (README, SPEC §8.7, §6.)
- Migrations: document versions migrate on access (SPEC §3.6); tasks carry versions with `migrate`; a newer-version task leaves an older Harness *blocked* (`task_too_old`) rather than dropping it (SPEC §5.4). SQLite schema migrates at open (1.4.0 → v2, no rollback). `pi.live` v1→v3 migrated by `migrate`. Extension/registry code is not stored; after restart you must install the same extensions.
- Footguns relevant to upgrades (SPEC §12): changing a registered tool's replay declaration; "Environment on recovery" (a rerun tool builds its env with the *current* `cwd`); uninstalled extensions leave blocked tasks that keep a conversation busy until Stop orphans them.
- **No importer from Pi session JSONL** (v3 tree format, `session-format.md`) to Durable storage was found; SPEC §13 lists "compatibility layer for earlier harness prototypes" as a non-goal. Switching would start a new store.

**Plain Pi:** JSONL sessions, version 3 (v1/v2 auto-migrate on load); compaction entries with `firstKeptEntryId`; branching in-file; `--session-dir`, `--fork`, `--session-id` (`session-format.md`, `cli.md`). `agent_settled` marks end of automatic work (retries/compaction/queue can follow `agent_end`).

## 10. Plain Pi SDK/RPC as the lower-risk alternative

| Dimension | Plain Pi RPC (current) | Plain Pi SDK (in a project Node worker) | Pi Durable |
|---|---|---|---|
| Stability signal | Pi 1.0 shipped 2026-10-01 per blog; docs describe stable RPC/SDK | same | README: API "changes without notice" |
| Process boundary | Child process (QProcess + JSONL), matches current panel | In-process Node; panel still needs a Node child | Node child owned by the project; a new program to build/maintain |
| Isolation | Global-CLI flags + dedicated agent dir: interim hardening only; depends on the installed-version flag set (`-ne` also drops built-in MCP unless `-e builtin:mcp`) | `ResourceLoader` override: total, project-owned (example `12-full-control.ts`) | Total by construction (explicit registry) |
| Reuse of existing auth/models/MCP | native | native | adapter (`ModelRuntime` as `Models` unverified) + MCP adapter |
| Existing steering/fence logic | unchanged | needs port | needs port; semantics same |
| Crash replay of mutations | Never auto-replays (no durable tasks) | same | `unsafe` is the default, so nothing is rerun; the model is told "may have partially run". `safe` reruns are opt-in per tool |
| Durable queue / multi-client | no | no | yes |
| Migration cost | none | moderate | high: new storage, no session import, version churn |
| Durable state (restart-surviving transcript, queued inputs, task graph, document state, usage) | session JSONL only | session JSONL only (or your own `SessionManager`) | yes: atomic commits, resumable tasks, `readOnly` viewers, typed documents |

## 11. Unresolved acceptance checks (all require explicit approval to run)

Order roughly by risk.

1. **Pin and diff:** obtain the exact 1.4.0 tarball's README/types and compare with `main`. Record every signature the panel would use.
2. **Dispatch/crash test (private Nuke, fake mutation tool):** kill the worker after the bridge receives a mutation and before the result is committed. Expect: no re-dispatch, an `interrupted` result, bridge op count = 1. Also kill before the intent commit and confirm `beforeTool` hooks are idempotent.
3. **Reconciliation design:** bridge-side operation-id journal plus a read-only "what happened to op X" tool. Required under either framework; neither provides it.
4. **Abort during an in-flight bridge call:** does the signal reach the Python bridge, and what does the transcript say if the mutation still lands?
5. **Plain Pi orphan-tool-call behavior** after a crash with a dangling call (UNKNOWN today).
6. **Steer latency vs abort-then-submit** under both frameworks, on the user's actual models, preserving same session and completed work. Manual only, no timers.
7. **Isolation proof for plain Pi:** against the *installed* 1.4.0 `pi`, launch the panel's Pi child with a project-owned agent dir and the chosen flags (`-ne`, `-ns`, `-np`, `-nc`, `--no-themes`; `--no-mcp` only disables the built-in MCP extension), with each Nuke tool path supplied through an explicit `-e` allowlist or project-owned registration. Confirm no global extension/skill/prompt/context file/MCP (including the global `pi-mcp-adapter`) appears in the first system prompt or tool list, **and that the Nuke tools the panel needs are present**. Do not assume these flags apply to the OMP binary; its exact version is unknown.
8. **Auth sharing:** concurrent OAuth refresh with a Pi child and a Durable worker on one `auth.json` (or avoid by having one process own credentials).
9. **Provider catalog:** confirm provider/model IDs for `zai` and `openai-codex` (or `openai`) in the 1.4.0 catalog, and effort/thinking level mapping.
10. **Images:** Nuke screenshot tool results: stored size, compaction with image blocks, strict-JSON `details`, model image support.
11. **Upgrade path:** open a store written by 1.4.0 with the next release; confirm blocked-task behavior; accept that rollback is not possible.
12. **Node/SQLite availability:** which SQLite driver `openNodeSqliteStorage` uses and whether it works on the user's Node ≥ 22.19 (not read).
13. **Licenses and size** of the transitive dependency tree, and the ~23 MB RSS TypeBox cost in the worker.
14. **Ownership budget:** decide who maintains the TypeScript worker (build, tests, type checks) before any Durable prototype.
