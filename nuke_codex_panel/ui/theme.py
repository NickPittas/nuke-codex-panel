"""Plug-in scoped theme: a dark, colourful style for this plug-in's own widgets only.

``apply_theme(widget)`` sets a palette and a style sheet on that one widget (and thereby its
children and the dialogs/menus/popups it parents). It never touches ``QApplication`` — no global
style, palette, font or style sheet — so the rest of Nuke is left exactly as it was.

Top-level windows (dialogs, message boxes, popups) do not inherit a palette from their parent, so
every plug-in dialog calls ``apply_theme(self)`` itself.

Selectors available to plug-in widgets:

* ``QPushButton[variant="primary"|"danger"|"ghost"]`` / ``QToolButton[variant="ghost"|"accent"]``
* ``QLabel[status="ok"|"warn"|"error"|"muted"|"accent"]`` (use ``set_variant`` to change at runtime)
* ``QLabel#heading``, ``QLabel#usageLabel``, ``QLabel#activityLabel``, ``QLabel#roleLabel``
* ``QFrame#card`` (rounded raised surface)
"""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets

PALETTE = {
    "bg": "#171a21",
    "surface": "#1f232c",
    "surface_alt": "#272c37",
    "surface_hover": "#303644",
    "border": "#363d4c",
    "border_strong": "#4a5368",
    "text": "#e8ebf2",
    "muted": "#98a2b5",
    "accent": "#4da3ff",
    "accent_hover": "#6bb4ff",
    "accent_pressed": "#2f86e0",
    "accent_text": "#08121f",
    "teal": "#2dd4bf",
    "ok": "#34d399",
    "warn": "#fbbf24",
    "error": "#f87171",
    "error_pressed": "#dc4c4c",
    "disabled_bg": "#20242d",
    "disabled_text": "#6a7385",
    "selection": "#2b5a94",
}

RADIUS = 6

# Chat text size in points (QSettings ``chat/font_size``); ChatView clamps to the same bounds.
FONT_DEFAULT = 11
FONT_MIN = 8
FONT_MAX = 24
_MARKER = "/* nuke-codex-panel theme */"


