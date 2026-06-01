"""Unit tests for the v0+ Compiler."""

from __future__ import annotations

from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
    ConversationStateV0Plus,
    ExplicitRejection,
    HardFilter,
    MentionedEntity,
    TrackFeedback,
)
from mcrs.qu_modules.compiler_v0plus import (
    BranchPool,
    CompileResult,
    CompilerConfig,
    DenseBranch,
    V0PlusCompiler,
)
from mcrs.qu_modules.fuzzy_matcher import RapidfuzzCatalogMatcher
from mcrs.qu_modules.resolver_v0plus import V0PlusResolver
from tests.v0plus_fakes import DictCatalog, FakeEmbeddingClient, FakeRetriever


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


def _catalog() -> DictCatalog:
    return DictCatalog(
        tracks={
            "t-morphine-1": {
                "artist_id": "a-morphine",
                "artist_name": "Morphine",
                "track_name": "Cure for Pain",
                "tag_list": ["smoky", "lounge"],
                "popularity": 70.0,
                "release_date": "1993-09-14",
                "metadata_vector": [1.0, 0.0, 0.0],
            },
            "t-morphine-2": {
                "artist_id": "a-morphine",
                "artist_name": "Morphine",
                "track_name": "Buena",
                "tag_list": ["smoky", "lounge", "heavy"],
                "popularity": 55.0,
                "release_date": "1995-02-21",
                "metadata_vector": [0.9, 0.1, 0.0],
            },
            "t-fugazi-1": {
                "artist_id": "a-fugazi",
                "artist_name": "Fugazi",
                "track_name": "Waiting Room",
                "tag_list": ["post-hardcore", "punk"],
                "popularity": 80.0,
                "release_date": "1988-11-04",
                "metadata_vector": [0.0, 1.0, 0.0],
            },
            "t-fugazi-2": {
                "artist_id": "a-fugazi",
                "artist_name": "Fugazi",
                "track_name": "Repeater",
                "tag_list": ["post-hardcore"],
                "popularity": 60.0,
                "release_date": "1990-04-19",
                "metadata_vector": [0.0, 0.95, 0.05],
            },
            "t-tomwaits-1": {
                "artist_id": "a-tomwaits",
                "artist_name": "Tom Waits",
                "track_name": "Hold On",
                "tag_list": ["smoky", "heavy", "blues"],
                "popularity": 90.0,
                "release_date": "1999-04-26",
                "metadata_vector": [0.5, 0.5, 0.0],
            },
            "t-filler-1": {
                "artist_id": "a-filler",
                "artist_name": "Filler Artist",
                "track_name": "Filler Track One",
                "tag_list": ["pop"],
                "popularity": 100.0,  # highest popularity for backfill
                "release_date": "2010-01-01",
                "metadata_vector": [0.0, 0.0, 1.0],
            },
        }
    )


def _fake_encoder():
    """Fresh FakeEmbeddingClient per test. Returns a fixed vector; tests
    assert on what the compiler does WITH the vector, not its contents."""
    return FakeEmbeddingClient(vector=[0.5, 0.5, 0.5])


def _state(**overrides) -> ConversationStateV0Plus:
    """Build a v0+ Pydantic state. `played_track_ids` is mechanical and lives on
    `ResolvedConversationState`, not the LLM schema — extract it before calling."""
    defaults = dict(
        turn_intent="play me some smoky lounge",
        intent_mode="refinement",
        track_feedback=[],
        referenced_track_ids=[],
        mentioned_entities=[],
        hard_filters=[],
        explicit_rejections=[],
    )
    defaults.update(overrides)
    return ConversationStateV0Plus(**defaults)


def _resolve(
    state: ConversationStateV0Plus,
    catalog: DictCatalog | None = None,
    played_track_ids: list[str] | None = None,
):
    catalog = catalog or _catalog()
    matcher = RapidfuzzCatalogMatcher(catalog)
    return V0PlusResolver(matcher, catalog).resolve(
        state, played_track_ids=played_track_ids or []
    )


# ---------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------


