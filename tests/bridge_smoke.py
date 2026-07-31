"""Exercise the authenticated sidecar-to-Nuke bridge on Nuke's Qt loop."""

import threading

import nuke
from PySide6 import QtCore

from nuke_codex_panel.bridge import NukeBridgeServer
from nuke_codex_panel.mcp_server.server import _bridge_call


node_name = "CodexBridgeSmokeNode"
existing = nuke.toNode(node_name)
if existing is not None:
    nuke.delete(existing)

loop = QtCore.QEventLoop()
bridge = NukeBridgeServer(lambda _code: True)
assert bridge.start()
outcome = {}


def worker():
    try:
        outcome["context"] = _bridge_call("get_context", {"include_nodes": False})
        outcome["execution"] = _bridge_call(
            "execute_python",
            {
                "code": (
                    "node = nuke.nodes.NoOp(name='%s')\n"
                    "node['label'].setValue('created through MCP bridge')\n"
                    "node.fullName()" % node_name
                ),
                "undo": True,
                "label": "Codex bridge smoke",
            },
        )
    except Exception as exc:
        outcome["error"] = repr(exc)


thread = threading.Thread(target=worker, daemon=True)
thread.start()


def poll():
    if not thread.is_alive():
        loop.quit()
    else:
        QtCore.QTimer.singleShot(20, poll)


QtCore.QTimer.singleShot(0, poll)
QtCore.QTimer.singleShot(15_000, loop.quit)
loop.exec()
thread.join(timeout=1)

try:
    assert not thread.is_alive(), "bridge call timed out"
    assert "error" not in outcome, outcome
    assert outcome["context"]["success"], outcome
    assert outcome["context"]["context"]["nuke_version"] == nuke.NUKE_VERSION_STRING
    assert outcome["execution"]["success"], outcome
    node = nuke.toNode(node_name)
    assert node is not None, outcome
    assert node["label"].value() == "created through MCP bridge"
    assert node_name in outcome["execution"]["added_nodes"]
    print("NUKE_CODEX_BRIDGE_OK", outcome["execution"]["result"])
finally:
    node = nuke.toNode(node_name)
    if node is not None:
        nuke.delete(node)
    bridge.stop()
