"""Offline search and retrieval over the *installed* Nuke documentation.

Two sources under the installed ``Documentation`` directory are indexed with the
standard library only (no ``nuke`` import, so a sidecar may call this from threads):

* ``PythonDevGuide/Nuke/objects.inv`` - the Sphinx inventory of the Python API
  (``nuke.createNode``, ``nuke.XY_Knob.setAnimated``, ...) and the developer-guide
  pages.  Reads return the signature, description, parameters and return type from
  the matching ``_autosummary/*.html`` anchor.
* ``html/Data/Alias.xml`` - node class name -> node reference page.  Reads return the
  page text including the *Control (UI) / Knob (Scripting)* tables, with row spans
  carried so every knob row keeps its tab, UI label, scripting name and default.

Nothing is copied into the repository and nothing is fetched from the web.  Document
ids (``py:nuke.createNode``, ``node:Radial``, ``guide:threading``, ...) are keys of the
in-memory index, never paths; every page is resolved from the index and must stay inside
its fixed documentation subtree.  Results for unknown names are explicitly empty - a
close name is never substituted for a missing one.
"""

from __future__ import annotations

import heapq
import re
import threading
import zlib
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple
from xml.etree import ElementTree

__all__ = [
    "ApiDocumentation",
    "DEFAULT_LIMIT",
    "MAX_CONTENT_CHARS",
    "MAX_LIMIT",
    "MAX_QUERY_CHARS",
]

DEFAULT_LIMIT = 5
MAX_LIMIT = 8
MAX_QUERY_CHARS = 200
MAX_CONTENT_CHARS = 12000
MAX_SUMMARY_CHARS = 300

_MAX_PAGE_BYTES = 8 * 1024 * 1024
_MAX_INVENTORY_BYTES = 64 * 1024 * 1024
_MAX_ALIAS_BYTES = 8 * 1024 * 1024
_PAGE_CACHE_SIZE = 12

_PYTHON_BASE = "PythonDevGuide/Nuke"
_PYTHON_INVENTORY = _PYTHON_BASE + "/objects.inv"
_NODE_BASE = "html/content"
_NODE_ALIAS = "html/Data/Alias.xml"

_PY_KINDS = {
    "py:module": "module",
    "py:class": "class",
    "py:function": "function",
    "py:method": "method",
    "py:attribute": "attribute",
    "py:property": "property",
    "py:exception": "exception",
}
_KIND_BONUS = {
    "node": 40,
    "function": 30,
    "class": 30,
    "exception": 25,
    "module": 20,
    "attribute": 5,
    "property": 5,
    "method": 0,
    "guide": 0,
    "guide_section": -10,
}
_NON_SECTION_LABELS = frozenset({"genindex", "modindex", "py-modindex", "search"})

# Words that describe *what the model wants* rather than naming an API symbol.
_STOP_WORDS = frozenset(
    "a an and api as at by class control controls doc docs documentation for from function "
    "how in is it knob knobs method methods node nodes nuke of on or parameter parameters "
    "python scripting table the to use using value values with".split()
)

_EXACT_FLOOR = 800
_RELEVANT_FLOOR = 600
_FALLBACK_CEILING = 300

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_TOKEN = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")
_INVENTORY_LINE = re.compile(r"^(.+?)\s+([^\s:]+:[^\s:]+)\s+(-?\d+)\s+(\S+)\s+(.*)$")


class _Entry(NamedTuple):
    id: str
    kind: str
    name: str
    title: str
    page: str  # POSIX path relative to the documentation root
    anchor: str
    tokens: frozenset
    short: str  # lowercase last dotted component


class _Index(NamedTuple):
    entries: tuple
    by_id: dict
    suffix: dict  # lowercase dotted suffix -> tuple of entry positions
    postings: dict  # token -> tuple of entry positions
    shorts: tuple
    version: str
    project: str


# ------------------------------------------------------------------ query helpers


