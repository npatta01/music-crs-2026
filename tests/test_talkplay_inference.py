import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from omegaconf import OmegaConf

import run_inference_talkplay_devset


def _build_conversations():
    conversations = []
    for turn_number in range(1, 9):
        conversations.extend(
            [
                {
                    "turn_number": turn_number,
                    "role": "user",
                    "content": f"user request {turn_number}",
                },
                {
                    "turn_number": turn_number,
                    "role": "assistant",
                    "content": f"assistant reply {turn_number}",
                },
                {
                    "turn_number": turn_number,
                    "role": "music",
                    "content": f"track-{turn_number}",
                },
            ]
        )
    return conversations


class _FakeAgent:
    def __init__(self):
        self.session_memory = []
        self.loaded_profiles = []
        self.seen_messages = []
        self.prompts = {"goal_tool_calling": ""}

    def _reset_session_memory(self):
        self.session_memory = []

    def _load_user_profile(self, explicit_user_info):
        self.loaded_profiles.append(explicit_user_info)

    def chat(self, message):
        self.seen_messages.append((list(self.session_memory), message))
        return {
            "tool_call_results": [
                {
                    "tool_name": "bm25",
                    "recommend_track_ids": [f"pred-{idx:04d}" for idx in range(1000)],
                }
            ],
            "answer_response": f"answer for {message}",
        }


class _ExplodingAgent(_FakeAgent):
    def chat(self, message):
        raise IndexError(f"boom for {message}")


def _talkplay_config():
    return OmegaConf.create(
        {
            "model_name": "Qwen/Qwen3-4B",
            "llm_backend": "local",
            "llm_kwargs": {},
            "cache_dir": "./cache",
            "test_dataset_name": "ignored",
            "track_dataset_name": "ignored",
            "track_split": "all_tracks",
            "track_embeddings_dataset_name": "ignored",
            "track_embeddings_split": "all_tracks",
            "user_dataset_name": "ignored",
            "user_split": "all_users",
            "prediction_depth": 1000,
            "user_mode": "cold_start",
            "num_sessions": 10,
            "enabled_tools": ["sql", "bm25", "text_to_item_similarity"],
            "embedding_enabled_retrievers": ["text"],
            "embedding_enabled_corpora": ["metadata", "attributes", "lyrics"],
        }
    )


def test_run_inference_talkplay_devset_writes_evaluator_rows(monkeypatch, tmp_path):
    fake_agent = _FakeAgent()
    captured_kwargs = {}
    monkeypatch.setattr(
        run_inference_talkplay_devset.OmegaConf,
        "load",
        lambda _: _talkplay_config(),
    )
    monkeypatch.setattr(
        run_inference_talkplay_devset,
        "load_talkplay_agent",
        lambda model_name, cache_dir, **kwargs: captured_kwargs.update(kwargs) or fake_agent,
    )
    monkeypatch.setattr(
        run_inference_talkplay_devset,
        "load_dataset",
        lambda name, split=None: {
            "ignored": [
                {
                    "session_id": "session-1",
                    "user_id": "user-1",
                    "user_profile": {
                        "age_group": "20s",
                        "gender": "female",
                        "country_name": "United States",
                    },
                    "conversations": _build_conversations(),
                }
            ],
        }[name]
        if split == "test"
        else [
            {
                "track_id": "track-1",
                "track_name": ["Song"],
                "artist_name": ["Artist"],
                "album_name": ["Album"],
                "tag_list": ["calm"],
                "popularity": 10.0,
                "release_date": "2001-01-01",
                "metadata-qwen3_embedding_0.6b": [1.0, 2.0],
                "attributes-qwen3_embedding_0.6b": [3.0, 4.0],
                "lyrics-qwen3_embedding_0.6b": [],
                "age_group": "20s",
                "gender": "female",
                "country_name": "United States",
                "user_id": "user-1",
            }
        ],
    )

    args = SimpleNamespace(
        tid="talkplay_qwen3_4b_devset_smoke",
        batch_size=1,
        session_ids_file=None,
        num_sessions=0,
        exp_dir=str(tmp_path / "exp"),
        clear_cache=False,
    )

    run_inference_talkplay_devset.main(args)

    output_path = tmp_path / "exp" / "inference" / "devset" / "talkplay_qwen3_4b_devset_smoke.json"
    rows = json.loads(output_path.read_text())

    assert len(rows) == 8
    assert rows[0]["session_id"] == "session-1"
    assert rows[0]["user_id"] == "user-1"
    assert rows[0]["turn_number"] == 1
    assert len(rows[0]["predicted_track_ids"]) == 1000
    assert rows[0]["predicted_response"] == "answer for user request 1"
    assert captured_kwargs["generate_response"] is True
    assert fake_agent.loaded_profiles[0]["user_type"] == "cold_start"
    assert fake_agent.loaded_profiles[0]["previous_history"] == []
    assert fake_agent.seen_messages[1][0][-1] == {
        "role": "music",
        "content": "track:track-1",
    }


