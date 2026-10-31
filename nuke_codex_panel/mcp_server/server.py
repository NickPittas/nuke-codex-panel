"""Dependency-free MCP stdio server: forwards tools into the active Nuke GUI and serves offline compositing knowledge."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path
import queue
import socket
import sys
import threading
import time
import uuid

from nuke_codex_panel import process_ownership, runtime_paths
from nuke_codex_panel.knowledge import library as knowledge
from nuke_codex_panel.knowledge import api_docs
from nuke_codex_panel.knowledge.api_docs import ApiDocumentation
from nuke_codex_panel.tools import guided


SERVER_INFO = {"name": "nuke-codex-panel", "version": "0.1.0.dev0"}

# Stable for this sidecar process: the bridge keys per-client evidence by it.
CLIENT_ID = uuid.uuid4().hex

# The harness client that owns this sidecar (HarnessClient exports it); the bridge pauses/revokes
# requests by it. Empty for external clients, which no control can affect.
CONTROL_ID = os.environ.get("NUKE_CODEX_CONTROL_ID", "").strip()[:64]


def _control_epoch():
    """This process's lease number (NUKE_CODEX_CONTROL_EPOCH), or None when the harness set none."""
    try:
        return int(os.environ["NUKE_CODEX_CONTROL_EPOCH"])
    except (KeyError, ValueError):
        return None


CONTROL_EPOCH = _control_epoch()

# error_codes with which the bridge refuses a request of an interrupted run; mirrors bridge.control.
CONTROL_ERROR_CODES = frozenset(
    {"control_paused", "control_stale", "control_mismatch", "control_closed", "control_retired"}
)

API_QUERY_CAP = api_docs.MAX_QUERY_CHARS
API_SEARCH_LIMIT_MAX = api_docs.MAX_LIMIT
API_SEARCH_LIMIT_DEFAULT = api_docs.DEFAULT_LIMIT

RESPONSE_TIMEOUT_SECONDS = 300
# A capture is answered when its render/screenshot finishes, however long that takes. It
# ends in an image or an explicit error, never a timeout that falls back to old pixels.
NO_DEADLINE_METHODS = frozenset({"capture_screenshot", "execute_action"})


