import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from nuke_codex_panel.mcp_server.server import _discover_bridge


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("NUKE_CODEX_BRIDGE_FILE", raising=False)
    directory = tmp_path / ("nuke-codex-panel-%s" % os.getuid())
    directory.mkdir()
    return directory


@pytest.fixture
def dead_pid():
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid


def write_record(path: Path, token: str, pid: int, mtime: int) -> Path:
    path.write_text(json.dumps({"token": token, "pid": pid}), encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def test_automatic_discovery_selects_newest_live_session(runtime, dead_pid):
    write_record(runtime / "session-old.json", "old-live", os.getpid(), 1_000)
    write_record(runtime / "session-new.json", "new-live", os.getpid(), 2_000)
    write_record(runtime / "session-newest-dead.json", "dead", dead_pid, 3_000)
    (runtime / "session-newest-malformed.json").write_text("{not json", encoding="utf-8")
    os.utime(runtime / "session-newest-malformed.json", (4_000, 4_000))

    assert _discover_bridge()["token"] == "new-live"


def test_automatic_discovery_fails_when_no_live_session_exists(runtime, dead_pid):
    write_record(runtime / "session-dead.json", "dead", dead_pid, 1_000)
    (runtime / "session-malformed.json").write_text("[]", encoding="utf-8")

    with pytest.raises(RuntimeError, match="No active Nuke Codex bridge"):
        _discover_bridge()


def test_explicit_session_wins_over_newer_automatic_session(runtime, monkeypatch):
    pinned = write_record(runtime / "session-pinned.json", "pinned", os.getpid(), 1_000)
    write_record(runtime / "session-newer.json", "newer", os.getpid(), 2_000)
    monkeypatch.setenv("NUKE_CODEX_BRIDGE_FILE", str(pinned))

    assert _discover_bridge()["token"] == "pinned"


def test_explicit_dead_session_does_not_fall_back_to_live_session(runtime, dead_pid, monkeypatch):
    pinned = write_record(runtime / "session-pinned.json", "pinned", dead_pid, 1_000)
    write_record(runtime / "session-other.json", "other", os.getpid(), 2_000)
    monkeypatch.setenv("NUKE_CODEX_BRIDGE_FILE", str(pinned))

    with pytest.raises(RuntimeError, match="not active"):
        _discover_bridge()


def test_explicit_missing_or_malformed_session_does_not_fall_back_to_live_session(
    runtime, monkeypatch
):
    write_record(runtime / "session-other.json", "other", os.getpid(), 2_000)
    missing = runtime / "session-missing.json"
    malformed = runtime / "session-malformed.json"
    malformed.write_text("{not json", encoding="utf-8")

    for path in (missing, malformed):
        monkeypatch.setenv("NUKE_CODEX_BRIDGE_FILE", str(path))
        with pytest.raises(RuntimeError, match="Configured Nuke bridge is unavailable"):
            _discover_bridge()
