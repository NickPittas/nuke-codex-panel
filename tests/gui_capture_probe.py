"""Interactive Nuke probe for real Viewer/DAG capture diagnostics."""

import json
from pathlib import Path
import traceback

import nuke
from PySide6 import QtCore, QtWidgets

from nuke_codex_panel.capture.widgets import (
    _find_widget,
    _lineage_text,
    capture_target,
    describe_candidates,
)


REPORT = Path("/tmp/nuke-codex-gui-capture-probe.json")
PANEL_REPORT = Path("/tmp/nuke-codex-gui-panel-probe.json")


def widget_record(widget):
    if widget is None:
        return None
    point = widget.mapToGlobal(QtCore.QPoint(0, 0))
    screen = widget.screen()
    return {
        "class": type(widget).__name__,
        "object_name": widget.objectName(),
        "title": widget.windowTitle(),
        "visible": widget.isVisible(),
        "size": [widget.width(), widget.height()],
        "global": [point.x(), point.y()],
        "screen": screen.name() if screen else None,
        "lineage": _lineage_text(widget),
    }


def run_probe():
    report = {"nuke": nuke.NUKE_VERSION_STRING, "targets": {}}
    try:
        nuke.scriptClear()
        checker = nuke.nodes.CheckerBoard2(name="CodexCaptureChecker")
        checker.setXYpos(100, 100)
        blur = nuke.nodes.Blur(name="CodexCaptureBlur")
        blur.setInput(0, checker)
        blur.setXYpos(100, 220)
        viewer = nuke.nodes.Viewer(name="CodexCaptureViewer")
        viewer.setInput(0, blur)
        viewer.setXYpos(100, 340)
        checker.setSelected(False)
        blur.setSelected(True)
        viewer.setSelected(False)
        nuke.show(blur)
        nuke.connectViewer(0, blur)
        nuke.zoomToFitSelected()
    except Exception:
        report["setup_error"] = traceback.format_exc()

    app = QtWidgets.QApplication.instance()
    for target in ("viewer", "nodegraph", "interface"):
        entry = {"candidates": describe_candidates(target, 20)}
        try:
            widget = _find_widget(app, target)
            entry["widget"] = widget_record(widget)
            entry["capture"] = str(capture_target(target, "/tmp"))
        except Exception:
            entry["error"] = traceback.format_exc()
        report["targets"][target] = entry

    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("NUKE_CODEX_GUI_PROBE_READY", REPORT)


def run_panel_probe():
    """Invoke the real docked panel slots and retain their exact UI errors."""
    app = QtWidgets.QApplication.instance()
    panels = [
        widget
        for widget in app.allWidgets()
        if widget.objectName() == "NukeCodexPanel"
    ]
    report = {"panel_count": len(panels), "captures": {}}
    if panels:
        panel = panels[0]
        panel.clear_pending_attachments()
        for target in ("viewer", "nodegraph", "interface"):
            try:
                before = list(panel.pending_images)
                panel.capture(target)
                after = list(panel.pending_images)
                report["captures"][target] = {
                    "status": panel.status.text(),
                    "new_paths": [path for path in after if path not in before],
                }
            except Exception:
                report["captures"][target] = {"exception": traceback.format_exc()}
    PANEL_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("NUKE_CODEX_GUI_PANEL_PROBE_READY", PANEL_REPORT)


QtCore.QTimer.singleShot(4000, run_probe)
QtCore.QTimer.singleShot(12_000, run_panel_probe)