def _stylesheet() -> str:
    p = PALETTE
    return (
        _MARKER
        + """
QWidget { color: %(text)s; selection-background-color: %(selection)s; selection-color: %(text)s; }
QDialog, QMessageBox, QWidget#NukeCodexPanel { background: %(bg)s; }
QLabel { background: transparent; }
QLabel#heading { font-weight: 700; color: %(accent)s; }
QLabel#usageLabel { color: %(muted)s; }
QLabel#activityLabel { color: %(teal)s; background: %(surface)s; border: 1px solid %(border)s;
    border-radius: %(r)dpx; padding: 4px 8px; }
QLabel[status="ok"] { color: %(ok)s; }
QLabel[status="warn"] { color: %(warn)s; }
QLabel[status="error"] { color: %(error)s; }
QLabel[status="muted"] { color: %(muted)s; }
QLabel[status="accent"] { color: %(accent)s; }
QToolTip { background: %(surface_alt)s; color: %(text)s; border: 1px solid %(border_strong)s; padding: 4px 6px; }

QFrame#card { background: %(surface)s; border: 1px solid %(border)s; border-radius: %(r)dpx; }
QGroupBox { background: %(surface)s; border: 1px solid %(border)s; border-radius: %(r)dpx;
    margin-top: 14px; padding: 10px 8px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 6px;
    color: %(teal)s; font-weight: 600; }

QPushButton, QToolButton { background: %(surface_alt)s; color: %(text)s; border: 1px solid %(border)s;
    border-radius: %(r)dpx; padding: 5px 12px; }
QToolButton { padding: 4px 9px; }
QPushButton:hover, QToolButton:hover { background: %(surface_hover)s; border-color: %(accent)s; }
QPushButton:pressed, QToolButton:pressed { background: %(border)s; }
QPushButton:focus, QToolButton:focus { border-color: %(accent)s; }
QPushButton:disabled, QToolButton:disabled { background: %(disabled_bg)s; color: %(disabled_text)s;
    border-color: %(border)s; }
QPushButton[variant="primary"], QPushButton:default { background: %(accent)s; color: %(accent_text)s;
    border: 1px solid %(accent)s; font-weight: 600; }
QPushButton[variant="primary"]:hover, QPushButton:default:hover { background: %(accent_hover)s;
    border-color: %(accent_hover)s; }
QPushButton[variant="primary"]:pressed, QPushButton:default:pressed { background: %(accent_pressed)s; }
QPushButton[variant="primary"]:disabled { background: %(disabled_bg)s; color: %(disabled_text)s;
    border-color: %(border)s; }
QPushButton[variant="danger"] { background: transparent; color: %(error)s; border: 1px solid %(error)s; }
QPushButton[variant="danger"]:hover { background: %(error)s; color: %(accent_text)s; }
QPushButton[variant="danger"]:pressed { background: %(error_pressed)s; color: %(accent_text)s; }
QPushButton[variant="danger"]:disabled { background: %(disabled_bg)s; color: %(disabled_text)s;
    border-color: %(border)s; }
QPushButton[variant="ghost"], QToolButton[variant="ghost"] { background: transparent; border-color: transparent; }
QPushButton[variant="ghost"]:hover, QToolButton[variant="ghost"]:hover { background: %(surface_hover)s;
    border-color: %(border)s; }
QToolButton[variant="accent"] { background: transparent; color: %(accent)s; border: 1px solid %(accent)s; }
QToolButton[variant="accent"]:hover { background: %(accent)s; color: %(accent_text)s; }

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox { background: %(surface)s; color: %(text)s;
    border: 1px solid %(border)s; border-radius: %(r)dpx; padding: 4px 6px; }
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus { border-color: %(accent)s; }
QLineEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
    background: %(disabled_bg)s; color: %(disabled_text)s; }

QComboBox { background: %(surface_alt)s; color: %(text)s; border: 1px solid %(border)s;
    border-radius: %(r)dpx; padding: 4px 8px; }
QComboBox:hover { border-color: %(accent)s; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: %(surface)s; color: %(text)s; border: 1px solid %(border_strong)s;
    selection-background-color: %(selection)s; selection-color: %(text)s; outline: 0; }

QCheckBox, QRadioButton { spacing: 7px; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator { width: 14px; height: 14px; background: %(surface)s;
    border: 1px solid %(border_strong)s; }
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: %(accent)s; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked { background: %(accent)s; border-color: %(accent)s; }
QCheckBox::indicator:indeterminate { background: %(teal)s; border-color: %(teal)s; }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { background: %(disabled_bg)s;
    border-color: %(border)s; }

QProgressBar { background: %(surface_alt)s; border: none; border-radius: 3px; }
QProgressBar::chunk { background: %(teal)s; border-radius: 3px; }

QListView, QListWidget, QTreeView, QTreeWidget, QTableView, QScrollArea { background: %(surface)s;
    color: %(text)s; border: 1px solid %(border)s; border-radius: %(r)dpx; alternate-background-color: %(surface_alt)s;
    outline: 0; }
QListView::item, QTreeView::item { padding: 3px 4px; }
QListView::item:hover, QTreeView::item:hover { background: %(surface_hover)s; }
QListView::item:selected, QTreeView::item:selected { background: %(selection)s; color: %(text)s; }
QHeaderView::section { background: %(surface_alt)s; color: %(muted)s; border: none; padding: 4px 6px; }

QScrollBar:vertical { background: transparent; width: 11px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 11px; margin: 0; }
QScrollBar::handle:vertical { background: %(border_strong)s; border-radius: 5px; min-height: 28px; margin: 1px; }
QScrollBar::handle:horizontal { background: %(border_strong)s; border-radius: 5px; min-width: 28px; margin: 1px; }
QScrollBar::handle:hover { background: %(accent)s; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QSplitter::handle { background: %(border)s; }
QSplitter::handle:vertical { height: 3px; }
QSplitter::handle:horizontal { width: 3px; }
QSplitter::handle:hover { background: %(accent)s; }

QMenu { background: %(surface)s; color: %(text)s; border: 1px solid %(border_strong)s; padding: 4px; }
QMenu::item { padding: 5px 22px; border-radius: 4px; }
QMenu::item:selected { background: %(selection)s; }
QMenu::item:disabled { color: %(disabled_text)s; }
QMenu::separator { height: 1px; background: %(border)s; margin: 4px 6px; }

QDialogButtonBox QPushButton { min-width: 72px; }
"""
        % {**p, "r": RADIUS}
    )


