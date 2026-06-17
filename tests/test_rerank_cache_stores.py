from __future__ import annotations

import importlib.util
import json
import sys
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
