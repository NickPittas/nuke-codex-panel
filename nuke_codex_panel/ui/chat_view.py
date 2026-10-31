"""Chat transcript view: one render pass, one layout path, one scroll owner.

Model first: every public call (``append_delta``, ``add_tool_event`` ...) only mutates plain
records/section objects and marks the section dirty (O(1), no widgets). A single fixed-cadence
timer then runs ``_flush``, which materializes/refreshes dirty sections in chronological order
within a small time budget, lays the container out synchronously and finally applies the scroll
position (bottom-follow or an anchor on the first visible row) exactly once. Nothing else moves the
scrollbar, so the view is stable while the user reads older content and monotonic while pinned.

Each chat item is its own bubble: user/error text, assistant text segments, a collapsible thinking
bubble, one collapsible bubble per tool call (formatted arguments/result, built lazily on first
expand) and delivered images. Finished records are never mutated again, which lets ``records()``
hand the persistence worker shared snapshots instead of deep copies.
"""

from __future__ import annotations

import copy
import logging
import re
import time
from collections import deque

from PySide6 import QtCore, QtGui, QtWidgets

from . import chat_format, chat_markdown
from .chat_style import FONT_DEFAULT, FONT_MAX, FONT_MIN, ChatStyle, clamp_font
from .chat_widgets import DeliveredImage, TextBlock, ThinkingCard, ToolCard
from .theme import PALETTE, apply_theme

_LOG = logging.getLogger(__name__)

RENDER_INTERVAL_MS = 60
RENDER_BUDGET_S = 0.012
SEGMENT_CHARS = 3000
ROW_INSET = 28
_CONTAINER_MARGIN = 10
_BUBBLE_PADDING = 26
_IMAGE_SKIP = frozenset({"data", "base64", "b64", "kind"})
_LEGACY_STATUS = re.compile(r" \u2014 (ok|error)(?::|$)")


def _wheel_pixels(event: QtGui.QWheelEvent, bar: QtWidgets.QScrollBar) -> int:
    pixel = event.pixelDelta().y()
    if pixel:
        return -pixel
    steps = event.angleDelta().y() / 120.0
    return -int(steps * QtWidgets.QApplication.wheelScrollLines() * bar.singleStep())


# -- sections -----------------------------------------------------------------------------------


class _Section:
    """One chat item: its persisted record, its row widget (lazy) and how to draw it."""

    def __init__(self, view: "ChatView", rec: dict):
        self.view = view
        self.rec = rec
        self.row: QtWidgets.QWidget | None = None
        self.needs_restyle = False
        self.version = 0

    def update(self):
        if self.row is None:
            self.materialize()
            self.needs_restyle = False
        elif self.needs_restyle:
            self.needs_restyle = False
            self.restyle()
        self.refresh()

    def materialize(self):  # pragma: no cover - subclass hook
        raise NotImplementedError

    def refresh(self):  # pragma: no cover - subclass hook
        raise NotImplementedError

    def restyle(self):
        """Style/font changed: default is to redraw from the record."""

    def sync(self):
        """Fold pending streamed data into ``rec`` (only text sections buffer)."""


class _UserSection(_Section):
    def __init__(self, view, rec, role: str):
        super().__init__(view, rec)
        self.role = role
        self.block: TextBlock | None = None

    def materialize(self):
        view = self.view
        bubble = QtWidgets.QFrame()
        bubble.setObjectName(self.role + "Bubble")
        layout = QtWidgets.QVBoxLayout(bubble)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(3)
        label = QtWidgets.QLabel("You" if self.role == "user" else "Error")
        label.setObjectName("roleLabel")
        layout.addWidget(label)
        self.block = TextBlock(view._wheel, view._text_width(), breaks=True)
        layout.addWidget(self.block)
        self.row = view._add_row(bubble, "user" if self.role == "user" else "assistant")

    def refresh(self):
        text = self.rec.get("text", "")
        images = self.rec.get("images") or []
        if images:
            text += "\n\n*%d image(s) attached*" % len(images)
        self.block.set_markdown(text, self.view.chat_style)