TOOLS = [
    {
        "name": "execute_python",
        "description": (
            "Execute unrestricted Python inside the active Foundry Nuke GUI on its main "
            "thread. The namespace persists between calls and already contains `nuke`. "
            "This is the normal way to inspect or manipulate Nuke: create, connect, delete and "
            "configure nodes, run trackers, paint, roto, keying, projection, render, anything "
            "the Nuke Python API can do. Nothing needs to be read, inspected or documented first; "
            "the whole script is compiled before anything runs. Syntax errors run nothing. "
            "A runtime error reports phase, what already executed, the failing location and the "
            "partial graph changes (they are not undone or replayed). Results report graph_changed, "
            "added/removed/modified nodes and node errors. Prefer native nodes and knobs over "
            "expressions or scripted stand-ins (e.g. Roto for shapes, CheckerBoard for checkers). "
            "Optional on demand references: search_compositing_knowledge / get_compositing_guidance "
            "(section='workflow' holds exact native Python for Viewer sampling, tracking, roto/paint, "
            "warping, calibration, analysis, baking, keying). When a result reports api_errors, "
            "each record carries runtime_evidence read from the live receiver in the running Nuke; "
            "search_nuke_api_docs/read_nuke_api_doc are optional. Nothing is held back by an error."
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
        "description": (
            "Read the current Nuke script: frame, project settings, selection, Viewers and the "
            "active Viewer's active input, and (include_nodes=true, the default) every node in "
            "the root graph and inside nested groups with its enclosing group and indexed "
            "input connections."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"include_nodes": {"type": "boolean", "default": True}},
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "capture_nuke_screenshot",
        "description": (
            "Capture visual evidence as a PNG plus JSON metadata. target='viewer' synchronously "
            "renders the existing Viewer at `frame` (default: the current frame) and returns "
            "that frame's actual pixels; metadata states the requested and rendered frame, "
            "Viewer, active input, and image size. It returns only when the render has finished, "
            "which can take long on a heavy comp. target='nodegraph' captures the root Node "
            "Graph: scope='all' (default) frames every root node; scope='visible' is only the "
            "current view. Nested group interiors are not drawn "
            "in it; use get_nuke_context for them. target='interface' first renders the active "
            "Viewer synchronously at the current frame (see its viewer_render_* metadata), then "
            "captures the Nuke window as UI context; it accepts no `frame`. "
            "target='viewer' can also frame the real Viewer first: `zoom` (percent, or 'fit') with an "
            "optional `center` [x, y], or `region` [x0, y0, x1, y1] (source-image pixels, origin "
            "bottom-left; excludes zoom/center). The image is the Viewer's viewport render, never a "
            "crop: 100% is 1:1 source detail, a region is fitted to the viewport. Framing persists as "
            "the Viewer's state; a region does not follow tracking across frames. Metadata reports "
            "viewer_zoom_percent (read back) and the requested centre/region. "
            "Every capture is delivered to you and shown to the user in the panel chat."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string", "enum": ["viewer", "nodegraph", "interface"]},
                "frame": {
                    "type": "integer",
                    "description": "Frame to render; target='viewer' only. Default: the current frame.",
                },
                "zoom": {
                    "type": ["number", "string"],
                    "description": "target='viewer' only: positive Viewer zoom percent, or 'fit'.",
                },
                "center": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "target='viewer' only: [x, y] source-image pixel to centre (bottom-left origin); with no zoom keeps the current zoom.",
                },
                "region": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "target='viewer' only: [x0, y0, x1, y1] source pixels to frame (fitted to the viewport); exclusive with zoom/center.",
                },
                "scope": {
                    "type": "string",
                    "enum": ["all", "visible"],
                    "default": "all",
                    "description": "target='nodegraph' only: frame every root node, or the visible view.",
                },
            },
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "search_compositing_knowledge",
        "description": (
            "Search packaged compositing guidance, targeted native-Python operational skills "
            "(Viewer, tracking, roto/paint, warping, calibration, analysis, training, baking), and "
            "static node references. Not live Nuke state. Returns compact matches; fetch workflow "
            "with get_compositing_guidance or controls with get_node_reference. Works without Nuke."
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
            "fundamentals/* ID) with citations. Use section='workflow' for operational Python "
            "recipes and run steps. Capped; prerequisite IDs are returned without their text."
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
            "Conceptual, static Nuke 17.1 artist documentation (runtime_verified is false): it is NOT "
            "the installed Nuke's knob truth, availability or a task instruction. Use "
            "nuke_action inspect for the live node's real knobs, enum labels and ports."
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
    {
        "name": "search_nuke_api_docs",
        "description": (
            "Search the installed Nuke's own Python SDK documentation (API symbols, node and knob "
            "documentation). A Python API reference, optional and on demand: nothing is gated on it. "
            "Returns compact matches with opaque ids; read one with read_nuke_api_doc. Useful when a "
            "Python run's api_errors runtime_evidence does not answer your question."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "maxLength": API_QUERY_CAP},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": API_SEARCH_LIMIT_MAX,
                    "default": API_SEARCH_LIMIT_DEFAULT,
                },
            },
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "read_nuke_api_doc",
        "description": (
            "Read one installed-Nuke API documentation entry by the id search_nuke_api_docs returned "
            "(signatures, parameters, knob tables). Optional reference; nothing is gated on it."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["doc_id"],
            "properties": {"doc_id": {"type": "string"}},
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "nuke_action",
        "description": guided.ACTION_DESCRIPTION,
        "inputSchema": guided.ACTION_INPUT_SCHEMA,
    },
    {
        "name": "nuke_workflow",
        "description": guided.WORKFLOW_DESCRIPTION,
        "inputSchema": guided.WORKFLOW_INPUT_SCHEMA,
    },
]

KNOWLEDGE_TOOLS = frozenset(
    {"search_compositing_knowledge", "get_compositing_guidance", "get_node_reference"}
)

API_DOC_TOOLS = frozenset({"search_nuke_api_docs", "read_nuke_api_doc"})

MUTATION_REMINDER = (
    "The graph changed. get_nuke_context and a nodegraph or Viewer capture show the result when you want to "
    "see it; nothing is required before your next Python."
)

UNKNOWN_MUTATION_REMINDER = (
    "The server could not determine whether this call changed the graph; treat it as possibly changed. " + MUTATION_REMINDER
)

ERROR_REMINDER = """ERROR — THIS OPERATION IS NOT VERIFIED

Read the error details above. Do not assume the operation was rolled back.
Inspect the current state before retrying, and address the reported cause.
Do not repeat the same failing command unchanged."""


