"""Read-only compositing knowledge index over the packaged Markdown corpus.

Pure standard library. The corpus is read through ``importlib.resources`` (never the
working directory), validated and indexed once per process. Edits to packaged
documents need a sidecar restart; there is deliberately no file watcher.

Every document starts with frontmatter of ``key: <JSON value>`` lines (see
``REQUIRED_FIELDS``). Callers address documents only by ID/title/alias through the
index; caller strings are never used to build paths.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import difflib
from functools import lru_cache
from importlib import resources
import json
import re

CONTENT_CAP = 6000
SOURCES_CAP = 1500
QUERY_CAP = 200
LIMIT_RANGE = (1, 8)
SUGGESTION_COUNT = 3

KINDS = ("router", "fundamental", "topic", "node")
SEARCH_KINDS = ("all", "topic", "fundamental", "node")
GUIDANCE_SECTIONS = ("overview", "workflow", "verify", "pitfalls", "full")
NODE_SECTIONS = ("overview", "inputs", "controls", "verify", "pitfalls", "full")

REQUIRED_FIELDS = {
    "id": str,
    "kind": str,
    "title": str,
    "category": str,
    "summary": str,
    "aliases": list,
    "tags": list,
    "requires": list,
    "related": list,
    "nodes": list,
    "version": str,
    "source_ids": list,
}
ROUTER_EXTRA_FIELDS = ("name", "description")
LIST_FIELDS = ("aliases", "tags", "requires", "related", "nodes", "source_ids")
SUMMARY_CAP = 300

# Section headings every document of a kind must have (lowercase).
REQUIRED_SECTIONS = {
    "router": (),
    "fundamental": ("applicability", "workflow", "verify", "pitfalls", "sources"),
    "topic": ("applicability", "workflow", "verify", "pitfalls", "sources"),
    "node": ("purpose", "inputs", "controls", "verify", "pitfalls", "sources"),
}
KIND_DIRECTORIES = {"fundamental": "fundamentals", "topic": "topics", "node": "nodes"}

_STOPWORDS = frozenset(
    "a an and are as at be by do does for from how i in is it of on or the to use using "
    "vs versus what when with my should can".split()
)

# Query-term expansion (stemmed keys) so task wording reaches native node documents.
_SYNONYMS = {
    "circle": ("ellipse", "roto", "shape"),
    "ellipse": ("roto", "shape"),
    "matte": ("alpha", "mask", "roto"),
    "mask": ("matte", "roto", "alpha"),
    "rotoscoping": ("roto",),
    "rotoscope": ("roto",),
    "paint": ("rotopaint",),
    "clone": ("rotopaint",),
    "checker": ("checkerboard",),
    "chessboard": ("checkerboard",),
    "chequerboard": ("checkerboard",),
    "keying": ("keyer", "key"),
    "chroma": ("keyer", "keylight", "greenscreen"),
    "greenscreen": ("keylight", "chroma", "keyer"),
    "bluescreen": ("keylight", "chroma", "keyer"),
    "luma": ("luminance", "keyer"),
    "combine": ("merge",),
    "blend": ("merge", "mix"),
    "composite": ("merge",),
    "over": ("merge",),
    "mix": ("keymix", "addmix"),
    "concatenation": ("concatenate", "filtering", "transform", "resample"),
    "concatenate": ("concatenation", "filtering", "transform", "resample"),
    "resample": ("filtering", "concatenation"),
    "projection": ("project3d", "camera", "project"),
    "retime": ("timewarp", "kronos", "optical", "flow"),
    "retiming": ("timewarp", "kronos", "optical", "flow"),
    "slowmo": ("kronos", "optical", "flow", "retime"),
    "motionblur": ("vectorblur",),
    "dof": ("zdefocus", "defocus", "depth", "field"),
    "track": ("tracker",),
    "stabilize": ("tracker", "stabilise"),
    "corner": ("cornerpin",),
    "pointcloud": ("point", "cloud"),
    "mesh": ("poissonmesh", "geometry"),
    "aov": ("multipass", "channels"),
    "premultiplied": ("premult", "unpremult", "alpha"),
    "colorspace": ("ocio", "color", "space"),
    "distortion": ("lensdistortion", "undistort"),
    "undistort": ("lensdistortion", "distortion"),
    "particle": ("particleemitter",),
    "image": ("read",),
}


class KnowledgeError(ValueError):
    """Bad request (unknown ID, invalid argument). Message is safe to show to a model."""


class CorpusError(RuntimeError):
    """The packaged corpus is malformed; message names the offending document."""


@dataclass(frozen=True)
class Document:
    id: str
    kind: str
    title: str
    category: str
    summary: str
    aliases: tuple[str, ...]
    tags: tuple[str, ...]
    requires: tuple[str, ...]
    related: tuple[str, ...]
    nodes: tuple[str, ...]
    version: str
    source_ids: tuple[str, ...]
    intro: str
    sections: dict[str, str]  # lowercase heading -> chunk including its heading line
    body: str
    title_tokens: frozenset[str] = field(repr=False, default=frozenset())
    alias_tokens: frozenset[str] = field(repr=False, default=frozenset())
    node_tokens: frozenset[str] = field(repr=False, default=frozenset())
    tag_tokens: frozenset[str] = field(repr=False, default=frozenset())
    summary_tokens: frozenset[str] = field(repr=False, default=frozenset())
    body_tokens: frozenset[str] = field(repr=False, default=frozenset())


def _stem(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokens(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", text.lower())]


def _token_set(*texts: str) -> frozenset[str]:
    return frozenset(t for text in texts for t in _tokens(text))


def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _parse_frontmatter(text: str, where: str) -> tuple[dict, str]:
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        raise CorpusError("%s: missing frontmatter" % where)
    meta: dict = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "\n".join(lines[index + 1 :]).strip("\n")
        if not line.strip():
            continue
        key, separator, raw = line.partition(":")
        if not separator or not key.strip().isidentifier():
            raise CorpusError("%s: bad frontmatter line %r" % (where, line))
        if key in meta:
            raise CorpusError("%s: duplicate frontmatter key %r" % (where, key))
        try:
            meta[key] = json.loads(raw.strip())
        except json.JSONDecodeError as exc:
            raise CorpusError("%s: frontmatter %r is not valid JSON (%s)" % (where, key, exc.msg))
    raise CorpusError("%s: frontmatter is not closed" % where)


def _split_sections(body: str, where: str) -> tuple[str, dict[str, str]]:
    """Split on ``## `` headings (ignoring fenced code). Returns (intro, sections)."""
    intro: list[str] = []
    sections: dict[str, list[str]] = {}
    current = intro
    in_fence = False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            name = line[3:].strip().lower()
            if name in sections:
                raise CorpusError("%s: duplicate section %r" % (where, name))
            current = sections.setdefault(name, [])
            continue  # the heading is re-added once when chunks are built
        elif not in_fence and line.startswith("# ") and current is intro:
            continue  # the H1 title is already in metadata
        current.append(line)
    chunks = {
        name: "## %s\n%s" % (name.capitalize(), "\n".join(lines).strip("\n"))
        for name, lines in sections.items()
    }
    return "\n".join(intro).strip(), chunks


