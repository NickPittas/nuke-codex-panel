// Owned, trusted Nuke runtime extension for the private Pi installation.
//
// 1. `/nuke_runtime` (read-only diagnostics). It makes no model/provider turn and calls no Nuke
//    API. It appends one non-LLM custom session entry (type "nuke-runtime-diagnostics") holding the
//    snapshot and shows only a short notification. The panel reads the entry through RPC
//    `get_entries`. Auth values, bridge tokens and credential-like settings are never emitted.
//    It also performs one authenticated, loopback-only round trip to the pinned bridge (see
//    probeBridge) so the entry reports live bridge/lease state, not just that a file exists.
// 2. `tool_call` surface guard: a call to a tool outside this session's launch allowlist is blocked
//    with an explicit reason. Ordinary and nested (codemode `parentToolCallId`) calls are treated
//    identically. Input is never mutated and nothing is executed on the extension's behalf.
// 3. Nuke MCP result delivery: results keep their content/details/structuredContent/isError. The
//    extension only (a) restores the full error text the MCP adapter shortened, from the complete
//    CallToolResult it keeps in `structuredContent`, and (b) for a script (codemode) parent, appends
//    what its nested Nuke calls produced that the script did not show: failed results, caught Nuke
//    API errors in successful results, calls that never reached a result (validation/blocked), nested
//    calls still unresolved when the script returned, and nested images. Nothing is capped or sampled;
//    evidence lives only while its model-issued call is in flight. The parent's own isError is never
//    changed, nothing is replayed or undone, and the bridge stays the sole authority on
//    syntax/API/graph/trust/leases/Undo.
//    Guard boundary: the tool_call guard sees calls routed through Pi's tool pipeline. It is not an OS
//    sandbox and does not intercept helper APIs a codemode script may reach inside its own runtime.
//
// Provenance: `measured` comes from live Pi APIs / process state in this process.
// `argv` is only what the launcher asked for and does not prove that anything loaded.
import { createHash, randomBytes } from "node:crypto";
import { existsSync, readFileSync, readlinkSync, statSync } from "node:fs";
import { connect } from "node:net";
import { basename, dirname, join } from "node:path";
import type {
	ExtensionAPI,
	ToolExecutionEndEvent,
	ToolExecutionStartEvent,
	ToolResultEvent,
	ToolResultEventResult,
} from "@earendil-works/pi-coding-agent";
const ENTRY_TYPE = "nuke-runtime-diagnostics";
const SCHEMA = 1;
const SECRET_FLAG = /^--?(api-?key|token|password|secret|auth\w*)$/i;
const BUILTIN_CODE_TOOLS = new Set(["read", "bash", "powershell", "edit", "write", "grep", "find", "ls"]);
// Settings are never dumped: only these non-secret fields are recorded, and only as booleans,
// numbers or short plain strings (never URLs, so proxy user:password cannot be persisted).
const SETTINGS_ALLOWLIST = [
	"defaultProvider",
	"defaultModel",
	"defaultThinkingLevel",
	"defaultTools",
	"enableInstallTelemetry",
	"enableSkillCommands",
	"quietStartup",
	"offline",
	"telemetry",
] as const;

function safeSettings(settings: unknown): Record<string, unknown> {
	const out: Record<string, unknown> = {};
	if (settings === null || typeof settings !== "object") return out;
	const source = settings as Record<string, unknown>;
	const plain = (v: unknown): boolean =>
		typeof v === "boolean" || typeof v === "number" || (typeof v === "string" && v.length <= 200 && !/:\/\/|@/.test(v));
	for (const key of SETTINGS_ALLOWLIST) {
		const v = source[key];
		if (plain(v)) out[key] = v;
		else if (Array.isArray(v) && v.every(plain)) out[key] = v;
	}
	return out;
}
// Non-secret Pi controls whose values are paths/flags; values of any other env var are never read.
const PI_ENV_VALUES = new Set([
	"PI_CODING_AGENT_DIR",
	"PI_CODING_AGENT_SESSION_DIR",
	"PI_SKIP_VERSION_CHECK",
	"PI_OFFLINE",
	"PI_TELEMETRY",
	"PI_CODING_AGENT",
	"JITI_FS_CACHE",
	"NUKE_CODEX_BRIDGE_FILE",
]);

function redactArgv(argv: readonly string[]): string[] {
	const out: string[] = [];
	let hide = false;
	for (const arg of argv) {
		if (hide) {
			out.push("[redacted]");
			hide = false;
			continue;
		}
		const eq = arg.indexOf("=");
		if (arg.startsWith("-") && eq > 0 && SECRET_FLAG.test(arg.slice(0, eq))) {
			out.push(`${arg.slice(0, eq)}=[redacted]`);
			continue;
		}
		if (SECRET_FLAG.test(arg)) hide = true;
		out.push(arg);
	}
	return out;
}

function argvFlagValues(argv: readonly string[], names: readonly string[]): string[] {
	const values: string[] = [];
	for (let i = 0; i < argv.length; i++) {
		if (names.includes(argv[i]) && i + 1 < argv.length) values.push(argv[i + 1]);
	}
	return values;
}

