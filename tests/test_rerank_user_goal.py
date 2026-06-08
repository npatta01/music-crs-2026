"""Block U (Tier-A user/goal + Tier-B culture match) feature tests for the v0+ reranker.

Covers: pinned categoricals (goal category/specificity, gender), session_date x release_year era
interactions (track age at session, after-session anomaly, user age at release, nostalgia
window), the preferred_musical_culture x candidate-tags genre-token match, neutral output when
the session-meta join is absent (serving path), and that all block-U columns are
monotone-unconstrained.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mcrs.rerank.branches import BRANCH_KEYS, raw_rank_col, raw_score_col
from mcrs.rerank.features import (
    CATEGORICAL_FEATURES,
    _culture_tokens,
    feature_columns,
    features_from_frames,
    feature_meta,
    monotone_constraints,
)

# track_id -> (release_year, tags)
_TRACKS = {
    "old": (1990, ["classic rock", "rock"]),
    "nost": (2010, ["alternative rock", "indie"]),
    "recent": (2019, ["pop", "dance"]),
    "future": (2022, ["jazz"]),
}


class _MetaCatalog:
    def all_track_ids(self):
        return list(_TRACKS)

    def artist_id_of(self, t):
        return f"art-{t}"

    def album_id_of(self, t):
        return f"alb-{t}"

    def tag_list(self, t):
        return list(_TRACKS[t][1])

    def release_year_of(self, t):
        return _TRACKS[t][0]


_CANDS = list(_TRACKS)


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


def _group(extra=None):
    g = {
        "session_id": "s", "turn_number": 1, "intent_mode": "open_explore",
        "exploration_policy": "balanced",
        "routing_tags": {k: False for k in ["exact_entity_probe", "lyric_search",
            "feature_articulation", "image_or_visual_search", "hidden_target_search"]},
        "turn_intent": "x", "has_lyrical_theme": False, "release_year_range": None,
        "n_mentioned_artists": 0, "n_mentioned_albums": 0, "n_mentioned_tracks": 0,
        "n_mentioned_tags": 0, "n_anchors": 0, "has_seed": False, "n_rejections": 0,
        "anchor_track_ids": [], "rejected_track_ids": [], "rejected_artist_ids": [],
        "rejected_tags": [], "positive_tags": [], "played_track_ids": [],
        "resolved_targets": [], "track_feedback": [], "branch_query_vectors": {},
        "pool_depth": {k: (len(_CANDS) if k == "bm25" else 0) for k in BRANCH_KEYS},
        "top_score": {k: (float(len(_CANDS)) if k == "bm25" else np.nan) for k in BRANCH_KEYS},
    }
    if extra:
        g.update(extra)
    return pd.DataFrame([g])


_TIER_A = {"goal_category": "J", "goal_specificity": "HH", "user_gender": "male",
           "user_age": 30, "session_date": "2020-06-01",
           "user_preferred_musical_culture": "Anglo-American Rock"}


def test_culture_tokens_strips_geo_and_filler():
    assert _culture_tokens("Anglo-American Rock") == {"rock"}  # anglo-american stripped
    assert _culture_tokens("American Hip-Hop Culture") == {"hip-hop"}
    assert _culture_tokens("Western Metal Culture") == {"metal"}
    assert _culture_tokens("90s Global Pop") == {"pop"}  # era + geo stripped
    assert _culture_tokens(None) == set()
    assert _culture_tokens("Western") == set()  # pure geo -> empty


def test_block_u_group_constants_and_categoricals():
    f = features_from_frames(_candidates(), _group(_TIER_A), _MetaCatalog())
    assert (f["q__user_age"] == 30).all()
    assert (f["q__session_year"] == 2020).all()
    assert (f["q__goal_category"].astype(str) == "J").all()
    assert list(f["q__goal_specificity"].cat.categories) == ["LL", "LH", "HL", "HH"]


def test_block_u_era_interactions():
    f = features_from_frames(_candidates(), _group(_TIER_A), _MetaCatalog())
    by_t = f.set_index("track_id")
    assert by_t.loc["nost", "u__track_age_at_session"] == 10
    assert by_t.loc["nost", "u__user_age_at_release"] == 20
    assert by_t.loc["nost", "u__release_in_formative_window"] == 1
    assert by_t.loc["old", "u__release_in_formative_window"] == 0
    assert by_t.loc["future", "u__released_after_session"] == 1
    assert by_t.loc["future", "u__track_age_at_session"] == -2


def test_block_u_culture_match():
    # culture "Anglo-American Rock" -> {rock}; matches rock-tagged tracks only.
    f = features_from_frames(_candidates(), _group(_TIER_A), _MetaCatalog())
    by_t = f.set_index("track_id")
    assert by_t.loc["old", "u__culture_tag_match"] == 1     # "classic rock","rock"
    assert by_t.loc["nost", "u__culture_tag_match"] == 1    # "alternative rock"
    assert by_t.loc["old", "u__culture_tag_overlap"] == 1   # only the "rock" token
    assert by_t.loc["recent", "u__culture_tag_match"] == 0  # pop/dance
    assert by_t.loc["future", "u__culture_tag_match"] == 0  # jazz


def test_block_u_neutral_when_session_meta_absent():
    f = features_from_frames(_candidates(), _group(), _MetaCatalog())
    for c in ["q__user_age", "q__session_year", "u__track_age_at_session",
              "u__released_after_session", "u__user_age_at_release",
              "u__release_in_formative_window", "u__culture_tag_overlap", "u__culture_tag_match"]:
        assert f[c].isna().all(), c
    assert f["q__goal_category"].isna().all()


def test_block_u_unseen_category_is_nan():
    f = features_from_frames(_candidates(), _group({**_TIER_A, "goal_category": "Z"}), _MetaCatalog())
    assert f["q__goal_category"].isna().all()


def test_block_u_registered_categoricals_and_monotone_zero():
    f = features_from_frames(_candidates(), _group(_TIER_A), _MetaCatalog())
    meta = feature_meta(f)
    for c in ["q__goal_category", "q__goal_specificity", "q__user_gender"]:
        assert c in CATEGORICAL_FEATURES
        assert c in meta["categorical_features"]
    cols = feature_columns(f)
    cons = dict(zip(cols, monotone_constraints(cols)))
    block_u = [c for c in cols if c.startswith("u__")] + \
              ["q__user_age", "q__session_year", "q__goal_category",
               "q__goal_specificity", "q__user_gender"]
    for c in block_u:
        assert cons[c] == 0, c
