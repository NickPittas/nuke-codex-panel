"""End-to-end test: Codex App Server calls execute_python in live Nuke."""

from pathlib import Path

import nuke
from PySide6 import QtCore

from nuke_codex_panel.app_server import CodexAppServerClient
from nuke_codex_panel.bridge import NukeBridgeServer


node_name = "CodexEndToEndSmokeNode"
existing = nuke.toNode(node_name)
if existing is not None:
    nuke.delete(existing)

loop = QtCore.QEventLoop()
bridge = NukeBridgeServer(lambda _code: True)
assert bridge.start()
project_root = Path(__file__).resolve().parents[1]
client = CodexAppServerClient(
    str(project_root), bridge_path=str(bridge.discovery_path)
)
deltas = []
failures = []


def on_ready(ready):
    if ready:
        client.send_turn(
            "Use the Nuke execute_python MCP tool now. Create exactly one NoOp node "
            "named CodexEndToEndSmokeNode and set its label to MCP_OK. After the tool "
            "succeeds, reply with exactly NUKE_CODEX_TOOL_OK."
        )


def on_error(message):
    failures.append(message)
    loop.quit()


client.ready_changed.connect(on_ready)
client.status_changed.connect(lambda message: print("CODEX_STATUS", message))
client.message_delta.connect(deltas.append)
client.error.connect(on_error)
client.turn_completed.connect(lambda _status: loop.quit())
QtCore.QTimer.singleShot(120_000, lambda: (failures.append("timeout"), loop.quit()))
client.start()
loop.exec()
client.stop()

try:
    assert not failures, failures
    response = "".join(deltas)
    assert "NUKE_CODEX_TOOL_OK" in response, response
    node = nuke.toNode(node_name)
    assert node is not None, response
    assert node["label"].value() == "MCP_OK", node["label"].value()
    print("NUKE_CODEX_TOOL_SMOKE_OK", response.strip())
finally:
    node = nuke.toNode(node_name)
    if node is not None:
        nuke.delete(node)
    bridge.stop()
