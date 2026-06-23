from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import numpy as np


def _load_module(name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    sys.path.insert(0, str(module_path.parent))
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_catalog_artist_ids_prefers_lance_reader(monkeypatch):
    module = _load_module("rerank_catalog_utils_lance", "scripts/rerank/catalog_utils.py")

    class FakeLanceTable:
        def to_pydict(self):
            return {"track_id": ["t1"], "artist_id": [["a1"]]}

    class FakeLance:
        def to_table(self, columns):
            assert columns == ["track_id", "artist_id"]
            return FakeLanceTable()

    class FakeTable:
        def to_lance(self):
            return FakeLance()

    fake_lancedb = types.SimpleNamespace(
        connect=lambda db_uri: types.SimpleNamespace(
            open_table=lambda table_name: FakeTable()
        )
    )
    monkeypatch.setitem(sys.modules, "lancedb", fake_lancedb)

    assert module.catalog_artist_ids("cache/lancedb") == {
        "track_id": ["t1"],
        "artist_id": [["a1"]],
    }


def test_catalog_artist_ids_falls_back_to_arrow_without_pylance(monkeypatch):
    module = _load_module("rerank_catalog_utils_arrow", "scripts/rerank/catalog_utils.py")

    class FakeArrowTable:
        def select(self, columns):
            assert columns == ["track_id", "artist_id"]
            return self

        def to_pydict(self):
            return {"track_id": ["t2"], "artist_id": [["a2"]]}

    class FakeTable:
        def to_lance(self):
            raise ImportError("pylance")

        def to_arrow(self):
            return FakeArrowTable()

    fake_lancedb = types.SimpleNamespace(
        connect=lambda db_uri: types.SimpleNamespace(
            open_table=lambda table_name: FakeTable()
        )
    )
    monkeypatch.setitem(sys.modules, "lancedb", fake_lancedb)

    assert module.catalog_artist_ids("cache/lancedb") == {
        "track_id": ["t2"],
        "artist_id": [["a2"]],
    }


def test_embed_memo_flush_merges_with_existing_file_updates(tmp_path):
    module = _load_module("build_features_embed_memo_merge", "scripts/rerank/build_features.py")
    path = tmp_path / "memo.json"

    first = module.EmbedMemo(path)
    second = module.EmbedMemo(path)
    first.memo["a"] = [1.0]
    first._dirty = 1
    second.memo["b"] = [2.0]
    second._dirty = 1

    first.flush()
    second.flush()

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "a": [1.0],
        "b": [2.0],
    }


def test_npz_embed_store_flush_allocates_chunks_from_current_disk_state(tmp_path):
    module = _load_module("build_features_npz_store_chunks", "scripts/rerank/build_features.py")
    store_dir = tmp_path / "msg_store"

    first = module.NpzEmbedStore(store_dir)
    second = module.NpzEmbedStore(store_dir)
    first.add("first", np.array([1.0, 0.0], dtype=np.float32))
    second.add("second", np.array([0.0, 1.0], dtype=np.float32))

    first.flush()
    second.flush()

    assert sorted(path.name for path in store_dir.glob("chunk_*.npz")) == [
        "chunk_00000.npz",
        "chunk_00001.npz",
    ]
    reloaded = module.NpzEmbedStore(store_dir)
    vectors = reloaded.get_many(["first", "second"], offline=True)
    assert set(vectors) == {"first", "second"}
    np.testing.assert_allclose(vectors["first"], np.array([1.0, 0.0], dtype=np.float32))
    np.testing.assert_allclose(vectors["second"], np.array([0.0, 1.0], dtype=np.float32))


def test_npz_embed_store_flush_skips_keys_written_by_another_instance(tmp_path):
    module = _load_module("build_features_npz_store_skip_existing", "scripts/rerank/build_features.py")
    store_dir = tmp_path / "msg_store"

    first = module.NpzEmbedStore(store_dir)
    second = module.NpzEmbedStore(store_dir)
    first.add("shared", np.array([1.0, 0.0], dtype=np.float32))
    second.add("shared", np.array([0.0, 1.0], dtype=np.float32))

    first.flush()
    second.flush()

    assert sorted(path.name for path in store_dir.glob("chunk_*.npz")) == ["chunk_00000.npz"]
    reloaded = module.NpzEmbedStore(store_dir)
    vectors = reloaded.get_many(["shared"], offline=True)
    np.testing.assert_allclose(vectors["shared"], np.array([1.0, 0.0], dtype=np.float32))


