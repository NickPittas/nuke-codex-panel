import json

import pytest

from nuke_codex_panel.knowledge import library
from nuke_codex_panel.knowledge.library import CorpusError, KnowledgeBase, KnowledgeError


# ---- synthetic corpus: retrieval mechanics and corpus validation ------------------------


def doc(kind, doc_id, title, *, aliases=(), tags=(), requires=(), nodes=(), summary="Short.", body=None,
        sources=("foundry-17.1",), extra=""):
    fields = {
        "id": doc_id, "kind": kind, "title": title, "category": "test", "summary": summary,
        "aliases": list(aliases), "tags": list(tags), "requires": list(requires), "related": [],
        "nodes": list(nodes), "version": "Nuke 17.1 documentation", "source_ids": list(sources),
    }
    head = "\n".join("%s: %s" % (k, json.dumps(v)) for k, v in fields.items()) + extra
    if body is None:
        names = ("Purpose", "Inputs", "Controls") if kind == "node" else ("Applicability", "Workflow")
        names += ("Verify", "Pitfalls", "Sources")
        body = "# %s\nIntro text.\n\n" % title + "\n\n".join("## %s\n%s text." % (n, n) for n in names)
    return "---\n%s\n---\n%s\n" % (head, body)


def build(tmp_path, files):
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "sources" / "catalog.json").write_text(
        json.dumps({"foundry-17.1": {"title": "Foundry docs", "type": "docs"}}), encoding="utf-8"
    )
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return KnowledgeBase(tmp_path)


@pytest.fixture
def kb(tmp_path):
    return build(tmp_path, {
        "fundamentals/alpha.md": doc("fundamental", "fundamentals/alpha", "Alpha and premultiplication"),
        "topics/keys.md": doc(
            "topic", "topics/keys", "Mixing keys", aliases=["key mix"], requires=["fundamentals/alpha"],
            nodes=["Keymix"], body=(
                "# Mixing keys\nIntro.\n\n## Applicability\nUse it.\n\n## Workflow\n" + "word " * 2000 +
                "\n\n## Verify\nCheck.\n\n## Pitfalls\nBad.\n\n## Sources\nhttps://example.test/keys"
            ),
        ),
        "nodes/roto.md": doc("node", "nodes/roto", "Roto", aliases=["Roto node", "bezier shapes"], nodes=["Roto"]),
        "nodes/rotopaint.md": doc("node", "nodes/rotopaint", "RotoPaint", nodes=["RotoPaint"]),
        "nodes/keymix.md": doc("node", "nodes/keymix", "Keymix", tags=["mask"], nodes=["Keymix"]),
    })


def test_search_ranks_native_node_for_task_wording(kb):
    top = kb.search("roto circle", limit=3)["matches"]
    assert top[0]["id"] == "nodes/roto"
    assert set(top[0]) == {"id", "title", "kind", "summary", "requires", "version"}


def test_search_joins_split_node_names_and_filters_kind(kb):
    assert kb.search("key mix", kind="topic")["matches"][0]["id"] == "topics/keys"
    assert {m["kind"] for m in kb.search("roto", kind="node", limit=8)["matches"]} == {"node"}
    assert kb.search("zzzz nothing")["matches"] == []


@pytest.mark.parametrize("kwargs", [
    {"query": ""}, {"query": "  "}, {"query": "x" * 201}, {"query": "../../etc/passwd"},
    {"query": "roto", "limit": 0}, {"query": "roto", "limit": 9}, {"query": "roto", "limit": True},
    {"query": "roto", "kind": "router"}, {"query": 5},
])
def test_search_rejects_invalid_arguments(kb, kwargs):
    with pytest.raises(KnowledgeError):
        kb.search(**kwargs)


def test_guidance_returns_chosen_section_with_provenance_and_no_prerequisite_text(kb):
    result = kb.get_guidance("topics/keys", "verify")
    assert "Check." in result["content"] and "Intro" not in result["content"]
    assert "https://example.test/keys" in result["content"]
    assert result["requires"] == ["fundamentals/alpha"]
    assert "Alpha" not in result["content"]
    assert result["sources"][0]["id"] == "foundry-17.1"
    assert set(result["available_sections"]) >= {"overview", "workflow", "verify", "pitfalls", "full"}


def test_overview_is_intro_plus_applicability(kb):
    content = kb.get_guidance("topics/keys")["content"]
    assert "Intro." in content and "Use it." in content and "Check." not in content