function argvPresent(argv: readonly string[], names: readonly string[]): string[] {
	return names.filter((n) => argv.includes(n));
}

function uniqueSorted(items: Iterable<string>): string[] {
	return [...new Set(items)].sort();
}

function readPackageVersion(dir: string | undefined): { version?: string; packageJson?: string } {
	// Walk up from the diagnostics extension to the private install's node_modules.
	for (let cur = dir; cur; ) {
		const candidate = join(cur, "node_modules", "@earendil-works", "pi-coding-agent", "package.json");
		if (existsSync(candidate)) {
			try {
				const parsed = JSON.parse(readFileSync(candidate, "utf8")) as { version?: string };
				return { version: parsed.version, packageJson: candidate };
			} catch {
				return { packageJson: candidate };
			}
		}
		const parent = dirname(cur);
		if (parent === cur) break;
		cur = parent;
	}
	return {};
}

// ---- structural tool-surface guard ---------------------------------------------------------------

// Used only when the launcher passed no `--tools`; mirrors harnesses/pi_rpc.py `_PI_TOOLS`.
const DEFAULT_TOOL_PATTERNS = ["codemode", "tool_search", "mcp__nuke__*"];
const NUKE_TOOL_PREFIX = "mcp__nuke__";

function argvListValues(argv: readonly string[], flag: string): string[] {
	const out: string[] = [];
	for (let i = 0; i < argv.length; i++) {
		const arg = argv[i];
		let value: string | undefined;
		if (arg === flag) value = argv[i + 1];
		else if (arg.startsWith(`${flag}=`)) value = arg.slice(flag.length + 1);
		if (value !== undefined) out.push(...value.split(",").map((s) => s.trim()).filter(Boolean));
	}
	return out;
}

function matchesPattern(name: string, pattern: string): boolean {
	return pattern.endsWith("*") ? name.startsWith(pattern.slice(0, -1)) : name === pattern;
}

interface ToolSurface {
	allowed: string[];
	excluded: string[];
	source: "argv" | "default";
}

// The surface is what the launcher advertised (`--tools` / `--exclude-tools`), read once at load.
function toolSurface(argv: readonly string[]): ToolSurface {
	const allowed = argvListValues(argv, "--tools");
	return {
		allowed: allowed.length > 0 ? uniqueSorted(allowed) : [...DEFAULT_TOOL_PATTERNS],
		excluded: uniqueSorted(argvListValues(argv, "--exclude-tools")),
		source: allowed.length > 0 ? "argv" : "default",
	};
}

function surfaceViolation(surface: ToolSurface, name: string, parentToolCallId: string | undefined): string | undefined {
	const excluded = surface.excluded.some((p) => matchesPattern(name, p));
	if (!excluded && surface.allowed.some((p) => matchesPattern(name, p))) return undefined;
	const via = parentToolCallId === undefined ? "" : ` (requested by a script through parent call ${parentToolCallId})`;
	return (
		`Blocked by the Nuke runtime extension: tool "${name}"${via} is not part of this session's tool surface ` +
		`(allowed: ${surface.allowed.join(", ")}). Nothing was executed. Reach Nuke only through codemode ` +
		`(searchTools()/describeTool(), then call the mcp__nuke__ tools) or tool_search.`
	);
}

// ---- structured helpers ----------------------------------------------------------------------------

interface TextBlock {
	type: "text";
	text: string;
}
interface ImageBlock {
	type: "image";
	data: string;
	mimeType: string;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
	return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;
}

function isText(block: unknown): block is TextBlock {
	const r = asRecord(block);
	return r !== undefined && r.type === "text" && typeof r.text === "string";
}

// MCP image blocks and Pi ImageContent share `{ type: "image", data, mimeType }`.
function isImage(block: unknown): block is ImageBlock {
	const r = asRecord(block);
	return r !== undefined && r.type === "image" && typeof r.data === "string" && typeof r.mimeType === "string";
}

function textOf(content: readonly unknown[]): string {
	return content.filter(isText).map((b) => b.text).join("\n");
}

function imageHash(block: ImageBlock): string {
	return createHash("sha256").update(block.mimeType).update("\0").update(block.data).digest("hex");
}

function errorText(error: unknown): string {
	return error instanceof Error ? error.message : String(error);
}

// ---- nested/ordinary result delivery ---------------------------------------------------------------

// Pi's MCP adapter cuts model-facing text in the middle above 20 KB and saves the rest to a file the
// model cannot read (no host read tool). The complete result rides in `structuredContent`; nothing
// here is capped, sampled or deduplicated across calls. Per-call evidence holds references to the SDK's
// own strings (images are never copied or re-encoded) and exists only until its parent's result is built.

