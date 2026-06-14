from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcrs.conversation_state.schema import ConversationStateV0Plus, MentionedEntity
from mcrs.qu_modules.fuzzy_matcher import RapidfuzzCatalogMatcher
from mcrs.qu_modules.state_ranker_qu import build_state_ranker_qu
from tests.v0plus_fakes import DictCatalog, FakeEmbeddingClient, FakeRetriever


@dataclass
class _FakeExtractor:
    state: ConversationStateV0Plus | None

    def extract(self, conversation, played_track_ids):
        return self.state

    async def aextract(self, conversation, played_track_ids):
        return self.state


class _FakeRanker:
    def rerank(self, trace, session_meta, user_id, hard_drop, fallback):
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


def test_state_ranker_requires_explicit_ranking_mode():
    with pytest.raises(ValueError, match="ranking.mode"):
        build_state_ranker_qu(qu_kwargs={"compiler": {"branch_trace_topk": 50}})
