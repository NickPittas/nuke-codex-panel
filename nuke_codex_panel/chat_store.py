"""Per-project chat transcripts and harness session handles.

Layout (under the app data dir, keyed by a hash of the project path so nothing
is written into project folders):

    chats/<slug>-<hash>/codex.json          # current transcript for a harness
    chats/<slug>-<hash>/archive/codex-<ts>.json
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from PySide6 import QtCore

VERSION = 1
MAX_RECORDS = 200
MAX_TEXT = 20000


def chats_root() -> Path:
    base = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppDataLocation
    )
    root = Path(base) if base else Path.home() / ".local" / "share" / "nuke-codex-panel"
    return root / "chats"


def project_key(project_path: str) -> str:
    """Stable, filesystem-safe key for a project path."""
    path = str(Path(str(project_path)).expanduser())
    digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(path).name or "untitled")[:40]
    return "%s-%s" % (slug.strip("-") or "untitled", digest)


def _trim_text(value) -> str:
    text = value if isinstance(value, str) else str(value or "")
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "\n… (truncated)"


def _trim(records: list) -> list:
    trimmed = []
    for record in records[-MAX_RECORDS:]:
        record = dict(record)
        if "text" in record:
            record["text"] = _trim_text(record["text"])
        if "sections" in record:
            for section in record["sections"]:
                if "text" in section:
                    section["text"] = _trim_text(section["text"])
                for line in section.get("lines") or []:
                    line["text"] = _trim_text(line.get("text", ""))
        trimmed.append(record)
    return trimmed


class ChatStore:
    """One transcript file per (project, harness)."""

    def __init__(self, project_path: str, harness: str):
        self.project_path = str(project_path)
        self.harness = harness
        self.dir = chats_root() / project_key(project_path)
        self.path = self.dir / ("%s.json" % harness)

    def load(self) -> dict:
        """Return {"messages": [...], "session": {...}}; empty when absent."""
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"messages": [], "session": {}}
        if payload.get("harness") != self.harness:
            return {"messages": [], "session": {}}
        return {
            "messages": payload.get("messages") or [],
            "session": payload.get("session") or {},
        }

    def save(self, records: list, session: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": VERSION,
            "project": self.project_path,
            "harness": self.harness,
            "saved": time.time(),
            # Empty handles mean "no session to resume"; drop them so a stored
            # transcript never triggers a resume prompt for nothing.
            "session": {key: value for key, value in (session or {}).items() if value},
            "messages": _trim(records),
        }
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)

    def archive(self) -> Path | None:
        """Move the current transcript into archive/ and return its new path."""
        if not self.path.is_file():
            return None
        archive_dir = self.dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = archive_dir / ("%s-%s.json" % (self.harness, stamp))
        counter = 1
        while target.exists():
            target = archive_dir / ("%s-%s-%d.json" % (self.harness, stamp, counter))
            counter += 1
        self.path.replace(target)
        return target
