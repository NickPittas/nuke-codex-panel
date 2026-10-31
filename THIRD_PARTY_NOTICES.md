# Third-party notices

Nuke Pi (`nuke-codex-panel`) is MIT licensed, Copyright (c) 2026 Nick Pittas (see [LICENSE](LICENSE)). That license covers this project's own code, including its owned Pi extensions (`runtime/pi/nuke-runtime.ts`, `auth-helper.mjs`, `generate-credential-env.mjs`, `credential-env.json`). It does **not** relicense anything below.

## Customized distribution, not a fork

The Pi used by the panel is the **official, unmodified Pi 1.4.0** (`@earendil-works/pi-coding-agent`, MIT, author Mario Zechner) from the npm registry, pinned by `runtime/pi/package-lock.json` and `runtime/pi/manifest.json`. "Custom Pi" here means official pinned Pi plus this project's own extensions and configuration. No upstream source is copied into or modified in this repository, and the upstream packages keep their own licenses and copyright holders.

## Node.js

The official Node.js 26.12.0 binary distribution for the target platform (Linux x64, Windows x64, macOS x64, macOS arm64) is downloaded from nodejs.org at install time and verified by the sha256 pinned in `runtime/pi/manifest.json`. Node.js is MIT licensed and its `LICENSE` file additionally carries notices for bundled third-party components (for example V8, OpenSSL, ICU, npm and others). That full upstream `LICENSE` is preserved unmodified in the installed runtime.

## Pi license (verbatim)

The seven `@earendil-works/pi-*` packages (`pi-agent-core`, `pi-ai`, `pi-codemode`, `pi-coding-agent`, `pi-mcp`, `pi-telemetry`, `pi-tui`, all 1.4.0, `"license": "MIT"`) come from the repository `https://github.com/earendil-works/pi`. The npm tarballs contain no license file, and `packages/*/LICENSE` does not exist at tag `v1.4.0`; the repository-root `LICENSE` at tag `v1.4.0` is the upstream license text. It is stored verbatim, byte for byte, in [licenses/Pi-LICENSE](licenses/Pi-LICENSE) and reproduced here:

```text
MIT License

Copyright (c) 2025 Mario Zechner

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Note: `pi-codemode` and `pi-mcp` list their author as "Earendil Works" in `package.json`, but the only upstream license text published is the repository-root one above. `pi-mcp` additionally ships `LICENSES/modelcontextprotocol-typescript-sdk.txt` (MIT, Copyright (c) 2024 Anthropic, PBC), preserved by the installer.

## Dependencies that ship no license file in their npm tarball

Of the pinned lock's installed packages, these 12 contain no LICENSE/NOTICE file in `node_modules` (checked against the installed tree). Nothing below was invented; the "authoritative text" column records what was found upstream.

| Package | Version | Declared | Authoritative upstream text |
|---|---|---|---|
| `@earendil-works/pi-*` (6 packages: agent-core, ai, codemode, coding-agent, telemetry, tui) | 1.4.0 | MIT | repository-root LICENSE at `v1.4.0`, above |
| `@aws-sdk/credential-provider-http` 3.972.81, `@aws-sdk/credential-provider-login` 3.972.86, `@aws-sdk/nested-clients` 3.997.53 | | Apache-2.0 | `aws/aws-sdk-js-v3` repository-root LICENSE (Apache-2.0, unmodified standard text), stored in [licenses/aws-sdk-js-v3-LICENSE](licenses/aws-sdk-js-v3-LICENSE); that repository has no NOTICE file |
| `standardwebhooks` | 1.1.1 | MIT | resolved: the npm registry `gitHead` `b4d2c14fc5b4ccff3ff271e3b087dff812254c59` has `libraries/LICENSE` (MIT, Copyright (c) 2023 Svix), stored verbatim in [licenses/standardwebhooks-libraries-LICENSE](licenses/standardwebhooks-libraries-LICENSE). The Apache-2.0 LICENSE at that repository's root covers the repository/specification, not this npm package, which is not licensed as Apache-2.0 |
| `data-uri-to-buffer` | 4.0.1 | MIT (per `package.json`) | **no license file** in `TooTallNate/node-data-uri-to-buffer` (README only); copyright holder per `package.json` author is Nathan Rajlich; no copyright line has been invented |
| `proxy-agent-negotiate` | 1.1.0 | MIT (per `package.json`) | **no license file** in `TooTallNate/proxy-agents` (root or `packages/negotiate`); author per `package.json` is Nathan Rajlich; no copyright line invented |

The last two rows (`data-uri-to-buffer`, `proxy-agent-negotiate`) are open: both published packages declare MIT and name Nathan Rajlich as author in their `package.json`, and the published tarballs and upstream repositories contain no LICENSE file, so no license text or copyright line exists to preserve. Their actual `package.json`/README declarations are all that can be retained; nothing has been invented, and only the author can supply a license file.

Only this project's own code and owned Pi extensions are under this project's MIT license ([LICENSE](LICENSE)); everything above is third-party and keeps its own terms. This source tree does not redistribute `node_modules`; the installer downloads Node and Pi dependencies, and retains every notice provided with them.

## npm dependencies of Pi

`runtime/pi/package-lock.json` pins the installed dependency tree. License families present in the lock (package counts excluding the root): MIT (59), Apache-2.0 (38), BSD-3-Clause (13), ISC (7), BlueOak-1.0.0 (2), Unlicense (1), 0BSD (1). Apache-2.0 components require preserving their LICENSE and any NOTICE files; the installer does so.

## Where the actual texts live

The installer copies the real upstream license and notice files (not summaries) into the installed plug-in:

- `<target>/runtime/pi/third-party-notices/index.json` — index of everything copied, with a sha256 per file.
- `<target>/runtime/pi/third-party-notices/npm/<name>@<version>/` — each npm package's LICENSE/NOTICE files, including notice files nested inside the package (for example vendored components).
- `<target>/runtime/pi/third-party-notices/node/LICENSE` (and `npm-LICENSE`) — Node.js and its bundled npm.

`install.py --check` re-hashes every file the index references and fails if one is missing or changed.

Some packages ship only a license identifier in `package.json` rather than a license file; the index records what was found. If you redistribute an installed tree, ship the `third-party-notices/` directory with it.

## Knowledge pack sources

`nuke_codex_panel/knowledge/` is original paraphrased guidance citing Foundry Nuke 17.1 documentation and Brinkmann, *The Art and Science of Digital Compositing* (2nd ed.). No book text, PDF or Foundry documentation is redistributed.

## Trademarks

Nuke is a trademark of Foundry. Pi, Node.js and other names belong to their owners; their use here is descriptive and implies no endorsement.
