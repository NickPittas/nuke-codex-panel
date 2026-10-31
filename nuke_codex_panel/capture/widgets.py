"""Nuke-aware Qt widget discovery and screenshot capture."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil


class CaptureError(RuntimeError):
    """Raised when the requested Nuke UI target cannot be found or saved."""


_TARGETS = ("viewer", "nodegraph", "interface")

# Widget-screenshot targets only; the Viewer is rendered, not screenshotted.
TARGET_HINTS = {
    "nodegraph": ("dag", "node graph", "nodegraph"),
    "interface": (),
}

_CAPTURE_BACKENDS = {}
_CAPTURE_METADATA = {}


def capture_backend(path: str | Path) -> str:
    """Return the backend that produced a capture in this process."""
    return _CAPTURE_BACKENDS.get(str(Path(path).resolve()), "unknown backend")


def capture_metadata(path: str | Path) -> dict:
    """Return the metadata recorded for a capture made in this process."""
    try:
        return dict(_CAPTURE_METADATA[str(Path(path).resolve())])
    except KeyError:
        raise CaptureError("No capture metadata recorded for %s" % path) from None


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
    if target == "nodegraph" and not object_name.startswith("dag."):
        return 0  # only the real DAG widget; never a pane/tab that merely contains one
    if target == "nodegraph" and object_name.startswith("dag."):
        score += 250
    for hint in TARGET_HINTS[target]:
        if hint in own:
            score += 100
        elif hint in lineage:
            score += 35
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
            # Native OpenGL widgets report an empty visibleRegion even when shown,
            # so instead require that the DAG's own tab/stack page is the current one.
            if target == "nodegraph":
                owner, page = _tab_owner(widget)
                if owner is not None and owner.currentWidget() is not page:
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


def _grim_grab(widget, path: Path) -> bool:
    """Capture Hyprland/Sway (wlroots) compositor pixels via grim."""
    from PySide6 import QtCore, QtGui, QtWidgets

    executable = shutil.which("grim")
    app = QtWidgets.QApplication.instance()
    if not executable or app is None:
        return False
    # -g takes the compositor's layout coordinates, which are the same logical
    # space Qt's mapToGlobal reports, and renders at the output's native
    # resolution, so HiDPI scaling needs no math here.
    top_left = widget.mapToGlobal(QtCore.QPoint(0, 0))
    geometry = "%d,%d %dx%d" % (top_left.x(), top_left.y(), widget.width(), widget.height())
    # Same reasoning as the Spectacle path: coax Nuke's GL surfaces to present
    # a fresh frame so the compositor has current pixels to hand over.
    widget.update()
    app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 100)
    process = QtCore.QProcess()
    process.setProgram(executable)
    process.setArguments(["-g", geometry, str(path)])
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
        path.unlink(missing_ok=True)
        return False
    if process.exitStatus() != QtCore.QProcess.ExitStatus.NormalExit or process.exitCode() != 0:
        path.unlink(missing_ok=True)
        return False

    image = QtGui.QImage(str(path))
    return not image.isNull() and not _image_is_blank(image)


def _dag_gl_window(widget):
    """(window, widget): the QOpenGLWindow hosting the DAG and the live DAG widget.

    The DAG draws in a QOpenGLWindow hosted by createWindowContainer, which is a
    QWindow and not a QWidget descendant. Only a destroyed Qt wrapper (the view
    change replaced the DAG) is stale: the live DAG is then looked up once.
    Anything else is a real failure.
    """
    try:
        return _gl_window(widget), widget
    except RuntimeError as error:
        if isinstance(error, CaptureError) or "already deleted" not in str(error):
            raise
    from PySide6 import QtWidgets

    widget = _find_widget(QtWidgets.QApplication.instance(), "nodegraph")
    if widget is None:
        raise CaptureError("The Node Graph (DAG) disappeared during capture.")
    return _gl_window(widget), widget


def _save_framebuffer(surface, path: Path) -> bool:
    grab_framebuffer = getattr(surface, "grabFramebuffer", None)
    if not callable(grab_framebuffer):
        return False
    try:
        image = grab_framebuffer()
        if image is not None and not _image_is_blank(image) and image.save(str(path), "PNG"):
            _CAPTURE_BACKENDS[str(path.resolve())] = "OpenGL framebuffer"
            return True
    except Exception:
        pass
    return False


def _save_widget(widget, target: str, path: Path) -> bool:
    # The DAG's own QOpenGLWindow holds exactly the pixels it presented: read them
    # directly, before any desktop/screen grab that occlusion or the wrong display
    # could corrupt. The interface target is the whole main window; no single GL
    # window is it.
    if target == "nodegraph":
        window, widget = _dag_gl_window(widget)
        if _save_framebuffer(window, path):
            return True

    # Qt screen grabs are intentionally blacked out by KWin under Wayland.
    # Spectacle has compositor permission and captures OpenGL surfaces as shown.
    if (
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        and os.environ.get("XDG_CURRENT_DESKTOP", "").lower().startswith("kde")
        and _spectacle_grab(widget, path)
    ):
        _CAPTURE_BACKENDS[str(path.resolve())] = "KDE compositor (Spectacle)"
        return True

    # Hyprland/Sway (wlroots) are invisible to Qt grabs for the same reason; grim
    # reads the compositor directly, like Spectacle does on KDE. It exits 0 with
    # a blank image only if grim itself is unavailable.
    if (
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        and _grim_grab(widget, path)
    ):
        _CAPTURE_BACKENDS[str(path.resolve())] = "wlroots compositor (grim)"
        return True

    # Capturing the visible screen region is more reliable for Nuke's externally
    # composited OpenGL Viewer and DAG than QWidget/OpenGL framebuffer reads.
    screen_pixmap = _screen_grab(widget)
    if screen_pixmap is not None:
        screen_image = screen_pixmap.toImage()
        if not _image_is_blank(screen_image) and screen_image.save(str(path), "PNG"):
            _CAPTURE_BACKENDS[str(path.resolve())] = "Qt screen grab"
            return True

    if _save_framebuffer(_surface_for(widget, target), path):
        return True
    widget_image = widget.grab().toImage()
    if not _image_is_blank(widget_image) and widget_image.save(str(path), "PNG"):
        _CAPTURE_BACKENDS[str(path.resolve())] = "Qt widget grab"
        return True
    return False


def _capture_directory(output_dir) -> Path:
    if output_dir is None:
        cache_root = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache"))
        directory = cache_root / "nuke-codex-panel" / "captures"
    else:
        directory = Path(output_dir) / "nuke-codex-panel"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _image_size(path: Path) -> tuple[int, int]:
    from PySide6 import QtGui

    image = QtGui.QImage(str(path))
    if image.isNull():
        raise CaptureError("Capture was written but cannot be read back: %s" % path)
    return image.width(), image.height()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_format(nuke) -> dict:
    fmt = nuke.root().format()
    return {
        "project_format_name": fmt.name() or "",
        "project_format_width": int(fmt.width()),
        "project_format_height": int(fmt.height()),
    }


def _is_root(group) -> bool:
    return group.Class() == "Root"


def _group_label(group) -> str:
    return "root" if _is_root(group) else group.fullName()


def _live_viewer_node(window):
    """The Viewer node of ``window`` if it is alive, a Viewer, and in this script."""
    if window is None:
        return None
    try:
        node = window.node()
        if node is None or node.Class() != "Viewer":
            return None
        import nuke

        return node if nuke.toNode(node.fullName()) == node else None
    except Exception:
        return None  # stale window whose node was deleted or script was cleared


def _find_viewer_node(nuke):
    """Return the existing Viewer to render: the active one, else the only one."""
    node = _live_viewer_node(nuke.activeViewer())
    if node is not None:
        return node
    viewers = nuke.allNodes("Viewer", recurseGroups=True)
    if len(viewers) == 1:
        return viewers[0]
    if not viewers:
        raise CaptureError("No Viewer node exists in the script; nothing to render.")
    raise CaptureError(
        "No Viewer is active and several exist (%s); activate one."
        % ", ".join(node.fullName() for node in viewers)
    )


def _tree_error_nodes(node) -> list:
    """Names of nodes in ``node``'s dependency tree that report an error."""
    seen = set()
    stack = [node]
    names = []
    while stack:
        current = stack.pop()
        full = current.fullName()
        if full in seen:
            continue
        seen.add(full)
        if current.hasError():
            names.append(full)
        stack.extend(current.dependencies())
    return names


