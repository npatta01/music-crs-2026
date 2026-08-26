"""Tests for the anchor-aware eval core (Phase 1).

Two metrics over the clean anchor labels (joined by sid,tn):
 - anchoring-violation rate@k: on asked_for_different turns, does the model's
   top-k repeat the just_played artist (deterministic name match on the model's
   recs).
 - cleaned-GT NDCG@k: single-gold NDCG averaged over turns whose clean label is
   NOT a NEGATIVE (anchoring/content) — i.e. legit turns only.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "rerank" / "anchor_labels"))

from anchor_aware_eval import (  # noqa: E402
    norm_artist,
    anchoring_hit,
    single_gold_ndcg,
    aggregate,
)


def test_norm_artist_casefold_and_strip():
    assert norm_artist("  Blake Shelton ") == norm_artist("blake shelton")
    assert norm_artist("Beyoncé") == norm_artist("beyoncé")
    assert norm_artist(None) == ""


def test_anchoring_hit_true_when_top_k_repeats_just_played():
    # top-3 artist sets; just_played = "Plaid"
    arts = [{"trifonic"}, {"plaid"}, {"boards of canada"}]
    assert anchoring_hit(arts, "plaid", k=3) is True
    assert anchoring_hit(arts, "plaid", k=1) is False  # not in top-1


def test_anchoring_hit_false_when_absent():
    arts = [{"trifonic"}, {"boards of canada"}]
    assert anchoring_hit(arts, "plaid", k=20) is False


def test_anchoring_hit_none_when_no_just_played():
    # turn-1 / no prior artist -> not a measurable pivot
    assert anchoring_hit([{"x"}], "", k=20) is None


def test_anchoring_hit_collab_counts():
    arts = [{"someone", "plaid"}]  # collab including the abandoned artist
    assert anchoring_hit(arts, "plaid", k=1) is True


def test_single_gold_ndcg():
    ranked = ["a", "b", "gold", "d"]
    import math
    assert single_gold_ndcg(ranked, "gold", k=20) == 1 / math.log2(3 + 1)
    assert single_gold_ndcg(ranked, "gold", k=2) == 0.0  # gold at rank 3, k=2
    assert single_gold_ndcg(ranked, "missing", k=20) == 0.0


def test_aggregate_violation_and_cleaned_ndcg():
    # 3 turns. t1,t2 pivot; t3 not pivot. labels: t1 NEGATIVE-anchoring, t2 POSITIVE, t3 POSITIVE
    rows = [
        # (is_pivot, anchoring_hit_bool_or_None, label_negative, ndcg)
        dict(pivot=True, hit=True, neg=True, ndcg=0.5),    # t1 anchoring viol + poisoned gold
        dict(pivot=True, hit=False, neg=False, ndcg=1.0),  # t2 clean pivot, no viol
        dict(pivot=False, hit=None, neg=False, ndcg=0.3),  # t3 non-pivot clean
    ]
    m = aggregate(rows)
    # violation rate over the 2 pivot turns: 1 of 2
    assert m["anchoring_violation_rate"] == 0.5
    assert m["n_pivot"] == 2
    # cleaned NDCG averages over non-NEGATIVE turns (t2,t3): (1.0+0.3)/2
    assert abs(m["cleaned_ndcg"] - (1.0 + 0.3) / 2) < 1e-9
    assert m["n_clean"] == 2