interface Evidence {
	callId: string;
	tool: string;
	isError: boolean;
	text: string;
	// False when only the adapter's already-shortened text was available.
	complete: boolean;
}
interface NestedBlock {
	callId: string;
	tool: string;
	reason: string;
}
interface ParentState {
	nukeCalls: number;
	evidence: Evidence[];
	blocked: NestedBlock[];
	// Nested Nuke calls started and not yet ended: callId -> tool name.
	pending: Map<string, string>;
	// Nested Nuke calls whose MCP request was aborted: callId -> tool name.
	aborted: Map<string, string>;
	// Images of this parent's nested calls, by content hash (duplicates inside one parent collapse).
	images: Map<string, ImageBlock>;
	// Failures of this extension's own handlers while recording for this parent.
	internalFailures: string[];
}
interface ResultView {
	content: readonly unknown[];
	structuredContent?: unknown;
	details?: unknown;
}

// The MCP blocks Pi's adapter keeps in `structuredContent` (the original CallToolResult.content).
function structuredBlocks(structuredContent: unknown): (TextBlock | ImageBlock)[] | undefined {
	const sc = asRecord(structuredContent);
	const blocks = sc !== undefined && Array.isArray(sc.content) ? (sc.content as unknown[]) : undefined;
	if (blocks !== undefined && blocks.length > 0 && blocks.every((b) => isText(b) || isImage(b))) {
		return blocks as (TextBlock | ImageBlock)[];
	}
	return undefined;
}

// Pi's MCP client turns a cancelled request (the script returned or was stopped while it ran) into an
// `McpAbortError` whose default message is exactly this; the SDK then reports it as a plain error result
// with no `structuredContent` (no CallToolResult ever arrived). "Operation aborted" (call never started)
// is deliberately not matched: nothing was sent to the bridge then.
const MCP_ABORT_TEXT = "MCP request aborted";

// Full text of a Nuke MCP result.
function evidenceText(view: ResultView): { text: string; complete: boolean } {
	const blocks = structuredBlocks(view.structuredContent);
	if (blocks !== undefined) return { text: textOf(blocks), complete: true };
	return { text: textOf(view.content), complete: typeof asRecord(view.details)?.fullOutputPath !== "string" };
}

// A successful Nuke result that still reports Nuke API errors the script caught. Parsed from the ORIGINAL
// first MCP text block (the bridge result as JSON), never from the SDK's flattened text, which can be cut
// in the middle.
function reportsCaughtApiErrors(structuredContent: unknown): boolean {
	const first = structuredBlocks(structuredContent)?.find(isText);
	if (first === undefined) return false;
	try {
		const result = asRecord(JSON.parse(first.text));
		if (result === undefined) return false;
		return Array.isArray(result.api_errors) && result.api_errors.length > 0;
	} catch {
		return false;
	}
}

// Distinct images of a result by content hash. Pi's own (already normalized) content wins; MCP image
// blocks kept in structuredContent are used only when the content carries none, so one capture is never
// attached twice in two encodings. Data strings are shared, not copied.
function resultImages(view: ResultView): Map<string, ImageBlock> {
	const out = new Map<string, ImageBlock>();
	const collect = (blocks: readonly unknown[]): void => {
		for (const block of blocks) {
			if (!isImage(block)) continue;
			const hash = imageHash(block);
			if (!out.has(hash)) out.set(hash, { type: "image", data: block.data, mimeType: block.mimeType });
		}
	};
	collect(view.content);
	if (out.size === 0) collect(structuredBlocks(view.structuredContent) ?? []);
	return out;
}


// ---- live bridge probe ---------------------------------------------------------------------------------

const BRIDGE_PIN_ENV = "NUKE_CODEX_BRIDGE_FILE";
const BRIDGE_TIMEOUT_MS = 5000;
const BRIDGE_REPLY_MAX = 65536;
// bridge/control.py refusal codes: the control lease of this Pi process is not usable.
const CONTROL_REFUSALS = ["control_paused", "control_stale", "control_mismatch", "control_closed", "control_retired"];
const ACTIVE_OPERATIONS_NOTE =
	"not available: the bridge wire protocol does not expose active operations (control status is in-process in Nuke)";

function clean(text: string, token: string): string {
	const redacted = token ? text.split(token).join("[redacted]") : text;
	return redacted.length > 300 ? `${redacted.slice(0, 300)}...` : redacted;
}

type Exchange = { ok: true; line: string } | { ok: false; state: string; error: string };

// One JSONL request/response on the loopback bridge. Never throws.
function bridgeExchange(port: number, request: string): Promise<Exchange> {
	const { promise, resolve } = Promise.withResolvers<Exchange>();
	let settled = false;
	let buffer = "";
	const socket = connect({ host: "127.0.0.1", port });
	const timer = setTimeout(
		() =>
			done({
				ok: false,
				state: "timeout",
				error: `no reply within ${BRIDGE_TIMEOUT_MS} ms: the bridge is busy (running operation or approval dialog) or not responding`,
			}),
		BRIDGE_TIMEOUT_MS,
	);
	function done(result: Exchange): void {
		if (settled) return;
		settled = true;
		clearTimeout(timer);
		socket.destroy();
		resolve(result);
	}
	socket.setEncoding("utf8");
	socket.on("connect", () => socket.write(`${request}\n`));
	socket.on("data", (chunk: string) => {
		buffer += chunk;
		const end = buffer.indexOf("\n");
		if (end >= 0) done({ ok: true, line: buffer.slice(0, end) });
		else if (buffer.length > BRIDGE_REPLY_MAX) done({ ok: false, state: "bad-response", error: "reply exceeded the size limit" });
	});
	socket.on("error", (error: Error) => done({ ok: false, state: "connect-failed", error: errorText(error) }));
	socket.on("close", () => done({ ok: false, state: "bad-response", error: "connection closed without a reply" }));
	return promise;
}

