"""Dockable Nuke Pi panel: screenshots, chat and the local Pi agent."""

from __future__ import annotations

from pathlib import Path
import re
import traceback

from PySide6 import QtCore, QtGui, QtWidgets

from ..bridge import ensure_bridge, register_trust_source
from ..capture import capture_backend, capture_target
from ..chat_store import ChatStore
from ..harnesses.intervention import describe_activity, describe_intervention
from ..harnesses.pi_rpc import PiRpcClient
from .chat_view import ChatView
from .theme import FONT_DEFAULT, FONT_MAX, FONT_MIN, apply_theme, enlarged_font, set_variant


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_LABEL = "Nuke Pi"


def _format_tokens(value) -> str:
    if not value:
        return "0"
    if value >= 1_000_000:
        return "%.1fM" % (value / 1_000_000.0)
    if value >= 1000:
        return "%.1fk" % (value / 1000.0)
    return str(int(value))


class _GroupedModelCombo(QtWidgets.QComboBox):
    """Provider-grouped model combo: the popup always shows every provider's models."""

    def showPopup(self):
        view = self.view()
        if isinstance(view, QtWidgets.QTreeView):
            view.expandAll()
        super().showPopup()


class CodexPanelWidget(QtWidgets.QWidget):
    """Native Nuke panel with streaming Pi chat and image attachments.

    (The class name is the registered panel entry point; the visible product name is "Nuke Pi".)
    """

    def __init__(self, parent=None):
        bridge = ensure_bridge()
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
        self._restored_session = False
        self._model_failed = None
        self._model_waiting = False
        self._last_models = None
        self._closed = False
        self._settings_dialog = None
        self._font_size = self._stored_font_size()
        # Repaints the observational clocks (request/tool/run time) once a second while busy.
        # It only updates labels; it never interrupts or steers the model.
        self._clock_timer = QtCore.QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_activity_label)
        self._build_ui()
        apply_theme(self)
        self.chat.set_font_size(self._font_size)
        self._update_font_controls()
        self.bridge = bridge
        self.bridge.status_changed.connect(self._on_bridge_status)
        self.bridge.image_delivered.connect(self._on_image_delivered)
        self._set_status("Nuke bridge ready on localhost")
        self.bridge_path = str(self.bridge.discovery_path)
        self._unregister_trust = register_trust_source(self.is_python_trusted)
        self._start_client()

    # -- layout -----------------------------------------------------------------

    def _tool_button(self, text: str, tooltip: str = "", variant: str = "ghost") -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setText(text)
        if tooltip:
            button.setToolTip(tooltip)
        button.setProperty("variant", variant)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        return button

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        heading_row = QtWidgets.QHBoxLayout()
        heading = QtWidgets.QLabel(PRODUCT_LABEL)
        heading.setObjectName("heading")
        heading.setFont(enlarged_font(heading.font(), 3))
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        self.font_smaller_button = self._tool_button("A\u2212", "Smaller chat text (Ctrl+\u2212)")
        self.font_reset_button = self._tool_button("A", "Reset chat text size (Ctrl+0)")
        self.font_larger_button = self._tool_button("A+", "Larger chat text (Ctrl+=)")
        for button in (self.font_smaller_button, self.font_reset_button, self.font_larger_button):
            heading_row.addWidget(button)
        self.new_chat_button = self._tool_button(
            "New chat",
            "Archive this transcript and start with an empty model context",
            "accent",
        )
        heading_row.addWidget(self.new_chat_button)
        layout.addLayout(heading_row)

        model_row = QtWidgets.QHBoxLayout()
        model_row.addWidget(QtWidgets.QLabel("Model"))
        self.model_combo = _GroupedModelCombo()
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
        model_row.addWidget(self.model_combo, 2)
        model_row.addWidget(QtWidgets.QLabel("Think"))
        self.thinking_combo = QtWidgets.QComboBox()
        model_row.addWidget(self.thinking_combo, 1)
        self.manage_models_button = self._tool_button("Manage models…", variant="")
        model_row.addWidget(self.manage_models_button)
        layout.addLayout(model_row)

        status_row = QtWidgets.QHBoxLayout()
        self.status = QtWidgets.QLabel("Preparing Pi…")
        self.status.setWordWrap(True)
        status_row.addWidget(self.status, 1)
        self.reconnect_button = self._tool_button("Reconnect")
        status_row.addWidget(self.reconnect_button)
        self.accounts_button = self._tool_button(
            "Accounts…", "Sign in to Pi providers with an API key or subscription"
        )
        status_row.addWidget(self.accounts_button)
        self.settings_button = self._tool_button("Settings…")
        status_row.addWidget(self.settings_button)
        layout.addLayout(status_row)

        # Steering status: per-message received/waiting/delivered plus observational clocks.
        self.activity_label = QtWidgets.QLabel("")
        self.activity_label.setObjectName("activityLabel")
        self.activity_label.setWordWrap(True)
        self.activity_label.setVisible(False)
        layout.addWidget(self.activity_label)

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
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, value=target: self.capture(value))
            capture_row.addWidget(button)
        layout.addLayout(capture_row)

        attachment_row = QtWidgets.QHBoxLayout()
        self.capture_status = QtWidgets.QLabel("No pending images")
        self.capture_status.setWordWrap(True)
        set_variant(self.capture_status, "status", "muted")
        attachment_row.addWidget(self.capture_status, 1)
        self.clear_attachments_button = self._tool_button("Clear all")
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
        self.send_button.setProperty("variant", "primary")
        self.send_button.setEnabled(False)
        action_row.addWidget(self.send_button, 1)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setProperty("variant", "danger")
        self.cancel_button.setEnabled(False)
        action_row.addWidget(self.cancel_button)
        layout.addLayout(action_row)

        self.send_button.clicked.connect(self.send_prompt)
        self.cancel_button.clicked.connect(lambda: self.client and self.client.interrupt())
        self.clear_attachments_button.clicked.connect(self.clear_pending_attachments)
        self.model_combo.activated.connect(self._on_model_picked)
        self.manage_models_button.clicked.connect(self._manage_models)
        self.thinking_combo.activated.connect(self._on_thinking_picked)
        self.reconnect_button.clicked.connect(lambda: self.client and self.client.restart())
        self.settings_button.clicked.connect(self._open_settings)
        self.accounts_button.clicked.connect(self._open_accounts)
        self.new_chat_button.clicked.connect(self._new_chat)
        self.font_smaller_button.clicked.connect(lambda: self._set_font_size(self._font_size - 1))
        self.font_larger_button.clicked.connect(lambda: self._set_font_size(self._font_size + 1))
        self.font_reset_button.clicked.connect(lambda: self._set_font_size(FONT_DEFAULT))
        # Shortcuts are scoped to this panel and its children: never global Nuke shortcuts.
        scope = QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut
        for keys, handler in (
            ("Ctrl+Return", self.send_prompt),
            ("Ctrl+=", lambda: self._set_font_size(self._font_size + 1)),
            ("Ctrl++", lambda: self._set_font_size(self._font_size + 1)),
            ("Ctrl+-", lambda: self._set_font_size(self._font_size - 1)),
            ("Ctrl+0", lambda: self._set_font_size(FONT_DEFAULT)),
        ):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(keys), self)
            shortcut.setContext(scope)
            shortcut.activated.connect(handler)

    def _set_status(self, text: str, kind: str = "muted"):
        self.status.setText(text)
        set_variant(self.status, "status", kind)

    # -- chat text size -----------------------------------------------------------

    def _stored_font_size(self) -> int:
        try:
            value = int(self.settings.value("chat/font_size", FONT_DEFAULT))
        except (TypeError, ValueError):
            value = FONT_DEFAULT
        return max(FONT_MIN, min(FONT_MAX, value))

    def _set_font_size(self, points: int):
        points = max(FONT_MIN, min(FONT_MAX, int(points)))
        if points == self._font_size:
            return
        self._font_size = points
        self.settings.setValue("chat/font_size", points)
        # The renderer owns keeping the reader's scroll position across the change.
        self.chat.set_font_size(points)
        self._update_font_controls()

    def _update_font_controls(self):
        self.font_smaller_button.setEnabled(self._font_size > FONT_MIN)
        self.font_larger_button.setEnabled(self._font_size < FONT_MAX)
        self.font_reset_button.setEnabled(self._font_size != FONT_DEFAULT)
        self.font_reset_button.setToolTip("Reset chat text size to %d pt (now %d pt)" % (FONT_DEFAULT, self._font_size))
        if self._settings_dialog is not None:
            self._settings_dialog.set_font_size(self._font_size)

    # -- agent lifecycle --------------------------------------------------------------

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

    def _start_client(self):
        """Create the one Pi client and bring the project's previous conversation back automatically.

        The stored session is adopted BEFORE the agent process starts, so Pi opens that session
        directly: there is no question to answer and nothing runs until the user sends a message.
        Send stays disabled until the agent reports ready (Nuke tools verified, current model and
        effort acknowledged by the SDK).
        """
        self.store = ChatStore(self.project_path)
        self.client = PiRpcClient(str(PROJECT_ROOT), self, self.bridge_path)
        self.client.session_dir = self.store.dir / "sessions"
        saved = self.store.load()
        session = saved["session"]
        self._restored_session = bool(session)
        self._models_signature = None
        self._applied_model = None
        self._model_failed = None
        self._set_model_placeholder("Loading models…")
        self.chat.clear()
        if saved["messages"]:
            self.chat.load_records(saved["messages"])
        self._update_usage({})
        if session:
            self.client.resume_session(session)
            self._set_status("Continuing the previous conversation…", "accent")
        self._connect_client()
        self._refresh_controls()
        self._update_activity_label()
        QtCore.QTimer.singleShot(0, self.client.start)

    def _set_model_placeholder(self, text: str):
        self.thinking_combo.clear()
        placeholder = QtGui.QStandardItem(text)
        placeholder.setFlags(placeholder.flags() & ~QtCore.Qt.ItemFlag.ItemIsSelectable)
        store = QtGui.QStandardItemModel(self.model_combo)
        store.appendRow(placeholder)
        self.model_combo.setModel(store)
        self.model_combo.setCurrentIndex(0)
        self.model_combo.setEnabled(False)

    def _connect_client(self):
        client = self.client
        client.status_changed.connect(self._set_status)
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
        client.selected_model_changed.connect(self._on_selected_model_changed)
        client.model_preferences_changed.connect(self._on_model_preferences_changed)
        client.intervention_changed.connect(self._on_intervention_changed)
        client.activity_changed.connect(self._on_activity_changed)
        client.guidance_withdrawn.connect(self._restore_withdrawn)
        client.model_selection_failed.connect(self._on_model_selection_failed)

    def _save_chat(self):
        if self.store is None or self.client is None:
            return
        try:
            # Coalesced background write owned by the store: no file IO or JSON on the GUI thread.
            self.store.request_save(self.chat.records(), self.client.session_state())
        except RuntimeError:
            return  # the store is closed with the pane; nothing to save any more
        failed = self.store.take_error()
        if failed is not None:
            self._set_status("Could not save this chat: %s" % failed, "error")

    @QtCore.Slot()
    def _new_chat(self):
        """Archive the transcript and reset the model context in one fenced step.

        The client replaces its agent process (new control epoch) before the conversation counts
        as fresh, so everything the old run still does — tool events, image deliveries — is refused.
        """
        if self.client is None or self.store is None:
            return
        archived = None
        try:
            # Everything written so far lands in the old transcript before it is archived.
            self.store.flush()
            archived = self.store.archive()
        except OSError as exc:
            self._set_status("Could not archive the old chat: %s" % exc, "error")
        self.chat.clear()
        self._restored_session = False
        self.client.new_session()
        self._update_usage({})
        self._refresh_controls()
        self._save_chat()
        self._set_status(
            "New chat — previous chat archived to %s" % archived.name
            if archived
            else "New chat started",
            "accent",
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

    # -- dialogs --------------------------------------------------------------------

    def _open_accounts(self):
        from .accounts_dialog import PiAccountsDialog

        PiAccountsDialog(self).exec()

    def _open_settings(self):
        from .settings_dialog import PiSettingsDialog

        dialog = PiSettingsDialog(self._font_size, self)
        dialog.font_size_changed.connect(self._set_font_size)
        self._settings_dialog = dialog
        try:
            dialog.exec()
        finally:
            self._settings_dialog = None
            dialog.deleteLater()
        if self.client is not None and not self.client.ready and not self.client.parked:
            self.client.restart()

    # -- model management -----------------------------------------------------------

    def _refresh_manage_button(self):
        prefs = self._model_prefs()
        idle = bool(prefs and prefs.get("editable") and not self._turn_active())
        self.manage_models_button.setEnabled(idle)
        self.manage_models_button.setToolTip(
            "Choose which models the picker offers and the default"
            if idle
            else "Available while the agent is idle"
        )

    def _manage_models(self):
        if self._turn_active():
            return
        from .model_manager_dialog import ModelManagerDialog

        prefs = self._model_prefs()
        if not prefs or not prefs.get("editable") or not prefs.get("available_models"):
            self._set_status(
                "Could not read model settings: %s" % ((prefs or {}).get("error") or "agent not ready"),
                "error",
            )
            return
        dialog = ModelManagerDialog(
            list(prefs.get("available_models") or []),
            prefs.get("enabled_models"),
            str(prefs.get("default_model") or ""),
            self,
            list(prefs.get("missing_models") or []),
        )
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        if self._turn_active():
            self._set_status("Model settings not saved: the agent became busy", "warn")
            return
        # Core renews the idle process itself and re-emits models_changed / selected_model_changed.
        if self.client.save_model_preferences(dialog.selected_ids(), dialog.default_id()):
            self._set_status("Model settings saved", "ok")
        else:
            self._set_status(
                "Model settings not saved: %s"
                % (self.client.model_preferences_error or "unknown error"),
                "error",
            )
        self._refresh_controls()

    def _on_model_preferences_changed(self):
        if self.sender() is not self.client:
            return
        if self._model_waiting and self._last_models is not None:
            # Actual SDK state arrived while nothing was chosen: adopt it now.
            self._models_signature = None
            self._on_models_changed(self._last_models, self.client)
        self._refresh_manage_button()

    def _model_prefs(self):
        try:
            return self.client.get_model_preferences()
        except Exception:
            return None

    def _show_model_blocked(self, model_id: str):
        self.model_combo.setRootModelIndex(QtCore.QModelIndex())
        self.model_combo.setCurrentIndex(-1)
        self.model_combo.setEnabled(True)
        self._applied_model = None
        self._model_failed = model_id or "none"
        err = str(self.client.selection_block or "")
        self._set_status(
            err
            or (
                "Model %s is not among your enabled models — pick an allowed model" % model_id
                if model_id
                else "No allowed model selected — pick a model"
            ),
            "warn",
        )
        self._refresh_controls()

    def _on_selected_model_changed(self, model_id: str):
        """The backend itself changed the desired model (new-chat default, removal by a save)."""
        if self.sender() is not self.client:
            return
        index = self._find_model_index(model_id) if model_id else QtCore.QModelIndex()
        if not index.isValid():
            self._show_model_blocked(model_id)
            return
        self._syncing_combos = True
        try:
            self.model_combo.setRootModelIndex(index.parent())
            self.model_combo.setCurrentIndex(index.row())
            self.model_combo.setRootModelIndex(QtCore.QModelIndex())
            self.model_tree.expand(index.parent())
            # The backend already holds this model: no set_model echo.
            self._applied_model = model_id
            self._model_failed = None
            self._apply_current_model(save=False)
            self._refresh_controls()
        finally:
            self._syncing_combos = False

    def _on_models_changed(self, models: list, client: "object | None" = None):
        sender = self.sender()
        if sender is not None and sender is not self.client:
            return
        if client is not None and client is not self.client:
            return
        if self.model_combo.view().isVisible():
            # Rebuilding under an open popup is what made the dropdown flicker;
            # try again once the user has finished choosing.
            own = self.client
            QtCore.QTimer.singleShot(
                200, lambda m=models: self._on_models_changed(m, own)
            )
            return
        signature = [
            (m["id"], m.get("label"), tuple(m.get("efforts") or [])) for m in models
        ]
        if signature == self._models_signature:
            return  # same list, no need to disturb the selection
        self._models_signature = signature
        self._syncing_combos = True
        self._last_models = models
        first_population = self._applied_model is None
        kept_id = (self.model_combo.currentData() or {}).get("id")
        try:
            store = QtGui.QStandardItemModel(self.model_combo)
            groups: dict[str, list] = {}
            order: list[str] = []
            for model in models:
                provider = model["id"].split("/", 1)[0] if "/" in model["id"] else "Models"
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
            self._model_waiting = False
            prefs = self._model_prefs() or {}
            selected = str(self.client.selected_model or "")
            default = str(prefs.get("default_model") or "") if prefs.get("default_configured") else ""
            session = str(prefs.get("session_model") or "") if prefs.get("session_model_known") else ""
            if self._restored_session:
                # A restored conversation keeps its own model; the configured default never replaces it.
                wanted = [kept_id if not first_population else "", selected, session]
            else:
                # Fresh chat: an explicit private default wins; otherwise the actual session model.
                wanted = [kept_id if not first_population else "", selected, default, session]
            wanted_id = next((w for w in wanted if w), "")
            if not wanted_id:
                # Nothing explicit and the SDK state is not known yet: wait, never guess.
                self._model_waiting = True
                self.model_combo.setRootModelIndex(QtCore.QModelIndex())
                self.model_combo.setCurrentIndex(-1)
                self.model_combo.setEnabled(True)
                self._refresh_controls()
                return
            index = self._find_model_index(wanted_id)
            if not index.isValid():
                # Not allowed: show blocked, never substitute another model.
                self._show_model_blocked(wanted_id)
                return
            chosen = self.model_combo.model().data(index, QtCore.Qt.ItemDataRole.UserRole)
            held = {str(self.client.selected_model or ""), str(self.client.current_model or "")}
            if isinstance(chosen, dict) and chosen.get("id") in held:
                self._applied_model = chosen["id"]  # backend already holds it: no set_model echo
                self._model_failed = None
            self.model_combo.setRootModelIndex(index.parent())
            self.model_combo.setCurrentIndex(index.row())
            self.model_combo.setRootModelIndex(QtCore.QModelIndex())
            self.model_tree.expand(index.parent())
            self.model_combo.setEnabled(True)
            self._apply_current_model(save=False)
        finally:
            self._syncing_combos = False
        self._refresh_controls()

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
        if self._syncing_combos:
            return
        if not isinstance(self.model_combo.currentData(), dict):
            # A provider header is never a choice: put back the previous selection (none when blocked).
            self._syncing_combos = True
            try:
                found = self._find_model_index(self._applied_model or "")
                if found.isValid():
                    self.model_combo.setRootModelIndex(found.parent())
                    self.model_combo.setCurrentIndex(found.row())
                    self.model_combo.setRootModelIndex(QtCore.QModelIndex())
                else:
                    self.model_combo.setCurrentIndex(-1)
            finally:
                self._syncing_combos = False
            return
        self._apply_current_model(save=True)

    def _apply_current_model(self, save: bool):
        model = self.model_combo.currentData()
        if not model:
            return
        if model["id"] != self._applied_model or self._model_failed is not None:
            if not save:
                # Programmatic sync (adoption/population): the backend holds or adopts it; never a set_model.
                if model["id"] != self._applied_model:
                    self._applied_model = model["id"]
                    self._model_failed = None
                    self._refresh_controls()
            else:
                # An explicit human pick: the backend applies it and only then lifts the Send gate.
                self._applied_model = model["id"]
                recovering = self._model_failed is not None
                self._model_failed = None
                self.client.set_model(model["id"])
                if recovering:
                    self._set_status("Applying model %s…" % model["id"], "accent")
                self._refresh_controls()
        if save:
            self.settings.setValue("model/%s" % self.client.name, model["id"])
        efforts = model.get("efforts") or []
        # A valid persisted/requested effort (e.g. xhigh) is preserved and seeded once the model is
        # known. With none valid, the backend's own effort is shown and nothing is pushed.
        backend_effort = str(self.client.selected_thinking or "")
        self._syncing_combos = True
        try:
            self.thinking_combo.clear()
            self.thinking_combo.addItems(efforts)
            self.thinking_combo.setEnabled(bool(efforts))
            if efforts:
                saved = str(self.settings.value("thinking/%s" % self.client.name, ""))
                pick = self.thinking_combo.findText(saved) if saved else -1
                wanted = saved if pick >= 0 else backend_effort
                self.thinking_combo.setCurrentIndex(self.thinking_combo.findText(wanted) if wanted else -1)
                # Seed only a valid persisted effort the backend doesn't already hold.
                if pick >= 0 and saved != backend_effort:
                    self.client.set_thinking(saved)
        finally:
            self._syncing_combos = False

    def _on_thinking_picked(self, index: int):
        if self._syncing_combos or not self.client:
            return
        level = self.thinking_combo.itemText(index)
        self.client.set_thinking(level)
        self.settings.setValue("thinking/%s" % self.client.name, level)

    # -- chat ---------------------------------------------------------------

    def _from_current_client(self) -> bool:
        """Signals from a client we already stopped must not drive the panel."""
        sender = self.sender()
        return self.client is not None and (sender is None or sender is self.client)

    def _turn_active(self) -> bool:
        return self.client is not None and self.client.busy

    def _refresh_controls(self):
        """One place decides Send/Cancel. Pi stays sendable (steerable) while a real turn runs."""
        client = self.client
        if client is None:
            return
        busy = self._turn_active()
        # A new chat's replacement process is not a real turn: nothing may be sent (or steered)
        # until it has its Nuke tools and its model/effort ACKed. Real busy turns stay steerable.
        fresh = bool(client.fresh_pending)
        reachable = bool(client.ready) and not fresh
        cancellable = (bool(client.ready) or busy) and not fresh
        model_failed = self._model_failed is not None
        model_unchosen = not isinstance(self.model_combo.currentData(), dict)
        self.send_button.setEnabled(bool(reachable and not model_failed and not model_unchosen))
        if fresh:
            self.send_button.setText("Starting new chat…")
        elif model_failed:
            self.send_button.setText("Model not applied — pick a model")
        elif not reachable:
            self.send_button.setText("Stopped — use Reconnect" if client.parked else "Connecting…")
        elif model_unchosen:
            self.send_button.setText("Pick a model to start")
        elif busy:
            self.send_button.setText("Steer (stop && send)")
        else:
            self.send_button.setText("Send")
        self.cancel_button.setEnabled(bool(cancellable and busy))
        self._refresh_manage_button()
        self.prompt.setPlaceholderText(
            "Message the agent: sending now stops its current work safely and continues "
            "the same conversation with your message (also /btw <message>)…"
            if busy
            else "Ask the agent about the current comp…"
        )
        if busy or self._clock_timer.isActive():
            self._update_activity_label()
        if busy and not self._clock_timer.isActive():
            self._clock_timer.start()
        elif not busy:
            self._clock_timer.stop()

    @QtCore.Slot()
    def _update_activity_label(self):
        client = self.client
        text = ""
        if client is not None:
            parts = [
                describe_intervention(client.intervention_state()),
                describe_activity(client.activity_snapshot()),
            ]
            text = "\n".join(part for part in parts if part)
        self.activity_label.setText(text)
        self.activity_label.setVisible(bool(text))

    @QtCore.Slot(dict)
    def _on_intervention_changed(self, _state: dict):
        if not self._from_current_client():
            return
        self._refresh_controls()
        self._update_activity_label()

    @QtCore.Slot(dict)
    def _on_activity_changed(self, _snapshot: dict):
        if not self._from_current_client():
            return
        self._refresh_controls()
        self._update_activity_label()

    @QtCore.Slot(list)
    def _restore_withdrawn(self, items: list):
        """Never-delivered messages come back to the input box (text and images), in order."""
        if not self._from_current_client():
            return
        texts = [str(item.get("text", "")) for item in items if item.get("text")]
        existing = self.prompt.toPlainText().strip()
        merged = "\n\n".join(texts + ([existing] if existing else []))
        if merged:
            self.prompt.setPlainText(merged)
        for item in items:
            for path in item.get("image_paths") or []:
                if path not in self.pending_images and Path(path).is_file():
                    self._add_attachment_row(Path(path), "restored image")
        self._update_capture_status()

    @QtCore.Slot(bool)
    def _on_ready(self, ready: bool):
        if not self._from_current_client():
            return
        self._refresh_controls()

    @staticmethod
    def _parse_btw(text: str) -> tuple[str | None, bool]:
        """``/btw <message>`` is explicit steering; the prefix is never sent to the agent."""
        match = re.match(r"^/btw(?:\s+(.*))?$", text, re.IGNORECASE | re.DOTALL)
        if match is None:
            return text, False
        body = (match.group(1) or "").strip()
        return (body or None), True

    @QtCore.Slot()
    def send_prompt(self):
        text = self.prompt.toPlainText().strip()
        if not text or self.client is None:
            return
        if not self.send_button.isEnabled():
            return  # the Ctrl+Return shortcut must not bypass a disabled Send
        client = self.client
        text, _explicit = self._parse_btw(text)
        if text is None:
            self._set_status(
                "Usage: /btw <message> — stops the agent's current work and continues with it.", "warn"
            )
            return
        if client.send_turn(text, self.pending_images):
            self.prompt.clear()
            self.clear_pending_attachments()
            self._refresh_controls()

    @QtCore.Slot(str, list)
    def _show_user_message(self, text: str, images: list):
        if not self._from_current_client():
            return
        self.chat.add_user_message(text, images)

    @QtCore.Slot()
    def _start_assistant_message(self):
        if not self._from_current_client():
            return
        self.chat.start_assistant(self.client.label)
        self._refresh_controls()

    @QtCore.Slot(str)
    def _finish_assistant_message(self, status: str):
        if not self._from_current_client():
            return
        self.chat.finish_assistant()
        self._refresh_controls()
        if not self._turn_active():
            self._set_status("%s connected — last turn %s" % (self.client.label, status), "ok")
        self._save_chat()

    @QtCore.Slot(str)
    def _show_error(self, message: str):
        if not self._from_current_client():
            return
        self.chat.add_error(message)
        self._refresh_controls()
        self._save_chat()

    # -- agent-delivered images -------------------------------------------------

    @QtCore.Slot(object)
    def _on_image_delivered(self, event):
        """An image the bundled MCP really handed to this panel's agent: show those same bytes inline."""
        client = self.client
        if self._closed or client is None or self.store is None or not isinstance(event, dict):
            return
        # Ownership: only this panel's conversation. The control id is the chat's identity at the bridge;
        # the process epoch (when both sides have one) rejects a replaced agent process's late delivery.
        if not event.get("control_id") or event.get("control_id") != client.control_id:
            return
        if client.fresh_pending:
            # A new chat is replacing the agent process: whatever the old run delivers is not this chat's.
            return
        epoch = event.get("control_epoch")
        current = getattr(client, "process_epoch", None)
        if isinstance(epoch, int) and isinstance(current, int) and epoch != current:
            return
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        image = {
            "delivery_id": str(event.get("delivery_id") or ""),
            "sha256": str(event.get("sha256") or ""),
            "caption": self._image_caption(event, metadata),
        }
        try:
            asset, size = self.store.save_image_asset(str(event.get("path") or ""), image["sha256"])
            image["asset"] = str(asset)
            image["bytes"] = size
        except (OSError, ValueError) as exc:
            image["error"] = "%s: %s" % (type(exc).__name__, exc)
        if self.chat.add_delivered_image(image):
            self._save_chat()

    @staticmethod
    def _image_caption(event: dict, metadata: dict) -> str:
        parts = []
        target = metadata.get("target")
        if target:
            scope = metadata.get("scope")
            parts.append("%s (%s scope)" % (target, scope) if scope else str(target))
        frame = next(
            (metadata[key] for key in ("frame", "viewer_render_frame", "requested_frame") if metadata.get(key) is not None),
            None,
        )
        if frame is not None:
            parts.append("frame %s" % frame)
        if metadata.get("viewer"):
            parts.append(str(metadata["viewer"]))
        source = metadata.get("source") or event.get("tool")
        if source:
            parts.append(str(source))
        if metadata.get("captured_at"):
            parts.append(str(metadata["captured_at"]))
        parts.append("sha256 %s" % str(event.get("sha256") or "")[:12])
        return "Delivered to the agent: " + " · ".join(parts)

    @QtCore.Slot(str)
    def _on_model_selection_failed(self, model_id: str):
        """The agent kept its previous model: forget the unacknowledged selection, keep the user's pick."""
        if not self._from_current_client():
            return
        # Only the current desired model's failure counts; an obsolete A must not block newer B.
        desired = (self.model_combo.currentData() or {}).get("id")
        if model_id != desired:
            return
        if model_id == self._applied_model:
            self._applied_model = None
        self._model_failed = model_id
        self._refresh_controls()

    # -- attachments ----------------------------------------------------------

    @QtCore.Slot(str)
    def capture(self, target: str):
        try:
            path = capture_target(target)
        except Exception as exc:
            self._set_status("Capture failed: %s" % exc, "error")
            dialog = QtWidgets.QMessageBox(self)
            dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.setWindowTitle("Nuke capture failed")
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            dialog.setText("Could not capture the Nuke %s." % target)
            dialog.setInformativeText("%s: %s" % (type(exc).__name__, exc))
            dialog.setDetailedText(traceback.format_exc())
            dialog.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            apply_theme(dialog)
            dialog.open()
            return

        label = target.replace("nodegraph", "node graph")
        self._add_attachment_row(path, label)
        backend = capture_backend(path)
        self._set_status(
            "Captured %s via %s; it will be attached to the next prompt." % (label, backend), "ok"
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
        set_variant(self.capture_status, "status", "accent" if count else "muted")
        self.clear_attachments_button.setEnabled(bool(count))
        self.history.setVisible(bool(count))

    def is_python_trusted(self) -> bool:
        """Whether this open, visible panel's Trusted Python session is enabled."""
        return not self._closed and self.isVisible() and self.trusted_python.isChecked()

    def hideEvent(self, event):
        """Hiding the pane ends Trusted Python; the shared bridge stays up."""
        self.trusted_python.setChecked(False)
        super().hideEvent(event)

    def _on_bridge_status(self, text: str):
        self._set_status(text)

    def _add_attachment_row(self, path: Path, label: str):
        """Register one pending image and show its thumbnail row."""
        path_string = str(path)
        self.pending_images.append(path_string)
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
        remove_button = self._tool_button("×", "Remove this attachment")
        remove_button.clicked.connect(
            lambda _checked=False, value=path_string, list_item=item: self.remove_attachment(
                value, list_item
            )
        )
        row_layout.addWidget(remove_button)
        item.setSizeHint(row.sizeHint())
        self.history.setItemWidget(item, row)
        self.history.setVisible(True)

    def closeEvent(self, event):
        """Save and stop only this panel's agent; the shared bridge outlives the pane."""
        if not self._closed:
            self._closed = True
            self._unregister_trust()
            self.trusted_python.setChecked(False)
            for signal, slot in (
                (self.bridge.status_changed, self._on_bridge_status),
                (self.bridge.image_delivered, self._on_image_delivered),
            ):
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
            self._save_chat()
            if self.store is not None:
                try:
                    self.store.close()
                except OSError:
                    pass
            if self.client is not None:
                self.client.stop()
                self.client.blockSignals(True)
            self._clock_timer.stop()
        super().closeEvent(event)
