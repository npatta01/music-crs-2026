from __future__ import annotations

import numpy as np
import pytest

from mcrs.qu_modules import lgbm_reranker
from mcrs.qu_modules.lgbm_reranker import _FeatureCatalogFromCompilerCatalog
from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog


class _CompilerCatalogSource:
    def __init__(self):
        self._rows = {
            "t-one": {
                "track_id": "t-one",
                "track_name": "Blue Smoke",
                "artist_name": ["The Example"],
                "artist_id": ["a-example"],
                "album_id": ["al-example"],
                "tag_list": ["smoky jazz", "late night"],
                "popularity": 25.0,
                "release_date": "1999-01-02",
                "duration": 180000,
            },
            "t-two": {
                "track_id": "t-two",
                "track_name": "Hard Pivot",
                "artist_name": ["Other Band"],
                "artist_id": ["a-other"],
                "album_id": ["al-other"],
                "tag_list": ["punk"],
                "popularity": 75.0,
                "release_date": "2005-03-04",
                "duration": 210000,
            },
        }
        self.vector_calls = []

    def feature_rows(self):
        return dict(self._rows)

    def vector(self, track_id: str, vector_field: str):
        self.vector_calls.append((track_id, vector_field))
        if track_id == "t-one" and vector_field == "metadata_qwen3_embedding_0_6b":
            return [3.0, 4.0]
        return None


def test_feature_catalog_adapter_reuses_compiler_metadata_and_vectors():
    source = _CompilerCatalogSource()

    catalog = _FeatureCatalogFromCompilerCatalog(source)

    assert set(catalog.meta) == {"t-one", "t-two"}
    assert catalog.meta["t-one"]["artists"] == ("a-example",)
    assert catalog.meta["t-one"]["albums"] == ("al-example",)
    assert catalog.meta["t-one"]["year"] == 1999
    assert catalog.meta["t-one"]["n_tags"] == 2
    assert catalog.artist_track_count["a-example"] == 1
    assert catalog.median_year == 2002
    assert catalog.median_duration == 195000.0

    np.testing.assert_allclose(
        catalog.v("metadata_qwen3_embedding_0_6b", "t-one"),
        np.array([0.6, 0.8], dtype=np.float32),
    )
    np.testing.assert_allclose(
        catalog.v("metadata_qwen3_embedding_0_6b", "t-one"),
        np.array([0.6, 0.8], dtype=np.float32),
    )
    assert source.vector_calls == [("t-one", "metadata_qwen3_embedding_0_6b")]
    assert catalog.v("metadata_qwen3_embedding_0_6b", "missing") is None


def test_feature_catalog_adapter_uses_public_feature_rows_accessor():
    source = _CompilerCatalogSource()
    rows = source._rows
    source.feature_rows = lambda: rows
    del source._rows

    catalog = _FeatureCatalogFromCompilerCatalog(source)

    assert set(catalog.meta) == {"t-one", "t-two"}


def test_catalog_selection_falls_back_only_for_unsupported_sources():
    calls = []

    class OfflineCatalog:
        def __init__(self, db_uri, table_name):
            calls.append((db_uri, table_name))

    catalog = lgbm_reranker._load_feature_catalog(
        catalog_source=object(),
        offline_catalog_cls=OfflineCatalog,
        db_uri="db",
        table_name="tracks",
    )

    assert isinstance(catalog, OfflineCatalog)
    assert calls == [("db", "tracks")]


def test_catalog_selection_does_not_treat_private_rows_as_supported():
    calls = []

    class PrivateRowsOnly:
        _per_track = {"t-one": {}}

    class OfflineCatalog:
        def __init__(self, db_uri, table_name):
            calls.append((db_uri, table_name))

    catalog = lgbm_reranker._load_feature_catalog(
        catalog_source=PrivateRowsOnly(),
        offline_catalog_cls=OfflineCatalog,
        db_uri="db",
        table_name="tracks",
    )

    assert isinstance(catalog, OfflineCatalog)
    assert calls == [("db", "tracks")]


