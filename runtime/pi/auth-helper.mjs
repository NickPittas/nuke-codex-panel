// Private Pi authentication helper for the Nuke Codex Panel.
//
// Drives the pinned official Pi SDK's public ModelRuntime login/logout/auth
// APIs over JSONL on stdin/stdout so the panel's Qt UI can offer Pi's complete,
// dynamically discovered API-key and subscription/OAuth catalog. All provider
// flows (callback servers, device polling, token exchange, credential file
// locking, refresh) are executed by the SDK; this helper never opens a browser,
// owns no conversation, hardcodes no provider and never serializes a credential.
//
//   node auth-helper.mjs --agent-dir /abs/private/agent/dir
//
// Requests  (stdin):  {id, type: "catalog"|"login"|"logout"|"refresh", provider?, authType?}
//                     {type: "reply", operationId, promptId, value}
//                     {type: "cancel", operationId}
// Output (stdout):    {type: "ready"}
//                     {type: "response", id, success, data?, error?, cancelled?, changed?}
//                     {type: "auth_prompt", operationId, promptId, prompt}
//                     {type: "auth_event", operationId, event}
//                     {type: "auth_prompt_cancelled", operationId, promptId}
// stdout carries protocol lines only; stderr carries at most fixed, sanitized
// diagnostics.

