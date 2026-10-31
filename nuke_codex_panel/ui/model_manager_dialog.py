"""Checkbox dialog choosing which models the managed Pi picker offers, plus the default."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .theme import apply_theme

_ID = QtCore.Qt.ItemDataRole.UserRole


class ModelManagerDialog(QtWidgets.QDialog):
    """Edits a model whitelist. Nothing is persisted here: the caller saves on accept.

    ``missing`` are shortlisted ids the accounts do not currently offer. They are shown disabled and
    checked, are never selectable as default, and the backend keeps them on save.
    """

    def __init__(
        self,
        available: list,
        enabled: "list | None",
        default: str,
        parent=None,
        missing: "list | None" = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Manage models")
        self.resize(460, 560)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(
            QtWidgets.QLabel("Checked models appear in the Model picker. One must be the default.")
        )
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        layout.addWidget(self.tree, 1)

        # None means unrestricted: every model starts checked.
        allowed = {m["id"] for m in available} if enabled is None else set(enabled)
        groups: dict[str, QtWidgets.QTreeWidgetItem] = {}
        for model in available:
            provider = model["id"].split("/", 1)[0] if "/" in model["id"] else "Models"
            parent_item = groups.get(provider)
            if parent_item is None:
                parent_item = QtWidgets.QTreeWidgetItem(self.tree, [provider])
                font = parent_item.font(0)
                font.setBold(True)
                parent_item.setFont(0, font)
                parent_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                groups[provider] = parent_item
            item = QtWidgets.QTreeWidgetItem(parent_item, [model.get("label") or model["id"]])
            item.setToolTip(0, model["id"])
            item.setData(0, _ID, model["id"])
            item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsEnabled
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsSelectable
            )
            item.setCheckState(
                0,
                QtCore.Qt.CheckState.Checked if model["id"] in allowed else QtCore.Qt.CheckState.Unchecked,
            )
        if missing:
            gone = QtWidgets.QTreeWidgetItem(self.tree, ["Unavailable (kept in your list)"])
            gone.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            for model_id in missing:
                row_item = QtWidgets.QTreeWidgetItem(gone, ["%s — not offered by your accounts" % model_id])
                row_item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)  # disabled, no id: never selectable
                row_item.setCheckState(0, QtCore.Qt.CheckState.Checked)
        self.tree.expandAll()
        self._labels = {
            m["id"]: "%s — %s" % (m["id"].split("/", 1)[0], m.get("label") or m["id"]) for m in available
        }

        buttons = QtWidgets.QHBoxLayout()
        select_all = QtWidgets.QPushButton("Select all")
        clear = QtWidgets.QPushButton("Clear")
        select_all.clicked.connect(lambda: self._set_all(QtCore.Qt.CheckState.Checked))
        clear.clicked.connect(lambda: self._set_all(QtCore.Qt.CheckState.Unchecked))
        buttons.addWidget(select_all)
        buttons.addWidget(clear)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Default model"))
        self.default_combo = QtWidgets.QComboBox()
        row.addWidget(self.default_combo, 1)
        layout.addLayout(row)

        self.note = QtWidgets.QLabel("")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

        self.box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.box.accepted.connect(self.accept)
        self.box.rejected.connect(self.reject)
        layout.addWidget(self.box)
        self.box.button(QtWidgets.QDialogButtonBox.StandardButton.Save).setProperty("variant", "primary")
        self.note.setProperty("status", "warn")
        apply_theme(self)

        self._wanted_default = default
        self.tree.itemChanged.connect(lambda *_: self._sync_default())
        self._sync_default()

    def _leaves(self):
        """Selectable (available) model rows only."""
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(0, _ID):
                    yield child

    def _set_all(self, state):
        self.tree.blockSignals(True)
        for item in self._leaves():
            item.setCheckState(0, state)
        self.tree.blockSignals(False)
        self._sync_default()

    def selected_ids(self) -> list:
        return [
            item.data(0, _ID)
            for item in self._leaves()
            if item.checkState(0) == QtCore.Qt.CheckState.Checked
        ]

    def default_id(self) -> str:
        return str(self.default_combo.currentData() or "")

    def _sync_default(self):
        keep = self.default_id() or self._wanted_default
        chosen = self.selected_ids()
        self.default_combo.clear()
        for model_id in chosen:
            self.default_combo.addItem(self._labels.get(model_id, model_id), model_id)
        pick = self.default_combo.findData(keep)
        if pick >= 0:
            self.default_combo.setCurrentIndex(pick)
        valid = bool(chosen) and self.default_combo.currentIndex() >= 0
        self.default_combo.setEnabled(bool(chosen))
        self.box.button(QtWidgets.QDialogButtonBox.StandardButton.Save).setEnabled(valid)
        self.note.setText("" if chosen else "Select at least one model.")