def test_catalog_selection_does_not_swallow_adapter_type_errors(monkeypatch):
    source = _CompilerCatalogSource()
    expected = TypeError("adapter bug")

    def boom(_source):
        raise expected

    monkeypatch.setattr(lgbm_reranker, "_FeatureCatalogFromCompilerCatalog", boom)

    with pytest.raises(TypeError) as exc_info:
        lgbm_reranker._load_feature_catalog(
            catalog_source=source,
            offline_catalog_cls=lambda *_args: object(),
            db_uri="db",
            table_name="tracks",
        )

    assert exc_info.value is expected


def _unit(values):
    vec = np.asarray(values, dtype=np.float32)
    return vec / max(float(np.linalg.norm(vec)), 1e-9)


class _StaticEmbeddings:
    def get_many(self, texts, offline=False):
        return {text: _unit([1.0, 1.0]) for text in texts if text}


class _StaticTagResolver:
    def resolve(self, phrase):
        tag = str(phrase).strip().lower()
        if tag not in {"bright", "warm", "calm"}:
            return type("ResolvedTags", (), {"matches": []})()
        match = type("ResolvedTagMatch", (), {
            "tag": tag,
            "score": 1.0,
            "tier": "exact",
        })()
        return type("ResolvedTags", (), {"matches": [match]})()


class _RecordingBooster:
    def __init__(self):
        self.calls = []

    def predict(self, features):
        self.calls.append(features.copy())
        return np.nan_to_num(features[:, 0], nan=-1.0)


def _make_synthetic_lgbm_reranker(cat):
    from features_v9 import TurnContext

    reranker = lgbm_reranker.LgbmOnlineReranker.__new__(lgbm_reranker.LgbmOnlineReranker)
    reranker.ctx = TurnContext(
        cat,
        sessions={},
        user_cf={},
        resolver=_StaticTagResolver(),
        tag_vec={
            "bright": _unit([1.0, 1.0]),
            "warm": _unit([0.0, 1.0]),
            "calm": _unit([1.0, 0.0]),
        },
        memo=_StaticEmbeddings(),
        msg_store=_StaticEmbeddings(),
        branch_names=["bm25"],
        pool_k=3,
        offline=True,
    )
    reranker.cols = [
        "pop_pct",
        "era_pop_pct",
        "within_artist_pop",
        "release_year",
        "tag_count",
        "cf_last",
        "cf_centroid",
        "cf_drift",
        "clap_last",
        "clap_centroid",
        "siglip_centroid",
        "same_artist_session",
        "same_album_last",
        "tag_overlap_idf",
        "tag_emb_cos",
        "msg_meta_cos",
        "msg_attr_cos",
        "msg_lyr_cos",
        "ctx_meta_cos",
        "q06_lyric_cos",
        "rank__bm25",
        "score__bm25",
        "margin__bm25",
        "ratio__bm25",
        "hit__bm25",
    ]
    reranker.cat_maps = {}
    reranker.booster = _RecordingBooster()
    reranker.top_k_out = 3
    return reranker


