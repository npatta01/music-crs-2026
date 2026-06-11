"""Unit tests for the v0+ Compiler."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from mcrs.conversation_state.schema import (
    ConversationStateV0Plus,
    ExplicitRejection,
    HardFilter,
    MentionedEntity,
    TrackFeedback,
)
from mcrs.qu_modules.compiler_v0plus import (
    CentroidOnlyBranch,
    CompilerConfig,
    DenseBranch,
    V0PlusCompiler,
)
from mcrs.qu_modules.fuzzy_matcher import RapidfuzzCatalogMatcher
from mcrs.qu_modules.resolver_v0plus import (
    ResolvedConversationState,
    ResolvedTarget,
    V0PlusResolver,
)
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


class CountingReleaseYearCatalog(DictCatalog):
    def __post_init__(self) -> None:
        self.release_year_calls = 0
        super().__post_init__()

    def release_year_of(self, track_id: str) -> int | None:
        self.release_year_calls += 1
        return super().release_year_of(track_id)


class NoReleaseTextFieldRetriever(FakeRetriever):
    @property
    def supported_text_fields(self) -> frozenset[str]:
        return frozenset({"track_name", "artist_name", "album_name", "tag_list"})


class LimitedVectorFieldRetriever(FakeRetriever):
    @property
    def supported_vector_fields(self) -> frozenset[str]:
        return frozenset({"metadata_qwen3_embedding_0_6b"})


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


def test_compiler_uses_satisfied_track_feedback_as_soft_anchor_on_refinement():
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="yes, keep going",
        intent_mode="refinement",
        track_feedback=[
            TrackFeedback(track_id="t-morphine-1", overall_sentiment=1, role="satisfied"),
        ],
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    clauses = retriever.search_calls[0]
    tag_query = next((c.query for c in clauses if c.field == "tag_list"), "")
    assert "smoky" in tag_query


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


def test_compiler_routes_single_decade_release_year_range_to_release_decade_bm25():
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="",
        release_year_range={"start": 1990, "end": 1999},
    )
    cfg = CompilerConfig(
        enable_dense=False,
        field_boosts={"release_decade": 2.25},
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(_resolve(state, catalog))

    clauses = retriever.search_calls[0]
    assert [
        (c.field, c.query, c.boost)
        for c in clauses
        if c.field in {"release_year", "release_decade"}
    ] == [("release_decade", "1990s", 2.25)]


def test_compiler_routes_exact_release_year_range_to_release_year_bm25():
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="",
        release_year_range={"start": 1995, "end": 1995},
    )
    cfg = CompilerConfig(
        enable_dense=False,
        field_boosts={"release_year": 3.5},
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(_resolve(state, catalog))

    clauses = retriever.search_calls[0]
    assert [
        (c.field, c.query, c.boost)
        for c in clauses
        if c.field in {"release_year", "release_decade"}
    ] == [("release_year", "1995", 3.5)]


def test_compiler_routes_cross_decade_release_year_range_to_each_decade_bm25():
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="",
        release_year_range={"start": 1995, "end": 2004},
    )
    cfg = CompilerConfig(
        enable_dense=False,
        field_boosts={"release_decade": 2.25},
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(_resolve(state, catalog))

    clauses = retriever.search_calls[0]
    assert [
        (c.field, c.query, c.boost)
        for c in clauses
        if c.field in {"release_year", "release_decade"}
    ] == [
        ("release_decade", "1990s", 2.25),
        ("release_decade", "2000s", 2.25),
    ]


def test_compiler_clamps_open_ended_release_year_range_to_catalog_decades():
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="",
        release_year_range={"start": 2000, "end": None},
    )
    cfg = CompilerConfig(
        enable_dense=False,
        field_boosts={"release_decade": 2.25},
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(_resolve(state, catalog))

    clauses = retriever.search_calls[0]
    assert [
        (c.field, c.query, c.boost)
        for c in clauses
        if c.field in {"release_year", "release_decade"}
    ] == [
        ("release_decade", "2000s", 2.25),
        ("release_decade", "2010s", 2.25),
    ]


def test_compiler_keeps_release_year_range_fts_disabled_by_default():
    catalog = _catalog()
    retriever = FakeRetriever()
    state = _state(
        turn_intent="",
        release_year_range={"start": 1990, "end": 1999},
    )
    V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    clauses = retriever.search_calls[0]
    assert [
        c for c in clauses
        if c.field in {"release_year", "release_decade"}
    ] == []


def test_compiler_does_not_scan_release_year_bounds_when_fts_boosts_disabled():
    catalog = CountingReleaseYearCatalog(tracks=_catalog().tracks)
    retriever = FakeRetriever()
    state = _state(
        turn_intent="",
        release_year_range={"start": 2000, "end": None},
    )
    cfg = CompilerConfig(enable_dense=False)

    V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(_resolve(state, catalog))

    assert catalog.release_year_calls == 0


def test_compiler_reuses_catalog_release_year_bounds_for_open_ranges():
    catalog = CountingReleaseYearCatalog(tracks=_catalog().tracks)
    retriever = FakeRetriever()
    state = _state(
        turn_intent="",
        release_year_range={"start": 2000, "end": None},
    )
    cfg = CompilerConfig(
        enable_dense=False,
        field_boosts={"release_decade": 2.25},
    )
    compiler = V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg)
    resolved = _resolve(state, catalog)

    compiler.compile(resolved)
    compiler.compile(resolved)

    assert catalog.release_year_calls == len(catalog.tracks)


def test_compiler_config_merges_default_field_boosts_without_mutating_input():
    field_boosts = {"tag_list": 9.0}

    cfg = CompilerConfig(field_boosts=field_boosts)

    assert field_boosts == {"tag_list": 9.0}
    assert cfg.field_boosts["tag_list"] == 9.0
    assert cfg.field_boosts["track_name"] == 3.0
    assert cfg.field_boosts["release_year"] == 0.0
    assert cfg.field_boosts["release_decade"] == 0.0


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


def test_compiler_skips_malformed_release_date_filter():
    """A `between` filter with missing bounds should be a no-op, not blow up
    the candidate pool. Regression: previously the catalog returned `set()`
    for malformed filters and the compiler intersected → empty pool.
    """
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={"tag_list": [("t-morphine-1", 5.0), ("t-tomwaits-1", 4.0)]},
    )
    # Construct a malformed filter the way the LLM occasionally does
    bogus = HardFilter(field="release_date", op="between")
    state = _state(hard_filters=[bogus])
    result = V0PlusCompiler(catalog, retriever, _fake_encoder()).compile(_resolve(state, catalog))

    # Pool should not be wiped by the malformed filter; both hits survive
    assert "t-morphine-1" in result
    assert "t-tomwaits-1" in result


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


def test_compiler_skips_dense_branches_for_unsupported_vector_fields():
    catalog = _catalog()
    retriever = LimitedVectorFieldRetriever(
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
            DenseBranch(vector_field="metadata_qwen3_embedding_8b"),
        ]
    )

    V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(_resolve(state, catalog))

    assert [call["vector_field"] for call in retriever.embedding_calls] == [
        "metadata_qwen3_embedding_0_6b"
    ]


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
    res = V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg)._compile(
        _resolve(state, catalog)
    )
    traces = {p.name: [t for t, _ in p.hits] for p in res.branch_pools}

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
    """`branch_trace_topk=0` (default) means branch_pools is empty — keeps the
    diagnostic free in prod."""
    catalog = _catalog()
    res = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder())._compile(_resolve(_state(), catalog))
    assert res.branch_pools == []


def test_branch_trace_includes_queries_status_and_filter_summary():
    """Branch tracing should preserve the runtime facts needed to rebuild
    ranker datasets offline without depending on RRF-derived features."""
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={
            "track_name": [
                ("t-fugazi-1", 4.0),      # release-date filtered
                ("t-tomwaits-1", 3.0),    # played hard-drop
                ("t-morphine-1", 2.0),    # explicit artist rejection
            ],
            "tag_list": [
                ("t-morphine-2", 1.0),    # explicit artist rejection
            ],
        },
        embedding_hits=[
            ("t-filler-1", 0.9),          # release-date filtered
            ("t-morphine-1", 0.8),        # explicit artist rejection
        ],
    )
    state = _state(
        turn_intent="smoky lounge",
        hard_filters=[
            HardFilter(
                field="release_date",
                op="between",
                start=date(1990, 1, 1),
                end=date(1999, 12, 31),
            )
        ],
        explicit_rejections=[
            ExplicitRejection(kind="artist", value="Morphine", source_turn=1),
        ],
    )
    cfg = CompilerConfig(
        enable_dense=True,
        branch_trace_topk=10,
        dense_branches=[
            DenseBranch(vector_field="metadata_qwen3_embedding_0_6b", query_id="intent"),
            DenseBranch(vector_field="lyrics_qwen3_embedding_0_6b", query_id="lyric"),
        ],
    )

    rs = _resolve(state, catalog, played_track_ids=["t-tomwaits-1"])
    res = V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg)._compile(rs)
    trace = res.to_trace_dict()

    assert trace["branch_queries"]["bm25"]["clauses"]
    dense_key = "dense.default.intent.metadata_qwen3_embedding_0_6b"
    assert trace["branch_queries"][dense_key]["query_text"] == "smoky lounge"
    lyric_key = "dense.default.lyric.lyrics_qwen3_embedding_0_6b"
    assert trace["branch_status"][lyric_key]["fired"] is False
    assert trace["branch_status"][lyric_key]["skip_reason"] == "no_query"

    summary = trace["candidate_filter_summary"]
    assert summary["raw_union_size"] == 5
    assert summary["eligible_union_size"] == 0
    assert summary["release_date_mask_dropped"] == 2
    assert summary["played_track_dropped"] == 1
    assert summary["explicit_rejection_dropped"] == 2


def test_candidate_filter_summary_counts_traced_topk_slice():
    """The compact filter summary mirrors the trace payload, not full pools."""
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={
            "track_name": [
                ("t-morphine-1", 3.0),
                ("t-fugazi-1", 2.0),
                ("t-filler-1", 1.0),
            ],
        },
    )
    cfg = CompilerConfig(branch_trace_topk=1)

    res = V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg)._compile(
        _resolve(_state(turn_intent="smoky lounge"), catalog)
    )
    trace = res.to_trace_dict()

    assert trace["depth"] == 1
    assert trace["pools"][0]["name"] == "bm25"
    assert trace["pools"][0]["hits"] == [["t-morphine-1", 9.0]]
    summary = trace["candidate_filter_summary"]
    assert summary["raw_union_size"] == 1
    assert summary["eligible_union_size"] == 1
    assert summary["release_date_mask_dropped"] == 0


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


# ---------------------------------------------------------------------
# Resolver: ground positive mentioned_entities into resolved_targets
# ---------------------------------------------------------------------


def test_resolver_grounds_positive_artist_mention():
    catalog = _catalog()
    state = _state(mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)])
    rs = _resolve(state, catalog)
    arts = [t for t in rs.resolved_targets if t.kind == "artist"]
    assert len(arts) == 1
    assert arts[0].entity_id == "a-morphine"
    assert arts[0].confidence >= 90
    assert arts[0].source_text == "Morphine"


def test_resolver_grounds_only_v1_seed_entities_as_targets():
    catalog = _catalog()
    state = _state(
        entities=[
            {
                "type": "artist",
                "value": "Morphine",
                "role": "satisfied",
                "source_turn": 2,
                "mentioned_current_turn": True,
                "use_as_retrieval_seed": False,
                "evidence_text": "another artist",
            },
            {
                "type": "tag",
                "value": "smoky",
                "role": "current_target",
                "source_turn": 2,
                "mentioned_current_turn": True,
                "use_as_retrieval_seed": True,
                "evidence_text": "smoky",
            },
        ],
        target_artist_mode="new_artist",
        retrieval_profile="novelty",
    )
    rs = _resolve(state, catalog)

    assert rs.resolved_targets == ()


def test_resolver_grounds_v1_current_artist_seed_as_target():
    catalog = _catalog()
    state = _state(
        entities=[
            {
                "type": "artist",
                "value": "Morphine",
                "role": "current_target",
                "source_turn": 1,
                "mentioned_current_turn": True,
                "use_as_retrieval_seed": True,
                "evidence_text": "more Morphine",
            }
        ],
        target_artist_mode="same_artist",
        retrieval_profile="exact_probe",
    )
    rs = _resolve(state, catalog)

    arts = [t for t in rs.resolved_targets if t.kind == "artist"]
    assert len(arts) == 1
    assert arts[0].entity_id == "a-morphine"


def test_resolver_grounds_fuzzy_artist_spelling():
    catalog = _catalog()
    state = _state(mentioned_entities=[MentionedEntity(type="artist", value="morphine", sentiment=1)])
    rs = _resolve(state, catalog)
    assert any(t.kind == "artist" and t.entity_id == "a-morphine" for t in rs.resolved_targets)


def test_resolver_grounds_exact_track_title():
    catalog = _catalog()
    state = _state(mentioned_entities=[MentionedEntity(type="track", value="Cure for Pain", sentiment=1)])
    rs = _resolve(state, catalog)
    tracks = [t for t in rs.resolved_targets if t.kind == "track"]
    assert tracks and tracks[0].entity_id == "t-morphine-1"


def test_resolver_does_not_ground_negative_sentiment_mention():
    catalog = _catalog()
    state = _state(mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=-1)])
    rs = _resolve(state, catalog)
    assert rs.resolved_targets == ()


def test_resolver_grounds_nothing_for_unknown_surface_form():
    catalog = _catalog()
    state = _state(mentioned_entities=[MentionedEntity(type="artist", value="Zzqxwv Nobody", sentiment=1)])
    rs = _resolve(state, catalog)
    arts = [t for t in rs.resolved_targets if t.kind == "artist"]
    assert len(arts) == 1
    assert arts[0].entity_id is None
    assert arts[0].confidence == 0.0
    assert arts[0].candidates == ()


def test_resolver_ignores_tag_and_album_for_grounding():
    catalog = _catalog()
    state = _state(mentioned_entities=[
        MentionedEntity(type="tag", value="smoky", sentiment=1),
        MentionedEntity(type="album", value="Cure for Pain", sentiment=1),
    ])
    rs = _resolve(state, catalog)
    assert rs.resolved_targets == ()


def _disco_cfg(**overrides):
    base = dict(
        enable_resolved_artist_discography=True,
        disco_weight=1.0,
        disco_cap=10,
        disco_confidence_threshold=90.0,
        disco_gated_intents=("pivot",),
        branch_trace_topk=100,
    )
    base.update(overrides)
    return CompilerConfig(**base)


def test_discography_branch_emits_artist_tracks_popularity_ordered():
    catalog = _catalog()
    state = _state(mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)])
    rs = _resolve(state, catalog)
    res = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), _disco_cfg())._compile(rs)
    traces = {p.name: [t for t, _ in p.hits] for p in res.branch_pools}
    pool = traces["lookup.resolved_artist_discography"]
    assert pool[:2] == ["t-morphine-1", "t-morphine-2"]  # pop 70 before 55


def test_discography_branch_disabled_by_default():
    catalog = _catalog()
    state = _state(mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)])
    rs = _resolve(state, catalog)
    cfg = CompilerConfig(branch_trace_topk=100)  # enable flag defaults False
    res = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), cfg)._compile(rs)
    traces = {p.name: [t for t, _ in p.hits] for p in res.branch_pools}
    assert "lookup.resolved_artist_discography" not in traces


def test_discography_branch_skips_below_confidence_threshold():
    catalog = _catalog()
    state = _state()
    rs = ResolvedConversationState(
        state=state,
        resolved_targets=(ResolvedTarget(kind="artist", source_text="x",
                                         entity_id="a-morphine", confidence=50.0),),
    )
    res = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), _disco_cfg())._compile(rs)
    traces = {p.name: [t for t, _ in p.hits] for p in res.branch_pools}
    assert "lookup.resolved_artist_discography" not in traces


def test_discography_branch_gated_off_on_pivot():
    catalog = _catalog()
    state = _state(intent_mode="pivot",
                   mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)])
    rs = _resolve(state, catalog)
    res = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), _disco_cfg())._compile(rs)
    traces = {p.name: [t for t, _ in p.hits] for p in res.branch_pools}
    assert "lookup.resolved_artist_discography" not in traces


def test_discography_branch_respects_hard_drop():
    catalog = _catalog()
    state = _state(mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)])
    rs = _resolve(state, catalog, played_track_ids=["t-morphine-1"])
    result = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), _disco_cfg()).compile(rs)
    # Played track is hard-dropped from the final candidates; the other
    # discography track is brought in.
    assert "t-morphine-1" not in result
    assert "t-morphine-2" in result


def test_routing_tags_default_false_and_settable():
    from mcrs.conversation_state.schema import (
        ConversationStateV0Plus, RoutingTags,
    )
    s = _state()
    assert isinstance(s.routing_tags, RoutingTags)
    assert s.routing_tags.lyric_search is False
    assert s.lyrical_theme is None
    s2 = _state(routing_tags=RoutingTags(lyric_search=True), lyrical_theme="heartbreak and longing")
    assert s2.routing_tags.lyric_search is True
    assert s2.lyrical_theme == "heartbreak and longing"
    # round-trips through a model_dump
    assert ConversationStateV0Plus.model_validate(s2.model_dump()).routing_tags.lyric_search is True


def test_lyric_query_uses_organizer_doc_format():
    catalog = _catalog()
    state = _state(lyrical_theme="heartbreak and city nights")
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder())
    q = compiler._build_lyric_query_string(rs)
    assert q == "music lyrics :heartbreak and city nights"


def test_lyric_query_none_without_theme():
    catalog = _catalog()
    rs = _resolve(_state(lyrical_theme=None), catalog)
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder())
    assert compiler._build_lyric_query_string(rs) is None


def test_routing_multiplier_boosts_matching_branch():
    catalog = _catalog()
    cfg = CompilerConfig(routing_boost={"lyric_search": 3.0, "exact_entity_probe": 2.0})
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), cfg)
    rs = _resolve(_state(lyrical_theme="late night loneliness"), catalog)
    assert compiler._routing_multiplier("dense.lyric", rs) == 3.0
    assert compiler._routing_multiplier("bm25", rs) == 1.0          # exact_entity_probe not set
    assert compiler._routing_multiplier("centroid.image", rs) == 1.0


def test_routing_multiplier_default_one_when_unconfigured():
    catalog = _catalog()
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder())  # no routing_boost
    rs = _resolve(
        _state(lyrical_theme="late night loneliness", retrieval_profile="exact_probe"),
        catalog,
    )
    assert compiler._routing_multiplier("dense.lyric", rs) == 1.0
    assert compiler._routing_multiplier("bm25", rs) == 1.0


def test_routing_multiplier_unmapped_kind_is_one():
    catalog = _catalog()
    cfg = CompilerConfig(routing_boost={"lyric_search": 3.0})
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), cfg)
    rs = _resolve(_state(lyrical_theme="late night loneliness"), catalog)
    assert compiler._routing_multiplier("dense.other", rs) == 1.0


def test_lyric_branch_fires_and_is_weighted_on_lyric_search():
    catalog = _catalog()
    enc = _fake_encoder()  # FakeEmbeddingClient records every embed_batch() text in `.calls`
    cfg = CompilerConfig(
        enable_dense=True,
        dense_branches=[DenseBranch(
            vector_field="lyrics_qwen3_embedding_0_6b", weight=1.0, query_id="lyric")],
        routing_boost={"lyric_search": 5.0},
        branch_trace_topk=50,
    )
    retr = FakeRetriever(embedding_hits=[("t-morphine-1", 0.9)])
    state = _state(lyrical_theme="late night loneliness")
    rs = _resolve(state, catalog)
    res = V0PlusCompiler(catalog, retr, enc, cfg)._compile(rs)
    traces = {p.name: [t for t, _ in p.hits] for p in res.branch_pools}
    assert any(k.startswith("dense.") and "lyric" in k for k in traces)
    encoded = [t for call in enc.calls for t in call]
    assert "music lyrics :late night loneliness" in encoded


# ---------------------------------------------------------------------
# Similar-artist anchoring (Fix 1, issue #74)
# ---------------------------------------------------------------------


def _sa_catalog() -> DictCatalog:
    """Catalog where the referenced artist (a-morphine) has 3 tracks of varied
    popularity WITH cf_bpr vectors, plus an other-artist track. Lets us verify
    similar-artist anchors feed the cf_bpr centroid even with no played
    anchors (turn-1 / pivot)."""
    return DictCatalog(
        tracks={
            "t-mor-1": {
                "artist_id": "a-morphine", "artist_name": "Morphine",
                "track_name": "Cure for Pain", "tag_list": ["alt-rock"],
                "popularity": 100.0, "vectors": {"cf_bpr": [1.0, 0.0]},
            },
            "t-mor-2": {
                "artist_id": "a-morphine", "artist_name": "Morphine",
                "track_name": "Buena", "tag_list": ["alt-rock"],
                "popularity": 50.0, "vectors": {"cf_bpr": [0.0, 1.0]},
            },
            "t-mor-3": {
                "artist_id": "a-morphine", "artist_name": "Morphine",
                "track_name": "Honey White", "tag_list": ["alt-rock"],
                "popularity": 10.0, "vectors": {"cf_bpr": [1.0, 1.0]},
            },
            "t-other-1": {
                "artist_id": "a-other", "artist_name": "Other Band",
                "track_name": "Other Song", "tag_list": ["pop"],
                "popularity": 75.0, "vectors": {"cf_bpr": [0.5, 0.5]},
            },
        }
    )


def _sa_rs(catalog=None, confidence=90.0, targets=None, intent_mode="open_explore",
           routing_tags=None):
    """ResolvedConversationState with NO played tracks (turn 1) and a resolved
    reference artist, mirroring the disco tests. Defaults to an intent the
    similar-artist gate ALLOWS (open_explore) so injection tests exercise
    injection; the gate itself is covered separately."""
    if targets is None:
        targets = (
            ResolvedTarget(kind="artist", source_text="Morphine",
                           entity_id="a-morphine", confidence=confidence),
        )
    state_kwargs = dict(turn_intent="more bands like Morphine", intent_mode=intent_mode)
    if routing_tags is not None:
        state_kwargs["routing_tags"] = routing_tags
    return ResolvedConversationState(
        state=_state(**state_kwargs),
        resolved_targets=tuple(targets),
    )


def _sa_cfg(**overrides):
    """Similar-artist anchoring ON, one cf_bpr centroid branch, dense OFF."""
    cfg = dict(
        enable_dense=False,
        enable_similar_artist_anchors=True,
        similar_artist_anchor_topk=3,
        similar_artist_confidence_threshold=90.0,
        similar_artist_max_artists=5,
        centroid_only_branches=[
            CentroidOnlyBranch(vector_field="cf_bpr", weight=1.0, topk=1000),
        ],
        branch_trace_topk=50,
    )
    cfg.update(overrides)
    return CompilerConfig(**cfg)


def test_similar_artist_anchors_disabled_by_default():
    # Flag off (default): no played tracks + a resolved artist must NOT produce
    # a centroid — identical to baseline (no similar-artist tracks injected).
    catalog = _sa_catalog()
    retriever = FakeRetriever(embedding_hits=[("t-mor-1", 0.9)])
    cfg = _sa_cfg(enable_similar_artist_anchors=False)
    compiler = V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg)
    rs = _sa_rs(catalog)
    assert compiler._similar_artist_anchor_track_ids(rs) == []
    compiler.compile(rs)
    # No anchors at all => centroid branch fires no embedding search.
    assert retriever.embedding_calls == []


def test_similar_artist_anchors_inject_referenced_artist_tracks():
    # Flag on, a resolved artist (conf >= 90) and NO played tracks (turn 1) =>
    # the centroid branch now PRODUCES a result from that artist's top tracks.
    import pytest

    catalog = _sa_catalog()
    retriever = FakeRetriever(embedding_hits=[("t-mor-1", 0.9)])
    compiler = V0PlusCompiler(catalog, retriever, _fake_encoder(), _sa_cfg())
    rs = _sa_rs(catalog)
    assert compiler._similar_artist_anchor_track_ids(rs) == [
        "t-mor-1", "t-mor-2", "t-mor-3",
    ]
    compiler.compile(rs)
    assert retriever.embedding_calls, "centroid branch should have fired"
    call = retriever.embedding_calls[0]
    assert call["vector_field"] == "cf_bpr"
    # Centroid is the normalized mean of the 3 injected cf_bpr vectors:
    # ([1,0] + [0,1] + [1,1]) / 3 = [2/3, 2/3] -> normalized = [1/sqrt2]*2.
    inv = 1.0 / (2.0 ** 0.5)
    assert call["query_vector"] == pytest.approx([inv, inv])


def test_similar_artist_anchors_respect_confidence_threshold():
    catalog = _sa_catalog()
    retriever = FakeRetriever(embedding_hits=[("t-mor-1", 0.9)])
    compiler = V0PlusCompiler(
        catalog, retriever, _fake_encoder(),
        _sa_cfg(similar_artist_confidence_threshold=90.0),
    )
    rs = _sa_rs(catalog, confidence=80.0)  # below threshold
    assert compiler._similar_artist_anchor_track_ids(rs) == []
    compiler.compile(rs)
    assert retriever.embedding_calls == []  # no centroid without anchors


def test_similar_artist_anchors_cap():
    # 6 artists, 4 cf_bpr-vector tracks each; cap to 2 artists x 2 tracks.
    tracks: dict[str, dict] = {}
    for ai in range(6):
        for ti in range(4):
            tracks[f"t-{ai}-{ti}"] = {
                "artist_id": f"a-{ai}", "artist_name": f"Artist {ai}",
                "track_name": f"Song {ai}-{ti}", "tag_list": ["rock"],
                "popularity": float(100 - ti),  # ti=0 most popular
                "vectors": {"cf_bpr": [1.0, 0.0]},
            }
    catalog = DictCatalog(tracks=tracks)
    retriever = FakeRetriever(embedding_hits=[("t-0-0", 0.9)])
    compiler = V0PlusCompiler(
        catalog, retriever, _fake_encoder(),
        _sa_cfg(similar_artist_max_artists=2, similar_artist_anchor_topk=2),
    )
    targets = [
        ResolvedTarget(kind="artist", source_text=f"Artist {ai}",
                       entity_id=f"a-{ai}", confidence=95.0)
        for ai in range(6)
    ]
    rs = _sa_rs(catalog, targets=targets)
    ids = compiler._similar_artist_anchor_track_ids(rs)
    # 2 artists (cap), 2 top-popularity tracks each (ti 0,1) => 4 ids.
    assert ids == ["t-0-0", "t-0-1", "t-1-0", "t-1-1"]


def test_similar_artist_anchors_do_not_change_tag_expansion():
    # Tag expansion (the tag_list BM25 channel) stays based on PLAYED anchors
    # only — similar-artist anchors are vector-centroid-only.
    catalog = _sa_catalog()
    retriever = FakeRetriever()
    compiler = V0PlusCompiler(
        catalog, retriever, _fake_encoder(), _sa_cfg(anchor_tag_expansion_n=5),
    )
    rs = _sa_rs(catalog)
    # No played anchors => no anchor tags, even though similar-artist anchors
    # exist for the centroid.
    assert compiler._top_anchor_tags(rs, 5) == []
    assert compiler._similar_artist_anchor_track_ids(rs) == [
        "t-mor-1", "t-mor-2", "t-mor-3",
    ]


def test_similar_artist_anchors_intent_gate():
    """Injection fires only when the named artist is the retrieval target this
    turn: on the allowed intents (open_explore / pivot) or an exact_entity_probe
    turn, and NOT on refinement / playlist_build (where the artist is a 'more
    like X but different' comparison)."""
    from mcrs.conversation_state.schema import RoutingTags
    catalog = _sa_catalog()
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), _sa_cfg())
    expect = ["t-mor-1", "t-mor-2", "t-mor-3"]
    # allowed intents -> inject
    for im in ("open_explore", "pivot"):
        assert compiler._similar_artist_anchor_track_ids(
            _sa_rs(catalog, intent_mode=im)) == expect
    # excluded intents -> no injection
    for im in ("refinement", "playlist_build"):
        assert compiler._similar_artist_anchor_track_ids(
            _sa_rs(catalog, intent_mode=im)) == []
    # excluded intent BUT exact_entity_probe set -> inject
    rs_eep = _sa_rs(catalog, intent_mode="refinement",
                    routing_tags=RoutingTags(exact_entity_probe=True))
    assert compiler._similar_artist_anchor_track_ids(rs_eep) == expect
    # on_exact_entity knob off -> excluded intent stays empty even with EEP
    compiler2 = V0PlusCompiler(
        catalog, FakeRetriever(), _fake_encoder(),
        _sa_cfg(similar_artist_anchor_on_exact_entity=False),
    )
    assert compiler2._similar_artist_anchor_track_ids(rs_eep) == []