def _render_errors(viewer, indices, window) -> list:
    """Errors in the Viewer's actually displayed A/B dependency trees.

    executeMultiple can write an error plate when an upstream node fails, so a
    written file is not proof of a good render. ``indices`` are the active
    primary/secondary input indices (None entries ignored); with no window,
    every connected Viewer input is checked. Only those trees are inspected, so
    unrelated broken nodes do not poison a valid Viewer.
    """
    if indices is None:
        indices = list(range(viewer.inputs()))
    failures = []
    checked = set()
    for index in indices:
        if index is None or index in checked:
            continue
        checked.add(index)
        source = viewer.input(index)
        if source is None:
            continue
        # Trust the engine's verdict for the displayed tree; inactive branches
        # (e.g. an unused Switch input) must not count. Traverse only to name
        # the culprits once the engine reports an error.
        if source.treeHasError() or source.hasError():
            bad = _tree_error_nodes(source)
            failures.append(
                "input %d (%s) has errors in: %s"
                % (index, source.fullName(), ", ".join(bad) or source.fullName())
            )
    if window is not None:
        message = window.getCurrentErrorMessage()
        if message:
            failures.append("Viewer error: %s" % message)
    return failures


def _finite_numbers(value, count: int, label: str) -> tuple:
    import math

    if (
        not isinstance(value, (list, tuple))
        or len(value) != count
        or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in value)
    ):
        raise ValueError("%s must be %d finite numbers, got %r" % (label, count, value))
    return tuple(float(item) for item in value)


def normalize_viewer_navigation(zoom=None, center=None, region=None) -> dict | None:
    """Validate Viewer framing arguments (pure); None when no navigation was requested.

    ``zoom`` is a positive percentage or 'fit'; ``center`` is [x, y] and ``region`` is
    [x0, y0, x1, y1], both in source-image pixels (origin bottom-left). A region is
    framing, so it excludes zoom and center.
    """
    import math

    if zoom is None and center is None and region is None:
        return None
    if region is not None:
        if zoom is not None or center is not None:
            raise ValueError("region is mutually exclusive with zoom and center")
        x0, y0, x1, y1 = _finite_numbers(region, 4, "region")
        if x1 <= x0 or y1 <= y0:
            raise ValueError("region must have positive width and height: [x0, y0, x1, y1] with x1>x0, y1>y0")
        return {"region": (x0, y0, x1, y1)}
    navigation = {}
    if zoom is not None:
        if isinstance(zoom, str) and zoom.strip().lower() == "fit":
            navigation["zoom"] = "fit"
        elif isinstance(zoom, bool) or not isinstance(zoom, (int, float)) or not math.isfinite(zoom) or zoom <= 0:
            raise ValueError("zoom must be a positive finite percentage or 'fit', got %r" % (zoom,))
        else:
            navigation["zoom"] = float(zoom)
    if center is not None:
        navigation["center"] = _finite_numbers(center, 2, "center")
    return navigation


