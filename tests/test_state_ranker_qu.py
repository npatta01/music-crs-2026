from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcrs.conversation_state.schema import ConversationStateV0Plus, MentionedEntity
from mcrs.qu_modules.fuzzy_matcher import RapidfuzzCatalogMatcher
from mcrs.qu_modules.state_ranker_qu import _normalise_ranking_config, build_state_ranker_qu
from tests.qu_fakes import DictCatalog, FakeEmbeddingClient, FakeRetriever


@dataclass
class _FakeExtractor:
    state: ConversationStateV0Plus | None

    def extract(self, conversation, played_track_ids):
        return self.state

    async def aextract(self, conversation, played_track_ids):
        return self.state


class _FakeRanker:
    def __init__(self):
        self.last_trace = None
        self.guard_actions = []

    def rerank(self, trace, session_meta, user_id, hard_drop, fallback):
        self.last_trace = trace
        if self.guard_actions:
            trace["ranking_guard_actions"] = list(self.guard_actions)
        return ["t-fugazi-1", "t-morphine-1"] + [
            track_id for track_id in fallback if track_id not in {"t-fugazi-1", "t-morphine-1"}
        ]


def _catalog() -> DictCatalog:
    return DictCatalog(
        tracks={
            "t-morphine-1": {
                "artist_id": "a-morphine",
                "artist_name": "Morphine",
                "track_name": "Cure for Pain",
                "tag_list": ["smoky", "lounge"],
                "popularity": 70.0,
                "release_date": "1993-09-14",
                "metadata_vector": [1.0, 0.0, 0.0],
            },
            "t-fugazi-1": {
                "artist_id": "a-fugazi",
                "artist_name": "Fugazi",
                "track_name": "Waiting Room",
                "tag_list": ["post-hardcore"],
                "popularity": 80.0,
                "release_date": "1988-11-04",
                "metadata_vector": [0.0, 1.0, 0.0],
            },
        }
    )


def _state(**overrides) -> ConversationStateV0Plus:
    defaults = dict(
        turn_intent="more like Morphine",
        intent_mode="refinement",
        track_feedback=[],
        referenced_track_ids=[],
        mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)],
        hard_filters=[],
        explicit_rejections=[],
    )
    defaults.update(overrides)
    return ConversationStateV0Plus(**defaults)


def _build_qu(*, mode: str = "rrf"):
    catalog = _catalog()
    ranking = {"mode": mode}
    if mode == "lgbm":
        ranking.update(
            {
                "model_version": "lgbm_v10",
                "model_path": "models/reranker_v10/model.txt",
                "meta_path": "models/reranker_v10/meta.json",
                "cat_maps": "models/reranker_v10/cat_maps.json",
                "branch_names": "models/reranker_v10/branch_names.json",
                "tag_index": "cache/tag_embedding_index/qwen_0_6b.npz",
                "embed_memo": "exp/analysis/rerank/q06_memo.json",
                "msg_store": "exp/analysis/rerank/raw_msg_store",
            }
        )
    qu = build_state_ranker_qu(
        qu_kwargs={
            "ranking": ranking,
            "compiler": {"branch_trace_topk": 50},
        },
        _overrides={
            "catalog": catalog,
            "matcher": RapidfuzzCatalogMatcher(catalog),
            "encoder": FakeEmbeddingClient(vector=[0.5, 0.5, 0.5]),
            "retriever": FakeRetriever(
                text_hits_by_field={
                    "artist_name": [("t-morphine-1", 5.0), ("t-fugazi-1", 3.0)],
                    "tag_list": [("t-fugazi-1", 2.0)],
                },
                embedding_hits=[("t-morphine-1", 0.9), ("t-fugazi-1", 0.7)],
            ),
            "extractor": _FakeExtractor(state=_state()),
        },
    )
    if mode == "lgbm":
        qu._reranker = _FakeRanker()
    return qu


def _build_qu_with_state(state: ConversationStateV0Plus, *, mode: str = "rrf"):
    qu = _build_qu(mode=mode)
    qu.extractor = _FakeExtractor(state=state)
    return qu