def test_extract_prediction_row_raises_on_short_rankings():
    with pytest.raises(ValueError, match="fewer than 1000"):
        run_inference_talkplay_devset.extract_prediction_row(
            result={
                "tool_call_results": [
                    {
                        "tool_name": "bm25",
                        "recommend_track_ids": ["track-1", "track-2"],
                    }
                ],
                "answer_response": "too short",
            },
            prediction_depth=1000,
        )


def test_normalize_prediction_row_backfills_short_rankings():
    predicted_track_ids, predicted_response, trace_summary = (
        run_inference_talkplay_devset.normalize_prediction_row(
            result={
                "tool_call_results": [
                    {
                        "tool_name": "bm25",
                        "tool_args": {"topk": 1000},
                        "recommend_track_ids": ["track-1", "track-2", "track-2"],
                    }
                ],
                "answer_response": "short but usable",
            },
            prediction_depth=4,
            catalog_track_ids=["track-1", "track-2", "track-3", "track-4", "track-5"],
            allow_backfill=True,
        )
    )

    assert predicted_track_ids == ["track-1", "track-2", "track-3", "track-4"]
    assert predicted_response == "short but usable"
    assert trace_summary["raw_final_count"] == 3
    assert trace_summary["unique_final_count"] == 2
    assert trace_summary["backfilled_count"] == 2


def test_build_fallback_prediction_row_uses_catalog_prefix():
    predicted_track_ids, predicted_response, trace_summary = (
        run_inference_talkplay_devset.build_fallback_prediction_row(
            result={"tool_call_results": [], "answer_response": ""},
            prediction_depth=3,
            catalog_track_ids=["track-1", "track-2", "track-3", "track-4"],
            error_message="no tool calls",
            fallback_reason="tool_call_missing",
        )
    )

    assert predicted_track_ids == ["track-1", "track-2", "track-3"]
    assert predicted_response == ""
    assert trace_summary["fallback_used"] is True
    assert trace_summary["fallback_strategy"] == "fixed_pool"
    assert trace_summary["fallback_reason"] == "tool_call_missing"
    assert trace_summary["error_message"] == "no tool calls"