def _tokens(text: str) -> list:
    out = []
    for part in re.split(r"[^A-Za-z0-9]+", text):
        out.extend(t.lower() for t in _TOKEN.findall(part))
    return out


def _safe_relative(location: str) -> str | None:
    """Return a normalised relative POSIX path, or None for anything that is not a plain
    in-tree relative reference (absolute, scheme, backslash, NUL, ``..``)."""
    if not location or "\x00" in location or "\\" in location or ":" in location:
        return None
    if location.startswith("/"):
        return None
    parts = location.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return None
    return "/".join(parts)


def _validate_query(query) -> str:
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    text = query.strip()
    if not text:
        raise ValueError("query must not be empty")
    if len(text) > MAX_QUERY_CHARS:
        raise ValueError("query is longer than %d characters" % MAX_QUERY_CHARS)
    if "\x00" in text:
        raise ValueError("query contains a NUL character")
    return text


def _validate_limit(limit) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    return min(limit, MAX_LIMIT)


# ------------------------------------------------------------------ index building


def _read_bounded(path: Path, limit: int) -> bytes:
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("%s is larger than the %d byte limit" % (path.name, limit))
    return data


def _parse_inventory(path: Path):
    data = _read_bounded(path, _MAX_INVENTORY_BYTES)
    header = []
    offset = 0
    for _ in range(4):
        end = data.index(b"\n", offset)
        header.append(data[offset:end].decode("utf-8", "replace").strip())
        offset = end + 1
    if not header[0].startswith("# Sphinx inventory version 2"):
        raise ValueError("%s is not a Sphinx version 2 inventory" % path.name)
    decompressor = zlib.decompressobj()
    body = decompressor.decompress(data[offset:], _MAX_INVENTORY_BYTES)
    if decompressor.unconsumed_tail:
        raise ValueError("%s expands beyond the size limit" % path.name)
    project = header[1].partition(":")[2].strip()
    version = header[2].partition(":")[2].strip()
    return project, version, body.decode("utf-8", "replace").splitlines()


def _make_entry(entry_id, kind, name, title, page, anchor, extra_text=""):
    tokens = frozenset(_tokens(name) + (_tokens(extra_text) if extra_text else []))
    return _Entry(entry_id, kind, name, title, page, anchor, tokens, name.rsplit(".", 1)[-1].lower())


def _python_entries(inventory_lines):
    entries = {}
    for line in inventory_lines:
        match = _INVENTORY_LINE.match(line)
        if not match:
            continue
        name, domain_role, priority, location, display = match.groups()
        location = location.replace("$", name) if location.endswith("$") else location
        page_part, _, anchor = location.partition("#")
        page = _safe_relative(page_part)
        if page is None or not page.endswith(".html"):
            continue
        page = "%s/%s" % (_PYTHON_BASE, page)
        if domain_role in _PY_KINDS and int(priority) >= 0:
            kind = _PY_KINDS[domain_role]
            entry_id = "py:" + name
            if entry_id not in entries:
                entries[entry_id] = _make_entry(entry_id, kind, name, name, page, anchor)
        elif domain_role == "std:doc" and not name.startswith("_autosummary/") and "/" not in name:
            entry_id = "guide:" + name
            title = display if display != "-" else name
            entries.setdefault(entry_id, _make_entry(entry_id, "guide", name, title, page, "", title))
        elif domain_role == "std:label" and name not in _NON_SECTION_LABELS and display != "-":
            entry_id = "section:" + name
            entries.setdefault(entry_id, _make_entry(entry_id, "guide_section", name, display, page, anchor, display))
    return list(entries.values())


def _node_entries(alias_path: Path):
    try:
        root = ElementTree.fromstring(_read_bounded(alias_path, _MAX_ALIAS_BYTES))
    except ElementTree.ParseError as exc:
        raise ValueError("%s is not valid XML: %s" % (alias_path.name, exc)) from exc
    entries = {}
    for node in root.iter("Map"):
        name = node.get("Name") or ""
        page = _safe_relative((node.get("Link") or "").partition("#")[0])
        if not name or page is None or not page.endswith(".html") or not _IDENT.fullmatch(name):
            continue
        entry_id = "node:" + name
        entries.setdefault(entry_id, _make_entry(entry_id, "node", name, name, "%s/%s" % (_NODE_BASE, page), ""))
    return list(entries.values())