def test_style_reference_resolves_for_centroid_but_not_discography():
    catalog = _sa_catalog()
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "new_artist",
            "summary": "New bands with the smoky Morphine feel, but not Morphine.",
            "source_turn": 1,
            "evidence_text": "new bands with the smoky Morphine feel",
        },
        facts=[
            {
                "type": "artist",
                "value": "Morphine",
                "role": "current_target",
                "anchor_use": "partial_anchor",
                "relation": "style_reference",
                "reuse": "avoid_exact",
                "source_turn": 1,
                "mentioned_current_turn": True,
                "evidence_text": "Morphine feel",
            },
            {
                "type": "attribute",
                "facet": "mood",
                "value": "smoky",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
                "evidence_text": "smoky",
            },
        ],
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        FakeRetriever(),
        _fake_encoder(),
        _sa_cfg(enable_resolved_artist_discography=True),
    )

    assert [(target.source_text, target.resolution_role) for target in rs.resolved_targets] == [
        ("Morphine", "style_reference"),
    ]
    assert compiler._resolved_artist_discography_pool(rs) == []
    assert compiler._similar_artist_anchor_track_ids(rs) == [
        "t-mor-1",
        "t-mor-2",
        "t-mor-3",
    ]


def test_style_reference_with_hard_exclusion_keeps_similarity_but_drops_exact_artist():
    catalog = _sa_catalog()
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "new_artist",
            "summary": "New bands with the smoky Morphine feel, but not Morphine.",
            "source_turn": 1,
            "evidence_text": "new bands with the smoky Morphine feel",
        },
        facts=[
            {
                "type": "artist",
                "value": "Morphine",
                "role": "satisfied_prior",
                "anchor_use": "do_not_use",
                "relation": "style_reference",
                "reuse": "avoid_exact",
                "source_turn": 1,
                "mentioned_current_turn": True,
                "evidence_text": "Morphine feel, but not Morphine",
            },
            {
                "type": "attribute",
                "facet": "mood",
                "value": "smoky",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
                "evidence_text": "smoky",
            },
        ],
        exclusions=[
            {
                "type": "artist",
                "value": "Morphine",
                "scope": "next_turn_hard",
                "source_turn": 1,
                "evidence_text": "but not Morphine",
            }
        ],
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        FakeRetriever(),
        _fake_encoder(),
        _sa_cfg(enable_resolved_artist_discography=True),
    )

    assert compiler._resolved_artist_discography_pool(rs) == []
    assert compiler._similar_artist_anchor_track_ids(rs) == [
        "t-mor-1",
        "t-mor-2",
        "t-mor-3",
    ]
    assert {"t-mor-1", "t-mor-2", "t-mor-3"} <= compiler._hard_drop_set(rs)


