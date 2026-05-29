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
    CentroidOnlyBranch,
    CompilerConfig,
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


def test_compiler_emits_one_bm25_clause_per_positive_entity():
    """Multiple positive mentions of the same entity type should each get their
    own FieldQuery, not be space-joined into a single multi-token query.

    With the joined form, tantivy's BM25 systematically out-scores docs that
    match a multi-token name (`"Rolling Stones"`) over docs that match a
    single-token name (`"Beatles"`), regardless of user intent. Splitting per
    entity gives each one an independent, normalized BM25 signal."""
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="",  # keep intent out so we only see entity clauses
        mentioned_entities=[
            MentionedEntity(type="artist", value="Morphine", sentiment=1),
            MentionedEntity(type="artist", value="Tom Waits", sentiment=1),
        ],
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    clauses = retriever.search_calls[0]
    artist_queries = [c.query for c in clauses if c.field == "artist_name"]
    # Two separate artist mentions => two separate clauses, NOT one joined.
    assert "Morphine" in artist_queries
    assert "Tom Waits" in artist_queries
    # And the buggy joined form must not appear.
    assert "Morphine Tom Waits" not in artist_queries


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


def test_compiler_skips_anchor_centroid_only_branches_on_pivot():
    catalog = _catalog()
    retriever = FakeRetriever(embedding_hits=[("t-morphine-2", 0.9)])
    state = _state(
        turn_intent="actually take me somewhere totally different",
        intent_mode="pivot",
        track_feedback=[
            TrackFeedback(track_id="t-morphine-1", overall_sentiment=1, role="accepted"),
        ],
    )
    cfg = CompilerConfig(
        enable_dense=False,
        centroid_only_branches=[
            CentroidOnlyBranch(vector_field="metadata_qwen3_embedding_0_6b"),
        ],
    )

    V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(_resolve(state, catalog))

    assert retriever.embedding_calls == []


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


def test_compiler_backfill_respects_artist_level_hard_exclusions():
    """When a rejection resolves to BOTH track_ids and artist_ids (per the
    `_apply_soft_adjustments` comment "kind='track' still resolves the owning
    artist"), `_backfill` must also honor the artist-level exclusion. Otherwise
    popularity-sorted backfill silently re-admits tracks by the rejected
    artist, undoing the post-fusion hard exclusion."""
    catalog = _catalog()
    # Force backfill: BM25 returns no hits, so the only way the result list
    # gets to 1000 is via the popularity-sorted backfill in _backfill.
    retriever = FakeRetriever(text_hits_by_field={})
    state = _state(
        explicit_rejections=[
            ExplicitRejection(kind="track", value="Cure for Pain", source_turn=2),
        ],
    )
    result = V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(
        _resolve(state, catalog)
    )

    # Both morphine tracks must stay out: t-morphine-1 via the track id,
    # t-morphine-2 via the artist id. Pre-fix, t-morphine-2 sneaks back in
    # through popularity-sorted backfill.
    assert "t-morphine-1" not in result
    assert "t-morphine-2" not in result


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
    from mcrs.qu_modules.compiler_v0plus import DenseBranch
    cfg = CompilerConfig(
        dense_branches=[
            DenseBranch(vector_field="metadata_qwen3_embedding_0_6b"),
        ]
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(_resolve(state, catalog))
    assert len(retriever.embedding_calls) == 1
    assert retriever.embedding_calls[0]["vector_field"] == "metadata_qwen3_embedding_0_6b"


# ---------------------------------------------------------------------
# Per-branch encoder / query-template dispatch (R1-R4 text-side work)
# ---------------------------------------------------------------------


def _branch(**overrides):
    """Shorthand for a DenseBranch — keeps tests readable when the branch
    list contains many entries differing only in encoder_id / query_id."""
    from mcrs.qu_modules.compiler_v0plus import DenseBranch
    defaults = dict(vector_field="metadata_qwen3_embedding_0_6b")
    defaults.update(overrides)
    return DenseBranch(**defaults)


def test_compiler_encodes_each_query_template_once_per_compile():
    """When two branches share `(encoder_id, query_id)`, the compiler must
    encode that query string exactly once and reuse the vector — even though
    the branches point at different vector columns. This is the v4-shape
    caching contract."""
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={"artist_name": [("t-morphine-1", 5.0)]},
        embedding_hits=[("t-morphine-1", 0.9)],
    )
    state = _state(
        mentioned_entities=[
            MentionedEntity(type="tag", value="smoky", sentiment=1),
        ],
    )
    encoder = FakeEmbeddingClient(vector=[0.1, 0.2, 0.3])
    cfg = CompilerConfig(
        dense_branches=[
            _branch(vector_field="vec_a", encoder_id="default", query_id="sonic"),
            _branch(vector_field="vec_b", encoder_id="default", query_id="sonic"),
            _branch(vector_field="vec_c", encoder_id="default", query_id="sonic_nl"),
        ]
    )
    V0PlusCompiler(catalog, retriever, encoder, cfg).compile(_resolve(state, catalog))

    # 2 unique (encoder, query) pairs => 2 encode calls (NOT 3).
    assert len(encoder.calls) == 2
    # All three branches were searched.
    assert len(retriever.embedding_calls) == 3


