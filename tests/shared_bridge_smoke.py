"""Real-Nuke smoke: the shared bridge outlives panes and serves external MCP stdio clients.

Panels run with an inert harness and an isolated settings/chat-history root, so
no model agent or adapter installer starts and nothing is written to the user's
config or chat history. The bridge, the stdio MCP server and the Nuke script
mutations/denials are real.

Run (no model turns are sent)::

    PYTHONPATH=<project root> Nuke --safe --tg tests/shared_bridge_smoke.py
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import uuid

_isolated = Path(tempfile.mkdtemp(prefix="nuke-shared-bridge-isolation-"))
os.environ["XDG_CONFIG_HOME"] = str(_isolated / "config")
os.environ["XDG_DATA_HOME"] = str(_isolated / "data")

import nuke
from PySide6 import QtCore, QtWidgets

# Qt may already have resolved the user settings root inside Nuke; redirect it
# before any panel opens its QSettings.
QtCore.QSettings.setPath(
    QtCore.QSettings.Format.NativeFormat, QtCore.QSettings.Scope.UserScope, str(_isolated / "config")
)
QtCore.QSettings.setPath(
    QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, str(_isolated / "config")
)

import nuke_codex_panel.chat_store as chat_store
import nuke_codex_panel.harnesses as harnesses
from nuke_codex_panel.bridge import ensure_bridge
from nuke_codex_panel.harnesses import nuke_mcp
from nuke_codex_panel.harnesses.base import HarnessClient


class InertClient(HarnessClient):
    """Harness that never resolves a binary or starts a process."""

    name = "inert"
    label = "Inert"
    binary_label = "Inert"
    env_var = "NUKE_INERT_BIN"

    def resolve_program(self):
        return None

    def start(self):
        self._set_ready(True)

    def stop(self, restart: bool = False):
        self._set_ready(False)

    def send_turn(self, text, image_paths=None):
        raise AssertionError("smoke must not send model turns")


_real_chats_root = chat_store.chats_root
_real_harnesses = list(harnesses.HARNESSES)
chat_store.chats_root = lambda: _isolated / "chats"
harnesses.HARNESSES[:] = [{"key": "inert", "label": "Inert", "factory": InertClient}]

_settings = QtCore.QSettings("nuke-codex-panel", "panel")
assert str(_settings.fileName()).startswith(str(_isolated)), _settings.fileName()
_settings.setValue("harness", "inert")
_settings.sync()

from nuke_codex_panel.ui.panel_widget import CodexPanelWidget  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 30_000
SUFFIX = "%d_%s" % (os.getpid(), uuid.uuid4().hex[:6])
NAMES = {
    key: "SharedBridgeSmoke_%s_%s" % (key, SUFFIX)
    for key in ("trusted", "denied_hidden", "denied_closed", "denied_new")
}
TOOL_CODE = "node = nuke.nodes.NoOp(name=%r)\nnode.fullName()"

app = QtWidgets.QApplication.instance()
assert app is not None, "needs Nuke's QApplication"
app.setQuitOnLastWindowClosed(False)

dialogs_seen = 0


def press_no():
    """Safely deny any confirmation dialog, counting how many appeared."""
    global dialogs_seen
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, QtWidgets.QMessageBox) and widget.isVisible():
            button = widget.button(QtWidgets.QMessageBox.StandardButton.No)
            if button is not None:
                dialogs_seen += 1
                button.click()


presser = QtCore.QTimer()
presser.setInterval(25)
presser.timeout.connect(press_no)
presser.start()


def run_blocking(fn):
    """Run a blocking call in a thread while Nuke's Qt loop keeps serving the bridge."""
    outcome = {}

    def target():
        try:
            outcome["value"] = fn()
        except Exception as exc:
            outcome["error"] = repr(exc)

    loop = QtCore.QEventLoop()
    thread = threading.Thread(target=target, daemon=True)
    thread.start()

    def poll():
        if thread.is_alive():
            QtCore.QTimer.singleShot(20, poll)
        else:
            loop.quit()

    QtCore.QTimer.singleShot(0, poll)
    QtCore.QTimer.singleShot(TIMEOUT, loop.quit)
    loop.exec()
    assert not thread.is_alive(), "call timed out"
    assert "error" not in outcome, outcome
    return outcome["value"]


class StdioMcpClient:
    """Minimal MCP client over a real stdio subprocess pinned to one bridge file."""

    def __init__(self, bridge_path):
        env = dict(os.environ)
        env.update(nuke_mcp.server_environment(str(bridge_path)))
        env.pop("PYTHONHOME", None)
        self.process = subprocess.Popen(
            nuke_mcp.server_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            cwd=str(PROJECT_ROOT),
        )
        self._next_id = 0

    def request(self, method, params=None):
        self._next_id += 1
        message = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params or {}}
        self.process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        assert line, "MCP server exited"
        reply = json.loads(line.decode("utf-8"))
        assert reply["id"] == self._next_id and "error" not in reply, reply
        return reply["result"]

    def tool(self, name, arguments):
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        return json.loads(result["content"][0]["text"])

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
        for stream in (self.process.stdin, self.process.stdout):
            try:
                stream.close()
            except Exception:
                pass
        self.process.wait(timeout=5)


