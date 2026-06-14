"""Adapters from compiler internals to the state-ranker v10 trace shape."""

from __future__ import annotations

from typing import Any

from mcrs.qu_modules.compiler_v0plus import CompileResult


def retrieval_trace_from_compile_result(result: CompileResult) -> dict[str, Any]:
    return {
        "branches": [
            {"name": pool.name, "hits": [[track_id, float(score)] for track_id, score in pool.hits]}
            for pool in result.branch_pools
        ],
        "branch_queries": result.branch_queries,
        "branch_status": result.branch_status,
        "candidate_filter_summary": result.candidate_filter_summary,
        "trace_depth": result.depth,
        "hard_drop": list(result.hard_drop),
    }


def candidate_fusion_track_ids(result: CompileResult) -> list[str]:
    """Track ids produced by deterministic candidate fusion before learned rankers."""
    return list(result.ranked)