def _discover_bridge() -> dict:
    explicit = os.environ.get("NUKE_CODEX_BRIDGE_FILE")
    if explicit:
        path = Path(explicit)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if process_ownership.pid_running(int(record["pid"])):
                return record
        except Exception as exc:
            raise RuntimeError("Configured Nuke bridge is unavailable: %s" % exc) from exc
        raise RuntimeError("Configured Nuke bridge process is not active")
    try:
        directory = runtime_paths.private_runtime_directory(create=False)
    except runtime_paths.RuntimePathMissing:
        directory = None
    except runtime_paths.RuntimePathError as exc:
        raise RuntimeError("The Nuke Codex runtime directory is not safe to use: %s" % exc) from exc
    candidates = []
    if directory is not None:
        candidates = sorted(directory.glob("session-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if process_ownership.pid_running(int(record["pid"])):
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
        "client_id": CLIENT_ID,
        "control_id": CONTROL_ID,
        "control_epoch": CONTROL_EPOCH,
        # CLOCK_MONOTONIC when this tool call's request line reached this process (see _read_requests).
        "received_ns": _request_stamp if _request_stamp is not None else time.monotonic_ns(),
        "method": method,
        "params": params,
    }
    with socket.create_connection((record["host"], int(record["port"])), timeout=10) as connection:
        connection.settimeout(None if method in NO_DEADLINE_METHODS else RESPONSE_TIMEOUT_SECONDS)
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


def _confirm_delivery(tokens: list) -> str | None:
    """Tell the bridge the evidence behind ``tokens`` is being handed to the model.

    Returns the problem text if the bridge did not record it, else None.
    """
    try:
        reply = _bridge_call("confirm_delivery", {"tokens": tokens})
    except Exception as exc:
        return "%s: %s" % (type(exc).__name__, exc)
    if not isinstance(reply, dict):
        return "malformed bridge response: %r" % (reply,)
    if not reply.get("success"):
        return str(reply.get("error") or reply)
    return None


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


_API_DOCUMENTATION: dict[str, ApiDocumentation] = {}


def _documentation(root: str) -> ApiDocumentation:
    """One index per documentation root for this sidecar process (built lazily, outside Nuke)."""
    documentation = _API_DOCUMENTATION.get(root)
    if documentation is None:
        documentation = _API_DOCUMENTATION[root] = ApiDocumentation(root)
    return documentation


def _api_docs_failure(message: str, source: dict | None = None) -> dict:
    """Explicit failure: what failed and where the documentation was looked up."""
    payload = {"success": False, "error": message}
    if source:
        payload["source"] = source
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": True}


def _api_docs_result(name: str, arguments: dict) -> dict:
    """Search or read the installed Nuke's API documentation, here in the sidecar (never on Nuke's GUI thread).

    The bridge supplies only the installed Documentation location. Nothing is gated on the result.
    """
    kind = "search" if name == "search_nuke_api_docs" else "read"
    if kind == "search":
        query = arguments.get("query")
        limit = arguments.get("limit", API_SEARCH_LIMIT_DEFAULT)
        if not isinstance(query, str) or not query.strip():
            return _api_docs_failure("query must be a non-empty string")
        if len(query) > API_QUERY_CAP:
            return _api_docs_failure("query is longer than %d characters" % API_QUERY_CAP)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= API_SEARCH_LIMIT_MAX:
            return _api_docs_failure("limit must be an integer from 1 to %d" % API_SEARCH_LIMIT_MAX)
    else:
        doc_id = arguments.get("doc_id")
        if not isinstance(doc_id, str) or not doc_id.strip():
            return _api_docs_failure("doc_id must be a non-empty string returned by search_nuke_api_docs")

    try:
        begun = _bridge_call("api_docs_begin", {"kind": kind})
    except Exception as exc:
        return _api_docs_failure(
            "Cannot locate the installed Nuke documentation because the Nuke bridge is unavailable: %s: %s"
            % (type(exc).__name__, exc)
        )
    if not isinstance(begun, dict) or not begun.get("success"):
        problem = begun.get("error") if isinstance(begun, dict) else begun
        return _api_docs_failure("Cannot locate the installed Nuke documentation: %s" % (problem,))
    root = begun.get("documentation_root")
    source = {"documentation_root": root, "nuke_version": begun.get("nuke_version")}
    if not isinstance(root, str):
        return _api_docs_failure("The Nuke bridge returned malformed documentation metadata", source)
    if begun.get("documentation_available") is False:
        return _api_docs_failure("The installed Nuke Documentation directory does not exist: %s" % root, source)

    try:
        documentation = _documentation(root)
        result = documentation.search(query, limit) if kind == "search" else documentation.read(doc_id)
    except Exception as exc:
        return _api_docs_failure("%s: %s" % (type(exc).__name__, exc), source)
    if not isinstance(result, dict) or not result.get("success"):
        problem = result.get("error") if isinstance(result, dict) else result
        return _api_docs_failure("The documentation lookup failed: %s" % (problem,), source)
    payload = {**result, "installed_documentation": source}
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}


