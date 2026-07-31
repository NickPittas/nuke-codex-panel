"""Temporary startup hook used by the interactive capture probe."""

from pathlib import Path
import runpy

import nuke


if nuke.GUI:
    from PySide6 import QtCore

    probe = Path(__file__).resolve().parents[1] / "gui_capture_probe.py"
    QtCore.QTimer.singleShot(5000, lambda: runpy.run_path(str(probe)))