def test_attributes_query_matches_doc_format():
    catalog = _catalog()
    state = _state(mentioned_entities=[
        MentionedEntity(type="tag", value="dark", sentiment=1),
        MentionedEntity(type="tag", value="synthwave", sentiment=1),
        MentionedEntity(type="artist", value="Kavinsky", sentiment=1),
    ])
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder())
    q = compiler._build_attributes_query_string(rs)
    # mirrors the catalog doc "music attributes, tags :..."; artist excluded
    assert q == "music attributes, tags :dark, synthwave"


def test_attributes_query_can_read_v1_attribute_facts_directly():
    catalog = _catalog()
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "80s hardcore punk with raw energy and short intense songs.",
            "source_turn": 1,
        },
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "hardcore punk",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "sonic",
                "value": "raw energy",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        FakeRetriever(),
        _fake_encoder(),
        CompilerConfig(attribute_query_source="v1_attribute_facts"),
    )

    assert compiler._build_attributes_query_string(rs) == (
        "music attributes, tags :hardcore punk, raw energy"
    )


def test_attributes_query_can_filter_v1_attribute_facets():
    catalog = _catalog()
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "album covers with red and black artwork.",
            "source_turn": 1,
        },
        facts=[
            {
                "type": "attribute",
                "facet": "visual",
                "value": "red and black artwork",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "mood",
                "value": "dark",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        FakeRetriever(),
        _fake_encoder(),
        CompilerConfig(
            attribute_query_source="v1_attribute_facts",
            attribute_query_allowed_facets=("mood", "genre", "sonic"),
        ),
    )

    assert compiler._build_attributes_query_string(rs) == "music attributes, tags :dark"


def test_bm25_can_exclude_v1_attribute_facets_from_tag_list():
    catalog = _catalog()
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "80s hardcore punk with raw energy and short intense songs.",
            "source_turn": 1,
        },
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "hardcore punk",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "sonic",
                "value": "raw energy",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        FakeRetriever(),
        _fake_encoder(),
        CompilerConfig(
            bm25_include_v1_attribute_facets=False,
            bm25_include_turn_intent_tag_clause=False,
        ),
    )

    clauses = compiler._build_bm25_clauses(rs)
    tag_queries = [clause.query for clause in clauses if clause.field == "tag_list"]
    track_queries = [clause.query for clause in clauses if clause.field == "track_name"]

    assert "hardcore punk" not in tag_queries
    assert "raw energy" not in tag_queries
    assert track_queries == ["80s hardcore punk with raw energy and short intense songs."]


