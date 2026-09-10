"""Bubble-style chat view with Markdown/code rendering."""

from __future__ import annotations

import time

from PySide6 import QtCore, QtGui, QtWidgets

# While a section is still streaming, only its tail is re-rendered: full
# setMarkdown of an ever-growing buffer is O(document) per flush and a large
# thinking stream would starve Nuke's main thread.
STREAM_PREVIEW_CHARS = 4000


_DOC_STYLESHEET = (
    "pre, code { font-family: 'DejaVu Sans Mono', 'Monospace', monospace; }"
    "pre { background-color: #141519; color: #d7dce2; margin: 4px 0; }"
    "code { background-color: #141519; color: #d7dce2; }"
    "a { color: #7ab3e0; }"
)

_STYLESHEET = """
QScrollArea#chatView { background: #1e1f22; border: none; }
QWidget#chatContainer { background: #1e1f22; }
QFrame#userBubble { background-color: #2f5373; border-radius: 10px; }
QFrame#assistantBubble { background-color: #2a2c30; border: 1px solid #3a3d42; border-radius: 10px; }
QFrame#errorBubble { background-color: #4d2a2a; border: 1px solid #7a3a3a; border-radius: 10px; }
QLabel#roleLabel { color: #9aa0a8; font-size: 10px; }
QLabel#toolLine { font-family: 'DejaVu Sans Mono', monospace; color: #98b098;
                  background: #232428; border-radius: 4px; padding: 2px 6px; font-size: 11px; }
QToolButton#sectionHeader { color: #9aa0a8; font-size: 11px; padding: 0; }
QTextBrowser { background: transparent; color: #e4e6ea; border: none; }
QTextBrowser#thinkingText { color: #9aa0a8; }
"""


