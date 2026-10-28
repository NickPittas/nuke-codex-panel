"""Protocol-level harness tests (no subprocesses)."""

import json

from PySide6 import QtWidgets

from nuke_codex_panel.harnesses import create_harness
from nuke_codex_panel.harnesses.nuke_mcp import (
    merge_agent_mcp_config,
    runtime_config_path,
    write_claude_mcp_config,
    write_opencode_config,
)


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_pi_rpc_message_routing():
    client = create_harness("pi", "/tmp")
    client._write = lambda message: None  # no live process in tests
    deltas, events = [], []
    client.message_delta.connect(deltas.append)
    client.turn_started.connect(lambda: events.append("start"))
    client.turn_completed.connect(lambda status: events.append(status))

    client._handle_message({"type": "ready"})
    assert client.ready
    client._handle_message({"type": "agent_start"})
    client._handle_message(
        {"type": "message_update",
         "assistantMessageEvent": {"type": "text_start", "contentIndex": 0}}
    )
    client._handle_message(
        {"type": "message_update",
         "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "Hel"}}
    )
    client._handle_message(
        {"type": "message_update",
         "assistantMessageEvent": {"type": "text_start", "contentIndex": 1}}
    )
    client._handle_message(
        {"type": "message_update",
         "assistantMessageEvent": {"type": "text_delta", "contentIndex": 1, "delta": "lo"}}
    )
    client._handle_message({"type": "agent_settled"})
    assert deltas == ["Hel", "\n\n", "lo"], deltas
    assert events == ["start", "completed"], events
    assert not client._busy


def test_pi_rpc_models_and_extension_dialogs():
    client = create_harness("pi", "/tmp")
    models, written = [], []
    client.models_changed.connect(models.append)
    client._write = written.append  # capture instead of writing to a process

    client._handle_message(
        {"type": "response", "id": 1, "command": "get_available_models", "success": True,
         "data": {"models": [{"provider": "openai", "id": "gpt-5.2", "name": "GPT-5.2"}]}}
    )  # unknown id: ignored
    assert models == []

    client._callbacks[1] = client._models_loaded
    client._handle_message(
        {"type": "response", "id": 1, "command": "get_available_models", "success": True,
         "data": {"models": [{"provider": "openai", "id": "gpt-5.2", "name": "GPT-5.2"}]}}
    )
    assert models[0][0]["id"] == "openai/gpt-5.2"

    client._handle_message(
        {"type": "extension_ui_request", "id": "x1", "method": "confirm"}
    )
    assert written == [
        {"type": "extension_ui_response", "id": "x1", "cancelled": True}
    ], written


def test_opencode_sse_events():
    client = create_harness("opencode", "/tmp")
    client.session_id = "ses_1"
    deltas, events = [], []
    client.message_delta.connect(deltas.append)
    client.turn_completed.connect(lambda status: events.append(status))
    client._turn_open = True

    client._handle_event({"type": "message.part.delta",
                          "properties": {"sessionID": "ses_2", "field": "text", "delta": "x"}})
    assert deltas == []  # foreign session ignored
    client._handle_event({"type": "message.part.delta",
                          "properties": {"sessionID": "ses_1", "field": "text", "delta": "Hi"}})
    client._handle_event({"type": "session.idle", "properties": {"sessionID": "ses_1"}})
    assert deltas == ["Hi"]
    assert events == ["completed"]
    assert not client._turn_open


def test_pi_rpc_thinking_and_tools():
    client = create_harness("pi", "/tmp")
    thinking, tools = [], []
    client.thinking_delta.connect(thinking.append)
    client.tool_event.connect(tools.append)

    client._handle_message(
        {"type": "message_update",
         "assistantMessageEvent": {"type": "thinking_delta", "delta": "pondering"}}
    )
    client._handle_message(
        {"type": "tool_execution_start", "toolCallId": "c1", "toolName": "bash",
         "args": {"command": "ls /"}}
    )
    client._handle_message(
        {"type": "tool_execution_end", "toolCallId": "c1", "toolName": "bash",
         "result": {"content": [{"type": "text", "text": "afs\nbin"}]}, "isError": False}
    )
    assert thinking == ["pondering"]
    assert tools[0]["phase"] == "start" and tools[0]["tool"] == "bash"
    assert tools[1]["phase"] == "end" and tools[1]["ok"] and "afs" in tools[1]["detail"]


def test_opencode_part_routing():
    client = create_harness("opencode", "/tmp")
    client.session_id = "ses_1"
    text, thinking, tools = [], [], []
    client.message_delta.connect(text.append)
    client.thinking_delta.connect(thinking.append)
    client.tool_event.connect(tools.append)

    def event(payload_type, part):
        client._handle_event(
            {"type": payload_type, "properties": {"sessionID": "ses_1", "part": part}}
        )

    event("message.part.updated", {"id": "p1", "type": "reasoning"})
    client._handle_event(
        {"type": "message.part.delta",
         "properties": {"sessionID": "ses_1", "partID": "p1", "field": "text", "delta": "hmm"}}
    )
    event("message.part.updated", {"id": "p2", "type": "text"})
    client._handle_event(
        {"type": "message.part.delta",
         "properties": {"sessionID": "ses_1", "partID": "p2", "field": "text", "delta": "answer"}}
    )
    event("message.part.updated",
          {"id": "p3", "type": "tool", "tool": "bash", "callID": "t1",
           "state": {"status": "running", "input": {"command": "ls"}}})
    event("message.part.updated",
          {"id": "p3", "type": "tool", "tool": "bash", "callID": "t1",
           "state": {"status": "completed", "output": "afs"}})

    assert thinking == ["hmm"]  # reasoning must not leak into the answer
    assert text == ["answer"]
    assert tools[0]["phase"] == "start" and tools[0]["tool"] == "bash"
    assert tools[1]["phase"] == "end" and tools[1]["ok"] and tools[1]["detail"] == "afs"


def test_mcp_config_merge(tmp_path):
    path = tmp_path / "agent" / "mcp.json"
    merge_agent_mcp_config(tmp_path / "agent")
    first = json.loads(path.read_text())
    assert first["mcpServers"]["nuke"]["args"][-1] == "nuke_codex_panel.mcp_server.server"
    # merging preserves unrelated entries
    first["mcpServers"]["other"] = {"command": "x"}
    path.write_text(json.dumps(first))
    merge_agent_mcp_config(tmp_path / "agent")
    merged = json.loads(path.read_text())
    assert "other" in merged["mcpServers"] and "nuke" in merged["mcpServers"]


def test_pinned_runtime_configs_do_not_clobber_each_other(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    first, second = (str(tmp_path / ("session-%d-ab.json" % pid)) for pid in (1, 2))

    def pin(path, key):
        data = json.loads(path.read_text())
        entry = data["mcpServers"]["nuke"] if key == "claude" else data["mcp"]["nuke"]
        return (entry["env"] if key == "claude" else entry["environment"])["NUKE_CODEX_BRIDGE_FILE"]

    for key, name, writer in (
        ("claude", "claude-mcp.json", write_claude_mcp_config),
        ("opencode", "opencode-nuke.json", write_opencode_config),
    ):
        path_one = runtime_config_path(name, first)
        path_two = runtime_config_path(name, second)
        writer(path_one, first)
        writer(path_two, second)
        assert path_one != path_two
        assert pin(path_one, key) == first
        assert pin(path_two, key) == second


def test_global_agent_config_stays_unpinned(tmp_path, monkeypatch):
    monkeypatch.setenv("NUKE_CODEX_BRIDGE_FILE", str(tmp_path / "session-1-ab.json"))
    path = tmp_path / "agent" / "mcp.json"
    path.parent.mkdir()
    other = {"command": "uvx", "args": ["x"], "env": {"KEY": "v"}, "directTools": True}
    path.write_text(json.dumps({"imports": ["codex"], "mcpServers": {"other": other}}))
    merge_agent_mcp_config(path.parent)
    saved = json.loads(path.read_text())
    assert saved["mcpServers"]["other"] == other
    assert saved["imports"] == ["codex"]
    assert "NUKE_CODEX_BRIDGE_FILE" not in saved["mcpServers"]["nuke"]["env"]