def _find_viewer_image_widget(viewer):
    """The visible Image_Window widget that displays ``viewer``; fail clearly if unknown or ambiguous."""
    from PySide6 import QtWidgets

    names = {viewer.name(), viewer.fullName()}

    def titled(widget) -> bool:
        current = widget
        for _ in range(12):
            if current is None:
                return False
            for attribute in ("windowTitle", "objectName"):
                text = _safe_call(current, attribute).strip()
                if text in names or any(text.startswith(name + " ") for name in names):
                    return True
            current = current.parentWidget() if hasattr(current, "parentWidget") else None
        return False

    candidates = []
    import shiboken6

    for widget in QtWidgets.QApplication.allWidgets():
        if not shiboken6.isValid(widget):
            continue
        try:
            if widget.metaObject().className() != "Image_Window" or not widget.isVisible():
                continue
        except Exception:
            continue
        if not _is_our_panel(widget):
            candidates.append(widget)
    matching = [widget for widget in candidates if titled(widget)]
    if not matching and len(candidates) == 1:
        import nuke

        if len(nuke.allNodes("Viewer", recurseGroups=True)) == 1:
            matching = candidates
    if len(matching) != 1:
        raise CaptureError(
            "Cannot navigate Viewer %s: %d visible Viewer image widgets match it (%d visible in all); "
            "show exactly one panel for this Viewer."
            % (viewer.fullName(), len(matching), len(candidates))
        )
    return matching[0]


def _fresh_roi_button(viewer):
    """The visible 'Enables Region-Of-Interest' QToolButton in ``viewer``'s own pane, or None.

    Looked up fresh for every click (ROI changes and renders rebuild the toolbar). Candidates come
    from QApplication.allWidgets filtered to live QToolButtons, never from findChildren on the
    abstract-button class, and each wrapper is checked with shiboken6.isValid before use.
    """
    from PySide6 import QtWidgets
    import shiboken6

    image = _find_viewer_image_widget(viewer)
    buttons = [
        widget
        for widget in QtWidgets.QApplication.allWidgets()
        if shiboken6.isValid(widget)
        and isinstance(widget, QtWidgets.QToolButton)
        and widget.isVisible()
        and widget.isCheckable()
        and "region-of-interest" in (widget.toolTip() or "").lower()
    ]
    current = image.parentWidget()
    for _ in range(12):
        if current is None:
            return None
        inside = [button for button in buttons if current.isAncestorOf(button)]
        if len(inside) == 1:
            return inside[0]
        if len(inside) > 1:
            raise CaptureError("Several Region-Of-Interest buttons found in the Viewer pane; cannot tell its state")
        current = current.parentWidget()
    return None


def _suspend_viewer_roi(viewer, restorers: list) -> None:
    """Turn the Viewer's ROI off for the render if the PUBLIC ``roiEnabled()`` says it is on; queue restoration.

    The toolbar button's checked state is not the ROI state, so it is never read; the button is only
    clicked (a toggle), freshly discovered for every click, and the public bool is verified after each.
    """
    from PySide6 import QtWidgets

    if not viewer.roiEnabled():
        return
    app = QtWidgets.QApplication.instance()

    def set_state(enabled: bool) -> None:
        if bool(viewer.roiEnabled()) != enabled:
            try:
                button = _fresh_roi_button(viewer)
            except CaptureError as exc:
                raise CaptureError("Viewer ROI cannot be %s: %s" % ("re-enabled" if enabled else "disabled", exc)) from exc
            if button is None:
                raise CaptureError(
                    "Viewer ROI is enabled and its toolbar button was not found; set the ROI manually and retry"
                )
            button.click()
            app.processEvents()
        if bool(viewer.roiEnabled()) != enabled:
            raise CaptureError(
                "Viewer ROI could not be %s; set it manually and retry"
                % ("re-enabled" if enabled else "disabled")
            )

    set_state(False)
    restorers.append(lambda: set_state(True))


def _suspend_capture_resize(viewer, restorers: list) -> None:
    """Force the Viewer's Capture-resize off for the render (it only enlarges the canvas); queue restoration."""
    if "capture_resize" not in viewer.knobs():
        return
    knob = viewer["capture_resize"]
    saved = knob.toScript()
    knob.setValue(False)
    restorers.append(lambda: knob.fromScript(saved))


