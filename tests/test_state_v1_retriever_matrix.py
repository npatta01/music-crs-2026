"""Tests for the focused V1 retriever matrix harness."""

from __future__ import annotations

import json
from types import SimpleNamespace

from mcrs.qu_modules.compiler_v0plus import BranchPool
from scripts.state_v1_retriever_matrix import (
    VARIANTS,
    _additive_metrics_for_pools,
    _baseline_summary,
    _class_summaries,
    _expanded_tag_terms,
    _extract_trace_baseline_pools,
    _pool_to_trace_payload,
    _rerank_branch_pools,
    _tag_popularity_pool,
    _variant_qu_kwargs,
)


class _FakeCatalog:
    def __init__(
        self,
        *,
        tags: dict[str, list[str]] | None = None,
        artists: dict[str, str] | None = None,
        years: dict[str, int] | None = None,
        popularity: dict[str, int] | None = None,
    ):
        self.tags = tags or {}
        self.artists = artists or {}
        self.years = years or {}
        self.popularity = popularity or {}

    def tag_list(self, track_id: str) -> list[str]:
        return self.tags.get(track_id, [])

    def artist_id_of(self, track_id: str) -> str | None:
        return self.artists.get(track_id)

    def release_year_of(self, track_id: str) -> int | None:
        return self.years.get(track_id)

    def all_track_ids(self) -> list[str]:
        return sorted(set(self.tags) | set(self.artists) | set(self.years) | set(self.popularity))

    def popularity_sorted_track_ids(self) -> list[str]:
        return sorted(self.all_track_ids(), key=lambda tid: (self.popularity.get(tid, 10**9), tid))


class _FakeCompiler:
    def __init__(self, catalog: _FakeCatalog, hard_drop: set[str] | None = None):
        self.catalog = catalog
        self.hard_drop = hard_drop or set()

    def _hard_drop_set(self, _rs):
        return set(self.hard_drop)

    def _anchor_track_ids(self, _state):
        return ["anchor"]

    def _top_anchor_tags(self, _rs, n: int):
        return ["indie", "warm"][:n]

    def _positive_mention_values(self, state, entity_type: str):
        if entity_type != "tag":
            return []
        out = []
        for fact in getattr(state, "facts", []) or []:
            if getattr(fact, "type", "") == "attribute":
                out.append(getattr(fact, "value", ""))
        return out

    def _popularity_rank(self):
        return dict(self.catalog.popularity)


def _fake_qu(state, catalog: _FakeCatalog, hard_drop: set[str] | None = None):
    return SimpleNamespace(
        compiler=_FakeCompiler(catalog, hard_drop=hard_drop),
    ), SimpleNamespace(state=state)


