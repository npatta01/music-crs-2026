from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcrs.embeddings.embedding_cache import (
    CachedTextEmbedder,
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


def test_disk_cache_rejects_bad_key_on_get(tmp_path: Path):
    store = DiskVectorCache(tmp_path)
    with pytest.raises(ValueError):
        store.get("bad/key")


class FakeEncoder:
    """Deterministic encoder that records every batch it is asked to encode."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def embed_batch(self, texts):
        self.calls.append(list(texts))
        return [[float(len(t)), float(sum(map(ord, t)) % 97)] for t in texts]


def test_wrapper_caches_across_calls(tmp_path):
    enc = FakeEncoder()
    cached = CachedTextEmbedder(enc, DiskVectorCache(tmp_path), "ns")
    first = cached.embed_batch(["a", "b"])
    second = cached.embed_batch(["a", "b"])
    assert first == second
    assert enc.calls == [["a", "b"]]  # second call served entirely from cache


def test_wrapper_encodes_only_misses(tmp_path):
    enc = FakeEncoder()
    cached = CachedTextEmbedder(enc, DiskVectorCache(tmp_path), "ns")
    cached.embed_batch(["a"])
    out = cached.embed_batch(["a", "c"])
    assert enc.calls == [["a"], ["c"]]  # only the miss "c" re-encoded
    assert out[0] == [1.0, float(ord("a") % 97)]


def test_wrapper_dedups_within_a_call(tmp_path):
    enc = FakeEncoder()
    cached = CachedTextEmbedder(enc, DiskVectorCache(tmp_path), "ns")
    out = cached.embed_batch(["a", "a", "b"])
    assert enc.calls == [["a", "b"]]  # "a" encoded once
    assert out[0] == out[1]  # fanned back to both positions
    assert len(out) == 3


def test_wrapper_preserves_input_order(tmp_path):
    enc = FakeEncoder()
    cached = CachedTextEmbedder(enc, DiskVectorCache(tmp_path), "ns")
    texts = ["zzz", "y", "xx"]
    out = cached.embed_batch(texts)
    expected = enc.embed_batch(texts)  # same deterministic fn, fresh encoder
    assert out == expected


def test_wrapper_disabled_is_passthrough(tmp_path):
    enc = FakeEncoder()
    store = DiskVectorCache(tmp_path)
    cached = CachedTextEmbedder(enc, store, "ns", enabled=False)
    cached.embed_batch(["a", "a"])
    assert enc.calls == [["a", "a"]]  # no dedup, no caching
    assert not list(tmp_path.rglob("*.json"))  # store untouched


def test_wrapper_empty_input(tmp_path):
    enc = FakeEncoder()
    cached = CachedTextEmbedder(enc, DiskVectorCache(tmp_path), "ns")
    assert cached.embed_batch([]) == []
    assert enc.calls == []
