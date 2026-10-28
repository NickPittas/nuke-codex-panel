"""Nuke MCP sidecar wiring shared by the non-Codex harnesses."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Env var the sidecar reads to pin one Nuke session's discovery record.
BRIDGE_FILE_ENV = "NUKE_CODEX_BRIDGE_FILE"

NUKE_SYSTEM_PROMPT = (
    "You are embedded in Foundry Nuke through the Nuke agent panel. "
    "Treat attached screenshots as current compositing context. Use the Nuke "
    "MCP tools to inspect the current comp, capture fresh visual evidence, and "
    "execute Python. execute_python is the primary unrestricted Nuke control "
    "surface; prefer concise Python over inventing many narrow actions, but use native "
    "nodes and knobs rather than expressions standing in for them. Before building or "
    "organizing any node graph, call get_compositing_guidance(..., section=\"workflow\") for "
    "fundamentals/graph-conventions and fundamentals/quality-safeguards; before keying, also "
    "fundamentals/keying-conventions. This applies even to familiar nodes. For unfamiliar "
    "operations use search_compositing_knowledge or get_node_reference; node references are static 17.1 "
    "docs, so confirm availability in the installed Nuke. Verify visual changes with a "
    "fresh Viewer or Node Graph screenshot."
)


def _sidecar_python() -> str:
    return shutil.which("python3") or "/usr/bin/python3"


def server_command() -> list[str]:
    """Stdio command line for the Nuke MCP sidecar."""
    return [_sidecar_python(), "-m", "nuke_codex_panel.mcp_server.server"]


def server_environment(bridge_path: str | None = None) -> dict[str, str]:
    """Sidecar env. PYTHONPATH is the code package root, never the project cwd.

    Without ``bridge_path`` the sidecar auto-discovers the newest live Nuke
    session; with it the sidecar is pinned to that exact discovery record.
    """
    env = {"PYTHONPATH": str(PROJECT_ROOT)}
    if bridge_path:
        env[BRIDGE_FILE_ENV] = str(bridge_path)
    return env


def merge_agent_mcp_config(agent_dir: Path) -> None:
    """Add or refresh the nuke server entry in a pi/omp-style agent mcp.json.

    The file is the user's persistent global config, so it never carries a
    per-instance bridge pin; pi/omp sidecars inherit the pin from the agent
    process environment instead (see ``JsonlProcessClient.launch_environment``).
    """
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


def write_claude_mcp_config(path: Path, bridge_path: str | None = None) -> Path:
    """Write a Claude Code --mcp-config file with the nuke stdio server."""
    config = {
        "mcpServers": {
            "nuke": {
                "command": server_command()[0],
                "args": server_command()[1:],
                "env": server_environment(bridge_path),
            }
        }
    }
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def write_opencode_config(path: Path, bridge_path: str | None = None) -> Path:
    """Write an OPENCODE_CONFIG overlay with the nuke MCP server and open permissions."""
    config = {
        "$schema": "https://opencode.ai/config.json",
        "permission": {"*": "allow"},
        "mcp": {
            "nuke": {
                "type": "local",
                "command": server_command(),
                "environment": server_environment(bridge_path),
                "enabled": True,
                # Nuke-side approval can take minutes; the default MCP timeout is far shorter.
                "timeout": 300000,
            }
        },
    }
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def runtime_config_path(name: str, bridge_path: str | None = None) -> Path:
    """Per-Nuke-session config file, so pinned configs never clobber each other."""
    from ..bridge.server import runtime_directory

    directory = runtime_directory() / "harness-config"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    prefix = Path(bridge_path).stem if bridge_path else "unpinned"
    return directory / ("%s-%s" % (prefix, name))
