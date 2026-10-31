"""Widgets the chat view is built from: fitted text blocks, collapsible cards, image previews."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from . import chat_document, chat_format, chat_markdown
from .chat_style import ChatStyle
from .theme import apply_theme

PREVIEW_MAX_WIDTH = 720


class TextBlock(QtWidgets.QTextBrowser):
    """Selectable rich text that is exactly as tall as its content.

    The document width is set in exactly one place (``fit``), always from the viewport width (the
    widget has no padding or frame of its own, and any remaining widget-to-viewport inset is added
    to the height), and nothing listens to document-size or contents signals; height is applied
    with setFixedHeight only when it changed. Layouts therefore never query the document (no
    heightForWidth), which removes the width -> height -> width feedback that made streaming text
    jitter. The widget font and the document default font are always the chat font: Qt resets the
    document font from the widget font on every FontChange, so both are kept in step and a late
    font change refits the block.
    """

    _LOCAL_QSS = "QTextBrowser { padding: 0px; margin: 0px; border: none; }"
    _font: QtGui.QFont | None = None
    _syncing = False

    def __init__(self, wheel, width_hint: int = 320, thinking: bool = False, breaks: bool = False, parent=None):
        super().__init__(parent)
        self._wheel = wheel
        self._thinking = thinking
        self._breaks = breaks
        self._font: QtGui.QFont | None = None
        self._syncing = False
        if thinking:
            self.setObjectName("thinkingText")
        self._mode = "md"
        self._source = ""
        self._style: ChatStyle | None = None
        self._shown_key = None
        self._base_font = QtGui.QFont(self.font())
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._open_link)
        self.setStyleSheet(self._LOCAL_QSS)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setViewportMargins(0, 0, 0, 0)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.document().setDocumentMargin(0)
        self.viewport().installEventFilter(self)
        self.resize(max(width_hint, 40), 24)
        self.setFixedHeight(24)

    @property
    def source(self) -> str:
        return self._source

    # -- content ---------------------------------------------------------------------------

    def set_markdown(self, source: str, style: ChatStyle):
        self._mode = "md"
        self._source = source
        self._show(style)

    def set_html(self, markup: str, style: ChatStyle):
        self._mode = "html"
        self._source = markup
        self._show(style)

    def restyle(self, style: ChatStyle):
        self._show(style, force=True)

    def _show(self, style: ChatStyle, force: bool = False):
        key = (self._mode, self._source)
        if not force and key == self._shown_key and style is self._style:
            return
        markdown_style = style.thinking if self._thinking else style.markdown
        document = self.document()
        style_changed = style is not self._style
        if style_changed:
            document.setDefaultStyleSheet(markdown_style.stylesheet())
            font = QtGui.QFont(self._base_font)
            font.setPointSizeF(float(style.font_pt))
            self._font = font
            self._apply_font()
            self._style = style
        if self._mode == "md":
            chat_document.load_markdown(document, self._source, markdown_style, self._breaks)
        else:
            document.setHtml(self._source)
        self._shown_key = key
        self.fit(force=style_changed or force)

    def _apply_font(self):
        self._syncing = True
        try:
            self.setFont(self._font)
            self.document().setDefaultFont(self.font())
        finally:
            self._syncing = False

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() != QtCore.QEvent.Type.FontChange or self._syncing or self._font is None:
            return
        if abs(self.font().pointSizeF() - self._font.pointSizeF()) > 0.01:
            self._apply_font()
            self.fit(force=True)

    # -- geometry ----------------------------------------------------------------------------

    def fit(self, force: bool = False):
        viewport = self.viewport()
        width = viewport.width()
        if width < 20:
            return
        document = self.document()
        if force or abs(document.textWidth() - width) > 0.5:
            document.setTextWidth(width)
        inset = max(self.height() - viewport.height(), 0)
        height = max(int(math.ceil(document.size().height())), 1) + inset
        if height != self.height():
            self.setFixedHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    # -- input ---------------------------------------------------------------------------------

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QtCore.QEvent.Type.Resize and obj is self.viewport():
            # The viewport is what the text is laid out against: refit whenever it really changes size.
            self.fit()
        elif kind == QtCore.QEvent.Type.Wheel and self._wheel is not None:
            # Bubbles always fit their content, so QTextBrowser would swallow wheel events; hand
            # them to the chat's single scroll path instead.
            self._wheel(event)
            return True
        return super().eventFilter(obj, event)

    def loadResource(self, resource_type, name):
        # Never load anything (no remote URLs, no local file: URLs) for untrusted chat content.
        return None

    def _open_link(self, url: QtCore.QUrl):
        target = chat_markdown.safe_url(url.toString())
        if target:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(target))


class ElidedLabel(QtWidgets.QLabel):
    """Single-line plain-text label that elides to whatever width its layout gives it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full = ""
        self.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)

    def set_full_text(self, text: str):
        if text == self._full:
            return
        self._full = text
        self._elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self):
        width = self.width()
        shown = self._full
        if width > 8:
            shown = self.fontMetrics().elidedText(self._full, QtCore.Qt.TextElideMode.ElideRight, width)
        if shown != self.text():
            self.setText(shown)
        self.setToolTip(self._full if shown != self._full else "")