def apply_viewer_navigation(viewer, window, navigation: dict) -> dict:
    """Frame the real Viewer (native zoom, then a Qt middle-drag pan) and describe it honestly.

    Persists as the Viewer's inspection state. The Viewer has no public pan getter, so the
    centre is reported as requested; the zoom is verified through getZoomLevel.
    """
    import math
    import nuke
    from PySide6 import QtCore, QtGui, QtWidgets

    if window is None or window.node() != viewer:
        raise CaptureError("Viewer navigation needs %s to be the active Viewer; click its panel." % viewer.fullName())
    app = QtWidgets.QApplication.instance()
    app.processEvents()
    index = window.activeInput(False)
    source = viewer.input(index) if index is not None else None
    if source is None:
        raise CaptureError("Viewer %s has no active input to frame." % viewer.fullName())
    fmt = source.format()
    format_width, format_height = float(fmt.width()), float(fmt.height())
    aspect = float(fmt.pixelAspect()) or 1.0
    widget = _find_viewer_image_widget(viewer)
    gl = _gl_window(widget)
    if gl is None:
        raise CaptureError("Viewer %s has no drawn OpenGL window to navigate." % viewer.fullName())
    view_width, view_height = float(gl.width()), float(gl.height())
    dpr = float(gl.devicePixelRatio())

    def fit(width, height):
        return min(view_width / (width * aspect), view_height / height) * 100.0

    region = navigation.get("region")
    requested_zoom = navigation.get("zoom")
    if region is not None:
        center = ((region[0] + region[2]) / 2.0, (region[1] + region[3]) / 2.0)
        zoom = fit(region[2] - region[0], region[3] - region[1])
    else:
        center = navigation.get("center") or (format_width / 2.0, format_height / 2.0)
        if requested_zoom == "fit":
            zoom = fit(format_width, format_height)
        elif requested_zoom is not None:
            zoom = requested_zoom
        else:
            zoom = float(viewer.getZoomLevel())
    if not math.isfinite(zoom) or zoom <= 0:
        raise CaptureError("Computed Viewer zoom %r is not a positive finite percentage." % zoom)
    needs_pan = abs(center[0] - format_width / 2.0) > 1e-9 or abs(center[1] - format_height / 2.0) > 1e-9
    if (needs_pan or region is not None or requested_zoom == "fit") and abs(dpr - 1.0) > 1e-9:
        raise CaptureError(
            "Viewer centring/fitting is only verified at device pixel ratio 1 (this display reports %s)." % dpr
        )

    viewer.setZoomLevel(float(zoom), True)  # resets the centre to the format centre
    app.processEvents()
    actual = float(viewer.getZoomLevel())
    if abs(actual - zoom) > max(0.01, zoom * 1e-3):
        raise CaptureError(
            "Nuke did not accept Viewer zoom %.4f%% (reads back %.4f%%); it may be outside the Viewer's range."
            % (zoom, actual)
        )
    if needs_pan:
        start = QtCore.QPointF(view_width / 2.0, view_height / 2.0)
        end = start + QtCore.QPointF(
            (format_width / 2.0 - center[0]) * actual / 100.0 * aspect,
            (center[1] - format_height / 2.0) * actual / 100.0,  # image Y is up, Qt Y is down
        )
        origin = QtCore.QPointF(gl.mapToGlobal(QtCore.QPoint(0, 0)))
        middle = QtCore.Qt.MouseButton.MiddleButton
        none = QtCore.Qt.MouseButton.NoButton
        modifiers = QtCore.Qt.KeyboardModifier.NoModifier
        for kind, point, button, buttons in (
            (QtCore.QEvent.Type.MouseButtonPress, start, middle, middle),
            (QtCore.QEvent.Type.MouseMove, end, none, middle),
            (QtCore.QEvent.Type.MouseButtonRelease, end, middle, none),
        ):
            QtCore.QCoreApplication.sendEvent(
                gl, QtGui.QMouseEvent(kind, point, point, origin + point, button, buttons, modifiers)
            )
        app.processEvents()
    meta = {
        "viewer_zoom_percent": float(viewer.getZoomLevel()),
        "requested_viewer_center": [center[0], center[1]],
        "viewer_center_is_requested_not_read_back": True,
        "viewer_source_format_width": int(format_width),
        "viewer_source_format_height": int(format_height),
        "viewer_source_pixel_aspect": aspect,
        "viewer_viewport_width": int(view_width),
        "viewer_viewport_height": int(view_height),
    }
    if region is not None:
        meta["requested_region"] = list(region)
    return meta