def _palette() -> QtGui.QPalette:
    p = PALETTE
    palette = QtGui.QPalette()
    role = QtGui.QPalette.ColorRole
    group = QtGui.QPalette.ColorGroup
    for r, key in (
        (role.Window, "bg"),
        (role.WindowText, "text"),
        (role.Base, "surface"),
        (role.AlternateBase, "surface_alt"),
        (role.Text, "text"),
        (role.Button, "surface_alt"),
        (role.ButtonText, "text"),
        (role.ToolTipBase, "surface_alt"),
        (role.ToolTipText, "text"),
        (role.Highlight, "selection"),
        (role.HighlightedText, "text"),
        (role.Link, "accent"),
        (role.LinkVisited, "teal"),
        (role.PlaceholderText, "muted"),
    ):
        palette.setColor(r, QtGui.QColor(p[key]))
    for r in (role.WindowText, role.Text, role.ButtonText):
        palette.setColor(group.Disabled, r, QtGui.QColor(p["disabled_text"]))
    return palette


_STYLE_MARKER = "_nukeCodexPanelStyled"
_plugin_style: QtWidgets.QStyle | None = None


def _scoped_style() -> QtWidgets.QStyle | None:
    """One Fusion style object shared by plug-in widgets only; kept alive here (widgets do not own styles)."""
    global _plugin_style
    if _plugin_style is None:
        _plugin_style = QtWidgets.QStyleFactory.create("Fusion")
    return _plugin_style


def enlarged_font(font: QtGui.QFont, points: int) -> QtGui.QFont:
    """``font`` grown by ``points``; keeps pixel-sized fonts (``pointSize() == -1``) valid."""
    result = QtGui.QFont(font)
    size = result.pointSizeF()
    if size > 0:
        result.setPointSizeF(size + points)
    elif result.pixelSize() > 0:
        result.setPixelSize(result.pixelSize() + round(points * 4 / 3))
    return result


def apply_theme(widget: QtWidgets.QWidget) -> None:
    """Theme ``widget`` and everything it parents; leaves QApplication and the rest of Nuke alone.

    Idempotent. Rules already set on the widget are kept and win ties with the theme, so a widget
    may set its own style sheet before or after this call. The widget and its existing descendants
    also get a private Fusion base style (Qt does not propagate ``setStyle`` to existing children),
    so Nuke's own application style does not paint over the style sheet; widgets created later
    under a themed parent inherit it.
    """
    existing = widget.styleSheet()
    if _MARKER not in existing:
        widget.setStyleSheet(_stylesheet() + "\n" + existing)
    widget.setPalette(_palette())
    style = _scoped_style()
    if style is None:
        return
    for target in (widget, *widget.findChildren(QtWidgets.QWidget)):
        if not target.property(_STYLE_MARKER):
            target.setStyle(style)
            target.setProperty(_STYLE_MARKER, True)


def set_variant(widget: QtWidgets.QWidget, name: str, value: str) -> None:
    """Change a styling property (``variant`` / ``status``) and re-polish the widget."""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