class ClickableHeader(QtWidgets.QWidget):
    clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cardHeader")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def set_state(widget: QtWidgets.QWidget, state: str):
    """Dynamic QSS property; repolishes only when it changed."""
    if widget.property("state") == state:
        return
    widget.setProperty("state", state)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class Card(QtWidgets.QFrame):
    """Collapsible bubble: a clickable header row and a lazily built body."""

    def __init__(self, object_name: str, on_toggle, parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self._on_toggle = on_toggle
        self._expanded = False
        self.body_widget: QtWidgets.QWidget | None = None
        self._outer = QtWidgets.QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)
        self.header = ClickableHeader()
        self.header_layout = QtWidgets.QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(10, 6, 10, 6)
        self.header_layout.setSpacing(8)
        self.arrow = QtWidgets.QLabel("\u25b8")
        self.arrow.setObjectName("cardArrow")
        self.header_layout.addWidget(self.arrow)
        self._outer.addWidget(self.header)
        self.header.clicked.connect(self._clicked)

    @property
    def expanded(self) -> bool:
        return self._expanded

    def build_body(self) -> QtWidgets.QWidget:  # pragma: no cover - subclass hook
        raise NotImplementedError

    def on_expanded(self, expanded: bool):
        """Subclass hook: fill the body when it becomes visible."""

    def _clicked(self):
        self._on_toggle(self, not self._expanded)

    def set_expanded(self, expanded: bool):
        if expanded and self.body_widget is None:
            self.body_widget = self.build_body()
            self._outer.addWidget(self.body_widget)
        if self.body_widget is not None:
            self.body_widget.setVisible(expanded)
        self._expanded = expanded
        self.arrow.setText("\u25be" if expanded else "\u25b8")
        self.on_expanded(expanded)


class ThinkingCard(Card):
    def __init__(self, on_toggle, parent=None):
        super().__init__("thinkingBubble", on_toggle, parent)
        title = QtWidgets.QLabel("Thinking")
        title.setObjectName("thinkingTitle")
        self.header_layout.addWidget(title)
        self.header_layout.addStretch(1)
        self.body_layout: QtWidgets.QVBoxLayout | None = None
        self.expanded_hook = None

    def build_body(self) -> QtWidgets.QWidget:
        body = QtWidgets.QWidget()
        body.setObjectName("cardBody")
        self.body_layout = QtWidgets.QVBoxLayout(body)
        self.body_layout.setContentsMargins(12, 0, 12, 8)
        self.body_layout.setSpacing(0)
        return body

    def on_expanded(self, expanded: bool):
        if expanded and self.expanded_hook is not None:
            self.expanded_hook()


