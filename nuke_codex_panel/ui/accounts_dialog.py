"""Pi accounts: API-key and subscription/OAuth sign-in driven by the Pi SDK.

Every provider, method label, status and interactive step comes from the
private Pi SDK through ``PiAuthClient``; nothing here is provider specific.
Secrets typed into prompts are sent straight to the helper and cleared; they
are never stored in QSettings, chat history, status text or logs.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from .theme import apply_theme, enlarged_font

API_KEY = "api_key"
OAUTH = "oauth"

_AMBIENT_NOTE = (
    "Pi runs here with a private, isolated account store. This plugin never automatically "
    "borrows your global Pi account store or inherited provider environment-variable credentials. "
    "Entries that Pi can only resolve from the environment or other ambient sources are listed for "
    "information only (Pi offers no sign-in for them). If you explicitly select an SDK method that "
    "uses an external credential store (for example an AWS profile / default chain or Google "
    "application-default credentials), that method may use those stores. Account changes are saved "
    "immediately; closing this dialog does not undo them."
)


def _is_web_url(text: str) -> bool:
    url = QtCore.QUrl(str(text or "").strip())
    return url.isValid() and url.scheme().lower() in ("http", "https") and bool(url.host())


def _status_text(status: dict | None, auth_type: str = "") -> str:
    status = status or {}
    if not status.get("configured"):
        return "not configured"
    source = str(status.get("source") or "")
    label = str(status.get("label") or "")
    kind = str(status.get("type") or auth_type or "")
    parts = [p for p in (kind, label) if p]
    detail = " ".join(parts)
    if source == "stored":
        if kind == OAUTH:
            text = "stored (OAuth token validity not checked)"
        else:
            text = "stored (locally resolvable; not verified with the provider)"
    elif source:
        text = "available via %s (informational; not verified)" % source
    else:
        text = "present (not verified)"
    return "%s %s" % (text, "[%s]" % detail) if detail else text


class _PromptForm(QtWidgets.QGroupBox):
    """One inline SDK prompt (text, secret, manual code or select)."""

    submitted = QtCore.Signal(int, str)

    def __init__(self, prompt_id: int, prompt: dict, parent=None):
        super().__init__(parent)
        self.prompt_id = prompt_id
        kind = str(prompt.get("type") or "text")
        self._kind = kind
        layout = QtWidgets.QVBoxLayout(self)
        message = QtWidgets.QLabel(str(prompt.get("message") or "Input requested"))
        message.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        message.setWordWrap(True)
        message.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(message)
        self._line = None
        self._combo = None
        if kind == "select":
            self._combo = QtWidgets.QComboBox()
            for option in prompt.get("options") or []:
                if not isinstance(option, dict):
                    continue
                self._combo.addItem(str(option.get("label") or option.get("id") or ""), str(option.get("id") or ""))
                description = option.get("description")
                if description:
                    self._combo.setItemData(
                        self._combo.count() - 1, str(description), QtCore.Qt.ItemDataRole.ToolTipRole
                    )
            layout.addWidget(self._combo)
        else:
            self._line = QtWidgets.QLineEdit()
            self._line.setPlaceholderText(str(prompt.get("placeholder") or ""))
            if kind == "secret":
                self._line.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            layout.addWidget(self._line)
            self._line.returnPressed.connect(self._submit)
        self._button = QtWidgets.QPushButton("Submit")
        self._button.setProperty("variant", "primary")
        self._button.clicked.connect(self._submit)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._button)
        layout.addLayout(row)

    def focus_input(self):
        (self._line or self._combo).setFocus()

    def clear_secret(self):
        if self._line is not None:
            self._line.clear()

    def _submit(self):
        if not self._button.isEnabled():
            return
        if self._combo is not None:
            if self._combo.currentIndex() < 0:
                return
            value = str(self._combo.currentData() or "")
        else:
            value = self._line.text()
        self._button.setEnabled(False)
        self.setEnabled(False)
        self.clear_secret()
        self.submitted.emit(self.prompt_id, value)


class PiAccountsDialog(QtWidgets.QDialog):
    """Add, check and remove Pi API-key / subscription accounts."""

    def __init__(self, parent=None, agent_dir: Path | None = None):
        super().__init__(parent)
        from ..harnesses.pi_auth import PiAuthClient

        if agent_dir is None:
            from ..harnesses.pi_rpc import managed_pi_dir

            agent_dir = managed_pi_dir()
        self.setWindowTitle("Pi accounts")
        self.resize(720, 760)
        self._options: list[dict] = []
        self._accounts: list[dict] = []
        self._op: dict | None = None  # {"kind", "provider", "name"} while an operation is active
        self._forms: dict[int, _PromptForm] = {}
        self._progress: QtWidgets.QLabel | None = None
        self._closing = False
        self._pending_close: int | None = None

        layout = QtWidgets.QVBoxLayout(self)
        note = QtWidgets.QLabel(_AMBIENT_NOTE)
        note.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.helper_label = QtWidgets.QLabel("Starting Pi account service…")
        self.helper_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.helper_label.setWordWrap(True)
        layout.addWidget(self.helper_label)
        self.catalog_warning_label = QtWidgets.QLabel("")
        self.catalog_warning_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.catalog_warning_label.setWordWrap(True)
        self.catalog_warning_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.catalog_warning_label.setVisible(False)
        layout.addWidget(self.catalog_warning_label)

        # Add account.
        add_box = QtWidgets.QGroupBox("Add account")
        add_layout = QtWidgets.QVBoxLayout(add_box)
        chooser = QtWidgets.QHBoxLayout()
        self.api_radio = QtWidgets.QRadioButton("API key")
        self.oauth_radio = QtWidgets.QRadioButton("Subscription / OAuth")
        self.api_radio.setChecked(True)
        group = QtWidgets.QButtonGroup(self)
        group.addButton(self.api_radio)
        group.addButton(self.oauth_radio)
        chooser.addWidget(self.api_radio)
        chooser.addWidget(self.oauth_radio)
        chooser.addStretch(1)
        add_layout.addLayout(chooser)
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter providers…")
        self.filter_edit.setClearButtonEnabled(True)
        add_layout.addWidget(self.filter_edit)
        self.provider_list = QtWidgets.QListWidget()
        self.provider_list.setMinimumHeight(150)
        add_layout.addWidget(self.provider_list)
        self.detail_label = QtWidgets.QLabel("")
        self.detail_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.detail_label.setWordWrap(True)
        self.detail_label.setObjectName("roleLabel")
        add_layout.addWidget(self.detail_label)
        add_row = QtWidgets.QHBoxLayout()
        add_row.addStretch(1)
        self.login_button = QtWidgets.QPushButton("Sign in…")
        self.login_button.setProperty("variant", "primary")
        add_row.addWidget(self.login_button)
        self.cancel_button = QtWidgets.QPushButton("Cancel sign-in")
        self.cancel_button.setProperty("variant", "danger")
        self.cancel_button.setEnabled(False)
        add_row.addWidget(self.cancel_button)
        add_layout.addLayout(add_row)
        layout.addWidget(add_box, 2)

        # Active flow: notices + inline prompts.
        self.flow_box = QtWidgets.QGroupBox("Sign-in progress")
        flow_outer = QtWidgets.QVBoxLayout(self.flow_box)
        self.flow_status = QtWidgets.QLabel("")
        self.flow_status.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.flow_status.setWordWrap(True)
        self.flow_status.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        flow_outer.addWidget(self.flow_status)
        holder = QtWidgets.QWidget()
        self.flow_layout = QtWidgets.QVBoxLayout(holder)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.addStretch(1)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        scroll.setMinimumHeight(110)
        flow_outer.addWidget(scroll)
        layout.addWidget(self.flow_box, 2)

        # Stored accounts.
        acct_box = QtWidgets.QGroupBox("Accounts")
        acct_layout = QtWidgets.QVBoxLayout(acct_box)
        self.account_list = QtWidgets.QListWidget()
        self.account_list.setMinimumHeight(110)
        acct_layout.addWidget(self.account_list)
        acct_row = QtWidgets.QHBoxLayout()
        self.refresh_catalog_button = QtWidgets.QPushButton("Reload list")
        self.check_button = QtWidgets.QPushButton("Check / refresh")
        self.check_button.setToolTip(
            "Resolve the credential locally and let Pi refresh an OAuth token when needed. "
            "Does not validate API keys with the provider; cannot be cancelled once started."
        )
        self.logout_button = QtWidgets.QPushButton("Log out…")
        self.logout_button.setProperty("variant", "danger")
        acct_row.addWidget(self.refresh_catalog_button)
        acct_row.addStretch(1)
        acct_row.addWidget(self.check_button)
        acct_row.addWidget(self.logout_button)
        acct_layout.addLayout(acct_row)
        layout.addWidget(acct_box, 2)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.api_radio.toggled.connect(lambda _c: self._populate_providers())
        self.filter_edit.textChanged.connect(lambda _t: self._populate_providers())
        self.provider_list.currentItemChanged.connect(lambda *_: self._update_controls())
        self.provider_list.itemDoubleClicked.connect(lambda _i: self._start_login())
        self.account_list.currentItemChanged.connect(lambda *_: self._update_controls())
        self.login_button.clicked.connect(self._start_login)
        self.cancel_button.clicked.connect(self._cancel_flow)
        self.refresh_catalog_button.clicked.connect(self._request_catalog)
        self.check_button.clicked.connect(self._check_selected)
        self.logout_button.clicked.connect(self._logout_selected)

        self.client = PiAuthClient(Path(agent_dir), self)
        self.client.ready_changed.connect(self._on_ready_changed)
        self.client.error.connect(self._on_client_error)
        self.client.status_changed.connect(self._on_helper_status)
        self.client.catalog_ready.connect(self._on_catalog)
        self.client.auth_prompt.connect(self._on_prompt)
        self.client.auth_event.connect(self._on_event)
        self.client.auth_prompt_cancelled.connect(self._on_prompt_cancelled)
        self.client.operation_finished.connect(self._on_finished)
        apply_theme(self)
        self._update_controls()
        self.client.start()

    # ---- helpers -------------------------------------------------------

    def _ready(self) -> bool:
        return bool(self.client.ready)

    def _idle(self) -> bool:
        return self._ready() and self._op is None and not bool(getattr(self.client, "busy", False))

    def _selected_option(self) -> dict | None:
        item = self.provider_list.currentItem()
        return item.data(QtCore.Qt.ItemDataRole.UserRole) if item is not None else None

    def _selected_account(self) -> dict | None:
        item = self.account_list.currentItem()
        return item.data(QtCore.Qt.ItemDataRole.UserRole) if item is not None else None

    @staticmethod
    def _account_is_stored(account: dict | None) -> bool:
        if not account:
            return False
        if "stored" in account:
            return bool(account.get("stored"))
        return str(account.get("source") or "stored") == "stored"

    def _update_controls(self):
        idle = self._idle()
        busy = self._op is not None
        option = self._selected_option()
        can_login = bool(option and option.get("canLogin"))
        self.login_button.setEnabled(idle and can_login)
        self.login_button.setText("Add API key…" if self.api_radio.isChecked() else "Sign in…")
        self.cancel_button.setEnabled(busy and self._op is not None and self._op.get("kind") == "login")
        self.api_radio.setEnabled(not busy)
        self.oauth_radio.setEnabled(not busy)
        self.provider_list.setEnabled(not busy)
        self.filter_edit.setEnabled(not busy)
        account = self._selected_account()
        self.logout_button.setEnabled(idle and self._account_is_stored(account))
        self.check_button.setEnabled(idle and account is not None)
        self.refresh_catalog_button.setEnabled(idle)
        self.account_list.setEnabled(not busy)
        if option is None:
            self.detail_label.setText("")
        else:
            text = "%s — %s" % (
                option.get("providerName") or option.get("providerId"),
                _status_text(option.get("status"), str(option.get("authType") or "")),
            )
            if not option.get("canLogin"):
                text += "\nNo sign-in is available for this entry; shown for information only."
            self.detail_label.setText(text)

    def _set_flow_status(self, text: str):
        self.flow_status.setText(text)

    def _clear_flow(self):
        for form in list(self._forms.values()):
            form.clear_secret()
        self._forms.clear()
        self._progress = None
        while self.flow_layout.count() > 1:
            item = self.flow_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _add_flow_widget(self, widget: QtWidgets.QWidget):
        self.flow_layout.insertWidget(self.flow_layout.count() - 1, widget)

    # ---- catalog -------------------------------------------------------

    def _request_catalog(self):
        if self._ready() and self._op is None:
            self.client.request_catalog()

    def _on_ready_changed(self, ready: bool):
        if ready:
            self.helper_label.setText("")
            if self._op is None:
                self.client.request_catalog()
        else:
            if self._op is not None:
                self._finish_local("Pi account service stopped.")
            if not self._closing:
                self.helper_label.setText("Pi account service is not running.")
        self._update_controls()

    def _on_helper_status(self, text: str):
        if text and not self._closing:
            self.helper_label.setText(str(text))

    def _on_client_error(self, text: str):
        if self._closing:
            return
        self.helper_label.setText(str(text))
        self._update_controls()

    def _on_catalog(self, payload: dict):
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        self._options = [o for o in (data.get("options") or []) if isinstance(o, dict)]
        self._accounts = [a for a in (data.get("accounts") or []) if isinstance(a, dict)]
        warning = str(data.get("warning") or "")
        self.catalog_warning_label.setText("Warning: " + warning if warning else "")
        self.catalog_warning_label.setVisible(bool(warning))
        self._populate_providers()
        self._populate_accounts()
        self._update_controls()

    def _populate_providers(self):
        wanted = API_KEY if self.api_radio.isChecked() else OAUTH
        needle = self.filter_edit.text().strip().lower()
        previous = self._selected_option()
        self.provider_list.blockSignals(True)
        self.provider_list.clear()
        select_row = -1
        for option in self._options:
            if option.get("authType") != wanted:
                continue
            name = str(option.get("providerName") or option.get("providerId") or "")
            method = str(option.get("loginLabel") or option.get("methodName") or "")
            haystack = ("%s %s %s" % (name, method, option.get("providerId") or "")).lower()
            if needle and needle not in haystack:
                continue
            title = name
            if method and method != name:
                title += " — " + method
            if wanted == OAUTH and option.get("subscription"):
                title += " (subscription)"
            title += "  ·  " + _status_text(option.get("status"), wanted)
            if not option.get("canLogin"):
                title += "  ·  info only"
            item = QtWidgets.QListWidgetItem(title)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, option)
            if not option.get("canLogin"):
                item.setForeground(QtGui.QBrush(QtGui.QColor("gray")))
            self.provider_list.addItem(item)
            if (
                previous
                and previous.get("providerId") == option.get("providerId")
                and previous.get("authType") == option.get("authType")
            ):
                select_row = self.provider_list.count() - 1
        self.provider_list.blockSignals(False)
        if select_row >= 0:
            self.provider_list.setCurrentRow(select_row)
        self._update_controls()

    def _populate_accounts(self):
        previous = self._selected_account()
        self.account_list.blockSignals(True)
        self.account_list.clear()
        select_row = -1
        for account in self._accounts:
            name = str(account.get("providerName") or account.get("providerId") or "")
            kind = {API_KEY: "API key", OAUTH: "subscription / OAuth"}.get(
                str(account.get("type") or ""), str(account.get("type") or "account")
            )
            source = str(account.get("source") or "stored")
            stored = self._account_is_stored(account)
            text = "%s — %s" % (name, kind)
            if not stored:
                text += "  ·  %s (informational)" % source
            elif str(account.get("type") or "") == OAUTH:
                text += "  ·  stored (token validity not checked)"
            elif account.get("configured", True):
                text += "  ·  stored, locally resolvable"
            else:
                text += "  ·  stored, not locally resolvable"
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, account)
            self.account_list.addItem(item)
            if (
                previous
                and previous.get("providerId") == account.get("providerId")
                and previous.get("type") == account.get("type")
            ):
                select_row = self.account_list.count() - 1
        self.account_list.blockSignals(False)
        if select_row >= 0:
            self.account_list.setCurrentRow(select_row)
        if not self._accounts:
            placeholder = QtWidgets.QListWidgetItem("No accounts yet.")
            placeholder.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            self.account_list.addItem(placeholder)

    # ---- operations ----------------------------------------------------

    def _begin(self, kind: str, provider: str, name: str, status: str, auth_type: str = "") -> None:
        self._clear_flow()
        self._op = {"kind": kind, "provider": provider, "name": name, "authType": auth_type}
        # Drop the previous operation's terminal helper status ("... finished/failed").
        if self._ready() and not self._closing:
            self.helper_label.setText("")
        self._set_flow_status(status)
        self._update_controls()

    def _start_login(self):
        option = self._selected_option()
        if not option or not option.get("canLogin") or not self._idle():
            return
        provider = str(option.get("providerId") or "")
        name = str(option.get("providerName") or provider)
        auth_type = str(option.get("authType") or "")
        self._begin("login", provider, name, "Signing in to %s…" % name, auth_type)
        if not self.client.login(provider, auth_type):
            self._finish_local("Could not start sign-in; try again.")
        self._update_controls()

    def _check_selected(self):
        account = self._selected_account()
        if not account or not self._idle():
            return
        provider = str(account.get("providerId") or "")
        name = str(account.get("providerName") or provider)
        self._begin(
            "refresh",
            provider,
            name,
            "Checking %s locally and refreshing an OAuth token if needed. This cannot be cancelled; "
            "it finishes safely before the dialog can close…" % name,
        )
        if not self.client.refresh(provider):
            self._finish_local("Could not start the check; try again.")
        self._update_controls()

    def _logout_selected(self):
        account = self._selected_account()
        if not account or not self._idle() or not self._account_is_stored(account):
            return
        provider = str(account.get("providerId") or "")
        name = str(account.get("providerName") or provider)
        confirm = QtWidgets.QMessageBox(self)
        confirm.setIcon(QtWidgets.QMessageBox.Icon.Question)
        confirm.setWindowTitle("Log out")
        confirm.setText(
            "Remove the stored credentials for %s (%s) from this plugin's private Pi account "
            "store?\n\nThis only forgets them locally; it does not revoke the key or token at "
            "the provider." % (name, provider)
        )
        confirm.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
        apply_theme(confirm)
        answer = confirm.exec()
        confirm.deleteLater()
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._begin("logout", provider, name, "Removing %s…" % name)
        if not self.client.logout(provider):
            self._finish_local("Could not start log out; try again.")
        self._update_controls()

    def _cancel_flow(self):
        if self._op is None or self._op.get("kind") != "login":
            return
        self._set_flow_status("Cancelling…")
        self.cancel_button.setEnabled(False)
        # Cancelling a flow never logs out an existing account.
        self.client.cancel()

    def _finish_local(self, message: str):
        self._clear_flow()
        self._op = None
        self._set_flow_status(message)
        self._complete_deferred_close()

    @staticmethod
    def _finished_text(op: dict, result: dict) -> str:
        name = op["name"]
        kind = op["kind"]
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        if kind == "login":
            if op.get("authType") == API_KEY:
                text = (
                    "API key for %s saved in the private Pi account store. It was not sent to or validated "
                    "by the provider." % name
                )
            else:
                text = "OAuth sign-in to %s completed and the credentials were saved." % name
        elif kind == "logout":
            status = data.get("status") if isinstance(data.get("status"), dict) else {}
            if not data.get("hadCredential"):
                text = "Nothing was stored for %s; nothing was removed." % name
            elif data.get("removed"):
                text = "Removed the stored credentials for %s (local only; not revoked at the provider)." % name
            else:
                text = "Log out for %s ran, but a stored credential could not be confirmed removed." % name
            if status.get("configured"):
                text += (
                    " Warning: a credential for this provider is still available via %s; log out cannot "
                    "remove it." % (status.get("source") or "another source")
                )
        elif kind == "refresh":
            if data.get("resolved", data.get("configured")):
                text = (
                    "%s: a credential was resolved locally%s. This does not validate the API key or token "
                    "with the provider; OAuth tokens are refreshed only when Pi needs it."
                    % (name, " (%s)" % data["source"] if data.get("source") else "")
                )
            else:
                text = "%s: no usable credential could be resolved locally. Stored credentials, if any, were kept." % name
        else:
            text = "%s updated." % name
        warning = str(data.get("warning") or "")
        if warning:
            text += "\nWarning: " + warning
        return text

    def _on_finished(self, result: dict):
        op = self._op
        if op is None:
            return
        name = op["name"]
        self._clear_flow()
        self._op = None
        changed = bool(result.get("changed"))
        if result.get("cancelled"):
            text = "Cancelled."
            if changed:
                text += " The account store changed before cancellation."
            self._set_flow_status(text)
        elif result.get("success"):
            self._set_flow_status(self._finished_text(op, result))
        else:
            text = str(result.get("error") or "The operation failed.")
            if changed:
                text += " (The stored credentials changed during this operation; running Pi sessions will be refreshed.)"
            self._set_flow_status("%s: %s" % (name, text))
        self._update_controls()
        if self._pending_close is not None:
            self._complete_deferred_close()
            return
        if not self._closing and self._ready():
            self.client.request_catalog()

    # ---- prompts and events -------------------------------------------

    def _on_prompt(self, event: dict):
        if self._op is None:
            return
        try:
            prompt_id = int(event.get("promptId"))
        except (TypeError, ValueError):
            return
        prompt = event.get("prompt") if isinstance(event.get("prompt"), dict) else {}
        old = self._forms.pop(prompt_id, None)
        if old is not None:
            old.setParent(None)
            old.deleteLater()
        form = _PromptForm(prompt_id, prompt)
        form.submitted.connect(self._on_submit)
        self._forms[prompt_id] = form
        self._add_flow_widget(form)
        form.focus_input()

    def _on_submit(self, prompt_id: int, value: str):
        self.client.respond(prompt_id, value)
        form = self._forms.pop(prompt_id, None)
        if form is not None:
            form.setParent(None)
            form.deleteLater()

    def _on_prompt_cancelled(self, event: dict):
        try:
            prompt_id = int(event.get("promptId"))
        except (TypeError, ValueError):
            return
        form = self._forms.pop(prompt_id, None)
        if form is None:
            return
        form.clear_secret()
        form.setParent(None)
        form.deleteLater()
        self._add_flow_widget(self._note("The sign-in helper withdrew an input request."))

    @staticmethod
    def _note(text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _link_row(self, url: str, label: str = "") -> QtWidgets.QWidget:
        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        if label:
            tag = QtWidgets.QLabel(label)
            tag.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            row_layout.addWidget(tag)
        edit = QtWidgets.QLineEdit(url)
        edit.setReadOnly(True)
        edit.setCursorPosition(0)
        row_layout.addWidget(edit, 1)
        open_button = QtWidgets.QPushButton("Open browser")
        open_button.setEnabled(_is_web_url(url))
        open_button.clicked.connect(lambda _c=False, u=url: self._open_url(u))
        copy_button = QtWidgets.QPushButton("Copy")
        copy_button.clicked.connect(lambda _c=False, u=url: QtWidgets.QApplication.clipboard().setText(u))
        row_layout.addWidget(open_button)
        row_layout.addWidget(copy_button)
        return row

    def _open_url(self, url: str):
        if _is_web_url(url):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url.strip()))

    def _on_event(self, payload: dict):
        if self._op is None:
            return
        event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
        kind = str(event.get("type") or "")
        if kind == "progress":
            message = str(event.get("message") or "")
            if self._progress is None:
                self._progress = self._note(message)
                self._add_flow_widget(self._progress)
            else:
                self._progress.setText(message)
        elif kind == "info":
            self._add_flow_widget(self._note(str(event.get("message") or "")))
            for link in event.get("links") or []:
                if isinstance(link, dict) and link.get("url"):
                    self._add_flow_widget(self._link_row(str(link["url"]), str(link.get("label") or "")))
        elif kind == "auth_url":
            instructions = str(event.get("instructions") or "")
            self._add_flow_widget(
                self._note(
                    "Open this address in your browser and complete the sign-in yourself."
                    + ("\n" + instructions if instructions else "")
                )
            )
            self._add_flow_widget(self._link_row(str(event.get("url") or "")))
        elif kind == "device_code":
            code = str(event.get("userCode") or "")
            lines = ["Enter this code on the verification page:"]
            self._add_flow_widget(self._note(lines[0]))
            code_row = QtWidgets.QWidget()
            code_layout = QtWidgets.QHBoxLayout(code_row)
            code_layout.setContentsMargins(0, 0, 0, 0)
            code_label = QtWidgets.QLabel(code)
            code_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            font = enlarged_font(code_label.font(), 4)
            font.setBold(True)
            code_label.setFont(font)
            code_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            copy = QtWidgets.QPushButton("Copy code")
            copy.clicked.connect(lambda _c=False, c=code: QtWidgets.QApplication.clipboard().setText(c))
            code_layout.addWidget(code_label)
            code_layout.addStretch(1)
            code_layout.addWidget(copy)
            self._add_flow_widget(code_row)
            self._add_flow_widget(self._link_row(str(event.get("verificationUri") or ""), "Page"))
            extra = []
            if event.get("expiresInSeconds"):
                extra.append("The code expires in about %s s." % event["expiresInSeconds"])
            extra.append("Waiting for you to finish in the browser…")
            self._add_flow_widget(self._note(" ".join(extra)))

    # ---- lifecycle -----------------------------------------------------

    def _defer_close(self, result: int) -> bool:
        """A refresh may be persisting rotated tokens and cannot be aborted: finish it first."""
        if self._op is None or self._op.get("kind") != "refresh":
            return False
        if self._pending_close is None:
            self._pending_close = int(result)
        self._set_flow_status("Finishing a safe credential refresh; the dialog will close when it completes…")
        self._update_controls()
        return True

    def _complete_deferred_close(self):
        if self._pending_close is None or self._op is not None:
            return
        result, self._pending_close = self._pending_close, None
        self.done(result)

    def _shutdown(self):
        if self._closing:
            return
        self._closing = True
        for form in list(self._forms.values()):
            form.clear_secret()
        self._forms.clear()
        try:
            if self._op is not None:
                self.client.cancel()
        finally:
            self._op = None
            self.client.stop()

    def done(self, result: int):
        if self._defer_close(result):
            return
        self._shutdown()
        super().done(result)

    def closeEvent(self, event):
        if self._defer_close(int(QtWidgets.QDialog.DialogCode.Rejected)):
            event.ignore()
            return
        self._shutdown()
        super().closeEvent(event)
