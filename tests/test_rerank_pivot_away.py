"""Block P (abandoned-direction / pivot demote) feature tests for the v0+ reranker.

Block P is the negative-pivot mirror of the e__*/anchor-match features: for each candidate it
flags resemblance (artist / album / track / tags) to the carried-forward positive ("abandoned")
tracks, so the LambdaMART model can learn `intent_mode==pivot AND resembles-abandoned => demote`.

The abandoned set is derived purely from `track_feedback` already present in every group record
(no trace regeneration), and the columns are left monotone-UNCONSTRAINED (direction flips with
intent), both of which are pinned here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mcrs.rerank.branches import BRANCH_KEYS, raw_rank_col, raw_score_col
from mcrs.rerank.features import (
    _abandoned_anchor_track_ids,
    feature_columns,
    features_from_frames,
    monotone_constraints,
)

# ----------------------------------------------------------------- synthetic catalog
# Abandoned (accepted) track t_ab: artist art-A, album alb-A, tags {rock, 90s}.
_META = {
    "t_ab": ("art-A", "alb-A", ["rock", "90s"]),          # the abandoned track itself
    "c_same_artist": ("art-A", "alb-X", ["rock"]),         # same artist, diff track
    "c_same_album": ("art-B", "alb-A", ["pop"]),           # same album, diff artist
    "c_same_tags": ("art-C", "alb-C", ["rock", "90s", "grunge"]),  # tag overlap only
    "c_unrelated": ("art-D", "alb-D", ["jazz"]),           # nothing in common
}


class _MetaCatalog:
    """Metadata-only catalog (no vector_matrix -> block H emits all-NaN, which is fine here)."""

    def all_track_ids(self):
        return list(_META)

    def artist_id_of(self, t):
        return _META.get(t, (None, None, []))[0]

    def album_id_of(self, t):
        return _META.get(t, (None, None, []))[1]

    def tag_list(self, t):
        return list(_META.get(t, (None, None, []))[2])

    def release_year_of(self, t):
        return 1995


_CANDS = ["t_ab", "c_same_artist", "c_same_album", "c_same_tags", "c_unrelated"]


def _candidates(tids=_CANDS):
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


def _group(intent_mode, track_feedback):
    return pd.DataFrame([{
        "session_id": "s", "turn_number": 1, "intent_mode": intent_mode,
        "exploration_policy": "balanced",
        "routing_tags": {k: False for k in ["exact_entity_probe", "lyric_search",
            "feature_articulation", "image_or_visual_search", "hidden_target_search"]},
        "turn_intent": "x", "has_lyrical_theme": False, "release_year_range": None,
        "n_mentioned_artists": 0, "n_mentioned_albums": 0, "n_mentioned_tracks": 0,
        "n_mentioned_tags": 0, "n_anchors": 0, "has_seed": False, "n_rejections": 0,
        "anchor_track_ids": [], "rejected_track_ids": [], "rejected_artist_ids": [],
        "rejected_tags": [], "positive_tags": [], "played_track_ids": [],
        "resolved_targets": [], "track_feedback": track_feedback,
        "branch_query_vectors": {},
        "pool_depth": {k: (len(_CANDS) if k == "bm25" else 0) for k in BRANCH_KEYS},
        "top_score": {k: (float(len(_CANDS)) if k == "bm25" else np.nan) for k in BRANCH_KEYS},
    }])


_ACCEPTED_TAB = [{"track_id": "t_ab", "role": "accepted", "overall_sentiment": 1}]


def test_abandoned_set_helper_mirrors_accepted_seed_positive():
    tf = [
        {"track_id": "a", "role": "accepted", "overall_sentiment": 1},
        {"track_id": "b", "role": "seed", "overall_sentiment": 1},
        {"track_id": "c", "role": "rejected", "overall_sentiment": -1},   # not positive
        {"track_id": "d", "role": "neutral", "overall_sentiment": 0},     # not positive
        {"track_id": "e", "role": "accepted", "overall_sentiment": 0},    # zero sentiment
    ]
    assert _abandoned_anchor_track_ids(tf) == {"a", "b"}
    assert _abandoned_anchor_track_ids([]) == set()
    assert _abandoned_anchor_track_ids(None) == set()


def test_block_p_pivot_matches_abandoned_facets():
    f = features_from_frames(_candidates(), _group("pivot", _ACCEPTED_TAB), _MetaCatalog())
    by_t = f.set_index("track_id")

    # group-constant pivot signals
    assert (f["q__is_pivot"] == 1).all()
    assert (f["q__n_abandoned_anchors"] == 1).all()

    # is_abandoned_track: only the abandoned track itself
    assert by_t.loc["t_ab", "p__is_abandoned_track"] == 1
    assert by_t.loc["c_same_artist", "p__is_abandoned_track"] == 0

    # artist match: t_ab + c_same_artist (both art-A)
    assert by_t.loc["c_same_artist", "p__artist_match_abandoned"] == 1
    assert by_t.loc["c_same_album", "p__artist_match_abandoned"] == 0

    # album match: t_ab + c_same_album (both alb-A)
    assert by_t.loc["c_same_album", "p__album_match_abandoned"] == 1
    assert by_t.loc["c_same_artist", "p__album_match_abandoned"] == 0

    # tag overlap with {rock, 90s}
    assert by_t.loc["c_same_artist", "p__tag_overlap_abandoned"] == 1   # {rock}
    assert by_t.loc["c_same_tags", "p__tag_overlap_abandoned"] == 2     # {rock, 90s}
    assert by_t.loc["c_unrelated", "p__tag_overlap_abandoned"] == 0

    # jaccard: c_same_tags has {rock,90s} of {rock,90s,grunge} = 2/3
    assert abs(by_t.loc["c_same_tags", "p__jaccard_tag_abandoned"] - 2.0 / 3.0) < 1e-9
    assert by_t.loc["c_unrelated", "p__jaccard_tag_abandoned"] == 0.0


def test_block_p_nonpivot_still_computes_set_but_flags_not_pivot():
    f = features_from_frames(_candidates(), _group("refinement", _ACCEPTED_TAB), _MetaCatalog())
    by_t = f.set_index("track_id")
    assert (f["q__is_pivot"] == 0).all()
    assert (f["q__n_abandoned_anchors"] == 1).all()
    # the abandoned (== anchor here) set is still measured off-pivot
    assert by_t.loc["c_same_artist", "p__artist_match_abandoned"] == 1


def test_block_p_empty_feedback_is_nan_safe():
    f = features_from_frames(_candidates(), _group("pivot", []), _MetaCatalog())
    assert (f["q__n_abandoned_anchors"] == 0).all()
    assert (f["p__is_abandoned_track"] == 0).all()
    assert (f["p__artist_match_abandoned"] == 0).all()
    assert (f["p__album_match_abandoned"] == 0).all()
    assert (f["p__tag_overlap_abandoned"] == 0).all()
    assert f["p__jaccard_tag_abandoned"].isna().all()  # no abandoned tags -> NaN, not 0


def test_block_p_columns_are_monotone_unconstrained():
    f = features_from_frames(_candidates(), _group("pivot", _ACCEPTED_TAB), _MetaCatalog())
    cols = feature_columns(f)
    cons = dict(zip(cols, monotone_constraints(cols)))
    block_p = [c for c in cols if c.startswith("p__")] + ["q__is_pivot", "q__n_abandoned_anchors"]
    assert block_p  # the columns exist
    for c in block_p:
        assert cons[c] == 0, c