def test_compiler_routes_artist_mention_to_artist_name_channel():
    """The artist_name channel gets the bound mention; turn_intent goes to
    track_name + tag_list. (`turn_intent` may itself contain artist tokens —
    that's a user-typing concern, not a compiler concern.)"""
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="more like that one please",  # no artist token in intent
        mentioned_entities=[
            MentionedEntity(type="artist", value="Morphine", sentiment=1),
        ],
    )
    compiler = V0PlusCompiler(catalog, retriever, _fake_encoder())
    compiler.compile(_resolve(state, catalog))

    assert len(retriever.search_calls) == 1
    clauses = retriever.search_calls[0]
    by_field = {c.field: c.query for c in clauses}
    # Bound artist mention lands ONLY in the artist_name channel
    assert by_field["artist_name"] == "Morphine"
    # turn_intent fans out to track_name + tag_list (NOT artist_name)
    assert "more like" in by_field["track_name"]
    assert "more like" in by_field["tag_list"]
    # No turn_intent vocab leaks into artist_name — just the bound mention
    assert by_field["artist_name"] == "Morphine"  # would have "more like Morphine" if leaked


def test_compiler_skips_negative_sentiment_mentions_in_bm25():
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="not them",
        mentioned_entities=[
            MentionedEntity(type="artist", value="Morphine", sentiment=-1),
        ],
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    clauses = retriever.search_calls[0]
    by_field = {c.field: c.query for c in clauses}
    assert "Morphine" not in by_field.get("artist_name", "")


def test_compiler_drops_anchor_tag_expansion_on_pivot():
    """Anchor tags from prior accepted feedback should NOT appear in BM25
    when intent_mode == 'pivot'."""
    catalog = _catalog()
    retriever = FakeRetriever()
    # User accepted a smoky-lounge track but then pivoted
    state = _state(
        turn_intent="actually take me to grunge",
        intent_mode="pivot",
        track_feedback=[
            TrackFeedback(track_id="t-morphine-1", overall_sentiment=1, role="accepted"),
        ],
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    clauses = retriever.search_calls[0]
    tag_query = next((c.query for c in clauses if c.field == "tag_list"), "")
    # Anchor tags ("smoky", "lounge") must NOT appear in the tag channel
    assert "smoky" not in tag_query
    assert "lounge" not in tag_query


def test_compiler_includes_anchor_tags_on_refinement():
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="more please",
        intent_mode="refinement",
        track_feedback=[
            TrackFeedback(track_id="t-morphine-1", overall_sentiment=1, role="accepted"),
        ],
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    clauses = retriever.search_calls[0]
    tag_query = next((c.query for c in clauses if c.field == "tag_list"), "")
    assert "smoky" in tag_query  # anchor tag from the accepted morphine track


def test_compiler_centroid_alpha_zero_on_pivot_means_no_mixing():
    """On pivot, dense query vector should equal encode(text) — no centroid mix."""
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="actually try jazz",
        intent_mode="pivot",
        track_feedback=[
            TrackFeedback(track_id="t-morphine-1", overall_sentiment=1, role="accepted"),
        ],
    )
    encoder = _fake_encoder()
    V0PlusCompiler(catalog, retriever, encoder).compile(_resolve(state, catalog))

    # 3 dense branches by default; each call should use the pure encoded vector
    # (no centroid mixing) when pivot disables α.
    assert len(retriever.embedding_calls) == 3
    raw = encoder.vector
    norm = sum(x * x for x in raw) ** 0.5
    expected = [x / norm for x in raw]
    for call in retriever.embedding_calls:
        actual = call["query_vector"]
        for a, e in zip(actual, expected):
            assert abs(a - e) < 1e-9


def test_compiler_centroid_alpha_positive_on_refinement_actually_mixes():
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="more please",
        intent_mode="refinement",
        track_feedback=[
            TrackFeedback(track_id="t-morphine-1", overall_sentiment=1, role="accepted"),
        ],
    )
    encoder = _fake_encoder()
    V0PlusCompiler(catalog, retriever, encoder).compile(_resolve(state, catalog))

    raw = encoder.vector
    norm = sum(x * x for x in raw) ** 0.5
    pure_encoded_normalized = [x / norm for x in raw]
    actual = retriever.embedding_calls[0]["query_vector"]
    # The mixed vector should differ from pure-encoded by something nontrivial
    # (anchor centroid is [1, 0, 0])
    assert any(abs(a - p) > 1e-6 for a, p in zip(actual, pure_encoded_normalized))


