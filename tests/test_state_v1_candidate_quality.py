"""Tests for focused V1 candidate-quality analysis helpers."""

from __future__ import annotations

from types import SimpleNamespace

from mcrs.qu_modules.compiler_v0plus import BranchPool
from scripts.state_v1_candidate_quality_matrix import (
    _cosine,
    _metrics_for_subset,
    _rank_pool_with_features,
    _valid_sample_ids,
)


def test_valid_sample_ids_excludes_noisy_gt_labels():
    labels = {
        "a": {"gt_audit_label": "valid_gt_state_supports_it"},
        "b": {"gt_audit_label": "gt_conflicts_with_explicit_user_constraint"},
        "c": {"gt_audit_label": "underspecified_next_play_behavior"},
        "d": {"gt_audit_label": "valid_gt_branch_local_ranking_weak"},
    }

    assert _valid_sample_ids(labels) == {"a", "d"}


def test_metrics_for_subset_reports_all_and_valid_only_counts():
    rows = {
        "a": {"union@20": True, "union@50": True, "union@100": True},
        "b": {"union@20": False, "union@50": True, "union@100": True},
        "c": {"union@20": True, "union@50": True, "union@100": True},
    }
    labels = {
        "a": {"gt_audit_label": "valid_gt_state_supports_it"},
        "b": {"gt_audit_label": "valid_gt_branch_local_ranking_weak"},
        "c": {"gt_audit_label": "gt_conflicts_with_explicit_user_constraint"},
    }

    metrics = _metrics_for_subset(["a", "b", "c"], rows, labels)

    assert metrics["all"]["n"] == 3
    assert metrics["all"]["union@20_count"] == 2
    assert metrics["valid_only"]["n"] == 2
    assert metrics["valid_only"]["union@20_count"] == 1
    assert metrics["valid_only"]["union@50_count"] == 2


def test_rank_pool_with_features_moves_specific_match_into_top20():
    hits = [(f"generic-{idx}", 1.0 / idx) for idx in range(1, 21)]
    hits.append(("target", 1.0 / 21))
    pool = BranchPool("analysis.scene", hits)
    features = {
        "target": SimpleNamespace(feature_score=0.5, hard_drop=False),
        **{
            f"generic-{idx}": SimpleNamespace(feature_score=0.0, hard_drop=False)
            for idx in range(1, 21)
        },
    }

    reranked = _rank_pool_with_features(pool, features, suffix="hybrid")

    assert reranked.name == "analysis.scene.hybrid"
    assert [track_id for track_id, _score in reranked.hits[:1]] == ["target"]


def test_rank_pool_with_features_hard_drops_only_marked_tracks():
    pool = BranchPool("bm25", [("rejected", 1.0), ("target", 0.5)])
    features = {
        "rejected": SimpleNamespace(feature_score=5.0, hard_drop=True),
        "target": SimpleNamespace(feature_score=0.0, hard_drop=False),
    }

    reranked = _rank_pool_with_features(pool, features, suffix="guarded")

    assert [track_id for track_id, _score in reranked.hits] == ["target"]


def test_cosine_handles_missing_vectors_and_scores_aligned_vectors():
    assert _cosine(None, [1.0, 0.0]) == 0.0
    assert _cosine([1.0, 0.0], None) == 0.0
    assert _cosine([2.0, 0.0], [4.0, 0.0]) == 1.0
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
