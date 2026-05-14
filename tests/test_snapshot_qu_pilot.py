import json
import sys
from types import SimpleNamespace

import pandas as pd

from run_snapshot_qu_pilot import (
    LiteLLMSnapshotAdapter,
    REQUIRED_SNAPSHOT_KEYS,
    SnapshotExtractionError,
    SnapshotExtractor,
    compute_pilot_metrics,
    retrieve_with_relaxation,
)


class _FakeAdapter:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def generate_batch(self, messages_list, max_new_tokens):
        self.calls.append(
            {
                "messages_list": messages_list,
                "max_new_tokens": max_new_tokens,
            }
        )
        return self.outputs


class _FakeRetriever:
    def __init__(self):
        self.queries = []

    def text_to_item_retrieval(self, query, topk):
        self.queries.append((query, topk))
        if len(self.queries) == 1:
            return []
        return ["track-2", "track-1", "track-3"]


class _ImmediateFakeRetriever:
    def __init__(self):
        self.queries = []

    def text_to_item_retrieval(self, query, topk):
        self.queries.append((query, topk))
        return ["track-9"]


def _valid_snapshot(**overrides):
    snapshot = {
        "intent": "refinement",
        "positive_preferences": {"moods": ["dreamy"]},
        "negative_preferences": {},
        "active_constraints": {
            "must_have": [],
            "nice_to_have": ["dreamy", "2010s"],
            "avoid": [],
            "relaxation_order": ["2010s", "dreamy"],
            "null_result_strategy": "relax_lowest_priority_then_retry",
        },
        "sparse_query": "dreamy 2010s r&b",
        "dense_query": "dreamy modern r&b",
    }
    snapshot.update(overrides)
    return snapshot


def test_snapshot_extractor_parses_required_json_without_fallback():
    adapter = _FakeAdapter([json.dumps(_valid_snapshot())])
    extractor = SnapshotExtractor(
        model_name="openai/gpt-5.4-mini",
        adapter=adapter,
        max_new_tokens=512,
    )

    result = extractor.extract_one(
        session_memory=[{"role": "user", "content": "Something dreamy"}],
        user_query="More like that",
    )

    assert set(REQUIRED_SNAPSHOT_KEYS).issubset(result.snapshot)
    assert result.extraction_status == "success"
    assert result.snapshot["sparse_query"] == "dreamy 2010s r&b"
    assert adapter.calls[0]["max_new_tokens"] == 512


def test_snapshot_extractor_abandons_invalid_json_instead_of_falling_back():
    adapter = _FakeAdapter(["not json"])
    extractor = SnapshotExtractor(model_name="openai/gpt-5.4-mini", adapter=adapter)

    try:
        extractor.extract_one([], "anything")
    except SnapshotExtractionError as exc:
        assert "invalid_json" in str(exc)
    else:
        raise AssertionError("invalid extraction should be abandoned")


def test_snapshot_extractor_abandons_missing_required_key():
    invalid = _valid_snapshot()
    invalid.pop("active_constraints")
    extractor = SnapshotExtractor(
        model_name="openai/gpt-5.4-mini",
        adapter=_FakeAdapter([json.dumps(invalid)]),
    )

    try:
        extractor.extract_one([], "anything")
    except SnapshotExtractionError as exc:
        assert "missing_keys" in str(exc)
    else:
        raise AssertionError("missing required keys should be abandoned")


def test_retrieve_with_relaxation_retries_after_dropping_nice_to_have():
    retriever = _FakeRetriever()
    snapshot = _valid_snapshot()

    result = retrieve_with_relaxation(snapshot, retriever, topk=3)

    assert result.track_ids == ["track-2", "track-1", "track-3"]
    assert result.relaxed_constraints == ["2010s"]
    assert retriever.queries == [
        ("dreamy 2010s r&b", 3),
        ("dreamy r&b", 3),
    ]


def test_retrieve_with_relaxation_can_use_dense_state_query():
    retriever = _ImmediateFakeRetriever()
    snapshot = _valid_snapshot(
        sparse_query="catalog terms only",
        dense_query="semantic state query for dense retrieval",
    )

    result = retrieve_with_relaxation(snapshot, retriever, topk=5, query_field="dense_query")

    assert result.query == "semantic state query for dense retrieval"
    assert result.query_field == "dense_query"
    assert retriever.queries == [("semantic state query for dense retrieval", 5)]


def test_retrieve_with_relaxation_rejects_missing_state_query():
    retriever = _ImmediateFakeRetriever()
    snapshot = _valid_snapshot(dense_query=" ")

    try:
        retrieve_with_relaxation(snapshot, retriever, topk=5, query_field="dense_query")
    except SnapshotExtractionError as exc:
        assert "invalid_dense_query" in str(exc)
    else:
        raise AssertionError("missing dense state query should be abandoned")


def test_litellm_adapter_uses_openrouter_when_only_openrouter_key_is_set(monkeypatch):
    captured = {}

    def fake_batch_completion(**kwargs):
        captured.update(kwargs)
        return [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps(_valid_snapshot())),
                    )
                ]
            )
        ]

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LITELLM_PROXY_BASE", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(batch_completion=fake_batch_completion),
    )
    adapter = LiteLLMSnapshotAdapter(model_name="openai/gpt-5.4-mini")

    outputs = adapter.generate_batch([[{"role": "user", "content": "hello"}]], max_new_tokens=64)

    assert captured["model"] == "openrouter/openai/gpt-5.4-mini"
    assert captured["api_key"] == "test-key"
    assert json.loads(outputs[0])["sparse_query"] == "dreamy 2010s r&b"


def test_compute_pilot_metrics_reports_failures_and_valid_snapshot_metrics():
    baseline_rows = pd.DataFrame(
        [
            {
                "session_id": "s1",
                "turn_number": 1,
                "predicted_track_ids": ["gold", "x", "y"],
                "predicted_response": "",
            },
            {
                "session_id": "s1",
                "turn_number": 2,
                "predicted_track_ids": ["x", "gold2", "y"],
                "predicted_response": "",
            },
        ]
    )
    snapshot_rows = pd.DataFrame(
        [
            {
                "session_id": "s1",
                "turn_number": 1,
                "predicted_track_ids": ["x", "gold", "y"],
                "predicted_response": "",
            },
        ]
    )
    ground_truth = pd.DataFrame(
        [
            {"session_id": "s1", "turn_number": 1, "ground_truth_track_id": "gold"},
            {"session_id": "s1", "turn_number": 2, "ground_truth_track_id": "gold2"},
        ]
    )
    debug_records = [
        {"extraction_status": "success"},
        {"extraction_status": "failure", "failure_reason": "invalid_json"},
    ]

    metrics = compute_pilot_metrics(
        baseline_rows=baseline_rows,
        snapshot_rows=snapshot_rows,
        ground_truth=ground_truth,
        debug_records=debug_records,
    )

    assert metrics["turns_total"] == 2
    assert metrics["snapshot_valid_turns"] == 1
    assert metrics["extraction_failure_count"] == 1
    assert metrics["extraction_failure_rate"] == 0.5
    assert metrics["baseline"]["n_turns_evaluated"] == 2
    assert metrics["snapshot"]["n_turns_evaluated"] == 1
