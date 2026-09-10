"""Chat persistence: store round-trip, transcript replay, usage routing."""

import json
from pathlib import Path

from PySide6 import QtWidgets

from nuke_codex_panel.chat_store import ChatStore, chats_root, project_key
from nuke_codex_panel.harnesses import create_harness
from nuke_codex_panel.ui.chat_view import BubbleText, ChatView, CollapsibleSection


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_store_round_trip_and_archive(tmp_path, monkeypatch):
    monkeypatch.setattr("nuke_codex_panel.chat_store.chats_root", lambda: tmp_path / "chats")
    store = ChatStore("/projects/comp.nk", "codex")
    records = [{"role": "user", "text": "hi", "images": []}]
    store.save(records, {"thread_id": "t1"})
    loaded = store.load()
    assert loaded["messages"] == records
    assert loaded["session"] == {"thread_id": "t1"}

    archived = store.archive()
    assert archived is not None and archived.exists()
    assert store.load()["messages"] == []  # transcript moved out of the way
    assert "codex-" in archived.name


def test_store_isolated_per_project_and_harness(tmp_path, monkeypatch):
    monkeypatch.setattr("nuke_codex_panel.chat_store.chats_root", lambda: tmp_path / "chats")
    ChatStore("/projects/a.nk", "codex").save([{"role": "user", "text": "A"}], {})
    ChatStore("/projects/b.nk", "codex").save([{"role": "user", "text": "B"}], {})
    ChatStore("/projects/a.nk", "pi").save([{"role": "user", "text": "P"}], {})
    assert ChatStore("/projects/a.nk", "codex").load()["messages"][0]["text"] == "A"
    assert ChatStore("/projects/b.nk", "codex").load()["messages"][0]["text"] == "B"
    assert ChatStore("/projects/a.nk", "pi").load()["messages"][0]["text"] == "P"
    assert project_key("/projects/a.nk") != project_key("/projects/b.nk")


def test_transcript_replay_round_trip():
    chat = ChatView()
    chat.add_user_message("hello", ["/tmp/shot.png"])
    chat.start_assistant("Pi")
    chat.append_thinking("pondering")
    chat.append_delta("first reply")
    chat.add_tool_event({"phase": "start", "id": "t1", "tool": "bash", "detail": "ls"})
    chat.add_tool_event({"phase": "end", "id": "t1", "tool": "bash", "ok": True, "detail": "ok!"})
    chat.append_delta("second reply")
    chat.finish_assistant()
    chat.add_error("boom")
    records = chat.records()

    restored = ChatView()
    restored.load_records(records)
    # Replaying must not mutate the saved records.
    assert restored.records() == records, (restored.records(), records)

    kinds = []
    for widget in restored.container.findChildren(CollapsibleSection):
        kinds.append(widget.title.split()[0])
    assert kinds == ["Thinking", "Tools"], kinds
    body_texts = [
        widget.toPlainText() for widget in restored.container.findChildren(BubbleText)
    ]
    joined = "\n".join(body_texts)
    assert "pondering" in joined and "first reply" in joined
    assert "second reply" in joined and "boom" in joined
    tools = restored.container.findChildren(QtWidgets.QLabel, "toolLine")
    assert "ok!" in tools[0].text()


def test_json_file_stays_valid_after_replay(tmp_path, monkeypatch):
    monkeypatch.setattr("nuke_codex_panel.chat_store.chats_root", lambda: tmp_path / "chats")
    store = ChatStore("/projects/x.nk", "pi")
    store.save([{"role": "assistant", "sections": [{"kind": "text", "text": "a" * 50}]}], {})
    payload = json.loads(store.path.read_text())
    assert payload["version"] == 1 and payload["harness"] == "pi"
    assert payload["messages"][0]["sections"][0]["text"].startswith("aaa")


def test_harness_session_states_and_usage_routing():
    codex = create_harness("codex", "/tmp")
    codex.resume_session({"thread_id": "abc"})
    assert codex.session_state() == {"thread_id": "abc"}
    usage = []
    codex.usage_changed.connect(usage.append)
    codex._usage_updated(
        {"tokenUsage": {"last": {"totalTokens": 5000, "inputTokens": 4000,
                                 "cachedInputTokens": 1000, "outputTokens": 50},
                        "total": {}, "modelContextWindow": 200000}}
    )
    assert usage[0]["used"] == 5000 and usage[0]["window"] == 200000
    assert usage[0]["percent"] == 2.5 and usage[0]["cached"] == 1000

    pi = create_harness("pi", "/tmp")
    pi.resume_session({"session_id": "s1", "session_file": "/tmp/s.jsonl"})
    assert pi.session_state() == {"session_id": "s1", "session_file": "/tmp/s.jsonl"}
    pi.session_dir = Path("/tmp/sessions")
    args = pi.launch_arguments()
    assert "--session-dir" in args and "--session-id" in args and "--no-session" not in args
    pi.session_dir = None
    args = pi.launch_arguments()
    assert "--no-session" in args and "--session-id" not in args  # ephemeral without a dir
    usage.clear()
    pi.usage_changed.connect(usage.append)
    pi._stats_loaded(
        {"data": {"tokens": {"input": 10, "cacheRead": 5, "output": 2},
                  "cost": 0.25, "contextUsage": {"tokens": 60000,
                                                 "contextWindow": 200000, "percent": 30}}}
    )
    assert usage[0]["used"] == 60000 and usage[0]["percent"] == 30 and usage[0]["cost"] == 0.25
