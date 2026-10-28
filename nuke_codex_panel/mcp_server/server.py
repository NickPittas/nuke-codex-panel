"""Dependency-free MCP stdio server: forwards tools into the active Nuke GUI and serves offline compositing knowledge."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import socket
import sys
import tempfile

from nuke_codex_panel.knowledge import library as knowledge


SERVER_INFO = {"name": "nuke-codex-panel", "version": "0.1.0.dev0"}


TOOLS = [
    {
        "name": "execute_python",
        "description": (
            "Execute unrestricted Python inside the active Foundry Nuke GUI on its main "
            "thread. The namespace persists between calls and already contains `nuke`. "
            "Use this as the primary way to inspect or manipulate Nuke. Prefer native nodes "
            "and knobs over expressions or scripted stand-ins (e.g. Roto for shapes, "
            "CheckerBoard for checkers). Before building or organizing any node graph, call "
            "get_compositing_guidance(..., section=\"workflow\") for fundamentals/graph-conventions "
            "and fundamentals/quality-safeguards; before keying, also fundamentals/keying-conventions "
            "(even for familiar nodes). For unfamiliar operations call "
            "search_compositing_knowledge / get_node_reference."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["code"],
            "properties": {
                "code": {"type": "string", "description": "Complete Python source to execute."},
                "undo": {"type": "boolean", "default": True},
                "label": {"type": "string", "default": "Codex Python"},
            },
        },
    },
    {
        "name": "get_nuke_context",
        "description": "Read the current Nuke script, frame, selection, Viewers, and node graph.",
        "inputSchema": {
            "type": "object",
            "properties": {"include_nodes": {"type": "boolean", "default": True}},
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "capture_nuke_screenshot",
        "description": (
            "Capture the visible Nuke Viewer, Node Graph, or full interface and return the "
            "PNG as visual context."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string", "enum": ["viewer", "nodegraph", "interface"]}
            },
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "search_compositing_knowledge",
        "description": (
            "Search packaged compositing guidance (topics, fundamentals, native-node "
            "references). Returns compact matches only; fetch details with "
            "get_compositing_guidance or get_node_reference. Works without Nuke."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "maxLength": knowledge.QUERY_CAP},
                "limit": {"type": "integer", "minimum": 1, "maximum": 8, "default": 3},
                "kind": {"type": "string", "enum": list(knowledge.SEARCH_KINDS), "default": "all"},
            },
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "get_compositing_guidance",
        "description": (
            "Get one section of a guidance document by ID (overview, a topics/* or "
            "fundamentals/* ID) with citations. Capped; returns prerequisite IDs, not text."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["topic_id"],
            "properties": {
                "topic_id": {"type": "string"},
                "section": {"type": "string", "enum": list(knowledge.GUIDANCE_SECTIONS), "default": "overview"},
            },
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "get_node_reference",
        "description": (
            "Get one section of a curated native-node reference by node name, ID or alias. "
            "Static Nuke 17.1 documentation facts; runtime_verified is false, so confirm "
            "availability in the installed Nuke."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["node"],
            "properties": {
                "node": {"type": "string"},
                "section": {"type": "string", "enum": list(knowledge.NODE_SECTIONS), "default": "overview"},
            },
        },
        "annotations": {"readOnlyHint": True},
    },
]

KNOWLEDGE_TOOLS = frozenset(
    {"search_compositing_knowledge", "get_compositing_guidance", "get_node_reference"}
)


def _runtime_directory() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return Path(base) / ("nuke-codex-panel-%s" % os.getuid())


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _discover_bridge() -> dict:
    explicit = os.environ.get("NUKE_CODEX_BRIDGE_FILE")
    if explicit:
        path = Path(explicit)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if _process_alive(int(record["pid"])):
                return record
        except Exception as exc:
            raise RuntimeError("Configured Nuke bridge is unavailable: %s" % exc) from exc
        raise RuntimeError("Configured Nuke bridge process is not active")
    directory = _runtime_directory()
    candidates = sorted(directory.glob("session-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if _process_alive(int(record["pid"])):
                return record
        except Exception:
            continue
    raise RuntimeError(
        "No active Nuke Codex bridge was found. Start Nuke with the Nuke Codex Panel "
        "integration installed; the bridge starts with Nuke."
    )


def _bridge_call(method: str, params: dict) -> dict:
    record = _discover_bridge()
    request = {
        "token": record["token"],
        "method": method,
        "params": params,
    }
    with socket.create_connection((record["host"], int(record["port"])), timeout=10) as connection:
        connection.settimeout(300)
        connection.sendall((json.dumps(request) + "\n").encode("utf-8"))
        chunks = b""
        while b"\n" not in chunks:
            part = connection.recv(65536)
            if not part:
                break
            chunks += part
    if not chunks:
        raise RuntimeError("Nuke bridge closed without a response")
    return json.loads(chunks.split(b"\n", 1)[0].decode("utf-8"))


def _knowledge_result(name: str, arguments: dict) -> dict:
    handlers = {
        "search_compositing_knowledge": lambda a: knowledge.search_compositing_knowledge(
            a.get("query"), a.get("limit", 3), a.get("kind", "all")
        ),
        "get_compositing_guidance": lambda a: knowledge.get_compositing_guidance(
            a.get("topic_id"), a.get("section", "overview")
        ),
        "get_node_reference": lambda a: knowledge.get_node_reference(
            a.get("node"), a.get("section", "overview")
        ),
    }
    try:
        result = handlers[name](arguments)
    except (knowledge.KnowledgeError, knowledge.CorpusError) as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": False}


def _tool_result(name: str, arguments: dict) -> dict:
    if name in KNOWLEDGE_TOOLS:
        return _knowledge_result(name, arguments)
    method = {
        "execute_python": "execute_python",
        "get_nuke_context": "get_context",
        "capture_nuke_screenshot": "capture_screenshot",
    }.get(name)
    if method is None:
        return {"content": [{"type": "text", "text": "Unknown tool: %s" % name}], "isError": True}
    try:
        result = _bridge_call(method, arguments)
    except Exception as exc:
        result = {"success": False, "error": "%s: %s" % (type(exc).__name__, exc)}

    content = [{"type": "text", "text": json.dumps(result, indent=2)}]
    if name == "capture_nuke_screenshot" and result.get("success") and result.get("path"):
        image_path = Path(result["path"])
        content.append(
            {
                "type": "image",
                "data": base64.b64encode(image_path.read_bytes()).decode("ascii"),
                "mimeType": "image/png",
            }
        )
    return {"content": content, "isError": not bool(result.get("success"))}


def _response(request: dict):
    method = request.get("method")
    params = request.get("params") or {}
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion", "2025-11-25"),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        return _tool_result(str(params.get("name", "")), params.get("arguments") or {})
    raise RuntimeError("Method not found: %s" % method)


def main():
    for raw_line in sys.stdin.buffer:
        request = None
        try:
            request = json.loads(raw_line.decode("utf-8"))
            if "id" not in request:
                continue
            result = _response(request)
            message = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except Exception as exc:
            request_id = request.get("id") if isinstance(request, dict) else None
            message = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": "%s: %s" % (type(exc).__name__, exc)},
            }
        sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
