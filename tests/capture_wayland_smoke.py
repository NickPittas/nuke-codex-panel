"""Validate KDE Wayland compositor capture and geometry cropping."""

from pathlib import Path
import tempfile

from PySide6 import QtCore, QtGui, QtWidgets

from nuke_codex_panel.capture.widgets import _image_is_blank, _spectacle_grab


app = QtWidgets.QApplication.instance()
assert app is not None
widget = QtWidgets.QWidget()
widget.setWindowTitle("Nuke Codex Wayland Capture Smoke")
widget.setStyleSheet("background: rgb(210, 30, 40);")
widget.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
widget.resize(420, 260)
widget.show()
widget.raise_()
widget.activateWindow()

for index, screen in enumerate(app.screens()):
    area = screen.availableGeometry()
    widget.move(area.x() + 80, area.y() + 80)
    widget.raise_()
    widget.activateWindow()
    for _event_index in range(25):
        app.processEvents()
        QtCore.QThread.msleep(20)

    path = Path(tempfile.gettempdir()) / (
        "nuke-codex-panel-wayland-smoke-%s.png" % index
    )
    assert _spectacle_grab(widget, path), "Capture failed on %s" % screen.name()
    image = QtGui.QImage(str(path))
    assert image.width() >= 400 and image.height() >= 240, image.size()
    assert not _image_is_blank(image)
    center = image.pixelColor(image.width() // 2, image.height() // 2)
    print(
        "NUKE_CODEX_WAYLAND_SCREEN_OK",
        screen.name(),
        image.width(),
        image.height(),
        center.name(),
    )
    path.unlink(missing_ok=True)

print("NUKE_CODEX_WAYLAND_CAPTURE_OK", len(app.screens()))
widget.close()
