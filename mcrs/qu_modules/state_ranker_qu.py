"""State-ranker v10 QU surface.

This module owns the public v10 contract:
extract state -> compile retrieval policy -> retrieve branch pools -> run ranking
stages -> publish one canonical final_recommendation object.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from mcrs.qu_modules.compiled_state import (
    TRACE_SCHEMA_VERSION,
    compiled_state_from_extracted,
    final_recommendation,
    ranking_stage,
)
from mcrs.qu_modules.compiler_v0plus import CompileResult
from mcrs.qu_modules.compiler_v0plus_qu import (
    V0PlusCompilerQU,
    build_v0plus_compiler_qu,
    session_memory_to_conversation,
)
from mcrs.qu_modules.retrieval_compiler import (
    candidate_fusion_track_ids,
    retrieval_trace_from_compile_result,
)
from mcrs.response_context import response_state_dict

logger = logging.getLogger(__name__)


_LGBM_REQUIRED_KEYS = {
    "model_path",
    "meta_path",
    "cat_maps",
    "branch_names",
    "tag_index",
    "embed_memo",
    "msg_store",
}


@dataclass
class StateRankerQU(V0PlusCompilerQU):
    """State-ranker v10 QU, backed by the existing branch retrieval engine."""

    ranking_mode: str = "rrf"
    model_version: str = "candidate_fusion"
    final_stage: str = "candidate_fusion"

    def compile_track_ids(
        self,
        session_memory: list[dict[str, Any]],
        topk: int = 1000,
        user_id: str | None = None,
    ) -> list[str]:
        return self.batch_compile_track_ids(
            [session_memory],
            topk=topk,
            user_ids=[user_id],
        )[0]

    async def _acompile_one(
        self,
        idx: int,
        session_memory: list[dict[str, Any]],
        topk: int,
        sem: asyncio.Semaphore,
        user_id: str | None = None,
        session_meta: dict[str, Any] | None = None,
    ) -> tuple[int, list[str], dict[str, Any]]:
        conv, played = session_memory_to_conversation(session_memory, self.catalog)
        async with sem:
            state = await self.extractor.aextract(conv, played)
        if state is None:
            trace = {
                "trace_schema_version": TRACE_SCHEMA_VERSION,
                "idx": idx,
                "extracted_state": None,
                "compiled_state": None,
                "retrieval": {"branches": []},
                "ranking": {"stages": [], "final_stage": None},
                "final_recommendation": final_recommendation(
                    [], source_stage="", ranking_mode=self.ranking_mode
                ),
                "compiler": {"extractor_returned_none": True},
            }
            return idx, [], trace

        rs = self.resolver.resolve(state, played_track_ids=played)

        def _run_compile() -> CompileResult:
            return self.compiler._compile(rs, user_id=user_id)

        compile_result = await asyncio.to_thread(_run_compile)
        candidate_track_ids = candidate_fusion_track_ids(compile_result)

        rejected_track_ids: list[str] = []
        rejected_artist_ids: list[str] = []
        for rej in rs.resolved_rejections.values():
            rejected_track_ids.extend(rej.track_ids)
            rejected_artist_ids.extend(rej.artist_ids)
        for tf in state.track_feedback:
            if tf.role == "rejected":
                aid = rs.track_feedback_artist_ids.get(tf.track_id)
                if aid is not None:
                    rejected_artist_ids.append(aid)
        resolver_block = {
            "anchor_track_ids": [
                tf.track_id
                for tf in state.track_feedback
                if tf.role in ("accepted", "seed") and tf.overall_sentiment > 0
            ]
            + list(state.referenced_track_ids),
            "anchor_artist_ids": [
                me.value
                for me in state.mentioned_entities
                if me.sentiment > 0 and me.type == "artist" and me.value
            ],
            "rejected_track_ids": rejected_track_ids,
            "rejected_artist_ids": rejected_artist_ids,
            "rejected_tags": [
                er.value for er in state.explicit_rejections if er.kind == "tag" and er.value
            ],
            "positive_tags": [
                me.value
                for me in state.mentioned_entities
                if me.sentiment > 0 and me.type == "tag" and me.value
            ],
            "played_track_ids": list(rs.played_track_ids),
        }

        compiler_summary = {
            "n_candidates": min(len(candidate_track_ids), topk),
            "n_hard_filters": len(state.hard_filters),
            "n_explicit_rejections": len(state.explicit_rejections),
        }
        extracted_state = response_state_dict(state)
        compiled_state = compiled_state_from_extracted(
            extracted_state,
            resolver=resolver_block,
            compiler=compiler_summary,
            ranking_mode=self.ranking_mode,
            final_stage=self.final_stage,
        )
        retrieval = retrieval_trace_from_compile_result(compile_result)

        stages = [
            ranking_stage(
                "candidate_fusion",
                candidate_track_ids,
                method="weighted_rrf",
                scores=compile_result.fused,
            )
        ]
        served_track_ids = list(candidate_track_ids)

        if self.ranking_mode == "lgbm":
            rr = self._get_reranker()
            if rr is not None:
                served_track_ids = await asyncio.to_thread(
                    rr.rerank,
                    {
                        "trace_schema_version": TRACE_SCHEMA_VERSION,
                        "extracted_state": extracted_state,
                        "compiled_state": compiled_state,
                        "state": extracted_state,
                        "intent_mode": getattr(state.intent_mode, "value", str(state.intent_mode)),
                        "resolver": resolver_block,
                        "routing_tags": extracted_state.get("routing_tags") or {},
                        "retrieval": retrieval,
                        "branches": {
                            "pools": retrieval["branches"],
                            "branch_queries": retrieval["branch_queries"],
                            "fused": compile_result.fused,
                        },
                    },
                    session_meta,
                    user_id,
                    set(compile_result.hard_drop),
                    candidate_track_ids,
                )
            stages.append(
                ranking_stage(self.model_version, served_track_ids, method="lightgbm_lambdamart")
            )

        final_ids = list(served_track_ids[:topk])
        trace = {
            "trace_schema_version": TRACE_SCHEMA_VERSION,
            "idx": idx,
            "intent_mode": getattr(state.intent_mode, "value", str(state.intent_mode)),
            "extracted_state": extracted_state,
            "compiled_state": compiled_state,
            "resolver": resolver_block,
            "resolved_targets": [
                {
                    "kind": t.kind,
                    "source_text": t.source_text,
                    "entity_id": t.entity_id,
                    "confidence": t.confidence,
                }
                for t in rs.resolved_targets
            ],
            "retrieval": retrieval,
            "ranking": {
                "stages": stages,
                "final_stage": self.final_stage,
            },
            "final_recommendation": final_recommendation(
                final_ids,
                source_stage=self.final_stage,
                ranking_mode=self.ranking_mode,
            ),
            "compiler": {
                **compiler_summary,
                "n_candidates": len(final_ids),
            },
        }
        return idx, final_ids, trace


def _normalise_ranking_config(qu_kwargs: dict[str, Any]) -> tuple[dict[str, Any], str, str, str]:
    ranking = dict(qu_kwargs.get("ranking") or {})
    if not ranking.get("mode"):
        raise ValueError("state_ranker configs must set qu_kwargs.ranking.mode explicitly")
    mode = str(ranking["mode"]).lower()
    if mode not in {"rrf", "lgbm"}:
        raise ValueError(f"ranking.mode must be 'rrf' or 'lgbm'; got {mode!r}")

    next_kwargs = dict(qu_kwargs)
    next_kwargs.pop("ranking", None)
    if "reranker" in next_kwargs:
        raise ValueError("state_ranker uses qu_kwargs.ranking, not legacy qu_kwargs.reranker")

    if mode == "rrf":
        forbidden = sorted(_LGBM_REQUIRED_KEYS & set(ranking))
        if forbidden:
            raise ValueError(f"ranking.mode='rrf' cannot include model keys: {forbidden}")
        return next_kwargs, mode, "candidate_fusion", "candidate_fusion"

    missing = sorted(key for key in _LGBM_REQUIRED_KEYS if not ranking.get(key))
    if missing:
        raise ValueError(f"ranking.mode='lgbm' missing required keys: {missing}")

    model_version = str(ranking.get("model_version") or "lgbm_v10")
    final_stage = str(ranking.get("final_stage") or model_version)
    next_kwargs["reranker"] = {
        "enabled": True,
        **{key: ranking[key] for key in _LGBM_REQUIRED_KEYS},
        "pool_k": int(ranking.get("pool_k", 500)),
        "top_k_out": int(ranking.get("top_k_out", 1000)),
    }
    return next_kwargs, mode, model_version, final_stage


def build_state_ranker_qu(
    qu_kwargs: dict[str, Any] | None = None,
    _overrides: dict[str, Any] | None = None,
) -> StateRankerQU:
    qu_kwargs = qu_kwargs or {}
    legacy_kwargs, ranking_mode, model_version, final_stage = _normalise_ranking_config(qu_kwargs)
    base = build_v0plus_compiler_qu(qu_kwargs=legacy_kwargs, _overrides=_overrides)
    return StateRankerQU(
        extractor=base.extractor,
        catalog=base.catalog,
        matcher=base.matcher,
        encoder=base.encoder,
        retriever=base.retriever,
        resolver=base.resolver,
        compiler=base.compiler,
        max_in_flight=base.max_in_flight,
        reranker_cfg=base.reranker_cfg,
        ranking_mode=ranking_mode,
        model_version=model_version,
        final_stage=final_stage,
    )