def test_bm25_catalog_exact_policy_keeps_only_catalog_safe_v1_attribute_tags():
    catalog = _catalog()
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "Post-hardcore with raw energy.",
            "source_turn": 1,
        },
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "post hardcore",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "sonic",
                "value": "raw energy",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        FakeRetriever(),
        _fake_encoder(),
        CompilerConfig(
            bm25_v1_attribute_tag_policy="catalog_exact",
            bm25_include_turn_intent_tag_clause=False,
        ),
    )

    clauses = compiler._build_bm25_clauses(rs)
    tag_queries = [clause.query for clause in clauses if clause.field == "tag_list"]

    assert tag_queries == ["post hardcore"]


def test_bm25_catalog_exact_policy_normalizes_v1_attribute_mentions():
    catalog = _catalog()
    state = ConversationStateV0Plus(
        mentioned_entities=[
            MentionedEntity(type="tag", value="post hardcore", sentiment=1),
            MentionedEntity(type="tag", value="raw energy", sentiment=1),
        ],
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "post-hardcore",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "sonic",
                "value": "raw-energy",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        FakeRetriever(),
        _fake_encoder(),
        CompilerConfig(
            bm25_v1_attribute_tag_policy="catalog_exact",
            bm25_include_turn_intent_tag_clause=False,
        ),
    )

    clauses = compiler._build_bm25_clauses(rs)
    tag_queries = [clause.query for clause in clauses if clause.field == "tag_list"]

    assert tag_queries == ["post-hardcore"]


