"""ChatGPT-app-style bubble chat view for the Nuke Codex panel.

Lightweight QScrollArea + QVBoxLayout of bubble widgets, sized for the
~320px-wide Nuke dock. Pure Qt, no external assets.
"""

from __future__ import annotations

import json

from PySide6 import QtCore, QtGui, QtWidgets

_MUTED = "rgba(235, 235, 235, 150)"

_GLYPHS = {"running": "…", "completed": "✓", "error": "✗"}


def _text_label(text: str, muted: bool = False, italic: bool = False) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    style = []
    if muted:
        style.append("color: %s;" % _MUTED)
    if italic:
        style.append("font-style: italic;")
    if style:
        label.setStyleSheet("QLabel { %s }" % " ".join(style))
    return label


class _Bubble(QtWidgets.QFrame):
    """Rounded frame with a tight vertical layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(2)


class UserBubble(_Bubble):
    def __init__(self, text: str, images: list, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "UserBubble { background: rgba(88, 130, 200, 70);"
            " border: 1px solid rgba(120, 160, 230, 90); border-radius: 8px; }"
        )
        self.label = _text_label(text)
        self._layout.addWidget(self.label)
        for path in images or []:
            line = _text_label(str(path), muted=True)
            line.setToolTip(str(path))
            font = line.font()
            font.setPointSize(max(6, font.pointSize() - 1))
            line.setFont(font)
            self._layout.addWidget(line)


class AgentBubble(_Bubble):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self.label = _text_label("")
        self._layout.addWidget(self.label)

    def append(self, delta: str):
        self._text += delta
        self.label.setText(self._text)


class CollapsibleBubble(_Bubble):
    """Bubble with a clickable ▸/▾ header and a hideable body."""

    def __init__(self, title: str, header_italic: bool = False, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "%s { background: rgba(255, 255, 255, 14);"
            " border: 1px solid rgba(255, 255, 255, 30); border-radius: 6px; }"
            % type(self).__name__
        )
        self.header = QtWidgets.QToolButton()
        self.header.setAutoRaise(True)
        self.header.setStyleSheet(
            "QToolButton { color: %s; border: none; padding: 0;%s }"
            % (_MUTED, " font-style: italic;" if header_italic else "")
        )
        self.header.clicked.connect(self.toggle)
        self._layout.addWidget(self.header)
        self.body = QtWidgets.QWidget()
        self.body_layout = QtWidgets.QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 2, 0, 0)
        self.body_layout.setSpacing(0)
        self._layout.addWidget(self.body)
        self._expanded = True
        self._title = title
        self._refresh_header()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, value: bool):
        self._expanded = bool(value)
        self.body.setVisible(self._expanded)
        self._refresh_header()

    def toggle(self):
        self.set_expanded(not self._expanded)

    def set_title(self, title: str):
        self._title = title
        self._refresh_header()

    def _refresh_header(self):
        self.header.setText(("▾ " if self._expanded else "▸ ") + self._title)


class ThinkingBubble(CollapsibleBubble):
    def __init__(self, parent=None):
        super().__init__("Thinking…", header_italic=True, parent=parent)
        self.text_label = _text_label("", muted=True, italic=True)
        self.body_layout.addWidget(self.text_label)

    def set_text(self, text: str):
        self.text_label.setText(text)

    def complete(self):
        self.set_title("Thinking")
        self.set_expanded(False)


class ToolBubble(CollapsibleBubble):
    def __init__(self, parent=None):
        super().__init__("", parent=parent)
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont))
        self.output.setMaximumHeight(150)
        self.output.setStyleSheet(
            "QPlainTextEdit { background: rgba(0, 0, 0, 60); border: none;"
            " color: rgba(235, 235, 235, 200); }"
        )
        self.body_layout.addWidget(self.output)

    def apply_update(self, name: str, status: str, args_json: str, output: str):
        glyph = _GLYPHS.get(status, status)
        self.set_title("%s %s" % (glyph, name))
        text = _pretty_json(args_json)
        if output and status != "running":
            text = (text + "\n\n" if text else "") + output
        self.output.setPlainText(text)
        # ponytail: expanded while running, auto-collapse on terminal status
        self.set_expanded(status == "running")


def _pretty_json(raw: str) -> str:
    if not raw:
        return ""
    try:
        return json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
    except ValueError:
        return raw


class ChatView(QtWidgets.QScrollArea):
    """Chronological bubble list with stick-to-bottom scrolling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._container = QtWidgets.QWidget()
        self._layout = QtWidgets.QVBoxLayout(self._container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(6)
        self._layout.addStretch(1)
        self.setWidget(self._container)
        self._rows = []
        self._thinking = {}
        self._tools = {}
        self._agent: AgentBubble | None = None
        self._agent_item_id = None
        self._pinned = True
        self.verticalScrollBar().valueChanged.connect(self._on_scrolled)

    # --- bubble rows -----------------------------------------------------

    def _add_row(self, bubble, user: bool = False):
        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        if user:
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 5)
        else:
            row_layout.addWidget(bubble, 1)
        row.bubble = bubble  # type: ignore[attr-defined]
        self._layout.insertWidget(self._layout.count() - 1, row)
        self._rows.append(row)
        self._maybe_scroll()
        return bubble

    def add_user_message(self, text: str, images: list):
        self._add_row(UserBubble(text, images), user=True)

    def start_agent_message(self, item_id=None):
        if self._agent is not None and item_id and item_id == self._agent_item_id:
            return
        self._agent = self._add_row(AgentBubble())
        self._agent_item_id = item_id

    def append_agent_delta(self, delta: str):
        if self._agent is None:
            self.start_agent_message()
        assert self._agent is not None
        self._agent.append(delta)
        self._maybe_scroll()

    def end_turn(self):
        self._agent = None
        self._agent_item_id = None

    def update_thinking(self, item_id: str, text: str):
        bubble = self._thinking.get(item_id)
        if bubble is None:
            bubble = self._add_row(ThinkingBubble())
            self._thinking[item_id] = bubble
        bubble.set_text(text)
        self._maybe_scroll()

    def complete_thinking(self, item_id: str):
        bubble = self._thinking.get(item_id)
        if bubble is not None:
            bubble.complete()

    def update_tool(self, item_id: str, name: str, status: str, args_json: str, output: str):
        bubble = self._tools.get(item_id)
        if bubble is None:
            bubble = self._add_row(ToolBubble())
            self._tools[item_id] = bubble
        bubble.apply_update(name, status, args_json, output)
        self._maybe_scroll()

    def add_error(self, message: str):
        bubble = AgentBubble()
        bubble.label.setStyleSheet("QLabel { color: rgba(255, 120, 120, 220); }")
        bubble.append("Error: %s" % message)
        self._add_row(bubble)

    def add_divider(self, text: str):
        label = _text_label("— %s —" % text, muted=True)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._add_row(label)

    def clear(self):
        for row in self._rows:
            self._layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._thinking.clear()
        self._tools.clear()
        self.end_turn()
        self._pinned = True
        self.verticalScrollBar().setValue(0)

    # --- scrolling -------------------------------------------------------

    def _on_scrolled(self, value: int):
        bar = self.verticalScrollBar()
        self._pinned = value >= bar.maximum() - 4

    def _maybe_scroll(self):
        if self._pinned:
            QtCore.QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())