// Live, read-only state of the ONE bridge pinned by NUKE_CODEX_BRIDGE_FILE (no discovery, no global
// config). The request is `confirm_delivery` with an empty token list: authenticated and admitted by the
// bridge's execution control exactly like a sidecar request. The bridge's admission/client bookkeeping and
// operation events see it, but it touches no graph, checkpoint, trust or Undo state and cannot satisfy or
// alter any checkpoint. `clientId` is this Pi process's single diagnostic identity. When this Pi process
// has a control id/epoch it is sent, so a successful reply proves this process still holds its control
// lease; a refusal names the code. The descriptor's auth token never leaves this function.
async function probeBridge(clientId: string): Promise<Record<string, unknown>> {
	const base = { probedAt: new Date().toISOString(), activeOperations: null, activeOperationsNote: ACTIVE_OPERATIONS_NOTE };
	let token = "";
	const fail = (state: string, error: string, extra: Record<string, unknown> = {}): Record<string, unknown> => ({
		...base,
		reachable: false,
		authenticated: false,
		state,
		error: clean(error, token),
		...extra,
	});

	const pin = process.env[BRIDGE_PIN_ENV];
	if (!pin) return fail("no-pin", `${BRIDGE_PIN_ENV} is not set; no bridge is pinned and none is discovered`);

	let raw: string;
	try {
		const st = statSync(pin);
		if (!st.isFile()) return fail("descriptor-unreadable", "the pinned path is not a regular file");
		if (process.platform !== "win32") {
			// POSIX only: Windows reports synthetic ownership/mode bits; there the Python side validated
			// the descriptor directory's private ACL when it wrote the file.
			if (typeof process.getuid === "function" && st.uid !== process.getuid()) {
				return fail("descriptor-unsafe", "the descriptor is not owned by this user; not used");
			}
			if ((st.mode & 0o077) !== 0) return fail("descriptor-unsafe", "the descriptor is accessible by group/others; not used");
		}
		if (st.size > 4096) return fail("descriptor-invalid", "the descriptor is unexpectedly large; not used");
		raw = readFileSync(pin, "utf8");
	} catch (error) {
		return fail("descriptor-unreadable", `the pinned descriptor cannot be read: ${errorText(error)}`);
	}
	let record: Record<string, unknown> | undefined;
	try {
		record = asRecord(JSON.parse(raw));
	} catch {
		// The parser message can quote file content (the token); say nothing about it.
		return fail("descriptor-invalid", "the pinned descriptor is not valid JSON");
	}
	const pid = record?.pid;
	const port = record?.port;
	if (
		record === undefined ||
		typeof record.token !== "string" ||
		record.token === "" ||
		typeof pid !== "number" ||
		!Number.isInteger(pid) ||
		pid <= 0 ||
		typeof port !== "number" ||
		!Number.isInteger(port) ||
		port < 1 ||
		port > 65535 ||
		record.host !== "127.0.0.1"
	) {
		return fail("descriptor-invalid", "the pinned descriptor lacks a valid pid, loopback host 127.0.0.1, port and token");
	}
	token = record.token;
	const descriptor = { pid, host: "127.0.0.1", port };

	let liveness: { alive: boolean | null; signalCheck: string } = { alive: true, signalCheck: "ok" };
	try {
		process.kill(pid, 0);
	} catch (error) {
		const code = (error as NodeJS.ErrnoException).code;
		if (code === "ESRCH") {
			return fail("process-gone", `the Nuke process ${pid} named by the descriptor is not running (stale descriptor)`, { descriptor });
		}
		// EPERM (exists, not signalable by this user) or anything else: liveness is unknown from here.
		liveness = { alive: null, signalCheck: code ?? errorText(error) };
	}
	// The executable name is only observable through Linux /proc; elsewhere it is reported as unavailable
	// (never inferred). The authenticated loopback reply below is the real proof of the bridge process.
	let exe: string | null = null;
	let exeVerification: string | undefined;
	if (process.platform === "linux") {
		try {
			exe = basename(readlinkSync(`/proc/${pid}/exe`));
		} catch {
			exe = null;
		}
	} else {
		exeVerification = `unavailable on ${process.platform} (Linux /proc only); liveness is process.kill(pid,0) + the authenticated loopback reply`;
	}

	const controlId = (process.env.NUKE_CODEX_CONTROL_ID ?? "").trim().slice(0, 64);
	const epochText = process.env.NUKE_CODEX_CONTROL_EPOCH ?? "";
	const epoch = /^\d+$/.test(epochText) ? Number.parseInt(epochText, 10) : undefined;
	const request: Record<string, unknown> = {
		token,
		client_id: clientId,
		method: "confirm_delivery",
		params: { tokens: [] },
	};
	if (controlId) {
		request.control_id = controlId;
		if (epoch !== undefined) request.control_epoch = epoch;
	}
	const lease: Record<string, unknown> = { scoped: controlId !== "", controlId: controlId || null, epoch: epoch ?? null };
	const started = Date.now();
	const exchange = await bridgeExchange(port, JSON.stringify(request));
	const common = {
		descriptor,
		process: { pid, ...liveness, exe, ...(exeVerification ? { exeVerification } : {}) },
		lease,
		roundTripMs: Date.now() - started,
	};
	if (!exchange.ok) return fail(exchange.state, exchange.error, common);

	let reply: Record<string, unknown> | undefined;
	try {
		reply = asRecord(JSON.parse(exchange.line));
	} catch {
		return fail("bad-response", "the bridge reply was not JSON", common);
	}
	if (reply === undefined) return fail("bad-response", "the bridge reply was not an object", common);
	const code = reply.error_code;
	if (reply.success === true && Array.isArray(reply.recorded)) {
		return {
			...base,
			...common,
			reachable: true,
			authenticated: true,
			state: "ok",
			graphRevision: Number.isInteger(reply.graph_revision) ? reply.graph_revision : null,
			lease: { ...lease, admitted: true, code: null },
		};
	}
	if (reply.success === false && typeof code === "string" && CONTROL_REFUSALS.includes(code)) {
		return {
			...base,
			...common,
			reachable: true,
			authenticated: true,
			state: "lease-refused",
			lease: { ...lease, admitted: false, code },
		};
	}
	if (reply.success === false && reply.error === "Unauthorized Nuke bridge request") {
		return { ...base, ...common, reachable: true, authenticated: false, state: "unauthorized", error: "the bridge rejected the descriptor's token (stale or foreign descriptor)" };
	}
	return fail("bad-response", `unrecognized bridge reply: ${typeof reply.error === "string" ? reply.error : "no error text"}`, common);
}