def call(client, name, arguments):
    return run_blocking(lambda: client.tool(name, arguments))


def execute(client, node_name):
    return call(client, "execute_python", {"code": TOOL_CODE % node_name, "undo": True, "label": "Shared bridge smoke"})


def context_ok(client):
    reply = call(client, "get_nuke_context", {"include_nodes": False})
    assert reply["success"], reply
    assert reply["context"]["nuke_version"] == nuke.NUKE_VERSION_STRING, reply


def open_pane():
    pane = CodexPanelWidget()
    pane.show()
    app.processEvents()
    assert pane.client.name == "inert", "panel must run the inert harness, not a model agent"
    assert pane.client.bridge_path == str(bridge.discovery_path), "panel client not pinned to the shared bridge"
    return pane


def assert_denied(client, node_name):
    before = dialogs_seen
    reply = execute(client, node_name)
    assert not reply["success"] and "denied" in reply["error"], reply
    assert dialogs_seen == before + 1, "expected exactly one approval dialog"
    assert nuke.toNode(node_name) is None, "denied execution mutated the script"


for name in NAMES.values():
    assert nuke.toNode(name) is None, "unique test node name already exists: %s" % name


def _timeout():
    print("NUKE_CODEX_SHARED_BRIDGE_TIMEOUT", flush=True)
    os._exit(1)


watchdog = threading.Timer(120, _timeout)
watchdog.daemon = True
watchdog.start()

client = None
panes = []
bridge = None
try:
    # 1. Bridge exists with no pane; an external stdio client reaches it.
    bridge = ensure_bridge()
    path = bridge.discovery_path
    assert path is not None and path.exists()
    client = StdioMcpClient(path)
    assert client.request("initialize", {"protocolVersion": "2025-11-25"})["serverInfo"]["name"]
    tool_names = {tool["name"] for tool in client.request("tools/list")["tools"]}
    assert {"execute_python", "get_nuke_context"} <= tool_names, tool_names
    context_ok(client)

    # 2. A real pane attaches to the same bridge; trust applies to external callers.
    pane = open_pane()
    panes.append(pane)
    assert ensure_bridge() is bridge and pane.bridge is bridge
    assert bridge.discovery_path == path and path.exists()
    assert not pane.is_python_trusted()
    pane.trusted_python.setChecked(True)
    assert pane.is_python_trusted()
    before = dialogs_seen
    reply = execute(client, NAMES["trusted"])
    assert reply["success"], reply
    assert NAMES["trusted"] in reply["added_nodes"], reply
    assert nuke.toNode(NAMES["trusted"]) is not None
    assert dialogs_seen == before, "trusted pane must not prompt"

    # 2b. Hiding the same pane must reset trust; external callers are asked again.
    pane.hide()
    app.processEvents()
    assert not pane.trusted_python.isChecked() and not pane.is_python_trusted(), "hidden pane kept trust"
    assert bridge.server.isListening() and bridge.discovery_path == path and path.exists()
    context_ok(client)
    assert_denied(client, NAMES["denied_hidden"])
    pane.show()
    app.processEvents()
    assert not pane.trusted_python.isChecked() and not pane.is_python_trusted(), "show must not restore trust"
    assert ensure_bridge() is bridge and pane.bridge is bridge and bridge.discovery_path == path
    pane.trusted_python.setChecked(True)
    assert pane.is_python_trusted()

    # 3. Closing the pane must not take the bridge down and must reset trust.
    pane.close()
    app.processEvents()
    assert not pane.trusted_python.isChecked() and not pane.is_python_trusted()
    assert bridge.server.isListening() and path.exists()
    assert ensure_bridge() is bridge
    context_ok(client)
    assert_denied(client, NAMES["denied_closed"])

    # 4. A new pane reuses the bridge and starts untrusted.
    pane = open_pane()
    panes.append(pane)
    assert pane.bridge is bridge and bridge.discovery_path == path
    assert not pane.trusted_python.isChecked() and not pane.is_python_trusted()
    assert_denied(client, NAMES["denied_new"])
    context_ok(client)

    pane.close()
    app.processEvents()
    context_ok(client)
    print("NUKE_CODEX_SHARED_BRIDGE_OK", str(path))
finally:
    presser.stop()
    for node_name in NAMES.values():
        node = nuke.toNode(node_name)
        if node is not None:
            nuke.delete(node)
    for pane in panes:
        try:
            pane.close()
            pane.deleteLater()
        except RuntimeError:
            pass
    if client is not None:
        client.close()
    app.aboutToQuit.emit()
    if bridge is not None and bridge.discovery_path is not None:
        assert not bridge.discovery_path.exists(), "discovery file survived shutdown"
    watchdog.cancel()
    chat_store.chats_root = _real_chats_root
    harnesses.HARNESSES[:] = _real_harnesses
    shutil.rmtree(_isolated, ignore_errors=True)