def test_bm25_v1_attribute_filter_preserves_legacy_tags():
    catalog = _catalog()
    state = _state(
        turn_intent="",
        mentioned_entities=[MentionedEntity(type="tag", value="classic disco", sentiment=1)],
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        FakeRetriever(),
        _fake_encoder(),
        CompilerConfig(bm25_include_v1_attribute_facets=False),
    )

    clauses = compiler._build_bm25_clauses(rs)

    assert [clause.query for clause in clauses if clause.field == "tag_list"] == [
        "classic disco"
    ]


def test_attributes_enriched_query_adds_anchor_catalog_tags():
    catalog = _catalog()
    state = _state(
        mentioned_entities=[
            MentionedEntity(type="tag", value="dark", sentiment=1),
            MentionedEntity(type="tag", value="synthwave", sentiment=1),
            MentionedEntity(type="tag", value="heavy", sentiment=-1),
        ],
        track_feedback=[
            TrackFeedback(
                track_id="t-morphine-1",
                overall_sentiment=1,
                role="accepted",
            ),
            TrackFeedback(
                track_id="t-fugazi-1",
                overall_sentiment=1,
                role="seed",
            ),
        ],
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder())

    q = compiler._build_attributes_enriched_query_string(rs)

    assert q == (
        "music attributes, tags :dark, synthwave, smoky, lounge, "
        "post-hardcore, punk"
    )
    assert "heavy" not in q


def test_current_configs_reference_supported_dense_query_ids():
    compiler = V0PlusCompiler(_catalog(), FakeRetriever(), _fake_encoder())
    known_query_ids = set(compiler._query_builders)
    repo_root = Path(__file__).resolve().parents[1]
    branch_signatures_by_config = {}

    for config_name in (
        "v0plus_compiler_all_retrievers_devset.yaml",
        "v0plus_compiler_blindset_A.yaml",
    ):
        config = yaml.safe_load((repo_root / "configs" / config_name).read_text())
        branches = config["qu_kwargs"]["compiler"]["dense_branches"]
        unknown_query_ids = sorted(
            {branch["query_id"] for branch in branches} - known_query_ids
        )
        branch_signatures_by_config[config_name] = [
            (branch["vector_field"], branch["encoder_id"], branch["query_id"])
            for branch in branches
        ]

        assert unknown_query_ids == []

    assert (
        branch_signatures_by_config["v0plus_compiler_all_retrievers_devset.yaml"]
        == branch_signatures_by_config["v0plus_compiler_blindset_A.yaml"]
    )