def test_state_ranker_rrf_trace_has_canonical_final_recommendation():
    qu = _build_qu(mode="rrf")

    rows = qu.batch_compile_track_ids([[{"role": "user", "content": "play Morphine"}]], topk=2)

    trace = qu.last_traces[0]
    assert trace["trace_schema_version"] == "state-ranker-v10"
    assert "extracted_state" in trace
    assert "compiled_state" in trace
    assert "state" not in trace
    assert "branches" not in trace
    assert trace["retrieval"]["branches"][0]["name"] == "bm25"
    assert [stage["name"] for stage in trace["ranking"]["stages"]] == ["candidate_fusion"]
    assert trace["ranking"]["final_stage"] == "candidate_fusion"
    assert trace["final_recommendation"]["track_ids"] == rows[0]
    assert trace["final_recommendation"]["primary_track_id"] == rows[0][0]
    assert trace["final_recommendation"]["source_stage"] == "candidate_fusion"
    assert trace["final_recommendation"]["ranking_mode"] == "rrf"


def test_state_ranker_lgbm_trace_keeps_candidate_and_served_stages_separate():
    qu = _build_qu(mode="lgbm")

    rows = qu.batch_compile_track_ids([[{"role": "user", "content": "play Morphine"}]], topk=2)

    trace = qu.last_traces[0]
    stages = {stage["name"]: stage for stage in trace["ranking"]["stages"]}
    assert list(stages) == ["candidate_fusion", "lgbm_v10"]
    assert stages["candidate_fusion"]["track_ids"][0] == "t-morphine-1"
    assert stages["lgbm_v10"]["track_ids"][0] == "t-fugazi-1"
    assert trace["ranking"]["final_stage"] == "lgbm_v10"
    assert trace["final_recommendation"] == {
        "track_ids": rows[0],
        "primary_track_id": "t-fugazi-1",
        "source_stage": "lgbm_v10",
        "ranking_mode": "lgbm",
    }


def test_state_ranker_lgbm_serving_trace_keeps_intent_mode_for_reranker():
    qu = _build_qu(mode="lgbm")

    qu.batch_compile_track_ids([[{"role": "user", "content": "play Morphine"}]], topk=2)

    assert qu._reranker.last_trace["intent_mode"] == "refinement"


def test_state_ranker_lgbm_serving_trace_keeps_routing_tags_for_reranker():
    qu = _build_qu_with_state(_state(retrieval_profile="exact_probe"), mode="lgbm")

    qu.batch_compile_track_ids([[{"role": "user", "content": "play Morphine"}]], topk=2)

    assert qu._reranker.last_trace["routing_tags"] == {
        "exact_entity_probe": True,
        "lyric_search": False,
        "feature_articulation": False,
        "image_or_visual_search": False,
        "hidden_target_search": False,
    }
    assert qu._reranker.last_trace["compiled_state"]["routing_tags"]["exact_entity_probe"] is True


def test_state_ranker_lgbm_trace_exposes_exact_pin_guard_actions():
    qu = _build_qu_with_state(
        _state(mentioned_entities=[MentionedEntity(type="track", value="Cure for Pain", sentiment=1)]),
        mode="lgbm",
    )
    action = {
        "type": "exact_track_pin",
        "track_id": "t-morphine-1",
        "from_rank": 2,
        "to_rank": 1,
        "request_type": "exact_track",
    }
    qu._reranker.guard_actions = [action]

    qu.batch_compile_track_ids([[{"role": "user", "content": "play Cure for Pain"}]], topk=2)

    resolver = qu._reranker.last_trace["resolver"]
    assert resolver["exact_track_target_ids"] == ["t-morphine-1"]
    assert resolver["exact_track_targets"] == [
        {
            "track_id": "t-morphine-1",
            "source_text": "Cure for Pain",
            "confidence": 100.0,
        }
    ]
    assert qu.last_traces[0]["ranking"]["guard_actions"] == [action]