class _TextSection(_Section):
    """Streamed assistant text or thinking: frozen segments plus one live tail block while it
    streams, then one block holding the whole text once finished, so Markdown that spans segment
    boundaries (reference-style link definitions) resolves exactly as in a single document."""

    def __init__(self, view, rec, thinking: bool, title: str, show_role: bool):
        super().__init__(view, rec)
        self.thinking = thinking
        self.title = title
        self.show_role = show_role
        self.chunks: list[str] = [rec.get("text", "")] if rec.get("text") else []
        self.committed = 0
        self.finished = False
        self.blocks: list[TextBlock] = []
        self.live: TextBlock | None = None
        self.layout: QtWidgets.QVBoxLayout | None = None
        self.card: ThinkingCard | None = None

    def append(self, delta: str):
        self.chunks.append(delta)

    def text(self) -> str:
        if len(self.chunks) > 1:
            self.chunks = ["".join(self.chunks)]
        return self.chunks[0] if self.chunks else ""

    def sync(self):
        self.rec["text"] = self.text()

    def materialize(self):
        view = self.view
        if self.thinking:
            card = ThinkingCard(view._toggle_card)
            card.expanded_hook = self._on_expanded
            self.card = card
            card.set_expanded(view._expanded_pref["thinking"])
            widget: QtWidgets.QWidget = card
        else:
            bubble = QtWidgets.QFrame()
            bubble.setObjectName("assistantBubble")
            self.layout = QtWidgets.QVBoxLayout(bubble)
            self.layout.setContentsMargins(12, 8, 12, 4)
            self.layout.setSpacing(0)
            if self.show_role:
                label = QtWidgets.QLabel(self.title)
                label.setObjectName("roleLabel")
                label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
                self.layout.addWidget(label)
                self.layout.addSpacing(3)
            widget = bubble
        self.row = view._add_row(widget, "assistant")

    def _on_expanded(self):
        # The thinking body was just built/shown: draw what streamed while it was collapsed.
        if self.row is not None:
            self.refresh()

    def _new_block(self, layout: QtWidgets.QVBoxLayout) -> TextBlock:
        block = TextBlock(self.view._wheel, self.view._text_width(), thinking=self.thinking)
        layout.addWidget(block)
        block.show()
        self.blocks.append(block)
        return block

    def refresh(self):
        full = self.text()
        self.rec["text"] = full
        if self.thinking:
            if self.card is None or not self.card.expanded or self.card.body_layout is None:
                return  # lazy: drawn when the bubble is expanded
            layout = self.card.body_layout
        else:
            layout = self.layout
        style = self.view.chat_style
        if self.finished and self.committed:
            for block in self.blocks[1:]:
                layout.removeWidget(block)
                block.hide()
                block.setParent(None)
                block.deleteLater()
            del self.blocks[1:]
            self.live = self.blocks[0]
            self.committed = 0
        live = full[self.committed :]
        while not self.finished and len(live) >= SEGMENT_CHARS:
            cut = chat_markdown.safe_split(live, SEGMENT_CHARS)
            if not cut:
                break
            block = self.live or self._new_block(layout)
            block.set_markdown(live[:cut], style)
            self.live = None
            self.committed += cut
            live = live[cut:]
        if live or not self.blocks:
            if self.live is None:
                self.live = self._new_block(layout)
            placeholder = "thinking\u2026" if self.thinking else "\u2026"
            self.live.set_markdown(live or placeholder, style)

    def restyle(self):
        style = self.view.chat_style
        for block in self.blocks:
            block.restyle(style)


class _ToolSection(_Section):
    def __init__(self, view, rec):
        super().__init__(view, rec)
        self.card: ToolCard | None = None
        self.t0 = time.monotonic()
        self.t0_ns: int | None = None

    def materialize(self):
        view = self.view
        self.card = ToolCard(view._wheel, view._toggle_card)
        self.card.set_expanded(view._expanded_pref["tool"])
        self.row = view._add_row(self.card, "assistant")

    def elapsed(self) -> float | None:
        if self.rec.get("status") == "running":
            return time.monotonic() - self.t0
        return self.rec.get("elapsed")

    def refresh(self):
        self.card.apply(self.rec, self.view.chat_style, self.elapsed(), self.version)


class _ImageSection(_Section):
    def materialize(self):
        bubble = QtWidgets.QFrame()
        bubble.setObjectName("imageBubble")
        layout = QtWidgets.QVBoxLayout(bubble)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.addWidget(DeliveredImage(self.rec))
        self.row = self.view._add_row(bubble, "assistant")

    def refresh(self):
        """Delivered images never change after they are shown."""