def test_feature_catalog_adapter_matches_offline_catalog_rerank_outputs(tmp_path):
    pytest.importorskip("lancedb")
    import lancedb
    from build_features import Catalog

    db_uri = str(tmp_path / "lancedb")
    table_name = "music_track_catalog"
    rows = [
        {
            "track_id": "t-low",
            "track_name": "Low Song",
            "artist_name": ["Artist A"],
            "artist_id": ["artist-a"],
            "album_name": ["Album A"],
            "album_id": ["album-a"],
            "tag_list": ["calm"],
            "popularity": 10.0,
            "release_date": "2001-01-01",
            "duration": 180000,
            "cf_bpr": [1.0, 0.0],
            "audio_laion_clap": [1.0, 0.0],
            "image_siglip2": [1.0, 0.0],
            "metadata_qwen3_embedding_0_6b": [1.0, 0.0],
            "attributes_qwen3_embedding_0_6b": [1.0, 0.0],
            "lyrics_qwen3_embedding_0_6b": [1.0, 0.0],
        },
        {
            "track_id": "t-mid",
            "track_name": "Mid Song",
            "artist_name": ["Artist B"],
            "artist_id": ["artist-b"],
            "album_name": ["Album B"],
            "album_id": ["album-b"],
            "tag_list": ["warm"],
            "popularity": 50.0,
            "release_date": "2005-01-01",
            "duration": 210000,
            "cf_bpr": [0.0, 1.0],
            "audio_laion_clap": [0.0, 1.0],
            "image_siglip2": [0.0, 1.0],
            "metadata_qwen3_embedding_0_6b": [0.0, 1.0],
            "attributes_qwen3_embedding_0_6b": [0.0, 1.0],
            "lyrics_qwen3_embedding_0_6b": [0.0, 1.0],
        },
        {
            "track_id": "t-high",
            "track_name": "High Song",
            "artist_name": ["Artist C"],
            "artist_id": ["artist-c"],
            "album_name": ["Album C"],
            "album_id": ["album-c"],
            "tag_list": ["bright"],
            "popularity": 90.0,
            "release_date": "2010-01-01",
            "duration": 240000,
            "cf_bpr": [0.7, 0.7],
            "audio_laion_clap": [0.7, 0.7],
            "image_siglip2": [0.7, 0.7],
            "metadata_qwen3_embedding_0_6b": [0.7, 0.7],
            "attributes_qwen3_embedding_0_6b": [0.7, 0.7],
            "lyrics_qwen3_embedding_0_6b": [0.7, 0.7],
        },
    ]
    db = lancedb.connect(db_uri)
    db.create_table(table_name, data=rows)

    compiler_catalog = LanceDbCatalog(
        db_uri=db_uri,
        table_name=table_name,
        eager_vector_fields=(
            "cf_bpr",
            "audio_laion_clap",
            "image_siglip2",
            "metadata_qwen3_embedding_0_6b",
            "attributes_qwen3_embedding_0_6b",
            "lyrics_qwen3_embedding_0_6b",
        ),
    )
    adapter_reranker = _make_synthetic_lgbm_reranker(
        _FeatureCatalogFromCompilerCatalog(compiler_catalog)
    )
    offline_reranker = _make_synthetic_lgbm_reranker(Catalog(db_uri, table_name))
    trace = {
        "branches": {
            "pools": [
                {
                    "name": "bm25",
                    "hits": [("t-low", 3.0), ("t-mid", 2.0), ("t-high", 1.0)],
                }
            ],
            "fused": [("t-low", 3.0), ("t-mid", 2.0), ("t-high", 1.0)],
            "branch_queries": {
                "lyric": {"kind": "dense", "query_text": "bright request"}
            },
        },
        "state": {
            "facts": [{"type": "attribute", "value": "bright"}],
            "current_request": {"request_type": "mood"},
        },
        "resolver": {"played_track_ids": [], "positive_tags": ["bright"]},
    }
    fallback = ["t-low", "t-mid", "t-high"]
    expected_ranked = ["t-high", "t-mid", "t-low"]

    for index in range(10):
        session_meta = {
            "session_id": f"session-{index}",
            "turn_number": 3,
            "session_date": "2020-01-01",
            "conversations": [
                {"role": "user", "content": "play something warm", "turn_number": 1},
                {"role": "music", "content": "t-mid", "turn_number": 1},
                {"role": "user", "content": "a calmer follow up", "turn_number": 2},
                {"role": "music", "content": "t-low", "turn_number": 2},
                {"role": "user", "content": f"bright request {index}", "turn_number": 3},
            ],
            "user_profile": {"age": 36, "age_group": "adult", "gender": "unknown"},
            "conversation_goal": {
                "category": "discovery",
                "specificity": "specific",
                "listener_goal": "bright request",
            },
        }

        adapter_ranked = adapter_reranker.rerank(
            trace, session_meta, user_id=f"user-{index}", hard_drop=set(), fallback=fallback
        )
        offline_ranked = offline_reranker.rerank(
            trace, session_meta, user_id=f"user-{index}", hard_drop=set(), fallback=fallback
        )

        assert adapter_ranked == expected_ranked
        assert offline_ranked == expected_ranked
        np.testing.assert_allclose(
            adapter_reranker.booster.calls[-1],
            offline_reranker.booster.calls[-1],
            equal_nan=True,
        )


