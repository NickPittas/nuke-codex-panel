"""Dockable Nuke UI for screenshots and a local agent harness thread."""

from __future__ import annotations

from pathlib import Path
import traceback

from PySide6 import QtCore, QtGui, QtWidgets

from ..bridge import NukeBridgeServer
from ..capture import capture_backend, capture_target
from ..chat_store import ChatStore
from ..harnesses import create_harness, harness_label, harness_names
from .chat_view import ChatView


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _format_tokens(value) -> str:
    if not value:
        return "0"
    if value >= 1_000_000:
        return "%.1fM" % (value / 1_000_000.0)
    if value >= 1000:
        return "%.1fk" % (value / 1000.0)
    return str(int(value))


class CodexPanelWidget(QtWidgets.QWidget):
    """Native Nuke panel with streaming agent chat and image attachments."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NukeCodexPanel")
        self.setMinimumWidth(360)
        self.pending_images = []
        self.client = None
        self.store = None
        self.project_path = self._resolve_project_path()
        self._syncing_combos = False
        self.settings = QtCore.QSettings("nuke-codex-panel", "panel")
        self._models_signature = None
        self._applied_model = None
        self._build_ui()
        self.bridge = NukeBridgeServer(self._approve_python, self)
        self.bridge.status_changed.connect(self.status.setText)
        bridge_ready = self.bridge.start()
        self.bridge_path = str(self.bridge.discovery_path) if bridge_ready else None
        harness = str(self.settings.value("harness", "codex"))
        if harness not in harness_names():
            # Never brick the panel on a stale or hand-edited setting.
            harness = harness_names()[0]
            self.settings.setValue("harness", harness)
        self.harness_combo.setCurrentText(harness_label(harness))
        self._switch_harness(harness)

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        heading_row = QtWidgets.QHBoxLayout()
        heading = QtWidgets.QLabel("Agent for Nuke")
        font = heading.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        heading.setFont(font)
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        self.new_chat_button = QtWidgets.QToolButton()
        self.new_chat_button.setText("New chat")
        self.new_chat_button.setToolTip(
            "Archive this transcript and start with an empty model context"
        )
        heading_row.addWidget(self.new_chat_button)
        self.settings_button = QtWidgets.QToolButton()
        self.settings_button.setText("Settings…")
        heading_row.addWidget(self.settings_button)
        self.reconnect_button = QtWidgets.QToolButton()
        self.reconnect_button.setText("Reconnect")
        heading_row.addWidget(self.reconnect_button)
        layout.addLayout(heading_row)

        harness_row = QtWidgets.QHBoxLayout()
        harness_row.addWidget(QtWidgets.QLabel("Harness"))
        self.harness_combo = QtWidgets.QComboBox()
        for name in harness_names():
            self.harness_combo.addItem(harness_label(name), name)
        harness_row.addWidget(self.harness_combo, 1)
        harness_row.addWidget(QtWidgets.QLabel("Model"))
        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.model_combo.setMinimumContentsLength(12)
        # Provider-grouped dropdown: bold, non-selectable provider rows with
        # their models nested underneath.
        self.model_tree = QtWidgets.QTreeView()
        self.model_tree.setHeaderHidden(True)
        self.model_tree.setRootIsDecorated(True)
        self.model_tree.setItemsExpandable(True)
        self.model_tree.setExpandsOnDoubleClick(False)
        self.model_tree.setUniformRowHeights(True)
        self.model_tree.setMinimumHeight(220)
        self.model_combo.setView(self.model_tree)
        harness_row.addWidget(self.model_combo, 2)
        harness_row.addWidget(QtWidgets.QLabel("Think"))
        self.thinking_combo = QtWidgets.QComboBox()
        harness_row.addWidget(self.thinking_combo, 1)
        layout.addLayout(harness_row)

        self.status = QtWidgets.QLabel("Preparing agent…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        usage_row = QtWidgets.QHBoxLayout()
        self.usage_label = QtWidgets.QLabel("context: —")
        self.usage_label.setObjectName("usageLabel")
        usage_row.addWidget(self.usage_label)
        self.usage_bar = QtWidgets.QProgressBar()
        self.usage_bar.setRange(0, 100)
        self.usage_bar.setTextVisible(False)
        self.usage_bar.setFixedHeight(6)
        self.usage_bar.setToolTip("Model context window usage")
        usage_row.addWidget(self.usage_bar, 1)
        layout.addLayout(usage_row)

        self.trusted_python = QtWidgets.QCheckBox("Trusted Python session")
        self.trusted_python.setToolTip(
            "When enabled, agent Python runs without a confirmation dialog."
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
        self.prompt.setPlaceholderText("Ask the agent about the current comp…")
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
        self.cancel_button.clicked.connect(lambda: self.client and self.client.interrupt())
        self.clear_attachments_button.clicked.connect(self.clear_pending_attachments)
        self.harness_combo.activated.connect(self._on_harness_picked)
        self.model_combo.activated.connect(self._on_model_picked)
        self.thinking_combo.activated.connect(self._on_thinking_picked)
        self.reconnect_button.clicked.connect(
            lambda: self.client and self.client.restart()
        )
        self.settings_button.clicked.connect(self._open_settings)
        self.new_chat_button.clicked.connect(self._new_chat)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self).activated.connect(
            self.send_prompt
        )

    # -- harness / model / thinking selection --------------------------------

    def _on_harness_picked(self, index: int):
        self._switch_harness(self.harness_combo.itemData(index))

    def _resolve_project_path(self) -> str:
        """Identify the project by its Nuke script, falling back to the cwd."""
        try:
            import nuke

            name = nuke.root().name()
            if name and name != "Root":
                return str(Path(name))
        except Exception:
            pass
        return str(Path.cwd())

    def _switch_harness(self, name: str):
        if self.client is not None:
            if self.client.name == name:
                return
            self._save_chat()
            self.client.stop()
            self.client.deleteLater()
        self.store = ChatStore(self.project_path, name)
        self.client = create_harness(name, str(PROJECT_ROOT), self, self.bridge_path)
        self.client.session_dir = self.store.dir / "sessions"
        saved = self.store.load()
        self._models_signature = None
        self._applied_model = None
        self.thinking_combo.clear()
        self.chat.clear()
        if saved["messages"]:
            self.chat.load_records(saved["messages"])
        self._update_usage({})
        self._connect_client()
        self.settings.setValue("harness", name)
        self.send_button.setEnabled(False)
        self.send_button.setText("Connecting…")
        state = saved["session"]
        if state:
            QtCore.QTimer.singleShot(0, lambda s=state: self._offer_resume(s))
        QtCore.QTimer.singleShot(0, self.client.start)

    def _offer_resume(self, state: dict):
        """Ask before resuming a stored session, per project."""
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Continue previous conversation?")
        box.setText(
            "This project has a previous %s conversation."
            % harness_label(self.client.name)
        )
        box.setInformativeText(
            "\u201cContinue\u201d restores the chat history and its context. Nothing is "
            "executed, and the model will not act until you send a message. "
            "\u201cStart fresh\u201d keeps the history visible but gives the model an "
            "empty context."
        )
        resume_button = box.addButton(
            "Continue conversation", QtWidgets.QMessageBox.ButtonRole.AcceptRole
        )
        box.addButton("Start fresh", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        box.finished.connect(
            lambda _result: self._apply_resume(box.clickedButton() is resume_button, state)
        )
        box.open()

    def _apply_resume(self, resume: bool, state: dict):
        if not resume or self.client is None:
            return
        self.client.resume_session(state)
        self.status.setText("Resuming %s session…" % self.client.label)
        self.client.restart()

    def _save_chat(self):
        if self.store is None or self.client is None:
            return
        try:
            self.store.save(self.chat.records(), self.client.session_state())
        except OSError as exc:
            self.status.setText("Could not save this chat: %s" % exc)

    @QtCore.Slot()
    def _new_chat(self):
        if self.client is None or self.store is None:
            return
        archived = None
        try:
            archived = self.store.archive()
        except OSError as exc:
            self.status.setText("Could not archive the old chat: %s" % exc)
        self.chat.clear()
        self.client.new_session()
        self._update_usage({})
        self._save_chat()
        self.status.setText(
            "New chat — previous chat archived to %s" % archived.name
            if archived
            else "New chat started"
        )

    @QtCore.Slot(dict)
    def _update_usage(self, info: dict):
        used = info.get("used")
        window = info.get("window")
        percent = info.get("percent")
        if used and window:
            percent = percent if percent is not None else used / window * 100.0
            self.usage_label.setText(
                "context %s / %s (%.0f%%)" % (_format_tokens(used), _format_tokens(window), percent)
            )
            self.usage_bar.setValue(int(percent))
        elif used:
            self.usage_label.setText("context %s used" % _format_tokens(used))
            self.usage_bar.setValue(0)
        else:
            self.usage_label.setText("context: —")
            self.usage_bar.setValue(0)
        detail = [
            "input %s" % _format_tokens(info.get("input")),
            "cached %s" % _format_tokens(info.get("cached")),
            "output %s" % _format_tokens(info.get("output")),
        ]
        if info.get("cost"):
            detail.append("cost $%.4f" % info["cost"])
        self.usage_label.setToolTip("Session totals: " + ", ".join(detail))

    def _connect_client(self):
        client = self.client
        client.status_changed.connect(self.status.setText)
        client.ready_changed.connect(self._on_ready)
        client.user_message.connect(self._show_user_message)
        client.turn_started.connect(self._start_assistant_message)
        client.thinking_delta.connect(self.chat.append_thinking)
        client.message_delta.connect(self.chat.append_delta)
        client.tool_event.connect(self.chat.add_tool_event)
        client.turn_completed.connect(self._finish_assistant_message)
        client.error.connect(self._show_error)
        client.usage_changed.connect(self._update_usage)
        client.models_changed.connect(self._on_models_changed)

    def _open_settings(self):
        from .settings_dialog import HarnessSettingsDialog

        dialog = HarnessSettingsDialog(self)
        dialog.exec()
        if self.client is not None and not self.client.ready:
            self.client.restart()

    def _on_models_changed(self, models: list):
        if self.model_combo.view().isVisible():
            # Rebuilding under an open popup is what made the dropdown flicker;
            # try again once the user has finished choosing.
            QtCore.QTimer.singleShot(200, lambda m=models: self._on_models_changed(m))
            return
        signature = [
            (m["id"], m.get("label"), tuple(m.get("efforts") or [])) for m in models
        ]
        if signature == self._models_signature:
            return  # same list, no need to disturb the selection
        self._models_signature = signature
        self._syncing_combos = True
        try:
            store = QtGui.QStandardItemModel(self.model_combo)
            groups: dict[str, list] = {}
            order: list[str] = []
            for model in models:
                provider = (
                    model["id"].split("/", 1)[0]
                    if "/" in model["id"]
                    else (self.client.label if self.client else "Models")
                )
                if provider not in groups:
                    groups[provider] = []
                    order.append(provider)
                groups[provider].append(model)
            for provider in order:
                header = QtGui.QStandardItem(provider)
                header.setFlags(header.flags() & ~QtCore.Qt.ItemFlag.ItemIsSelectable)
                font = header.font()
                font.setBold(True)
                header.setFont(font)
                store.appendRow(header)
                for model in groups[provider]:
                    item = QtGui.QStandardItem(model.get("label") or model["id"])
                    item.setData(model, QtCore.Qt.ItemDataRole.UserRole)
                    header.appendRow(item)
            self.model_combo.setModel(store)
            saved = str(self.settings.value("model/%s" % self.client.name, ""))
            wanted = saved or getattr(self.client, "current_model", None) or ""
            index = self._find_model_index(wanted)
            if not index.isValid():
                index = self._first_model_index()
            if index.isValid():
                self.model_combo.setRootModelIndex(index.parent())
                self.model_combo.setCurrentIndex(index.row())
                self.model_combo.setRootModelIndex(QtCore.QModelIndex())
                self.model_tree.expand(index.parent())
            else:
                self.model_combo.setRootModelIndex(QtCore.QModelIndex())
                self.model_combo.setCurrentIndex(-1)
            self._apply_current_model(save=False)
        finally:
            self._syncing_combos = False

    def _first_model_index(self):
        """First selectable model leaf, for the deterministic default pick."""
        model = self.model_combo.model()
        if model is None:
            return QtCore.QModelIndex()
        for row in range(model.rowCount()):
            parent = model.index(row, 0)
            if model.rowCount(parent):
                return model.index(0, 0, parent)
            if isinstance(model.data(parent, QtCore.Qt.ItemDataRole.UserRole), dict):
                return parent
        return QtCore.QModelIndex()

    def _find_model_index(self, model_id: str):
        """Locate a model id inside the grouped combo model."""
        model = self.model_combo.model()
        if model is None or not model_id:
            return QtCore.QModelIndex()

        def find(parent):
            for row in range(model.rowCount(parent)):
                index = model.index(row, 0, parent)
                data = model.data(index, QtCore.Qt.ItemDataRole.UserRole)
                if isinstance(data, dict) and data.get("id") == model_id:
                    return index
                nested = find(index)
                if nested.isValid():
                    return nested
            return QtCore.QModelIndex()

        return find(QtCore.QModelIndex())

    def _on_model_picked(self, index: int):
        if not self._syncing_combos:
            self._apply_current_model(save=True)

    def _apply_current_model(self, save: bool):
        model = self.model_combo.currentData()
        if not model:
            return
        if model["id"] != self._applied_model:
            self._applied_model = model["id"]
            self.client.set_model(model["id"])
        if save:
            self.settings.setValue("model/%s" % self.client.name, model["id"])
        efforts = model.get("efforts") or []
        self._syncing_combos = True
        try:
            self.thinking_combo.clear()
            self.thinking_combo.addItems(efforts)
            self.thinking_combo.setEnabled(bool(efforts))
            if efforts:
                saved = str(self.settings.value("thinking/%s" % self.client.name, ""))
                pick = self.thinking_combo.findText(saved) if saved else -1
                self.thinking_combo.setCurrentIndex(pick if pick >= 0 else 0)
                self.client.set_thinking(self.thinking_combo.currentText())
        finally:
            self._syncing_combos = False

    def _on_thinking_picked(self, index: int):
        if self._syncing_combos or not self.client:
            return
        level = self.thinking_combo.itemText(index)
        self.client.set_thinking(level)
        self.settings.setValue("thinking/%s" % self.client.name, level)

    # -- chat ---------------------------------------------------------------

    @QtCore.Slot(bool)
    def _on_ready(self, ready: bool):
        self.send_button.setEnabled(ready)
        self.send_button.setText("Send" if ready else "Connecting…")

    @QtCore.Slot()
    def send_prompt(self):
        text = self.prompt.toPlainText().strip()
        if not text or self.client is None:
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
        self.chat.start_assistant(self.client.label if self.client else "Assistant")

    @QtCore.Slot(str)
    def _finish_assistant_message(self, status: str):
        self.chat.finish_assistant()
        self.cancel_button.setEnabled(False)
        self.send_button.setEnabled(self.client.ready)
        self.status.setText(
            "%s connected — last turn %s" % (self.client.label, status)
        )
        self._save_chat()

    @QtCore.Slot(str)
    def _show_error(self, message: str):
        self.chat.add_error(message)
        self.cancel_button.setEnabled(False)
        self.send_button.setEnabled(self.client.ready)
        self.send_button.setText("Send" if self.client.ready else "Connecting…")
        self._save_chat()

    # -- attachments ----------------------------------------------------------

    @QtCore.Slot(str)
    def capture(self, target: str):
        try:
            path = capture_target(target)
        except Exception as exc:
            self.status.setText("Capture failed: %s" % exc)
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Nuke capture failed")
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
        dialog.setWindowTitle("Agent requests Nuke Python execution")
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
        self._save_chat()
        self.bridge.stop()
        if self.client is not None:
            self.client.stop()
        super().closeEvent(event)
