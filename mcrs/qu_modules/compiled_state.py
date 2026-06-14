"""State-ranker v10 trace contract helpers.

The state-ranker trace separates LLM extraction from deterministic retrieval
policy and keeps the final user-facing recommendation independent from any
particular intermediate ranker stage.
"""

from __future__ import annotations

from typing import Any


TRACE_SCHEMA_VERSION = "state-ranker-v10"


def compiled_state_from_extracted(
    extracted_state: dict[str, Any] | None,
    *,
    resolver: dict[str, Any],
    compiler: dict[str, Any],
    ranking_mode: str,
    final_stage: str,
) -> dict[str, Any] | None:
    """Build the deterministic retrieval/ranking policy snapshot.

    This is intentionally a compact JSON-ready snapshot, not a second Pydantic
    schema that needs to stay in lockstep with the extractor.
    """
    if extracted_state is None:
        return None
    return {
        "turn_intent": extracted_state.get("turn_intent", ""),
        "intent_mode": extracted_state.get("intent_mode"),
        "target_artist_mode": extracted_state.get("target_artist_mode"),
        "retrieval_profile": extracted_state.get("retrieval_profile"),
        "process_constraints": extracted_state.get("process_constraints") or [],
        "routing_tags": extracted_state.get("routing_tags") or {},
        "hard_filters": extracted_state.get("hard_filters") or [],
        "explicit_rejections": extracted_state.get("explicit_rejections") or [],
        "anchor_policy": {
            "anchor_track_ids": list(resolver.get("anchor_track_ids") or []),
            "anchor_artist_ids": list(resolver.get("anchor_artist_ids") or []),
        },
        "rejection_policy": {
            "rejected_track_ids": list(resolver.get("rejected_track_ids") or []),
            "rejected_artist_ids": list(resolver.get("rejected_artist_ids") or []),
            "rejected_tags": list(resolver.get("rejected_tags") or []),
        },
        "candidate_policy": {
            "n_hard_filters": int(compiler.get("n_hard_filters") or 0),
            "n_explicit_rejections": int(compiler.get("n_explicit_rejections") or 0),
        },
        "ranking": {
            "mode": ranking_mode,
            "final_stage": final_stage,
        },
    }


def ranking_stage(
    name: str,
    track_ids: list[str],
    *,
    method: str,
    scores: list[tuple[str, float]] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": name,
        "method": method,
        "track_ids": list(track_ids),
    }
    if scores is not None:
        out["scores"] = [[track_id, float(score)] for track_id, score in scores]
    return out


def final_recommendation(
    track_ids: list[str],
    *,
    source_stage: str,
    ranking_mode: str,
) -> dict[str, Any]:
    return {
        "track_ids": list(track_ids),
        "primary_track_id": track_ids[0] if track_ids else None,
        "source_stage": source_stage,
        "ranking_mode": ranking_mode,
    }