def _build_index(root: Path) -> _Index:
    inventory = root / _PYTHON_INVENTORY
    alias = root / _NODE_ALIAS
    for source in (inventory, alias):
        if not source.is_file():
            raise FileNotFoundError("Nuke documentation source not found: %s" % source)
    project, version, lines = _parse_inventory(inventory)
    entries = tuple(_python_entries(lines) + _node_entries(alias))
    if not entries:
        raise ValueError("no documentation entries could be indexed from %s" % root)
    by_id, suffix, postings = {}, {}, {}
    for position, entry in enumerate(entries):
        by_id[entry.id] = position
        components = entry.name.lower().split(".")
        for start in range(len(components)):
            suffix.setdefault(".".join(components[start:]), []).append(position)
        for token in entry.tokens:
            postings.setdefault(token, []).append(position)
    return _Index(
        entries,
        by_id,
        {k: tuple(v) for k, v in suffix.items()},
        {k: tuple(v) for k, v in postings.items()},
        tuple(e.short for e in entries),
        version,
        project,
    )


_INDEX_CACHE: dict = {}
_INDEX_LOCK = threading.Lock()


def _cached_index(root: Path) -> _Index:
    """One immutable index per documentation root, rebuilt only if a source file changes."""
    stamps = []
    for relative in (_PYTHON_INVENTORY, _NODE_ALIAS):
        try:
            stat = (root / relative).stat()
        except OSError as exc:
            raise FileNotFoundError("Nuke documentation source not found: %s" % (root / relative)) from exc
        stamps.append((stat.st_mtime_ns, stat.st_size))
    key = (str(root), tuple(stamps))
    with _INDEX_LOCK:
        cached = _INDEX_CACHE.get(key)
        if cached is None:
            for stale in [k for k in _INDEX_CACHE if k[0] == key[0]]:
                del _INDEX_CACHE[stale]
            cached = _INDEX_CACHE[key] = _build_index(root)
        return cached


# ------------------------------------------------------------------ HTML -> text


_VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
_SKIP_TAGS = frozenset("script style nav footer head svg button form aside noscript template".split())
_HEADINGS = {"h%d" % n: n for n in range(1, 7)}
_BLOCK_TAGS = frozenset(
    "address article blockquote dd details div dl dt fieldset figure header main ol p section summary ul".split()
)


class _Table:
    __slots__ = ("rows", "row", "spans", "col", "cell_attrs")

    def __init__(self):
        self.rows = []
        self.row = None
        self.spans = {}
        self.col = 0
        self.cell_attrs = None