def test_abandoned_sets_fires_on_pivot_satisfied_and_rejected_artist():
    """On a pivot, prior *satisfied* artists are abandoned (what the user is
    leaving), and explicitly rejected artist UUIDs are added directly. Matching is
    by artist_id (UUID), not name-key — the catalog id<->name arrays aren't
    reliably pair-aligned."""
    from features_v9 import _abandoned_sets
    from mcrs.qu_modules.tag_resolver import catalog_tag_key

    catalog = _FeatureCatalogFromCompilerCatalog(_CompilerCatalogSource())
    state = {
        "target_artist_mode": "new_artist",
        "track_feedback": [
            {"track_id": "t-one", "role": "satisfied", "overall_sentiment": 1},
        ],
    }
    resolver_block = {"rejected_artist_ids": ["a-other"], "rejected_tags": ["punk"]}

    artist_ids, tags = _abandoned_sets(state, resolver_block, catalog)

    assert "a-example" in artist_ids  # prior satisfied artist, left on pivot
    assert "a-other" in artist_ids    # explicitly rejected artist (id added directly)
    assert catalog_tag_key("punk") in tags


def test_abandoned_sets_keeps_satisfied_artist_when_not_pivot():
    """Continuation turn: a satisfied artist is what the user wants MORE of — it
    must NOT be added to the abandoned set."""
    from features_v9 import _abandoned_sets

    catalog = _FeatureCatalogFromCompilerCatalog(_CompilerCatalogSource())
    state = {
        "target_artist_mode": "same_artist",
        "track_feedback": [
            {"track_id": "t-one", "role": "satisfied", "overall_sentiment": 1},
        ],
    }

    artist_ids, _ = _abandoned_sets(state, {}, catalog)

    assert "a-example" not in artist_ids


def test_abandoned_sets_fires_on_negative_feedback_regardless_of_pivot():
    """A negatively-rated track's artist is abandoned even on a non-pivot turn."""
    from features_v9 import _abandoned_sets

    catalog = _FeatureCatalogFromCompilerCatalog(_CompilerCatalogSource())
    state = {
        "target_artist_mode": "same_artist",
        "track_feedback": [
            {"track_id": "t-two", "role": "rejected", "overall_sentiment": -1},
        ],
    }

    artist_ids, _ = _abandoned_sets(state, {}, catalog)

    assert "a-other" in artist_ids