class ToolCard(Card):
    """One tool call: status/elapsed header, formatted arguments and result in the body."""

    def __init__(self, wheel, on_toggle, parent=None):
        super().__init__("toolBubble", on_toggle, parent)
        self._wheel = wheel
        self._rec: dict = {}
        self._style: ChatStyle | None = None
        self._filled_version = -1
        self._filled_style = None
        self._version = 0
        self.title = QtWidgets.QLabel()
        self.title.setObjectName("cardTitle")
        self.title.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.summary = ElidedLabel()
        self.summary.setObjectName("toolSummary")
        self.status = QtWidgets.QLabel()
        self.status.setObjectName("toolStatus")
        self.elapsed = QtWidgets.QLabel()
        self.elapsed.setObjectName("toolElapsed")
        self.elapsed.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.header_layout.addWidget(self.title)
        self.header_layout.addWidget(self.summary, 1)
        self.header_layout.addWidget(self.status)
        self.header_layout.addWidget(self.elapsed)
        self.detail: TextBlock | None = None
        self._copy_args: QtWidgets.QToolButton | None = None
        self._copy_result: QtWidgets.QToolButton | None = None

    # -- header ------------------------------------------------------------------------------

    def apply(self, rec: dict, style: ChatStyle, elapsed_s: float | None, version: int = 0):
        self._rec = rec
        self._style = style
        self._version = version
        tool = rec.get("tool", "tool")
        self.title.setText(chat_format.display_name(tool))
        self.title.setToolTip(tool)
        status = rec.get("status", "running")
        summary = rec.get("summary") or ""
        if status == "error" and rec.get("result_summary"):
            summary = "%s \u2014 %s" % (summary, rec["result_summary"]) if summary else rec["result_summary"]
        self.summary.set_full_text(summary)
        self.status.setText(chat_format.STATUS_LABELS.get(status, status))
        set_state(self.status, status)
        set_state(self, status)
        self.set_elapsed(elapsed_s)
        if self._expanded:
            self._fill()

    def set_elapsed(self, seconds: float | None):
        text = chat_format.elapsed_text(seconds)
        if text != self.elapsed.text():
            self.elapsed.setText(text)

    # -- body ----------------------------------------------------------------------------------

    def build_body(self) -> QtWidgets.QWidget:
        body = QtWidgets.QWidget()
        body.setObjectName("cardBody")
        layout = QtWidgets.QVBoxLayout(body)
        layout.setContentsMargins(10, 0, 10, 8)
        layout.setSpacing(4)
        self.detail = TextBlock(self._wheel, max(self.width() - 24, 120))
        layout.addWidget(self.detail)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._copy_args = self._copy_button("Copy arguments", chat_format.arguments_copy_text)
        self._copy_result = self._copy_button("Copy result", chat_format.result_copy_text)
        row.addWidget(self._copy_args)
        row.addWidget(self._copy_result)
        row.addStretch(1)
        layout.addLayout(row)
        return body

    def _copy_button(self, label: str, producer) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setObjectName("copyButton")
        button.setText(label)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        def copy():
            QtWidgets.QApplication.clipboard().setText(producer(self._rec))
            button.setText("Copied")
            QtCore.QTimer.singleShot(1200, lambda: button.setText(label))

        button.clicked.connect(copy)
        return button

    def on_expanded(self, expanded: bool):
        if expanded:
            self._fill()

    def _fill(self):
        if self.detail is None or self._style is None:
            return
        rec = self._rec
        if self._version == self._filled_version and self._style is self._filled_style:
            return
        self._filled_version = self._version
        self._filled_style = self._style
        self.detail.set_html(chat_format.tool_body_html(rec, self._style.markdown), self._style)
        if self._copy_result is not None:
            self._copy_result.setVisible(rec.get("status") in ("ok", "error", "interrupted"))
            self._copy_args.setVisible(rec.get("arguments") not in (None, "", {}, []))