class _TextRenderer(HTMLParser):
    """Small HTML->text renderer keeping signatures, lists and table row/column structure."""

    def __init__(self, *, drop_nested_py: bool, keep_newlines: bool):
        super().__init__(convert_charrefs=True)
        self.drop_nested_py = drop_nested_py
        self.keep_newlines = keep_newlines
        self.lines: list = []
        self.cur: list = []
        self.cur_stack: list = []
        self.skip_tag = None
        self.skip_depth = 0
        self.pre = 0
        self.dl_depth = 0
        self.list_depth = 0
        self.heading = 0
        self.in_sig = False
        self.item_prefix = None
        self.tables: list = []

    # -- output helpers
    def _in_cell(self) -> bool:
        return bool(self.tables) and self.tables[-1].cell_attrs is not None

    def _gap(self):
        if self.lines and self.lines[-1] != "":
            self.lines.append("")

    def _take_text(self) -> list:
        raw = "".join(self.cur)
        self.cur = []
        if self.pre:
            return raw.splitlines()
        if self.in_sig or not self.keep_newlines:
            raw = raw.replace("\n", " ")
        out = []
        for part in raw.split("\n"):
            part = re.sub(r"[ \t\r\f]+", " ", part).strip()
            if part:
                out.append(part)
        return out

    def _flush(self, *, prefix: str = ""):
        if self._in_cell():
            self.cur.append(" ")
            return
        text = self._take_text()
        pending = self.item_prefix
        for number, line in enumerate(text):
            if number == 0 and pending is not None:
                line = pending + line
                self.item_prefix = pending = None
            self.lines.append(prefix + line if prefix and number == 0 else line)

    # -- parser callbacks
    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        classes = (attr.get("class") or "").split()
        if self.skip_tag is not None:
            if tag == self.skip_tag and tag not in _VOID:
                self.skip_depth += 1
            return
        if (
            tag in _SKIP_TAGS
            or (tag == "a" and "headerlink" in classes)
            or "viewcode-link" in classes
            or "nocontent" in classes  # MadCap in-page menus
        ):
            if tag not in _VOID:
                self.skip_tag, self.skip_depth = tag, 1
            return
        if tag == "dl":
            if self.drop_nested_py and self.dl_depth >= 1 and "py" in classes:
                self.skip_tag, self.skip_depth = tag, 1
                return
            self.dl_depth += 1
        if tag == "table":
            self._flush()
            self._gap()
            self.tables.append(_Table())
        elif tag == "tr" and self.tables:
            table = self.tables[-1]
            table.row, table.col = [], 0
        elif tag in ("td", "th") and self.tables and self.tables[-1].row is not None:
            table = self.tables[-1]
            table.cell_attrs = (_span(attr.get("rowspan")), _span(attr.get("colspan")))
            self.cur_stack.append(self.cur)
            self.cur = []
        elif tag in _HEADINGS:
            self._flush()
            self._gap()
            self.heading = _HEADINGS[tag]
        elif tag in ("ul", "ol"):
            self._flush()
            self.list_depth += 1
        elif tag == "li":
            self._flush()
            self.item_prefix = "  " * max(self.list_depth - 1, 0) + "- "
        elif tag == "pre":
            self._flush()
            self._gap()
            self.pre += 1
        elif tag == "dt":
            self._flush()
            if "sig" in classes:
                self._gap()
                self.in_sig = True
        elif tag == "br":
            if self._in_cell():
                self.cur.append(" ")
            else:
                self.cur.append("\n")
        elif tag == "p":
            self._flush()
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.skip_tag is not None:
            if tag == self.skip_tag:
                self.skip_depth -= 1
                if self.skip_depth == 0:
                    self.skip_tag = None
            return
        if tag == "dl":
            self.dl_depth = max(self.dl_depth - 1, 0)
            self._flush()
        elif tag in ("td", "th") and self.tables and self.tables[-1].cell_attrs is not None:
            table = self.tables[-1]
            text = re.sub(r"\s+", " ", "".join(self.cur)).strip()
            self.cur = self.cur_stack.pop() if self.cur_stack else []
            rowspan, colspan = table.cell_attrs
            table.cell_attrs = None
            _place_cell(table, text, rowspan, colspan)
        elif tag == "tr" and self.tables and self.tables[-1].row is not None:
            table = self.tables[-1]
            _finish_row(table)
        elif tag == "table" and self.tables:
            table = self.tables.pop()
            rendered = [row for row in table.rows if row]
            if self.tables and self.tables[-1].cell_attrs is not None:
                self.cur.append(" " + "; ".join(row.lstrip("# ") for row in rendered) + " ")
            else:
                self._flush()
                self.lines.extend(rendered)
                self._gap()
        elif tag in _HEADINGS and self.heading:
            level, self.heading = self.heading, 0
            text = " ".join(self._take_text())
            if text:
                self.lines.append("%s %s" % ("#" * level, text))
        elif tag in ("ul", "ol"):
            self._flush()
            self.list_depth = max(self.list_depth - 1, 0)
        elif tag == "pre" and self.pre:
            self._flush()
            self.pre -= 1
            self._gap()
        elif tag == "dt":
            self._flush()
            self.in_sig = False
        elif tag in ("p", "li") or tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self.skip_tag is not None:
            return
        self.cur.append(data if self.pre else data.replace("\xb6", ""))

    # -- result
    def text(self) -> str:
        self._flush()
        out, blank = [], True
        for line in self.lines:
            if line == "":
                if not blank:
                    out.append("")
                blank = True
            else:
                out.append(line)
                blank = False
        return "\n".join(out).strip()


