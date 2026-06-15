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
    pytest.importorskip("lance")
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