import { mkdirSync, statSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";

// ---------------------------------------------------------------------------
// stdout/stderr discipline: only this helper writes protocol lines. Anything
// the SDK or its dependencies print is discarded so it can neither corrupt the
// JSONL stream nor leak entered values to stderr.
// ---------------------------------------------------------------------------
const writeProtocol = process.stdout.write.bind(process.stdout);
const writeDiagnostic = process.stderr.write.bind(process.stderr);
const discard = (...args) => {
  const callback = args.find((arg) => typeof arg === "function");
  if (callback) callback();
  return true;
};
process.stdout.write = discard;
process.stderr.write = discard;
for (const name of ["log", "info", "debug", "warn", "error", "trace", "dir", "table"]) {
  console[name] = () => {};
}

let shuttingDown = false;

function send(message) {
  try {
    writeProtocol(`${JSON.stringify(message)}\n`);
  } catch {
    // Broken pipe: the parent is gone; stdin end/exit handling terminates us.
  }
}

function diagnostic(text) {
  try {
    writeDiagnostic(`${text}\n`);
  } catch {
    // ignore
  }
}

// A broken output pipe means the parent is gone. Shut down through the same
// path as end-of-stdin so an in-flight OAuth refresh still persists first.
process.stdout.on("error", () => shutdown(0));

// ---------------------------------------------------------------------------
// Argument handling. The agent directory is the only argv input.
// ---------------------------------------------------------------------------
function parseAgentDir(argv) {
  const index = argv.indexOf("--agent-dir");
  const value = index >= 0 ? argv[index + 1] : undefined;
  if (typeof value !== "string" || !value || !isAbsolute(value)) {
    diagnostic("auth-helper: --agent-dir <absolute path> is required");
    process.exit(2);
  }
  return resolve(value);
}

const agentDir = parseAgentDir(process.argv.slice(2));
const authPath = join(agentDir, "auth.json");
const modelsPath = join(agentDir, "models.json");

// Keep SDK path helpers on the private directory even if the launcher omitted it.
process.env.PI_CODING_AGENT_DIR = agentDir;
try {
  mkdirSync(agentDir, { recursive: true, mode: 0o700 });
} catch {
  diagnostic("auth-helper: cannot create private agent directory");
  process.exit(2);
}

// ---------------------------------------------------------------------------
// Text sanitation and secret redaction.
// ---------------------------------------------------------------------------
const MAX_ERROR_CHARS = 600;
const MAX_FIELD_CHARS = 4096;
const MAX_REPLY_CHARS = 65536;
const MAX_LINE_CHARS = 4 * 1024 * 1024;
const REDACTED = "[redacted]";

/** Strip control characters (keeping \n and \t when allowed) and cap length. */
function cleanText(value, max = MAX_FIELD_CHARS, { multiline = true } = {}) {
  let text = typeof value === "string" ? value : value === undefined || value === null ? "" : String(value);
  // eslint-disable-next-line no-control-regex
  text = text.replace(/\u001b\[[0-9;?]*[ -/]*[@-~]/g, "");
  // eslint-disable-next-line no-control-regex
  text = text.replace(multiline ? /[\u0000-\u0008\u000b-\u001f\u007f]/g : /[\u0000-\u001f\u007f]/g, " ");
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

const GENERIC_SECRET_PATTERNS = [
  [/\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]*/g, () => REDACTED],
  [/\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}/gi, (_m, scheme) => `${scheme} ${REDACTED}`],
  [
    /\b(access_token|refresh_token|id_token|token|api[_-]?key|client_secret|secret|password|code|state|authorization)(["']?\s*[:=]\s*["']?)[^\s"'&,;}]+/gi,
    (_m, name, separator) => `${name}${separator}${REDACTED}`,
  ],
  [/\bsk-[A-Za-z0-9_-]{8,}/g, () => REDACTED],
];

function redact(text, secrets) {
  let result = text;
  if (secrets && secrets.size > 0) {
    for (const secret of [...secrets].sort((a, b) => b.length - a.length)) {
      if (secret.length >= 4) result = result.split(secret).join(REDACTED);
    }
  }
  for (const [pattern, replacement] of GENERIC_SECRET_PATTERNS) {
    result = result.replace(pattern, replacement);
  }
  return result;
}

function safeMessage(error, secrets) {
  const raw = typeof error?.message === "string" ? error.message : typeof error === "string" ? error : "";
  const text = cleanText(redact(raw, secrets), MAX_ERROR_CHARS, { multiline: false }).trim();
  return text || "Authentication operation failed.";
}

/** Error message plus one level of cause text; never a stack or an object. */
function describeError(error, secrets) {
  const head = safeMessage(error, secrets);
  const cause = error?.cause;
  const causeText =
    cause && typeof cause === "object" && typeof cause.message === "string"
      ? cleanText(redact(cause.message, secrets), 300, { multiline: false }).trim()
      : "";
  return causeText && !head.includes(causeText) ? `${head}: ${causeText}` : head;
}

function addSecret(secrets, value, minLength) {
  if (typeof value !== "string" || value.length < minLength) return;
  secrets.add(value);
  // A pasted redirect URL carries the authorization code in query/hash params.
  if (value.includes("://") || value.includes("?") || value.includes("=")) {
    try {
      const url = new URL(value, "http://localhost");
      for (const [, v] of url.searchParams) if (v.length >= 4) secrets.add(v);
      const hash = new URLSearchParams(url.hash.replace(/^#/, ""));
      for (const [, v] of hash) if (v.length >= 4) secrets.add(v);
    } catch {
      // not a URL
    }
    for (const part of value.split(/[?&#]/)) {
      const eq = part.indexOf("=");
      if (eq >= 0 && part.length - eq - 1 >= 4) secrets.add(part.slice(eq + 1));
    }
  }
}

function collectCredentialSecrets(secrets, value, depth = 0) {
  if (depth > 3 || value === null || value === undefined) return;
  if (typeof value === "string") {
    if (value.length >= 6) secrets.add(value);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) collectCredentialSecrets(secrets, item, depth + 1);
    return;
  }
  if (typeof value === "object") {
    for (const item of Object.values(value)) collectCredentialSecrets(secrets, item, depth + 1);
  }
}

function abortError(message = "Authentication cancelled.") {
  const error = new Error(message);
  error.name = "AbortError";
  return error;
}

function isAbortLike(error) {
  return error?.name === "AbortError" || error?.code === "ABORT_ERR";
}

// ---------------------------------------------------------------------------
// SDK runtime (public API only).
// ---------------------------------------------------------------------------
let sdk;
let runtime;
try {
  sdk = await import("@earendil-works/pi-coding-agent");
  runtime = await sdk.ModelRuntime.create({
    authPath,
    modelsPath,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });
} catch {
  diagnostic("auth-helper: failed to initialize the Pi SDK model runtime");
  process.exit(1);
}

const { CredentialSynchronizationError, SettingsManager } = sdk;

// OpenAI's ChatGPT flow needs a stable per-installation device id. Pi keeps it
// in the agent directory's settings.json, so reusing the private directory
// yields the same id the managed Pi runtime sees. Project settings are never read.
let deviceSettingsManager;
function deviceSettings() {
  deviceSettingsManager ??= SettingsManager.create(agentDir, agentDir, { projectTrusted: false });
  return deviceSettingsManager;
}

function isSyncError(error) {
  return CredentialSynchronizationError !== undefined && error instanceof CredentialSynchronizationError;
}

async function storedCredentialTypes(signal) {
  const stored = new Map();
  for (const info of await runtime.listCredentials({ signal })) {
    if (info && typeof info.providerId === "string") stored.set(info.providerId, info.type);
  }
  return stored;
}

function activeAuthType(providerId, stored) {
  return stored.get(providerId) ?? (runtime.isUsingOAuth(providerId) ? "oauth" : "api_key");
}

/** Per-entry status from the SDK's local provider status (no secrets, no network). */
function entryStatus(providerId, authType, stored) {
  const sdkStatus = runtime.getProviderAuthStatus(providerId);
  if (!sdkStatus.configured || activeAuthType(providerId, stored) !== authType) {
    return { configured: false };
  }
  const status = { configured: true, type: authType };
  if (typeof sdkStatus.source === "string") status.source = cleanText(sdkStatus.source, 200, { multiline: false });
  if (typeof sdkStatus.label === "string") status.label = cleanText(sdkStatus.label, 200, { multiline: false });
  return status;
}

function authMethod(provider, authType) {
  return authType === "oauth" ? provider.auth?.oauth : provider.auth?.apiKey;
}

function buildCatalog(stored) {
  const options = [];
  const providers = runtime.getProviders();
  for (const provider of providers) {
    for (const authType of ["oauth", "api_key"]) {
      const method = authMethod(provider, authType);
      if (!method) continue;
      const option = {
        providerId: provider.id,
        providerName: cleanText(provider.name ?? provider.id, 200, { multiline: false }),
        authType,
        methodName: cleanText(method.name ?? provider.name ?? provider.id, 200, { multiline: false }),
        subscription: authType === "oauth" && method.isSubscription === true,
        canLogin: typeof method.login === "function",
        status: entryStatus(provider.id, authType, stored),
      };
      if (authType === "oauth" && typeof method.loginLabel === "string" && method.loginLabel) {
        option.loginLabel = cleanText(method.loginLabel, 200, { multiline: false });
      }
      options.push(option);
    }
  }
  options.sort((a, b) => a.providerName.localeCompare(b.providerName));

  const names = new Map(providers.map((p) => [p.id, p.name ?? p.id]));
  const accounts = [];
  for (const [providerId, type] of stored) {
    accounts.push({
      providerId,
      providerName: cleanText(names.get(providerId) ?? providerId, 200, { multiline: false }),
      type,
      // Public SDK predicate over the offline availability snapshot. For OAuth it
      // proves only that a stored credential exists (token validity is not
      // checked and no network/refresh happens); for API keys it also reflects
      // whether the key resolves locally. It is never provider authentication.
      configured: runtime.hasConfiguredAuth(providerId),
      configuredBasis: type === "oauth" ? "presence_only" : "local_resolution",
      source: "stored",
      stored: true,
      known: names.has(providerId),
    });
  }
  accounts.sort((a, b) => a.providerName.localeCompare(b.providerName) || a.providerId.localeCompare(b.providerId));
  return { options, accounts };
}

function authFileRevision() {
  try {
    const info = statSync(authPath, { bigint: true });
    return `${info.ino}:${info.size}:${info.mtimeNs}`;
  } catch {
    return "missing";
  }
}

// ---------------------------------------------------------------------------
// Operation state: at most one login/logout/refresh at a time.
// ---------------------------------------------------------------------------
let active; // { id, kind, controller, prompts: Map, nextPromptId, secrets, done, cancelled }

function emitEvent(op, event) {
  if (op.done || op.controller.signal.aborted || !event || typeof event !== "object") return;
  let out;
  switch (event.type) {
    case "info": {
      out = { type: "info", message: cleanText(event.message) };
      if (Array.isArray(event.links)) {
        out.links = event.links
          .filter((link) => link && typeof link.url === "string" && link.url)
          .map((link) => {
            const item = { url: cleanText(link.url, MAX_FIELD_CHARS, { multiline: false }) };
            if (typeof link.label === "string" && link.label) item.label = cleanText(link.label, 300, { multiline: false });
            return item;
          });
      }
      break;
    }
    case "auth_url": {
      if (typeof event.url !== "string" || !event.url) return;
      out = { type: "auth_url", url: cleanText(event.url, MAX_FIELD_CHARS, { multiline: false }) };
      if (typeof event.instructions === "string" && event.instructions) out.instructions = cleanText(event.instructions);
      break;
    }
    case "device_code": {
      if (typeof event.userCode !== "string" || typeof event.verificationUri !== "string") return;
      out = {
        type: "device_code",
        userCode: cleanText(event.userCode, 200, { multiline: false }),
        verificationUri: cleanText(event.verificationUri, MAX_FIELD_CHARS, { multiline: false }),
      };
      if (Number.isFinite(event.intervalSeconds)) out.intervalSeconds = event.intervalSeconds;
      if (Number.isFinite(event.expiresInSeconds)) out.expiresInSeconds = event.expiresInSeconds;
      break;
    }
    case "progress": {
      out = { type: "progress", message: cleanText(event.message) };
      break;
    }
    default:
      return;
  }
  send({ type: "auth_event", operationId: op.id, event: out });
}

function serializePrompt(prompt) {
  const type = prompt?.type;
  if (type !== "text" && type !== "secret" && type !== "manual_code" && type !== "select") return undefined;
  const out = { type, message: cleanText(prompt.message) };
  if (type !== "select") {
    if (typeof prompt.placeholder === "string" && prompt.placeholder) out.placeholder = cleanText(prompt.placeholder, 500);
    return out;
  }
  if (!Array.isArray(prompt.options) || prompt.options.length === 0) return undefined;
  out.options = prompt.options
    .filter((option) => option && typeof option.id === "string")
    .map((option) => {
      const item = { id: option.id, label: cleanText(option.label ?? option.id, 500, { multiline: false }) };
      if (typeof option.description === "string" && option.description) item.description = cleanText(option.description, 1000);
      return item;
    });
  return out.options.length > 0 ? out : undefined;
}

function createInteraction(op) {
  const { signal } = op.controller;
  return {
    signal,
    notify(event) {
      try {
        emitEvent(op, event);
      } catch {
        // A malformed event must not break the SDK flow.
      }
    },
    prompt(prompt) {
      if (op.done || signal.aborted) return Promise.reject(signal.reason ?? abortError());
      const serialized = serializePrompt(prompt);
      if (!serialized) return Promise.reject(new Error("Unsupported authentication prompt."));
      const promptSignal = prompt.signal;
      if (promptSignal?.aborted) return Promise.reject(promptSignal.reason ?? abortError("Prompt withdrawn."));

      const promptId = op.nextPromptId++;
      return new Promise((resolvePrompt, rejectPrompt) => {
        const entry = {
          type: serialized.type,
          optionIds: serialized.type === "select" ? new Set(serialized.options.map((o) => o.id)) : undefined,
          resolve: resolvePrompt,
          reject: rejectPrompt,
          onPromptAbort: undefined,
        };
        entry.cleanup = () => {
          op.prompts.delete(promptId);
          if (entry.onPromptAbort) promptSignal?.removeEventListener("abort", entry.onPromptAbort);
        };
        if (promptSignal) {
          entry.onPromptAbort = () => {
            if (!op.prompts.has(promptId)) return;
            entry.cleanup();
            if (!op.done && !signal.aborted) send({ type: "auth_prompt_cancelled", operationId: op.id, promptId });
            rejectPrompt(promptSignal.reason ?? abortError("Prompt withdrawn."));
          };
          promptSignal.addEventListener("abort", entry.onPromptAbort, { once: true });
        }
        op.prompts.set(promptId, entry);
        send({ type: "auth_prompt", operationId: op.id, promptId, prompt: serialized });
      });
    },
  };
}

function settlePendingPrompts(op, reason) {
  for (const entry of [...op.prompts.values()]) {
    entry.cleanup();
    entry.reject(reason);
  }
  op.prompts.clear();
}

function handleReply(message) {
  const op = active;
  if (!op || op.done || message.operationId !== op.id || !Number.isSafeInteger(message.promptId)) return;
  const entry = op.prompts.get(message.promptId);
  if (!entry || typeof message.value !== "string" || message.value.length > MAX_REPLY_CHARS) return;
  if (entry.optionIds && !entry.optionIds.has(message.value)) return;
  if (entry.type === "secret" || entry.type === "manual_code") addSecret(op.secrets, message.value, 4);
  else if (entry.type === "text") addSecret(op.secrets, message.value, 8);
  entry.cleanup();
  entry.resolve(message.value);
}

function handleCancel(message) {
  const op = active;
  if (!op || op.done || message.operationId !== op.id) return;
  // A credential refresh deliberately outlives its caller: the SDK persists a
  // rotated OAuth token even when the caller gives up, so it is never aborted.
  if (op.kind === "refresh") return;
  op.cancelled = true;
  const reason = abortError();
  settlePendingPrompts(op, reason);
  if (!op.controller.signal.aborted) op.controller.abort(reason);
}

function validProvider(value) {
  return typeof value === "string" && value.length > 0 && value.length <= 256;
}

function validAuthType(value) {
  return value === "api_key" || value === "oauth";
}

function finishResponse(op, response) {
  op.done = true;
  settlePendingPrompts(op, abortError());
  if (active === op) active = undefined;
  send({ type: "response", id: op.id, ...response });
}

/** Terminal failure. `changed` reflects the actual auth-file revision, not the outcome. */
function failureResponse(op, error) {
  const changed = authFileRevision() !== op.revisionBefore;
  if (op.cancelled || op.controller.signal.aborted || isAbortLike(error)) {
    return { success: false, cancelled: true, error: "Cancelled.", changed };
  }
  return { success: false, error: describeError(error, op.secrets), changed };
}

const SYNC_WARNING =
  "Credential changes were committed, but Pi could not refresh its local model/auth snapshot";

function syncWarning(error, secrets) {
  const cause = error?.cause;
  const detail =
    cause && typeof cause.message === "string"
      ? cleanText(redact(cause.message, secrets), 300, { multiline: false }).trim()
      : "";
  return detail ? `${SYNC_WARNING}: ${detail}` : `${SYNC_WARNING}.`;
}

async function runLogin(op, providerId, authType) {
  const provider = runtime.getProvider(providerId);
  if (!provider) throw new Error(`Unknown provider: ${cleanText(providerId, 100, { multiline: false })}`);
  const method = authMethod(provider, authType);
  if (!method || typeof method.login !== "function") {
    throw new Error(
      `${cleanText(provider.name ?? providerId, 100, { multiline: false })} has no interactive ${
        authType === "oauth" ? "subscription/OAuth" : "API key"
      } login; it is configured through the environment or models.json.`,
    );
  }
  let warning;
  try {
    const credential = await runtime.login(providerId, authType, createInteraction(op), {
      getDeviceId: () => deviceSettings().getOrCreateDeviceId(),
    });
    collectCredentialSecrets(op.secrets, credential);
  } catch (error) {
    if (!isSyncError(error)) throw error;
    // The credential was written; only the in-memory snapshot sync failed.
    collectCredentialSecrets(op.secrets, error.credential);
    warning = syncWarning(error, op.secrets);
  }
  await deviceSettingsManager?.flush().catch(() => {});
  const stored = await storedCredentialTypes(AbortSignal.timeout(15_000)).catch(() => new Map());
  const data = {
    kind: "login",
    providerId,
    providerName: cleanText(provider.name ?? providerId, 200, { multiline: false }),
    authType,
    status: entryStatus(providerId, authType, stored),
  };
  if (warning) data.warning = warning;
  return { success: true, changed: true, data };
}

async function runLogout(op, providerId) {
  const provider = runtime.getProvider(providerId);
  const { signal } = op.controller;
  const before = await storedCredentialTypes(signal);
  const hadCredential = before.has(providerId);
  let warning;
  if (hadCredential) {
    try {
      await runtime.logout(providerId, { signal });
    } catch (error) {
      if (!isSyncError(error)) throw error;
      warning = syncWarning(error, op.secrets);
    }
  }
  const after = await storedCredentialTypes(AbortSignal.timeout(15_000)).catch(() => new Map());
  const data = {
    kind: "logout",
    providerId,
    providerName: cleanText(provider?.name ?? providerId, 200, { multiline: false }),
    hadCredential,
    removed: hadCredential && !after.has(providerId),
  };
  // Environment/models.json credentials are outside Pi's logout and may remain.
  data.status = entryStatus(providerId, activeAuthType(providerId, after), after);
  if (warning) data.warning = warning;
  // A logout with nothing stored must not renew the running Pi.
  return { success: true, changed: hadCredential || authFileRevision() !== op.revisionBefore, data };
}

async function runRefresh(op, providerId, requestedType) {
  const provider = runtime.getProvider(providerId);
  if (!provider) throw new Error(`Unknown provider: ${cleanText(providerId, 100, { multiline: false })}`);
  // Non-cancellable: no abort signal reaches the SDK. The SDK races a caller
  // signal against its credential refresh but still persists rotated tokens
  // after the caller stops waiting; the helper must stay alive until that
  // settles. The SDK's own refresh/lock bounds remain the only limits.
  const storedBefore = await storedCredentialTypes();

  // getAuth resolves stored/ambient auth and lets the SDK refresh an OAuth
  // token that is near expiry under its credential lock. The result holds
  // secrets and is only inspected, never serialized.
  const resolution = await runtime.getAuth(providerId);
  const configured = resolution !== undefined;
  const source = typeof resolution?.source === "string" ? cleanText(resolution.source, 200, { multiline: false }) : undefined;

  let warning;
  try {
    const result = await runtime.refresh({ allowNetwork: false, providers: [providerId] });
    const refreshError = result.errors?.get(providerId);
    if (refreshError) warning = `Local status refresh reported: ${safeMessage(refreshError, op.secrets)}`;
    // Without a signal the SDK should never report an abort; if it does, the
    // outcome is truthfully cancelled and failureResponse records the changes.
    if (result.aborted) throw abortError();
  } catch (error) {
    if (isAbortLike(error)) throw error;
    warning = `Local status refresh failed: ${safeMessage(error, op.secrets)}`;
  }

  const stored = await storedCredentialTypes(AbortSignal.timeout(15_000)).catch(() => storedBefore);
  const storedType = stored.get(providerId);
  const type = storedType ?? (configured ? activeAuthType(providerId, stored) : undefined);
  const authType = requestedType ?? type ?? (provider.auth?.oauth && !provider.auth?.apiKey ? "oauth" : "api_key");
  const data = {
    kind: "refresh",
    providerId,
    providerName: cleanText(provider.name ?? providerId, 200, { multiline: false }),
    authType,
    checked: true,
    // True when the SDK resolved a credential locally (an OAuth token that was
    // near expiry has been refreshed). It is not a provider-side validation.
    configured,
    resolved: configured,
    stored: storedType !== undefined,
    providerValidated: false,
    status: entryStatus(providerId, authType, stored),
  };
  if (type) data.type = type;
  if (source) data.source = source;
  if (warning) data.warning = warning;
  // A stored OAuth token may have rotated; compare the auth file revision
  // (metadata only) so the running Pi is renewed only when something changed.
  return { success: true, changed: authFileRevision() !== op.revisionBefore, data };
}

async function runMutation(id, type, request) {
  const op = {
    id,
    kind: type,
    controller: new AbortController(),
    prompts: new Map(),
    nextPromptId: 1,
    secrets: new Set(),
    done: false,
    cancelled: false,
    revisionBefore: authFileRevision(),
  };
  active = op;
  try {
    let response;
    if (type === "login") response = await runLogin(op, request.provider, request.authType);
    else if (type === "logout") response = await runLogout(op, request.provider);
    else response = await runRefresh(op, request.provider, request.authType);
    finishResponse(op, response);
  } catch (error) {
    finishResponse(op, failureResponse(op, error));
  }
}

let catalogQueue = Promise.resolve();

function runCatalog(id) {
  catalogQueue = catalogQueue.then(async () => {
    try {
      let warning;
      // Re-read models.json/availability locally; never network. While a login
      // is mid-flight the existing snapshot is used instead of rebuilding.
      if (!active) {
        try {
          const result = await runtime.refresh({ allowNetwork: false, signal: AbortSignal.timeout(15_000) });
          const failed = [...(result.errors?.entries() ?? [])];
          if (failed.length > 0) {
            warning = `Provider status refresh reported errors for: ${failed
              .map(([providerId]) => cleanText(providerId, 80, { multiline: false }))
              .join(", ")}`;
          }
        } catch (error) {
          warning = `Local catalog refresh failed: ${safeMessage(error)}`;
        }
      }
      const stored = await storedCredentialTypes(AbortSignal.timeout(15_000));
      const data = buildCatalog(stored);
      const configError = runtime.getError();
      if (configError) {
        const text = cleanText(redact(configError), 500, { multiline: false });
        warning = warning ? `${warning}; ${text}` : text;
      }
      if (warning) data.warning = warning;
      send({ type: "response", id, success: true, data });
    } catch (error) {
      send({ type: "response", id, success: false, error: describeError(error) });
    }
  });
}

function handleRequest(message) {
  const id = message.id;
  if (!Number.isSafeInteger(id)) return;
  if (shuttingDown) {
    send({ type: "response", id, success: false, error: "The authentication helper is shutting down.", changed: false });
    return;
  }
  const type = message.type;
  if (type === "catalog") {
    runCatalog(id);
    return;
  }
  if (type !== "login" && type !== "logout" && type !== "refresh") {
    send({ type: "response", id, success: false, error: "Unknown request type." });
    return;
  }
  if (!validProvider(message.provider)) {
    send({ type: "response", id, success: false, error: "A provider is required." });
    return;
  }
  if (type === "login" && !validAuthType(message.authType)) {
    send({ type: "response", id, success: false, error: "A valid authType (api_key or oauth) is required." });
    return;
  }
  if (message.authType !== undefined && !validAuthType(message.authType)) {
    send({ type: "response", id, success: false, error: "Invalid authType." });
    return;
  }
  if (active) {
    send({ type: "response", id, success: false, error: "Another authentication operation is already in progress." });
    return;
  }
  void runMutation(id, type, { provider: message.provider, authType: message.authType });
}

function handleLine(line) {
  if (!line.trim()) return;
  let message;
  try {
    message = JSON.parse(line);
  } catch {
    return;
  }
  if (!message || typeof message !== "object" || Array.isArray(message)) return;
  try {
    if (message.type === "reply") handleReply(message);
    else if (message.type === "cancel") handleCancel(message);
    else handleRequest(message);
  } catch {
    if (Number.isSafeInteger(message.id)) {
      send({ type: "response", id: message.id, success: false, error: "Internal authentication helper error." });
    }
  }
}

// ---------------------------------------------------------------------------
// stdin loop (never blocked by SDK awaits) and shutdown.
// ---------------------------------------------------------------------------
function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  const op = active;
  if (!op || op.done) {
    setImmediate(() => process.exit(code));
    return;
  }
  if (op.kind !== "refresh") {
    op.cancelled = true;
    const reason = abortError();
    settlePendingPrompts(op, reason);
    if (!op.controller.signal.aborted) op.controller.abort(reason);
    // Give the SDK a moment to close callback servers and release locks.
    const timer = setTimeout(() => process.exit(code), 1500);
    timer.unref?.();
  }
  // A credential refresh is never aborted and never force-exited: wait for the
  // SDK to finish persisting any rotated token, then exit. The interval keeps
  // the event loop alive while that settles.
  const poll = setInterval(() => {
    if (op.done) {
      clearInterval(poll);
      setImmediate(() => process.exit(code));
    }
  }, 20);
}

process.on("SIGTERM", () => shutdown(0));
process.on("SIGINT", () => shutdown(0));
process.on("SIGHUP", () => shutdown(0));
process.on("unhandledRejection", () => {});
process.on("uncaughtException", () => {
  diagnostic("auth-helper: internal error");
  shutdown(1);
});

let buffer = "";
let discarding = false;
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  let text = chunk;
  while (text.length > 0) {
    const newline = text.indexOf("\n");
    if (newline < 0) {
      if (!discarding) {
        buffer += text;
        if (buffer.length > MAX_LINE_CHARS) {
          buffer = "";
          discarding = true;
        }
      }
      return;
    }
    const piece = text.slice(0, newline);
    text = text.slice(newline + 1);
    if (discarding) {
      discarding = false;
      buffer = "";
      continue;
    }
    const line = buffer + piece;
    buffer = "";
    handleLine(line);
  }
});
process.stdin.on("end", () => shutdown(0));
process.stdin.on("error", () => shutdown(0));
process.stdin.resume();

send({ type: "ready" });
