"""Per-project chat transcript and Pi session handle.

Layout (under the app data dir, keyed by a hash of the project path so nothing
is written into project folders):

    chats/<slug>-<hash>/pi.json             # current transcript
    chats/<slug>-<hash>/archive/pi-<ts>.json
    chats/<slug>-<hash>/assets/<sha256>.png # delivered images, content addressed

Saving is either synchronous (``save``) or handed to one background writer
(``request_save``): the newest request wins, the JSON is built and written off the
caller's thread, and ``flush``/``archive``/``close`` wait for it. Every transcript write
carries a monotonically increasing sequence number and the store generation it was
requested under, so an older snapshot or a write that belongs to an archived chat can
never overwrite newer data. The writer thread never touches Qt objects.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import re
import threading
import time
import weakref
from pathlib import Path

from PySide6 import QtCore

VERSION = 2
MAX_RECORDS = 200
MAX_TEXT = 20000
_MAX_DEPTH = 8
_MAX_ITEMS = 200
_HARNESS = "pi"


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


def _trim_value(value, depth: int = 0):
    """Bounded copy of a structured payload (tool arguments/results); never mutates its input."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _trim_text(value)
    if depth >= _MAX_DEPTH:
        return _trim_text(str(value))
    if isinstance(value, dict):
        return {
            str(key): _trim_value(item, depth + 1)
            for key, item in list(value.items())[:_MAX_ITEMS]
        }
    if isinstance(value, (list, tuple)):
        return [_trim_value(item, depth + 1) for item in list(value)[:_MAX_ITEMS]]
    return _trim_text(str(value))


def _trim_section(section: dict) -> dict:
    out = dict(section)
    if "text" in out:
        out["text"] = _trim_text(out["text"])
    for key in ("arguments", "result", "partial"):
        if key in out:
            out[key] = _trim_value(out[key])
    if "lines" in out:
        out["lines"] = [
            dict(line, text=_trim_text(line.get("text", ""))) for line in out["lines"] or []
        ]
    return out


def _trim(records: list) -> list:
    trimmed = []
    for record in records[-MAX_RECORDS:]:
        record = dict(record)
        if "text" in record:
            record["text"] = _trim_text(record["text"])
        if "sections" in record:
            record["sections"] = [_trim_section(section) for section in record["sections"]]
        trimmed.append(record)
    return trimmed


_LIVE: "weakref.WeakSet[ChatStore]" = weakref.WeakSet()


def _flush_live_stores():
    for store in list(_LIVE):
        try:
            store.flush(timeout=5.0)
        except Exception:
            pass


atexit.register(_flush_live_stores)