def test_state_ranker_lgbm_ranking_config_passes_guard_flags_to_reranker():
    reranker_cfg, mode, _, _ = _normalise_ranking_config(
        {
            "ranking": {
                "mode": "lgbm",
                "model_path": "models/reranker_v10/model.txt",
                "meta_path": "models/reranker_v10/meta.json",
                "cat_maps": "models/reranker_v10/cat_maps.json",
                "branch_names": "models/reranker_v10/branch_names.json",
                "tag_index": "cache/tag_embedding_index/qwen_0_6b.npz",
                "embed_memo": "exp/analysis/rerank/q06_memo.json",
                "msg_store": "exp/analysis/rerank/raw_msg_store",
                "visual_rescue_enabled": True,
                "visual_rescue_top_n": 1,
                "visual_rescue_target_rank": 10,
                "lyric_rescue_enabled": True,
                "lyric_rescue_top_n": 1,
                "lyric_rescue_target_rank": 10,
                "lyric_rescue_require_phrase": True,
                "final_artist_guard_enabled": True,
                "final_artist_guard_top_k": 1,
            }
        }
    )

    assert mode == "lgbm"
    assert reranker_cfg["reranker"]["visual_rescue_enabled"] is True
    assert reranker_cfg["reranker"]["visual_rescue_top_n"] == 1
    assert reranker_cfg["reranker"]["visual_rescue_target_rank"] == 10
    assert reranker_cfg["reranker"]["lyric_rescue_enabled"] is True
    assert reranker_cfg["reranker"]["lyric_rescue_top_n"] == 1
    assert reranker_cfg["reranker"]["lyric_rescue_target_rank"] == 10
    assert reranker_cfg["reranker"]["lyric_rescue_require_phrase"] is True
    assert reranker_cfg["reranker"]["final_artist_guard_enabled"] is True
    assert reranker_cfg["reranker"]["final_artist_guard_top_k"] == 1


def test_state_ranker_resolver_trace_uses_artist_ids_and_keeps_surface_values():
    qu = _build_qu_with_state(
        _state(mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)]),
        mode="rrf",
    )

    qu.batch_compile_track_ids([[{"role": "user", "content": "play Morphine"}]], topk=2)

    resolver = qu.last_traces[0]["resolver"]
    assert resolver["anchor_artist_ids"] == ["a-morphine"]
    assert resolver["anchor_artist_values"] == ["Morphine"]
    assert qu.last_traces[0]["compiled_state"]["anchor_policy"]["anchor_artist_ids"] == ["a-morphine"]


def test_state_ranker_resolver_trace_uses_resolved_exact_track_anchors():
    qu = _build_qu_with_state(
        _state(mentioned_entities=[MentionedEntity(type="track", value="Cure for Pain", sentiment=1)]),
        mode="rrf",
    )

    qu.batch_compile_track_ids([[{"role": "user", "content": "play Cure for Pain"}]], topk=2)

    resolver = qu.last_traces[0]["resolver"]
    assert resolver["anchor_track_ids"] == ["t-morphine-1"]
    assert resolver["anchor_track_values"] == ["Cure for Pain"]
    assert qu.last_traces[0]["compiled_state"]["anchor_policy"]["anchor_track_ids"] == ["t-morphine-1"]


def test_state_ranker_exposes_batch_and_trace_timings():
    qu = _build_qu(mode="lgbm")

    qu.batch_compile_track_ids([[{"role": "user", "content": "play Morphine"}]], topk=2)

    assert set(qu.last_batch_timings) >= {
        "total",
        "session_memory",
        "extractor",
        "resolver",
        "compile",
        "compile.total",
        "compile.bm25_search",
        "compile.dense_search",
        "reranker_load",
        "rerank",
        "trace",
    }
    assert all(value >= 0.0 for value in qu.last_batch_timings.values())
    assert set(qu.last_traces[0]["timings"]) >= {
        "session_memory",
        "extractor",
        "resolver",
        "compile",
        "reranker_load",
        "rerank",
        "trace",
        "total",
    }


def test_state_ranker_accepts_compile_max_in_flight():
    catalog = _catalog()
    qu = build_state_ranker_qu(
        qu_kwargs={
            "max_in_flight": 2,
            "compile_max_in_flight": 1,
            "ranking": {"mode": "rrf"},
            "compiler": {"branch_trace_topk": 50},
        },
        _overrides={
            "catalog": catalog,
            "matcher": RapidfuzzCatalogMatcher(catalog),
            "encoder": FakeEmbeddingClient(vector=[0.5, 0.5, 0.5]),
            "retriever": FakeRetriever(
                text_hits_by_field={
                    "artist_name": [("t-morphine-1", 5.0), ("t-fugazi-1", 3.0)],
                },
                embedding_hits=[("t-morphine-1", 0.9), ("t-fugazi-1", 0.7)],
            ),
            "extractor": _FakeExtractor(state=_state()),
        },
    )

    rows = qu.batch_compile_track_ids(
        [[{"role": "user", "content": "play Morphine"}] for _ in range(2)],
        topk=2,
    )

    assert qu.compile_max_in_flight == 1
    assert len(rows) == 2
    assert all(row for row in rows)


def test_state_ranker_requires_explicit_ranking_mode():
    with pytest.raises(ValueError, match="ranking.mode"):
        build_state_ranker_qu(qu_kwargs={"compiler": {"branch_trace_topk": 50}})