class BubbleText(QtWidgets.QTextBrowser):
    """Read-only Markdown text that shrinks vertically to fit its content."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )
        document = self.document()
        document.setDocumentMargin(0)
        document.setDefaultStyleSheet(_DOC_STYLESHEET)
        document.contentsChanged.connect(self._fit_height)
        self.viewport().installEventFilter(self)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        document = self.document()
        document.setTextWidth(max(width - 4, 50))
        return int(document.size().height()) + 6

    def _fit_height(self):
        self.updateGeometry()
        self.setMinimumHeight(self.heightForWidth(self.viewport().width() or 300))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_height()

    def eventFilter(self, obj, event):
        # Wheel events arrive on the viewport, where QAbstractScrollArea
        # swallows them even though bubbles always fit their content. Steer
        # them to the enclosing chat scroll area instead.
        if event.type() == QtCore.QEvent.Type.Wheel:
            target = self.parentWidget()
            while target is not None and not isinstance(target, QtWidgets.QScrollArea):
                target = target.parentWidget()
            if isinstance(target, QtWidgets.QScrollArea):
                bar = target.verticalScrollBar()
                steps = -event.angleDelta().y() / 120.0
                bar.setValue(
                    bar.value()
                    + int(steps * QtWidgets.QApplication.wheelScrollLines() * bar.singleStep())
                )
                return True
        return super().eventFilter(obj, event)


class CollapsibleSection(QtWidgets.QWidget):
    """Header that shows or hides its body; used for thinking and tool groups."""

    def __init__(self, title: str, body: QtWidgets.QWidget, parent=None):
        super().__init__(parent)
        self.title = title
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.header = QtWidgets.QToolButton()
        self.header.setObjectName("sectionHeader")
        self.header.setCheckable(True)
        self.header.setChecked(True)
        self.header.setAutoRaise(True)
        self.header.toggled.connect(self._on_toggled)
        layout.addWidget(self.header, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.body = body
        layout.addWidget(body)
        self._refresh()

    def set_title(self, title: str):
        self.title = title
        self._refresh()

    def _on_toggled(self, checked: bool):
        self.body.setVisible(checked)
        self._refresh()

    def _refresh(self):
        self.header.setText("%s %s" % ("▾" if self.header.isChecked() else "▸", self.title))


class ChatView(QtWidgets.QScrollArea):
    """Scrollable bubble chat: user right/accent, assistant left/neutral."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatView")
        self.setWidgetResizable(True)
        self.setStyleSheet(_STYLESHEET)
        self.container = QtWidgets.QWidget()
        self.container.setObjectName("chatContainer")
        self.messages_layout = QtWidgets.QVBoxLayout(self.container)
        self.messages_layout.setContentsMargins(8, 8, 8, 8)
        self.messages_layout.setSpacing(10)
        self.messages_layout.addStretch(1)
        self.setWidget(self.container)
        self._bubble_layout = None
        self._stream_section = None
        self._tool_group = None
        # Kinds the user collapsed: new sections of that kind start collapsed.
        self._collapsed_kinds: set[str] = set()
        # Serializable mirror of what is rendered, for save/restore.
        self._records: list[dict] = []
        self._record: dict | None = None
        self._assistant_title = "Assistant"
        self._render_timer = QtCore.QTimer(self)
        self._render_timer.setInterval(60)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_stream)
        self._render_interval = 60

    # -- public API ---------------------------------------------------------

    def add_user_message(self, text: str, images: list | None = None):
        suffix = "\n\n*%s image(s) attached*" % len(images) if images else ""
        self._add_bubble("user", "You", text + suffix)
        self._records.append(
            {"role": "user", "text": text, "images": list(images or [])}
        )

    def add_error(self, message: str):
        self._add_bubble("error", "Error", message)
        self._records.append({"role": "error", "text": message})

    def records(self) -> list[dict]:
        """Serializable chat history, safe to persist."""
        import copy

        return copy.deepcopy(self._records)

    def load_records(self, records: list[dict]):
        """Replay a saved transcript into fresh widgets."""
        self.clear()
        self._records = []
        for record in records or []:
            role = record.get("role")
            if role == "user":
                self.add_user_message(record.get("text", ""), record.get("images") or [])
            elif role == "error":
                self.add_error(record.get("text", ""))
            elif role == "assistant":
                self._replay_assistant(record.get("sections") or [])

    def _replay_assistant(self, sections: list[dict]):
        self.start_assistant(self._assistant_title)
        for section in sections:
            kind = section.get("kind")
            if kind == "thinking":
                self.append_thinking(section.get("text", ""))
            elif kind == "text":
                self.append_delta(section.get("text", ""))
            elif kind == "tools":
                for line in section.get("lines") or []:
                    self.add_tool_event(
                        {
                            "phase": "start",
                            "id": line.get("id"),
                            "tool": line.get("tool", "tool"),
                            "text": line.get("text", ""),
                        }
                    )
        self.finish_assistant()

    def start_assistant(self, title: str = "Assistant"):
        self._stream_section = None
        self._tool_group = None
        self._assistant_title = title
        self._record = {"role": "assistant", "sections": []}
        self._records.append(self._record)
        bubble = QtWidgets.QFrame()
        bubble.setObjectName("assistantBubble")
        self._bubble_layout = QtWidgets.QVBoxLayout(bubble)
        self._bubble_layout.setContentsMargins(10, 6, 10, 8)
        self._bubble_layout.setSpacing(4)
        role_label = QtWidgets.QLabel(title)
        role_label.setObjectName("roleLabel")
        self._bubble_layout.addWidget(role_label)
        self._attach_row(bubble, stretch_left=False)
        self._scroll_to_bottom()

    def append_delta(self, delta: str):
        self._stream_into("text", delta)

    def append_thinking(self, delta: str):
        self._stream_into("thinking", delta)

    def add_tool_event(self, info: dict):
        if self._bubble_layout is None:
            self.start_assistant()
        # Any tool activity ends the current reply run, so text that follows a
        # tool call starts a new block below it instead of growing the old one.
        section = self._stream_section
        if section is not None:
            self._render_section(section, final=True)  # full render on close
            self._stream_section = None
        tool_id = info.get("id") or id(info)
        line_text = info.get("text") or "%s: %s" % (
            info.get("tool", "tool"),
            info.get("detail") or "…",
        )
        if info.get("phase") == "end":
            group = self._tool_group
            label = group["labels"].get(tool_id) if group else None
            if label is not None:
                outcome = "ok" if info.get("ok", True) else "error"
                detail = info.get("detail") or ""
                label.setText(
                    "%s — %s%s"
                    % (label.text(), outcome, ": %s" % detail if detail else "")
                )
                record_line = self._record_line(tool_id)
                if record_line is not None:
                    record_line["text"] = label.text()
                self._scroll_to_bottom()
            return
        group = self._tool_group
        if group is None:
            body = QtWidgets.QWidget()
            body_layout = QtWidgets.QVBoxLayout(body)
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(2)
            container = CollapsibleSection("Tools", body)
            self._track_collapse(container, "tools")
            self._bubble_layout.addWidget(container)
            group = self._tool_group = {
                "section": container,
                "layout": body_layout,
                "labels": {},
                "count": 0,
            }
            self._record["sections"].append({"kind": "tools", "lines": []})
        line = QtWidgets.QLabel(line_text)
        line.setObjectName("toolLine")
        line.setWordWrap(True)
        group["layout"].addWidget(line)
        group["labels"][tool_id] = line
        group["count"] += 1
        group["section"].set_title("Tools (%d)" % group["count"])
        self._record["sections"][-1]["lines"].append(
            {"id": tool_id, "tool": info.get("tool", "tool"), "text": line.text()}
        )
        self._scroll_to_bottom()

    def finish_assistant(self):
        self._render_timer.stop()
        self._render_stream(final=True)
        self._bubble_layout = None
        self._stream_section = None
        self._tool_group = None

    def clear(self):
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._bubble_layout = None
        self._stream_section = None
        self._tool_group = None
        self._record = None
        self._records = []

    # -- internals ----------------------------------------------------------

    def _stream_into(self, kind: str, delta: str):
        if self._bubble_layout is None:
            self.start_assistant()
        section = self._stream_section
        if section is None or section["kind"] != kind:
            if section is not None:
                self._render_section(section, final=True)  # full render on close
            text = BubbleText()
            text.setObjectName("thinkingText" if kind == "thinking" else "answerText")
            if kind == "thinking":
                container = CollapsibleSection("Thinking", text)
                self._track_collapse(container, "thinking")
                self._bubble_layout.addWidget(container)
            else:
                self._bubble_layout.addWidget(text)
            section = self._stream_section = {
                "kind": kind,
                "widget": text,
                "buffer": "",
            }
            section["record"] = {"kind": kind, "text": ""}
            self._record["sections"].append(section["record"])
            self._tool_group = None  # a reply or thought breaks the tool run
        section["buffer"] += delta
        if not self._render_timer.isActive():
            self._render_timer.start()

    def _render_stream(self, final: bool = False):
        self._render_section(self._stream_section, final=final)

    def _track_collapse(self, section: "CollapsibleSection", kind: str):
        """Keep the user's collapse choice for the sections that follow."""
        if kind in self._collapsed_kinds:
            section.header.setChecked(False)
        section.header.toggled.connect(
            lambda expanded, k=kind: self._collapsed_kinds.discard(k)
            if expanded
            else self._collapsed_kinds.add(k)
        )

    def _render_section(self, section, final: bool = False):
        if section is None:
            return
        start = time.monotonic()
        buffer = section["buffer"]
        if not final and len(buffer) > STREAM_PREVIEW_CHARS:
            shown = buffer[-STREAM_PREVIEW_CHARS:]
            newline = shown.find("\n")
            if newline >= 0:
                shown = shown[newline + 1 :]
            section["widget"].setMarkdown(
                "… (%d chars so far)\n\n%s" % (len(buffer) - len(shown), shown)
            )
        else:
            placeholder = "thinking…" if section["kind"] == "thinking" else "…"
            section["widget"].setMarkdown(buffer or placeholder)
        section["record"]["text"] = buffer
        self._scroll_to_bottom()
        # Adaptive backoff: expensive renders stream slower so Nuke's main
        # thread keeps breathing.
        elapsed = time.monotonic() - start
        if elapsed > 0.08:
            self._render_interval = min(1000, max(120, self._render_interval * 2))
        elif elapsed < 0.02 and self._render_interval > 60:
            self._render_interval = max(60, self._render_interval // 2)
        self._render_timer.setInterval(self._render_interval)

    def _record_line(self, tool_id):
        for section in reversed(self._record.get("sections") or []):
            for line in section.get("lines") or []:
                if line.get("id") == tool_id:
                    return line
        return None

    def _attach_row(self, bubble: QtWidgets.QWidget, stretch_left: bool):
        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        if stretch_left:
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 4)
        else:
            row_layout.addWidget(bubble, 4)
            row_layout.addStretch(1)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)

    def _add_bubble(self, role: str, title: str, markdown: str) -> BubbleText:
        bubble = QtWidgets.QFrame()
        bubble.setObjectName(role + "Bubble")
        bubble_layout = QtWidgets.QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(10, 6, 10, 8)
        bubble_layout.setSpacing(2)
        role_label = QtWidgets.QLabel(title)
        role_label.setObjectName("roleLabel")
        bubble_layout.addWidget(role_label)
        text = BubbleText(bubble)
        if markdown:
            text.setMarkdown(markdown)
        bubble_layout.addWidget(text)
        self._attach_row(bubble, stretch_left=(role == "user"))
        self._scroll_to_bottom()
        return text

    def _scroll_to_bottom(self):
        QtCore.QTimer.singleShot(
            0,
            lambda: self.verticalScrollBar().setValue(self.verticalScrollBar().maximum()),
        )