def test_run_inference_talkplay_devset_falls_back_when_chat_raises(monkeypatch, tmp_path):
    fake_agent = _ExplodingAgent()
    config = _talkplay_config()
    config.prediction_depth = 2
    monkeypatch.setattr(
        run_inference_talkplay_devset.OmegaConf,
        "load",
        lambda _: config,
    )
    monkeypatch.setattr(
        run_inference_talkplay_devset,
        "load_talkplay_agent",
        lambda model_name, cache_dir, **kwargs: fake_agent,
    )
    monkeypatch.setattr(
        run_inference_talkplay_devset,
        "load_dataset",
        lambda name, split=None: {
            "ignored": [
                {
                    "session_id": "session-1",
                    "user_id": "user-1",
                    "user_profile": {
                        "age_group": "20s",
                        "gender": "female",
                        "country_name": "United States",
                    },
                    "conversations": _build_conversations(),
                }
            ],
        }[name]
        if split == "test"
        else [
            {
                "track_id": "track-1",
                "track_name": ["Song"],
                "artist_name": ["Artist"],
                "album_name": ["Album"],
                "tag_list": ["calm"],
                "popularity": 10.0,
                "release_date": "2001-01-01",
                "metadata-qwen3_embedding_0.6b": [1.0, 2.0],
                "attributes-qwen3_embedding_0.6b": [3.0, 4.0],
                "lyrics-qwen3_embedding_0.6b": [],
                "age_group": "20s",
                "gender": "female",
                "country_name": "United States",
                "user_id": "user-1",
            },
            {
                "track_id": "track-2",
                "track_name": ["Song 2"],
                "artist_name": ["Artist 2"],
                "album_name": ["Album 2"],
                "tag_list": ["bright"],
                "popularity": 8.0,
                "release_date": "2002-02-02",
                "metadata-qwen3_embedding_0.6b": [2.0, 3.0],
                "attributes-qwen3_embedding_0.6b": [4.0, 5.0],
                "lyrics-qwen3_embedding_0.6b": [],
                "age_group": "20s",
                "gender": "female",
                "country_name": "United States",
                "user_id": "user-2",
            },
        ],
    )

    args = SimpleNamespace(
        tid="talkplay_qwen3_4b_devset_smoke",
        batch_size=1,
        session_ids_file=None,
        num_sessions=0,
        exp_dir=str(tmp_path / "exp"),
        clear_cache=False,
    )

    run_inference_talkplay_devset.main(args)

    output_path = tmp_path / "exp" / "inference" / "devset" / "talkplay_qwen3_4b_devset_smoke.json"
    trace_path = tmp_path / "exp" / "inference" / "devset" / "talkplay_qwen3_4b_devset_smoke_trace.json"
    rows = json.loads(output_path.read_text())
    traces = json.loads(trace_path.read_text())

    assert rows[0]["predicted_track_ids"][:2] == ["track-1", "track-2"]
    assert traces[0]["tool_trace"]["fallback_used"] is True
    assert traces[0]["tool_trace"]["fallback_strategy"] == "fixed_pool"
    assert traces[0]["tool_trace"]["fallback_reason"] == "runtime_error"
    assert "agent chat failed" in traces[0]["tool_trace"]["error_message"]


def test_classify_talkplay_failure_marks_missing_tool_call_cases():
    assert (
        run_inference_talkplay_devset.classify_talkplay_failure("151668 is not in list")
        == "tool_call_missing"
    )
    assert (
        run_inference_talkplay_devset.classify_talkplay_failure(
            "TalkPlay result did not include any tool call results."
        )
        == "tool_call_missing"
    )


def test_run_inference_talkplay_devset_passes_generate_response_flag(monkeypatch, tmp_path):
    fake_agent = _FakeAgent()
    captured_kwargs = {}
    config = _talkplay_config()
    config.generate_response = False
    monkeypatch.setattr(
        run_inference_talkplay_devset.OmegaConf,
        "load",
        lambda _: config,
    )
    monkeypatch.setattr(
        run_inference_talkplay_devset,
        "load_talkplay_agent",
        lambda model_name, cache_dir, **kwargs: captured_kwargs.update(kwargs) or fake_agent,
    )
    monkeypatch.setattr(
        run_inference_talkplay_devset,
        "load_dataset",
        lambda name, split=None: {
            "ignored": [
                {
                    "session_id": "session-1",
                    "user_id": "user-1",
                    "user_profile": {
                        "age_group": "20s",
                        "gender": "female",
                        "country_name": "United States",
                    },
                    "conversations": _build_conversations(),
                }
            ],
        }[name]
        if split == "test"
        else [
            {
                "track_id": "track-1",
                "track_name": ["Song"],
                "artist_name": ["Artist"],
                "album_name": ["Album"],
                "tag_list": ["calm"],
                "popularity": 10.0,
                "release_date": "2001-01-01",
                "metadata-qwen3_embedding_0.6b": [1.0, 2.0],
                "attributes-qwen3_embedding_0.6b": [3.0, 4.0],
                "lyrics-qwen3_embedding_0.6b": [],
                "age_group": "20s",
                "gender": "female",
                "country_name": "United States",
                "user_id": "user-1",
            }
        ],
    )

    args = SimpleNamespace(
        tid="talkplay_qwen3_4b_devset_smoke",
        batch_size=1,
        session_ids_file=None,
        num_sessions=0,
        exp_dir=str(tmp_path / "exp"),
        clear_cache=False,
    )

    run_inference_talkplay_devset.main(args)

    assert captured_kwargs["generate_response"] is False