def test_each_section_heading_appears_once(kb):
    assert kb.get_guidance("topics/keys", "verify")["content"].count("## Verify") == 1
    assert kb.get_guidance("topics/keys")["content"].count("## Applicability") == 1
    full = kb.get_guidance("fundamentals/alpha", "full")["content"]
    for heading in ("Applicability", "Workflow", "Verify", "Pitfalls", "Sources"):
        assert full.count("## %s\n" % heading) == 1
    assert kb.get_node_reference("roto", "inputs")["content"].count("## Inputs") == 1


def test_node_lookup_rejects_absolute_path_like_input(kb):
    with pytest.raises(KnowledgeError):
        kb.get_node_reference("/Roto")


def test_explicit_node_id_wins_over_alias_collision(tmp_path):
    kb = build(tmp_path, {
        "nodes/a.md": doc("node", "nodes/a", "Alpha Node"),
        "nodes/b.md": doc("node", "nodes/b", "Beta Node", aliases=["a"]),
    })
    with pytest.raises(KnowledgeError, match="ambiguous"):
        kb.get_node_reference("a")
    assert kb.get_node_reference("nodes/a")["id"] == "nodes/a"
    assert kb.get_node_reference("nodes/b")["id"] == "nodes/b"
    with pytest.raises(KnowledgeError, match="unknown node id"):
        kb.get_node_reference("nodes/missing")


def test_name_ending_in_node_resolves_exact_name_before_suffix_fallback(tmp_path):
    kb = build(tmp_path, {
        "nodes/gizmo.md": doc("node", "nodes/gizmo", "Gizmo"),
        "nodes/gizmonode.md": doc("node", "nodes/gizmonode", "GizmoNode"),
    })
    assert kb.get_node_reference("GizmoNode")["id"] == "nodes/gizmonode"
    assert kb.get_node_reference("Gizmo node")["id"] == "nodes/gizmonode"


def test_router_content_lists_sources_once(tmp_path):
    router = doc("router", "overview", "Router", body="# Router\nRoute here.\n\n## Use\nGo.\n\n## Sources\nhttps://example.test/r",
                 extra='\nname: "nuke-compositing"\ndescription: "Routes."')
    kb = build(tmp_path, {"SKILL.md": router})
    for section in ("overview", "full"):
        content = kb.get_guidance("overview", section)["content"]
        assert content.count("https://example.test/r") == 1 and "Go." in content


def test_oversize_section_is_truncated_but_keeps_sources(kb):
    for section in ("workflow", "full"):
        result = kb.get_guidance("topics/keys", section)
        assert result["truncated"] is True
        assert len(result["content"]) <= library.CONTENT_CAP
        assert result["content"].rstrip().endswith("https://example.test/keys")


@pytest.mark.parametrize("bad", ["../topics/keys", "/topics/keys", "topics\\keys", "topics/nope", ""])
def test_guidance_rejects_paths_and_unknown_ids(kb, bad):
    with pytest.raises(KnowledgeError):
        kb.get_guidance(bad)


def test_near_miss_id_suggests_the_real_document(kb):
    with pytest.raises(KnowledgeError, match="topics/keys"):
        kb.get_guidance("topics/kyes")


def test_guidance_refuses_node_ids_and_unknown_sections(kb):
    with pytest.raises(KnowledgeError, match="get_node_reference"):
        kb.get_guidance("nodes/roto")
    with pytest.raises(KnowledgeError):
        kb.get_guidance("topics/keys", "controls")


def test_node_reference_resolves_id_title_alias_and_is_unverified(kb):
    for name in ("Roto", "roto", "nodes/roto", "Roto node", "bezier shapes"):
        result = kb.get_node_reference(name)
        assert result["id"] == "nodes/roto"
        assert result["runtime_verified"] is False
        assert "Purpose text." in result["content"] and "Inputs text." not in result["content"]
    assert "Inputs text." in kb.get_node_reference("roto", "inputs")["content"]


def test_documents_merely_referencing_a_node_do_not_hijack_its_lookup(kb):
    # topics/keys lists Keymix in `nodes` but is not the Keymix reference.
    assert kb.get_node_reference("Keymix")["id"] == "nodes/keymix"


def test_unknown_node_fails_clearly_without_fallback(kb):
    with pytest.raises(KnowledgeError, match="RotoPaint"):
        kb.get_node_reference("RotoPaintt")
    with pytest.raises(KnowledgeError, match="no node reference"):
        kb.get_node_reference("Frobnicate")


