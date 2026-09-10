"""Model selection must survive harnesses that re-announce their model list."""

import tempfile
from pathlib import Path

from PySide6 import QtCore, QtWidgets

import nuke_codex_panel.chat_store as chat_store
import nuke_codex_panel.harnesses as harnesses
from nuke_codex_panel.harnesses import create_harness
from nuke_codex_panel.harnesses.base import HarnessClient


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

MODELS = [
    {"id": "prov/alpha", "label": "Alpha", "efforts": ["low"]},
    {"id": "prov/beta", "label": "Beta", "efforts": ["low"]},
]


def test_pi_rpc_emits_models_once_for_identical_payloads():
    """set_model re-queries the list; an unchanged list must not re-emit."""
    client = create_harness("pi", "/tmp")
    emitted = []
    client.models_changed.connect(emitted.append)
    payload = {
        "data": {"models": [{"provider": "prov", "id": "alpha", "name": "Alpha"}]}
    }
    client._models_loaded(payload)
    client._models_loaded(payload)
    client._models_loaded(payload)
    assert len(emitted) == 1, emitted

    changed = {
        "data": {"models": [{"provider": "prov", "id": "alpha", "name": "Alpha renamed"}]}
    }
    client._models_loaded(changed)
    assert len(emitted) == 2


class LoopyClient(HarnessClient):
    """Re-announces its models whenever set_model is called (pi's behaviour)."""

    name = "loopy"
    label = "Loopy"
    binary_label = "Loopy"
    env_var = "NUKE_LOOPY_BIN"

    def __init__(self, cwd, parent=None, bridge_path=None):
        super().__init__(cwd, parent, bridge_path)
        self.set_model_calls = []

    def start(self):
        self._set_ready(True)
        QtCore.QTimer.singleShot(0, lambda: self.models_changed.emit(MODELS))

    def stop(self, restart: bool = False):
        self._set_ready(False)

    def send_turn(self, text, image_paths=None):
        return True

    def set_model(self, model_id):
        self.set_model_calls.append(model_id)
        self.models_changed.emit(MODELS)  # closing the loop, as pi does


def test_model_selection_is_stable_and_not_reapplied_forever(monkeypatch, tmp_path):
    import nuke_codex_panel.ui.panel_widget as panel_widget

    class FakeSettings:
        store = {"harness": "loopy"}

        def __init__(self, *args):
            pass

        def value(self, key, default=None):
            return self.store.get(key, default)

        def setValue(self, key, value):
            self.store[key] = value

        def sync(self):
            pass

    class FakeBridge(QtCore.QObject):
        status_changed = QtCore.Signal(str)

        def __init__(self, approve, parent=None):
            super().__init__(parent)
            self.discovery_path = tmp_path / "bridge.json"

        def start(self):
            return True

        def stop(self):
            pass

    monkeypatch.setattr(panel_widget.QtCore, "QSettings", FakeSettings)
    monkeypatch.setattr(panel_widget, "NukeBridgeServer", FakeBridge)
    chat_store.chats_root = lambda: tmp_path / "chats"
    harnesses.HARNESSES[:] = [
        entry for entry in harnesses.HARNESSES if entry["key"] != "loopy"
    ]
    harnesses.HARNESSES.append(
        {"key": "loopy", "label": "Loopy", "factory": LoopyClient}
    )

    panel = panel_widget.CodexPanelWidget()
    for _ in range(20):
        app.processEvents()
    # Models are grouped under a bold provider row; both models reachable.
    assert panel._find_model_index("prov/alpha").isValid()
    assert panel._find_model_index("prov/beta").isValid()
    assert panel.client.set_model_calls == ["prov/alpha"], panel.client.set_model_calls

    # The user picks the second model...
    beta = panel._find_model_index("prov/beta")
    panel.model_combo.setRootModelIndex(beta.parent())
    panel.model_combo.setCurrentIndex(beta.row())
    panel.model_combo.setRootModelIndex(QtCore.QModelIndex())
    panel._on_model_picked(beta.row())
    for _ in range(20):
        app.processEvents()

    # ...and it must stick, with the list not re-announced endlessly.
    assert panel.model_combo.currentData()["id"] == "prov/beta"
    assert panel.client.set_model_calls == ["prov/alpha", "prov/beta"], (
        panel.client.set_model_calls
    )
    assert FakeSettings.store["model/loopy"] == "prov/beta"
    panel.close()
