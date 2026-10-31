# Runtime-grounded recovery for failed multi-step Nuke Python

Status: **historical design and verification record (2026-10-29), superseded in part by the 2026-10-30 Python-first cutover.** The preflight, structured failures and receiver-grounded runtime evidence described here remain; API-recovery gates, delivery tickets, mandatory documentation sequences and scoped `internal_python` rollback do not. See the [current runtime contract](../README.md#python-optional-actions-and-workflows). The historical verification ran 242 tests in 12 files in real Nuke 17.1v1 plus the stdio MCP shared-bridge smoke; its graph-checkpoint image was a stub fixture, not real screenshot proof, and no model turns ran. Those results describe that earlier implementation, not a rerun of the current code. Code is authoritative. Statements marked **[INFERENCE]** were not observed in a run.

Related: `RESEARCH-nuke-python-type-checking.md` (static checking, deferred), `RESEARCH-task-api-references.md`.

## 1. Problem solved

A model sends one multi-step `execute_python` script and something in it fails (syntax slip, wrong node class, wrong knob, bad enum label, missing native Roto member). Before this work:

* A syntax-class error could surface **after** part of the script ran (the last expression was compiled only after the prefix had executed; `yield`/`await` outside a function pass `ast.parse` but fail `compile()`).
* A failure had no structured location and no honest statement of what was unknown; `graph_changed: false` only meant the fingerprint was equal.
* The graph fingerprint does not cover the persisted Python namespace, files/renders/saves, callbacks, selection/Viewer state or the undo stack.
* The API gate could be cleared only by a search plus a read of a returned page, even where the docs omit or misdescribe native members (`_curveknob`, `_rotopaint`; Foundry's `nuke.rotopaint` page says to use `help('_rotopaint')`), and a failed (`isError`) result could never confirm a delivery token.

## 2. Hard rules (implemented)

1. No source re-execution, no expression re-evaluation, no re-calling the failed callable; evidence comes only from objects alive at the failure.
2. No automatic undo, retry, replay or script splitting. Partial effects are reported, never repaired. (Guided `internal_python` keeps its own scoped, verified rollback, reported as `rolled_back`.)
3. Neither route proves correctness. Route A validates a *sequence* (fresh-generation search, then a read of an entry id that search returned), **not** the semantic correctness or relevance of the page; reading relevant pages is model guidance, and the server cannot prove relevance. Route B is receiver/member-grounded facts from the running Nuke, not proof the next call is valid or the compositing is right.
4. No new public tool and no model-supplied waiver; evidence is collected inside an existing run, in the existing exception hook. Private sidecar-to-bridge handshake only.
5. Effects are never claimed fully observable. No new dependency; no static type checker.

## 3. Preflight

`execute_python` and `NativeActions.internal_python` compile **every** original code unit (`tools/script_run.py` `compile_script`) before any mutation, Undo group or namespace binding. The raw last-expression-as-`result` behaviour is kept. A syntax or compile error yields `failure.phase` `syntax`/`compile` with `executed: false` and nothing run (effects: graph unchanged because the code was only compiled). It is not an API error and does not arm the API checkpoint.

## 4. Response contract

Additive keys; the existing `success`, `error`, `traceback`, `api_errors`, `graph_changed`, `graph_change_detection`, `added_nodes`, `removed_nodes`, `modified_nodes`, `node_errors` keep their meaning and serve as the effect record. Everything is bounded by count and length caps (no timer).

### 4.1 `failure` (on failure)

```
failure: {
  phase:          "syntax" | "compile" | "setup" | "runtime",
  executed:       bool,                 // false for syntax/compile
  exception_type: str, message: str,    // clipped
  location:       {function, line, column?, source},   // innermost user-code frame
  frames:         [...],                // user-code frames, bounded; frames_omitted when cut
  effects:        {graph: <pointer to the graph-delta fields; nothing undone/retried/replayed>,
                   unknown: [...],      // not observed: namespace bindings, files/renders, callbacks, selection/Viewer, undo stack...
                   undo?: str},
  limitations?:   [str]                 // e.g. location unreadable
}
```

`location`/`frames` say where it stopped, not that earlier statements fully succeeded. `graph_changed: false` means the fingerprint did not change, not that nothing happened.

### 4.2 `api_errors[i].runtime_evidence` (bounded, read-only, failure-time)

Collected in `tools/api_errors.py` where the record is settled, inside the existing hook while the receiver is alive. Failures become `limitations`, never exceptions in user code (counted in `api_error_tracking_failures`).

```
runtime_evidence: {
  source: "running_nuke",
  available: bool, sufficient: bool,
  limitations: [str],          // read-only note, unknowns, truncation, "no signature or docstring", ...
  receiver?: {class, module, kind: "module"|"class"|"instance"},
  member?: str,                // the failing member
  members?: [...], members_total?,     // public dir() names (missing-attribute failures)
  controls?: [...], controls_total?,   // knob names/choices (Node/knob receivers)
  callable?: {name, signature?, doc?}  // read without calling
}
```

`sufficient` is true only with a receiver, a member, and at least one readable fact (`members`, `controls`, callable `signature` or `doc`). Opaque native receivers or absent classes stay `available: false` or insufficient; unknowns are stated explicitly. A docstring is text from the binary, not proof of correct usage. `nuke.nodeTypes()`-style class suggestions are not evidence. Permitted reads: `dir()`, `inspect.getattr_static`, `inspect.signature`/`__doc__` (no call), `Node.knobs()`, `Enumeration_Knob.values()`, only on accepted API objects. No `knob.value()`, no sampling/bbox/format/metadata/render, no setters, no `getattr` on non-API objects, no `help()`.

### 4.3 Parity

`internal_python` reuses the same preflight, failure and evidence builders; its own scoped rollback stays separate.

## 5. Gate: SDK documentation OR confirmed runtime evidence

After a run reports `api_errors`, `ApiRecoveryGate.arm(client_id, api_errors, omitted=, tracking_failures=)` starts a per-client generation (new generation voids all older evidence) and records whether runtime evidence is eligible. `execute_python` is refused (`api_documentation_required`) and `internal_python` cannot bypass the checkpoint, until `missing()` is empty by either:

* **A (SDK):** a confirmed non-empty `search_nuke_api_docs` after the error, then a confirmed `read_nuke_api_doc` of an id from it. An empty search is a reported reference limitation; the refusal never asks to repeat the same query.
* **B (runtime):** substantive `runtime_evidence` for **every** original `api_errors` record (validated on all records, not the 5-record `bounded_records` preview), with no `api_errors_omitted` and no `api_error_tracking_failures`, **and** delivery confirmed:
  * the bridge result carries a private one-time, client/generation-bound `api_runtime_evidence_token` (`ApiRecoveryGate.runtime_ticket`);
  * the sidecar strips it (the model never sees it), assembles the response, then confirms via `confirm_api_docs` kind `runtime` **even when the result is `isError`**, and reserializes the updated `api_documentation`;
  * failed confirmation stays blocked; stale, repeated, foreign or unconfirmed tokens never count; the result's `sufficient` flag is a hint the gate revalidates.

`status()` reports `required`, `generation`, `satisfied`, `missing`, `runtime_evidence {eligible, delivered, reason?}` and, once cleared, `cleared_by` with a note that runtime evidence satisfied the checkpoint only. The graph-inspection checkpoint, trust and leases are independent: clearing the API gate satisfies none of them, and `nuke_action` inspect (only where the profile offers it) or `get_nuke_context` may clarify the graph but never clear the API checkpoint. `API_RTFM_REMINDER` lives in both `bridge/api_recovery.py` and `mcp_server/server.py` (the sidecar must not import the Qt package). The tool description and refusal text name both routes.

## 6. Manual steering, crash and cancellation caveats

* `execute_python` runs on Nuke's GUI thread to completion. A manual intervention cannot cancel an executing operation; it only prevents later requests (`control_paused`, `control_stale`, `control_retired`). A dispatched script finishes even if the sidecar times out (300 s) or the harness dies, and its result may never be delivered.
* Consequences: no replay; the generation is armed but the evidence token is never confirmed, so route B stays closed and route A remains; `graph_changed` is unknown to the model and the inspection gate closes until re-inspection; the model re-plans from the live graph, not memory. Retirement drops per-client generation/evidence state.
* A hard Nuke crash loses in-process state; not mitigated here.

## 7. Decisions and risks

* **Route B open even when docs exist.** Risk: a model can clear the gate without reading helpful docs; mitigated by requiring every record substantive and keeping route A.
* **Static advisory deferred.** No 17.1 stubs verified; runtime facts cover the observed failures.
* **Cost.** `Node.knobs()` and `Enumeration_Knob.values()` are the only Nuke method calls in the hook; output is capped, call cost on very large nodes is not **[INFERENCE]**.
* **Residual blocked limitation (fail closed).** If runtime evidence is insufficient (unknown receiver/class factory, omitted errors, tracking failure) and documentation is absent, empty or irrelevant, the gate stays closed. The refusal states the limitation, suggests no waiver or new tool, and does not loop on the same query.
* **Staleness.** Evidence describes failure-time state; later lines may change the receiver.
* **`dir()` completeness.** Native members may be undocumented or unstable across 17.x.

## 8. Open items

* Whether `inspect.signature`/`__doc__` yield anything for 17.1's native Roto and `_nuke` callables (assumed often empty; handled by `limitations`).
* Whether `dir()` output is useful on every native Roto type.
* Route B proof exists for a node/knob failure (Blur bad knob) in the shared-bridge smoke; other native receivers are covered only by unit-level cases. Static advisory and statement-index reporting were not built.
