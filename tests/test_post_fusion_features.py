"""Unit tests for the post-fusion feature framework.

Covers:
- UserFeedbackFeature: each sub-rule fires independently and composes
  multiplicatively
- SessionAnchorFeature: already_played short-circuits to 0; anchor demote
  depends on policy-driven multiplier
- PostFusionReranker: composition with weights, drop-on-zero, score order
"""
from __future__ import annotations

from mcrs.qu_modules.post_fusion_features import (
    PostFusionReranker,
    SessionAnchorFeature,
    UserFeedbackFeature,
)


class StubCatalog:
    """Minimal CatalogProtocol implementation for tests."""

    def __init__(self, artists=None, albums=None, tags=None):
        self.artists = artists or {}
        self.albums = albums or {}
        self.tags = tags or {}

    def artist_id_of(self, tid):
        return self.artists.get(tid)

    def album_id_of(self, tid):
        return self.albums.get(tid)

    def tag_list(self, tid):
        return self.tags.get(tid, [])


def _cat():
    return StubCatalog(
        artists={"t1": "morphine", "t2": "morphine", "t3": "tomwaits"},
        albums={"t1": "cfp", "t2": "cfp", "t3": "rd"},
        tags={"t1": ["rock"], "t2": ["rock", "heavy"], "t3": ["blues"]},
    )


# ---------- UserFeedbackFeature ----------


def test_user_feedback_no_rules_returns_identity():
    f = UserFeedbackFeature(name="uf")
    fv = f.compute("t1", _cat())
    assert fv.value == 1.0
    assert fv.breakdown == {}


def test_user_feedback_explicit_track_rejection_hard_zero():
    f = UserFeedbackFeature(name="uf", rejected_track_ids=frozenset(["t1"]))
    assert f.compute("t1", _cat()).value == 0.0
    assert f.compute("t2", _cat()).value == 1.0


def test_user_feedback_explicit_artist_rejection_hard_zero():
    f = UserFeedbackFeature(name="uf", rejected_artist_ids=frozenset(["morphine"]))
    assert f.compute("t1", _cat()).value == 0.0  # Morphine track
    assert f.compute("t2", _cat()).value == 0.0  # Morphine track
    assert f.compute("t3", _cat()).value == 1.0  # Tom Waits — unaffected


def test_user_feedback_inferred_artist_rejection_is_soft():
    """track_feedback.role=rejected → softer demote (default 0.7) on
    same-artist tracks, distinct from hard explicit_rejections."""
    f = UserFeedbackFeature(
        name="uf",
        inferred_rejected_artist_ids=frozenset(["morphine"]),
        inferred_artist_rejection_mult=0.7,
    )
    fv = f.compute("t1", _cat())
    assert fv.value == 0.7
    assert fv.breakdown["inferred_artist_rejection"] == 0.7


def test_user_feedback_tag_rejection_multiplicative_per_overlap():
    """0.5^overlap — t2 has 2 tags (rock, heavy), both rejected → 0.25."""
    f = UserFeedbackFeature(
        name="uf",
        rejected_tags=frozenset(["rock", "heavy"]),
        tag_rejection_per_overlap=0.5,
    )
    assert f.compute("t2", _cat()).value == 0.5 * 0.5
    assert f.compute("t1", _cat()).value == 0.5  # only 'rock' overlaps
    assert f.compute("t3", _cat()).value == 1.0  # no overlap


def test_user_feedback_positive_tag_boost():
    """(1.15)^overlap — t2 has both, gets 1.3225."""
    f = UserFeedbackFeature(
        name="uf",
        positive_tags=frozenset(["rock", "heavy"]),
        positive_tag_per_overlap=1.15,
    )
    assert f.compute("t2", _cat()).value == 1.15 * 1.15
    assert f.compute("t3", _cat()).value == 1.0


