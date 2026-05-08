from pathlib import Path
from types import SimpleNamespace

from omegaconf import OmegaConf

import run_inference_blindset
import run_inference_devset


class _FakeCRS:
    def __init__(self):
        self.item_db = SimpleNamespace(id_to_metadata=lambda track_id: f"track:{track_id}")

    def batch_chat(self, batch):
        return []


def _rewrite_config():
    return OmegaConf.create(
        {
            "lm_type": "dummy",
            "retrieval_type": "bm25",
            "qu_type": "llm_rewrite",
            "qu_kwargs": {
                "model_name": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
                "prompt_name": "preserve_entities_v1",
                "max_new_tokens": 96,
                "audit_path": "./exp/inference/devset/<tid>_rewrite_audit.jsonl",
                "stats_path": "./exp/inference/devset/<tid>_rewrite_stats.json",
            },
            "test_dataset_name": "ignored",
            "item_db_name": "ignored",
            "user_db_name": "ignored",
            "track_split_types": ["all_tracks"],
            "user_split_types": ["all_users"],
            "corpus_types": ["track_name", "artist_name", "album_name", "tag_list"],
            "cache_dir": "./cache",
            "device": "cpu",
            "attn_implementation": "eager",
            "retrieval_topk": 1000,
        }
    )


def _passthrough_config():
    return OmegaConf.create(
        {
            "lm_type": "dummy",
            "retrieval_type": "bm25",
            "qu_type": "passthrough",
            "test_dataset_name": "ignored",
            "item_db_name": "ignored",
            "user_db_name": "ignored",
            "track_split_types": ["all_tracks"],
            "user_split_types": ["all_users"],
            "corpus_types": ["track_name", "artist_name", "album_name", "tag_list"],
            "cache_dir": "./cache",
            "device": "cpu",
            "attn_implementation": "eager",
            "retrieval_topk": 1000,
        }
    )


def _agentic_config():
    return OmegaConf.create(
        {
            "pipeline_type": "agentic",
            "planner_backend": "litellm_chat_completions",
            "planner_model_name": "openai/qwen3.5-9b",
            "lm_type": "dummy",
            "retrieval_type": "bm25",
            "qu_type": "passthrough",
            "test_dataset_name": "ignored",
            "item_db_name": "ignored",
            "user_db_name": "ignored",
            "track_split_types": ["all_tracks"],
            "user_split_types": ["all_users"],
            "corpus_types": ["track_name", "artist_name", "album_name", "tag_list"],
            "cache_dir": "./cache",
            "device": "cpu",
            "attn_implementation": "eager",
            "retrieval_topk": 20,
            "toolcalling_config": {
                "max_planning_steps": 3,
                "enabled_tools": ["bm25_search", "text_to_item_similarity", "item_to_item_similarity", "user_to_item_similarity"],
                "allow_prediction_backfill": True,
                "planner_protocol": "structured_retrieval_bm25_boost",
                "bm25_boost_weight": 0.35,
            },
        }
    )


def test_run_inference_devset_passes_qu_kwargs(monkeypatch, tmp_path):
    captured = {}

    def fake_load_crs_baseline(**kwargs):
        captured.update(kwargs)
        return _FakeCRS()

    monkeypatch.setattr(run_inference_devset.OmegaConf, "load", lambda _: _rewrite_config())
    monkeypatch.setattr(run_inference_devset, "load_crs_baseline", fake_load_crs_baseline)
    monkeypatch.setattr(run_inference_devset, "load_dataset", lambda *args, **kwargs: [])

    args = SimpleNamespace(
        tid="wave3_devset",
        batch_size=1,
        session_ids_file=None,
        num_sessions=0,
        exp_dir=str(tmp_path / "exp"),
        clear_cache=False,
    )

    run_inference_devset.main(args)

    assert captured["qu_type"] == "llm_rewrite"
    assert captured["qu_kwargs"]["prompt_name"] == "preserve_entities_v1"
    assert captured["qu_kwargs"]["audit_path"] == str(
        tmp_path / "exp" / "inference" / "devset" / "wave3_devset_rewrite_audit.jsonl"
    )
    assert captured["qu_kwargs"]["stats_path"] == str(
        tmp_path / "exp" / "inference" / "devset" / "wave3_devset_rewrite_stats.json"
    )


def test_run_inference_blindset_passes_qu_kwargs(monkeypatch, tmp_path):
    captured = {}

    def fake_load_crs_baseline(**kwargs):
        captured.update(kwargs)
        return _FakeCRS()

    monkeypatch.setattr(run_inference_blindset.OmegaConf, "load", lambda _: _rewrite_config())
    monkeypatch.setattr(run_inference_blindset, "load_crs_baseline", fake_load_crs_baseline)
    monkeypatch.setattr(run_inference_blindset, "load_dataset", lambda *args, **kwargs: [])

    args = SimpleNamespace(
        tid="wave3_blindset",
        eval_dataset="blindset_A",
        batch_size=1,
        exp_dir=str(tmp_path / "exp"),
        clear_cache=False,
    )

    run_inference_blindset.main(args)

    assert captured["qu_type"] == "llm_rewrite"
    assert captured["qu_kwargs"]["prompt_name"] == "preserve_entities_v1"
    assert captured["qu_kwargs"]["audit_path"] == str(
        tmp_path / "exp" / "inference" / "devset" / "wave3_blindset_rewrite_audit.jsonl"
    )
    assert captured["qu_kwargs"]["stats_path"] == str(
        tmp_path / "exp" / "inference" / "devset" / "wave3_blindset_rewrite_stats.json"
    )


