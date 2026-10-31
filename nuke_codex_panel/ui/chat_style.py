"""Chat colors, sizes and the chat-scoped stylesheet, derived from the panel theme tokens."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6 import QtGui

from .chat_markdown import MarkdownStyle
from .theme import PALETTE

FONT_DEFAULT = 11
FONT_MIN = 8
FONT_MAX = 24


def clamp_font(points) -> int:
    try:
        value = int(round(float(points)))
    except (TypeError, ValueError):
        return FONT_DEFAULT
    return max(FONT_MIN, min(FONT_MAX, value))


def mono_family() -> str:
    return QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont).family()


@dataclass(frozen=True)
class ChatStyle:
    """Everything size/color dependent the chat renders with, for one font size."""

    font_pt: int
    markdown: MarkdownStyle
    thinking: MarkdownStyle
    mono: str

    @classmethod
    def build(cls, font_pt: int) -> "ChatStyle":
        p = PALETTE
        mono = mono_family()
        base = MarkdownStyle(
            text=p["text"],
            muted=p["muted"],
            accent=p["accent"],
            border=p["border"],
            code_bg="#12151b",
            code_fg="#d7dce2",
            code_header_bg="#1a1f28",
            table_header_bg=p["surface_alt"],
            quote_bar=p["teal"],
            error=p["error"],
            font_pt=float(font_pt),
            mono_family=mono,
        )
        return cls(font_pt, base, replace(base, text=p["muted"]), mono)

    @property
    def small_pt(self) -> int:
        return max(self.font_pt - 2, 7)

    @property
    def mono_pt(self) -> int:
        return max(self.font_pt - 1, 7)

    def qss(self) -> str:
        p = PALETTE
        values = dict(p)
        values.update(
            base=self.font_pt,
            small=self.small_pt,
            mono_pt=self.mono_pt,
            mono=self.mono.replace("'", ""),
        )
        return (
            """
QWidget#chatContainer { background: %(bg)s; }
QFrame#userBubble { background-color: %(selection)s; border: 1px solid %(accent_pressed)s; border-radius: 10px; }
QFrame#assistantBubble { background-color: %(surface)s; border: 1px solid %(border)s; border-radius: 10px; }
QFrame#thinkingBubble { background-color: %(bg)s; border: 1px dashed %(border_strong)s; border-radius: 10px; }
QFrame#errorBubble { background-color: #3a2226; border: 1px solid %(error)s; border-radius: 10px; }
QFrame#imageBubble { background-color: %(surface)s; border: 1px solid %(teal)s; border-radius: 10px; }
QFrame#toolBubble { background-color: %(surface_alt)s; border: 1px solid %(border)s;
    border-left: 3px solid %(muted)s; border-radius: 8px; }
QFrame#toolBubble[state="running"] { border-left-color: %(accent)s; border-color: %(accent_pressed)s; }
QFrame#toolBubble[state="ok"] { border-left-color: %(ok)s; }
QFrame#toolBubble[state="error"] { border-left-color: %(error)s; border-color: %(error)s; }
QFrame#toolBubble[state="interrupted"] { border-left-color: %(warn)s; }
QWidget#cardHeader { background: transparent; }
QWidget#cardBody { background: transparent; }
QLabel { background: transparent; border: none; }
QLabel#roleLabel { color: %(muted)s; font-size: %(small)dpt; font-weight: 600; }
QLabel#cardArrow { color: %(muted)s; font-size: %(base)dpt; }
QLabel#cardTitle { color: %(text)s; font-size: %(base)dpt; font-weight: 700; }
QLabel#thinkingTitle { color: %(muted)s; font-size: %(base)dpt; font-style: italic; }
QLabel#toolSummary { color: %(muted)s; font-family: '%(mono)s', monospace; font-size: %(mono_pt)dpt; }
QLabel#toolElapsed { color: %(muted)s; font-size: %(small)dpt; }
QLabel#toolStatus { color: %(muted)s; font-size: %(small)dpt; font-weight: 600; }
QLabel#toolStatus[state="running"] { color: %(accent)s; }
QLabel#toolStatus[state="ok"] { color: %(ok)s; }
QLabel#toolStatus[state="error"] { color: %(error)s; }
QLabel#toolStatus[state="interrupted"] { color: %(warn)s; }
QLabel#imageCaption { color: %(muted)s; font-size: %(small)dpt; }
QToolButton#copyButton { font-size: %(small)dpt; padding: 2px 8px; }
QTextBrowser { background: transparent; color: %(text)s; border: none; selection-background-color: %(selection)s; }
QTextBrowser#thinkingText { color: %(muted)s; }
"""
            % values
        )
