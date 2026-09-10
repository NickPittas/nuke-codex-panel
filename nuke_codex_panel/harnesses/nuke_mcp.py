"""Nuke MCP sidecar wiring shared by the non-Codex harnesses."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

PROJECT_ROOT = Path(__file__).resolve().parents[2]

NUKE_SYSTEM_PROMPT = (
    "You are embedded in Foundry Nuke through the Nuke agent panel. "
    "Treat attached screenshots as current compositing context. Use the Nuke "
    "MCP tools to inspect the current comp, capture fresh visual evidence, and "
    "execute Python. execute_python is the primary unrestricted Nuke control "
    "surface; prefer concise Python over inventing many narrow actions. Verify "
    "visual changes with a fresh Viewer or Node Graph screenshot."
)


def _sidecar_python() -> str:
    return shutil.which("python3") or "/usr/bin/python3"


def server_command() -> list[str]:
    """Stdio command line for the Nuke MCP sidecar."""
    return [_sidecar_python(), "-m", "nuke_codex_panel.mcp_server.server"]


def server_environment() -> dict[str, str]:
    # The bridge file is intentionally not pinned here: the sidecar
    # auto-discovers the newest live Nuke session in the runtime directory.
    return {"PYTHONPATH": str(PROJECT_ROOT)}


def merge_agent_mcp_config(agent_dir: Path) -> None:
    """Add or refresh the nuke server entry in a pi/omp-style agent mcp.json."""
    agent_dir.mkdir(parents=True, exist_ok=True)
    path = agent_dir / "mcp.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        config = {}
    servers = config.setdefault("mcpServers", {})
    servers["nuke"] = {
        "command": server_command()[0],
        "args": server_command()[1:],
        "env": server_environment(),
    }
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def write_claude_mcp_config(path: Path) -> Path:
    """Write a Claude Code --mcp-config file with the nuke stdio server."""
    config = {
        "mcpServers": {
            "nuke": {
                "command": server_command()[0],
                "args": server_command()[1:],
                "env": server_environment(),
            }
        }
    }
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def write_opencode_config(path: Path) -> Path:
    """Write an OPENCODE_CONFIG overlay with the nuke MCP server and open permissions."""
    config = {
        "$schema": "https://opencode.ai/config.json",
        "permission": {"*": "allow"},
        "mcp": {
            "nuke": {
                "type": "local",
                "command": server_command(),
                "environment": server_environment(),
                "enabled": True,
            }
        },
    }
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def runtime_config_dir() -> Path:
    from ..bridge.server import runtime_directory

    directory = runtime_directory() / "harness-config"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return directory