def test_run_inference_talkplay_devset_passes_litellm_backend_kwargs(monkeypatch, tmp_path):
    fake_agent = _FakeAgent()
    captured_kwargs = {}
    config = _talkplay_config()
    config.model_name = "openrouter/qwen/qwen3.5-9b"
    config.llm_backend = "litellm"
    config.llm_kwargs = {"api_base": "https://openrouter.ai/api/v1", "temperature": 0.0}
    monkeypatch.setattr(
        run_inference_talkplay_devset.OmegaConf,
        "load",
        lambda _: config,
    )
    monkeypatch.setattr(
        run_inference_talkplay_devset,
        "load_talkplay_agent",
        lambda model_name, cache_dir, **kwargs: captured_kwargs.update(kwargs) or fake_agent,
    )
    monkeypatch.setattr(
        run_inference_talkplay_devset,
        "load_dataset",
        lambda name, split=None: {
            "ignored": [
                {
                    "session_id": "session-1",
                    "user_id": "user-1",
                    "user_profile": {
                        "age_group": "20s",
                        "gender": "female",
                        "country_name": "United States",
                    },
                    "conversations": _build_conversations(),
                }
            ],
        }[name]
        if split == "test"
        else [
            {
                "track_id": "track-1",
                "track_name": ["Song"],
                "artist_name": ["Artist"],
                "album_name": ["Album"],
                "tag_list": ["calm"],
                "popularity": 10.0,
                "release_date": "2001-01-01",
                "metadata-qwen3_embedding_0.6b": [1.0, 2.0],
                "attributes-qwen3_embedding_0.6b": [3.0, 4.0],
                "lyrics-qwen3_embedding_0.6b": [],
                "age_group": "20s",
                "gender": "female",
                "country_name": "United States",
                "user_id": "user-1",
            }
        ],
    )

    args = SimpleNamespace(
        tid="talkplay_openrouter_qwen35_9b_devset_smoke",
        batch_size=1,
        session_ids_file=None,
        num_sessions=0,
        exp_dir=str(tmp_path / "exp"),
        clear_cache=False,
    )

    run_inference_talkplay_devset.main(args)

    assert captured_kwargs["llm_backend"] == "litellm"
    assert captured_kwargs["llm_kwargs"] == {
        "api_base": "https://openrouter.ai/api/v1",
        "temperature": 0.0,
    }


def test_prepare_talkplay_smoke_cache_writes_minimal_assets(monkeypatch, tmp_path):
    datasets_by_name = {
        "tracks": [
            {
                "track_id": "track-1",
                "track_name": ["Song"],
                "artist_name": ["Artist"],
                "album_name": ["Album"],
                "tag_list": ["calm", "piano"],
                "popularity": 12.0,
                "release_date": "2001-01-01",
            }
        ],
        "track-embs": [
            {
                "track_id": "track-1",
                "metadata-qwen3_embedding_0.6b": [1.0, 2.0],
                "attributes-qwen3_embedding_0.6b": [3.0, 4.0],
                "lyrics-qwen3_embedding_0.6b": [],
            }
        ],
        "users": [
            {
                "user_id": "user-1",
                "age_group": "20s",
                "gender": "female",
                "country_name": "United States",
            }
        ],
    }

    monkeypatch.setattr(
        run_inference_talkplay_devset,
        "load_dataset",
        lambda name, split=None: datasets_by_name[name],
    )

    config = OmegaConf.create(
        {
            "cache_dir": str(tmp_path / "cache"),
            "track_dataset_name": "tracks",
            "track_embeddings_dataset_name": "track-embs",
            "user_dataset_name": "users",
            "track_split": "all_tracks",
            "user_split": "all_users",
        }
    )

    run_inference_talkplay_devset.prepare_talkplay_smoke_cache(config)

    test_metadata = json.loads((tmp_path / "cache" / "metadata" / "test_metadata.json").read_text())
    user_profiles = json.loads((tmp_path / "cache" / "metadata" / "user_profiles.json").read_text())
    vector_db = torch.load(tmp_path / "cache" / "encoder" / "vector_db.pt", map_location="cpu")

    assert test_metadata["track-1"]["track_release_date_spotify"] == "2001-01-01"
    assert test_metadata["track-1"]["lyrics"] == "calm piano"
    assert user_profiles["user-1"]["user_type"] == "cold_start"
    assert user_profiles["user-1"]["last_track_ids"] == []
    assert set(vector_db.keys()) == {"metadata", "attributes", "lyrics"}
    assert torch.equal(vector_db["metadata"]["track-1"], torch.tensor([1.0, 2.0], dtype=torch.float32))
    assert torch.equal(vector_db["lyrics"]["track-1"], torch.tensor([3.0, 4.0], dtype=torch.float32))