def test_v1_regression_variant_configs_reference_supported_dense_query_ids():
    compiler = V0PlusCompiler(_catalog(), FakeRetriever(), _fake_encoder())
    known_query_ids = set(compiler._query_builders)
    repo_root = Path(__file__).resolve().parents[1]

    for config_name in (
        "v0plus_compiler_pruned_devset.yaml",
        "v0plus_compiler_pruned_dense_attrs_devset.yaml",
        "v0plus_compiler_pruned_safe_tags_devset.yaml",
    ):
        config_path = repo_root / "configs" / config_name
        if not config_path.exists():
            continue  # superseded smoke configs are pruned from the tree
        config = yaml.safe_load(config_path.read_text())
        branches = config["qu_kwargs"]["compiler"]["dense_branches"]
        unknown_query_ids = sorted(
            {branch["query_id"] for branch in branches} - known_query_ids
        )

        assert unknown_query_ids == []


def test_metadata_query_excludes_explicit_state_tags():
    catalog = _catalog()
    state = _state(
        turn_intent="find something similar",
        mentioned_entities=[
            MentionedEntity(type="tag", value="dark", sentiment=1),
            MentionedEntity(type="artist", value="Kavinsky", sentiment=1),
            MentionedEntity(type="album", value="Nightcall", sentiment=1),
            MentionedEntity(type="track", value="Roadgame", sentiment=1),
        ],
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder())

    q = compiler._build_metadata_query_string(rs)

    assert q == "find something similar; artists: Kavinsky; albums: Nightcall; tracks: Roadgame"
    assert "dark" not in q
    assert "tags:" not in q


def test_attributes_query_none_without_tags():
    catalog = _catalog()
    state = _state(mentioned_entities=[
        MentionedEntity(type="artist", value="Kavinsky", sentiment=1),
    ])
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder())
    assert compiler._build_attributes_query_string(rs) is None


def test_bm25_release_year_terms_skip_when_retriever_lacks_text_fields():
    state = _state(
        turn_intent="late 70s classic rock",
        temporal_constraint={
            "kind": "style_era",
            "start_year": 1977,
            "end_year": 1984,
            "strength": "soft",
            "apply_as_filter": False,
            "evidence_text": "late 70s or early 80s",
        },
    )
    rs = _resolve(state)
    compiler = V0PlusCompiler(
        _catalog(),
        NoReleaseTextFieldRetriever(),
        _fake_encoder(),
        CompilerConfig(
            enable_dense=False,
            field_boosts={
                "track_name": 3.0,
                "artist_name": 3.0,
                "album_name": 2.0,
                "tag_list": 1.5,
                "release_year": 1.0,
                "release_decade": 1.0,
            },
        ),
    )

    clauses = compiler._build_bm25_clauses(rs)

    assert "release_year" not in {clause.field for clause in clauses}
    assert "release_decade" not in {clause.field for clause in clauses}


def _era_cfg(**overrides):
    cfg = dict(enable_dense=False, enable_era_popularity=True, era_pop_cap=200,
               branch_trace_topk=50)
    cfg.update(overrides)
    return CompilerConfig(**cfg)


def test_era_popularity_pool_filters_by_year_and_orders_by_popularity():
    catalog = _catalog()
    # _catalog tracks span 1988-2010; restrict to the 1990s
    state = _state(release_year_range={"start":1990,"end":1999})
    rs = _resolve(state, catalog)
    pool = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), _era_cfg())._era_popularity_pool(rs)
    ids = [t for t, _ in pool]
    # Only 1990s tracks; ordered by popularity desc. From _catalog:
    # Tom Waits Hold On 1999 pop90, Fugazi Repeater 1990 pop60, Morphine Buena 1995 pop55
    assert ids[0] == "t-tomwaits-1"  # highest pop in-range
    assert "t-fugazi-1" not in ids   # 1988, out of range
    assert "t-filler-1" not in ids   # 2010, out of range


def test_era_popularity_pool_empty_when_disabled_or_no_range():
    catalog = _catalog()
    # disabled
    rs = _resolve(_state(release_year_range={"start":1990,"end":1999}), catalog)
    assert V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), _era_cfg(enable_era_popularity=False))._era_popularity_pool(rs) == []
    # enabled but no range
    rs2 = _resolve(_state(release_year_range=None), catalog)
    assert V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), _era_cfg())._era_popularity_pool(rs2) == []


def _scene_feature_catalog() -> DictCatalog:
    tracks: dict[str, dict] = {}
    for idx in range(20):
        tracks[f"t-generic-{idx:02d}"] = {
            "artist_id": f"a-generic-{idx:02d}",
            "artist_name": f"Generic {idx}",
            "track_name": f"Generic Rap {idx}",
            "tag_list": ["rap", "pop"],
            "popularity": 100.0 - idx,
            "release_date": "1994-01-01",
            "vectors": {"cf_bpr": [0.0, 1.0, 0.0]},
        }
    tracks["t-target"] = {
        "artist_id": "a-target",
        "artist_name": "Specific Artist",
        "track_name": "Specific Scene",
        "tag_list": ["underground hip-hop", "jazz rap"],
        "popularity": 1.0,
        "release_date": "1993-01-01",
        "vectors": {"cf_bpr": [1.0, 0.0, 0.0]},
    }
    tracks["t-anchor"] = {
        "artist_id": "a-anchor",
        "artist_name": "Anchor Artist",
        "track_name": "Anchor Track",
        "tag_list": ["underground hip-hop", "jazz rap"],
        "popularity": 50.0,
        "release_date": "1992-01-01",
        "vectors": {"cf_bpr": [1.0, 0.0, 0.0]},
    }
    return DictCatalog(tracks=tracks)


def test_branch_local_feature_rerank_is_off_by_default():
    catalog = _scene_feature_catalog()
    raw_hits = [(f"t-generic-{idx:02d}", float(100 - idx)) for idx in range(20)]
    raw_hits.append(("t-target", 1.0))
    retriever = FakeRetriever(text_hits_by_field={"track_name": raw_hits})
    state = ConversationStateV0Plus(
        turn_intent="jazzy underground hip hop from the early 90s",
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "underground hip hop",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "jazz rap",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
        release_year_range={"start": 1990, "end": 1996},
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        retriever,
        _fake_encoder(),
        CompilerConfig(enable_dense=False, branch_trace_topk=25, final_topk=25),
    )

    result = compiler._compile(rs)
    bm25 = next(pool for pool in result.branch_pools if pool.name == "bm25")

    assert [track_id for track_id, _score in bm25.hits].index("t-target") == 20
    assert all(not pool.name.endswith(".state_features") for pool in result.branch_pools)
    assert all(pool.name != "state_feature_selector" for pool in result.branch_pools)
    assert all(pool.name != "state_feature_survivor" for pool in result.branch_pools)


def test_branch_local_feature_rerank_promotes_specific_catalog_match():
    catalog = _scene_feature_catalog()
    raw_hits = [(f"t-generic-{idx:02d}", float(100 - idx)) for idx in range(20)]
    raw_hits.append(("t-target", 1.0))
    retriever = FakeRetriever(text_hits_by_field={"track_name": raw_hits})
    state = ConversationStateV0Plus(
        turn_intent="jazzy underground hip hop from the early 90s",
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "underground hip hop",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "jazz rap",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
        track_feedback=[
            TrackFeedback(track_id="t-anchor", overall_sentiment=1, role="accepted"),
        ],
        release_year_range={"start": 1990, "end": 1996},
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        retriever,
        _fake_encoder(),
        CompilerConfig(
            enable_dense=False,
            branch_trace_topk=25,
            final_topk=25,
            enable_branch_local_feature_rerank=True,
        ),
    )

    result = compiler._compile(rs)
    feature_pool = next(
        pool for pool in result.branch_pools if pool.name == "bm25.state_features"
    )
    ids = [track_id for track_id, _score in feature_pool.hits]

    assert ids.index("t-target") < 20
    assert ids[0] == "t-target"


