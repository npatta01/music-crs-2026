"""Block H (dense cross-scoring) feature tests for the v0+ reranker.

Covers: cosine correctness against captured query vectors, NaN where a branch didn't fire or
a candidate lacks a vector, and byte-identical features whether the query vectors arrive as
base64 (offline trace) or plain float lists (online entry) — the train/serve parity guarantee.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mcrs.rerank.branches import (
    BRANCH_KEYS,
    CROSS_SCORE_COLS,
    parse_branch_name,
    raw_rank_col,
    raw_score_col,
    xcos_col,
)
from mcrs.rerank.features import features_from_frames
from mcrs.rerank.vec_codec import decode_branch_vectors, encode_branch_vectors


def test_parse_branch_name():
    assert parse_branch_name("dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b") == (
        "dense", None, "metadata_qwen3_embedding_0_6b")
    assert parse_branch_name("centroid.user.cf_bpr") == ("centroid", "user", "cf_bpr")
    assert parse_branch_name("centroid.anchor_tracks.audio_laion_clap") == (
        "centroid", "anchor_tracks", "audio_laion_clap")
    assert parse_branch_name("bm25") == (None, None, None)


def test_vec_codec_roundtrip_and_list_passthrough():
    enc = encode_branch_vectors({"a": [0.1, 0.2, 0.3]})
    assert isinstance(enc["a"], str)
    dec = decode_branch_vectors(enc)
    assert dec["a"].dtype == np.float32
    np.testing.assert_allclose(dec["a"], [0.1, 0.2, 0.3], atol=1e-6)
    # Online path hands plain lists straight to the decoder.
    dec2 = decode_branch_vectors({"a": [0.1, 0.2, 0.3]})
    np.testing.assert_allclose(dec2["a"], dec["a"], atol=0)


class _VecCatalog:
    """Minimal catalog exposing only what block H needs: all_track_ids, the metadata-frame
    accessors, and vector_matrix(field) -> (id_to_row, unit-norm float32 matrix)."""

    def __init__(self, vectors_by_field: dict[str, dict[str, list[float]]]):
        self._vbf = vectors_by_field
        self._ids = sorted({t for d in vectors_by_field.values() for t in d})

    def all_track_ids(self):
        return list(self._ids)

    # catalog_metadata_frame() accessors (block C/E/F); trivial here.
    def artist_id_of(self, t):
        return f"art-{t}"

    def album_id_of(self, t):
        return None

    def release_year_of(self, t):
        return 2000

    def tag_list(self, t):
        return []

    def vector_matrix(self, field):
        d = self._vbf.get(field)
        if not d:
            return (None, None)
        ids = sorted(d)
        mat = np.asarray([d[t] for t in ids], dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = mat / norms
        return ({t: i for i, t in enumerate(ids)}, mat)


def _candidates(tids):
    rows = []
    for r, t in enumerate(tids):
        row = {"session_id": "s", "turn_number": 1, "track_id": t}
        for k in BRANCH_KEYS:
            row[raw_rank_col(k)] = np.nan
            row[raw_score_col(k)] = np.nan
        row[raw_rank_col("bm25")] = r
        row[raw_score_col("bm25")] = float(len(tids) - r)
        rows.append(row)
    return pd.DataFrame(rows)


def _group(bqv):
    return pd.DataFrame([{
        "session_id": "s", "turn_number": 1, "intent_mode": "refinement",
        "exploration_policy": "balanced",
        "routing_tags": {k: False for k in ["exact_entity_probe", "lyric_search",
            "feature_articulation", "image_or_visual_search", "hidden_target_search"]},
        "turn_intent": "x", "has_lyrical_theme": False, "release_year_range": None,
        "n_mentioned_artists": 0, "n_mentioned_albums": 0, "n_mentioned_tracks": 0,
        "n_mentioned_tags": 0, "n_anchors": 0, "has_seed": False, "n_rejections": 0,
        "anchor_track_ids": [], "rejected_track_ids": [], "rejected_artist_ids": [],
        "rejected_tags": [], "positive_tags": [], "played_track_ids": [],
        "resolved_targets": [], "track_feedback": [],
        "branch_query_vectors": bqv,
        "pool_depth": {k: (len(_TIDS) if k == "bm25" else 0) for k in BRANCH_KEYS},
        "top_score": {k: (float(len(_TIDS)) if k == "bm25" else np.nan) for k in BRANCH_KEYS},
    }])


_TIDS = ["t0", "t1", "t2"]


def _catalog():
    return _VecCatalog({
        "metadata_qwen3_embedding_0_6b": {
            "t0": [1.0, 0.0, 0.0], "t1": [0.0, 1.0, 0.0], "t2": [1.0, 1.0, 0.0]},
        "cf_bpr": {"t0": [1.0, 0.0], "t1": [0.0, 1.0]},  # t2 has NO cf_bpr vector
    })


def test_block_h_cosine_correct_and_nan_when_absent():
    cat = _catalog()
    # Metadata query == t0's vector -> t0 cosine 1.0; t1 orthogonal -> 0.0.
    bqv = {"dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b": [1.0, 0.0, 0.0]}
    f = features_from_frames(_candidates(_TIDS), _group(bqv), cat)
    col = xcos_col("metadata_qwen3")
    by_t = dict(zip(f["track_id"], f[col]))
    assert abs(by_t["t0"] - 1.0) < 1e-6
    assert abs(by_t["t1"] - 0.0) < 1e-6
    assert abs(by_t["t2"] - (1.0 / np.sqrt(2))) < 1e-6
    # A branch with no captured query vector this turn -> all-NaN column.
    assert f[xcos_col("attributes_qwen3")].isna().all()


def test_block_h_nan_for_candidate_without_vector():
    cat = _catalog()
    bqv = {"centroid.user.cf_bpr": [1.0, 0.0]}
    f = features_from_frames(_candidates(_TIDS), _group(bqv), cat)
    by_t = dict(zip(f["track_id"], f[xcos_col("cf_bpr_user")]))
    assert abs(by_t["t0"] - 1.0) < 1e-6
    assert np.isnan(by_t["t2"])  # t2 lacks a cf_bpr vector


def test_block_h_offline_online_parity():
    cat = _catalog()
    bqv = {
        "dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b": [0.3, 0.7, 0.1],
        "centroid.user.cf_bpr": [0.6, 0.8],
    }
    f_online = features_from_frames(_candidates(_TIDS), _group(bqv), cat)             # lists
    f_offline = features_from_frames(_candidates(_TIDS), _group(encode_branch_vectors(bqv)), cat)  # base64
    for c in CROSS_SCORE_COLS:
        a = f_online[c].to_numpy(dtype=float)
        b = f_offline[c].to_numpy(dtype=float)
        diff = np.where(np.isnan(a) & np.isnan(b), 0.0, np.abs(a - b))
        assert np.nanmax(diff, initial=0.0) < 1e-6


def test_block_h_absent_when_no_query_vectors_column():
    # Old traces / capture off: no branch_query_vectors column -> columns present but all-NaN.
    cat = _catalog()
    g = _group({})
    g = g.drop(columns=["branch_query_vectors"])
    f = features_from_frames(_candidates(_TIDS), g, cat)
    for c in CROSS_SCORE_COLS:
        assert c in f.columns
        assert f[c].isna().all()
