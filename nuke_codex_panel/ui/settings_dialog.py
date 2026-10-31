"""Nuke Pi settings: private runtime status, Pi accounts and chat text size.

The Pi runtime is installed and owned by this plug-in, so there is nothing to locate or configure
here: the dialog only reports what the plug-in resolves and offers the user-facing preferences.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .theme import FONT_DEFAULT, FONT_MAX, FONT_MIN, apply_theme, set_variant


def runtime_status() -> tuple[bool, str]:
    """``(ok, text)`` for the plug-in's private Pi runtime; a cheap local check, no process started."""
    from .. import pi_runtime

    return pi_runtime.runtime_status()


class PiSettingsDialog(QtWidgets.QDialog):
    """Runtime status, accounts and chat text size for the Nuke Pi panel."""

    # The panel owns the persisted value and the ChatView; the dialog only reports the user's choice.
    font_size_changed = QtCore.Signal(int)

    def __init__(self, font_size: int = FONT_DEFAULT, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuke Pi settings")
        self.setMinimumWidth(460)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)

        runtime_box = QtWidgets.QGroupBox("Pi runtime")
        runtime_layout = QtWidgets.QVBoxLayout(runtime_box)
        note = QtWidgets.QLabel(
            "Nuke Pi runs the official Pi agent on a private Node that the installer placed "
            "inside this plug-in. It never uses a global Node, a global Pi or your PATH."
        )
        note.setWordWrap(True)
        set_variant(note, "status", "muted")
        runtime_layout.addWidget(note)
        self.runtime_label = QtWidgets.QLabel("")
        self.runtime_label.setWordWrap(True)
        self.runtime_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        runtime_layout.addWidget(self.runtime_label)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        self.recheck_button = QtWidgets.QPushButton("Check again")
        self.recheck_button.clicked.connect(self._refresh_runtime)
        row.addWidget(self.recheck_button)
        runtime_layout.addLayout(row)
        layout.addWidget(runtime_box)

        accounts_box = QtWidgets.QGroupBox("Pi accounts")
        accounts_layout = QtWidgets.QHBoxLayout(accounts_box)
        accounts_note = QtWidgets.QLabel(
            "Sign in to model providers with an API key or a subscription. Credentials are kept "
            "in this plug-in's private account store."
        )
        accounts_note.setWordWrap(True)
        accounts_layout.addWidget(accounts_note, 1)
        accounts_button = QtWidgets.QPushButton("Pi accounts…")
        accounts_button.setProperty("variant", "primary")
        accounts_button.clicked.connect(self._open_accounts)
        accounts_layout.addWidget(accounts_button)
        layout.addWidget(accounts_box)

        appearance_box = QtWidgets.QGroupBox("Chat text")
        appearance_layout = QtWidgets.QHBoxLayout(appearance_box)
        appearance_layout.addWidget(QtWidgets.QLabel("Text size (pt)"))
        self.font_spin = QtWidgets.QSpinBox()
        self.font_spin.setRange(FONT_MIN, FONT_MAX)
        self.font_spin.setValue(max(FONT_MIN, min(FONT_MAX, int(font_size))))
        self.font_spin.valueChanged.connect(self.font_size_changed.emit)
        appearance_layout.addWidget(self.font_spin)
        reset = QtWidgets.QPushButton("Reset")
        reset.clicked.connect(lambda: self.font_spin.setValue(FONT_DEFAULT))
        appearance_layout.addWidget(reset)
        appearance_layout.addStretch(1)
        layout.addWidget(appearance_box)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        apply_theme(self)
        self._refresh_runtime()

    def set_font_size(self, points: int):
        """Follow a size change made elsewhere (toolbar) without echoing it back."""
        if self.font_spin.value() != points:
            self.font_spin.blockSignals(True)
            self.font_spin.setValue(points)
            self.font_spin.blockSignals(False)

    def _refresh_runtime(self):
        ok, text = runtime_status()
        self.runtime_label.setText(text)
        set_variant(self.runtime_label, "status", "ok" if ok else "error")

    def _open_accounts(self):
        from .accounts_dialog import PiAccountsDialog

        PiAccountsDialog(self).exec()
