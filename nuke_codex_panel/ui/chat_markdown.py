"""Markdown-adjacent helpers for the chat (pure Python, no Qt imports).

Markdown itself is parsed by Qt (``QTextDocument.setMarkdown``, GitHub dialect, HTML disabled);
see ``chat_document``. This module only holds what Qt does not provide: the style tokens shared
with the tool cards, HTML for the formatted tool-call code blocks (those are generated output,
not Markdown), link-scheme filtering, newline handling for user-typed text and the safe cut
points that let a long streaming answer be rendered as frozen segments plus a live tail.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MarkdownStyle:
    """Colors (CSS hex) and sizes (points) used by chat text, code and tool bodies."""

    text: str = "#e8ebf2"
    muted: str = "#98a2b5"
    accent: str = "#4da3ff"
    border: str = "#363d4c"
    code_bg: str = "#12151b"
    code_fg: str = "#d7dce2"
    code_header_bg: str = "#1a1f28"
    table_header_bg: str = "#272c37"
    quote_bar: str = "#2dd4bf"
    font_pt: float = 11.0
    error: str = "#f87171"
    mono_family: str = "monospace"

    @property
    def mono_pt(self) -> float:
        return max(self.font_pt - 1.0, 7.0)

    def stylesheet(self) -> str:
        """Default stylesheet for HTML documents (tool-card bodies)."""
        mono = "'%s', monospace" % self.mono_family.replace("'", "")
        return "body { color: %s; } p { margin-top: 0px; margin-bottom: 6px; } code { font-family: %s; }" % (
            self.text,
            mono,
        )


_SPACER = '<p style="margin: 0px; font-size: 3pt;">&nbsp;</p>'
_ALLOWED_SCHEMES = ("http", "https", "mailto")

_RE_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
_RE_HR = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
_RE_LIST = re.compile(r"^( {0,3})([-+*]|\d{1,9}[.)])([ \t]+|$)(.*)$")


def escape(text: str) -> str:
    return html.escape(text, quote=True)


def safe_url(url: str) -> str | None:
    """The URL when it is an http/https/mailto target, else None (never open anything else)."""
    candidate = (url or "").strip()
    if not candidate:
        return None
    scheme = candidate.split(":", 1)[0].lower() if ":" in candidate else ""
    if scheme not in _ALLOWED_SCHEMES:
        return None
    return candidate


def user_breaks(text: str) -> str:
    """Make single newlines in typed text hard line breaks (Markdown would soft-wrap them)."""
    return re.sub(r"(?<!\n)\n(?!\n)", "  \n", text)


def code_block_html(text: str, language: str = "", style: MarkdownStyle | None = None) -> str:
    """A shaded code block for tool cards that keeps every space/newline and wraps long lines."""
    style = style or MarkdownStyle()
    body = text[:-1] if text.endswith("\n") else text
    body = escape(body.expandtabs(4)) if body else "&nbsp;"
    header = ""
    if language:
        header = (
            '<tr><td bgcolor="%s"><span style="color: %s; font-size: %gpt;">%s</span></td></tr>'
            % (style.code_header_bg, style.muted, style.mono_pt, escape(language))
        )
    return (
        '<table width="100%%" cellspacing="0" cellpadding="7" bgcolor="%s">%s'
        '<tr><td><pre style="white-space: pre-wrap; margin: 0px; font-family: \'%s\', monospace; '
        'font-size: %gpt; color: %s;">%s</pre></td></tr></table>%s'
        % (
            style.code_bg,
            header,
            style.mono_family.replace("'", ""),
            style.mono_pt,
            style.code_fg,
            body,
            _SPACER,
        )
    )


# -- segmentation ---------------------------------------------------------------------------------


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _fence_open(line: str):
    match = _RE_FENCE.match(line)
    if not match:
        return None
    indent, marker, info = match.groups()
    if marker[0] == "`" and "`" in info:
        return None
    return len(indent), marker[0], len(marker), info.strip()


def _list_marker(line: str):
    if _RE_HR.match(line):
        return None
    return _RE_LIST.match(line)


def safe_split(text: str, minimum: int = 3000) -> int:
    """Index of the first safe cut at or after ``minimum`` characters, or 0.

    A cut is only taken at a blank line outside a code fence, before a complete (newline
    terminated) column-0 line that is not a list item, quote or table row, so rendering the
    two halves separately never changes how either half's own blocks are parsed. Links that use
    reference definitions are the exception, which is why a finished section is rendered whole.
    """
    offset = 0
    in_fence = None
    previous_blank = False
    for line in text.split("\n")[:-1]:
        length = len(line) + 1
        fence = _fence_open(line)
        if in_fence is not None:
            stripped = line.strip()
            if stripped and set(stripped) == {in_fence[0]} and len(stripped) >= in_fence[1] and _indent(line) < 4:
                in_fence = None
        elif fence:
            in_fence = (fence[1], fence[2])
        elif (
            previous_blank
            and offset >= minimum
            and line.strip()
            and not line.startswith((" ", "\t", ">", "|"))
            and not _list_marker(line)
        ):
            return offset
        previous_blank = in_fence is None and not line.strip()
        offset += length
    return 0
