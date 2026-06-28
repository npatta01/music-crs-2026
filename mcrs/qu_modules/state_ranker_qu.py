"""State-ranker v10 QU surface.

This module owns the public v10 contract:
extract state -> compile retrieval policy -> retrieve branch pools -> run ranking
stages -> publish one canonical final_recommendation object.
"""

from __future__ import annotations

import asyncio
import logging
import time
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
    _add_elapsed,
    aextract_with_cache_context,
    build_v0plus_compiler_qu,
    session_memory_to_conversation,
    state_cache_context_from_session_meta,
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


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _surface_key(value: str) -> str:
    return value.casefold().strip()


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
        extract_sem: asyncio.Semaphore,
        compile_sem: asyncio.Semaphore,
        user_id: str | None = None,
        session_meta: dict[str, Any] | None = None,
    ) -> tuple[int, list[str], dict[str, Any]]:
        timings: dict[str, float] = {}
        total_start = time.perf_counter()
        start = time.perf_counter()
        conv, played = session_memory_to_conversation(session_memory, self.catalog)
        _add_elapsed(timings, "session_memory", start)
        start = time.perf_counter()
        cache_context = state_cache_context_from_session_meta(session_meta)
        async with extract_sem:
            state = await aextract_with_cache_context(
                self.extractor,
                conv,
                played,
                cache_context=cache_context,
            )
        _add_elapsed(timings, "extractor", start)
        if state is None:
            timings.setdefault("resolver", 0.0)
            timings.setdefault("compile", 0.0)
            timings.setdefault("rerank", 0.0)
            timings.setdefault("trace", 0.0)
            _add_elapsed(timings, "total", total_start)
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
                "timings": timings,
            }
            return idx, [], trace

        start = time.perf_counter()
        rs = self.resolver.resolve(state, played_track_ids=played)
        _add_elapsed(timings, "resolver", start)

        def _run_compile() -> CompileResult:
            return self.compiler._compile(rs, user_id=user_id)

        start = time.perf_counter()
        async with compile_sem:
            compile_result = await asyncio.to_thread(_run_compile)
        _add_elapsed(timings, "compile", start)
        for key, value in compile_result.timings.items():
            timings[f"compile.{key}"] = timings.get(f"compile.{key}", 0.0) + float(value)
        candidate_track_ids = candidate_fusion_track_ids(compile_result)

        start = time.perf_counter()
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
        anchor_track_ids = [
            tf.track_id
            for tf in state.track_feedback
            if tf.role in ("accepted", "seed") and tf.overall_sentiment > 0
        ] + list(state.referenced_track_ids)
        anchor_track_values = [
            me.value
            for me in state.mentioned_entities
            if me.sentiment > 0 and me.type == "track" and me.value
        ]
        anchor_artist_values = [
            me.value
            for me in state.mentioned_entities
            if me.sentiment > 0 and me.type == "artist" and me.value
        ]
        resolved_track_ids_by_surface = {
            _surface_key(t.source_text): t.entity_id
            for t in rs.resolved_targets
            if t.kind == "track"
            and t.entity_id
            and getattr(t, "resolution_role", "exact_target") == "exact_target"
        }
        exact_track_targets: list[dict[str, Any]] = []
        seen_exact_track_ids: set[str] = set()
        for target in rs.resolved_targets:
            if (
                target.kind != "track"
                or not target.entity_id
                or getattr(target, "resolution_role", "exact_target") != "exact_target"
            ):
                continue
            track_id = str(target.entity_id)
            if track_id in seen_exact_track_ids:
                continue
            seen_exact_track_ids.add(track_id)
            exact_track_targets.append(
                {
                    "track_id": track_id,
                    "source_text": target.source_text,
                    "confidence": target.confidence,
                }
            )
        resolved_artist_ids_by_surface = {
            _surface_key(t.source_text): t.entity_id
            for t in rs.resolved_targets
            if t.kind == "artist"
            and t.entity_id
            and getattr(t, "resolution_role", "exact_target") == "exact_target"
        }
        anchor_track_ids.extend(
            track_id
            for value in anchor_track_values
            if (track_id := resolved_track_ids_by_surface.get(_surface_key(value)))
        )
        anchor_artist_ids = [
            artist_id
            for value in anchor_artist_values
            if (artist_id := resolved_artist_ids_by_surface.get(_surface_key(value)))
        ]
        resolver_block = {
            "anchor_track_ids": _dedupe_preserving_order(anchor_track_ids),
            "anchor_track_values": _dedupe_preserving_order(anchor_track_values),
            "anchor_artist_ids": _dedupe_preserving_order(anchor_artist_ids),
            "anchor_artist_values": _dedupe_preserving_order(anchor_artist_values),
            "exact_track_target_ids": [
                target["track_id"] for target in exact_track_targets
            ],
            "exact_track_targets": exact_track_targets,
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
        intent_mode = getattr(state.intent_mode, "value", str(state.intent_mode))
        routing_tags = state.routing_tags.model_dump(mode="json")

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
        _add_elapsed(timings, "trace", start)

        stages = [
            ranking_stage(
                "candidate_fusion",
                candidate_track_ids,
                method="weighted_rrf",
                scores=compile_result.fused,
            )
        ]
        served_track_ids = list(candidate_track_ids)
        ranking_guard_actions: list[dict[str, Any]] = []

        if self.ranking_mode == "lgbm":
            had_reranker = self._reranker is not None
            start = time.perf_counter()
            rr = self._get_reranker()
            _add_elapsed(timings, "reranker_load", start)
            if rr is not None and not had_reranker:
                for key, value in getattr(rr, "load_timings", {}).items():
                    if isinstance(value, (int, float)):
                        timings[f"reranker_load.{key}"] = (
                            timings.get(f"reranker_load.{key}", 0.0) + float(value)
                        )
            if rr is not None:
                start = time.perf_counter()
                rerank_trace = {
                    "trace_schema_version": TRACE_SCHEMA_VERSION,
                    "extracted_state": extracted_state,
                    "compiled_state": compiled_state,
                    "state": extracted_state,
                    "intent_mode": intent_mode,
                    "resolver": resolver_block,
                    "routing_tags": routing_tags,
                    "retrieval": retrieval,
                    "branches": {
                        "pools": retrieval["branches"],
                        "branch_queries": retrieval["branch_queries"],
                        "fused": compile_result.fused,
                    },
                }
                served_track_ids = await asyncio.to_thread(
                    rr.rerank,
                    rerank_trace,
                    session_meta,
                    user_id,
                    set(compile_result.hard_drop),
                    candidate_track_ids,
                )
                ranking_guard_actions = list(rerank_trace.get("ranking_guard_actions") or [])
                _add_elapsed(timings, "rerank", start)
            else:
                timings.setdefault("rerank", 0.0)
            stages.append(
                ranking_stage(self.model_version, served_track_ids, method="lightgbm_lambdamart")
            )
        else:
            timings.setdefault("rerank", 0.0)

        final_ids = list(served_track_ids[:topk])
        start = time.perf_counter()
        trace = {
            "trace_schema_version": TRACE_SCHEMA_VERSION,
            "idx": idx,
            "intent_mode": intent_mode,
            "routing_tags": routing_tags,
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
                "guard_actions": ranking_guard_actions,
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
        _add_elapsed(timings, "trace", start)
        _add_elapsed(timings, "total", total_start)
        trace["timings"] = timings
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
    for key in (
        "exact_pin_top_n",
        "exact_pin_min_confidence",
        "visual_rescue_enabled",
        "visual_rescue_top_n",
        "visual_rescue_target_rank",
        "lyric_rescue_enabled",
        "lyric_rescue_top_n",
        "lyric_rescue_target_rank",
        "lyric_rescue_require_phrase",
    ):
        if key in ranking:
            next_kwargs["reranker"][key] = ranking[key]
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
        compile_max_in_flight=base.compile_max_in_flight,
        reranker_cfg=base.reranker_cfg,
        ranking_mode=ranking_mode,
        model_version=model_version,
        final_stage=final_stage,
    )
