from nuke_codex_panel import __version__
from nuke_codex_panel.panel import PANEL_ID, PANEL_TITLE, WIDGET_PATH


def test_package_metadata_and_panel_identity():
    assert __version__ == "0.1.0.dev0"
    assert PANEL_TITLE == "Codex"
    assert PANEL_ID == "com.nukecodex.panel"
    assert WIDGET_PATH.endswith("CodexPanelWidget")


def test_widget_expression_is_self_contained():
    """Nuke evaluates this source later inside a PyCustom_Knob context."""
    assert "__import__(" in WIDGET_PATH
    assert "fromlist=['CodexPanelWidget']" in WIDGET_PATH
