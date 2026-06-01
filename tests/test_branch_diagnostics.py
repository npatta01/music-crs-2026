"""Unit tests for scripts/branch_diagnostics.py metric functions."""

from __future__ import annotations

from scripts.branch_diagnostics import (
    compute_metrics,
    final_hit_at_k,
    per_branch_recall,
    union_hit_at_k,
)


def _turn(final_ids, pools, top1=None):
    """Build a minimal `branches` dict like the trace emits."""
    return {
        "depth": 1000,
        "pools": [{"name": n, "hits": [[t, 1.0] for t in ids]} for n, ids in pools.items()],
        "fused": [[t, 1.0] for t in final_ids],
        "final": {"track_ids": final_ids, "n_from_fusion": len(final_ids), "n_from_backfill": 0},
        "recommended": {"top1_track_id": top1 if top1 is not None else (final_ids[0] if final_ids else None)},
    }


def test_final_hit_at_k():
    b = _turn(["a", "b", "c"], {})
    assert final_hit_at_k(b, "a", 1) is True
    assert final_hit_at_k(b, "c", 1) is False
    assert final_hit_at_k(b, "c", 3) is True
    assert final_hit_at_k(b, "z", 3) is False


def test_union_hit_at_k():
    b = _turn(["x"], {"bm25": ["a", "b"], "dense:f": ["c", "d"]})
    assert union_hit_at_k(b, "c", 100) is True
    assert union_hit_at_k(b, "z", 100) is False
    # cutoff applies per branch before union
    b2 = _turn(["x"], {"bm25": ["a", "b", "gt"], "dense:f": ["c"]})
    assert union_hit_at_k(b2, "gt", 2) is False  # gt is at rank 3 in bm25
    assert union_hit_at_k(b2, "gt", 3) is True


def test_per_branch_recall_only_counts_fired_branches():
    turns = [
        (_turn(["x"], {"bm25": ["gt", "a"], "dense:f": ["b"]}), "gt"),  # bm25 hits, dense misses
        (_turn(["x"], {"bm25": ["a", "b"]}), "gt"),                      # dense did NOT fire this turn
    ]
    rec = per_branch_recall(turns, ks=[100])
    # bm25 fired twice, hit once
    assert rec["bm25"]["fired"] == 2
    assert rec["bm25"]["recall@100"] == 0.5
    # dense fired once (turn 1 only), missed -> 0.0 over 1 fired turn
    assert rec["dense:f"]["fired"] == 1
    assert rec["dense:f"]["recall@100"] == 0.0


def test_compute_metrics_aggregates():
    turns = [
        (_turn(["gt", "a", "b"], {"bm25": ["gt"], "dense:f": ["a"]}), "gt"),
        (_turn(["a", "b", "gt"], {"bm25": ["a"], "dense:f": ["gt"]}), "gt"),
    ]
    m = compute_metrics(turns)
    assert m["n_turns"] == 2
    assert m["hit@1"] == 0.5           # turn1 top1=gt hit, turn2 top1=a miss
    assert m["hit@20"] == 1.0          # gt in final top-20 both turns
    assert m["hit@50"] == 1.0          # 50-slice cutoff present
    assert m["unionhit@100"] == 1.0    # gt in union both turns
    assert m["unionhit@20"] == 1.0     # union@20 cutoff present
    assert m["unionhit@50"] == 1.0     # union@50 cutoff present
    assert "fusion_efficiency@100" in m