def _parse_document(text: str, relative: str) -> Document:
    meta, body = _parse_frontmatter(text, relative)
    expected = set(REQUIRED_FIELDS)
    if meta.get("kind") == "router":
        expected |= set(ROUTER_EXTRA_FIELDS)
    missing = expected - set(meta)
    extra = set(meta) - expected
    if missing or extra:
        raise CorpusError(
            "%s: frontmatter fields missing=%s unexpected=%s"
            % (relative, sorted(missing), sorted(extra))
        )
    for name, kind in {**REQUIRED_FIELDS, **{f: str for f in ROUTER_EXTRA_FIELDS}}.items():
        if name in meta and not isinstance(meta[name], kind):
            raise CorpusError("%s: field %r must be %s" % (relative, name, kind.__name__))
    for name in LIST_FIELDS:
        if not all(isinstance(item, str) and item for item in meta[name]):
            raise CorpusError("%s: field %r must be a list of non-empty strings" % (relative, name))
    kind = meta["kind"]
    if kind not in KINDS:
        raise CorpusError("%s: unknown kind %r" % (relative, kind))
    stem = relative[: -len(".md")]
    expected_id = "overview" if relative == "SKILL.md" else stem
    if (kind == "router") != (relative == "SKILL.md"):
        raise CorpusError("%s: only SKILL.md may be kind router" % relative)
    if meta["id"] != expected_id:
        raise CorpusError("%s: id %r must equal %r" % (relative, meta["id"], expected_id))
    if kind != "router" and KIND_DIRECTORIES[kind] != stem.split("/")[0]:
        raise CorpusError("%s: kind %r does not match its directory" % (relative, kind))
    if not meta["title"].strip() or not meta["summary"].strip():
        raise CorpusError("%s: title and summary must be non-empty" % relative)
    if len(meta["summary"]) > SUMMARY_CAP:
        raise CorpusError("%s: summary exceeds %d characters" % (relative, SUMMARY_CAP))

    intro, sections = _split_sections(body, relative)
    absent = [s for s in REQUIRED_SECTIONS[kind] if s not in sections]
    if absent:
        raise CorpusError("%s: missing required sections %s" % (relative, absent))
    title, aliases, nodes = meta["title"], meta["aliases"], meta["nodes"]
    return Document(
        id=meta["id"],
        kind=kind,
        title=title,
        category=meta["category"],
        summary=meta["summary"],
        aliases=tuple(aliases),
        tags=tuple(meta["tags"]),
        requires=tuple(meta["requires"]),
        related=tuple(meta["related"]),
        nodes=tuple(nodes),
        version=meta["version"],
        source_ids=tuple(meta["source_ids"]),
        intro=intro,
        sections=sections,
        body=body,
        title_tokens=_token_set(title),
        alias_tokens=_token_set(*aliases),
        node_tokens=_token_set(*nodes),
        tag_tokens=_token_set(*meta["tags"]),
        summary_tokens=_token_set(meta["summary"]),
        body_tokens=_token_set(body),
    )


