"""Shared per-request confirmation dialog for Nuke Python execution."""

from __future__ import annotations

from PySide6 import QtWidgets

from ..ui.theme import apply_theme
from .control import current_operation


def confirm_python_execution(code: str, parent=None) -> bool:
    """Ask the user to approve one Python snippet; ``parent`` is optional."""
    preview = code if len(code) <= 1200 else code[:1200] + "\n…"
    dialog = QtWidgets.QMessageBox(parent)
    # Lets the harness that owns a control close exactly its own pending dialog on a manual pause.
    dialog.setObjectName("NukeCodexPythonApproval")
    operation = current_operation()
    dialog.setProperty("controlId", operation.control_id if operation else "")
    dialog.setProperty("clientId", operation.client_id if operation else "")
    dialog.setWindowTitle("Nuke Pi requests Nuke Python execution")
    dialog.setIcon(QtWidgets.QMessageBox.Icon.Question)
    dialog.setText("Run this Python inside the current Nuke session?")
    dialog.setInformativeText(preview)
    dialog.setDetailedText(code)
    dialog.setStandardButtons(
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
    )
    dialog.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
    # Top-level windows do not inherit the panel's palette: theme this dialog itself (plug-in scope only).
    apply_theme(dialog)
    try:
        return dialog.exec() == QtWidgets.QMessageBox.StandardButton.Yes
    finally:
        dialog.deleteLater()