def test_compiler_no_dense_call_when_query_string_is_empty():
    """If turn_intent is blank AND no positive entity / tag, skip dense entirely."""
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(turn_intent="")
    V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    assert retriever.embedding_calls == []  # dense skipped
    # BM25 may also be empty; that's fine — backfill handles it


# ---------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------


def test_compiler_hard_drops_played_tracks():
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={
            "tag_list": [
                ("t-morphine-1", 5.0),
                ("t-morphine-2", 4.0),
                ("t-tomwaits-1", 3.0),
            ],
        },
    )
    state = _state()
    result = V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(
        _resolve(state, catalog, played_track_ids=["t-morphine-1"])
    )

    assert "t-morphine-1" not in result


def test_compiler_hard_drops_track_feedback_rejected():
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={
            "tag_list": [
                ("t-fugazi-1", 5.0),
                ("t-fugazi-2", 4.0),
            ],
        },
    )
    state = _state(
        track_feedback=[
            TrackFeedback(track_id="t-fugazi-1", overall_sentiment=-1, role="rejected"),
        ],
    )
    result = V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    assert "t-fugazi-1" not in result


def test_compiler_hard_drops_resolved_artist_rejections():
    """All tracks by a rejected artist should be hard-dropped."""
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={
            "tag_list": [
                ("t-fugazi-1", 5.0),
                ("t-fugazi-2", 4.0),
                ("t-morphine-1", 3.0),
            ],
        },
    )
    state = _state(
        explicit_rejections=[
            ExplicitRejection(kind="artist", value="Fugazi", source_turn=2),
        ],
    )
    result = V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    assert "t-fugazi-1" not in result
    assert "t-fugazi-2" not in result
    # Morphine survives
    assert "t-morphine-1" in result


def test_compiler_release_date_filter_excludes_out_of_range_tracks():
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={
            "tag_list": [
                ("t-fugazi-1", 5.0),    # 1988 — too old
                ("t-morphine-1", 4.0),  # 1993 — in range
                ("t-tomwaits-1", 3.0),  # 1999 — in range
            ],
        },
    )
    state = _state(
        hard_filters=[
            HardFilter(field="release_date", op="between", start="1990-01-01", end="2000-12-31"),
        ],
    )
    result = V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    assert "t-fugazi-1" not in result
    assert "t-morphine-1" in result
    assert "t-tomwaits-1" in result


# ---------------------------------------------------------------------
# Soft adjustments
# ---------------------------------------------------------------------


def test_compiler_soft_demotes_same_artist_as_rejected_feedback():
    """Tracks sharing artist_id with a rejected track should rank below
    same-score tracks from other artists."""
    catalog = _catalog()
    # Equal raw BM25 scores; the demote should differentiate them
    retriever = FakeRetriever(
        text_hits_by_field={
            "tag_list": [
                ("t-morphine-2", 5.0),  # same artist as rejected -> demote
                ("t-tomwaits-1", 5.0),  # different artist -> no demote
            ],
        },
    )
    state = _state(
        track_feedback=[
            TrackFeedback(track_id="t-morphine-1", overall_sentiment=-1, role="rejected"),
        ],
    )
    result = V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    # t-morphine-1 is hard-dropped; t-morphine-2 demoted below t-tomwaits-1
    pos_tomwaits = result.index("t-tomwaits-1")
    pos_morphine2 = result.index("t-morphine-2")
    assert pos_tomwaits < pos_morphine2


def test_compiler_soft_demotes_tracks_with_rejected_tag_overlap():
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={
            "tag_list": [
                ("t-morphine-2", 5.0),  # has "heavy" -> demote
                ("t-morphine-1", 5.0),  # no "heavy" -> no demote
            ],
        },
    )
    state = _state(
        explicit_rejections=[
            ExplicitRejection(kind="tag", value="heavy", source_turn=2),
        ],
    )
    result = V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    assert result.index("t-morphine-1") < result.index("t-morphine-2")