def test_pivot_abandoned_features_parity_and_liveness(tmp_path):
    """Real-trace parity + liveness on a PIVOT trace.

    Online (compiler-catalog adapter) and offline (Catalog) feature computation
    must agree per-candidate per-feature, AND the pivot-away features must FIRE
    (track_feedback + rejected_artist_ids + rejected_tags present). Both were
    silently ~0 before the artist-key fixes; this guards against the next
    regression that lets them go dead, and against online/offline drift."""
    import math
    import numbers

    pytest.importorskip("lancedb")
    import lancedb
    from build_features import Catalog
    from features_v9 import compute_turn_features

    db_uri = str(tmp_path / "lancedb")
    table_name = "music_track_catalog"

    def _row(tid, name, artist_id, artist_name, tag, pop, year, v):
        return {
            "track_id": tid, "track_name": name,
            "artist_name": [artist_name], "artist_id": [artist_id],
            "album_name": [f"al-{tid}"], "album_id": [f"album-{tid}"],
            "tag_list": [tag], "popularity": pop,
            "release_date": f"{year}-01-01", "duration": 200000,
            "cf_bpr": v, "audio_laion_clap": v, "image_siglip2": v,
            "metadata_qwen3_embedding_0_6b": v,
            "attributes_qwen3_embedding_0_6b": v,
            "lyrics_qwen3_embedding_0_6b": v,
        }

    rows = [
        _row("t-low", "Low", "artist-a", "Artist A", "calm", 10.0, 2001, [1.0, 0.0]),
        _row("t-mid", "Mid", "artist-b", "Artist B", "warm", 50.0, 2005, [0.0, 1.0]),
        _row("t-high", "High", "artist-c", "Artist C", "bright", 90.0, 2010, [0.7, 0.7]),
    ]
    lancedb.connect(db_uri).create_table(table_name, data=rows)

    eager = ("cf_bpr", "audio_laion_clap", "image_siglip2",
             "metadata_qwen3_embedding_0_6b", "attributes_qwen3_embedding_0_6b",
             "lyrics_qwen3_embedding_0_6b")
    online_ctx = _make_synthetic_lgbm_reranker(
        _FeatureCatalogFromCompilerCatalog(
            LanceDbCatalog(db_uri=db_uri, table_name=table_name, eager_vector_fields=eager))
    ).ctx
    offline_ctx = _make_synthetic_lgbm_reranker(Catalog(db_uri, table_name)).ctx

    trace = {
        "branches": {
            "pools": [{"name": "bm25", "hits": [("t-low", 3.0), ("t-mid", 2.0), ("t-high", 1.0)]}],
            "fused": [("t-low", 3.0), ("t-mid", 2.0), ("t-high", 1.0)],
            "branch_queries": {"lyric": {"kind": "dense", "query_text": "bright request"}},
        },
        "state": {
            "facts": [{"type": "attribute", "value": "bright"}],
            "current_request": {"request_type": "mood"},
            "target_artist_mode": "new_artist",
            "track_feedback": [{"track_id": "t-mid", "role": "satisfied", "overall_sentiment": 1}],
        },
        "resolver": {
            "played_track_ids": [],
            "rejected_artist_ids": ["artist-a"],
            "rejected_tags": ["calm"],
        },
    }
    row = {"session_id": "s1", "turn_number": 3, "user_id": "u1", "trace": trace}

    online_rows, _ = compute_turn_features(row, online_ctx, gt=None)
    offline_rows, _ = compute_turn_features(row, offline_ctx, gt=None)
    on = {r["track_id"]: r for r in online_rows}
    off = {r["track_id"]: r for r in offline_rows}
    assert set(on) == set(off) == {"t-low", "t-mid", "t-high"}

    def _eq(x, y):
        if isinstance(x, numbers.Real) and isinstance(y, numbers.Real):
            if math.isnan(x) and math.isnan(y):
                return True
            return math.isclose(float(x), float(y), rel_tol=1e-6, abs_tol=1e-9)
        return x == y

    for tid in on:
        assert set(on[tid]) == set(off[tid]), tid
        for key in on[tid]:
            assert _eq(on[tid][key], off[tid][key]), \
                f"online/offline skew on {tid}.{key}: {on[tid][key]!r} != {off[tid][key]!r}"

    # liveness — abandoned-artist + abandoned-tag features must fire (were ~0 before the fix)
    assert on["t-mid"]["same_artist_as_abandoned"] == 1.0   # satisfied Artist B, left on pivot
    assert on["t-low"]["same_artist_as_abandoned"] == 1.0   # Artist A explicitly rejected (UUID resolved)
    assert on["t-high"]["same_artist_as_abandoned"] == 0.0
    assert on["t-low"]["tag_overlap_abandoned"] >= 1.0      # 'calm' rejected tag matches t-low


