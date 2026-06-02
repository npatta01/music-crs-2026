from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcrs.embeddings.embedding_cache import (
    DiskVectorCache,
    make_key,
)


def test_make_key_is_stable_and_namespaced():
    k1 = make_key("ns-a", "hello")
    k2 = make_key("ns-a", "hello")
    k3 = make_key("ns-b", "hello")
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 64 and all(c in "0123456789abcdef" for c in k1)


def test_disk_cache_set_then_get_roundtrips(tmp_path: Path):
    store = DiskVectorCache(tmp_path)
    key = make_key("ns", "song about rain")
    assert store.get(key) is None
    store.set(key, [0.1, 0.2, 0.3])
    assert store.get(key) == [0.1, 0.2, 0.3]


def test_disk_cache_missing_returns_none(tmp_path: Path):
    store = DiskVectorCache(tmp_path)
    assert store.get(make_key("ns", "never written")) is None


def test_disk_cache_corrupt_file_returns_none(tmp_path: Path):
    store = DiskVectorCache(tmp_path)
    key = make_key("ns", "x")
    store.set(key, [1.0])
    # Corrupt the stored file in place.
    path = next(p for p in tmp_path.rglob("*.json"))
    path.write_text("{ not json", encoding="utf-8")
    assert store.get(key) is None


def test_disk_cache_writes_valid_json(tmp_path: Path):
    store = DiskVectorCache(tmp_path)
    store.set(make_key("ns", "y"), [1.5, 2.5])
    path = next(p for p in tmp_path.rglob("*.json"))
    assert json.loads(path.read_text(encoding="utf-8")) == [1.5, 2.5]


def test_disk_cache_rejects_bad_key(tmp_path: Path):
    store = DiskVectorCache(tmp_path)
    with pytest.raises(ValueError):
        store.set("bad/key", [1.0])