def test_state_feature_selector_branch_promotes_deep_state_match_without_replacing_source_branch():
    catalog = _scene_feature_catalog()
    raw_hits = [(f"t-generic-{idx:02d}", float(100 - idx)) for idx in range(20)]
    raw_hits.append(("t-target", 1.0))
    retriever = FakeRetriever(text_hits_by_field={"track_name": raw_hits})
    state = ConversationStateV0Plus(
        turn_intent="jazzy underground hip hop from the early 90s",
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "underground hip hop",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "jazz rap",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
        track_feedback=[
            TrackFeedback(track_id="t-anchor", overall_sentiment=1, role="accepted"),
        ],
        release_year_range={"start": 1990, "end": 1996},
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        retriever,
        _fake_encoder(),
        CompilerConfig(
            enable_dense=False,
            branch_trace_topk=25,
            final_topk=25,
            enable_state_feature_selector_branch=True,
        ),
    )

    result = compiler._compile(rs)
    bm25 = next(pool for pool in result.branch_pools if pool.name == "bm25")
    selector = next(pool for pool in result.branch_pools if pool.name == "state_feature_selector")
    bm25_ids = [track_id for track_id, _score in bm25.hits]
    selector_ids = [track_id for track_id, _score in selector.hits]

    assert bm25_ids.index("t-target") == 20
    assert selector_ids[0] == "t-target"
    assert result.branch_queries["state_feature_selector"]["kind"] == "state_feature_selector"
    assert result.branch_queries["state_feature_selector"]["top_feature_scores"][0]["best_source_branch"] == "bm25"


def test_state_feature_survivor_branch_promotes_midrank_state_match_only():
    catalog = _scene_feature_catalog()
    raw_hits = [(f"t-generic-{idx:02d}", float(100 - idx)) for idx in range(20)]
    raw_hits.append(("t-target", 1.0))
    retriever = FakeRetriever(text_hits_by_field={"track_name": raw_hits})
    state = ConversationStateV0Plus(
        turn_intent="jazzy underground hip hop from the early 90s",
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "underground hip hop",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "jazz rap",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
        track_feedback=[
            TrackFeedback(track_id="t-anchor", overall_sentiment=1, role="accepted"),
        ],
        release_year_range={"start": 1990, "end": 1996},
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        retriever,
        _fake_encoder(),
        CompilerConfig(
            enable_dense=False,
            branch_trace_topk=25,
            final_topk=25,
            enable_state_feature_survivor_branch=True,
            state_feature_survivor_min_rank=21,
            state_feature_survivor_max_rank=25,
        ),
    )

    result = compiler._compile(rs)
    bm25 = next(pool for pool in result.branch_pools if pool.name == "bm25")
    survivor = next(pool for pool in result.branch_pools if pool.name == "state_feature_survivor")
    bm25_ids = [track_id for track_id, _score in bm25.hits]
    survivor_ids = [track_id for track_id, _score in survivor.hits]

    assert bm25_ids.index("t-target") == 20
    assert survivor_ids[0] == "t-target"
    assert result.branch_queries["state_feature_survivor"]["kind"] == "state_feature_survivor"
    assert result.branch_queries["state_feature_survivor"]["source_rank_window"] == [21, 25]
    assert result.branch_queries["state_feature_survivor"]["top_feature_scores"][0]["best_source_rank"] == 21


def test_state_feature_selector_can_group_by_source_family():
    catalog = _scene_feature_catalog()
    raw_hits = [(f"t-generic-{idx:02d}", float(100 - idx)) for idx in range(20)]
    raw_hits.append(("t-target", 1.0))
    retriever = FakeRetriever(
        text_hits_by_field={"track_name": raw_hits},
        embedding_hits=raw_hits,
    )
    state = ConversationStateV0Plus(
        turn_intent="jazzy underground hip hop from the early 90s",
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "underground hip hop",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "jazz rap",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
        track_feedback=[
            TrackFeedback(track_id="t-anchor", overall_sentiment=1, role="accepted"),
        ],
        release_year_range={"start": 1990, "end": 1996},
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        retriever,
        _fake_encoder(),
        CompilerConfig(
            enable_dense=True,
            branch_trace_topk=25,
            final_topk=25,
            dense_branches=[
                DenseBranch(
                    vector_field="metadata_qwen3_embedding_0_6b",
                    query_id="intent",
                ),
                DenseBranch(
                    vector_field="attributes_qwen3_embedding_0_6b",
                    query_id="attributes",
                ),
            ],
            enable_state_feature_selector_branch=True,
            state_feature_selector_grouping="family",
        ),
    )

    result = compiler._compile(rs)
    pools = {pool.name: [track_id for track_id, _score in pool.hits] for pool in result.branch_pools}

    assert pools["state_feature_selector.lexical"][0] == "t-target"
    assert pools["state_feature_selector.dense.intent"][0] == "t-target"
    assert pools["state_feature_selector.dense.attributes"][0] == "t-target"
    assert result.branch_queries["state_feature_selector.dense.intent"]["source_group"] == "dense.intent"


def test_branch_local_feature_rerank_can_reorder_source_branch_in_place():
    catalog = _scene_feature_catalog()
    raw_hits = [(f"t-generic-{idx:02d}", float(100 - idx)) for idx in range(20)]
    raw_hits.append(("t-target", 1.0))
    retriever = FakeRetriever(text_hits_by_field={"track_name": raw_hits})
    state = ConversationStateV0Plus(
        turn_intent="jazzy underground hip hop from the early 90s",
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "underground hip hop",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "jazz rap",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
        track_feedback=[
            TrackFeedback(track_id="t-anchor", overall_sentiment=1, role="accepted"),
        ],
        release_year_range={"start": 1990, "end": 1996},
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        retriever,
        _fake_encoder(),
        CompilerConfig(
            enable_dense=False,
            branch_trace_topk=25,
            final_topk=25,
            enable_branch_local_feature_rerank=True,
            branch_local_feature_rerank_mode="in_place",
        ),
    )

    result = compiler._compile(rs)
    bm25 = next(pool for pool in result.branch_pools if pool.name == "bm25")
    ids = [track_id for track_id, _score in bm25.hits]

    assert ids[0] == "t-target"
    assert all(not pool.name.endswith(".state_features") for pool in result.branch_pools)
    assert result.branch_queries["bm25.state_features"]["applied_mode"] == "in_place"


def test_branch_local_feature_context_is_reused_for_trace():
    catalog = _scene_feature_catalog()
    raw_hits = [(f"t-generic-{idx:02d}", float(100 - idx)) for idx in range(20)]
    raw_hits.append(("t-target", 1.0))
    retriever = FakeRetriever(text_hits_by_field={"track_name": raw_hits})
    state = ConversationStateV0Plus(
        turn_intent="jazzy underground hip hop",
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "underground hip hop",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 1,
                "mentioned_current_turn": True,
            },
        ],
    )
    rs = _resolve(state, catalog)
    compiler = V0PlusCompiler(
        catalog,
        retriever,
        _fake_encoder(),
        CompilerConfig(
            enable_dense=False,
            branch_trace_topk=25,
            final_topk=25,
            enable_branch_local_feature_rerank=True,
        ),
    )
    original_context = compiler._branch_local_feature_context
    call_count = {"n": 0}

    def counted_context(resolved_state):
        call_count["n"] += 1
        return original_context(resolved_state)

    compiler._branch_local_feature_context = counted_context

    compiler._compile(rs)

    assert call_count["n"] == 1


def _ryr_cfg(**overrides):
    cfg = dict(enable_dense=False, enable_release_year_filter=True,
               release_year_filter_min_keep=1)
    cfg.update(overrides)
    return CompilerConfig(**cfg)