def test_compiler_soft_promotes_positive_tag_overlap():
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={
            "tag_list": [
                ("t-fugazi-1", 5.0),    # no tag overlap with "smoky"
                ("t-morphine-1", 5.0),  # has "smoky" -> promote
            ],
        },
    )
    state = _state(
        mentioned_entities=[
            MentionedEntity(type="tag", value="smoky", sentiment=1),
        ],
    )
    result = V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    assert result.index("t-morphine-1") < result.index("t-fugazi-1")


# ---------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------


def test_compiler_backfills_to_final_topk_with_popularity_sorted():
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={
            "tag_list": [("t-morphine-1", 5.0)],
        },
    )
    state = _state()
    compiler = V0PlusCompiler(
        catalog, retriever, _fake_encoder(),
        CompilerConfig(final_topk=3),
    )
    result = compiler.compile(_resolve(state, catalog))

    assert len(result) == 3
    assert result[0] == "t-morphine-1"
    # The next two slots are filled by popularity (t-filler-1 is highest at 100)
    assert result[1] == "t-filler-1"


def test_compiler_backfill_respects_hard_drops():
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={"tag_list": [("t-morphine-1", 5.0)]},
    )
    # User explicitly rejected the highest-popularity backfill candidate
    state = _state(
        explicit_rejections=[
            ExplicitRejection(kind="track", value="Filler Track One", source_turn=1),
        ],
    )
    compiler = V0PlusCompiler(
        catalog, retriever, _fake_encoder(),
        CompilerConfig(final_topk=4),
    )
    result = compiler.compile(_resolve(state, catalog))

    assert "t-filler-1" not in result  # never re-introduced via backfill


def test_compiler_backfill_respects_release_date_mask():
    catalog = _catalog()
    retriever = FakeRetriever(text_hits_by_field={"tag_list": [("t-morphine-1", 5.0)]})
    state = _state(
        hard_filters=[
            HardFilter(field="release_date", op="<", end="2000-01-01"),
        ],
    )
    compiler = V0PlusCompiler(
        catalog, retriever, _fake_encoder(),
        CompilerConfig(final_topk=10),
    )
    result = compiler.compile(_resolve(state, catalog))

    # t-filler-1 is 2010 — must NOT appear even though it's the most popular
    assert "t-filler-1" not in result


# ---------------------------------------------------------------------
# Integration: exactly two retrieval calls per turn
# ---------------------------------------------------------------------


def test_compiler_call_counts_one_bm25_plus_one_per_dense_branch():
    """Compiler issues one `search(clauses)` call (BM25, multi-field, Solr-style)
    plus one `search_embedding(...)` per enabled dense branch."""
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={"artist_name": [("t-morphine-1", 5.0)]},
        embedding_hits=[("t-morphine-1", 0.9)],
    )
    state = _state(
        mentioned_entities=[
            MentionedEntity(type="artist", value="Morphine", sentiment=1),
        ],
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    # Single BM25 call (multi-field clauses internally)
    assert len(retriever.search_calls) == 1
    # One dense call per default branch: metadata + attributes + lyrics
    assert len(retriever.embedding_calls) == 3
    vector_fields = {c["vector_field"] for c in retriever.embedding_calls}
    assert vector_fields == {
        "metadata_qwen3_embedding_0_6b",
        "attributes_qwen3_embedding_0_6b",
        "lyrics_qwen3_embedding_0_6b",
    }


def test_compiler_respects_custom_dense_branches_config():
    """Caller can specify a single dense branch (e.g. metadata-only ablation)."""
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={"artist_name": [("t-morphine-1", 5.0)]},
        embedding_hits=[("t-morphine-1", 0.9)],
    )
    state = _state(
        mentioned_entities=[
            MentionedEntity(type="artist", value="Morphine", sentiment=1),
        ],
    )
    cfg = CompilerConfig(
        dense_branches=[
            DenseBranch(vector_field="metadata_qwen3_embedding_0_6b"),
        ]
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(_resolve(state, catalog))
    assert len(retriever.embedding_calls) == 1
    assert retriever.embedding_calls[0]["vector_field"] == "metadata_qwen3_embedding_0_6b"


# ---------------------------------------------------------------------
# CompileResult / BranchPool (Task 1)
# ---------------------------------------------------------------------


def _compiler_with_hits():
    """Compiler whose BM25 + one dense branch return scripted hits."""
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={
            "track_name": [("t-morphine-1", 5.0), ("t-fugazi-1", 3.0)],
        },
        embedding_hits=[("t-morphine-2", 0.9), ("t-fugazi-2", 0.8)],
    )
    cfg = CompilerConfig(
        final_topk=10,
        bm25_k=10,
        dense_k=10,
        dense_branches=[DenseBranch(vector_field="metadata_qwen3_embedding_0_6b")],
    )
    compiler = V0PlusCompiler(
        catalog=catalog,
        retriever=retriever,
        encoder=FakeEmbeddingClient(),
        config=cfg,
    )
    return compiler


