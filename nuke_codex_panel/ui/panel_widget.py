"""Dockable Nuke UI for screenshots and a local Codex App Server thread."""

from __future__ import annotations

from pathlib import Path
import traceback

from PySide6 import QtCore, QtGui, QtWidgets

from ..app_server import CodexAppServerClient
from ..bridge import NukeBridgeServer
from ..capture import capture_backend, capture_target


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class CodexPanelWidget(QtWidgets.QWidget):
    """Native Nuke panel with streaming Codex chat and image attachments."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NukeCodexPanel")
        self.setMinimumWidth(360)
        self.pending_images = []
        self._assistant_stream_open = False
        self._assistant_item_id = None
        self._assistant_item_seen = False
        self._build_ui()
        self.bridge = NukeBridgeServer(self._approve_python, self)
        self.bridge.status_changed.connect(self.status.setText)
        bridge_ready = self.bridge.start()
        self.client = CodexAppServerClient(
            str(PROJECT_ROOT),
            self,
            bridge_path=str(self.bridge.discovery_path) if bridge_ready else None,
        )
        self._connect_client()
        QtCore.QTimer.singleShot(0, self.client.start)

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        heading_row = QtWidgets.QHBoxLayout()
        heading = QtWidgets.QLabel("Codex for Nuke")
        font = heading.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        heading.setFont(font)
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        self.reconnect_button = QtWidgets.QToolButton()
        self.reconnect_button.setText("Reconnect")
        heading_row.addWidget(self.reconnect_button)
        layout.addLayout(heading_row)

        self.status = QtWidgets.QLabel("Preparing Codex…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.trusted_python = QtWidgets.QCheckBox("Trusted Python session")
        self.trusted_python.setToolTip(
            "When enabled, Codex Python runs without a confirmation dialog."
        )
        self.trusted_python.setChecked(False)
        layout.addWidget(self.trusted_python)

        capture_row = QtWidgets.QHBoxLayout()
        for label, target in (
            ("Viewer", "viewer"),
            ("Node Graph", "nodegraph"),
            ("Full UI", "interface"),
        ):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, value=target: self.capture(value))
            capture_row.addWidget(button)
        layout.addLayout(capture_row)

        attachment_row = QtWidgets.QHBoxLayout()
        self.capture_status = QtWidgets.QLabel("No pending images")
        self.capture_status.setWordWrap(True)
        attachment_row.addWidget(self.capture_status, 1)
        self.clear_attachments_button = QtWidgets.QToolButton()
        self.clear_attachments_button.setText("Clear all")
        self.clear_attachments_button.setEnabled(False)
        attachment_row.addWidget(self.clear_attachments_button)
        layout.addLayout(attachment_row)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.chat = QtWidgets.QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setAcceptRichText(False)
        self.chat.setPlaceholderText("Codex messages will appear here.")
        splitter.addWidget(self.chat)

        self.history = QtWidgets.QListWidget()
        self.history.setAlternatingRowColors(True)
        self.history.setMaximumHeight(170)
        self.history.setVisible(False)
        splitter.addWidget(self.history)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.prompt = QtWidgets.QPlainTextEdit()
        self.prompt.setPlaceholderText("Ask Codex about the current comp…")
        self.prompt.setMaximumHeight(110)
        layout.addWidget(self.prompt)

        action_row = QtWidgets.QHBoxLayout()
        self.send_button = QtWidgets.QPushButton("Connecting…")
        self.send_button.setEnabled(False)
        action_row.addWidget(self.send_button, 1)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        action_row.addWidget(self.cancel_button)
        layout.addLayout(action_row)

        self.send_button.clicked.connect(self.send_prompt)
        self.cancel_button.clicked.connect(lambda: self.client.interrupt())
        self.clear_attachments_button.clicked.connect(self.clear_pending_attachments)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self).activated.connect(
            self.send_prompt
        )

    def _connect_client(self):
        self.reconnect_button.clicked.connect(self.client.restart)
        self.client.status_changed.connect(self.status.setText)
        self.client.ready_changed.connect(self._on_ready)
        self.client.user_message.connect(self._show_user_message)
        self.client.turn_started.connect(self._start_assistant_message)
        self.client.agent_message_started.connect(self._start_agent_message_item)
        self.client.message_delta.connect(self._append_assistant_delta)
        self.client.turn_completed.connect(self._finish_assistant_message)
        self.client.error.connect(self._show_error)

    @QtCore.Slot(bool)
    def _on_ready(self, ready: bool):
        self.send_button.setEnabled(ready)
        self.send_button.setText("Send" if ready else "Connecting…")

    @QtCore.Slot()
    def send_prompt(self):
        text = self.prompt.toPlainText().strip()
        if not text:
            return
        if self.client.send_turn(text, self.pending_images):
            self.prompt.clear()
            self.clear_pending_attachments()
            self.send_button.setEnabled(False)
            self.cancel_button.setEnabled(True)

    @QtCore.Slot(str, list)
    def _show_user_message(self, text: str, images: list):
        suffix = "\n[%s image(s) attached]" % len(images) if images else ""
        self._append_block("You", text + suffix)

    @QtCore.Slot()
    def _start_assistant_message(self):
        cursor = self.chat.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        if not self.chat.document().isEmpty():
            cursor.insertText("\n\n")
        cursor.insertText("Codex:\n")
        self.chat.setTextCursor(cursor)
        self._assistant_stream_open = True
        self._assistant_item_id = None
        self._assistant_item_seen = False

    @QtCore.Slot(str, str)
    def _start_agent_message_item(self, item_id: str, _phase: str):
        if not self._assistant_stream_open:
            self._start_assistant_message()
        if item_id and item_id == self._assistant_item_id:
            return
        cursor = self.chat.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        if self._assistant_item_seen:
            cursor.insertText("\n\n")
        self.chat.setTextCursor(cursor)
        self._assistant_item_id = item_id
        self._assistant_item_seen = True

    @QtCore.Slot(str)
    def _append_assistant_delta(self, delta: str):
        if not self._assistant_stream_open:
            self._start_assistant_message()
        if not self._assistant_item_seen:
            self._assistant_item_seen = True
        cursor = self.chat.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertText(delta)
        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()

    @QtCore.Slot(str)
    def _finish_assistant_message(self, status: str):
        self._assistant_stream_open = False
        self._assistant_item_id = None
        self._assistant_item_seen = False
        self.cancel_button.setEnabled(False)
        self.send_button.setEnabled(self.client.ready)
        self.status.setText("Codex connected — last turn %s" % status)

    @QtCore.Slot(str)
    def _show_error(self, message: str):
        self._append_block("Error", message)
        self.cancel_button.setEnabled(False)
        self.send_button.setEnabled(self.client.ready)
        self.send_button.setText("Send" if self.client.ready else "Connecting…")

    def _append_block(self, role: str, text: str):
        cursor = self.chat.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        if not self.chat.document().isEmpty():
            cursor.insertText("\n\n")
        cursor.insertText("%s:\n%s" % (role, text))
        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()

    @QtCore.Slot(str)
    def capture(self, target: str):
        try:
            path = capture_target(target)
        except Exception as exc:
            self.status.setText("Capture failed: %s" % exc)
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Nuke Codex capture failed")
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            dialog.setText("Could not capture the Nuke %s." % target)
            dialog.setInformativeText("%s: %s" % (type(exc).__name__, exc))
            dialog.setDetailedText(traceback.format_exc())
            dialog.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            dialog.open()
            return

        path_string = str(path)
        self.pending_images.append(path_string)
        label = target.replace("nodegraph", "node graph")
        item = QtWidgets.QListWidgetItem()
        item.setData(QtCore.Qt.ItemDataRole.UserRole, path_string)
        item.setToolTip(path_string)
        self.history.insertItem(0, item)

        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(4, 3, 4, 3)
        thumbnail = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(path_string)
        thumbnail.setPixmap(
            pixmap.scaled(
                120,
                68,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        )
        thumbnail.setFixedSize(124, 72)
        row_layout.addWidget(thumbnail)
        description = QtWidgets.QLabel("%s\n%s" % (label.title(), path.name))
        description.setWordWrap(True)
        row_layout.addWidget(description, 1)
        remove_button = QtWidgets.QToolButton()
        remove_button.setText("×")
        remove_button.setToolTip("Remove this attachment")
        remove_button.clicked.connect(
            lambda _checked=False, value=path_string, list_item=item: self.remove_attachment(
                value, list_item
            )
        )
        row_layout.addWidget(remove_button)
        item.setSizeHint(row.sizeHint())
        self.history.setItemWidget(item, row)
        self.history.setVisible(True)
        backend = capture_backend(path)
        self.status.setText(
            "Captured %s via %s; it will be attached to the next prompt."
            % (label, backend)
        )
        self._update_capture_status()

    def remove_attachment(self, path: str, item):
        self.pending_images = [value for value in self.pending_images if value != path]
        row = self.history.row(item)
        if row >= 0:
            self.history.takeItem(row)
        self._update_capture_status()

    @QtCore.Slot()
    def clear_pending_attachments(self):
        self.pending_images = []
        self.history.clear()
        self._update_capture_status()

    def _update_capture_status(self):
        count = len(self.pending_images)
        self.capture_status.setText(
            "%s pending image(s) — cleared automatically after Send" % count
            if count
            else "No pending images"
        )
        self.clear_attachments_button.setEnabled(bool(count))
        self.history.setVisible(bool(count))

    def _approve_python(self, code: str) -> bool:
        if self.trusted_python.isChecked():
            return True
        preview = code if len(code) <= 1200 else code[:1200] + "\n…"
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle("Codex requests Nuke Python execution")
        dialog.setIcon(QtWidgets.QMessageBox.Icon.Question)
        dialog.setText("Run this Python inside the current Nuke session?")
        dialog.setInformativeText(preview)
        dialog.setDetailedText(code)
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No
        )
        dialog.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
        return dialog.exec() == QtWidgets.QMessageBox.StandardButton.Yes

    def closeEvent(self, event):
        self.bridge.stop()
        self.client.stop()
        super().closeEvent(event)