def test_run_inference_devset_handles_missing_qu_kwargs(monkeypatch, tmp_path):
    captured = {}

    def fake_load_crs_baseline(**kwargs):
        captured.update(kwargs)
        return _FakeCRS()

    monkeypatch.setattr(run_inference_devset.OmegaConf, "load", lambda _: _passthrough_config())
    monkeypatch.setattr(run_inference_devset, "load_crs_baseline", fake_load_crs_baseline)
    monkeypatch.setattr(run_inference_devset, "load_dataset", lambda *args, **kwargs: [])

    args = SimpleNamespace(
        tid="control_devset",
        batch_size=1,
        session_ids_file=None,
        num_sessions=0,
        exp_dir=str(tmp_path / "exp"),
        clear_cache=False,
    )

    run_inference_devset.main(args)

    assert captured["qu_type"] == "passthrough"
    assert captured["qu_kwargs"] == {}


def test_run_inference_devset_passes_agentic_kwargs(monkeypatch, tmp_path):
    captured = {}

    def fake_load_crs_baseline(**kwargs):
        captured.update(kwargs)
        return _FakeCRS()

    monkeypatch.setattr(run_inference_devset.OmegaConf, "load", lambda _: _agentic_config())
    monkeypatch.setattr(run_inference_devset, "load_crs_baseline", fake_load_crs_baseline)
    monkeypatch.setattr(run_inference_devset, "load_dataset", lambda *args, **kwargs: [])

    args = SimpleNamespace(
        tid="agentic_devset_smoke",
        batch_size=1,
        session_ids_file=None,
        num_sessions=0,
        exp_dir=str(tmp_path / "exp"),
        clear_cache=False,
    )

    run_inference_devset.main(args)

    assert captured["pipeline_type"] == "agentic"
    assert captured["planner_backend"] == "litellm_chat_completions"
    assert captured["planner_model_name"] == "openai/qwen3.5-9b"
    assert captured["toolcalling_config"]["max_planning_steps"] == 3
    assert captured["toolcalling_config"]["enabled_tools"] == [
        "bm25_search",
        "text_to_item_similarity",
        "item_to_item_similarity",
        "user_to_item_similarity",
    ]
    assert captured["toolcalling_config"]["allow_prediction_backfill"] is True
    assert captured["toolcalling_config"]["planner_protocol"] == "structured_retrieval_bm25_boost"
    assert captured["toolcalling_config"]["bm25_boost_weight"] == 0.35


def test_run_inference_devset_writes_trace_sidecar(monkeypatch, tmp_path):
    class _FakeAgenticCRS:
        def __init__(self):
            self.item_db = SimpleNamespace(id_to_metadata=lambda track_id: f"track:{track_id}")

        def batch_chat(self, batch):
            return [
                {
                    "retrieval_items": ["track-2", "track-3"],
                    "response": "",
                    "tool_trace": {
                        "tool_names": ["bm25_search", "bm25_boost"],
                        "final_tool_name": "bm25_boost",
                        "raw_final_count": 2,
                        "unique_final_count": 2,
                        "backfilled_count": 18,
                    },
                }
            ]

    conversations = [
        {"turn_number": turn_number, "role": "user", "content": f"user turn {turn_number}"}
        for turn_number in range(1, 9)
    ]
    fake_dataset = [
        {
            "session_id": "session-1",
            "user_id": "user-1",
            "conversations": conversations,
        }
    ]

    monkeypatch.setattr(run_inference_devset.OmegaConf, "load", lambda _: _agentic_config())
    monkeypatch.setattr(run_inference_devset, "load_crs_baseline", lambda **_: _FakeAgenticCRS())
    monkeypatch.setattr(run_inference_devset, "load_dataset", lambda *args, **kwargs: fake_dataset)

    args = SimpleNamespace(
        tid="agentic_trace_smoke",
        batch_size=1,
        session_ids_file=None,
        num_sessions=0,
        exp_dir=str(tmp_path / "exp"),
        clear_cache=False,
    )

    run_inference_devset.main(args)

    trace_path = tmp_path / "exp" / "inference" / "devset" / "agentic_trace_smoke_trace.json"
    trace_rows = __import__("json").loads(trace_path.read_text(encoding="utf-8"))
    assert len(trace_rows) == 8
    assert trace_rows[0]["tool_trace"]["final_tool_name"] == "bm25_boost"
    assert trace_rows[0]["user_query"] == "user turn 1"


def test_blindset_chat_history_parser_resolves_music_turns():
    fake_crs = _FakeCRS()
    conversations = [
        {"turn_number": 1, "role": "user", "content": "Need mellow electronic"},
        {"turn_number": 1, "role": "assistant", "content": "Try this"},
        {"turn_number": 1, "role": "music", "content": "track-123"},
        {"turn_number": 2, "role": "user", "content": "More instrumental please"},
    ]

    chat_history, user_query = run_inference_blindset.chat_history_parser(
        conversations,
        fake_crs,
        target_turn_number=2,
    )

    assert user_query == "More instrumental please"
    assert chat_history[-1]["role"] == "music"
    assert chat_history[-1]["content"] == "track:track-123"