def test_ambiguous_node_alias_is_reported(tmp_path):
    kb = build(tmp_path, {
        "nodes/a.md": doc("node", "nodes/a", "Alpha Node", aliases=["shared"]),
        "nodes/b.md": doc("node", "nodes/b", "Beta Node", aliases=["shared"]),
    })
    with pytest.raises(KnowledgeError, match="ambiguous"):
        kb.get_node_reference("shared")


# ---- malformed corpus boundaries -------------------------------------------------------


def corrupt(tmp_path, text, relative="topics/bad.md"):
    return build(tmp_path, {relative: text})


def test_corpus_rejects_malformed_metadata(tmp_path):
    good = doc("topic", "topics/bad", "Bad")
    cases = {
        "no frontmatter": "# Bad\n",
        "invalid json": good.replace('"test"', "test", 1),
        "id mismatch": good.replace('"topics/bad"', '"topics/other"', 1),
        "unknown field": good.replace("\n---\n", '\nextra: "x"\n---\n', 1),
        "kind mismatch": good.replace('"topic"', '"node"', 1),
        "long summary": doc("topic", "topics/bad", "Bad", summary="x" * 301),
        "missing section": good.replace("## Pitfalls", "## Other"),
        "duplicate section": good + "\n## Verify\nagain\n",
        "dangling requires": doc("topic", "topics/bad", "Bad", requires=["topics/missing"]),
        "unknown source": doc("topic", "topics/bad", "Bad", sources=("nobody",)),
    }
    for label, text in cases.items():
        sub = tmp_path / label.replace(" ", "_")
        sub.mkdir()
        with pytest.raises(CorpusError):
            corrupt(sub, text)


def test_new_well_formed_document_is_indexed_without_code_changes(tmp_path):
    kb = build(tmp_path, {"topics/new-idea.md": doc("topic", "topics/new-idea", "Brand new idea", tags=["zebra"])})
    assert kb.search("zebra")["matches"][0]["id"] == "topics/new-idea"


# ---- packaged corpus: what a model would actually ask ----------------------------------


@pytest.fixture(scope="module")
def packaged():
    return library.default_knowledge()


def top_ids(packaged, query, limit=3):
    return [m["id"] for m in packaged.search(query, limit=limit)["matches"]]


@pytest.mark.parametrize("query, expected", [
    ("make a circle matte with roto", "nodes/roto"),
    ("checkerboard test pattern instead of expression", "nodes/checkerboard"),
    ("combine two keys with keymix", "nodes/keymix"),
    ("addmix versus keymix", "topics/addmix-keymix"),
    ("why transforms concatenation resample", "fundamentals/filtering-concatenation"),
    ("camera projection onto geometry", "topics/camera-projection"),
    ("retime clip with optical flow", "topics/optical-flow-retiming"),
])
def test_packaged_search_finds_expected_document(packaged, query, expected):
    assert expected in top_ids(packaged, query)


def test_packaged_node_reference_is_static_version_aware(packaged):
    result = packaged.get_node_reference("Roto")
    assert result["runtime_verified"] is False
    assert "17.1" in result["version"]
    assert len(result["content"]) <= library.CONTENT_CAP


@pytest.mark.parametrize("query, expected", [
    ("organize node graph with B pipe trunk and A branches", "fundamentals/graph-conventions"),
    ("assemble key matte with ChannelMerge and copy alpha back to clean RGB", "fundamentals/keying-conventions"),
    ("reuse one Read with PostageStamp or Dot instead of duplicate Reads", "fundamentals/graph-conventions"),
    ("root format bbox out of memory roto jitter preflight", "fundamentals/quality-safeguards"),
])
def test_packaged_search_finds_teacher_conventions(packaged, query, expected):
    assert expected in top_ids(packaged, query)


@pytest.mark.parametrize("doc_id", [
    "fundamentals/graph-conventions",
    "fundamentals/keying-conventions",
    "fundamentals/quality-safeguards",
])
def test_teacher_conventions_are_policy_with_provenance(packaged, doc_id):
    result = packaged.get_guidance(doc_id, "full")
    assert result["id"] == doc_id
    assert "studio-conventions" in {s["id"] for s in result["sources"]}
    assert "Sources" in result["content"]
    assert len(result["content"]) <= library.CONTENT_CAP


def test_channelmerge_node_reference_resolves_statically(packaged):
    result = packaged.get_node_reference("ChannelMerge")
    assert result["id"] == "nodes/channelmerge"
    assert result["runtime_verified"] is False