def _capture_viewer(frame, directory: Path, navigation: dict | None = None) -> tuple[Path, dict]:
    """Synchronously render the existing Viewer at ``frame`` via nuke.executeMultiple.

    executeMultiple returns only after the frame is rendered (or raises on
    failure/cancel), so no delay or polling is involved. There is no timeout.
    """
    import nuke

    # A just-created Viewer's native op is initialised by the Qt event loop;
    # flush queued events (no delay) so the render targets a live viewer.
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        raise CaptureError("No QApplication is running")
    app.processEvents()
    viewer = _find_viewer_node(nuke)
    nuke_frame = int(nuke.frame())
    requested = nuke_frame if frame is None else int(frame)

    active = nuke.activeViewer()
    view = None
    if active is not None:
        try:
            view = active.view()
        except Exception:
            view = None
    if not view:
        view = nuke.views()[0]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    pattern = str(directory / ("viewer-%s.####.png" % stamp))
    final = directory / ("viewer-%s-f%d.png" % (stamp, requested))

    file_knob = viewer["file"]
    old_file = file_knob.toScript()
    from ..tools import graph_snapshot

    old_modified = nuke.root().modified()
    before_graph = graph_snapshot()
    scope_group = viewer.parent()
    with scope_group:
        old_selected = [n.fullName() for n in nuke.selectedNodes()]
    # activeInput lives on ViewerWindow, not the Viewer node; without a window
    # the active A/B inputs are unknown and reported as such (None).
    window = active if active is not None and active.node() == viewer else None
    inputs = {"A": (None, None), "B": (None, None)}
    if window is not None:
        for label, secondary in (("A", False), ("B", True)):
            index = window.activeInput(secondary)
            source = viewer.input(index) if index is not None else None
            inputs[label] = (index, source.fullName() if source is not None else None)
    process = viewer["viewerProcess"].value() if "viewerProcess" in viewer.knobs() else ""
    restorers = []
    restore_errors = []
    navigation_meta = {}
    try:
        # Stale pixels outside an enabled ROI must never be certified as the image.
        _suspend_viewer_roi(viewer, restorers)
        if navigation is not None:
            # Navigated captures need the viewport-sized render, not Capture-resize's canvas.
            _suspend_capture_resize(viewer, restorers)
            navigation_meta = apply_viewer_navigation(viewer, window, navigation)
        file_knob.setValue(pattern)
        context = nuke.OutputContext()
        context.setFrame(requested)
        try:
            context.setView(view)
        except Exception:
            pass
        produced = Path(file_knob.getEvaluatedValue(context))
        if produced.exists():
            produced.unlink()
        try:
            nuke.executeMultiple((viewer,), nuke.FrameRanges([str(requested)]), [view], False)
        except RuntimeError as exc:
            raise CaptureError(
                "Viewer render of frame %d failed or was cancelled: %s" % (requested, exc)
            ) from exc
        if not produced.exists():
            raise CaptureError(
                "Viewer render of frame %d finished but wrote no image at %s"
                % (requested, produced)
            )
        failures = _render_errors(
            viewer, [inputs["A"][0], inputs["B"][0]] if window is not None else None, window
        )
        if failures:
            produced.unlink()
            raise CaptureError(
                "Viewer render of frame %d completed with errors, so the image was "
                "discarded: %s" % (requested, "; ".join(failures))
            )
        produced.replace(final)
    finally:
        for restore in reversed(restorers):
            try:
                restore()
            except Exception as exc:
                restore_errors.append("%s: %s" % (type(exc).__name__, exc))
        file_knob.fromScript(old_file)
        # Restore the root frame only if the render itself left it at the
        # requested frame; a different value is a concurrent user change.
        if requested != nuke_frame and int(nuke.frame()) == requested:
            nuke.frame(nuke_frame)
        with scope_group:
            wanted = set(old_selected)
            for node in nuke.allNodes():
                node["selected"].setValue(node.fullName() in wanted)
        # Restore the modified flag only when the graph is provably unchanged;
        # otherwise a genuine edit made during the render keeps its flag.
        after_graph = graph_snapshot()
        if before_graph is not None and after_graph == before_graph:
            nuke.root().setModified(old_modified)

    if restore_errors:
        raise CaptureError(
            "The Viewer render finished but temporary state could not be restored: %s"
            % "; ".join(restore_errors)
        )
    width, height = _image_size(final)
    metadata = {
        "source": "viewer_render",
        "freshness": "verified_by_synchronous_render",
        "requested_frame": requested,
        "frame": requested,
        "nuke_frame_at_request": nuke_frame,
        "viewer": viewer.fullName(),
        "viewer_active_input": inputs["A"][0],
        "viewer_input_node": inputs["A"][1],
        "viewer_wipe_input": inputs["B"][0],
        "viewer_wipe_input_node": inputs["B"][1],
        "viewer_inputs_known": window is not None,
        "viewer_process": process,
        "view": view,
        "image_width": width,
        "image_height": height,
        "image_is_viewport_render": True,
    }
    metadata.update(navigation_meta)
    if navigation_meta:
        metadata["viewer_image_matches_viewport"] = (
            (width, height)
            == (navigation_meta["viewer_viewport_width"], navigation_meta["viewer_viewport_height"])
        )
    metadata.update(_project_format(nuke))
    return final, metadata


def _bounds(node):
    if node.Class() == "BackdropNode":
        width = float(node["bdwidth"].value())
        height = float(node["bdheight"].value())
    else:
        width = float(node.screenWidth())
        height = float(node.screenHeight())
    return node.xpos(), node.ypos(), node.xpos() + width, node.ypos() + height


def _contained(boxes, center, zoom, view_w, view_h) -> bool:
    half_w = view_w / (2.0 * zoom)
    half_h = view_h / (2.0 * zoom)
    return all(
        left >= center[0] - half_w
        and right <= center[0] + half_w
        and top >= center[1] - half_h
        and bottom <= center[1] + half_h
        for left, top, right, bottom in boxes
    )


# Raise-only guard for a GL window that never presents: the wait itself is event
# driven (frameSwapped), so this is never a settling delay and never falls back
# to grabbing whatever pixels are on screen.
_PRESENT_GUARD_MS = 30_000


def _gl_window(widget):
    """The QOpenGLWindow Nuke hosts inside a GL widget (DAG/Viewer), or None.

    Foundry::UI::GLWidget is a plain QWidget that embeds a QOpenGLWindow through
    QWidget.createWindowContainer, so the drawn pixels belong to a separate native
    window that QWidget.repaint()/grab() never reach. The window lying over the
    widget's screen rectangle is the one that displays it.
    """
    from PySide6 import QtCore, QtGui, QtOpenGL

    rect = QtCore.QRect(widget.mapToGlobal(QtCore.QPoint(0, 0)), widget.size())
    covering = []
    for window in QtGui.QGuiApplication.allWindows():
        if not isinstance(window, QtOpenGL.QOpenGLWindow):
            continue
        overlap = QtCore.QRect(window.mapToGlobal(QtCore.QPoint(0, 0)), window.size()).intersected(rect)
        area = max(0, overlap.width()) * max(0, overlap.height())
        if area * 2 >= _area(widget):
            covering.append((window.isVisible(), area, window))
    # A visible window beats a hidden one over the same rectangle (other tab pages).
    return max(covering, key=lambda item: item[:2])[2] if covering else None


