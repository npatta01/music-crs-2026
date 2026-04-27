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
