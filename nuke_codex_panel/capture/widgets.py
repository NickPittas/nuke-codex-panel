"""Nuke-aware Qt widget discovery and screenshot capture."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil


class CaptureError(RuntimeError):
    """Raised when the requested Nuke UI target cannot be found or saved."""


TARGET_HINTS = {
    "viewer": ("viewer",),
    "nodegraph": ("dag", "node graph", "nodegraph"),
    "interface": (),
}

_CAPTURE_BACKENDS = {}


def capture_backend(path: str | Path) -> str:
    """Return the backend that produced a capture in this process."""
    return _CAPTURE_BACKENDS.get(str(Path(path).resolve()), "unknown backend")


def _safe_call(widget, attribute: str) -> str:
    value = getattr(widget, attribute, None)
    if not callable(value):
        return ""
    try:
        return str(value() or "")
    except Exception:
        return ""


def _widget_text(widget) -> str:
    parts = [
        _safe_call(widget, "objectName"),
        _safe_call(widget, "windowTitle"),
        _safe_call(widget, "accessibleName"),
    ]
    try:
        parts.append(str(widget.metaObject().className()))
    except Exception:
        parts.append(type(widget).__name__)
    return " ".join(part for part in parts if part).lower()


def _lineage_text(widget) -> str:
    parts = []
    current = widget
    for _ in range(12):
        if current is None:
            break
        parts.append(_widget_text(current))
        current = current.parentWidget() if hasattr(current, "parentWidget") else None
    return " ".join(parts)


def _area(widget) -> int:
    try:
        return max(0, widget.width()) * max(0, widget.height())
    except Exception:
        return 0


def _is_our_panel(widget) -> bool:
    return "nukecodexpanel" in _lineage_text(widget).replace(" ", "")


def _surface_for(container, target: str):
    """Prefer an OpenGL framebuffer inside a matching Viewer/DAG container."""
    from PySide6 import QtWidgets

    descendants = [container]
    descendants.extend(container.findChildren(QtWidgets.QWidget))
    framebuffer = [
        widget
        for widget in descendants
        if widget.isVisible()
        and callable(getattr(widget, "grabFramebuffer", None))
        and _area(widget) > 4096
    ]
    if framebuffer:
        return max(framebuffer, key=_area)

    if target == "nodegraph":
        graphics = [
            widget
            for widget in descendants
            if widget.isVisible()
            and isinstance(widget, QtWidgets.QGraphicsView)
            and _area(widget) > 4096
        ]
        if graphics:
            return max(graphics, key=_area)
    return container


def _score_widget(widget, target: str) -> int:
    own = _widget_text(widget)
    lineage = _lineage_text(widget)
    class_name = type(widget).__name__.lower()
    score = 0
    object_name = _safe_call(widget, "objectName").lower()
    if target == "viewer" and object_name.startswith("viewer."):
        score += 250
    if target == "nodegraph" and object_name.startswith("dag."):
        score += 250
    for hint in TARGET_HINTS[target]:
        if hint in own:
            score += 100
        elif hint in lineage:
            score += 35
    if target == "viewer" and ("opengl" in class_name or "gl" in own):
        score += 20
    if target == "nodegraph" and "graphicsview" in class_name:
        score += 20
    if _area(widget) > 200_000:
        score += 5
    return score


def _find_main_window(app):
    visible = [widget for widget in app.topLevelWidgets() if widget.isVisible()]
    preferred = []
    for widget in visible:
        text = _widget_text(widget)
        if "foundry" in text or ("nuke" in text and "main" in text):
            preferred.append(widget)
    candidates = preferred or [widget for widget in visible if not _is_our_panel(widget)]
    return max(candidates, key=_area) if candidates else None


def _find_widget(app, target: str):
    if target == "interface":
        return _find_main_window(app)

    candidates = []
    for widget in app.allWidgets():
        try:
            if not widget.isVisible() or _area(widget) < 4096 or _is_our_panel(widget):
                continue
        except Exception:
            continue
        score = _score_widget(widget, target)
        if score:
            candidates.append((score, _area(widget), widget))

    if not candidates:
        return None
    _score, _size, container = max(candidates, key=lambda item: (item[0], item[1]))
    return container


def describe_candidates(target: str, limit: int = 12) -> list[str]:
    """Return useful visible-widget diagnostics for an in-Nuke failure report."""
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        return []
    rows = []
    for widget in app.allWidgets():
        if not widget.isVisible() or _area(widget) < 4096:
            continue
        score = _score_widget(widget, target)
        if score:
            rows.append((score, _area(widget), _widget_text(widget)))
    rows.sort(reverse=True)
    return ["score=%s area=%s %s" % row for row in rows[:limit]]


def _screen_grab(widget):
    """Capture displayed pixels, including OpenGL surfaces composited by the OS."""
    from PySide6 import QtCore, QtWidgets

    app = QtWidgets.QApplication.instance()
    screen = widget.screen() or (app.primaryScreen() if app else None)
    if screen is None:
        return None
    try:
        top_left = widget.mapToGlobal(QtCore.QPoint(0, 0))
        pixmap = screen.grabWindow(
            0,
            top_left.x(),
            top_left.y(),
            widget.width(),
            widget.height(),
        )
        return None if pixmap.isNull() else pixmap
    except Exception:
        return None


def _image_is_blank(image) -> bool:
    """Detect compositor-denied captures without rejecting normally dark images."""
    if image is None or image.isNull() or image.width() < 2 or image.height() < 2:
        return True
    sample_x = max(1, image.width() // 24)
    sample_y = max(1, image.height() // 24)
    minimum = 255
    maximum = 0
    colorful_or_bright = 0
    samples = 0
    for y in range(0, image.height(), sample_y):
        for x in range(0, image.width(), sample_x):
            color = image.pixelColor(x, y)
            channels = (color.red(), color.green(), color.blue())
            minimum = min(minimum, *channels)
            maximum = max(maximum, *channels)
            if max(channels) > 12 or max(channels) - min(channels) > 5:
                colorful_or_bright += 1
            samples += 1
    # Wayland-denied Qt grabs are uniformly transparent/black. A genuinely dark
    # Viewer still normally has chrome, controls, text, or small pixel variation.
    return (maximum - minimum <= 3 and maximum <= 8) or colorful_or_bright == 0


def _spectacle_grab(widget, path: Path) -> bool:
    """Capture KDE Wayland's composited desktop and crop to a Qt widget."""
    from PySide6 import QtCore, QtGui, QtWidgets

    executable = shutil.which("spectacle")
    app = QtWidgets.QApplication.instance()
    if not executable or app is None:
        return False

    desktop_path = path.with_name(path.stem + "-desktop.png")
    # Make the embedded Viewer/DAG native surfaces repaint before requesting a
    # compositor frame. Blocking Nuke's GUI thread with waitForFinished() can
    # make those surfaces disappear from a KWin screenshot while ordinary Qt
    # chrome remains visible.
    widget.update()
    app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 100)
    process = QtCore.QProcess()
    environment = QtCore.QProcessEnvironment.systemEnvironment()
    # Nuke is commonly launched with vendor LD_PRELOAD/Qt overrides (for
    # example Mocha's bundled FreeType). Passing those into KDE's Spectacle can
    # corrupt or disable its independent Qt/compositor capture process.
    for name in (
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        "QML2_IMPORT_PATH",
        "PYTHONHOME",
        "PYTHONPATH",
    ):
        environment.remove(name)
    process.setProcessEnvironment(environment)
    process.setProgram(executable)
    process.setArguments(
        [
            "--background",
            "--nonotify",
            "--fullscreen",
            "--delay",
            "250",
            "--output",
            str(desktop_path),
        ]
    )
    loop = QtCore.QEventLoop()
    timed_out = {"value": False}

    def timeout():
        timed_out["value"] = True
        loop.quit()

    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(timeout)
    process.finished.connect(loop.quit)
    process.start()
    timer.start(12_000)
    loop.exec()
    timer.stop()
    if timed_out["value"] or process.state() != QtCore.QProcess.ProcessState.NotRunning:
        process.kill()
        process.waitForFinished(1000)
        desktop_path.unlink(missing_ok=True)
        return False
    if process.exitStatus() != QtCore.QProcess.ExitStatus.NormalExit or process.exitCode() != 0:
        desktop_path.unlink(missing_ok=True)
        return False

    desktop = QtGui.QImage(str(desktop_path))
    desktop_path.unlink(missing_ok=True)
    if _image_is_blank(desktop):
        return False

    screens = app.screens()
    if not screens:
        return False
    virtual = screens[0].geometry()
    for screen in screens[1:]:
        virtual = virtual.united(screen.geometry())
    if virtual.width() <= 0 or virtual.height() <= 0:
        return False

    top_left = widget.mapToGlobal(QtCore.QPoint(0, 0))
    scale_x = desktop.width() / float(virtual.width())
    scale_y = desktop.height() / float(virtual.height())
    crop = QtCore.QRect(
        round((top_left.x() - virtual.x()) * scale_x),
        round((top_left.y() - virtual.y()) * scale_y),
        max(1, round(widget.width() * scale_x)),
        max(1, round(widget.height() * scale_y)),
    ).intersected(desktop.rect())
    if crop.isEmpty():
        return False
    image = desktop.copy(crop)
    return not _image_is_blank(image) and bool(image.save(str(path), "PNG"))