def test_constraint_feature_row_shared_helper():
    """Pin the shared sidecar helper used by both the online reranker and the
    offline build_constraint_features (parity by construction)."""
    from build_features import constraint_feature_row

    assert constraint_feature_row(
        "t1", ("a1", "a2"), played={"t1"}, rejected_tracks={"t9"},
        rejected_artists={"a2"}, target_artist_mode="new_artist",
        same_artist_session=1.0) == {
            "is_played_track": 1.0, "rejected_track_exact": 0.0,
            "rejected_artist_exact": 1.0, "violates_new_artist": 1.0}

    assert constraint_feature_row(
        "t2", ("b1",), played=set(), rejected_tracks={"t2"},
        rejected_artists=set(), target_artist_mode="same_artist",
        same_artist_session=1.0) == {
            "is_played_track": 0.0, "rejected_track_exact": 1.0,
            "rejected_artist_exact": 0.0, "violates_new_artist": 0.0}

    # pivot but not same-artist -> no violation
    assert constraint_feature_row(
        "t3", ("c1",), played=set(), rejected_tracks=set(),
        rejected_artists=set(), target_artist_mode="different_artist",
        same_artist_session=0.0)["violates_new_artist"] == 0.0


@pytest.mark.parametrize(
    "intent_mode,target_artist_mode,expected",
    [
        # intent_mode arm fires regardless of artist mode
        ("pivot", "unknown", True),
        ("pivot", "same_artist", True),
        # artist-mode arm: "new" / "different" substrings fire
        ("open_explore", "new_artist", True),
        ("refinement", "different_artist", True),
        ("open_explore", "different", True),
        # neither arm -> not a pivot
        ("open_explore", "same_artist", False),
        ("refinement", "unknown", False),
        ("open_explore", "", False),
        # robustness: None inputs must not raise and must be False
        (None, None, False),
        (None, "same_artist", False),
        ("open_explore", None, False),
    ],
)
def test_is_pivot_turn_gate(intent_mode, target_artist_mode, expected):
    """The shared pivot gate: pivot iff intent_mode=='pivot' OR
    target_artist_mode contains 'new'/'different'. Single source of truth for
    both the offline training-row filter and the online router."""
    from features_v9 import is_pivot_turn

    assert is_pivot_turn(intent_mode, target_artist_mode) is expected


def test_pivot_mask_from_codes_matches_gate():
    """The training-row pivot mask is derived from the categorical CODE columns
    already encoded in X.npy (alignment-guaranteed, no parquet rescan). It must
    reproduce is_pivot_turn applied to the decoded values, via either arm."""
    from train_v9 import pivot_mask_from_codes

    cols = ["pool_rank", "intent_mode", "popularity", "target_artist_mode"]
    cat_maps = {
        "intent_mode": {"open_explore": 0, "pivot": 1, "refinement": 2},
        "target_artist_mode": {"unknown": 0, "new_artist": 1, "same_artist": 2},
    }
    # rows: (intent_code, tam_code) -> expected pivot
    #  0: pivot, unknown        -> True  (intent arm)
    #  1: open_explore, new     -> True  (artist-mode arm)
    #  2: open_explore, same    -> False
    #  3: refinement, unknown   -> False
    X = np.array(
        [
            [9.0, 1, 0.5, 0],
            [9.0, 0, 0.5, 1],
            [9.0, 0, 0.5, 2],
            [9.0, 2, 0.5, 0],
        ],
        dtype=np.float32,
    )

    mask = pivot_mask_from_codes(X, cols, cat_maps)

    assert mask.dtype == bool
    assert mask.tolist() == [True, True, False, False]


def test_select_feature_columns_remaps_indices_and_categoricals():
    """Restricting training to a feature subset must map names->full-matrix
    column positions (in subset order) and re-express categorical indices
    relative to the subset, so LightGBM gets the right cat columns."""
    from train_v9 import select_feature_columns

    cols = ["a", "b", "c", "d", "e"]
    cat_idx = [1, 3]  # b, d are categorical in the full matrix
    subset = ["c", "d", "a"]  # pick a non-contiguous, reordered subset

    col_indices, sub_cols, sub_cat_idx = select_feature_columns(cols, cat_idx, subset)

    assert col_indices == [2, 3, 0]      # positions of c, d, a in full matrix
    assert sub_cols == ["c", "d", "a"]   # preserved subset order
    assert sub_cat_idx == [1]            # only "d" (subset position 1) is categorical


