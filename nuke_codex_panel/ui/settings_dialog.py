"""Per-harness binary path overrides with live auto-detection feedback."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..harnesses import HARNESSES, resolve_harness_binary


class HarnessSettingsDialog(QtWidgets.QDialog):
    """Edit the binary path each harness resolves to.

    Paths probe automatically (Settings override, env var, PATH, known install
    dirs); the hint under each row shows what currently resolves.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Harness Settings")
        self.settings = QtCore.QSettings("nuke-codex-panel", "panel")
        self._hints: dict[str, QtWidgets.QLabel] = {}
        self._snapshot: dict[str, str] = {}

        layout = QtWidgets.QVBoxLayout(self)
        note = QtWidgets.QLabel(
            "Binaries are found automatically (PATH and common install dirs).\n"
            "Set an explicit path only when auto-detection fails; it wins over "
            "everything else. Reconnect applies changes."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        box = QtWidgets.QGroupBox("Harness binaries")
        box_layout = QtWidgets.QVBoxLayout(box)
        for entry in HARNESSES:
            key = entry["key"]
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            line = QtWidgets.QLineEdit()
            line.setText(str(self.settings.value("binary/%s" % key, "") or ""))
            line.setPlaceholderText("auto-detected")
            self._snapshot[key] = line.text()
            browse = QtWidgets.QToolButton()
            browse.setText("…")
            browse.setToolTip("Browse for the %s executable" % entry["label"])
            browse.clicked.connect(lambda _checked=False, k=key, l=line: self._browse(k, l))
            row_layout.addWidget(QtWidgets.QLabel(entry["label"]))
            row_layout.addWidget(line, 1)
            row_layout.addWidget(browse)
            hint = QtWidgets.QLabel()
            hint.setObjectName("roleLabel")
            self._hints[key] = hint
            box_layout.addWidget(row)
            box_layout.addWidget(hint)
            line.textChanged.connect(lambda text, k=key: self._save(k, text))
            self._refresh_hint(key)
        layout.addWidget(box)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self._cancel)
        layout.addWidget(buttons)

    def _browse(self, key: str, line: QtWidgets.QLineEdit):
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select the %s executable" % key
        )
        if path:
            line.setText(path)

    def _save(self, key: str, text: str):
        self.settings.setValue("binary/%s" % key, text.strip())
        self.settings.sync()
        self._refresh_hint(key)

    def _refresh_hint(self, key: str):
        path = resolve_harness_binary(key)
        self._hints[key].setText("Detected: %s" % path if path else "Not found")

    def _cancel(self):
        for key, value in self._snapshot.items():
            self.settings.setValue("binary/%s" % key, value)
        self.settings.sync()
        self.reject()
