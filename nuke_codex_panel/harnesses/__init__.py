"""Agent harness clients: one class per CLI agent, uniform interface."""

from __future__ import annotations

from pathlib import Path

from .base import HarnessClient, JsonlProcessClient, resolve_binary
from .claude import ClaudeClient
from .codex import CodexClient
from .opencode import OpencodeClient
from .pi_rpc import PiRpcClient, _agent_dir


def _make_pi(binary_name: str):
    def factory(cwd: str, parent=None, bridge_path: str | None = None):
        return PiRpcClient(cwd, binary_name, _agent_dir(binary_name), parent, bridge_path)

    return factory


HARNESSES = [
    {"key": "codex", "label": "Codex", "factory": CodexClient},
    {"key": "claude", "label": "Claude", "factory": ClaudeClient},
    {"key": "pi", "label": "Pi", "factory": _make_pi("pi")},
    {"key": "omp", "label": "OMP", "factory": _make_pi("omp")},
    {"key": "opencode", "label": "Opencode", "factory": OpencodeClient},
]


def create_client(key: str, cwd: str, parent=None, bridge_path: str | None = None) -> HarnessClient:
    for entry in HARNESSES:
        if entry["key"] == key:
            return entry["factory"](cwd, parent, bridge_path)
    raise KeyError("Unknown harness: %s" % key)


def harness_names() -> list[str]:
    return [entry["key"] for entry in HARNESSES]


def harness_label(key: str) -> str:
    for entry in HARNESSES:
        if entry["key"] == key:
            return entry["label"]
    return key


def resolve_harness_binary(key: str) -> str | None:
    """Probe where a harness binary currently resolves (no process started)."""
    client = create_client(key, "/tmp")
    try:
        return client.resolve_program()
    finally:
        client.deleteLater()


create_harness = create_client


__all__ = [
    "HarnessClient",
    "JsonlProcessClient",
    "resolve_binary",
    "HARNESSES",
    "create_client",
    "create_harness",
    "harness_names",
    "harness_label",
    "resolve_harness_binary",
]