def _state(**kwargs):
    defaults = {
        "facts": [],
        "explicit_rejections": [],
        "target_artist_mode": "unknown",
        "release_year_range": None,
        "current_request": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_current_config_variant_preserves_base_compiler_branches(tmp_path):
    base = {
        "lancedb": {"db_uri": "old"},
        "encoders": {
            "qwen_0_6b": {"backend": "litellm"},
            "clap_text": {"backend": "modal_multimodal"},
        },
        "compiler": {
            "dense_branches": [
                {
                    "vector_field": "metadata_qwen3_embedding_0_6b",
                    "encoder_id": "qwen_0_6b",
                    "query_id": "metadata",
                },
                {
                    "vector_field": "audio_laion_clap",
                    "encoder_id": "clap_text",
                    "query_id": "sonic_nl",
                },
            ],
            "enable_dense": True,
            "enable_era_popularity": True,
            "enable_resolved_artist_discography": True,
            "enable_similar_artist_anchors": True,
        },
    }

    out = _variant_qu_kwargs(base, VARIANTS["current_config"], tmp_path)

    assert out["lancedb"]["db_uri"] == str(tmp_path)
    assert out["compiler"]["dense_branches"] == base["compiler"]["dense_branches"]
    assert set(out["encoders"]) == {"qwen_0_6b", "clap_text"}
    assert out["compiler"]["enable_dense"] is True
    assert out["compiler"]["enable_era_popularity"] is True


def test_baseline_summary_infers_union50_when_bounds_match():
    turn_meta = {
        "a": {"baseline": {"union20": True, "union100": True, "final_rank": 12}},
        "b": {"baseline": {"union20": False, "union100": False, "final_rank": 80}},
    }

    summary = _baseline_summary(turn_meta, ["a", "b"])

    assert summary["union@20"] == 0.5
    assert summary["union@50"] == 0.5
    assert summary["union@100"] == 0.5
    assert summary["final@20"] == 0.5


def test_additive_metrics_preserve_protected_baseline_hit():
    baseline = [BranchPool("baseline.bm25", [("target", 1.0)])]
    candidate = [BranchPool("new.branch", [("other", 1.0), ("x", 0.5)])]

    metrics = _additive_metrics_for_pools(baseline, candidate, "target")

    assert metrics["branch_only@20"] is False
    assert metrics["additive_union@20"] is True
    assert metrics["additive_best_branch"] == "baseline.bm25"
    assert metrics["additive_best_branch_rank"] == 1


def test_additive_metrics_rescue_baseline_miss_with_new_branch():
    baseline = [BranchPool("baseline.bm25", [("a", 1.0), ("b", 0.5)])]
    candidate = [BranchPool("new.genre_popularity", [("a", 1.0), ("target", 0.5)])]

    metrics = _additive_metrics_for_pools(baseline, candidate, "target")

    assert metrics["branch_only@20"] is True
    assert metrics["additive_union@20"] is True
    assert metrics["branch_only_best_branch"] == "new.genre_popularity"
    assert metrics["branch_only_best_branch_rank"] == 2
    assert metrics["additive_best_branch"] == "new.genre_popularity"


def test_expanded_tag_terms_adds_common_catalog_aliases():
    terms = _expanded_tag_terms(["hip hop", "pop-punk", "r&b"])

    assert {"hip hop", "hip-hop", "rap", "pop punk", "pop-punk", "rnb", "r&b"} <= terms


def test_tag_popularity_pool_ranks_matching_popular_tracks():
    catalog = _FakeCatalog(
        tags={
            "popular-funk": ["funk", "dance"],
            "unmatched": ["metal"],
            "deep-funk": ["funk"],
        },
        popularity={"popular-funk": 1, "unmatched": 0, "deep-funk": 50},
    )

    pool = _tag_popularity_pool(
        catalog,
        tags=["funk"],
        name="analysis.tag_popularity",
        topk=10,
    )

    assert [track_id for track_id, _ in pool.hits] == ["popular-funk", "deep-funk"]


def test_extract_trace_baseline_pools_streams_only_requested_turns(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "session_id": "s1",
                        "turn_number": 1,
                        "trace": {
                            "branches": {
                                "pools": [
                                    {
                                        "name": "bm25",
                                        "hits": [["a", 1.0], ["target", 0.5], ["tail", 0.1]],
                                    }
                                ]
                            }
                        },
                    }
                ),
                json.dumps(
                    {
                        "session_id": "s2",
                        "turn_number": 1,
                        "trace": {
                            "branches": {
                                "pools": [
                                    {"name": "bm25", "hits": [["unwanted", 1.0]]}
                                ]
                            }
                        },
                    }
                ),
            ]
        )
        + "\n"
    )
    turn_meta = {
        "s1::t1": {
            "session_id": "s1",
            "turn": 1,
            "baseline": {"union20": True, "union100": True},
        }
    }

    extracted = _extract_trace_baseline_pools(trace_path, turn_meta, depth=2)

    assert set(extracted) == {"s1::t1"}
    assert extracted["s1::t1"][0].name == "baseline.bm25"
    assert _pool_to_trace_payload(extracted["s1::t1"][0]) == {
        "name": "baseline.bm25",
        "hits": ["a", "target"],
    }