class _ImageViewer(QtWidgets.QDialog):
    """Full-resolution view of one delivered image: 100% in a scroll area, or fitted to the window."""

    def __init__(self, path: str, title: str, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.setWindowTitle(title)
        self.resize(1100, 760)
        self._image = QtGui.QImage(path)
        layout = QtWidgets.QVBoxLayout(self)
        self._fit = QtWidgets.QCheckBox("Fit to window")
        self._fit.setChecked(False)
        self._fit.toggled.connect(self._apply)
        layout.addWidget(self._fit)
        self._label = QtWidgets.QLabel()
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidget(self._label)
        self._scroll.setWidgetResizable(False)
        layout.addWidget(self._scroll, 1)
        self._apply()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit.isChecked():
            self._apply()

    def _apply(self, *_args):
        if self._image.isNull():
            self._label.setText("The image file could not be read.")
            self._label.adjustSize()
            return
        if self._fit.isChecked():
            pixmap = QtGui.QPixmap.fromImage(
                self._image.scaled(
                    self._scroll.viewport().size(),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            pixmap = QtGui.QPixmap.fromImage(self._image)
        self._label.setPixmap(pixmap)
        self._label.resize(pixmap.size())


class _PreviewCanvas(QtWidgets.QWidget):
    """Downscaled picture of a delivered PNG; decodes lazily (first paint) and keeps only the thumbnail."""

    clicked = QtCore.Signal()

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path
        reader = QtGui.QImageReader(path)
        size = reader.size()
        self.natural = size if size.isValid() else QtCore.QSize()
        self._thumb: QtGui.QImage | None = None
        self._failed = not size.isValid()
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMaximumWidth(
            min(PREVIEW_MAX_WIDTH, self.natural.width()) if self.natural.isValid() else PREVIEW_MAX_WIDTH
        )

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        if not self.natural.isValid() or self.natural.width() <= 0:
            return 24
        width = min(width, self.maximumWidth())
        return max(1, round(width * self.natural.height() / self.natural.width()))

    def sizeHint(self) -> QtCore.QSize:
        width = self.maximumWidth()
        return QtCore.QSize(width, self.heightForWidth(width))

    def _load(self):
        reader = QtGui.QImageReader(self._path)
        reader.setScaledSize(
            self.natural.scaled(PREVIEW_MAX_WIDTH, 100000, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            if self.natural.width() > PREVIEW_MAX_WIDTH
            else self.natural
        )
        image = reader.read()
        self._failed = image.isNull()
        self._thumb = None if self._failed else image

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        if self._thumb is None and not self._failed:
            self._load()
        if self._thumb is None:
            painter.setPen(QtGui.QColor("#c89090"))
            painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "image unreadable")
            return
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(self.rect(), self._thumb)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class DeliveredImage(QtWidgets.QWidget):
    """An image handed to the agent: preview + caption; click opens the full-resolution file."""

    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self._record = record
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        self.setObjectName("deliveredImage")
        asset = record.get("asset")
        caption = record.get("caption") or "Image delivered to the agent"
        if asset and Path(asset).is_file():
            canvas = _PreviewCanvas(asset)
            canvas.setToolTip("Click to open the full-resolution image")
            canvas.clicked.connect(self._open_full)
            layout.addWidget(canvas, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        else:
            reason = record.get("error") or "the stored image file is missing"
            caption = "%s \u2014 preview unavailable: %s" % (caption, reason)
        label = QtWidgets.QLabel(caption)
        label.setObjectName("imageCaption")
        label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        details = []
        if record.get("sha256"):
            details.append("sha256 %s" % str(record["sha256"])[:12])
        if record.get("bytes"):
            details.append("%.1f KB" % (float(record["bytes"]) / 1024.0))
        if record.get("delivery_id"):
            details.append("delivery %s" % str(record["delivery_id"])[:8])
        if details:
            label.setToolTip(" \u00b7 ".join(details))
        layout.addWidget(label)

    def _open_full(self):
        viewer = _ImageViewer(
            self._record["asset"], self._record.get("caption") or "Delivered image", self.window()
        )
        viewer.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        viewer.show()