@pytest.mark.parametrize(
    "scores,gt_score,expected",
    [
        ([0.9, 0.5, 0.3], 0.9, 1.0),    # unique top -> rank 1 (matches old behavior)
        ([0.9, 0.8, 0.7], 0.7, 3.0),    # GT below two -> rank 3
        ([0.9, 0.9, 0.3], 0.9, 1.5),    # GT tied with one at top -> expected 1.5
        ([0.5, 0.5, 0.5, 0.5], 0.5, 2.5),  # constant scorer -> middle, NOT rank 1
    ],
)
def test_gt_tie_averaged_rank(scores, gt_score, expected):
    """Expected GT rank under random tie-breaking: n_greater + (n_tied+1)/2.
    Unique GT reduces to the old (n_greater+1); ties no longer collapse to
    best-case rank 1, so a constant scorer can't game the metric."""
    from train_v9 import gt_tie_averaged_rank
    import numpy as np

    assert gt_tie_averaged_rank(np.array(scores), gt_score) == expected


def test_training_feature_subset_all_excludes_dropped():
    """'all' trains on every column EXCEPT DROPPED_FEATURES (order preserved);
    a dropped column not present in the matrix is simply a no-op."""
    import train_v9

    cols = ["a", "wants_new_artist", "b", "c"]
    assert train_v9.training_feature_subset(cols, "all") == ["a", "b", "c"]
    # dropped feature absent -> unchanged
    assert train_v9.training_feature_subset(["a", "b"], "all") == ["a", "b"]


def test_training_feature_subset_pivot_uses_pivot_list_and_drops_wna():
    """'pivot' trains on PIVOT_FEATURES restricted to available columns, and
    wants_new_artist must no longer be in that list."""
    import train_v9

    assert "wants_new_artist" not in train_v9.PIVOT_FEATURES
    cols = list(train_v9.PIVOT_FEATURES) + ["unrelated"]
    assert train_v9.training_feature_subset(cols, "pivot") == list(train_v9.PIVOT_FEATURES)


@pytest.mark.parametrize(
    "is_gt,gt_moves,is_future,expected",
    [
        (True, True, False, 3),    # GT that moved toward goal -> strongest positive
        (True, False, False, 1),   # GT that did NOT move toward goal -> weak positive
        (False, False, True, 2),   # non-GT track played later in the session (proxy good)
        (False, False, False, 0),  # ordinary non-GT candidate
        (True, True, True, 3),     # GT takes precedence over future membership
        (False, True, True, 2),    # gt_moves is irrelevant for non-GT rows
    ],
)
def test_graded_label(is_gt, gt_moves, is_future, expected):
    """Graded relevance: GT&moves=3, future-played proxy=2, GT&not-moves=1, else 0.
    Mirrors the binary->graded upgrade (GT noise + reward for good alternatives)."""
    from train_v9 import graded_label

    assert graded_label(is_gt, gt_moves, is_future) == expected


def test_artist_recency_in_session():
    """Turns since the candidate's artist was last played BEFORE the current turn;
    sentinel when never played. Graded novelty for pivots."""
    from train_v9 import artist_recency_in_session

    played = {1: {"A"}, 2: {"B"}, 3: {"A", "C"}}
    # A last played at turn 3 -> recency 1 at turn 4
    assert artist_recency_in_session({"A"}, played, 4, sentinel=99) == 1
    # B last at turn 2 -> recency 2 at turn 4
    assert artist_recency_in_session({"B"}, played, 4, sentinel=99) == 2
    # never played -> sentinel
    assert artist_recency_in_session({"Z"}, played, 4, sentinel=99) == 99
    # only count plays strictly BEFORE the turn: C first appears AT turn 3
    assert artist_recency_in_session({"C"}, played, 3, sentinel=99) == 99
    # A at turn 1 is before turn 2
    assert artist_recency_in_session({"A"}, played, 2, sentinel=99) == 1
