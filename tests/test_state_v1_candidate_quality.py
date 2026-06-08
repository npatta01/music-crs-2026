"""Tests for focused V1 candidate-quality analysis helpers."""

from __future__ import annotations

from types import SimpleNamespace

from mcrs.qu_modules.compiler_v0plus import BranchPool
from scripts.state_v1_candidate_quality_matrix import (
    CandidateFeature,
    TrackMeta,
    _branch_deep_summary,
    _branch_family,
    _branch_local_rescue_scorer_diagnostics,
    _branch_survivor_rank_ids,
    _branch_survivor_summary,
    _candidate_scorer_proxy_summary,
    _candidate_scorer_rank_map,
    _candidate_scorer_rank_ids,
    _cosine,
    _feature_scores_for_sample,
    _fusion_proxy_summary,
    _learned_listwise_proxy_summary,
    _listwise_candidate_rank_ids,
    _metrics_for_subset,
    _pool_recipe_summary,
    _rank_pool_with_features,
    _state_requests_recent_releases,
    _rrf_fuse_pool_ids,
    _state_family_weights,
    _state_weighted_fuse_pool_ids,
    _state_weighted_fusion_proxy_summary,
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


def test_rrf_fuse_pool_ids_rewards_cross_pool_agreement():
    pools = [
        BranchPool("a", [("shared", 1.0), ("solo-a", 0.9)]),
        BranchPool("b", [("solo-b", 1.0), ("shared", 0.9)]),
    ]

    fused = _rrf_fuse_pool_ids(pools, limit=3)

    assert fused[0] == "shared"
    assert set(fused) == {"shared", "solo-a", "solo-b"}


def test_fusion_proxy_summary_counts_all_and_valid_hits():
    sample_ids = ["a", "b", "c"]
    turn_meta = {
        "a": {"gt_track_id": "ta"},
        "b": {"gt_track_id": "tb"},
        "c": {"gt_track_id": "tc"},
    }
    labels = {
        "a": {"valid_gt": True},
        "b": {"valid_gt": True},
        "c": {"valid_gt": False},
    }
    variants = {
        "baseline": {
            "a": [BranchPool("bm25", [("ta", 1.0)])],
            "b": [BranchPool("bm25", [("x", 1.0), ("tb", 0.5)])],
            "c": [BranchPool("bm25", [("tc", 1.0)])],
        },
        "candidate": {
            "a": [BranchPool("bm25", [("x", 1.0)])],
            "b": [BranchPool("bm25", [("tb", 1.0)])],
            "c": [BranchPool("bm25", [("x", 1.0)])],
        },
    }

    rows = _fusion_proxy_summary(
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        labels=labels,
        variants=variants,
    )

    by_variant = {row["variant"]: row for row in rows}
    assert by_variant["baseline"]["all_proxy_final@20_count"] == 3
    assert by_variant["baseline"]["valid_proxy_final@20_count"] == 2
    assert by_variant["candidate"]["all_proxy_final@20_count"] == 1
    assert by_variant["candidate"]["valid_proxy_final@20_count"] == 1


def test_state_family_weights_boost_popularity_and_lyrics():
    state = SimpleNamespace(
        current_request=SimpleNamespace(
            request_type="attribute_search",
            summary="popular lyric driven story song",
            evidence_text="popular lyric driven story",
        ),
        facts=[
            SimpleNamespace(type="attribute", facet="popularity", relation="query_facet", role="current_target", value="popular"),
        ],
        track_feedback=[],
        referenced_track_ids=[],
        lyrical_theme="storytelling",
        target_artist_mode=None,
    )

    weights = _state_family_weights(state)

    assert weights["qwen_lyrics"] > 0.65
    assert weights["tag_scene"] > 0.82
    assert weights["era_popularity"] > 0.55


def test_state_weighted_fuse_pool_ids_applies_hard_drops_and_agreement():
    state = SimpleNamespace(
        current_request=SimpleNamespace(request_type="attribute_search", summary=""),
        facts=[],
        explicit_rejections=[
            SimpleNamespace(kind="track", entity_id="drop", certainty="explicit"),
        ],
        track_feedback=[],
        referenced_track_ids=[],
        lyrical_theme=None,
        target_artist_mode=None,
    )
    pools = [
        BranchPool("bm25", [("drop", 1.0), ("shared", 0.9), ("solo", 0.8)]),
        BranchPool("dense.qwen_8b.intent.metadata_qwen3_embedding_8b", [("shared", 1.0), ("other", 0.9)]),
    ]

    fused = _state_weighted_fuse_pool_ids(
        pools,
        state=state,
        limit=3,
        depth=10,
        agreement_bonus=0.01,
    )

    assert "drop" not in fused
    assert fused[0] == "shared"


def test_state_weighted_fusion_proxy_summary_reports_current_miss_rescues():
    sample_ids = ["a", "b"]
    turn_meta = {
        "a": {"gt_track_id": "ta"},
        "b": {"gt_track_id": "tb"},
    }
    labels = {
        "a": {"valid_gt": True},
        "b": {"valid_gt": False},
    }
    states = {
        "a": SimpleNamespace(current_request=SimpleNamespace(request_type="attribute_search", summary=""), facts=[], track_feedback=[], referenced_track_ids=[]),
        "b": SimpleNamespace(current_request=SimpleNamespace(request_type="attribute_search", summary=""), facts=[], track_feedback=[], referenced_track_ids=[]),
    }
    current_rows = {
        "a": {"union@20": False, "union@50": False, "union@100": False},
        "b": {"union@20": True, "union@50": True, "union@100": True},
    }
    variants = {
        "weighted": {
            "a": [BranchPool("bm25", [("ta", 1.0)])],
            "b": [BranchPool("bm25", [("tb", 1.0)])],
        }
    }

    rows = _state_weighted_fusion_proxy_summary(
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        labels=labels,
        states=states,
        variants=variants,
        current_rows=current_rows,
        protected_pools={},
        depths=(20,),
    )

    row = rows[0]
    assert row["all_proxy_final@20_count"] == 2
    assert row["all_current_plus_proxy@20_count"] == 2
    assert row["all_current_miss_rescue@20_count"] == 1
    assert row["valid_current_miss_rescue@20_count"] == 1


def test_candidate_scorer_rank_ids_uses_feature_evidence_over_raw_rank():
    hits = [(f"generic-{idx}", 1.0 / idx) for idx in range(1, 21)]
    hits.append(("target", 1.0 / 21))
    state = SimpleNamespace(
        current_request=SimpleNamespace(request_type="attribute_search", summary=""),
        facts=[],
        explicit_rejections=[],
        track_feedback=[],
        referenced_track_ids=[],
        lyrical_theme=None,
        target_artist_mode=None,
    )
    features = {
        track_id: CandidateFeature(feature_score=0.0, hard_drop=False)
        for track_id, _score in hits
    }
    features["target"] = CandidateFeature(feature_score=0.5, hard_drop=False)

    ranked = _candidate_scorer_rank_ids(
        [BranchPool("bm25", hits)],
        features=features,
        state=state,
        limit=20,
        depth=25,
    )

    assert ranked[0] == "target"


def test_candidate_scorer_proxy_summary_reports_additive_rescues():
    sample_ids = ["a", "b"]
    turn_meta = {
        "a": {"gt_track_id": "ta"},
        "b": {"gt_track_id": "tb"},
    }
    labels = {
        "a": {"valid_gt": True},
        "b": {"valid_gt": False},
    }
    states = {
        "a": SimpleNamespace(current_request=SimpleNamespace(request_type="attribute_search", summary=""), facts=[], track_feedback=[], referenced_track_ids=[]),
        "b": SimpleNamespace(current_request=SimpleNamespace(request_type="attribute_search", summary=""), facts=[], track_feedback=[], referenced_track_ids=[]),
    }
    current_rows = {
        "a": {"union@20": False, "union@50": False, "union@100": False},
        "b": {"union@20": True, "union@50": True, "union@100": True},
    }
    pools = {
        "a": [BranchPool("bm25", [("x", 1.0), ("ta", 0.5)])],
        "b": [BranchPool("bm25", [("tb", 1.0)])],
    }
    features = {
        "a": {
            "x": CandidateFeature(feature_score=0.0, hard_drop=False),
            "ta": CandidateFeature(feature_score=0.5, hard_drop=False),
        },
        "b": {
            "tb": CandidateFeature(feature_score=0.0, hard_drop=False),
        },
    }

    rows = _candidate_scorer_proxy_summary(
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        labels=labels,
        states=states,
        current_rows=current_rows,
        pools_by_sample=pools,
        features_by_sample=features,
        depths=(20,),
    )

    row = rows[0]
    assert row["all_scorer_final@20_count"] == 2
    assert row["all_current_plus_scorer@20_count"] == 2
    assert row["all_current_miss_rescue@20_count"] == 1
    assert row["valid_current_miss_rescue@20_count"] == 1


def test_candidate_scorer_rank_map_reports_missing_and_ranked_targets():
    sample_ids = ["a", "b"]
    turn_meta = {
        "a": {"gt_track_id": "ta"},
        "b": {"gt_track_id": "tb"},
    }
    states = {
        "a": SimpleNamespace(current_request=SimpleNamespace(request_type="attribute_search", summary=""), facts=[], track_feedback=[], referenced_track_ids=[]),
        "b": SimpleNamespace(current_request=SimpleNamespace(request_type="attribute_search", summary=""), facts=[], track_feedback=[], referenced_track_ids=[]),
    }
    pools = {
        "a": [BranchPool("bm25", [("x", 1.0), ("ta", 0.5)])],
        "b": [BranchPool("bm25", [("x", 1.0)])],
    }
    features = {
        "a": {
            "x": CandidateFeature(feature_score=0.0, hard_drop=False),
            "ta": CandidateFeature(feature_score=0.5, hard_drop=False),
        },
        "b": {"x": CandidateFeature(feature_score=0.0, hard_drop=False)},
    }

    ranks = _candidate_scorer_rank_map(
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        states=states,
        pools_by_sample=pools,
        features_by_sample=features,
        depth=20,
    )

    assert ranks == {"a": 1, "b": None}


def test_branch_local_rescue_scorer_diagnostics_buckets_rescued_rows():
    sample_ids = ["valid_rescue", "noisy_rescue", "current_hit", "still_miss"]
    turn_meta = {
        "valid_rescue": {"pack": "P0", "gt_track": "Track A", "gt_artist": "Artist A", "current_user": "more like this"},
        "noisy_rescue": {"pack": "P1", "gt_track": "Track B", "gt_artist": "Artist B", "current_user": "not that artist"},
        "current_hit": {"pack": "P0", "gt_track": "Track C", "gt_artist": "Artist C", "current_user": "play it"},
        "still_miss": {"pack": "P0", "gt_track": "Track D", "gt_artist": "Artist D", "current_user": "find it"},
    }
    labels = {
        "valid_rescue": {"valid_gt": True, "gt_audit_label": "valid_gt_branch_local_ranking_weak"},
        "noisy_rescue": {"valid_gt": False, "gt_audit_label": "gt_conflicts_with_explicit_user_constraint"},
        "current_hit": {"valid_gt": True, "gt_audit_label": "valid_gt_state_supports_it"},
        "still_miss": {"valid_gt": True, "gt_audit_label": "valid_gt_retriever_source_weak"},
    }
    baseline_rows = {
        "valid_rescue": {"union@20": False, "best_branch_rank": 46},
        "noisy_rescue": {"union@20": False, "best_branch_rank": 24},
        "current_hit": {"union@20": True, "best_branch_rank": 5},
        "still_miss": {"union@20": False, "best_branch_rank": None},
    }
    promoted_rows = {
        "valid_rescue": {"union@20": True, "best_branch_rank": 8, "best_branch": "hybrid"},
        "noisy_rescue": {"union@20": True, "best_branch_rank": 3, "best_branch": "anchor_cf"},
        "current_hit": {"union@20": True, "best_branch_rank": 4, "best_branch": "bm25"},
        "still_miss": {"union@20": False, "best_branch_rank": None, "best_branch": None},
    }
    scorer_ranks = {
        "valid_rescue": 42,
        "noisy_rescue": 10,
        "current_hit": 3,
        "still_miss": None,
    }

    diagnostics = _branch_local_rescue_scorer_diagnostics(
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        labels=labels,
        baseline_rows=baseline_rows,
        promoted_rows=promoted_rows,
        scorer_ranks=scorer_ranks,
        scorer_variant="candidate_test",
    )

    assert diagnostics["summary"] == {
        "scorer_variant": "candidate_test",
        "all_branch_local_rescues": 2,
        "valid_branch_local_rescues": 1,
        "noisy_branch_local_rescues": 1,
        "valid_scorer_top20": 0,
        "valid_scorer_21_50": 1,
        "valid_scorer_51_100": 0,
        "valid_scorer_missing": 0,
    }
    assert diagnostics["rows"][0]["sample_id"] == "valid_rescue"
    assert diagnostics["rows"][0]["scorer_rank_bucket"] == "rank_21_50"


def test_state_requests_recent_releases_from_fact_or_request_text():
    state_from_fact = SimpleNamespace(
        current_request=SimpleNamespace(request_type="new_artist", summary=""),
        facts=[
            SimpleNamespace(type="attribute", facet="era", value="recent", relation="query_facet", role="current_target"),
        ],
    )
    state_from_text = SimpleNamespace(
        current_request=SimpleNamespace(request_type="attribute_search", summary="newer contemporary pop"),
        facts=[],
    )
    oldies_state = SimpleNamespace(
        current_request=SimpleNamespace(request_type="attribute_search", summary="classic 70s rock"),
        facts=[],
    )

    assert _state_requests_recent_releases(state_from_fact)
    assert _state_requests_recent_releases(state_from_text)
    assert not _state_requests_recent_releases(oldies_state)


class _MiniCatalog:
    def __init__(self, artists: dict[str, str], vectors: dict[str, list[float]]):
        self.artists = artists
        self.vectors = vectors

    def vector(self, track_id: str, _field: str) -> list[float] | None:
        return self.vectors.get(track_id)

    def artist_id_of(self, track_id: str) -> str | None:
        return self.artists.get(track_id)


def test_feature_scores_apply_recent_release_soft_preference():
    state = SimpleNamespace(
        current_request=SimpleNamespace(request_type="attribute_search", summary="more recent upbeat scene music"),
        facts=[],
        explicit_rejections=[],
        track_feedback=[],
        referenced_track_ids=[],
        lyrical_theme=None,
        target_artist_mode=None,
    )
    track_meta = {
        "old": TrackMeta(tags=frozenset(), text="", release_year=1994, popularity_rank=None, cf_bpr=None, artist_id="old_artist"),
        "recent": TrackMeta(tags=frozenset(), text="", release_year=2018, popularity_rank=None, cf_bpr=None, artist_id="new_artist"),
    }

    features = _feature_scores_for_sample(
        state=state,
        track_meta=track_meta,
        candidate_ids={"old", "recent"},
        catalog=_MiniCatalog({}, {}),
        user_vector=None,
        mode="strict_constraints",
    )

    assert features["recent"].feature_score > features["old"].feature_score


def test_feature_scores_strongly_demote_anchor_artist_for_new_artist_request():
    state = SimpleNamespace(
        current_request=SimpleNamespace(request_type="new_artist", summary="new artist with similar energy"),
        facts=[],
        explicit_rejections=[],
        track_feedback=[SimpleNamespace(track_id="anchor", role="satisfied")],
        referenced_track_ids=[],
        lyrical_theme=None,
        target_artist_mode="new_artist",
    )
    track_meta = {
        "same_artist": TrackMeta(tags=frozenset(), text="", release_year=2020, popularity_rank=None, cf_bpr=[1.0, 0.0], artist_id="anchor_artist"),
        "other_artist": TrackMeta(tags=frozenset(), text="", release_year=2020, popularity_rank=None, cf_bpr=[1.0, 0.0], artist_id="other_artist"),
    }
    catalog = _MiniCatalog(
        artists={"anchor": "anchor_artist", "same_artist": "anchor_artist", "other_artist": "other_artist"},
        vectors={"anchor": [1.0, 0.0]},
    )

    features = _feature_scores_for_sample(
        state=state,
        track_meta=track_meta,
        candidate_ids={"same_artist", "other_artist"},
        catalog=catalog,
        user_vector=None,
        mode="strict_constraints",
    )

    assert features["other_artist"].feature_score - features["same_artist"].feature_score >= 0.05


def test_branch_survivor_rank_ids_reserves_slots_for_promoted_branch_winners():
    state = SimpleNamespace(
        current_request=SimpleNamespace(request_type="attribute_search", summary=""),
        facts=[],
        explicit_rejections=[],
        track_feedback=[],
        referenced_track_ids=[],
        lyrical_theme=None,
        target_artist_mode=None,
    )
    protected = [
        BranchPool("bm25", [(f"base-{idx}", 1.0 / idx) for idx in range(1, 21)])
    ]
    promoted = [
        BranchPool(
            "dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b.branch_local_hybrid",
            [("target", 1.0), ("branch-noise", 0.9)],
        )
    ]

    ranked = _branch_survivor_rank_ids(
        protected_pools=protected,
        survivor_pools=promoted,
        state=state,
        limit=20,
        survivor_slots=2,
        survivor_depth=20,
    )

    assert "target" in ranked[:20]
    assert ranked.index("target") < 2
    assert len(ranked) == 20


def test_branch_survivor_rank_ids_applies_explicit_hard_drops():
    state = SimpleNamespace(
        current_request=SimpleNamespace(request_type="attribute_search", summary=""),
        facts=[],
        explicit_rejections=[
            SimpleNamespace(kind="track", entity_id="drop", certainty="explicit"),
        ],
        track_feedback=[],
        referenced_track_ids=[],
        lyrical_theme=None,
        target_artist_mode=None,
    )
    protected = [BranchPool("bm25", [("keep", 1.0)])]
    promoted = [BranchPool("analysis.tag_popularity_alias.branch_local_hybrid", [("drop", 1.0), ("target", 0.9)])]

    ranked = _branch_survivor_rank_ids(
        protected_pools=protected,
        survivor_pools=promoted,
        state=state,
        limit=3,
        survivor_slots=2,
        survivor_depth=20,
    )

    assert "drop" not in ranked
    assert ranked[:2] == ["target", "keep"]


def test_branch_survivor_summary_reports_valid_current_miss_rescues():
    sample_ids = ["a", "b"]
    turn_meta = {
        "a": {"gt_track_id": "ta"},
        "b": {"gt_track_id": "tb"},
    }
    labels = {
        "a": {"valid_gt": True},
        "b": {"valid_gt": False},
    }
    states = {
        "a": SimpleNamespace(current_request=SimpleNamespace(request_type="attribute_search", summary=""), facts=[], explicit_rejections=[], track_feedback=[], referenced_track_ids=[]),
        "b": SimpleNamespace(current_request=SimpleNamespace(request_type="attribute_search", summary=""), facts=[], explicit_rejections=[], track_feedback=[], referenced_track_ids=[]),
    }
    current_rows = {
        "a": {"union@20": False, "union@50": False, "union@100": False},
        "b": {"union@20": True, "union@50": True, "union@100": True},
    }
    protected = {
        "a": [BranchPool("bm25", [("x", 1.0)])],
        "b": [BranchPool("bm25", [("tb", 1.0)])],
    }
    promoted = {
        "a": [BranchPool("analysis.tag_popularity_alias.branch_local_hybrid", [("ta", 1.0)])],
        "b": [BranchPool("analysis.tag_popularity_alias.branch_local_hybrid", [("x", 1.0)])],
    }

    rows = _branch_survivor_summary(
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        labels=labels,
        states=states,
        current_rows=current_rows,
        protected_pools=protected,
        survivor_pools=promoted,
        survivor_slots=(1,),
        survivor_depths=(20,),
    )

    row = rows[0]
    assert row["all_current_plus_survivor@20_count"] == 2
    assert row["valid_current_plus_survivor@20_count"] == 1
    assert row["all_current_miss_rescue@20_count"] == 1
    assert row["valid_current_miss_rescue@20_count"] == 1


def test_listwise_candidate_rank_ids_uses_learned_weights_and_hard_drops():
    state = SimpleNamespace(
        current_request=SimpleNamespace(request_type="attribute_search", summary=""),
        facts=[],
        explicit_rejections=[
            SimpleNamespace(kind="track", entity_id="drop", certainty="explicit"),
        ],
        track_feedback=[],
        referenced_track_ids=[],
        lyrical_theme=None,
        target_artist_mode=None,
    )
    pools = [BranchPool("bm25", [("drop", 1.0), ("target", 0.9), ("other", 0.8)])]
    features = {
        "drop": CandidateFeature(feature_score=5.0, hard_drop=True),
        "target": CandidateFeature(feature_score=1.0, hard_drop=False),
        "other": CandidateFeature(feature_score=0.0, hard_drop=False),
    }

    ranked = _listwise_candidate_rank_ids(
        pools,
        features=features,
        state=state,
        weights=[0.0, 5.0],
        mean=[0.0],
        scale=[1.0],
        limit=3,
        depth=20,
        feature_names=("candidate_feature_score",),
    )

    assert ranked == ["target", "other"]


def test_learned_listwise_proxy_summary_cross_validates_current_miss_rescue():
    sample_ids = ["a0", "a1", "b0", "b1"]
    turn_meta = {
        sid: {"gt_track_id": f"target-{sid}"}
        for sid in sample_ids
    }
    labels = {sid: {"valid_gt": True} for sid in sample_ids}
    states = {
        sid: SimpleNamespace(current_request=SimpleNamespace(request_type="attribute_search", summary=""), facts=[], explicit_rejections=[], track_feedback=[], referenced_track_ids=[])
        for sid in sample_ids
    }
    current_rows = {
        sid: {"union@20": False, "union@50": False, "union@100": False}
        for sid in sample_ids
    }
    pools = {
        sid: [BranchPool("bm25", [(f"noise-{sid}", 1.0), (f"target-{sid}", 0.9)])]
        for sid in sample_ids
    }
    features = {
        sid: {
            f"noise-{sid}": CandidateFeature(feature_score=0.0, hard_drop=False),
            f"target-{sid}": CandidateFeature(feature_score=1.0, hard_drop=False),
        }
        for sid in sample_ids
    }

    rows = _learned_listwise_proxy_summary(
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        labels=labels,
        states=states,
        current_rows=current_rows,
        pools_by_sample=pools,
        features_by_sample=features,
        variant_name="learned_test",
        depths=(20,),
        folds=2,
        feature_names=("candidate_feature_score",),
    )

    row = rows[0]
    assert row["valid_current_miss_rescue@20_count"] == 4
    assert row["valid_current_plus_listwise@20_count"] == 4
