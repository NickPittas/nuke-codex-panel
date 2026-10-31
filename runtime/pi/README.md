# Private Pi runtime

Official Node.js and official Pi (`@earendil-works/pi-coding-agent`) owned by this
plugin. Nothing here uses the global Node, global Pi, `PATH`, `~/.npmrc`, or
`~/.pi`.
`manifest.json` records the pinned versions and hashes; `nuke_codex_panel/pi_runtime.py`
resolves the runtime and checks it for consistency (see "What is verified").

Committed: `package.json`, `package-lock.json`, `manifest.json`,
`credential-env.json`, `generate-credential-env.mjs`, `auth-helper.mjs` (F2 private SDK
account helper: public `ModelRuntime` login/logout/refresh against the private
`<agent dir>/auth.json`, JSONL over stdio, no credentials in argv), `nuke-runtime.ts` (sole project extension: `/nuke_runtime` diagnostics incl. live pinned-bridge probe, F3 `tool_call` surface guard and `tool_result` error/image forwarding; F3 live-exercised, READY for user acceptance, NOT ACCEPTED; routed-tool guard only, not an OS sandbox), this file.
Ignored (reproducible from the above): `node/`, `node_modules/`.

## Managed MCP readiness

The panel registers its Nuke MCP server with direct exposure. Its restricted tool list remains `codemode,tool_search,mcp__nuke__*`, with the ordinary coding tools excluded. Direct declaration avoids depending on replay of lazily discovered tools when Pi resumes with an explicit tool selection.

The owned `/nuke_tools` command reports registered and active Nuke tool names without a provider turn. The panel checks this before reporting ready on initial launch and steering renewal. If the complete bundled Nuke toolset does not become active during the bounded startup wait, it stays not-ready and reports an error; it does not send the pending model prompt. `/nuke_runtime` remains the fuller diagnostic snapshot.

## Install

Do not install by hand. From the project root run the installer (`python3 install.py --target PATH --nuke-dir PATH [--no-register] [--check]`; Windows `py -3`); see [docs/INSTALLATION.md](../../docs/INSTALLATION.md). It downloads the official Node archive for `linux-x64`, `win-x64`, `darwin-x64` or `darwin-arm64` over TLS, verifies its sha256 against `manifest.json`, then runs `npm ci --ignore-scripts` with the private Node against `package-lock.json` using an isolated config/cache and no ambient auth, stages the owned files, copies upstream licenses to `third-party-notices/` (`index.json`; `npm/<name>@<version>/`; `node/LICENSE`) and records `install-state.json`. Linux x64 is the only natively verified platform.

Pi (MIT) is the unmodified official package; this runtime is a customized distribution (pinned Pi plus the owned extensions listed above), not a fork. See [../../THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).

`npm ci` installs exactly the lockfile. The lock records an SRI (sha512) hash for each
package, which npm checks at install time.

## What is verified

Install time: TLS to nodejs.org / registry.npmjs.org, the Node tarball sha256 from
SHASUMS256.txt (no GPG signature check), and npm's lockfile integrity hashes.

Every launch (`resolve_runtime()`, not cached) only checks consistency: the required files
exist (Node binary, executable; `node_version.h`; `package.json`; `package-lock.json`; the
installed Pi `package.json`; the RPC entry; `nuke-runtime.ts`; `credential-env.json`), the
Node version read from its header equals the pin, the sha256 of the root `package.json` and
`package-lock.json` (and `credential-env.json` when read) match `manifest.json`, and the
installed Pi version equals the pin. The Node binary and the contents of `node_modules/` are
NOT hashed at runtime. This detects a missing or mismatched install, not tampering by anyone
who can write to this directory.

## Updating the pin

Change `package.json`, re-run `npm install --ignore-scripts` as above, run
`node/bin/node generate-credential-env.mjs`, then update the hashes and versions
in `manifest.json`. A mismatch makes `pi_runtime.resolve_runtime()` fail closed.
