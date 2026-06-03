import importlib.util
import json
import sys
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


def _milvus_config():
    return OmegaConf.create(
        {
            "lm_type": "dummy",
            "retrieval_type": "milvus",
            "qu_type": "passthrough",
            "test_dataset_name": "ignored",
            "item_db_name": "ignored",
            "user_db_name": "ignored",
            "track_split_types": ["all_tracks"],
            "user_split_types": ["all_users"],
            "corpus_types": ["track_name", "artist_name", "album_name", "release_date", "tag_list"],
            "cache_dir": "./cache",
            "device": "cpu",
            "attn_implementation": "eager",
            "retrieval_topk": 1000,
            "retrieval_config": {
                "uri": "http://localhost:19530",
                "db_name": "default",
                "collection_name": "music_track_catalog",
                "searches": [
                    {
                        "name": "bm25_with_tag_list",
                        "kind": "bm25_compat",
                        "corpus_fields": [
                            "track_name",
                            "artist_name",
                            "album_name",
                            "release_date",
                            "tag_list",
                        ],
                        "weight": 1.0,
                        "topk": 1000,
                    }
                ],
                "fusion": {"method": "weighted"},
            },
        }
    )


def _lancedb_config():
    return OmegaConf.create(
        {
            "lm_type": "dummy",
            "retrieval_type": "lancedb",
            "qu_type": "passthrough",
            "test_dataset_name": "ignored",
            "item_db_name": "ignored",
            "user_db_name": "ignored",
            "track_split_types": ["all_tracks"],
            "user_split_types": ["all_users"],
            "corpus_types": ["track_name", "artist_name", "album_name", "release_date", "tag_list"],
            "cache_dir": "./cache",
            "device": "cpu",
            "attn_implementation": "eager",
            "retrieval_topk": 1000,
            "retrieval_config": {
                "db_uri": "./cache/lancedb",
                "table_name": "music_track_catalog",
                "searches": [
                    {
                        "name": "bm25_with_tag_list",
                        "kind": "fts_bm25s_compat",
                        "corpus_fields": [
                            "track_name",
                            "artist_name",
                            "album_name",
                            "release_date",
                            "tag_list",
                        ],
                        "weight": 1.0,
                        "topk": 1000,
                    }
                ],
                "fusion": {"method": "weighted_rrf"},
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


def test_run_inference_devset_passes_milvus_retrieval_config_unchanged(monkeypatch, tmp_path):
    captured = {}

    def fake_load_crs_baseline(**kwargs):
        captured.update(kwargs)
        return _FakeCRS()

    monkeypatch.setattr(run_inference_devset.OmegaConf, "load", lambda _: _milvus_config())
    monkeypatch.setattr(run_inference_devset, "load_crs_baseline", fake_load_crs_baseline)
    monkeypatch.setattr(run_inference_devset, "load_dataset", lambda *args, **kwargs: [])

    args = SimpleNamespace(
        tid="milvus_benchmark_devset",
        batch_size=1,
        session_ids_file=None,
        num_sessions=0,
        exp_dir=str(tmp_path / "exp"),
        clear_cache=False,
    )

    run_inference_devset.main(args)

    assert captured["retrieval_type"] == "milvus"
    assert captured["retrieval_config"] == {
        "uri": "http://localhost:19530",
        "db_name": "default",
        "collection_name": "music_track_catalog",
        "searches": [
            {
                "name": "bm25_with_tag_list",
                "kind": "bm25_compat",
                "corpus_fields": [
                    "track_name",
                    "artist_name",
                    "album_name",
                    "release_date",
                    "tag_list",
                ],
                "weight": 1.0,
                "topk": 1000,
            }
        ],
        "fusion": {"method": "weighted"},
    }


def test_run_inference_devset_passes_lancedb_retrieval_config_unchanged(monkeypatch, tmp_path):
    captured = {}

    def fake_load_crs_baseline(**kwargs):
        captured.update(kwargs)
        return _FakeCRS()

    monkeypatch.setattr(run_inference_devset.OmegaConf, "load", lambda _: _lancedb_config())
    monkeypatch.setattr(run_inference_devset, "load_crs_baseline", fake_load_crs_baseline)
    monkeypatch.setattr(run_inference_devset, "load_dataset", lambda *args, **kwargs: [])

    args = SimpleNamespace(
        tid="lancedb_fts_with_tag_list_devset",
        batch_size=1,
        session_ids_file=None,
        num_sessions=0,
        exp_dir=str(tmp_path / "exp"),
        clear_cache=False,
    )

    run_inference_devset.main(args)

    assert captured["retrieval_type"] == "lancedb"
    assert captured["device"] == "cpu"
    assert captured["retrieval_config"]["db_uri"] == "./cache/lancedb"
    assert captured["retrieval_config"]["fusion"] == {"method": "weighted_rrf"}


def test_blindset_shard_slice_keeps_each_session_in_one_shard():
    """Contiguous index slicing partitions blindset sessions with no overlap."""
    total = 47
    seen = set()
    for num_shards in (1, 3, 5, 8):
        seen.clear()
        for shard_id in range(num_shards):
            start = (shard_id * total) // num_shards
            end = ((shard_id + 1) * total) // num_shards
            for i in range(start, end):
                assert i not in seen
                seen.add(i)
        assert seen == set(range(total))


def _load_blindset_module():
    module_path = Path(__file__).resolve().parents[1] / "run_inference_blindset.py"
    sys.path.insert(0, str(module_path.parent))
    spec = importlib.util.spec_from_file_location("run_inference_blindset_mod", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_blindset_main_writes_suffixed_shard_output(tmp_path, monkeypatch):
    module = _load_blindset_module()

    rows = [
        {"user_id": f"u{i}", "session_id": f"s{i}",
         "conversations": [{"role": "user", "content": "hi", "turn_number": 1}]}
        for i in range(4)
    ]

    class _FakeDB(list):
        def select(self, idx):
            return _FakeDB(self[i] for i in idx)

    monkeypatch.setattr(module, "load_dataset", lambda *a, **k: _FakeDB(rows))

    class _FakeCRS:
        def batch_chat(self, batch):
            return [{"retrieval_items": ["t1"], "response": "r"} for _ in batch]

    monkeypatch.setattr(module, "load_crs_baseline", lambda **k: _FakeCRS())
    monkeypatch.setattr(module, "chat_history_parser", lambda conv, crs, tn: ([], "q"))

    cfg = {
        "lm_type": "dummy", "retrieval_type": "dummy", "item_db_name": "x",
        "user_db_name": "x", "track_split_types": [], "user_split_types": [],
        "corpus_types": [], "cache_dir": "./cache", "device": "cpu",
        "attn_implementation": "eager", "test_dataset_name": "x",
    }
    monkeypatch.setattr(module.OmegaConf, "load", lambda p: OmegaConf.create(cfg))

    args = SimpleNamespace(
        tid="foo_blindset_A", eval_dataset="blindset_A", batch_size=2,
        exp_dir=str(tmp_path), clear_cache=False,
        num_shards=2, shard_id=0, output_suffix=".run_RID.shard_0",
    )
    module.main(args)

    out = tmp_path / "inference" / "blindset_A" / "foo_blindset_A.run_RID.shard_0.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert {r["session_id"] for r in data} == {"s0", "s1"}  # shard 0 of 2 over 4 sessions


def test_blindset_main_rejects_out_of_range_shard_id(monkeypatch, tmp_path):
    module = _load_blindset_module()

    rows = [
        {"user_id": "u0", "session_id": "s0",
         "conversations": [{"role": "user", "content": "hi", "turn_number": 1}]}
    ]

    class _FakeDB(list):
        def select(self, idx):
            return _FakeDB(self[i] for i in idx)

    monkeypatch.setattr(module, "load_dataset", lambda *a, **k: _FakeDB(rows))
    monkeypatch.setattr(module, "load_crs_baseline", lambda **k: object())
    monkeypatch.setattr(module, "chat_history_parser", lambda conv, crs, tn: ([], "q"))

    cfg = {
        "lm_type": "dummy", "retrieval_type": "dummy", "item_db_name": "x",
        "user_db_name": "x", "track_split_types": [], "user_split_types": [],
        "corpus_types": [], "cache_dir": "./cache", "device": "cpu",
        "attn_implementation": "eager", "test_dataset_name": "x",
    }
    from omegaconf import OmegaConf
    monkeypatch.setattr(module.OmegaConf, "load", lambda p: OmegaConf.create(cfg))

    import pytest
    args = SimpleNamespace(
        tid="foo_blindset_A", eval_dataset="blindset_A", batch_size=2,
        exp_dir=str(tmp_path), clear_cache=False,
        num_shards=3, shard_id=5, output_suffix="",
    )
    with pytest.raises(ValueError, match="out of range"):
        module.main(args)


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
