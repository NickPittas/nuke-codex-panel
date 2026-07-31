"""Run with ``Nuke17.0 -t tests/nuke_smoke.py`` to verify host discovery."""

import nuke

import nuke_codex_panel
import nuke_codex_panel.menu
from nuke_codex_panel.panel import PANEL_ID, PANEL_TITLE, WIDGET_PATH


assert nuke.NUKE_VERSION_MAJOR >= 17
assert PANEL_TITLE == "Codex"
assert PANEL_ID == "com.nukecodex.panel"
assert eval(WIDGET_PATH).__name__ == "CodexPanelWidget"
print("NUKE_CODEX_SMOKE_OK", nuke.NUKE_VERSION_STRING, nuke_codex_panel.__version__)