def _present_frame(window) -> None:
    """Return only after ``window`` drew and swapped a frame requested now.

    The DAG repaints through its QOpenGLWindow's own event queue, so processEvents()
    can return while the screen still shows the previous view. Every view change
    must precede this call: the frame drawn after it reflects that state, and
    ``frameSwapped`` is emitted once the swap was handed to the display server.
    Raises CaptureError if the window is hidden/destroyed or never presents.
    """
    from PySide6 import QtCore

    loop = QtCore.QEventLoop()
    outcome = []

    def finish(reason):
        outcome.append(reason)
        loop.quit()

    def on_swapped():
        finish("swapped")

    def on_visible(visible):
        if not visible:
            finish("hidden")

    def on_destroyed(*_args):
        finish("destroyed")

    def on_silent():
        finish("silent")

    guard = QtCore.QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(on_silent)
    window.frameSwapped.connect(on_swapped)
    window.visibleChanged.connect(on_visible)
    window.destroyed.connect(on_destroyed)
    guard.start(_PRESENT_GUARD_MS)
    try:
        window.update()
        if not outcome:  # hidden/destroyed can be emitted synchronously
            loop.exec()
    finally:
        guard.stop()
        for name, slot in (
            ("frameSwapped", on_swapped),
            ("visibleChanged", on_visible),
            ("destroyed", on_destroyed),
        ):
            try:
                getattr(window, name).disconnect(slot)
            except (RuntimeError, TypeError):
                pass  # the window was destroyed while waiting
    reason = outcome[0] if outcome else "interrupted"
    if reason != "swapped":
        raise CaptureError(
            "The Node Graph (DAG) window did not present a frame (%s); the capture "
            "would show stale pixels." % reason
        )


def _flush_redraw(app):
    """Return the live DAG widget once its GL window presented the current view.

    View/selection changes can replace the native DAG widget, so callers must
    use the returned handle, never one kept across event processing. Fails if
    no real DAG is visible or presents rather than using a stale handle/pixels.
    """
    for _attempt in range(3):
        try:
            app.processEvents()
            widget = _find_widget(app, "nodegraph")
            if widget is None:
                raise CaptureError("The Node Graph (DAG) is not visible; cannot capture it.")
            window = _gl_window(widget)
            if window is None:
                raise CaptureError(
                    "The Node Graph (DAG) has no OpenGL window to wait on; its pixels "
                    "cannot be certified current."
                )
            _present_frame(window)
            current = _find_widget(app, "nodegraph")
            if current is None:
                raise CaptureError("The Node Graph (DAG) disappeared during capture.")
            if current is widget:
                return current
        except CaptureError:
            raise
        except RuntimeError as error:
            # Only a Qt wrapper whose C++ widget/window was destroyed by the view
            # change is stale; look the live DAG up again. Anything else is real.
            if "already deleted" not in str(error):
                raise
    raise CaptureError(
        "The Node Graph (DAG) widget kept being replaced or destroyed; no stable frame was presented."
    )


def _frame_graph(app, group):
    """Frame every node of ``group``; caller restores view/selection.

    Returns (metadata, entries): entries are (name, is_backdrop, bounds) for the
    saved image to be checked against. ``complete`` is decided from that image.
    """
    import nuke

    with group:
        nodes = list(nuke.allNodes())
        for node in nodes:
            node["selected"].setValue(True)
        if nodes:
            nuke.zoomToFitSelected()
            for node in nodes:
                node["selected"].setValue(False)
    entries = [(node.name(), node.Class() == "BackdropNode", _bounds(node)) for node in nodes]
    boxes = [entry[2] for entry in entries]
    widget = _flush_redraw(app)

    if nodes:
        for _attempt in range(8):
            zoom = nuke.zoom()
            if zoom and _contained(
                boxes, nuke.center(), zoom, widget.width(), widget.height()
            ):
                break
            nuke.zoom(zoom * 0.85, nuke.center())
            widget = _flush_redraw(app)
    names = [entry[0] for entry in entries]
    metadata = {
        "graph_group": _group_label(group),
        "group_is_root": _is_root(group),
        "included_nodes": names,
        "included_node_count": len(names),
        "graph_bounds": {
            "left": min(b[0] for b in boxes),
            "top": min(b[1] for b in boxes),
            "right": max(b[2] for b in boxes),
            "bottom": max(b[3] for b in boxes),
        }
        if boxes
        else None,
    }
    return metadata, entries


def _names(items, limit=5) -> str:
    shown = ", ".join(items[:limit])
    return shown + (", ..." if len(items) > limit else "")