# -- view ---------------------------------------------------------------------------------------


class ChatView(QtWidgets.QScrollArea):
    """Scrollable chat: user right/accent, assistant side with a bubble per item."""

    _ready = False  # set once __init__ finished; Qt delivers filtered/theme events before that
    _text_anchor = None  # (block, char position, px into its line, px it sat below the viewport top)
    _anchor_scroll = -1  # scroll value the last restore produced; the anchor is only valid there
    _anchor_pending = False  # a font change is waiting for its final layout to restore the anchor

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatView")
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Always on: a scrollbar that appears/disappears with content height would change the
        # viewport width and with it every text block's wrapping.
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setStyleSheet("QScrollArea#chatView { background: %s; border: none; }" % PALETTE["bg"])
        apply_theme(self)
        self._font_size = FONT_DEFAULT
        self.chat_style = ChatStyle.build(self._font_size)
        self.container = QtWidgets.QWidget()
        self.container.setObjectName("chatContainer")
        self.container.setStyleSheet(self.chat_style.qss())
        self.messages_layout = QtWidgets.QVBoxLayout(self.container)
        self.messages_layout.setContentsMargins(_CONTAINER_MARGIN, _CONTAINER_MARGIN, _CONTAINER_MARGIN, _CONTAINER_MARGIN)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch(1)
        self.setWidget(self.container)
        self.verticalScrollBar().setSingleStep(24)
        self.verticalScrollBar().valueChanged.connect(self._on_scrolled)

        self._queue: deque[_Section] = deque()
        self._queued: set[_Section] = set()
        self._sections: list[_Section] = []
        self._rows: list[QtWidgets.QWidget] = []
        self._records: list[dict] = []
        self._turn_rec: dict | None = None
        self._turn_title = "Assistant"
        self._role_shown = False
        self._open_text: _TextSection | None = None
        self._tools: dict[str, _ToolSection] = {}
        self._running: set[_ToolSection] = set()
        self._tool_counter = 0
        self._delivery_ids: set[str] = set()
        self._expanded_pref = {"thinking": True, "tool": False}
        self._follow = True
        self._programmatic = 0
        self._needs_relayout = False
        self._loading = False
        self._flushing = False

        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(RENDER_INTERVAL_MS)
        self._timer.timeout.connect(self._on_timer)
        self._clock = QtCore.QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._tick_clock)
        self._ready = True

    # -- font ---------------------------------------------------------------------------------

    @property
    def font_size(self) -> int:
        return self._font_size

    def set_font_size(self, points: int):
        points = clamp_font(points)
        if points == self._font_size:
            return
        if not self._follow and self.isVisible():
            # Every step of a font change maps back to the same character: re-capturing from the
            # restored position would snap to the start of the wrapped line each time and ratchet
            # the view away from what the user was reading. Only a scroll made by anything else
            # (user, card toggle, resize) invalidates the anchor.
            if not self._anchor_pending and (
                self._text_anchor is None or self.verticalScrollBar().value() != self._anchor_scroll
            ):
                self._text_anchor = self._capture_text_anchor()
            self._anchor_pending = self._text_anchor is not None
        self._font_size = points
        self.chat_style = ChatStyle.build(points)
        self.container.setStyleSheet(self.chat_style.qss())
        for section in self._sections:
            section.needs_restyle = True
            self._enqueue(section)
        self._needs_relayout = True
        self._schedule()

    # -- public API ---------------------------------------------------------------------------

    def add_user_message(self, text: str, images: list | None = None):
        self._follow = True
        rec = {"role": "user", "text": text, "images": list(images or [])}
        self._records.append(rec)
        self._register(_UserSection(self, rec, "user"))
        self._flush_now()

    def add_error(self, message: str):
        self._close_text()
        rec = {"role": "error", "text": message}
        self._records.append(rec)
        self._register(_UserSection(self, rec, "error"))
        self._flush_now()

    def records(self) -> list[dict]:
        """Serializable chat history. Finished records are shared and never mutated again; only the
        reply still streaming is copied, so persisting does not deep-copy the whole history."""
        for section in self._queue:
            section.sync()
        if self._open_text is not None:
            self._open_text.sync()
        return [copy.deepcopy(rec) if rec is self._turn_rec else rec for rec in self._records]

    def load_records(self, records: list[dict]):
        """Replay a saved transcript; rows are drawn progressively within the render budget."""
        self.clear()
        for record in records or []:
            role = record.get("role")
            if role in ("user", "error"):
                rec = {"role": role, "text": str(record.get("text", ""))}
                if role == "user":
                    rec["images"] = list(record.get("images") or [])
                self._records.append(rec)
                self._register(_UserSection(self, rec, role))
            elif role == "assistant":
                self._replay_assistant(record.get("sections") or [])
        if self._queue:
            self._loading = True
            self.viewport().setUpdatesEnabled(False)
            self._schedule()

    def start_assistant(self, title: str = "Assistant"):
        self._close_text()
        self._turn_title = title
        self._role_shown = False
        self._turn_rec = {"role": "assistant", "sections": []}
        self._records.append(self._turn_rec)

    def append_delta(self, delta: str):
        if delta:
            section = self._text_target("text")
            section.append(delta)
            self._mark(section)

    def append_thinking(self, delta: str):
        if delta:
            section = self._text_target("thinking")
            section.append(delta)
            self._mark(section)

    def add_tool_event(self, info: dict):
        if not isinstance(info, dict):
            return
        phase = info.get("phase") or "start"
        tool_id = info.get("id")
        tool_id = str(tool_id) if tool_id not in (None, "") else ""
        section = self._tools.get(tool_id) if tool_id else None
        if phase == "start":
            if section is not None and section.rec.get("status") == "running":
                self._tool_apply_start(section, info)
            else:
                section = self._tool_create(tool_id, info)
                self._tool_apply_start(section, info)
        elif phase == "end":
            if section is None:
                if self._turn_rec is None:
                    return  # a late end for a tool of an already finished reply
                section = self._tool_create(tool_id, info)
                self._tool_apply_start(section, info)
            self._tool_finish(section, info)
        else:
            if section is None:
                return
            partial = info.get("partial", info.get("update"))
            if partial is None:
                partial = info.get("detail")
            if partial is not None:
                section.rec["partial"] = chat_format.sanitize_payload(partial)
        if section is not None:
            section.version += 1
            self._mark(section)

    def add_delivered_image(self, image: dict) -> bool:
        """Show an image the agent was handed, as its own bubble in the current reply.

        ``image``: delivery_id (unique per tool instance; the only dedup key), asset (persistent PNG
        path) or error (why no preview exists), caption, sha256, bytes. Returns False when this
        delivery id was already shown, so a repeated notification never duplicates it while two
        identical captures with different delivery ids both appear.
        """
        delivery_id = str(image.get("delivery_id") or "")
        if delivery_id and delivery_id in self._delivery_ids:
            return False
        self._ensure_turn()
        if delivery_id:
            self._delivery_ids.add(delivery_id)
        self._close_text()
        rec = self._image_record(image)
        self._turn_rec["sections"].append(rec)
        self._register(_ImageSection(self, rec))
        return True

    def finish_assistant(self):
        self._close_text()
        for section in list(self._running):
            section.rec["status"] = "interrupted"
            section.version += 1
            self._mark(section)
        self._running.clear()
        self._clock.stop()
        self._tools.clear()
        rec = self._turn_rec
        if rec is not None and not rec["sections"]:
            self._records = [item for item in self._records if item is not rec]
        self._turn_rec = None
        self._flush_now()

    def clear(self):
        self._timer.stop()
        self._clock.stop()
        self._queue.clear()
        self._queued.clear()
        for row in self._rows:
            self.messages_layout.removeWidget(row)
            row.hide()
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        self._sections = []
        self._records = []
        self._turn_rec = None
        self._open_text = None
        self._role_shown = False
        self._tools.clear()
        self._running.clear()
        self._delivery_ids = set()
        self._follow = True
        self._text_anchor = None
        self._loading = False
        self.viewport().setUpdatesEnabled(True)
        self._needs_relayout = True
        self._flush_now()

    # -- model helpers --------------------------------------------------------------------------

    def _register(self, section: _Section):
        self._sections.append(section)
        self._mark(section)

    def _enqueue(self, section: _Section):
        if section not in self._queued:
            self._queued.add(section)
            self._queue.append(section)

    def _mark(self, section: _Section):
        self._enqueue(section)
        self._schedule()

    def _ensure_turn(self):
        if self._turn_rec is None:
            self.start_assistant(self._turn_title)

    def _close_text(self):
        section = self._open_text
        self._open_text = None
        if section is not None:
            section.finished = True
            if section.committed:
                self._mark(section)

    def _text_target(self, kind: str) -> _TextSection:
        self._ensure_turn()
        current = self._open_text
        if current is not None and current.rec["kind"] == kind:
            return current
        self._close_text()
        rec = {"kind": kind, "text": ""}
        self._turn_rec["sections"].append(rec)
        show_role = kind == "text" and not self._role_shown
        if kind == "text":
            self._role_shown = True
        section = _TextSection(self, rec, kind == "thinking", self._turn_title, show_role)
        self._sections.append(section)
        self._open_text = section
        return section

    def _tool_create(self, tool_id: str, info: dict) -> _ToolSection:
        self._ensure_turn()
        self._close_text()
        self._tool_counter += 1
        rec = {
            "kind": "tool",
            "id": tool_id or "tool-%d" % self._tool_counter,
            "tool": str(info.get("tool") or "tool"),
            "status": "running",
            "summary": "",
        }
        self._turn_rec["sections"].append(rec)
        section = _ToolSection(self, rec)
        self._sections.append(section)
        if tool_id:
            self._tools[tool_id] = section
        return section

    def _tool_apply_start(self, section: _ToolSection, info: dict):
        rec = section.rec
        if info.get("tool"):
            rec["tool"] = str(info["tool"])
        detail = info.get("detail") if info.get("phase") != "end" else None
        text = detail or info.get("text")
        if text:
            rec["summary"] = str(text)
        if "arguments" in info:
            rec["arguments"] = chat_format.sanitize_payload(info["arguments"])
        if info.get("nuke"):
            rec["nuke"] = True
        if info.get("phase") != "end":
            section.t0 = time.monotonic()
            section.t0_ns = info.get("time_ns") if isinstance(info.get("time_ns"), int) else None
            if rec.get("status") == "running":
                self._running.add(section)
                if not self._clock.isActive():
                    self._clock.start()

    def _tool_finish(self, section: _ToolSection, info: dict):
        rec = section.rec
        rec["status"] = "ok" if info.get("ok", True) else "error"
        if info.get("detail"):
            rec["result_summary"] = str(info["detail"])
        if "result" in info:
            rec["result"] = chat_format.sanitize_payload(info["result"])
        rec.pop("partial", None)
        end_ns = info.get("time_ns")
        if section.t0_ns is not None and isinstance(end_ns, int) and end_ns >= section.t0_ns:
            elapsed = (end_ns - section.t0_ns) / 1e9
        else:
            elapsed = time.monotonic() - section.t0
        rec["elapsed"] = round(elapsed, 3)
        self._running.discard(section)
        if not self._running:
            self._clock.stop()

    @staticmethod
    def _image_record(image: dict) -> dict:
        rec = {
            key: value
            for key, value in image.items()
            if key not in _IMAGE_SKIP and isinstance(value, (str, int, float, bool)) and value not in (None, "")
        }
        rec["kind"] = "image"
        return rec

    def _replay_assistant(self, sections: list):
        rec = {"role": "assistant", "sections": []}
        role_shown = False
        for item in sections:
            kind = item.get("kind")
            if kind in ("text", "thinking"):
                text = str(item.get("text", ""))
                srec = {"kind": kind, "text": text}
                show_role = kind == "text" and not role_shown
                role_shown = role_shown or kind == "text"
                section = _TextSection(self, srec, kind == "thinking", self._turn_title, show_role)
                section.finished = True
            elif kind == "tool":
                srec = dict(item)
                if srec.get("status") == "running":
                    srec["status"] = "interrupted"
                srec.setdefault("status", "ok")
                section = _ToolSection(self, srec)
            elif kind == "tools":
                for line in item.get("lines") or []:
                    text = str(line.get("text", ""))
                    outcome = _LEGACY_STATUS.findall(text)
                    srec = {
                        "kind": "tool",
                        "id": str(line.get("id") or ""),
                        "tool": str(line.get("tool", "tool")),
                        "summary": text,
                        "status": "error" if outcome and outcome[-1] == "error" else ("ok" if outcome else "interrupted"),
                        "legacy": True,
                    }
                    rec["sections"].append(srec)
                    self._register(_ToolSection(self, srec))
                continue
            elif kind == "image":
                delivery_id = str(item.get("delivery_id") or "")
                if delivery_id and delivery_id in self._delivery_ids:
                    continue
                if delivery_id:
                    self._delivery_ids.add(delivery_id)
                srec = self._image_record(item)
                section = _ImageSection(self, srec)
            else:
                continue
            rec["sections"].append(srec)
            self._register(section)
        if rec["sections"]:
            self._records.append(rec)

    # -- render pass ---------------------------------------------------------------------------

    def _schedule(self):
        if not self._timer.isActive():
            self._timer.start()

    def _on_timer(self):
        self._flush(RENDER_BUDGET_S)

    def _flush_now(self):
        self._timer.stop()
        self._flush(None)
        if self._queue or self._needs_relayout:
            self._schedule()

    def _flush(self, budget: float | None):
        if self._flushing or not (self._queue or self._needs_relayout):
            return
        if not self.isVisible() or self.viewport().width() < 80:
            return  # nothing is drawn while hidden; showEvent resumes the pass
        self._flushing = True
        self._programmatic += 1
        try:
            anchor = None
            if not self._follow:
                # The reading position is the character at the viewport top, kept across passes: a
                # height change that arrives between passes (late block fit, resize) moved the text
                # while the scroll value stayed, and a fresh capture would bake that move in.
                if not self._anchor_pending and (
                    self._text_anchor is None or self.verticalScrollBar().value() != self._anchor_scroll
                ):
                    self._text_anchor = self._capture_text_anchor()
                anchor = self._capture_anchor()
            deadline = None if budget is None else time.monotonic() + budget
            while self._queue:
                section = self._queue.popleft()
                self._queued.discard(section)
                try:
                    section.update()
                except Exception:  # one broken record must not stall the rest of the chat
                    _LOG.exception("chat section failed to render")
                if deadline is not None and time.monotonic() >= deadline:
                    break
            self._settle(anchor)
            if self._loading and not self._queue:
                self._loading = False
                self.viewport().setUpdatesEnabled(True)
                self.viewport().update()
        finally:
            self._programmatic -= 1
            self._flushing = False
        if self._queue:
            self._schedule()

    def _text_width(self) -> int:
        return max(self.viewport().width() - 2 * _CONTAINER_MARGIN - ROW_INSET - _BUBBLE_PADDING, 120)

    def _add_row(self, widget: QtWidgets.QWidget, side: str) -> QtWidgets.QWidget:
        row = QtWidgets.QWidget()
        row.setObjectName("chatRow")
        layout = QtWidgets.QHBoxLayout(row)
        left, right = (ROW_INSET, 0) if side == "user" else (0, ROW_INSET)
        layout.setContentsMargins(left, 0, right, 0)
        layout.addWidget(widget, 1)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        self._rows.append(row)
        # Shown now (not via the queued show Qt schedules for layout children) so the synchronous
        # layout pass of this flush already accounts for it.
        row.show()
        return row

    # -- layout / scroll (the only code that sizes the container or moves the scrollbar) -------

    def _pos(self, widget: QtWidgets.QWidget) -> int:
        return widget.mapTo(self.container, QtCore.QPoint(0, 0)).y()

    def _capture_anchor(self):
        """(widget, offset): the first row reaching into the viewport and where it sits in it."""
        value = self.verticalScrollBar().value()
        rows = self._rows
        low, high = 0, len(rows)
        while low < high:
            middle = (low + high) // 2
            row = rows[middle]
            if row.y() + row.height() > value:
                high = middle
            else:
                low = middle + 1
        if low >= len(rows):
            return None
        return rows[low], rows[low].y() - value

    def _capture_text_anchor(self):
        """The text at the viewport top: (TextBlock, character position, pixels into its line, lead).

        Row anchors keep a bubble in place but not what is read inside it; a font change rescales
        every bubble, so the character at the top of the viewport is tracked instead."""
        anchor = self._capture_anchor()
        if anchor is None:
            return None
        value = self.verticalScrollBar().value()
        limit = value + self.viewport().height()
        for row in self._rows[self._rows.index(anchor[0]) :]:
            if row.y() >= limit:
                break
            for block in row.findChildren(TextBlock):
                if not block.isVisibleTo(self.container):
                    continue
                top = self._pos(block)
                if top + block.height() <= value:
                    continue
                if top >= limit:
                    return None
                if top > value:
                    return block, 0, 0.0, top - value
                document = block.document()
                y = value - top
                position = document.documentLayout().hitTest(
                    QtCore.QPointF(0.0, float(y)), QtCore.Qt.HitTestAccuracy.FuzzyHit
                )
                if position < 0:
                    return None
                return block, position, y - self._line_top(block, position), 0
        return None

    @staticmethod
    def _line_top(block: TextBlock, position: int) -> float:
        """Document y of the line holding ``position``, as the widget paints it (tables included)."""
        document = block.document()
        cursor = QtGui.QTextCursor(document)
        cursor.setPosition(max(min(position, document.characterCount() - 1), 0))
        return float(block.cursorRect(cursor).top())

    def _restore_text_anchor(self, anchor) -> bool:
        block, position, delta, lead = anchor
        try:
            if block.parent() is None or not block.isVisibleTo(self.container):
                return False
            y = self._line_top(block, position) + delta
            target = self._pos(block) + y - lead
        except RuntimeError:  # the block was deleted (a finished section merged its segments)
            return False
        self.verticalScrollBar().setValue(int(round(target)))
        return True

    def _relayout(self):
        viewport = self.viewport()
        width, height = viewport.width(), viewport.height()
        layout = self.messages_layout
        for _ in range(4):
            layout.activate()
            content = layout.totalHeightForWidth(width) if layout.hasHeightForWidth() else layout.sizeHint().height()
            target = max(content, height)
            if self.container.width() == width and self.container.height() == target:
                break
            self.container.resize(width, target)
        self._needs_relayout = False

    def _settle(self, anchor):
        self._relayout()
        bar = self.verticalScrollBar()
        if self._follow:
            self._text_anchor = None
            self._anchor_pending = False
            bar.setValue(bar.maximum())
            return
        if not self._queue:
            self._anchor_pending = False
        restored = False
        if self._text_anchor is not None:
            restored = self._restore_text_anchor(self._text_anchor)
            if restored:
                self._anchor_scroll = bar.value()
            else:
                self._text_anchor = None
        if not restored and anchor is not None:
            widget, offset = anchor
            bar.setValue(self._pos(widget) - offset)
        if (restored or anchor is not None) and bar.value() >= bar.maximum() - 2:
            self._follow = True

    def _on_scrolled(self, value: int):
        if self._programmatic:
            return
        self._text_anchor = None
        self._anchor_pending = False
        # A user scroll (wheel, drag, keys): following resumes only at the very bottom.
        self._follow = value >= self.verticalScrollBar().maximum() - 2

    def _wheel(self, event: QtGui.QWheelEvent):
        bar = self.verticalScrollBar()
        delta = _wheel_pixels(event, bar)
        if delta:
            bar.setValue(bar.value() + delta)

    def _toggle_card(self, card, expanded: bool):
        """User expanded/collapsed a card: keep its header where it is on screen."""
        self._expanded_pref["thinking" if isinstance(card, ThinkingCard) else "tool"] = expanded
        if not self.isVisible():
            card.set_expanded(expanded)
            return
        bar = self.verticalScrollBar()
        offset = self._pos(card) - bar.value()
        self._programmatic += 1
        try:
            card.set_expanded(expanded)
            self._relayout()
            bar.setValue(self._pos(card) - offset)
            self._follow = bar.value() >= bar.maximum() - 2
        finally:
            self._programmatic -= 1

    def _tick_clock(self):
        for section in self._running:
            if section.card is not None:
                section.card.set_elapsed(section.elapsed())

    def eventFilter(self, obj, event):
        # A block whose height changed outside a render pass (late font/style/viewport change) asks
        # the container for a layout; the render pass is the only code that sizes the container.
        if (
            self._ready
            and obj is self.container
            and event.type() == QtCore.QEvent.Type.LayoutRequest
            and not self._flushing
        ):
            self._needs_relayout = True
            self._schedule()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._needs_relayout = True
        self._schedule()

    def showEvent(self, event):
        super().showEvent(event)
        self._needs_relayout = True
        self._schedule()