def test_user_feedback_composes_subrules_multiplicatively():
    """inferred artist demote 0.7 × positive tag boost 1.15 = 0.805."""
    f = UserFeedbackFeature(
        name="uf",
        inferred_rejected_artist_ids=frozenset(["morphine"]),
        positive_tags=frozenset(["rock"]),
    )
    fv = f.compute("t1", _cat())  # Morphine + rock
    assert fv.value == 0.7 * 1.15
    assert "inferred_artist_rejection" in fv.breakdown
    assert "positive_tag" in fv.breakdown


# ---------- SessionAnchorFeature ----------


def test_session_anchor_no_rules_returns_identity():
    f = SessionAnchorFeature(name="sa")
    assert f.compute("t1", _cat()).value == 1.0


def test_session_anchor_already_played_is_hard_zero_and_short_circuits():
    """already_played returns 0.0 and does NOT also evaluate anchor sub-rules
    (no need — the multiplier is already collapsed)."""
    f = SessionAnchorFeature(
        name="sa",
        played_track_ids=frozenset(["t1"]),
        anchor_artist_ids=frozenset(["morphine"]),
        anchor_artist_mult=0.4,
    )
    fv = f.compute("t1", _cat())
    assert fv.value == 0.0
    assert fv.breakdown == {"already_played": 0.0}  # short-circuited


def test_session_anchor_artist_demote_uses_configured_multiplier():
    f = SessionAnchorFeature(
        name="sa",
        anchor_artist_ids=frozenset(["morphine"]),
        anchor_artist_mult=0.4,
    )
    assert f.compute("t2", _cat()).value == 0.4  # Morphine, demoted
    assert f.compute("t3", _cat()).value == 1.0  # Tom Waits, unaffected


def test_session_anchor_demote_disabled_when_multiplier_is_one():
    """exploit / balanced default to 1.0 → no demote even if anchor set is populated."""
    f = SessionAnchorFeature(
        name="sa",
        anchor_artist_ids=frozenset(["morphine"]),
        anchor_artist_mult=1.0,
    )
    assert f.compute("t2", _cat()).value == 1.0


def test_session_anchor_album_demote():
    """anchor_album_mult fires on track-album-overlap (diversify_albums policy)."""
    f = SessionAnchorFeature(
        name="sa",
        anchor_album_ids=frozenset(["cfp"]),  # Morphine's 'Cure for Pain'
        anchor_album_mult=0.6,
    )
    # t1 + t2 are on the cfp album → demoted
    assert f.compute("t1", _cat()).value == 0.6
    assert f.compute("t2", _cat()).value == 0.6
    # t3 is on a different album → not affected
    assert f.compute("t3", _cat()).value == 1.0


def test_session_anchor_artist_and_album_compose_multiplicatively():
    """If both rules fire, multipliers compose: 0.4 × 0.6 = 0.24."""
    f = SessionAnchorFeature(
        name="sa",
        anchor_artist_ids=frozenset(["morphine"]),
        anchor_album_ids=frozenset(["cfp"]),
        anchor_artist_mult=0.4,
        anchor_album_mult=0.6,
    )
    fv = f.compute("t1", _cat())
    assert abs(fv.value - (0.4 * 0.6)) < 1e-9
    assert "anchor_artist" in fv.breakdown
    assert "anchor_album" in fv.breakdown


# ---------- PostFusionReranker ----------


def test_reranker_default_weights_pure_multiplicative():
    cat = _cat()
    features = [
        UserFeedbackFeature(name="uf", rejected_artist_ids=frozenset(["morphine"])),
        SessionAnchorFeature(name="sa"),
    ]
    r = PostFusionReranker(features=features)
    out = r.rerank([("t1", 0.5), ("t2", 0.3), ("t3", 0.1)], cat)
    # t1 and t2 are Morphine — filtered (multiplier 0). Only t3 survives.
    assert out == [("t3", 0.1)]


