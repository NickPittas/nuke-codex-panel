"""Display formatting for tool calls in the chat (pure Python, no Qt imports).

Tool records keep the structured payload (arguments, result) the backend delivered; this module
turns it into labelled, readable blocks for the tool cards and into plain text for copying. Image
blocks only ever carry metadata here; the exact delivered images are separate chat rows.
"""

from __future__ import annotations

import json

from .chat_markdown import MarkdownStyle, code_block_html, escape

# Per-field cap for persisted/displayed payload text (same bound the transcript store applies).
MAX_FIELD_CHARS = 20000
_MAX_DEPTH = 8
_MAX_ITEMS = 200

# Argument keys whose string value is code, and the language label to show for it.
_CODE_KEYS = {
    "code": "python",
    "script": "python",
    "python": "python",
    "source": "",
    "command": "bash",
    "cmd": "bash",
    "expression": "",
    "query": "",
    "text": "",
    "content": "",
    "patch": "diff",
    "diff": "diff",
}

STATUS_LABELS = {
    "running": "running",
    "ok": "done",
    "error": "failed",
    "interrupted": "interrupted",
}


def clip(text: str, limit: int = MAX_FIELD_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + "\n\u2026 (truncated)"


def sanitize_payload(value, depth: int = 0):
    """JSON-safe copy of a tool payload: bounded depth/size, image bytes reduced to metadata."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return clip(value)
    if depth >= _MAX_DEPTH:
        return clip(str(value), 500)
    if isinstance(value, dict):
        if value.get("type") == "image" and ("data" in value or "base64" in value):
            data = value.get("data") or value.get("base64") or ""
            kept = {key: value[key] for key in ("type", "mimeType", "mime_type") if key in value}
            kept["bytes"] = len(data) * 3 // 4 if isinstance(data, str) else 0
            return kept
        return {
            str(key): sanitize_payload(item, depth + 1)
            for key, item in list(value.items())[:_MAX_ITEMS]
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_payload(item, depth + 1) for item in list(value)[:_MAX_ITEMS]]
    return clip(str(value), 2000)


def pretty_json(value) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def elapsed_text(seconds: float | None) -> str:
    if seconds is None:
        return ""
    if seconds < 1:
        return "%d ms" % round(seconds * 1000)
    if seconds < 10:
        return "%.1f s" % seconds
    if seconds < 60:
        return "%d s" % round(seconds)
    minutes, rest = divmod(int(round(seconds)), 60)
    return "%dm %02ds" % (minutes, rest)


def display_name(tool: str) -> str:
    """Short title for a tool name (drops the MCP server prefix)."""
    name = tool or "tool"
    if name.startswith("mcp__") and name.count("__") >= 2:
        name = name.split("__", 2)[2]
    return name


def _block_text(block) -> str:
    if isinstance(block, str):
        return block
    if not isinstance(block, dict):
        return pretty_json(block)
    kind = block.get("type")
    if kind == "text" or (kind is None and isinstance(block.get("text"), str)):
        return str(block.get("text", ""))
    if kind == "image":
        mime = block.get("mimeType") or block.get("mime_type") or "image"
        size = block.get("bytes") or ((block.get("base64_chars") or 0) * 3 // 4)
        return "[image: %s%s]" % (mime, ", %s bytes" % size if size else "")
    return pretty_json(block)


def result_text(result) -> tuple[str, str]:
    """(text, language) for a tool result: content blocks joined, JSON text pretty-printed."""
    if result is None:
        return "", ""
    if isinstance(result, dict) and isinstance(result.get("content"), list):
        text = "\n".join(_block_text(block) for block in result["content"])
    elif isinstance(result, list) and result and all(isinstance(item, dict) and "type" in item for item in result):
        text = "\n".join(_block_text(block) for block in result)
    elif isinstance(result, str):
        text = result
    else:
        return pretty_json(result), "json"
    stripped = text.strip()
    if stripped[:1] in ("{", "[") and len(stripped) < 200000:
        try:
            return pretty_json(json.loads(stripped)), "json"
        except ValueError:
            pass
    return text, ""


def _language_for(tool: str, key: str) -> str:
    language = _CODE_KEYS.get(key, "")
    lowered = (tool or "").lower()
    if key in ("code", "script") and any(word in lowered for word in ("bash", "shell")):
        return "bash"
    return language


def argument_blocks(tool: str, arguments) -> list[tuple[str, str, str]]:
    """Labelled (label, text, language) blocks for a tool's arguments; code fields stand alone."""
    if arguments in (None, "", {}, []):
        return []
    if isinstance(arguments, str):
        stripped = arguments.strip()
        if stripped[:1] in ("{", "["):
            try:
                return argument_blocks(tool, json.loads(stripped))
            except ValueError:
                pass
        return [("input", arguments, "")]
    if not isinstance(arguments, dict):
        return [("input", pretty_json(arguments), "json")]
    blocks: list[tuple[str, str, str]] = []
    rest: dict = {}
    for key, value in arguments.items():
        if isinstance(value, str) and (("\n" in value) or len(value) > 120 or key in ("code", "script", "command")):
            blocks.append((str(key), value, _language_for(tool, str(key))))
        else:
            rest[key] = value
    if rest:
        blocks.insert(0, ("parameters", pretty_json(rest), "json"))
    return blocks


def arguments_copy_text(rec: dict) -> str:
    blocks = argument_blocks(rec.get("tool", ""), rec.get("arguments"))
    if not blocks:
        return rec.get("summary", "") or ""
    if len(blocks) == 1:
        return blocks[0][1]
    return "\n\n".join("%s:\n%s" % (label, text) for label, text, _ in blocks)


def result_copy_text(rec: dict) -> str:
    text, _ = result_text(rec.get("result"))
    return text or rec.get("result_summary", "") or ""


def _label(text: str, style: MarkdownStyle, color: str = "") -> str:
    return (
        '<p style="margin: 6px 0px 3px 0px; color: %s; font-size: %gpt; font-weight: 600;">%s</p>'
        % (color or style.muted, max(style.font_pt - 2.0, 7.0), escape(text.upper()))
    )


def tool_body_html(rec: dict, style: MarkdownStyle) -> str:
    """The expanded content of a tool card: formatted arguments, partial output, result/error."""
    out = []
    if rec.get("legacy"):
        out.append(code_block_html(rec.get("summary", ""), "", style))
        return "".join(out)
    blocks = argument_blocks(rec.get("tool", ""), rec.get("arguments"))
    if blocks:
        out.append(_label("Arguments", style))
        for label, text, language in blocks:
            tag = language
            if len(blocks) > 1 or label not in ("input", "parameters"):
                tag = ("%s \u00b7 %s" % (label, language)) if language else label
            out.append(code_block_html(clip(text), tag, style))
    elif rec.get("summary"):
        out.append(_label("Arguments", style))
        out.append(code_block_html(rec["summary"], "", style))
    status = rec.get("status")
    if status == "running" and rec.get("partial") is not None:
        text, language = result_text(rec["partial"])
        if text:
            out.append(_label("Output so far", style))
            out.append(code_block_html(clip(text), language, style))
    if status in ("ok", "error", "interrupted"):
        text, language = result_text(rec.get("result"))
        failed = status == "error"
        if text or rec.get("result_summary"):
            text = text or rec.get("result_summary") or ""
            out.append(_label("Error" if failed else "Result", style, style.error if failed else ""))
            out.append(code_block_html(clip(text), language, style))
        elif status == "interrupted":
            out.append(_label("No result received (interrupted)", style))
        else:
            out.append(_label("Finished without output", style))
    return "".join(out) or _label("No details", style)