def test_compiler_routes_each_branch_to_named_encoder():
    """`encoder_id` dispatches to the corresponding entry in the encoders map.
    Two branches naming different encoder_ids must hit different clients."""
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={"artist_name": [("t-morphine-1", 5.0)]},
        embedding_hits=[("t-morphine-1", 0.9)],
    )
    state = _state(
        mentioned_entities=[
            MentionedEntity(type="tag", value="smoky", sentiment=1),
        ],
    )
    qwen3 = FakeEmbeddingClient(vector=[1.0, 0.0, 0.0])
    siglip = FakeEmbeddingClient(vector=[0.0, 1.0, 0.0])
    clap = FakeEmbeddingClient(vector=[0.0, 0.0, 1.0])
    cfg = CompilerConfig(
        dense_branches=[
            _branch(vector_field="metadata_qwen3_embedding_0_6b",
                    encoder_id="default", query_id="intent"),
            _branch(vector_field="image_siglip2",
                    encoder_id="siglip2_text", query_id="visual"),
            _branch(vector_field="audio_laion_clap",
                    encoder_id="clap_text", query_id="sonic"),
        ]
    )
    V0PlusCompiler(
        catalog,
        retriever,
        encoders={"default": qwen3, "siglip2_text": siglip, "clap_text": clap},
        config=cfg,
    ).compile(_resolve(state, catalog))

    assert len(qwen3.calls) == 1
    assert len(siglip.calls) == 1
    assert len(clap.calls) == 1


def test_compiler_unknown_encoder_id_raises_keyerror():
    """Branches referencing an encoder_id missing from the map must fail
    fast with a clear message (caught at compile time, not silently dropped)."""
    import pytest
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        mentioned_entities=[MentionedEntity(type="tag", value="smoky", sentiment=1)],
    )
    cfg = CompilerConfig(
        dense_branches=[
            _branch(encoder_id="missing_encoder", query_id="intent"),
        ]
    )
    compiler = V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg)
    with pytest.raises(KeyError, match="missing_encoder"):
        compiler.compile(_resolve(state, catalog))


def test_compiler_unknown_query_id_raises_keyerror():
    """Branches with a query_id that has no registered builder must fail fast."""
    import pytest
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state()
    cfg = CompilerConfig(
        dense_branches=[_branch(query_id="not_a_real_template")],
    )
    compiler = V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg)
    with pytest.raises(KeyError, match="not_a_real_template"):
        compiler.compile(_resolve(state, catalog))


def test_branch_traces_use_distinct_keys_for_each_branch():
    """v4 defines three CLAP branches that share (encoder_id, vector_field) and
    differ only by query_id. The branch_rankings trace key MUST include
    query_id so the three branches don't collapse to one entry — the bug
    surfaced by reviewer audit before merge."""
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={"artist_name": [("t-morphine-1", 5.0)]},
        embedding_hits=[("t-morphine-1", 0.9)],
    )
    state = _state(
        mentioned_entities=[MentionedEntity(type="tag", value="smoky", sentiment=1)],
    )
    cfg = CompilerConfig(
        branch_trace_topk=10,
        dense_branches=[
            _branch(vector_field="audio_laion_clap",
                    encoder_id="default", query_id="sonic"),
            _branch(vector_field="audio_laion_clap",
                    encoder_id="default", query_id="sonic_nl"),
            _branch(vector_field="audio_laion_clap",
                    encoder_id="default", query_id="sonic_nl_enriched"),
        ],
    )
    traces: dict[str, list[str]] = {}
    V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(
        _resolve(state, catalog), branch_traces=traces
    )

    dense_keys = [k for k in traces if k.startswith("dense.")]
    # Three branches => three distinct dense trace entries (NOT one collapsed).
    assert len(dense_keys) == 3
    assert len(set(dense_keys)) == 3
    # Each key includes both query_id and vector_field.
    for qid in ("sonic", "sonic_nl", "sonic_nl_enriched"):
        assert any(qid in k and "audio_laion_clap" in k for k in dense_keys), (
            f"missing trace key for query_id={qid}: {dense_keys}"
        )


def test_branch_traces_off_by_default():
    """`branch_trace_topk=0` (default) means no trace dict gets populated even
    when the caller passes one — keeps the diagnostic free in prod."""
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={"artist_name": [("t-morphine-1", 5.0)]},
        embedding_hits=[("t-morphine-1", 0.9)],
    )
    state = _state(
        mentioned_entities=[MentionedEntity(type="tag", value="smoky", sentiment=1)],
    )
    traces: dict[str, list[str]] = {}
    V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(
        _resolve(state, catalog), branch_traces=traces
    )
    assert traces == {}


# ---------------------------------------------------------------------
# Query template content (sonic / visual / sonic_nl / lyric)
# ---------------------------------------------------------------------