def _dominant_rgb(image) -> int:
    """The graph background: the most common colour of a coarse pixel grid."""
    counts = {}
    step_x = max(1, image.width() // 64)
    step_y = max(1, image.height() // 64)
    for y in range(0, image.height(), step_y):
        for x in range(0, image.width(), step_x):
            rgb = image.pixel(x, y) & 0xFFFFFF
            counts[rgb] = counts.get(rgb, 0) + 1
    return max(counts, key=counts.get)


def _differs(rgb: int, background: int) -> bool:
    return (
        abs(((rgb >> 16) & 255) - ((background >> 16) & 255))
        + abs(((rgb >> 8) & 255) - ((background >> 8) & 255))
        + abs((rgb & 255) - (background & 255))
    ) > 24


def _certify_graph_image(path: Path, entries, view) -> dict:
    """Guard ``complete`` against the pixels actually saved, not logical state alone.

    Freshness comes from the frameSwapped barrier, not from this check. It only adds
    a missing-node/crop guard on the saved PNG: every node must lie inside it, and
    every node (Backdrops are translucent, so exempt) must show something other
    than the empty graph background where the framed view places it. It is a
    heuristic: wires or other nodes can occupy a sampled point, so passing it is
    not proof the frame is current.
    """
    from PySide6 import QtGui

    zoom, center, view_w, view_h = view
    image = QtGui.QImage(str(path))
    result = {
        "view": {
            "zoom": zoom,
            "center": list(center),
            "widget_size": [view_w, view_h],
            "image_size": [image.width(), image.height()],
        }
    }
    if image.isNull() or view_w <= 0 or view_h <= 0:
        return {**result, "complete": False, "incomplete_reason": "the saved image could not be read back"}
    scale_x = image.width() / float(view_w)
    scale_y = image.height() / float(view_h)
    if abs(scale_x - scale_y) > 0.02 * scale_x:
        return {
            **result,
            "complete": False,
            "incomplete_reason": "the saved image %dx%d does not match the Node Graph widget %dx%d (cropped capture)"
            % (image.width(), image.height(), view_w, view_h),
        }
    background = _dominant_rgb(image)
    clipped, blank = [], []
    for name, is_backdrop, (left, top, right, bottom) in entries:
        x0 = (view_w / 2.0 + (left - center[0]) * zoom) * scale_x
        y0 = (view_h / 2.0 + (top - center[1]) * zoom) * scale_y
        x1 = (view_w / 2.0 + (right - center[0]) * zoom) * scale_x
        y1 = (view_h / 2.0 + (bottom - center[1]) * zoom) * scale_y
        if x0 < -1 or y0 < -1 or x1 > image.width() + 1 or y1 > image.height() + 1:
            clipped.append(name)
            continue
        left_px, top_px = max(0, int(x0)), max(0, int(y0))
        right_px, bottom_px = min(image.width(), int(x1) + 1), min(image.height(), int(y1) + 1)
        if is_backdrop or right_px - left_px < 3 or bottom_px - top_px < 3:
            continue
        shown = any(
            _differs(
                image.pixel(
                    left_px + (right_px - left_px) * (2 * i + 1) // 18,
                    top_px + (bottom_px - top_px) * (2 * j + 1) // 18,
                )
                & 0xFFFFFF,
                background,
            )
            for i in range(9)
            for j in range(9)
        )
        if not shown:
            blank.append(name)
    problems = []
    if clipped:
        problems.append("%d node(s) extend beyond the saved image (%s)" % (len(clipped), _names(clipped)))
    if blank:
        problems.append(
            "%d node(s) are not drawn where the framed view places them (%s); the image is missing them"
            % (len(blank), _names(blank))
        )
    if problems:
        return {**result, "complete": False, "incomplete_reason": "; ".join(problems)}
    return {**result, "complete": True}


def _dag_widgets(app) -> list:
    return [
        widget
        for widget in app.allWidgets()
        if _safe_call(widget, "objectName").lower().startswith("dag.")
    ]


def _tab_owner(widget):
    """(owner, page) for the nearest tab/stack that switches ``widget``'s page."""
    from PySide6 import QtWidgets

    child = widget
    while child is not None:
        parent = child.parentWidget()
        if isinstance(parent, QtWidgets.QStackedWidget):
            grand = parent.parentWidget()
            owner = grand if isinstance(grand, QtWidgets.QTabWidget) else parent
            if owner.indexOf(child) < 0:
                return None, None  # removed/orphaned page still alive in Qt; not a real tab
            return owner, child
        child = parent
    return None, None


def _tab_states(app) -> dict:
    states = {}
    for dag in _dag_widgets(app):
        owner, _page = _tab_owner(dag)
        if owner is not None:
            states[owner] = owner.currentWidget()
    return states


def _restore_tabs(states: dict) -> None:
    for owner, current in states.items():
        try:
            if current is not None and owner.currentWidget() is not current:
                owner.setCurrentWidget(current)
        except RuntimeError:
            pass  # the pane was destroyed during the capture; nothing to restore


def _activate_hidden_dag(app, tabs: dict) -> None:
    """Bring hidden Node Graph pages to the front so the DAG can be captured.

    The previously current page of every switched owner is recorded in ``tabs``
    (without overwriting an earlier record) so the caller can restore it.
    """
    for dag in _dag_widgets(app):
        if dag.isVisible():
            continue
        owner, page = _tab_owner(dag)
        if owner is not None and owner.currentWidget() is not page:
            tabs.setdefault(owner, owner.currentWidget())
            owner.setCurrentWidget(page)


def _restore_view(zoom, center) -> None:
    """Set the DAG zoom/center, correcting Nuke's center quantisation drift.

    nuke.zoom(scale, center) can land up to a unit off the requested center;
    re-aiming by the observed error converges (bounded) instead of leaving
    each capture to shift the user's view.
    """
    import nuke

    target = list(center)
    nuke.zoom(zoom, target)
    for _attempt in range(3):
        got = list(nuke.center())
        if got == list(center):
            break
        target = [target[0] + (center[0] - got[0]), target[1] + (center[1] - got[1])]
        nuke.zoom(zoom, target)


def _capture_widget(target: str, scope: str, directory: Path) -> tuple[Path, dict]:
    import nuke
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        raise CaptureError("No QApplication is running")

    widget = None
    if not (target == "nodegraph" and scope == "all"):
        widget = _find_widget(app, target)
        if widget is None:
            diagnostics = "; ".join(describe_candidates(target, limit=5))
            suffix = (" Candidates: " + diagnostics) if diagnostics else ""
            raise CaptureError("Could not find a visible %s widget.%s" % (target, suffix))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = directory / ("%s-%s.png" % (target, stamp))
    metadata = {
        "source": "ui_screenshot",
        "freshness": "ui_screenshot_not_frame_certified",
        "nuke_frame_at_request": int(nuke.frame()),
    }
    if target == "interface":
        # The interface may contain a Viewer; its pixels are NOT certified
        # current for any frame. Use target=viewer for frame evidence.
        metadata["viewer_pixels_certified"] = False
        metadata["viewer_render_completed"] = False
        if nuke.activeViewer() is not None:
            # Render-completion barrier: wait (no timeout) for the active
            # Viewer to finish rendering the current frame, then discard the
            # barrier image. Failure/cancel propagates; it never falls through.
            barrier, barrier_meta = _capture_viewer(None, directory)
            barrier.unlink()
            metadata["viewer_render_completed"] = True
            metadata["viewer_render_frame"] = barrier_meta["frame"]
            metadata["viewer"] = barrier_meta["viewer"]
            app.processEvents()

    if target == "nodegraph":
        original_group = nuke.activeGroup()
        group = original_group
        tabs = _tab_states(app)
        all_nodes = []
        old_selected = set()
        old_zoom = old_center = None
        original_zoom = nuke.zoom()
        original_center = nuke.center()
        try:
            if scope == "all":
                # scope=all is the ROOT graph. Always activate it through the
                # supported showDag workflow (even if root is already the active
                # group, its DAG tab may be hidden behind another panel), then
                # rediscover the DAG widget that actually displays it.
                if _find_widget(app, target) is None:
                    _activate_hidden_dag(app, tabs)
                    app.processEvents()
                nuke.showDag(nuke.root())
                app.processEvents()
                group = nuke.activeGroup()
                if not _is_root(group):
                    raise CaptureError(
                        "Could not show the root node graph (active group is still %s)"
                        % _group_label(group)
                    )
                widget = _find_widget(app, target)
                if widget is None:
                    # showDag may have (re)created the DAG on another page.
                    _activate_hidden_dag(app, tabs)
                    app.processEvents()
                    widget = _find_widget(app, target)
                if widget is None:
                    raise CaptureError(
                        "No Node Graph (DAG) widget is visible after showing the root graph; "
                        "the screenshot would not contain the graph."
                    )
            with group:
                all_nodes = list(nuke.allNodes())
                old_selected = {n.fullName() for n in nuke.selectedNodes()}
            old_zoom = nuke.zoom()
            old_center = nuke.center()
            metadata["scope"] = scope
            metadata["active_group_at_request"] = _group_label(original_group)
            entries = []
            if scope == "all":
                graph_metadata, entries = _frame_graph(app, group)
                metadata.update(graph_metadata)
            else:
                metadata.update(
                    {
                        "graph_group": _group_label(group),
                        "group_is_root": _is_root(group),
                        "included_nodes": None,
                        "included_node_count": None,
                        "complete": False,
                        "incomplete_reason": "scope=visible captures only the current viewport",
                    }
                )
            metadata["group_node_count"] = len(all_nodes)
            widget = _flush_redraw(app)  # fresh handle: view ops may replace the DAG widget
            metadata["presentation_barrier"] = "QOpenGLWindow.frameSwapped"
            view = (nuke.zoom(), list(nuke.center()), widget.width(), widget.height())
            saved = _save_widget(widget, target, path)
            if saved and scope == "all":
                metadata.update(_certify_graph_image(path, entries, view))
        finally:
            with group:
                for node in all_nodes:
                    node["selected"].setValue(node.fullName() in old_selected)
            if old_zoom:
                _restore_view(old_zoom, old_center)  # the captured group's own prior view
            if _group_label(group) != _group_label(original_group):
                nuke.showDag(original_group)
            if original_zoom:
                # Original view taken before any showDag/tab activation changed it.
                _restore_view(original_zoom, original_center)
            _restore_tabs(tabs)
            app.processEvents()
    else:
        saved = _save_widget(widget, target, path)

    if not saved:
        from PySide6 import QtGui

        raise CaptureError(
            "All capture backends returned blank or unavailable pixels for %s "
            "(Qt platform %s); no image was written to %s"
            % (target, QtGui.QGuiApplication.platformName(), path)
        )
    metadata["image_width"], metadata["image_height"] = _image_size(path)
    return path, metadata


def capture_target(
    target: str,
    output_dir: str | Path | None = None,
    *,
    frame: int | None = None,
    scope: str = "all",
    zoom=None,
    center=None,
    region=None,
) -> Path:
    """Capture the Viewer (synchronous render), Node Graph, or main interface to PNG.

    ``frame``, ``zoom``, ``center`` and ``region`` (Viewer framing, see
    :func:`normalize_viewer_navigation`) apply to ``viewer`` only; ``scope`` ('all' or
    'visible') to ``nodegraph`` only. Metadata is available via :func:`capture_metadata`.
    """
    if target not in _TARGETS:
        raise ValueError("target must be viewer, nodegraph, or interface")
    if scope not in ("all", "visible"):
        raise ValueError("scope must be all or visible")
    navigation = normalize_viewer_navigation(zoom, center, region)
    if navigation is not None and target != "viewer":
        raise ValueError("zoom, center and region are only valid with target='viewer'")

    directory = _capture_directory(output_dir)
    if target == "viewer":
        path, metadata = _capture_viewer(frame, directory, navigation)
        backend = "Viewer synchronous render (nuke.executeMultiple)"
    else:
        path, metadata = _capture_widget(target, scope, directory)
        backend = _CAPTURE_BACKENDS.get(str(path.resolve()), "unknown backend")
    metadata["target"] = target
    metadata["backend"] = backend
    metadata["captured_at"] = _now()
    metadata["path"] = str(path.resolve())
    key = str(path.resolve())
    _CAPTURE_BACKENDS[key] = backend
    _CAPTURE_METADATA[key] = metadata
    return path.resolve()