def _announce_images(name: str, attached: list) -> None:
    """Tell the panel which images were really handed to the model (same bytes, never a recapture).

    Best effort: the panel preview never changes or fails the tool result.
    """
    if not attached:
        return
    try:
        _bridge_call(
            "images_delivered",
            {"images": [{**entry, "delivery_id": uuid.uuid4().hex, "tool": name} for entry in attached]},
        )
    except Exception:
        pass


def _tool_result(name: str, arguments: dict) -> dict:
    if name in KNOWLEDGE_TOOLS:
        return _knowledge_result(name, arguments)
    if name in API_DOC_TOOLS:
        return _api_docs_result(name, arguments)
    method = {
        "execute_python": "execute_python",
        "nuke_action": "execute_action",
        "nuke_workflow": "workflow",
        "get_nuke_context": "get_context",
        "capture_nuke_screenshot": "capture_screenshot",
    }.get(name)
    if method is None:
        return {"content": [{"type": "text", "text": "Unknown tool: %s" % name}], "isError": True}
    transport_failed = False
    try:
        result = _bridge_call(method, arguments)
    except Exception as exc:
        transport_failed = True
        result = {"success": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    if not isinstance(result, dict):
        result = {"success": False, "error": "Malformed bridge response: %r" % (result,)}

    # Private bridge-to-sidecar handshake; the model never sees the tokens.
    tokens = [token for token in [result.pop("delivery_token", None)] if token is not None]
    action_tokens = result.pop("delivery_tokens", None) or []
    images = result.pop("images", None) or []
    if result.get("error_code") in CONTROL_ERROR_CODES:
        # Refused before anything ran because the user interrupted this run: no mutation or retry
        # reminder applies, and the refusal names the only correct behavior.
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}], "isError": True}
    content = [{"type": "text", "text": json.dumps(result, indent=2)}]
    if name == "capture_nuke_screenshot" and result.get("success") and result.get("path"):
        images = [{"path": result["path"]}]
        action_tokens = []
    delivered = list(tokens)
    attached = []
    if images:
        delivered = []
        unreadable = []
        for position, image in enumerate(images):
            try:
                raw = Path(image["path"]).read_bytes()
            except Exception as exc:
                unreadable.append({"path": image.get("path"), "error": "%s: %s" % (type(exc).__name__, exc)})
                continue
            content.append({"type": "image", "data": base64.b64encode(raw).decode("ascii"), "mimeType": "image/png"})
            attached.append(
                {"path": str(image["path"]), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
            )
            if position < len(action_tokens):
                delivered.append(action_tokens[position])
        if name == "capture_nuke_screenshot":
            # The single screenshot's own checkpoint token only counts if its image really attached.
            delivered = tokens if not unreadable else []
        if unreadable:
            # Failed image delivery: those tokens are dropped unconfirmed, so they can never unlock.
            if name == "capture_nuke_screenshot":
                result = {
                    "success": False,
                    "error": "Screenshot saved but could not be read: %s" % unreadable[0]["error"],
                    "path": unreadable[0]["path"],
                }
                content = [{"type": "text", "text": json.dumps(result, indent=2)}]
            else:
                result["success"] = False
                result["image_delivery_failed"] = unreadable
                content[0] = {"type": "text", "text": json.dumps(result, indent=2)}
    else:
        delivered = tokens + action_tokens

    failed = not bool(result.get("success"))
    if delivered and not failed:
        problem = _confirm_delivery(delivered)
        if problem is not None:
            failed = True
            content.append(
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": False,
                            "error": "The bridge could not confirm delivery of this result, so it does "
                            "not count as evidence: " + problem,
                        },
                        indent=2,
                    ),
                }
            )
    if name in ("execute_python", "nuke_action"):
        changed = result.get("graph_changed")
        if transport_failed or "graph_changed" not in result:
            # The call may have run (e.g. timeout after dispatch); state is not known.
            changed = None
        if changed is None:
            content.append({"type": "text", "text": UNKNOWN_MUTATION_REMINDER})
        elif changed:
            content.append({"type": "text", "text": MUTATION_REMINDER})
        if failed or result.get("node_errors"):
            content.append({"type": "text", "text": ERROR_REMINDER})
    elif failed:
        content.append({"type": "text", "text": ERROR_REMINDER})
    # Only images that really sit in this result reach the panel preview.
    _announce_images(name, attached)
    return {"content": content, "isError": failed}


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


