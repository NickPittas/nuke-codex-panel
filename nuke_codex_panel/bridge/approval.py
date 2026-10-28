"""Shared per-request confirmation dialog for Nuke Python execution."""

from __future__ import annotations

from PySide6 import QtWidgets


def confirm_python_execution(code: str, parent=None) -> bool:
    """Ask the user to approve one Python snippet; ``parent`` is optional."""
    preview = code if len(code) <= 1200 else code[:1200] + "\n…"
    dialog = QtWidgets.QMessageBox(parent)
    dialog.setWindowTitle("Codex requests Nuke Python execution")
    dialog.setIcon(QtWidgets.QMessageBox.Icon.Question)
    dialog.setText("Run this Python inside the current Nuke session?")
    dialog.setInformativeText(preview)
    dialog.setDetailedText(code)
    dialog.setStandardButtons(
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
    )
    dialog.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
    try:
        return dialog.exec() == QtWidgets.QMessageBox.StandardButton.Yes
    finally:
        dialog.deleteLater()
