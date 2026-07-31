"""Nuke panel registration."""

PANEL_ID = "com.nukecodex.panel"
PANEL_TITLE = "Codex"
WIDGET_PATH = (
    "__import__('nuke_codex_panel.ui.panel_widget', "
    "fromlist=['CodexPanelWidget']).CodexPanelWidget"
)

_registered = False


def register_panel():
    """Register the dockable widget once for the current Nuke process."""
    global _registered
    if _registered:
        return None

    from nukescripts import panels

    result = panels.registerWidgetAsPanel(WIDGET_PATH, PANEL_TITLE, PANEL_ID)
    _registered = True
    return result