# Seconds between liveness notifications while a tool call is pending. Native Pi drops a request
# after 60 s without a message; an echoed progress token resets that idle timer with no total cap.
PROGRESS_INTERVAL_SECONDS = 30.0
PROGRESS_MESSAGE = "Waiting for Nuke/tool completion"

# One lock for every stdout line so a keepalive never interleaves with a response.
_stdout_lock = threading.Lock()


def _emit(message: dict) -> None:
    line = json.dumps(message, separators=(",", ":")) + "\n"
    with _stdout_lock:
        sys.stdout.write(line)
        sys.stdout.flush()


def _progress_token(request: dict):
    """The client's progressToken for a tools/call (a string or integer, 0 included), else None."""
    params = request.get("params")
    meta = params.get("_meta") if isinstance(params, dict) else None
    token = meta.get("progressToken") if isinstance(meta, dict) else None
    if isinstance(token, bool) or not isinstance(token, (str, int)):
        return None
    return token


@contextlib.contextmanager
def _progress_keepalive(token):
    """Send transport-only progress notifications while the block runs; none after it exits.

    Never touches the tool itself: no cancel, timeout or replay. Without a token this is a no-op.
    """
    if token is None:
        yield
        return
    finished = threading.Event()

    def beat():
        progress = 0
        while not finished.wait(PROGRESS_INTERVAL_SECONDS):
            try:
                _emit(
                    {
                        "jsonrpc": "2.0",
                        "method": "notifications/progress",
                        "params": {"progressToken": token, "progress": progress, "message": PROGRESS_MESSAGE},
                    }
                )
            except (OSError, ValueError):
                return  # stdout is gone; the tool result still gets its own attempt
            progress += 1

    thread = threading.Thread(target=beat, name="mcp-progress", daemon=True)
    thread.start()
    try:
        yield
    finally:
        finished.set()
        thread.join()


def _read_requests(lines: queue.Queue) -> None:
    """Read stdin on its own thread and stamp each request the instant it arrives.

    The main loop may be blocked for minutes inside a bridge call. A request that was already sent
    when the user interrupted the run must still carry its *arrival* time, not the time the loop
    finally gets to it, or the bridge could not tell it from a request of the resumed run.
    """
    try:
        for raw_line in sys.stdin.buffer:
            lines.put((time.monotonic_ns(), raw_line))
    finally:
        lines.put(None)


def main():
    """Register as a panel-owned process (if the panel launched this sidecar), then serve until stdin closes.

    The registration comes first: a managed sidecar that the panel could not find again to retire
    must never serve a tool call, so failing to register ends the process with an explicit message.
    """
    if CONTROL_ID:
        try:
            process_ownership.register_current_process(CONTROL_ID, CONTROL_EPOCH, os.environ.get("NUKE_CODEX_BRIDGE_FILE"))
        except process_ownership.ProcessOwnershipError as exc:
            raise SystemExit("Nuke MCP sidecar cannot start: it could not register with the panel (%s)" % exc)
    try:
        _serve()
    finally:
        process_ownership.unregister_current_process()


def _serve():
    global _request_stamp
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=_read_requests, args=(lines,), name="mcp-stdin", daemon=True).start()
    while True:
        item = lines.get()
        if item is None:
            return
        _request_stamp, raw_line = item
        request = None
        try:
            request = json.loads(raw_line.decode("utf-8"))
            if "id" not in request:
                continue
            token = _progress_token(request) if request.get("method") == "tools/call" else None
            with _progress_keepalive(token):
                result = _response(request)
            message = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except Exception as exc:
            request_id = request.get("id") if isinstance(request, dict) else None
            message = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": "%s: %s" % (type(exc).__name__, exc)},
            }
        _emit(message)


if __name__ == "__main__":
    main()
