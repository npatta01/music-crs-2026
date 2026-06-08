"""Tests for focused V1 candidate-quality analysis helpers."""

from __future__ import annotations

from types import SimpleNamespace

from mcrs.qu_modules.compiler_v0plus import BranchPool
from scripts.state_v1_candidate_quality_matrix import (
    _branch_deep_summary,
    _branch_family,
    _cosine,
    _metrics_for_subset,
    _pool_recipe_summary,
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


def test_branch_family_maps_known_branch_names():
    assert _branch_family("bm25") == "bm25"
    assert (
        _branch_family("dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b")
        == "qwen_attributes_enriched"
    )
    assert (
        _branch_family("centroid.anchor_tracks.image_siglip2")
        == "image_anchor_centroid"
    )
    assert _branch_family("analysis.same_album_fanout") == "same_album_fanout"


def test_branch_deep_summary_counts_hits_and_marginal_rescues():
    sample_ids = ["a", "b", "c"]
    turn_meta = {
        "a": {"gt_track_id": "ta", "pack": "P0"},
        "b": {"gt_track_id": "tb", "pack": "P0"},
        "c": {"gt_track_id": "tc", "pack": "P1"},
    }
    pools = {
        "a": [BranchPool("bm25", [("x", 1.0), ("ta", 0.5)])],
        "b": [BranchPool("bm25", [("tb", 1.0)])],
        "c": [BranchPool("bm25", [("x", 1.0)])],
    }
    protected = {
        "a": {"union@20": False, "union@50": False, "union@100": False},
        "b": {"union@20": True, "union@50": True, "union@100": True},
        "c": {"union@20": False, "union@50": False, "union@100": False},
    }

    summary = _branch_deep_summary(
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        pools_by_sample=pools,
        protected_rows=protected,
    )

    row = summary["branches"][0]
    assert row["branch"] == "bm25"
    assert row["hit@20_count"] == 2
    assert row["marginal_rescue@20_count"] == 1
    assert row["classes_helped@20"] == {"P0": 1}


def test_pool_recipe_summary_reports_unique_candidate_size_and_gt_hits():
    sample_ids = ["a", "b"]
    turn_meta = {
        "a": {"gt_track_id": "ta", "pack": "P0"},
        "b": {"gt_track_id": "tb", "pack": "P1"},
    }
    labels = {
        "a": {"gt_audit_label": "valid_gt_state_supports_it"},
        "b": {"gt_audit_label": "gt_conflicts_with_explicit_user_constraint"},
    }
    pools = {
        "a": [
            BranchPool("bm25", [("x1", 1.0), ("ta", 0.5)]),
            BranchPool("dense.qwen_8b.intent.metadata_qwen3_embedding_8b", [("x2", 1.0)]),
        ],
        "b": [BranchPool("bm25", [("tb", 1.0), ("x3", 0.5)])],
    }

    rows = _pool_recipe_summary(
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        labels=labels,
        pools_by_sample=pools,
        depths={"small": 1, "medium": 2},
    )

    assert rows[0]["recipe"] == "small"
    assert rows[0]["all_gt_in_pool_count"] == 1
    assert rows[0]["valid_gt_in_pool_count"] == 0
    assert rows[1]["recipe"] == "medium"
    assert rows[1]["all_gt_in_pool_count"] == 2
    assert rows[1]["valid_gt_in_pool_count"] == 1