def _resolved_state_track_query():
    """A resolved state with a free-text turn_intent so BM25 + dense both fire."""
    catalog = _catalog()
    state = _state(turn_intent="smoky lounge")
    resolver = V0PlusResolver(RapidfuzzCatalogMatcher(catalog), catalog)
    return resolver.resolve(state, played_track_ids=[])


def test_compile_returns_list_of_str_unchanged():
    compiler = _compiler_with_hits()
    rs = _resolved_state_track_query()
    out = compiler.compile(rs)
    assert isinstance(out, list)
    assert all(isinstance(t, str) for t in out)


def test_internal_compile_returns_compileresult_with_ranked_equal_to_compile():
    compiler = _compiler_with_hits()
    rs = _resolved_state_track_query()
    out = compiler.compile(rs)
    res = compiler._compile(rs)
    assert isinstance(res, CompileResult)
    assert res.ranked == out


def test_compile_result_has_named_branch_pools():
    compiler = _compiler_with_hits()
    rs = _resolved_state_track_query()
    res = compiler._compile(rs)
    names = [p.name for p in res.branch_pools]
    assert "bm25" in names
    assert "dense:metadata_qwen3_embedding_0_6b" in names
    for p in res.branch_pools:
        assert isinstance(p, BranchPool)
        assert all(isinstance(t, str) and isinstance(s, float) for t, s in p.hits)


def test_to_trace_dict_shape_and_recommended():
    compiler = _compiler_with_hits()
    rs = _resolved_state_track_query()
    res = compiler._compile(rs)
    d = res.to_trace_dict()

    assert set(d.keys()) == {"depth", "pools", "fused", "final", "recommended"}
    assert d["depth"] == 10  # cfg.final_topk in _compiler_with_hits

    # pools: list of {name, hits:[[id, score], ...]}
    for pool in d["pools"]:
        assert set(pool.keys()) == {"name", "hits"}
        for hit in pool["hits"]:
            assert len(hit) == 2 and isinstance(hit[0], str)

    # final + recommended consistency
    assert d["final"]["track_ids"] == res.ranked
    assert d["recommended"]["top1_track_id"] == (res.ranked[0] if res.ranked else None)
    assert d["final"]["n_from_fusion"] + d["final"]["n_from_backfill"] == len(res.ranked)


def test_provenance_counts_pure_backfill_when_no_hits():
    """No BM25/dense hits → final list is entirely popularity backfill."""
    catalog = _catalog()
    retriever = FakeRetriever()  # returns nothing
    cfg = CompilerConfig(final_topk=5, dense_branches=[], enable_dense=False)
    compiler = V0PlusCompiler(
        catalog=catalog, retriever=retriever, encoder=FakeEmbeddingClient(), config=cfg
    )
    rs = _resolved_state_track_query()
    res = compiler._compile(rs)
    assert res.n_from_fusion == 0
    assert res.n_from_backfill == len(res.ranked)
    assert res.to_trace_dict()["recommended"]["top1_track_id"] == res.ranked[0]