def test_reranker_weight_zero_disables_feature():
    """Setting weight=0 makes the feature a no-op without removing it."""
    cat = _cat()
    features = [UserFeedbackFeature(name="uf", rejected_artist_ids=frozenset(["morphine"]))]
    r = PostFusionReranker(features=features, weights={"uf": 0.0})
    out = r.rerank([("t1", 0.5), ("t3", 0.1)], cat)
    # With uf disabled, t1 survives (0.5 > 0.1)
    assert out == [("t1", 0.5), ("t3", 0.1)]


def test_reranker_weight_amplifies():
    """weight=2 squares the feature multiplier — a 0.5 demote becomes 0.25."""
    cat = _cat()
    features = [
        UserFeedbackFeature(
            name="uf",
            rejected_tags=frozenset(["rock"]),
            tag_rejection_per_overlap=0.5,
        )
    ]
    r = PostFusionReranker(features=features, weights={"uf": 2.0})
    out = r.rerank([("t1", 1.0), ("t3", 1.0)], cat)
    # t1 has tag 'rock' → 0.5^2 = 0.25; t3 unaffected
    by_tid = dict(out)
    assert abs(by_tid["t1"] - 0.25) < 1e-9
    assert by_tid["t3"] == 1.0


def test_reranker_trace_captures_per_feature_values():
    cat = _cat()
    features = [
        UserFeedbackFeature(name="uf", positive_tags=frozenset(["rock"])),
        SessionAnchorFeature(name="sa", played_track_ids=frozenset(["t1"])),
    ]
    r = PostFusionReranker(features=features, record_trace=True)
    r.rerank([("t1", 0.5), ("t2", 0.3), ("t3", 0.1)], cat)
    assert len(r.traces) == 3
    t1_trace = next(t for t in r.traces if t.track_id == "t1")
    # t1 is played → final 0
    assert t1_trace.final_score_out == 0.0
    # Both features still recorded for diagnostics
    names = [fv.name for fv in t1_trace.values]
    assert names == ["uf", "sa"]


def test_reranker_drops_zero_scored_tracks_from_output():
    cat = _cat()
    features = [SessionAnchorFeature(name="sa", played_track_ids=frozenset(["t1"]))]
    r = PostFusionReranker(features=features)
    out = r.rerank([("t1", 0.5), ("t2", 0.3)], cat)
    assert "t1" not in dict(out)
    assert dict(out)["t2"] == 0.3


# --- release_year_range soft date feature (extractor_prompt_v2 follow-up) ---

from mcrs.qu_modules.post_fusion_features import ReleaseYearRangeFeature


class _YearCatalog:
    def __init__(self, year): self._y = year
    def artist_id_of(self, t): return None
    def album_id_of(self, t): return None
    def tag_list(self, t): return []
    def release_year_of(self, t): return self._y


def test_release_year_feature_in_range_boosts():
    f = ReleaseYearRangeFeature(name="ryr", start_year=2010, end_year=2014)
    assert f.compute("t", _YearCatalog(2012)).value == 1.10


def test_release_year_feature_outside_decays_and_floors():
    f = ReleaseYearRangeFeature(name="ryr", start_year=2010, end_year=2014)
    assert abs(f.compute("t", _YearCatalog(2015)).value - 0.95) < 1e-9   # 1yr out
    assert f.compute("t", _YearCatalog(2050)).value == 0.6              # floored


def test_release_year_feature_noop_when_inactive_or_unknown():
    # no era -> always 1.0
    assert ReleaseYearRangeFeature(name="ryr").compute("t", _YearCatalog(2012)).value == 1.0
    # era set but candidate year unknown -> 1.0
    assert ReleaseYearRangeFeature(name="ryr", start_year=1990, end_year=1999).compute(
        "t", _YearCatalog(None)).value == 1.0


def test_release_year_feature_open_bounds():
    # "after 1900" (start only): a 2000 track is in-range, an 1850 track demoted
    f = ReleaseYearRangeFeature(name="ryr", start_year=1901, end_year=None)
    assert f.compute("t", _YearCatalog(2000)).value == 1.10
    assert f.compute("t", _YearCatalog(1850)).value == 0.6