def _capture_query_text(state, query_id, encoder=None) -> str | None:
    """Helper: run compile() with one dense branch using `query_id` and
    return the string actually handed to the encoder (or None if the
    branch was skipped)."""
    catalog = _catalog()
    retriever = FakeRetriever()
    encoder = encoder or FakeEmbeddingClient()
    cfg = CompilerConfig(
        dense_branches=[_branch(query_id=query_id)],
    )
    V0PlusCompiler(catalog, retriever, encoder, cfg).compile(_resolve(state, catalog))
    if not encoder.calls:
        return None
    return encoder.calls[0][0]


def test_sonic_query_uses_music_prefixed_tag_list():
    """`sonic` (CLAP music) template: "music: {tags}; {turn_intent}"."""
    state = _state(
        turn_intent="energetic and intense",
        mentioned_entities=[
            MentionedEntity(type="tag", value="punk", sentiment=1),
            MentionedEntity(type="tag", value="hardcore", sentiment=1),
        ],
    )
    q = _capture_query_text(state, "sonic")
    assert q is not None and q.startswith("music: ")
    assert "punk" in q and "hardcore" in q
    assert "energetic and intense" in q


def test_visual_query_uses_album_cover_prefix():
    """`visual` (SigLIP-2) template: "album cover, {tags}"."""
    state = _state(
        turn_intent="moody atmospheric",
        mentioned_entities=[
            MentionedEntity(type="tag", value="indie", sentiment=1),
            MentionedEntity(type="tag", value="dreamy", sentiment=1),
        ],
    )
    q = _capture_query_text(state, "visual")
    assert q is not None and q.startswith("album cover, ")
    assert "indie" in q and "dreamy" in q


def test_sonic_nl_query_uses_natural_language_phrasing():
    """`sonic_nl` template: "A song with {tags} sound, similar to {artists}"."""
    state = _state(
        mentioned_entities=[
            MentionedEntity(type="tag", value="indie", sentiment=1),
            MentionedEntity(type="artist", value="Fugazi", sentiment=1),
        ],
    )
    q = _capture_query_text(state, "sonic_nl")
    assert q is not None
    assert "A song with indie sound" in q
    assert "similar to Fugazi" in q


def test_sonic_nl_query_skips_negative_sentiment_mentions():
    """Negative-sentiment entities must not leak into the natural-language
    query — they describe what the user does NOT want."""
    state = _state(
        mentioned_entities=[
            MentionedEntity(type="tag", value="punk", sentiment=1),
            MentionedEntity(type="tag", value="metal", sentiment=-1),
            MentionedEntity(type="artist", value="Fugazi", sentiment=-1),
        ],
    )
    q = _capture_query_text(state, "sonic_nl")
    assert q is not None
    assert "punk" in q
    assert "metal" not in q
    assert "Fugazi" not in q


def test_lyric_query_fires_when_intent_has_lyric_signal():
    """`lyric` template should fire when intent contains a hint word like
    "lyrics" / "story" / "meaningful"."""
    state = _state(turn_intent="songs with meaningful lyrics about loss")
    q = _capture_query_text(state, "lyric")
    assert q is not None
    assert "meaningful lyrics" in q


def test_lyric_query_skips_when_intent_has_no_lyric_signal():
    """No hint vocabulary in state => `lyric` template returns None (the
    compiler converts this to an empty hit list that RRF ignores)."""
    state = _state(
        turn_intent="upbeat dance music",
        mentioned_entities=[
            MentionedEntity(type="tag", value="dance", sentiment=1),
            MentionedEntity(type="tag", value="electronic", sentiment=1),
        ],
    )
    q = _capture_query_text(state, "lyric")
    assert q is None


def test_lyric_query_uses_token_boundary_not_substring_match():
    """Substring matching would falsely fire on `"history"` (contains "story")
    or `"deepfake"` (contains "deep"). The lyric builder must use word-boundary
    matching so common English doesn't trigger the lyric branch."""
    # "history" must NOT trigger via substring "story"
    state = _state(turn_intent="songs about the history of jazz")
    assert _capture_query_text(state, "lyric") is None, (
        "substring match on 'story' should not fire for 'history'"
    )
    # Real lyric mention DOES still trigger.
    state = _state(turn_intent="songs with a strong story")
    assert _capture_query_text(state, "lyric") is not None


def test_lyric_query_skipped_branch_does_not_emit_encode_call():
    """When the lyric branch is skipped (no lyric signal), the compiler must
    NOT encode anything for it — wasted Modal RPC otherwise."""
    state = _state(
        turn_intent="upbeat dance",
        mentioned_entities=[MentionedEntity(type="tag", value="dance", sentiment=1)],
    )
    catalog = _catalog()
    retriever = FakeRetriever()
    encoder = FakeEmbeddingClient()
    cfg = CompilerConfig(
        dense_branches=[_branch(query_id="lyric")],
    )
    V0PlusCompiler(catalog, retriever, encoder, cfg).compile(_resolve(state, catalog))
    # No query string => no encode call AND no search_embedding call.
    assert encoder.calls == []
    assert retriever.embedding_calls == []
