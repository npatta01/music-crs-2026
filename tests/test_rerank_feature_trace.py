"""Tests for reranker feature trace normalization."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RERANK_DIR = ROOT / "scripts" / "rerank"
if str(RERANK_DIR) not in sys.path:
    sys.path.insert(0, str(RERANK_DIR))

from build_features import feature_trace_view  # noqa: E402


def test_feature_trace_view_reads_state_ranker_v10_trace():
    trace = {
        "trace_schema_version": "state-ranker-v10",
        "intent_mode": "current_only",
        "extracted_state": {
            "facts": [{"type": "attribute", "value": "dream pop"}],
            "current_request": {"request_type": "similar_to"},
            "target_artist_mode": "new_artist",
        },
        "compiled_state": {
            "routing_tags": {"lyric_search": True},
        },
        "retrieval": {
            "branches": [
                {"name": "bm25", "hits": [["t1", 2.0], ["t2", 1.0]]},
                {"name": "dense", "hits": [["t3", 0.9]]},
            ],
            "branch_queries": {
                "dense": {"kind": "dense", "query_text": "dream pop shimmer"},
            },
        },
        "ranking": {
            "stages": [
                {
                    "name": "candidate_fusion",
                    "method": "weighted_rrf",
                    "track_ids": ["t3", "t1", "t2"],
                    "scores": [["t3", 0.04], ["t1", 0.03], ["t2", 0.02]],
                },
            ],
            "final_stage": "candidate_fusion",
        },
        "final_recommendation": {"track_ids": ["t3", "t1", "t2"]},
    }

    view = feature_trace_view(trace)

    assert view["state"] == trace["extracted_state"]
    assert view["routing_tags"] == {"lyric_search": True}
    assert view["intent_mode"] == "current_only"
    assert view["branches"] == {
        "pools": trace["retrieval"]["branches"],
        "branch_queries": trace["retrieval"]["branch_queries"],
        "fused": trace["ranking"]["stages"][0]["scores"],
    }


def test_feature_trace_view_filters_retrieval_hard_drops_from_feature_pools():
    trace = {
        "retrieval": {
            "hard_drop": ["played", "policy"],
            "branches": [
                {"name": "bm25", "hits": [["keep", 2.0], ["played", 1.0]]},
                {"name": "dense", "hits": [["policy", 0.8], ["also-keep", 0.7]]},
            ],
            "branch_queries": {},
        },
        "ranking": {
            "stages": [
                {
                    "name": "candidate_fusion",
                    "scores": [["played", 0.5], ["keep", 0.4], ["policy", 0.3]],
                }
            ]
        },
        "resolver": {"played_track_ids": ["played"]},
    }

    view = feature_trace_view(trace)

    assert view["branches"]["pools"] == [
        {"name": "bm25", "hits": [["keep", 2.0]]},
        {"name": "dense", "hits": [["also-keep", 0.7]]},
    ]
    assert view["branches"]["fused"] == [["keep", 0.4]]


def test_feature_trace_view_filters_inline_branch_hard_drops_from_feature_pools():
    trace = {
        "branches": {
            "hard_drop": ["played"],
            "pools": [{"name": "bm25", "hits": [["played", 2.0], ["keep", 1.0]]}],
            "branch_queries": {},
            "fused": [["played", 0.5], ["keep", 0.4]],
            "final": {"track_ids": ["played", "keep"]},
        },
        "state": {},
    }

    view = feature_trace_view(trace)

    assert view is not trace
    assert view["branches"]["pools"] == [
        {"name": "bm25", "hits": [["keep", 1.0]]}
    ]
    assert view["branches"]["fused"] == [["keep", 0.4]]
    assert view["branches"]["final"]["track_ids"] == ["keep"]


def test_feature_trace_view_preserves_existing_feature_trace():
    trace = {"branches": {"pools": [], "branch_queries": {}, "fused": []}, "state": {}}
    assert feature_trace_view(trace) is trace
