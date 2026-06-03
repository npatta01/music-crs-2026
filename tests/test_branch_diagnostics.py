"""Unit tests for scripts/branch_diagnostics.py metric functions."""

from __future__ import annotations

import json as _json

import pytest

from scripts.branch_diagnostics import (
    align_turns,
    compute_metrics,
    compute_metrics_streaming,
    final_hit_at_k,
    load_ground_truth,
    load_trace,
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


def test_align_turns_matches_on_session_and_turn():
    trace = [
        {"session_id": "s1", "turn_number": 1, "trace": {"branches": {"final": {"track_ids": ["gt"]},
            "recommended": {"top1_track_id": "gt"}, "pools": [], "fused": [], "depth": 1000}}},
        {"session_id": "s1", "turn_number": 2, "trace": {"branches": {"final": {"track_ids": ["x"]},
            "recommended": {"top1_track_id": "x"}, "pools": [], "fused": [], "depth": 1000}}},
    ]
    gt = [
        {"session_id": "s1", "turn_number": 1, "ground_truth_track_id": "gt"},
        {"session_id": "s1", "turn_number": 2, "ground_truth_track_id": "y"},
        {"session_id": "s9", "turn_number": 1, "ground_truth_track_id": "z"},  # no trace -> skipped
    ]
    aligned = align_turns(trace, load_ground_truth(gt))
    assert len(aligned) == 2
    assert aligned[0][1] == "gt"
    assert aligned[1][1] == "y"


def test_load_trace_rejects_missing_branches(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text(_json.dumps({"session_id": "s1", "turn_number": 1, "trace": {"state": {}}}) + "\n")
    with pytest.raises(SystemExit) as exc:
        load_trace(str(p), require_branches=True)
    assert exc.value.code == 2


def test_load_trace_reads_jsonl(tmp_path):
    p = tmp_path / "t.jsonl"
    rows = [
        {"session_id": "s1", "turn_number": 1, "trace": {"branches": {"final": {"track_ids": ["gt"]}}}},
        {"session_id": "s1", "turn_number": 2, "trace": {"branches": {"final": {"track_ids": ["x"]}}}},
    ]
    # trailing blank line must be tolerated
    p.write_text("\n".join(_json.dumps(r) for r in rows) + "\n\n")
    loaded = load_trace(str(p), require_branches=True)
    assert loaded == rows


def test_failure_turn_counts_as_miss():
    """A turn with empty/falsy branches (extractor failure -> no candidates)
    stays in the scored denominator and counts as a miss, so hit@k /
    unionhit@k are not overstated."""
    hit = _turn(["gt", "a"], {"bm25": ["gt"]})
    turns = [(hit, "gt"), ({}, "gt")]  # second turn = extractor failure
    m = compute_metrics(turns)
    assert m["n_turns"] == 2
    assert m["n_failed_no_branches"] == 1
    assert m["hit@1"] == 0.5         # 1 hit / 2 turns (failure scored as miss)
    assert m["hit@20"] == 0.5
    assert m["unionhit@100"] == 0.5
    # failure turn contributes nothing to any branch's fired count
    assert m["per_branch"]["bm25"]["fired"] == 1


def test_streaming_matches_in_memory(tmp_path):
    """compute_metrics_streaming (one pass, O(1) memory) must produce the same
    metrics as compute_metrics(align_turns(...)) on the same data."""
    rows = [
        {"session_id": "s1", "turn_number": 1,
         "trace": {"branches": _turn(["gt", "a", "b"], {"bm25": ["gt"], "dense:f": ["a"]})}},
        {"session_id": "s1", "turn_number": 2,
         "trace": {"branches": _turn(["a", "b", "gt"], {"bm25": ["a"], "dense:f": ["gt"]})}},
        {"session_id": "s1", "turn_number": 3, "trace": {"state": None}},   # extractor failure
        {"session_id": "s9", "turn_number": 1,
         "trace": {"branches": _turn(["x"], {"bm25": ["x"]})}},            # no GT -> skipped
    ]
    trace_path = tmp_path / "t_trace.jsonl"
    trace_path.write_text("\n".join(_json.dumps(r) for r in rows) + "\n")
    gt_records = [
        {"session_id": "s1", "turn_number": 1, "ground_truth_track_id": "gt"},
        {"session_id": "s1", "turn_number": 2, "ground_truth_track_id": "gt"},
        {"session_id": "s1", "turn_number": 3, "ground_truth_track_id": "miss"},
    ]
    gt = load_ground_truth(gt_records)

    streamed = compute_metrics_streaming(str(trace_path), gt)
    reference = compute_metrics(align_turns(rows, gt))

    for key in ("n_turns", "n_failed_no_branches", "hit@1", "hit@20",
                "unionhit@100", "unionhit@1000", "fusion_efficiency@100"):
        assert streamed.get(key) == reference.get(key), key
    assert streamed["n_turns"] == 3            # 2 real + 1 failure; s9 (no GT) excluded
    assert streamed["n_skipped_no_gt"] == 1    # s9
    assert streamed["per_branch"] == reference["per_branch"]


def test_align_turns_keeps_branchless_row_as_miss():
    """A v0+ trace row with NO `branches` key (extractor returned None) but a
    valid GT must be aligned as an empty-branches miss, not dropped."""
    trace = [
        {"session_id": "s1", "turn_number": 1, "trace": {"branches": {
            "final": {"track_ids": ["gt"]}, "recommended": {"top1_track_id": "gt"},
            "pools": [{"name": "bm25", "hits": [["gt", 1.0]]}], "fused": [], "depth": 50}}},
        {"session_id": "s1", "turn_number": 2, "trace": {"state": None}},  # extractor failure
        {"session_id": "s9", "turn_number": 1, "trace": {"branches": {}}},  # no GT -> skipped
    ]
    gt = [
        {"session_id": "s1", "turn_number": 1, "ground_truth_track_id": "gt"},
        {"session_id": "s1", "turn_number": 2, "ground_truth_track_id": "miss"},
    ]
    aligned = align_turns(trace, load_ground_truth(gt))
    assert len(aligned) == 2                 # both s1 turns; s9 (no GT) dropped
    assert aligned[1][0] == {}               # branchless failure -> empty dict
    m = compute_metrics(aligned)
    assert m["n_turns"] == 2
    assert m["n_failed_no_branches"] == 1
    assert m["hit@1"] == 0.5                 # turn1 hits, turn2 (failure) misses
