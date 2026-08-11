"""Dockable Nuke UI for screenshots and a local Codex App Server thread."""

from __future__ import annotations

from pathlib import Path
import traceback

from PySide6 import QtCore, QtGui, QtWidgets

from ..app_server import (
    BACKEND_DISPLAY,
    BackendClient,
    create_backend,
    detected_backends,
    implemented_backends,
)
from ..bridge import NukeBridgeServer
from ..capture import capture_backend, capture_target
from .chat_view import ChatView


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class CodexPanelWidget(QtWidgets.QWidget):
    """Native Nuke panel with streaming Codex chat and image attachments."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NukeCodexPanel")
        self.setMinimumWidth(360)
        self.pending_images = []
        self._assistant_stream_open = False
        self._build_ui()
        self.bridge = NukeBridgeServer(self._approve_python, self)
        self.bridge.status_changed.connect(self.status.setText)
        bridge_ready = self.bridge.start()
        self._backend_key = "codex"
        self.reconnect_button.clicked.connect(lambda _checked=False: self.client.restart())
        self.client = self._build_client(self._backend_key, bridge_ready)
        self._connect_client()
        self._populate_backend_selector()
        self._refresh_backend_labels()
        QtCore.QTimer.singleShot(0, self.client.start)

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        heading_row = QtWidgets.QHBoxLayout()
        self.heading = QtWidgets.QLabel("Codex for Nuke")
        font = self.heading.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        self.heading.setFont(font)
        heading_row.addWidget(self.heading)
        heading_row.addStretch(1)
        self.backend_selector = QtWidgets.QComboBox()
        self.backend_selector.setToolTip("Coding-agent backend")
        heading_row.addWidget(self.backend_selector)
        self.new_conversation_button = QtWidgets.QToolButton()
        self.new_conversation_button.setText("New Conversation")
        self.new_conversation_button.setToolTip("Clear the chat and start a new conversation")
        heading_row.addWidget(self.new_conversation_button)
        self.reconnect_button = QtWidgets.QToolButton()
        self.reconnect_button.setText("Reconnect")
        heading_row.addWidget(self.reconnect_button)
        layout.addLayout(heading_row)

        model_row = QtWidgets.QHBoxLayout()
        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.setToolTip("Model")
        self.model_combo.setPlaceholderText("Model")
        self.model_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.model_tree = QtWidgets.QTreeView()
        self.model_tree.setHeaderHidden(True)
        self.model_tree.setRootIsDecorated(True)
        self.model_tree.setItemsExpandable(True)
        self.model_tree.setExpandsOnDoubleClick(False)
        self.model_tree.setUniformRowHeights(True)
        self.model_tree.setMinimumHeight(220)
        self.model_combo.setView(self.model_tree)
        model_row.addWidget(self.model_combo, 2)
        self.thinking_combo = QtWidgets.QComboBox()
        self.thinking_combo.setToolTip("Thinking")
        self.thinking_combo.setPlaceholderText("Thinking")
        model_row.addWidget(self.thinking_combo, 1)
        layout.addLayout(model_row)
        self._models = []
        self._settings = QtCore.QSettings("nuke-codex-panel")
        self.model_combo.setVisible(False)
        self.thinking_combo.setVisible(False)
        self.model_combo.currentIndexChanged.connect(self._on_model_selected)
        self.thinking_combo.currentIndexChanged.connect(self._on_thinking_selected)

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
        self.chat = ChatView()
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
        self.new_conversation_button.clicked.connect(self._on_new_conversation)
        self.clear_attachments_button.clicked.connect(self.clear_pending_attachments)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self).activated.connect(
            self.send_prompt
        )

    def _connect_client(self):
        self.client.status_changed.connect(self.status.setText)
        self.client.ready_changed.connect(self._on_ready)
        self.client.user_message.connect(self._show_user_message)
        self.client.turn_started.connect(self._start_assistant_message)
        self.client.agent_message_started.connect(self._start_agent_message_item)
        self.client.message_delta.connect(self._append_assistant_delta)
        self.client.turn_completed.connect(self._finish_assistant_message)
        self.client.error.connect(self._show_error)
        self.client.models_changed.connect(self._on_models_changed)
        self.client.thinking_updated.connect(self.chat.update_thinking)
        self.client.thinking_completed.connect(self.chat.complete_thinking)
        self.client.tool_updated.connect(self.chat.update_tool)

    def _disconnect_client(self):
        for sig in (
            self.client.status_changed,
            self.client.ready_changed,
            self.client.user_message,
            self.client.turn_started,
            self.client.agent_message_started,
            self.client.message_delta,
            self.client.turn_completed,
            self.client.error,
            self.client.models_changed,
            self.client.thinking_updated,
            self.client.thinking_completed,
            self.client.tool_updated,
        ):
            try:
                sig.disconnect()
            except RuntimeError:
                pass

    def _build_client(self, key: str, bridge_ready: bool) -> BackendClient:
        bridge_path = str(self.bridge.discovery_path) if bridge_ready else None
        client = create_backend(key, str(PROJECT_ROOT), self, bridge_path=bridge_path)
        assert client is not None, "default backend %s is not implemented" % key
        return client

    def switch_backend(self, key: str):
        """Switch to a different coding-agent backend; no-op if not implemented."""
        if key == self._backend_key:
            return
        new_client = create_backend(
            key, str(PROJECT_ROOT), self, bridge_path=self.client.bridge_path
        )
        if new_client is None:
            self.status.setText("%s adapter is not available yet" % key.title())
            return
        old = self.client
        self._disconnect_client()
        old.stop()
        old.deleteLater()
        self.client = new_client
        self._backend_key = key
        self._connect_client()
        self.status.setText("Switching to %s…" % new_client.display_name)
        self.client.start()
        self._refresh_backend_labels()
        self._hide_model_selectors()

    def _hide_model_selectors(self):
        self._models = []
        self.model_combo.setVisible(False)
        self.thinking_combo.setVisible(False)

    def _populate_backend_selector(self):
        self.backend_selector.blockSignals(True)
        self.backend_selector.clear()
        detected = detected_backends()
        keys = list(detected.keys()) if detected else [self._backend_key]
        for key in keys:
            label = BACKEND_DISPLAY.get(key, key.title())
            if key not in implemented_backends():
                label += " (soon)"
            self.backend_selector.addItem(label, key)
        idx = self.backend_selector.findData(self._backend_key)
        if idx >= 0:
            self.backend_selector.setCurrentIndex(idx)
        self.backend_selector.blockSignals(False)
        self.backend_selector.currentIndexChanged.connect(self._on_backend_selected)

    @QtCore.Slot(int)
    def _on_backend_selected(self, index: int):
        key = self.backend_selector.itemData(index)
        if key is None or key == self._backend_key:
            return
        self.switch_backend(key)
        # switch_backend declines unimplemented backends; snap selector back.
        if self.backend_selector.currentData() != self._backend_key:
            idx = self.backend_selector.findData(self._backend_key)
            if idx >= 0:
                self.backend_selector.blockSignals(True)
                self.backend_selector.setCurrentIndex(idx)
                self.backend_selector.blockSignals(False)

    def _refresh_backend_labels(self):
        display = self.client.display_name
        self.heading.setText("%s for Nuke" % display)
        self.prompt.setPlaceholderText("Ask %s about the current comp…" % display)
        self._update_capture_status()

    @QtCore.Slot(bool)
    def _on_ready(self, ready: bool):
        self.send_button.setEnabled(ready)
        self.send_button.setText("Send" if ready else "Connecting…")
        if ready and self.client.supports_model_select:
            self.client.request_models()
        elif not self.client.supports_model_select:
            self._hide_model_selectors()

    def _settings_key(self, name: str) -> str:
        return "%s/%s" % (self._backend_key, name)

    def _selected_model(self):
        model_id = self.model_combo.currentData()
        for model in self._models:
            if model.get("id") == model_id:
                return model
        return None

    def _find_model_index(self, model_id):
        if not model_id:
            return QtCore.QModelIndex()
        model = self.model_combo.model()

        def find(parent):
            for row in range(model.rowCount(parent)):
                index = model.index(row, 0, parent)
                if model.data(index, QtCore.Qt.ItemDataRole.UserRole) == model_id:
                    return index
                nested = find(index)
                if nested.isValid():
                    return nested
            return QtCore.QModelIndex()

        return find(QtCore.QModelIndex())

    @QtCore.Slot(list)
    def _on_models_changed(self, models: list):
        if not self.client.supports_model_select or not models:
            self._hide_model_selectors()
            return
        self._models = models
        stored_id = self._settings.value(self._settings_key("model"))
        stored_effort = self._settings.value(self._settings_key("effort"))
        self.model_combo.blockSignals(True)
        model_store = QtGui.QStandardItemModel(self.model_combo)
        default_item = QtGui.QStandardItem("Default")
        default_item.setData(None, QtCore.Qt.ItemDataRole.UserRole)
        model_store.appendRow(default_item)
        provider_groups = []
        grouped_models = {}
        provider_labels = {}
        for model_info in models:
            group_key = (
                model_info.get("provider")
                or model_info.get("provider_name")
                or ""
            )
            if group_key not in grouped_models:
                grouped_models[group_key] = []
                provider_groups.append(group_key)
                provider_labels[group_key] = (
                    model_info.get("provider_name") or model_info.get("provider")
                )
            grouped_models[group_key].append(model_info)

        for provider in provider_groups:
            provider_label = provider_labels[provider]
            if provider_label:
                provider_item = QtGui.QStandardItem(provider_label)
                provider_item.setFlags(
                    provider_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsSelectable
                )
                font = provider_item.font()
                font.setBold(True)
                provider_item.setFont(font)
                model_store.appendRow(provider_item)
            else:
                provider_item = model_store.invisibleRootItem()
            for model_info in grouped_models[provider]:
                model_item = QtGui.QStandardItem(
                    model_info.get("name") or model_info.get("id")
                )
                model_item.setData(
                    model_info.get("id"), QtCore.Qt.ItemDataRole.UserRole
                )
                provider_item.appendRow(model_item)
        self.model_combo.setModel(model_store)
        stored_index = self._find_model_index(stored_id)
        if stored_index.isValid():
            self.model_combo.setRootModelIndex(stored_index.parent())
            self.model_combo.setCurrentIndex(stored_index.row())
            self.model_combo.setRootModelIndex(QtCore.QModelIndex())
            self.model_tree.expand(stored_index.parent())
        else:
            self.model_combo.setRootModelIndex(QtCore.QModelIndex())
            self.model_combo.setCurrentIndex(0)
        self.model_combo.blockSignals(False)
        effort = self._populate_thinking(stored_effort)
        self.model_combo.setVisible(True)
        self.client.set_model(self.model_combo.currentData(), effort)

    def _populate_thinking(self, preferred):
        """Fill the thinking combo for the selected model; return chosen effort."""
        model = self._selected_model()
        efforts = (model or {}).get("efforts") or []
        self.thinking_combo.blockSignals(True)
        self.thinking_combo.clear()
        choice = None
        if efforts:
            for effort in efforts:
                self.thinking_combo.addItem(effort, effort)
            default_effort = (model or {}).get("default_effort")
            if preferred in efforts:
                choice = preferred
            elif default_effort in efforts:
                choice = default_effort
            else:
                choice = efforts[0]
            self.thinking_combo.setCurrentIndex(efforts.index(choice))
        self.thinking_combo.blockSignals(False)
        self.thinking_combo.setVisible(bool(efforts))
        return choice

    @QtCore.Slot(int)
    def _on_model_selected(self, index: int):
        model_id = self.model_combo.currentData()
        if model_id is None:
            self._settings.remove(self._settings_key("model"))
        else:
            self._settings.setValue(self._settings_key("model"), model_id)
        effort = self._populate_thinking(
            self._settings.value(self._settings_key("effort"))
        )
        if effort is None:
            self._settings.remove(self._settings_key("effort"))
        else:
            self._settings.setValue(self._settings_key("effort"), effort)
        self.client.set_model(model_id, effort)

    @QtCore.Slot(int)
    def _on_thinking_selected(self, index: int):
        effort = self.thinking_combo.itemData(index)
        if effort is None:
            self._settings.remove(self._settings_key("effort"))
        else:
            self._settings.setValue(self._settings_key("effort"), effort)
        self.client.set_model(self.model_combo.currentData(), effort)

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
        self.chat.add_user_message(text, images)

    @QtCore.Slot()
    def _start_assistant_message(self):
        self._assistant_stream_open = True
        self.chat.end_turn()

    @QtCore.Slot(str, str)
    def _start_agent_message_item(self, item_id: str, _phase: str):
        self.chat.start_agent_message(item_id or None)

    @QtCore.Slot(str)
    def _append_assistant_delta(self, delta: str):
        self.chat.append_agent_delta(delta)

    @QtCore.Slot(str)
    def _finish_assistant_message(self, status: str):
        self._assistant_stream_open = False
        self.chat.end_turn()
        self.cancel_button.setEnabled(False)
        self.send_button.setEnabled(self.client.ready)
        self.status.setText("%s connected — last turn %s" % (self.client.display_name, status))

    @QtCore.Slot(str)
    def _show_error(self, message: str):
        self.chat.add_error(message)
        self.cancel_button.setEnabled(False)
        self.send_button.setEnabled(self.client.ready)
        self.send_button.setText("Send" if self.client.ready else "Connecting…")

    @QtCore.Slot()
    def _on_new_conversation(self):
        if self._assistant_stream_open:
            return
        self.client.new_conversation()
        self.chat.clear()
        self.chat.add_divider("New conversation")

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
        if count:
            self.capture_status.setText(
                "%s pending image(s) — cleared automatically after Send" % count
            )
        elif not self.client.supports_images:
            self.capture_status.setText(
                "%s has limited image support — screenshots become file references"
                % self.client.display_name
            )
        else:
            self.capture_status.setText("No pending images")
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