export default function nukeRuntime(pi: ExtensionAPI): void {
	const surface = toolSurface(process.argv);
	// One diagnostic bridge client identity for this Pi process, reused by every /nuke_runtime probe.
	const diagClientId = `nuke-runtime-diag-${randomBytes(6).toString("hex")}`;
	// Transient per-script state. `live` holds the ids of model-issued calls still running; `parents`
	// holds what their nested Nuke calls left behind. Both are cleared when the parent's result is
	// built and on every terminal lifecycle event (turn/agent end, abort, error, shutdown).
	const live = new Set<string>();
	const parents = new Map<string, ParentState>();
	const stats = {
		blockedCalls: 0,
		blockedNestedCalls: 0,
		lastBlockedTool: null as string | null,
		restoredErrorResults: 0,
		scriptResultsAugmented: 0,
		nestedEvidenceForwarded: 0,
		nestedImagesForwarded: 0,
		unresolvedNestedCallsReported: 0,
		handlerErrors: 0,
		lastHandlerError: null as string | null,
	};

	const clearTransient = (): void => {
		live.clear();
		parents.clear();
	};
	// The running model-issued call that `parentToolCallId` (possibly itself nested: `<id>/<n>`) belongs to.
	const rootOf = (parentToolCallId: string): string | undefined => {
		let best: string | undefined;
		for (const id of live) {
			if ((parentToolCallId === id || parentToolCallId.startsWith(`${id}/`)) && (best === undefined || id.length > best.length)) best = id;
		}
		return best;
	};
	const stateFor = (root: string): ParentState => {
		let state = parents.get(root);
		if (state === undefined) {
			state = { nukeCalls: 0, evidence: [], blocked: [], pending: new Map(), aborted: new Map(), images: new Map(), internalFailures: [] };
			parents.set(root, state);
		}
		return state;
	};
	const noteHandlerError = (error: unknown, root: string | undefined): void => {
		const message = errorText(error).slice(0, 200);
		stats.handlerErrors++;
		stats.lastHandlerError = message;
		if (root !== undefined) parents.get(root)?.internalFailures.push(message);
	};

	// A nested call finished (any way: result hook, blocked, validation/preparation failure, abort).
	// `tool_execution_end` is the one event every nested call reaches, with the final result.
	const recordNestedEnd = (event: ToolExecutionEndEvent, root: string): void => {
		const state = stateFor(root);
		state.pending.delete(event.toolCallId);
		if (!event.toolName.startsWith(NUKE_TOOL_PREFIX)) return;
		if (state.blocked.some((b) => b.callId === event.toolCallId)) return;
		state.nukeCalls++;
		const result = asRecord(event.result) ?? {};
		const view: ResultView = {
			content: Array.isArray(result.content) ? (result.content as unknown[]) : [],
			structuredContent: result.structuredContent,
			details: result.details,
		};
		if (event.isError || reportsCaughtApiErrors(view.structuredContent)) {
			const { text, complete } = evidenceText(view);
			state.evidence.push({ callId: event.toolCallId, tool: event.toolName, isError: event.isError, text, complete });
		}
		if (event.isError && result.structuredContent === undefined && textOf(view.content).trim() === MCP_ABORT_TEXT) {
			state.aborted.set(event.toolCallId, event.toolName);
		}
		for (const [hash, image] of resultImages(view)) {
			if (!state.images.has(hash)) state.images.set(hash, image);
		}
	};

	// A script's own result: add what its nested Nuke calls produced but the script did not show.
	const deliverToParent = (state: ParentState, event: ToolResultEvent): ToolResultEventResult | undefined => {
		const parentText = textOf(event.content);
		const shown = new Set<string>();
		for (const block of event.content) if (isImage(block)) shown.add(imageHash(block));
		const lines: string[] = [];
		let evidenceListed = 0;
		for (const e of state.evidence) {
			if (e.text !== "" && parentText.includes(e.text)) continue;
			const what = e.isError
				? "returned isError=true"
				: "succeeded (isError=false) but reported caught Nuke API errors or owed API documentation";
			const note = e.complete ? "" : " (only the MCP adapter's shortened text was available)";
			lines.push(`- ${e.tool} (${e.callId}) ${what}${note}:\n${e.text === "" ? "(no text)" : e.text}`);
			evidenceListed++;
		}
		for (const b of state.blocked) {
			if (!parentText.includes(b.reason)) lines.push(`- ${b.tool} (${b.callId}) was blocked before it ran: ${b.reason}`);
		}
		for (const [callId, tool] of state.pending) {
			lines.push(
				`- ${tool} (${callId}) had not finished when this script returned or was stopped. Its bridge operation MAY still have executed or MAY still be running; ` +
					`nothing was cancelled, retried or rolled back. Inspect fresh Nuke state before retrying or repeating it.`,
			);
		}
		for (const [callId, tool] of state.aborted) {
			lines.push(
				`- ${tool} (${callId}) was aborted on the MCP request (its result above is only the abort notice, not a bridge outcome). Its bridge operation MAY still have executed or MAY still be running; ` +
					`nothing was cancelled, retried or rolled back. Inspect fresh Nuke state before retrying or repeating it.`,
			);
		}
		for (const message of state.internalFailures) {
			lines.push(`- The runtime extension failed while recording nested Nuke results for this script (${message}); some evidence may be missing.`);
		}
		// Only this parent's own images: never suppressed because an earlier call carried the same capture.
		const attach: ImageBlock[] = [];
		for (const [hash, image] of state.images) if (!shown.has(hash)) attach.push(image);
		if (attach.length > 0) {
			lines.push(`- ${attach.length} image(s) returned by nested Nuke calls that the script did not show are attached below.`);
		}
		if (lines.length === 0) return undefined;
		stats.scriptResultsAugmented++;
		stats.nestedEvidenceForwarded += evidenceListed;
		stats.nestedImagesForwarded += attach.length;
		stats.unresolvedNestedCallsReported += state.aborted.size;
		stats.unresolvedNestedCallsReported += state.pending.size;
		const header =
			`[nuke_runtime] Nested Nuke call results recorded by the runtime for this script (${state.nukeCalls} Nuke call(s) finished). ` +
			`Nothing was replayed or undone; a later step of the script may already have repaired a failure, so inspect fresh state before relying on it.`;
		const text: TextBlock = { type: "text", text: `${header}\n${lines.join("\n")}` };
		return { content: [...event.content, text, ...attach], structuredContent: event.structuredContent };
	};

	// An ordinary Nuke result: Pi already keeps content/details/structuredContent/isError. The only change is
	// to give back error text its MCP adapter shortened (the full CallToolResult rides in structuredContent),
	// whatever its size and whether or not the adapter could save the rest to a file.
	const restoreFullError = (event: ToolResultEvent): ToolResultEventResult | undefined => {
		if (!event.isError) return undefined;
		const blocks = structuredBlocks(event.structuredContent);
		if (blocks === undefined) return undefined;
		const text = textOf(blocks);
		if (text === "" || text === textOf(event.content)) return undefined;
		stats.restoredErrorResults++;
		const images = [...resultImages(event).values()];
		return { content: [{ type: "text", text }, ...images], structuredContent: event.structuredContent };
	};

	pi.on("tool_call", (event) => {
		const parentId = event.parentToolCallId;
		const reason = surfaceViolation(surface, event.toolName, parentId);
		if (reason === undefined) {
			if (parentId === undefined) live.add(event.toolCallId);
			return undefined;
		}
		stats.blockedCalls++;
		stats.lastBlockedTool = event.toolName;
		if (parentId !== undefined) {
			stats.blockedNestedCalls++;
			const root = rootOf(parentId);
			if (root !== undefined) stateFor(root).blocked.push({ callId: event.toolCallId, tool: event.toolName, reason });
		}
		return { block: true, reason };
	});

	// Nested Nuke calls are tracked from their start so a script that returns (or is stopped) while one is
	// still running can be told so. The start event precedes validation and the tool_call hook.
	pi.on("tool_execution_start", (event: ToolExecutionStartEvent) => {
		if (event.parentToolCallId === undefined || !event.toolName.startsWith(NUKE_TOOL_PREFIX)) return;
		const root = rootOf(event.parentToolCallId);
		try {
			if (root !== undefined) stateFor(root).pending.set(event.toolCallId, event.toolName);
		} catch (error) {
			noteHandlerError(error, root);
		}
	});

	pi.on("tool_result", (event) => {
		// Nested results reach their script untouched; `tool_execution_end` records what the parent needs.
		if (event.parentToolCallId !== undefined) return undefined;
		const state = parents.get(event.toolCallId);
		parents.delete(event.toolCallId);
		live.delete(event.toolCallId);
		try {
			if (event.toolName.startsWith(NUKE_TOOL_PREFIX)) return restoreFullError(event);
			return state === undefined ? undefined : deliverToParent(state, event);
		} catch (error) {
			// Never silent: the model sees that attachment failed. (A thrown handler error only reaches Pi's
			// extension error channel, not the model, so the warning rides on this result instead.)
			noteHandlerError(error, undefined);
			const warning: TextBlock = {
				type: "text",
				text:
					`[nuke_runtime] The runtime extension failed while attaching Nuke evidence to this result (${errorText(error).slice(0, 200)}). ` +
					`Nested/shortened evidence may be missing; inspect fresh Nuke state before retrying.`,
			};
			return { content: [...event.content, warning], structuredContent: event.structuredContent };
		}
	});

	pi.on("tool_execution_end", (event: ToolExecutionEndEvent) => {
		if (event.parentToolCallId !== undefined) {
			const root = rootOf(event.parentToolCallId);
			if (root === undefined) return;
			try {
				recordNestedEnd(event, root);
			} catch (error) {
				noteHandlerError(error, root);
			}
			return;
		}
		// Terminal for a model-issued call (after its result hook): per-call state never outlives it.
		parents.delete(event.toolCallId);
		live.delete(event.toolCallId);
	});

	// Terminal lifecycles: per-call transient state never outlives the call, turn or run.
	pi.on("turn_end", () => clearTransient());
	pi.on("agent_start", () => clearTransient());
	pi.on("agent_end", () => clearTransient());
	pi.on("session_shutdown", () => clearTransient());

	// Readiness probe for the panel launcher: no model turn, no Nuke call, nothing written to the
	// session. Replies with one compact notify (the panel's RPC client consumes it by prefix) listing
	// the project-owned MCP tools that are registered and active (declared to the model).
	// Keep the prefix in sync with _TOOLS_REPLY_PREFIX in harnesses/pi_rpc.py.
	pi.registerCommand("nuke_tools", {
		description: "Report which Nuke MCP tools are registered and active (compact, not recorded)",
		handler: async (args, ctx) => {
			const activeSet = new Set(pi.getActiveTools());
			const nuke = pi.getAllTools().filter((t) => t.namespace?.name === "mcp__nuke");
			ctx.ui.notify(
				"nuke-tool-readiness:" +
					JSON.stringify({
						nonce: args.trim(),
						registered: uniqueSorted(nuke.map((t) => t.name)),
						active: uniqueSorted(nuke.filter((t) => activeSet.has(t.name)).map((t) => t.name)),
						exposure: uniqueSorted(nuke.map((t) => String(t.exposure))),
					}),
				"info",
			);
		},
	});

	pi.registerCommand("nuke_runtime", {
		description: "Record read-only Nuke runtime diagnostics as a non-model session entry",
		handler: async (_args, ctx) => {
			const argv = process.argv;
			const prompt = ctx.getSystemPrompt();
			const promptOptions = ctx.getSystemPromptOptions();

			const active = pi.getActiveTools();
			const activeSet = new Set(active);
			const all = pi.getAllTools();
			const tools = all.map((t) => {
				const isActive = activeSet.has(t.name);
				// `codemode`/`deferred` tools stay callable from codemode scripts whether active or not.
				const callableViaCodemode = t.exposure === "codemode" || t.exposure === "deferred";
				return {
					name: t.name,
					exposure: t.exposure,
					active: isActive,
					callable: isActive || callableViaCodemode,
					callableVia: isActive ? "declared" : callableViaCodemode ? "codemode" : "none",
					namespace: t.namespace?.name,
					readOnlyHint: t.annotations?.readOnlyHint,
					source: t.sourceInfo,
				};
			});
			const callableNames = tools.filter((t) => t.callable).map((t) => t.name);
			const codeToolsCallable = uniqueSorted(callableNames.filter((n) => BUILTIN_CODE_TOOLS.has(n)));
			const namespaces = uniqueSorted(tools.map((t) => t.namespace).filter((n): n is string => !!n));

			const commands = pi.getCommands().map((c) => ({ name: c.name, source: c.source, path: c.sourceInfo.path }));
			const self = commands.find((c) => c.name === "nuke_runtime");
			const pkg = readPackageVersion(self ? dirname(self.path) : undefined);

			const sourcePaths = uniqueSorted([
				...tools.map((t) => t.source.path),
				...commands.map((c) => c.path),
			]);

			const envValues: Record<string, string | null> = {};
			for (const name of PI_ENV_VALUES) envValues[name] = process.env[name] ?? null;
			const piEnvNames = uniqueSorted(Object.keys(process.env).filter((n) => n.startsWith("PI_")));
			const bridgePin = process.env.NUKE_CODEX_BRIDGE_FILE ?? null;
			const bridge = await probeBridge(diagClientId);

			const snapshot = {
				schema: SCHEMA,
				measured: {
					capturedAt: new Date().toISOString(),
					node: { execPath: process.execPath, version: process.version, pid: process.pid },
					pi: { version: pkg.version ?? null, packageJson: pkg.packageJson ?? null },
					mode: ctx.mode,
					cwd: ctx.cwd,
					projectTrusted: ctx.isProjectTrusted(),
					session: {
						id: ctx.sessionManager.getSessionId(),
						file: ctx.sessionManager.getSessionFile() ?? null,
						dir: ctx.sessionManager.getSessionDir(),
					},
					model: ctx.model ? { provider: ctx.model.provider, id: ctx.model.id } : null,
					thinkingLevel: ctx.thinkingLevel ?? null,
					env: { values: envValues, piVariableNames: piEnvNames },
					bridgePin: { envVar: "NUKE_CODEX_BRIDGE_FILE", path: bridgePin, exists: bridgePin ? existsSync(bridgePin) : false },
					path: (process.env.PATH ?? "").split(":").filter(Boolean),
					settings: safeSettings(pi.getSettings()),
					systemPrompt: {
						sha256: createHash("sha256").update(prompt).digest("hex"),
						length: prompt.length,
						text: prompt,
						options: {
							hasCustomPrompt: promptOptions.customPrompt !== undefined,
							hasForcedPrompt: promptOptions.forceSystemPrompt !== undefined,
							selectedTools: promptOptions.selectedTools ?? null,
							hiddenTools: promptOptions.hiddenTools ?? null,
							appendSystemPromptLength: promptOptions.appendSystemPrompt?.length ?? 0,
							promptGuidelineCount: promptOptions.promptGuidelines?.length ?? 0,
							sectionNames: Object.keys(promptOptions.sections ?? {}),
							contextFiles: (promptOptions.contextFiles ?? []).map((f) => f.path),
							skills: (promptOptions.skills ?? []).map((s) => ({ name: s.name, path: s.filePath })),
						},
					},
					tools: {
						active: [...active].sort(),
						callable: uniqueSorted(callableNames),
						builtinCodeToolsCallable: codeToolsCallable,
						mcpNamespaces: namespaces,
						all: tools,
					},
					commands,
					loadedSourcePaths: sourcePaths,
					bridge,
					enforcement: {
						toolSurface: surface,
						hooks: ["tool_call", "tool_execution_start", "tool_result", "tool_execution_end", "turn_end", "agent_start", "agent_end", "session_shutdown"],
						evidence: { capped: false, retention: "transient, per in-flight model-issued call" },
						guardBoundary:
							"tool_call guard covers calls routed through Pi's tool pipeline; not an OS sandbox; helper APIs inside a codemode script's own runtime are outside it",
						bridgeProbeClientId: diagClientId,
						stats: { ...stats, runningCalls: live.size, pendingScriptStates: parents.size },
					},
				},
				// What the launcher requested. Not proof that any resource loaded.
				argv: {
					argv: redactArgv(argv),
					explicitExtensions: argvFlagValues(argv, ["-e", "--extension"]),
					systemPromptFlag: argvFlagValues(argv, ["--system-prompt"]).length > 0,
					toolsAllowlist: argvFlagValues(argv, ["--tools"]),
					isolationFlags: argvPresent(argv, [
						"-ne", "--no-extensions", "-ns", "--no-skills", "-np", "--no-prompt-templates",
						"-nc", "--no-context-files", "--no-themes", "-nbt", "--no-builtin-tools", "--no-tools",
					]),
				},
			};

			pi.appendEntry(ENTRY_TYPE, snapshot);

			const lease = asRecord(bridge.lease);
			const leaseText =
				bridge.reachable !== true || lease?.scoped !== true
					? ""
					: lease.admitted === true
						? ", lease ok"
						: `, lease refused (${String(lease.code)})`;
			const summary =
				`nuke_runtime: pi ${pkg.version ?? "?"}, node ${process.version}, ` +
				`${active.length} active/${callableNames.length} callable tools, ` +
				`code tools callable: ${codeToolsCallable.length ? codeToolsCallable.join(",") : "none"}, ` +
				`bridge ${String(bridge.state)}${leaseText}`;
			ctx.ui.notify(summary, "info");
		},
	});
}
