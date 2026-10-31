# Installing Nuke Pi

Nuke Pi (repository/package `nuke-codex-panel`) installs its own private, pinned Node.js 26.12.0 and official Pi 1.4.0. Nothing global is used or modified: no system Node, global Pi, `PATH` lookup, `~/.npmrc` or `~/.pi`.

## Platforms

| Platform | Manifest key | Native verification |
|----------|--------------|---------------------|
| Linux x64 | `linux-x64` | **verified** (project workstation, Nuke 17.1) |
| Windows x64 | `win-x64` | implemented, **not natively verified** |
| macOS Intel | `darwin-x64` | implemented, **not natively verified** |
| macOS Apple Silicon | `darwin-arm64` | implemented, **not natively verified** |

## Prerequisites

- Foundry Nuke 17+ (PySide6 ships with it).
- A **standalone** Python 3.11+ to run `install.py` (Linux/macOS `python3`; Windows `py -3`). Not Nuke's own Python: Nuke's interpreter is the Nuke binary and cannot host the MCP server. The installer records the standalone interpreter it ran under in an install receipt, and the panel launches the MCP sidecar with that recorded interpreter.
- Internet access to `nodejs.org` and `registry.npmjs.org` during install only.
- Install from the **source tree or an sdist, not a wheel**. The official product distribution is source + `install.py`; the pinned Node/Pi runtime assets are not in a wheel, so a bare `pip install` of the wheel is not a complete installation. Run `install.py` from the unpacked source or sdist. The installed plug-in directory is self-contained.

## Install

```bash
# Linux / macOS
python3 install.py --target ~/.nuke/nuke-codex-panel --nuke-dir ~/.nuke
```

```bat
:: Windows (cmd)
py -3 install.py --target "%USERPROFILE%\.nuke\nuke-codex-panel" --nuke-dir "%USERPROFILE%\.nuke"
```

| Option | Meaning |
|--------|---------|
| `--target PATH` | plug-in install location (default `~/.nuke/nuke-codex-panel`) |
| `--nuke-dir PATH` | Nuke user directory with `init.py`/`menu.py` (default `~/.nuke`) |
| `--no-register` | do not touch `init.py`/`menu.py` (temporary installs) |
| `--check` | read-only verification of an installed runtime (hashes, Node, licenses, recorded Python) and, unless `--no-register` is also given, the `init.py`/`menu.py` registration; no network, no changes |

Exit codes: 0 success, 1 failure, 2 usage error.

What it does:

1. Downloads the official Node archive for the platform over TLS and verifies its sha256 against `runtime/pi/manifest.json`.
2. With that private Node, runs `npm ci --ignore-scripts` against `package-lock.json` (isolated config and cache, no ambient auth); npm checks each package's lock integrity hash.
3. Stages the owned extensions and runtime files, and copies upstream licenses and notices, including nested notice files, to `runtime/pi/third-party-notices/` (index `index.json` with a sha256 per file).
4. Activates atomically. A failed install leaves any previous working install and your private Pi accounts untouched. Provenance is recorded in `runtime/pi/install-state.json`.
5. Only after the install verifies, registers (idempotently) a managed block in `init.py` and `menu.py`, delimited by `# >>> Nuke Codex Panel >>>` and `# <<< Nuke Codex Panel <<<`. Unrelated content is preserved; a one-time backup `<file>.nuke-codex-panel.bak-<UTC timestamp>` is made for each changed file. Existing unrelated targets or backups are refused rather than overwritten.

The registration is equivalent to:

```python
# init.py
nuke.pluginAddPath("./nuke-codex-panel")

# menu.py
import nuke_codex_panel.menu
```

`install.py` is also copied into the target, so `python3 <target>/install.py --target <target> --check` re-verifies it later.

Installing in place from a checkout (`--target` equal to the checkout) is supported and does not recursively copy or delete your changes.

## First run

Restart Nuke and open **Pane > Nuke Pi**. Open **Pi accounts…** and sign in (API key or subscription/OAuth). Credentials are stored only in the private Pi store outside the install directory. Then open **Manage models…**, check the models to keep and pick a default.

## Verify

```bash
python3 install.py --target ~/.nuke/nuke-codex-panel --check
```

Checks that the Node binary and Pi package exist at the pinned versions, that package, lock and credential-environment hashes match `manifest.json` (schema 2, per-platform pins), that every notice file referenced by `third-party-notices/index.json` exists and matches its recorded sha256, that the recorded sidecar Python still exists, and that registration is in place. Like the panel's per-launch check, it detects a missing or mismatched install, not tampering by someone who can write to the directory.

## Uninstall

Remove the managed block from `init.py`/`menu.py` and delete the target folder. Private Pi accounts, model preferences and chats live outside the install and are kept.

## Moving from the old plug-ins

Remove `import nuke_mcp_addon`/`nuke_mcp` path lines if present (leave the old folder on disk). Codex, Claude, OMP and opencode backends are no longer supported; their past chat metadata is kept readable but never launched.

## Notes for agents installing this

Do not edit unrelated `init.py`/`menu.py` content, do not copy or read existing Pi/auth files, do not install Node or Pi by hand, and do not register the MCP server globally. Use `--no-register` for a temporary install.