def _span(value) -> int:
    try:
        return max(1, min(int(value), 64))
    except (TypeError, ValueError):
        return 1


def _place_cell(table: _Table, text: str, rowspan: int, colspan: int):
    row = table.row
    carried = table.spans
    while table.col in carried:
        remaining, carried_text = carried[table.col]
        row.append(carried_text)
        if remaining <= 1:
            del carried[table.col]
        else:
            carried[table.col] = (remaining - 1, carried_text)
        table.col += 1
    row.append(text)
    if rowspan > 1:
        carried[table.col] = (rowspan - 1, text)
    table.col += 1
    if colspan > 1:
        row.append(("\x00span", colspan))
        table.col += colspan - 1


def _finish_row(table: _Table):
    row, carried = table.row, table.spans
    table.row = None
    while table.col in carried:
        remaining, carried_text = carried[table.col]
        row.append(carried_text)
        if remaining <= 1:
            del carried[table.col]
        else:
            carried[table.col] = (remaining - 1, carried_text)
        table.col += 1
    cells = [c for c in row if not isinstance(c, tuple)]
    if not any(cells):
        return
    if len(cells) == 1 and len(row) > 1:
        table.rows.append("## " + cells[0])  # a cell spanning the whole row is a sub-heading
    else:
        table.rows.append(" | ".join(cells))


def _render(fragment: str, *, drop_nested_py: bool, keep_newlines: bool) -> str:
    renderer = _TextRenderer(drop_nested_py=drop_nested_py, keep_newlines=keep_newlines)
    renderer.feed(fragment)
    renderer.close()
    return renderer.text()


# ------------------------------------------------------------------ fragment extraction


def _matching_end(text: str, start: int, tag: str):
    """Index just past the closing tag that balances the ``<tag`` opening at ``start``."""
    pattern = re.compile(r"<(/?)%s\b[^>]*>" % tag, re.IGNORECASE)
    depth = 0
    for match in pattern.finditer(text, start):
        if match.group(1):
            depth -= 1
            if depth == 0:
                return match.end()
        elif not match.group(0).endswith("/>"):
            depth += 1
    return None


def _element_with_id(text: str, anchor: str):
    match = re.search(r'<([A-Za-z][A-Za-z0-9]*)\b[^>]*\sid="%s"' % re.escape(anchor), text)
    if match is None:
        raise ValueError("anchor %r not found in the installed documentation page" % anchor)
    return match.group(1).lower(), match.start()


def _article_section(text: str) -> str:
    body = text.find('itemprop="articleBody"')
    start = text.find("<section", max(body, 0))
    if start < 0:
        raise ValueError("documentation page has no article section")
    end = _matching_end(text, start, "section")
    return text[start:end] if end else text[start:]


def _extract(entry: _Entry, text: str):
    """Return ``(html_fragment, drop_nested_py)`` for one entry."""
    if entry.kind == "node":
        start = text.find('id="mc-main-content"')
        if start < 0:
            raise ValueError("node reference page has no main content")
        start = text.rfind("<div", 0, start)
        end = _matching_end(text, start, "div")
        return (text[start:end] if end else text[start:]), False
    if entry.kind in ("module", "guide"):
        return _article_section(text), True
    if entry.kind == "guide_section":
        tag, start = _element_with_id(text, entry.anchor)
        if tag != "section":  # an empty <span id> label sits inside the section it names
            start = text.rfind("<section", 0, start)
            if start < 0:
                raise ValueError("section %r has no content" % entry.anchor)
        end = _matching_end(text, start, "section")
        return (text[start:end] if end else text[start:]), True
    tag, start = _element_with_id(text, entry.anchor)
    if tag == "dt":
        start = text.rfind("<dl", 0, start)
        end = _matching_end(text, start, "dl")
        return (text[start:end] if end else text[start:]), entry.kind == "class"
    end = _matching_end(text, start, tag)
    return (text[start:end] if end else text[start : start + 20000]), False