def _iter_markdown(root) -> list[tuple[str, object]]:
    """(relative path, Traversable) for SKILL.md and the flat kind directories, sorted."""
    found = []
    router = root.joinpath("SKILL.md")
    if router.is_file():
        found.append(("SKILL.md", router))
    for directory in KIND_DIRECTORIES.values():
        folder = root.joinpath(directory)
        if not folder.is_dir():
            continue
        for entry in sorted(folder.iterdir(), key=lambda e: e.name):
            if entry.is_file() and entry.name.endswith(".md"):
                found.append(("%s/%s" % (directory, entry.name), entry))
    return found


def _load_sources(root) -> dict[str, dict]:
    path = root.joinpath("sources", "catalog.json")
    if not path.is_file():
        raise CorpusError("sources/catalog.json is missing")
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusError("sources/catalog.json is not valid JSON (%s)" % exc.msg)
    if not isinstance(catalog, dict) or not all(isinstance(v, dict) for v in catalog.values()):
        raise CorpusError("sources/catalog.json must map source IDs to objects")
    return catalog


class KnowledgeBase:
    """Validated, immutable index over a corpus root (a Path or importlib Traversable)."""

    def __init__(self, root):
        self.sources = _load_sources(root)
        self.documents: dict[str, Document] = {}
        for relative, entry in _iter_markdown(root):
            document = _parse_document(entry.read_text(encoding="utf-8"), relative)
            if document.id in self.documents:
                raise CorpusError("duplicate document id %r" % document.id)
            self.documents[document.id] = document
        if not self.documents:
            raise CorpusError("corpus contains no documents")
        self._validate_references()
        self._node_keys: dict[str, set[str]] = {}
        for document in self.documents.values():
            if document.kind == "node":
                names = [document.id.split("/", 1)[1], document.title, *document.aliases]
                for name in names:
                    self._node_keys.setdefault(_normalize_key(name), set()).add(document.id)

    def _validate_references(self) -> None:
        for document in self.documents.values():
            for name in ("requires", "related"):
                for target in getattr(document, name):
                    if target not in self.documents:
                        raise CorpusError("%s: %s references unknown id %r" % (document.id, name, target))
            for source in document.source_ids:
                if source not in self.sources:
                    raise CorpusError("%s: unknown source id %r" % (document.id, source))

    # ---- search -------------------------------------------------------------------

    def search(self, query, limit=3, kind="all") -> dict:
        if not isinstance(query, str) or not query.strip():
            raise KnowledgeError("query must be a non-empty string")
        if len(query) > QUERY_CAP:
            raise KnowledgeError("query is longer than %d characters" % QUERY_CAP)
        if "\x00" in query or ".." in query:
            raise KnowledgeError("query contains invalid characters")
        if isinstance(limit, bool) or not isinstance(limit, int) or not LIMIT_RANGE[0] <= limit <= LIMIT_RANGE[1]:
            raise KnowledgeError("limit must be an integer from %d to %d" % LIMIT_RANGE)
        if kind not in SEARCH_KINDS:
            raise KnowledgeError("kind must be one of %s" % ", ".join(SEARCH_KINDS))

        terms = self._query_terms(query)
        phrase = _normalize_key(query)
        scored = []
        for document in self.documents.values():
            if document.kind == "router" or kind not in ("all", document.kind):
                continue
            score = self._score(document, terms, phrase)
            if score > 0:
                scored.append((-score, document.id, document))
        scored.sort(key=lambda item: item[:2])
        return {
            "query": query.strip(),
            "matches": [
                {
                    "id": d.id,
                    "title": d.title,
                    "kind": d.kind,
                    "summary": d.summary,
                    "requires": list(d.requires),
                    "version": d.version,
                }
                for _, _, d in scored[:limit]
            ],
        }

    @staticmethod
    def _query_terms(query: str) -> dict[str, float]:
        """Weighted stemmed terms: the query itself, joined neighbours, then synonyms."""
        base = [t for t in _tokens(query) if t not in _STOPWORDS]
        terms: dict[str, float] = {t: 1.0 for t in base}
        for left, right in zip(base, base[1:]):
            terms.setdefault(left + right, 1.0)  # "key mix" -> keymix
        for term in list(terms):
            for synonym in _SYNONYMS.get(term, ()):
                terms.setdefault(_stem(synonym), 0.5)
        return terms

    @staticmethod
    def _score(document: Document, terms: dict[str, float], phrase: str) -> float:
        score = 0.0
        for term, weight in terms.items():
            for tokens, points in (
                (document.title_tokens, 6),
                (document.alias_tokens, 5),
                (document.node_tokens, 5),
                (document.tag_tokens, 4),
                (document.summary_tokens, 2),
                (document.body_tokens, 1),
            ):
                if term in tokens:
                    score += points * weight
        if score:
            names = [document.id.rsplit("/", 1)[-1], document.title, *document.aliases]
            for name in names:
                key = _normalize_key(name)
                if key and key == phrase:
                    score += 20
                elif len(key) > 3 and key in phrase:
                    score += 8
        return score

    # ---- retrieval ----------------------------------------------------------------

    def get_guidance(self, topic_id, section="overview") -> dict:
        if section not in GUIDANCE_SECTIONS:
            raise KnowledgeError("section must be one of %s" % ", ".join(GUIDANCE_SECTIONS))
        document = self._lookup_id(topic_id)
        if document.kind == "node":
            raise KnowledgeError(
                "%r is a node reference; use get_node_reference(node=%r)" % (document.id, document.title)
            )
        return self._render(document, section)

    def get_node_reference(self, node, section="overview") -> dict:
        if section not in NODE_SECTIONS:
            raise KnowledgeError("section must be one of %s" % ", ".join(NODE_SECTIONS))
        document = self._resolve_node(node)
        result = self._render(document, section)
        result["runtime_verified"] = False
        return result

    def _lookup_id(self, value) -> Document:
        if not isinstance(value, str) or not value.strip():
            raise KnowledgeError("topic_id must be a non-empty string")
        value = value.strip()
        if len(value) > 100 or "\x00" in value or "\\" in value or ".." in value or value.startswith("/"):
            raise KnowledgeError("invalid topic_id %r" % value[:100])
        document = self.documents.get(value)
        if document is None:
            raise KnowledgeError(self._unknown("topic_id", value, [i for i, d in self.documents.items() if d.kind != "node"]))
        return document

    def _resolve_node(self, value) -> Document:
        if not isinstance(value, str) or not value.strip():
            raise KnowledgeError("node must be a non-empty string")
        value = value.strip()
        if len(value) > 100 or "\x00" in value or "\\" in value or ".." in value or value.startswith("/"):
            raise KnowledgeError("invalid node %r" % value[:100])
        if value.lower().startswith("nodes/"):
            document = self.documents.get(value)
            if document is None or document.kind != "node":
                known = sorted(i for i, d in self.documents.items() if d.kind == "node")
                close = difflib.get_close_matches(value, known, n=SUGGESTION_COUNT, cutoff=0.6)
                hint = "; did you mean: %s" % ", ".join(close) if close else ""
                raise KnowledgeError("unknown node id %r%s" % (value, hint))
            return document
        key = _normalize_key(value)
        for candidate in (key, key[: -len("node")] if key.endswith("node") else None):
            ids = self._node_keys.get(candidate) if candidate else None
            if ids and len(ids) > 1:
                raise KnowledgeError(
                    "node %r is ambiguous; use an explicit id: %s" % (value, ", ".join(sorted(ids)))
                )
            if ids:
                return self.documents[next(iter(ids))]
        names = {}
        for node_key, ids in self._node_keys.items():
            for doc_id in ids:
                names[node_key] = self.documents[doc_id].title
        close = difflib.get_close_matches(key, list(names), n=SUGGESTION_COUNT, cutoff=0.6)
        hint = "; did you mean: %s" % ", ".join(dict.fromkeys(names[k] for k in close)) if close else ""
        raise KnowledgeError("no node reference for %r%s" % (value, hint))

    def _unknown(self, label: str, value: str, ids: list[str]) -> str:
        stems = {i.rsplit("/", 1)[-1]: i for i in ids}
        close = difflib.get_close_matches(value.rsplit("/", 1)[-1], list(stems), n=SUGGESTION_COUNT, cutoff=0.5)
        suggestions = [stems[c] for c in close]
        if len(suggestions) < SUGGESTION_COUNT:
            hits = self.search(value.replace("/", " ").replace("-", " "), limit=SUGGESTION_COUNT)["matches"]
            for hit in hits:
                if hit["kind"] != "node" and hit["id"] not in suggestions:
                    suggestions.append(hit["id"])
        suggestions = suggestions[:SUGGESTION_COUNT]
        hint = "; closest: %s" % ", ".join(suggestions) if suggestions else "; use search_compositing_knowledge"
        return "unknown %s %r%s" % (label, value, hint)

    def _render(self, document: Document, section: str) -> dict:
        is_node = document.kind == "node"
        available = ["overview", "full"]
        if document.kind != "router":
            allowed = NODE_SECTIONS if is_node else GUIDANCE_SECTIONS
            available = [s for s in allowed if s in ("overview", "full") or s in document.sections]
        if section not in available:
            raise KnowledgeError(
                "%s has no %r section; available: %s" % (document.id, section, ", ".join(available))
            )

        if section == "full" or document.kind == "router":
            main = "\n\n".join(
                [document.intro] * bool(document.intro)
                + [c for name, c in document.sections.items() if name != "sources"]
            )
        elif section == "overview":
            if is_node:
                main = document.sections["purpose"]
            else:
                main = "\n\n".join(
                    [document.intro] * bool(document.intro) + [document.sections["applicability"]]
                )
        else:
            main = document.sections[section]
        main = main.strip()

        sources_text = document.sections["sources"] if "sources" in document.sections else ""
        truncated = False
        if len(sources_text) > SOURCES_CAP:
            sources_text, truncated = sources_text[:SOURCES_CAP].rstrip() + "\n[truncated]", True
        budget = CONTENT_CAP - len(sources_text) - 2
        marker = "\n[truncated]"
        if len(main) > budget:
            cut = main[: budget - len(marker)]
            main = (cut.rsplit("\n", 1)[0] if "\n" in cut else cut).rstrip() + marker
            truncated = True
        content = main + ("\n\n" + sources_text if sources_text else "")

        return {
            "id": document.id,
            "title": document.title,
            "kind": document.kind,
            "section": section,
            "content": content,
            "truncated": truncated,
            "available_sections": available,
            "requires": list(document.requires),
            "related": list(document.related),
            "nodes": list(document.nodes),
            "version": document.version,
            "sources": [{"id": s, **self.sources[s]} for s in document.source_ids],
        }


@lru_cache(maxsize=1)
def default_knowledge() -> KnowledgeBase:
    """Packaged corpus, loaded and validated once per process (restart to pick up edits)."""
    return KnowledgeBase(resources.files("nuke_codex_panel.knowledge"))


def search_compositing_knowledge(query, limit=3, kind="all") -> dict:
    return default_knowledge().search(query, limit, kind)


def get_compositing_guidance(topic_id, section="overview") -> dict:
    return default_knowledge().get_guidance(topic_id, section)


def get_node_reference(node, section="overview") -> dict:
    return default_knowledge().get_node_reference(node, section)