def test_release_year_filter_narrows_mask_to_in_range():
    catalog = _catalog()  # tracks span 1988-2010
    rs = _resolve(
        _state(
            temporal_constraint={
                "kind": "release_date",
                "start_year": 1990,
                "end_year": 1999,
                "strength": "hard",
                "apply_as_filter": True,
                "evidence_text": "only 90s tracks",
            }
        ),
        catalog,
    )
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), _ryr_cfg())
    mask = compiler._release_date_mask(rs.state)
    # only 1990s tracks: Morphine Buena 1995, Fugazi Repeater 1990, Tom Waits 1999
    assert "t-morphine-2" in mask and "t-fugazi-2" in mask and "t-tomwaits-1" in mask
    assert "t-fugazi-1" not in mask   # 1988
    assert "t-filler-1" not in mask   # 2010


def test_release_year_filter_does_not_narrow_soft_style_era():
    catalog = _catalog()
    rs = _resolve(
        _state(
            temporal_constraint={
                "kind": "style_era",
                "start_year": 1990,
                "end_year": 1999,
                "strength": "soft",
                "apply_as_filter": False,
                "evidence_text": "90s vibe",
            }
        ),
        catalog,
    )
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), _ryr_cfg())

    mask = compiler._release_date_mask(rs.state)

    assert mask == set(catalog.all_track_ids())


def test_release_year_filter_off_by_default_keeps_all():
    catalog = _catalog()
    rs = _resolve(_state(release_year_range={"start": 1990, "end": 1999}), catalog)
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder())  # default off
    mask = compiler._release_date_mask(rs.state)
    assert mask == set(catalog.all_track_ids())


def test_release_year_filter_open_bounds():
    catalog = _catalog()
    rs = _resolve(
        _state(
            temporal_constraint={
                "kind": "release_date",
                "start_year": 2000,
                "end_year": None,
                "strength": "hard",
                "apply_as_filter": True,
                "evidence_text": "released after 2000",
            }
        ),
        catalog,
    )
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), _ryr_cfg())
    mask = compiler._release_date_mask(rs.state)
    assert mask == {"t-filler-1"}  # only 2010 is >= 2000


def test_release_year_filter_respects_hard_empty_range():
    catalog = _catalog()
    # v1 hard temporal filters are explicit user constraints, so an impossible
    # range is allowed to produce an empty candidate mask.
    rs = _resolve(
        _state(
            temporal_constraint={
                "kind": "release_date",
                "start_year": 1700,
                "end_year": 1750,
                "strength": "hard",
                "apply_as_filter": True,
                "evidence_text": "only 1700s tracks",
            }
        ),
        catalog,
    )
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(),
                              _ryr_cfg(release_year_filter_min_keep=1))
    mask = compiler._release_date_mask(rs.state)
    assert mask == set()


# ---------------------------------------------------------------------------
# bm25_v1_attribute_tag_policy = "resolved" (tiered tag resolver)
# ---------------------------------------------------------------------------


def _resolved_policy_compiler(catalog):
    return V0PlusCompiler(
        catalog,
        FakeRetriever(),
        _fake_encoder(),
        CompilerConfig(
            bm25_v1_attribute_tag_policy="resolved",
            bm25_include_turn_intent_tag_clause=False,
            tag_resolver_min_track_count=1,
        ),
    )


def _attribute_fact(facet, value):
    return {
        "type": "attribute",
        "facet": facet,
        "value": value,
        "role": "current_target",
        "anchor_use": "query_facet",
        "relation": "query_facet",
        "reuse": "not_applicable",
        "source_turn": 1,
        "mentioned_current_turn": True,
    }


def test_bm25_resolved_policy_substitutes_grounded_tags():
    catalog = _catalog()
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "Smoky lounge revival sounds.",
            "source_turn": 1,
        },
        facts=[_attribute_fact("sonic", "smoky lounge revival")],
    )
    rs = _resolve(state, catalog)
    compiler = _resolved_policy_compiler(catalog)

    clauses = compiler._build_bm25_clauses(rs)
    tag_queries = [c.query for c in clauses if c.field == "tag_list"]

    # phrase grounded via substring tier -> emits the catalog tags it
    # contains, not the raw phrase
    assert "smoky" in tag_queries
    assert "lounge" in tag_queries
    assert "smoky lounge revival" not in tag_queries


def test_bm25_resolved_policy_exact_match_normalizes():
    catalog = _catalog()
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "Post-hardcore please.",
            "source_turn": 1,
        },
        facts=[_attribute_fact("genre", "Post-Hardcore")],
    )
    rs = _resolve(state, catalog)
    compiler = _resolved_policy_compiler(catalog)

    clauses = compiler._build_bm25_clauses(rs)
    tag_queries = [c.query for c in clauses if c.field == "tag_list"]

    assert tag_queries == ["post hardcore"]


def test_bm25_resolved_policy_unresolved_phrase_keeps_raw_text():
    catalog = _catalog()
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "Driving music.",
            "source_turn": 1,
        },
        facts=[_attribute_fact("sonic", "songs about late night drives")],
    )
    rs = _resolve(state, catalog)
    compiler = _resolved_policy_compiler(catalog)

    clauses = compiler._build_bm25_clauses(rs)
    tag_queries = [c.query for c in clauses if c.field == "tag_list"]

    assert tag_queries == ["songs about late night drives"]


def test_bm25_resolved_policy_records_resolution_metadata():
    catalog = _catalog()
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "Smoky lounge revival sounds.",
            "source_turn": 1,
        },
        facts=[_attribute_fact("sonic", "smoky lounge revival")],
    )
    rs = _resolve(state, catalog)
    compiler = _resolved_policy_compiler(catalog)

    compiler._build_bm25_clauses(rs)

    assert "smoky lounge revival" in compiler._last_tag_resolutions
    matches = compiler._last_tag_resolutions["smoky lounge revival"]
    assert all(len(m) == 3 for m in matches)  # (tag, score, tier)
    tags = {m[0] for m in matches}
    assert {"smoky", "lounge"} <= tags


# ---------------------------------------------------------------------------
# 2026-06-12 bugfix batch knobs
# ---------------------------------------------------------------------------


def test_rejection_drop_policy_track_only_keeps_artist_discography():
    catalog = _catalog()
    state = _state(
        explicit_rejections=[ExplicitRejection(kind="track", value="Cure for Pain", source_turn=1)],
    )
    rs = _resolve(state, catalog)
    legacy = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(),
                            CompilerConfig(rejection_drop_policy="expanded"))
    fixed = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(),
                           CompilerConfig(rejection_drop_policy="track_only"))
    drop_legacy = legacy._resolved_rejection_drop_set(rs)
    drop_fixed = fixed._resolved_rejection_drop_set(rs)
    # legacy expands to the whole Morphine discography; track_only keeps the
    # other Morphine track alive
    assert "t-morphine-2" in drop_legacy
    assert "t-morphine-2" not in drop_fixed
    assert "t-morphine-1" in drop_fixed  # the named track itself still drops


def test_release_date_hard_filter_gate():
    catalog = _catalog()
    state = _state(hard_filters=[HardFilter(field="release_date", op="<",
                                            end="1990-01-01", source_turn=1)])
    rs = _resolve(state, catalog)
    on = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(),
                        CompilerConfig(enable_release_date_hard_filter=True))
    off = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(),
                         CompilerConfig(enable_release_date_hard_filter=False))
    assert len(off._release_date_mask(rs.state)) > len(on._release_date_mask(rs.state))


def test_strip_negated_spans():
    f = V0PlusCompiler._strip_negated_spans
    assert "experimental" not in f("something upbeat but not experimental noise rock")
    assert "upbeat" in f("something upbeat but not experimental")
    assert f("no slow ballads please") == ""or f("no slow ballads please").strip() != "slow ballads please"
    assert f("rock music") == "rock music"