def test_build_features_allows_embedding_fill_by_default_and_flushes_msg_store(monkeypatch, tmp_path):
    module = _load_module("build_features_cli_offline_flag", "scripts/rerank/build_features.py")
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        json.dumps({"session_id": "s1", "turn_number": 1, "trace": {}}) + "\n",
        encoding="utf-8",
    )
    gt_path = tmp_path / "ground_truth.json"
    gt_path.write_text(
        json.dumps([{"session_id": "s1", "turn_number": 1, "ground_truth_track_id": "t1"}]),
        encoding="utf-8",
    )
    branch_names_path = tmp_path / "branch_names.json"
    branch_names_path.write_text(json.dumps([]), encoding="utf-8")

    captured_offline: list[bool] = []

    fake_features = types.ModuleType("features_v9")

    class FakeTurnContext:
        def __init__(self, *args, offline=True, **kwargs):
            captured_offline.append(offline)

    fake_features.TurnContext = FakeTurnContext
    fake_features.compute_turn_features = lambda row, ctx, gt=None: ([], True)
    monkeypatch.setitem(sys.modules, "features_v9", fake_features)

    class FakeMemo:
        def __init__(self, path):
            self.path = path

        def flush(self):
            pass

    class FakeMsgStore:
        instances = []

        def __init__(self, path):
            self.path = path
            self.flushed = 0
            self.instances.append(self)

        def flush(self):
            self.flushed += 1

    fake_catalog = types.SimpleNamespace(meta={}, vec={}, has_duration=False)

    monkeypatch.setattr(module, "Catalog", lambda *args, **kwargs: fake_catalog)
    monkeypatch.setattr(module, "load_sessions", lambda: {})
    monkeypatch.setattr(module, "load_user_cf", lambda: {})
    monkeypatch.setattr(
        module,
        "TagEmbeddingIndex",
        types.SimpleNamespace(load=lambda path: types.SimpleNamespace(tags=[], matrix=[])),
    )
    monkeypatch.setattr(module, "TieredTagResolver", lambda **kwargs: object())
    monkeypatch.setattr(module, "EmbedMemo", FakeMemo)
    monkeypatch.setattr(module, "NpzEmbedStore", FakeMsgStore)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_features.py",
            "--trace",
            str(trace_path),
            "--ground-truth",
            str(gt_path),
            "--db-uri",
            str(tmp_path / "lancedb"),
            "--tag-index",
            str(tmp_path / "tag_index.npz"),
            "--branch-names",
            str(branch_names_path),
            "--msg-store",
            str(tmp_path / "msg_store"),
            "--out",
            str(tmp_path / "features.parquet"),
            "--num-shards",
            "1",
        ],
    )

    module.main()

    assert captured_offline == [False]
    assert FakeMsgStore.instances[0].flushed == 1


def test_build_features_main_loads_dotenv_before_embedding_fill(monkeypatch, tmp_path):
    module = _load_module("build_features_loads_dotenv", "scripts/rerank/build_features.py")
    (tmp_path / ".env").write_text("DEEPINFRA_API_KEY=from-dotenv\n", encoding="utf-8")

    trace_path = tmp_path / "trace.jsonl"
    gt_path = tmp_path / "ground_truth.json"
    branch_names_path = tmp_path / "branch_names.json"
    out_dir = tmp_path / "features"
    env_seen: list[str | None] = []

    def fake_sharded_build(args):
        env_seen.append(os.environ.get("DEEPINFRA_API_KEY"))

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    monkeypatch.setattr(module, "run_sharded_build", fake_sharded_build, raising=False)
    monkeypatch.setattr(
        module,
        "Catalog",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run inline")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_features.py",
            "--trace",
            str(trace_path),
            "--ground-truth",
            str(gt_path),
            "--db-uri",
            str(tmp_path / "lancedb"),
            "--tag-index",
            str(tmp_path / "tag_index.npz"),
            "--branch-names",
            str(branch_names_path),
            "--msg-store",
            str(tmp_path / "msg_store"),
            "--out",
            str(out_dir),
        ],
    )

    module.main()

    assert env_seen == ["from-dotenv"]


def test_build_features_defaults_to_parallel_shards(monkeypatch, tmp_path):
    module = _load_module("build_features_default_parallel", "scripts/rerank/build_features.py")
    trace_path = tmp_path / "trace.jsonl"
    gt_path = tmp_path / "ground_truth.json"
    branch_names_path = tmp_path / "branch_names.json"
    out_dir = tmp_path / "features"
    calls = []

    def fake_sharded_build(args):
        calls.append(args)

    monkeypatch.setattr(module, "run_sharded_build", fake_sharded_build, raising=False)
    monkeypatch.setattr(
        module,
        "Catalog",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run inline")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_features.py",
            "--trace",
            str(trace_path),
            "--ground-truth",
            str(gt_path),
            "--db-uri",
            str(tmp_path / "lancedb"),
            "--tag-index",
            str(tmp_path / "tag_index.npz"),
            "--branch-names",
            str(branch_names_path),
            "--msg-store",
            str(tmp_path / "msg_store"),
            "--out",
            str(out_dir),
        ],
    )

    module.main()

    assert len(calls) == 1
    args = calls[0]
    assert args.num_shards == 12
    assert args.num_workers == 4
    assert Path(args.out) == out_dir
    assert args.shard_id is None
