"""Panel-level persistence: save, restore, archive, and the context widget.

Runs with isolated settings, app data, and chat storage: this smoke must never
write into the user's real config or history.
"""

import os
import tempfile
from pathlib import Path

_isolated = Path(tempfile.mkdtemp(prefix="nuke-panel-isolation-"))
os.environ["XDG_CONFIG_HOME"] = str(_isolated / "config")
os.environ["XDG_DATA_HOME"] = str(_isolated / "data")

from PySide6 import QtCore, QtWidgets

import nuke_codex_panel.chat_store as chat_store
import nuke_codex_panel.harnesses as harnesses
from nuke_codex_panel.chat_store import ChatStore
from nuke_codex_panel.harnesses.base import HarnessClient


app = QtWidgets.QApplication.instance()
assert app is not None

tmp = Path(tempfile.mkdtemp(prefix="nuke-panel-smoke-"))
chat_store.chats_root = lambda: tmp / "chats"
# Guard: the panel must be reading the isolated settings file.
assert str(QtCore.QSettings("nuke-codex-panel", "panel").fileName()).startswith(
    str(_isolated)
), QtCore.QSettings("nuke-codex-panel", "panel").fileName()

# Use a harness that resolves to nothing so no subprocess is spawned.
class FakeClient(HarnessClient):
    name = "codex"
    label = "Fake"
    binary_label = "Fake"
    env_var = "NUKE_FAKE_BIN"

    def __init__(self, cwd, parent=None, bridge_path=None):
        super().__init__(cwd, parent, bridge_path)
        self.sent = []

    def resolve_program(self):
        return None

    def start(self):
        self._set_ready(True)

    def stop(self, restart: bool = False):
        self._set_ready(False)

    def send_turn(self, text, image_paths=None):
        self.sent.append(text)
        self.user_message.emit(text, list(image_paths or []))
        return True


harnesses.HARNESSES.append({"key": "fake", "label": "Fake", "factory": FakeClient})

import nuke_codex_panel.ui.panel_widget as panel_widget  # noqa: E402


class FakeBridge(QtCore.QObject):
    """Stand-in for the Nuke bridge, which needs the real `nuke` module."""

    status_changed = QtCore.Signal(str)

    def __init__(self, approve, parent=None):
        super().__init__(parent)
        self.discovery_path = tmp / "bridge-session.json"

    def start(self):
        return True

    def stop(self):
        pass


panel_widget.NukeBridgeServer = FakeBridge
from nuke_codex_panel.ui.panel_widget import CodexPanelWidget  # noqa: E402

panel = CodexPanelWidget()
panel._switch_harness("fake")
assert panel.project_path
for _ in range(3):
    app.processEvents()

# A turn is recorded, then persisted.
panel.chat.add_user_message("remember ZEBRA42", [])
panel.chat.start_assistant("Fake")
panel.chat.append_thinking("pondering zebra")
panel.chat.append_delta("OK")
panel.chat.finish_assistant()
panel.client.usage_changed.emit({"used": 60000, "window": 200000, "percent": 30.0,
                                 "input": 50000, "cached": 9000, "output": 12, "cost": 0.25})
panel._save_chat()
saved = ChatStore(panel.project_path, "fake").load()
assert len(saved["messages"]) == 2, saved
assert "ZEBRA42" in saved["messages"][0]["text"]

assert "60.0k" in panel.usage_label.text() and "200.0k" in panel.usage_label.text()
assert panel.usage_bar.value() == 30
assert "cost $0.2500" in panel.usage_label.toolTip()
assert "cached 9.0k" in panel.usage_label.toolTip()

# Restoring: a fresh panel for the same project replays the transcript.
restored = CodexPanelWidget()
for _ in range(3):
    app.processEvents()
restored_text = "\n".join(
    widget.toPlainText()
    for widget in restored.chat.container.findChildren(QtWidgets.QTextBrowser)
)
assert "ZEBRA42" in restored_text and "pondering zebra" in restored_text, restored_text

# New chat archives the old transcript and wipes the pane.
archived_before = sorted((tmp / "chats").rglob("archive/*.json"))
panel._new_chat()
for _ in range(2):
    app.processEvents()
archived_after = sorted((tmp / "chats").rglob("archive/*.json"))
assert len(archived_after) == len(archived_before) + 1, (archived_before, archived_after)
assert panel.chat.records() == []
assert ChatStore(panel.project_path, "fake").load()["messages"] == []
assert "archived" in panel.status.text().lower()
assert panel.usage_label.text() == "context: —"

panel.close()
restored.close()

# Regression: a stale/hand-edited harness setting must not brick the panel.
settings = QtCore.QSettings("nuke-codex-panel", "panel")
settings.setValue("harness", "definitely-not-a-harness")
settings.sync()
survivor = CodexPanelWidget()
for _ in range(2):
    app.processEvents()
assert settings.value("harness") in harnesses.harness_names(), settings.value("harness")
assert survivor.client is not None and survivor.client.name == "codex"
survivor.close()

print("NUKE_CODEX_PANEL_SMOKE_OK", len(saved["messages"]), "messages persisted")