def _save_widget(widget, target: str, path: Path) -> bool:
    # Qt screen grabs are intentionally blacked out by KWin under Wayland.
    # Spectacle has compositor permission and captures OpenGL surfaces as shown.
    if (
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        and os.environ.get("XDG_CURRENT_DESKTOP", "").lower().startswith("kde")
        and _spectacle_grab(widget, path)
    ):
        _CAPTURE_BACKENDS[str(path.resolve())] = "KDE compositor (Spectacle)"
        return True

    # Capturing the visible screen region is more reliable for Nuke's externally
    # composited OpenGL Viewer and DAG than QWidget/OpenGL framebuffer reads.
    screen_pixmap = _screen_grab(widget)
    if screen_pixmap is not None:
        screen_image = screen_pixmap.toImage()
        if not _image_is_blank(screen_image) and screen_image.save(str(path), "PNG"):
            _CAPTURE_BACKENDS[str(path.resolve())] = "Qt screen grab"
            return True

    surface = _surface_for(widget, target)
    grab_framebuffer = getattr(surface, "grabFramebuffer", None)
    if callable(grab_framebuffer):
        try:
            image = grab_framebuffer()
            if image is not None and not _image_is_blank(image):
                if image.save(str(path), "PNG"):
                    _CAPTURE_BACKENDS[str(path.resolve())] = "OpenGL framebuffer"
                    return True
        except Exception:
            pass
    widget_image = widget.grab().toImage()
    if not _image_is_blank(widget_image) and widget_image.save(str(path), "PNG"):
        _CAPTURE_BACKENDS[str(path.resolve())] = "Qt widget grab"
        return True
    return False


def capture_target(target: str, output_dir: str | Path | None = None) -> Path:
    """Capture a visible Nuke Viewer, Node Graph, or main interface to PNG."""
    if target not in TARGET_HINTS:
        raise ValueError("target must be viewer, nodegraph, or interface")

    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        raise CaptureError("No QApplication is running")

    widget = _find_widget(app, target)
    if widget is None:
        diagnostics = "; ".join(describe_candidates(target, limit=5))
        suffix = (" Candidates: " + diagnostics) if diagnostics else ""
        raise CaptureError("Could not find a visible %s widget.%s" % (target, suffix))

    if output_dir is None:
        cache_root = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache"))
        directory = cache_root / "nuke-codex-panel" / "captures"
    else:
        directory = Path(output_dir) / "nuke-codex-panel"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = directory / ("%s-%s.png" % (target, stamp))
    if not _save_widget(widget, target, path):
        raise CaptureError(
            "All capture backends returned blank or unavailable pixels for %s; "
            "no image was written to %s" % (target, path)
        )
    return path.resolve()