# ------------------------------------------------------------------ public API


class ApiDocumentation:
    """Search/read facade over one installed Nuke ``Documentation`` directory."""

    def __init__(self, documentation_root):
        root = Path(documentation_root).expanduser()
        if not root.is_dir():
            raise FileNotFoundError("Nuke Documentation directory not found: %s" % root)
        self._root = root.resolve()
        self._pages: OrderedDict = OrderedDict()
        self._summaries: dict = {}
        self._lock = threading.Lock()

    @property
    def root(self) -> Path:
        return self._root

    # -- search
    def search(self, query: str, limit: int = DEFAULT_LIMIT) -> dict:
        text = _validate_query(query)
        limit = _validate_limit(limit)
        index = _cached_index(self._root)
        scores = _score(index, text)
        notes = self._inherited_members(index, text, scores)
        total = len(scores)
        top = heapq.nsmallest(
            limit, scores.items(), key=lambda item: (-item[1], index.entries[item[0]].name.count("."), index.entries[item[0]].name)
        )
        results = []
        for position, _score_value in top:
            entry = index.entries[position]
            results.append(
                {
                    "id": entry.id,
                    "title": entry.title,
                    "kind": entry.kind,
                    "summary": self._summary(entry),
                    "source_url": self._source_url(entry),
                    **({"note": notes[position]} if position in notes else {}),
                }
            )
        response = {
            "success": True,
            "query": text,
            "results": results,
            "total_matches": total,
            "version": index.version,
            "source": "installed %s" % (index.project or "Nuke documentation"),
        }
        if notes:
            response["inheritance"] = sorted(set(notes.values()))
        if not results:
            response["message"] = (
                "No installed Nuke %s documentation entry matches %r. The name may not exist in this "
                "version; check spelling and try the class, method or node name on its own."
                % (index.version or "", text)
            ) + _missing_member_hint(index, text)
        elif max(scores.values()) < _FALLBACK_CEILING:
            response["message"] = (
                "No documentation entry is named %r; these are the only names that start with or contain it."
                % text
            )
        elif total > len(results):
            response["message"] = "%d more matches; use a fuller name such as Class.method to narrow." % (total - len(results))
        return response

    def _inherited_members(self, index: _Index, query: str, scores: dict) -> dict:
        """Resolve ``Class.member`` queries the inventory does not list on ``Class`` itself.

        Walks the ``Bases:`` line of the installed class page and adds the base-class member
        with an explicit note; a member that no base documents is left unmatched.
        """
        notes: dict = {}
        for ident in dict.fromkeys(_IDENT.findall(query)):
            parts = ident.lower().split(".")
            if len(parts) < 2 or index.suffix.get(".".join(parts[-2:])):
                continue
            member, class_name = parts[-1], parts[-2]
            classes = [p for p in index.suffix.get(class_name, ()) if index.entries[p].kind == "class"]
            seen = set()
            queue = [(p, index.entries[p]) for p in classes]
            while queue and len(seen) < 24:
                _, klass = queue.pop(0)
                if klass.id in seen:
                    continue
                seen.add(klass.id)
                for base in self._bases(klass):
                    base_key = base.lower()
                    for position in index.suffix.get(base_key, ()):
                        base_entry = index.entries[position]
                        if base_entry.kind == "class" and base_entry.name.lower().split(".")[0] == klass.name.lower().split(".")[0]:
                            for hit in index.suffix.get("%s.%s" % (base_key, member), ()):
                                found = index.entries[hit]
                                if found.kind in ("method", "attribute", "property") and found.name.lower().startswith(
                                    base_entry.name.lower() + "."
                                ):
                                    scores[hit] = max(scores.get(hit, 0), 860)
                                    notes[hit] = "%s does not list %r itself; it is inherited from %s" % (
                                        klass.name,
                                        ident.rsplit(".", 1)[-1],
                                        base_entry.name,
                                    )
                            queue.append((position, base_entry))
        return notes

    def _bases(self, klass: _Entry) -> list:
        for line in self._render_entry(klass).split("\n")[:4]:
            if line.startswith("Bases:"):
                return [b.strip().rsplit(".", 1)[-1] for b in line[6:].split(",") if b.strip()]
        return []

    # -- read
    def read(self, doc_id: str) -> dict:
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError("doc_id must be a non-empty string")
        index = _cached_index(self._root)
        position = index.by_id.get(doc_id.strip())
        if position is None:
            raise ValueError(
                "Unknown documentation id %r. Use an id returned by search_nuke_api_docs." % doc_id[:120]
            )
        entry = index.entries[position]
        content = self._render_entry(entry)
        truncated = len(content) > MAX_CONTENT_CHARS
        if truncated:
            cut = content.rfind("\n", 0, MAX_CONTENT_CHARS)
            body = content[: cut if cut > MAX_CONTENT_CHARS // 2 else MAX_CONTENT_CHARS]
            content = "%s\n[truncated: %d of %d characters shown]" % (body, len(body), len(content))
        return {
            "success": True,
            "id": entry.id,
            "title": entry.title,
            "kind": entry.kind,
            "content": content,
            "source_url": self._source_url(entry),
            "source_path": entry.page,
            "version": index.version,
            "truncated": truncated,
        }

    # -- internals
    def _page_path(self, entry: _Entry) -> Path:
        base = _NODE_BASE if entry.kind == "node" else _PYTHON_BASE
        allowed = (self._root / base).resolve()
        path = (self._root / entry.page).resolve()
        if not path.is_relative_to(allowed) or path.suffix != ".html":
            raise ValueError("documentation page for %s is outside the installed documentation tree" % entry.id)
        if not path.is_file():
            raise FileNotFoundError("Installed documentation page missing: %s" % entry.page)
        return path

    def _source_url(self, entry: _Entry) -> str:
        url = (self._root / entry.page).resolve().as_uri()
        return "%s#%s" % (url, entry.anchor) if entry.anchor else url

    def _load_page(self, path: Path) -> str:
        key = str(path)
        stamp = path.stat().st_mtime_ns
        with self._lock:
            cached = self._pages.get(key)
            if cached is not None and cached[0] == stamp:
                self._pages.move_to_end(key)
                return cached[1]
        text = _read_bounded(path, _MAX_PAGE_BYTES).decode("utf-8", "replace")
        with self._lock:
            self._pages[key] = (stamp, text)
            self._pages.move_to_end(key)
            while len(self._pages) > _PAGE_CACHE_SIZE:
                self._pages.popitem(last=False)
        return text

    def _render_entry(self, entry: _Entry) -> str:
        text = self._load_page(self._page_path(entry))
        fragment, drop_nested = _extract(entry, text)
        rendered = _render(fragment, drop_nested_py=drop_nested, keep_newlines=entry.kind != "node")
        if not rendered:
            raise ValueError("documentation for %s rendered no text" % entry.id)
        return rendered

    def _summary(self, entry: _Entry) -> str:
        cached = self._summaries.get(entry.id)
        if cached is not None:
            return cached
        lines = [ln for ln in self._render_entry(entry).split("\n") if ln.strip()]
        if entry.kind == "node":
            summary = next((ln for ln in lines if not ln.startswith("#")), entry.title)
        elif entry.kind == "module":
            summary = "Module %s (%d lines of members and classes)" % (entry.name, len(lines))
        elif entry.kind in ("guide", "guide_section"):
            summary = next((ln for ln in lines[1:] if not ln.startswith(("#", "|"))), entry.title)
        else:
            signature = lines[0]
            description = next((ln for ln in lines[1:] if not ln.startswith(("Bases:", "Parameters", "Returns"))), "")
            summary = "%s - %s" % (signature, description) if description else signature
        summary = summary[: MAX_SUMMARY_CHARS - 3] + "..." if len(summary) > MAX_SUMMARY_CHARS else summary
        self._summaries[entry.id] = summary
        return summary


def _missing_member_hint(index: _Index, query: str) -> str:
    """When ``Class.member`` has no entry but ``Class`` does, say so: the member does not exist."""
    for ident in _IDENT.findall(query):
        parts = ident.lower().split(".")
        if len(parts) >= 2:
            for position in index.suffix.get(parts[-2], ()):
                entry = index.entries[position]
                if entry.kind == "class":
                    return " The class %s exists (id %s) but neither it nor its documented bases list %r; read it for its real members." % (
                        entry.name,
                        entry.id,
                        ident.rsplit(".", 1)[-1],
                    )
    return ""


def _score(index: _Index, query: str) -> dict:
    """Map entry position -> relevance for ``query``; empty when nothing really matches."""
    entries = index.entries
    scores: dict = {}

    def bump(position: int, base: int, bonus_name: str | None = None):
        entry = entries[position]
        value = base + _KIND_BONUS.get(entry.kind, 0) - 2 * entry.name.count(".")
        if bonus_name is not None and entry.name.endswith(bonus_name):
            value += 5  # case-exact spelling
        if value > scores.get(position, -1):
            scores[position] = value

    idents = _IDENT.findall(query)
    wanted = [i for i in idents if i.lower() not in _STOP_WORDS] or idents
    keys = list(wanted)
    for width in (2, 3):  # "XY_Knob setAnimated" -> "XY_Knob.setAnimated"
        if len(idents) > 1:
            keys.extend(".".join(idents[n : n + width]) for n in range(len(idents) - width + 1))
    for ident in dict.fromkeys(keys):
        lowered = ident.lower()
        parts = lowered.count(".") + 1
        for position in index.suffix.get(lowered, ()):
            entry = entries[position]
            if entry.name.lower() == lowered:
                # a dotted path ("nuke.createNode") is the invoked symbol; a bare word that equals a
                # top-level name ("Radial", often a call argument) must not outrank it
                base = 1000 if parts > 1 else 950
            elif parts > 1:
                base = 880 + 10 * parts
            else:
                base = 950 if entry.kind == "node" else 800
            bump(position, base, ident)

    qtokens = _tokens(query)
    core = [t for t in qtokens if t not in _STOP_WORDS] or qtokens
    if core and all(t in index.postings for t in core):
        candidates = None
        for token in sorted(core, key=lambda t: len(index.postings[t])):
            found = set(index.postings[token])
            candidates = found if candidates is None else candidates & found
            if not candidates:
                break
        qset = set(qtokens)
        for position in candidates or ():
            matched = len(qset & entries[position].tokens)
            bump(position, 400 + 30 * matched - 4 * (len(entries[position].tokens) - matched))
    if len(idents) > 1 and len(core) > 1:  # a node name among descriptive words ("Radial area knob")
        for token in core:
            for position in index.suffix.get(token, ()):
                if entries[position].kind == "node" and entries[position].name.lower() == token:
                    bump(position, 350)

    if not scores and len(idents) == 1 and len(idents[0]) >= 3 and "." not in idents[0]:
        needle = idents[0].lower()  # misspelled / partial single name: prefix, then substring
        for position, short in enumerate(index.shorts):
            if short.startswith(needle):
                bump(position, 250)
            elif needle in short:
                bump(position, 150)
    if scores and max(scores.values()) >= _EXACT_FLOOR:  # a real hit: drop loose token matches
        scores = {p: v for p, v in scores.items() if v >= _RELEVANT_FLOOR}
    return scores