def test_class_summaries_pick_best_single_and_combined_variants():
    turn_meta = {
        "a": {"pack": "P0_a", "baseline": {"union20": False, "union100": False, "final_rank": 90}},
        "b": {"pack": "P0_a", "baseline": {"union20": True, "union100": True, "final_rank": 10}},
        "c": {"pack": "P1_b", "baseline": {"union20": False, "union100": False, "final_rank": 120}},
    }
    rows = [
        {"sample_id": "a", "variant": "qwen8_metadata", "union@20": True, "union@50": True, "union@100": True, "final@20": False},
        {"sample_id": "b", "variant": "qwen8_metadata", "union@20": False, "union@50": True, "union@100": True, "final@20": False},
        {"sample_id": "c", "variant": "qwen8_metadata", "union@20": False, "union@50": False, "union@100": True, "final@20": False},
        {"sample_id": "a", "variant": "all_candidate_recall", "union@20": True, "union@50": True, "union@100": True, "final@20": True},
        {"sample_id": "b", "variant": "all_candidate_recall", "union@20": True, "union@50": True, "union@100": True, "final@20": False},
        {"sample_id": "c", "variant": "all_candidate_recall", "union@20": True, "union@50": True, "union@100": True, "final@20": False},
    ]

    summaries = _class_summaries(
        rows,
        turn_meta,
        variant_names=["qwen8_metadata", "all_candidate_recall"],
        combined_variant_names={"all_candidate_recall"},
    )

    p0 = next(row for row in summaries if row["pack"] == "P0_a")
    p1 = next(row for row in summaries if row["pack"] == "P1_b")
    assert p0["baseline_union@20"] == 0.5
    assert p0["best_single_variant"] == "qwen8_metadata"
    assert p0["combined_union@20"] == 1.0
    assert p1["best_single_union@20"] == 0.0
    assert p1["combined_union@20"] == 1.0


def test_branch_local_rules_hard_drop_only_removes_compiler_drop_set():
    qu, rs = _fake_qu(_state(), _FakeCatalog(), hard_drop={"rejected-track"})
    pools = [BranchPool("bm25", [("rejected-track", 1.0), ("target", 0.5)])]

    reranked = _rerank_branch_pools(qu, rs, pools, ("hard_drop",))

    assert [track_id for track_id, _ in reranked[0].hits] == ["target"]


def test_branch_local_negative_tag_is_soft_not_filter():
    state = _state(
        explicit_rejections=[SimpleNamespace(kind="tag", value="abrasive")],
    )
    catalog = _FakeCatalog(tags={"negative": ["abrasive"], "neutral": []})
    qu, rs = _fake_qu(state, catalog)
    pools = [BranchPool("dense", [("negative", 1.0), ("neutral", 0.5)])]

    reranked = _rerank_branch_pools(qu, rs, pools, ("negative_tag_demote",))
    ids = [track_id for track_id, _ in reranked[0].hits]

    assert ids == ["neutral", "negative"]
    assert "negative" in ids


def test_branch_local_popularity_boost_requires_structured_popularity_fact():
    catalog = _FakeCatalog(popularity={"deep-cut": 10_000, "classic": 20})
    pool = BranchPool("bm25", [("deep-cut", 1.0), ("classic", 0.5)])
    no_pop_state = _state()
    qu, rs = _fake_qu(no_pop_state, catalog)

    unchanged = _rerank_branch_pools(qu, rs, [pool], ("explicit_popularity_boost",))

    pop_state = _state(
        facts=[
            SimpleNamespace(
                type="attribute",
                facet="popularity",
                value="classic",
                role="current_target",
            )
        ]
    )
    qu, rs = _fake_qu(pop_state, catalog)
    boosted = _rerank_branch_pools(qu, rs, [pool], ("explicit_popularity_boost",))

    assert [track_id for track_id, _ in unchanged[0].hits] == ["deep-cut", "classic"]
    assert [track_id for track_id, _ in boosted[0].hits] == ["classic", "deep-cut"]