class ChatStore:
    """The one transcript file of a project (Pi), plus its archive and image assets."""

    def __init__(self, project_path: str):
        self.project_path = str(project_path)
        self.dir = chats_root() / project_key(project_path)
        self.path = self.dir / ("%s.json" % _HARNESS)
        self._io = threading.Lock()  # serializes file operations (writes, archive)
        self._cond = threading.Condition()  # guards _pending/_busy/_closed/_seq/_generation
        self._pending = None
        self._busy = False
        self._closed = False
        self._thread: threading.Thread | None = None
        self._seq = 0
        self._written_seq = 0
        self._generation = 0
        self._error: BaseException | None = None
        _LIVE.add(self)

    # -- reading -----------------------------------------------------------------------------

    def load(self) -> dict:
        """Return {"messages": [...], "session": {...}}; empty when absent."""
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"messages": [], "session": {}}
        if not isinstance(payload, dict) or payload.get("harness") != _HARNESS:
            return {"messages": [], "session": {}}
        return {
            "messages": payload.get("messages") or [],
            "session": payload.get("session") or {},
        }

    # -- writing -----------------------------------------------------------------------------

    def _serialize(self, records: list, session: dict) -> str:
        payload = {
            "version": VERSION,
            "project": self.project_path,
            "harness": _HARNESS,
            "saved": time.time(),
            # Empty handles mean "no session to resume"; drop them so a stored
            # transcript never claims a session that does not exist.
            "session": {key: value for key, value in (session or {}).items() if value},
            "messages": _trim(records),
        }
        return json.dumps(payload, ensure_ascii=False)

    def _write(self, seq: int, generation: int, text: str):
        with self._io:
            if generation != self._generation or seq < self._written_seq:
                return  # an archived chat's write, or an older snapshot than what is on disk
            self.dir.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(self.path)
            self._written_seq = seq

    def save(self, records: list, session: dict) -> None:
        """Write the transcript now (raises OSError on failure). Supersedes any queued save."""
        with self._cond:
            self._pending = None
            self._seq += 1
            seq, generation = self._seq, self._generation
        self._write(seq, generation, self._serialize(records, session))

    def request_save(self, records: list, session: dict) -> None:
        """Queue a save for the background writer and return at once.

        ``records`` must not be mutated afterwards (``ChatView.records()`` already guarantees that).
        Only the newest queued request is written; failures are reported by ``take_error``.
        """
        with self._cond:
            if self._closed:
                raise RuntimeError("chat store is closed")
            self._seq += 1
            self._pending = (self._seq, self._generation, list(records), dict(session or {}))
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._run, name="nuke-codex-chat-writer", daemon=True
                )
                self._thread.start()
            self._cond.notify_all()

    def _run(self):
        while True:
            with self._cond:
                while self._pending is None and not self._closed:
                    self._cond.wait()
                if self._pending is None:
                    return
                seq, generation, records, session = self._pending
                self._pending = None
                self._busy = True
            try:
                self._write(seq, generation, self._serialize(records, session))
            except (OSError, TypeError, ValueError) as exc:
                self._error = exc
            finally:
                with self._cond:
                    self._busy = False
                    self._cond.notify_all()

    def flush(self, timeout: float | None = None) -> bool:
        """Block until every queued save has been written; False when ``timeout`` expired first."""
        with self._cond:
            return self._cond.wait_for(
                lambda: self._pending is None and not self._busy, timeout
            )

    def take_error(self) -> BaseException | None:
        """The last background write failure (cleared by this call), or None."""
        error, self._error = self._error, None
        return error

    def close(self) -> None:
        """Write whatever is queued and stop the writer. The store is not usable afterwards."""
        self.flush(timeout=10.0)
        with self._cond:
            self._closed = True
            self._cond.notify_all()
            thread = self._thread
        if thread is not None:
            thread.join(timeout=5.0)

    # -- assets / archive -----------------------------------------------------------------------

    def save_image_asset(self, source: str, expected_sha256: str) -> tuple[Path, int]:
        """Copy a delivered image into this chat's persistent assets; returns (asset path, byte size).

        The bytes are read once and must hash to ``expected_sha256`` (what the model received);
        anything else raises ValueError, so a preview can never show different pixels than the agent
        got. Assets are content-addressed, immutable, and kept when a chat is archived or reloaded.
        """
        data = Path(source).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_sha256:
            raise ValueError("the file changed after it was delivered (sha256 %s, delivered %s)" % (digest[:12], expected_sha256[:12]))
        directory = self.dir / "assets"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / ("%s.png" % digest)
        if not target.is_file() or target.stat().st_size != len(data):
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(data)
            temporary.replace(target)
        return target, len(data)

    def archive(self) -> Path | None:
        """Move the current transcript into archive/ and return its new path.

        Queued saves are written first so the archive holds the final state; the store generation is
        then advanced so nothing requested for the archived chat can be written over the next one.
        """
        self.flush()
        with self._io:
            with self._cond:
                self._generation += 1
            if not self.path.is_file():
                return None
            archive_dir = self.dir / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            target = archive_dir / ("%s-%s.json" % (_HARNESS, stamp))
            counter = 1
            while target.exists():
                target = archive_dir / ("%s-%s-%d.json" % (_HARNESS, stamp, counter))
                counter += 1
            self.path.replace(target)
            return target
