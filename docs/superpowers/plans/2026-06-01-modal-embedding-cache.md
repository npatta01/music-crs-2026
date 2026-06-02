# Modal GPU Embedding Cache — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistently cache text→vector results for every GPU-native Modal embedder (Qwen3, SigLIP-2, CLAP) so repeated text encodes at most once per run and never across runs.

**Architecture:** A Modal-free, reusable `CachedTextEmbedder` wraps any object with `embed_batch(texts)`. It keys on `sha256(namespace\x00text)` and stores vectors as JSON files in a `DiskVectorCache` backed by a new dedicated Modal Volume v2, mounted on both GPU encoder classes. Cache logic is unit-tested locally; Modal wiring is verified by a static AST test.

**Tech Stack:** Python 3.10, pytest, Modal (Volume v2), OmegaConf config.

**Spec:** `docs/superpowers/specs/2026-06-01-modal-embedding-cache-design.md`

---

## File Structure

- **Create** `mcrs/embeddings/embedding_cache.py` — `KeyValueStore` protocol, `make_key`, `DiskVectorCache`, `CachedTextEmbedder`. One responsibility: cache a deterministic `embed_batch` call.
- **Create** `tests/test_embedding_cache.py` — unit tests for the store + wrapper with a fake encoder and temp dir.
- **Modify** `modal/config.yaml` — add `volumes.embedding_cache` + `container.embedding_cache_dir`.
- **Modify** `modal/app.py` — volume constants + object, mount on `Qwen3Encoder` and `MultimodalTextEncoder`, wrap clients in their `setup()`, add `@modal.exit()` commit.
- **Modify** `tests/test_modal_app_resources.py` — static AST test that both encoder classes mount the cache dir.

---

## Task 1: DiskVectorCache + KeyValueStore

**Files:**
- Create: `mcrs/embeddings/embedding_cache.py`
- Test: `tests/test_embedding_cache.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_embedding_cache.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_embedding_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mcrs.embeddings.embedding_cache'`

- [ ] **Step 3: Write the store implementation**

Create `mcrs/embeddings/embedding_cache.py`:

```python
"""Persistent cache for deterministic text->vector embedding calls.

`CachedTextEmbedder` wraps any object exposing `embed_batch(texts) ->
list[list[float]]` and serves repeated texts from a `KeyValueStore` instead
of re-encoding. `DiskVectorCache` is a self-contained on-disk store (one
JSON file per key, atomic writes, sharded layout) suitable for backing by a
Modal Volume. The store is swappable (e.g. modal.Dict) without touching the
wrapper.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Protocol

Vector = list[float]


def make_key(namespace: str, text: str) -> str:
    """Stable cache key for a (namespace, text) pair.

    `namespace` pins model identity + anything that changes the output
    vector (model name, dtype). Different namespaces never collide.
    """
    return hashlib.sha256(f"{namespace}\x00{text}".encode("utf-8")).hexdigest()


class KeyValueStore(Protocol):
    def get(self, key: str) -> Vector | None: ...

    def set(self, key: str, vec: Vector) -> None: ...


class DiskVectorCache:
    """On-disk vector cache: one JSON file per key, sharded `ab/cd/<key>.json`.

    Writes are atomic (temp file + os.replace). Any read problem (missing
    file, bad JSON, OS error) is treated as a cache miss and returns None —
    cache failures never propagate into the encode path.
    """

    def __init__(self, directory: str | os.PathLike[str]):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_key(key: str) -> str:
        if not isinstance(key, str) or not key:
            raise ValueError("cache key must be a non-empty string")
        if "/" in key or "\\" in key or "\x00" in key:
            raise ValueError("cache key must not contain a path separator or null byte")
        return key

    def _path(self, key: str) -> Path:
        key = self._validate_key(key)
        return self.directory / key[:2] / key[2:4] / f"{key}.json"

    def get(self, key: str) -> Vector | None:
        try:
            return json.loads(self._path(key).read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return None

    def set(self, key: str, vec: Vector) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.stem}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = handle.name
                json.dump(vec, handle, separators=(",", ":"))
            os.replace(temp_path, path)
            temp_path = None
        finally:
            if temp_path is not None:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_embedding_cache.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add mcrs/embeddings/embedding_cache.py tests/test_embedding_cache.py
git commit -m "feat(embeddings): DiskVectorCache + make_key for embedding cache"
```

---

## Task 2: CachedTextEmbedder wrapper

**Files:**
- Modify: `mcrs/embeddings/embedding_cache.py`
- Test: `tests/test_embedding_cache.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_embedding_cache.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_embedding_cache.py -k wrapper -v`
Expected: FAIL with `ImportError: cannot import name 'CachedTextEmbedder'` (or AttributeError once imported)

- [ ] **Step 3: Implement the wrapper**

Append to `mcrs/embeddings/embedding_cache.py`:

```python
class CachedTextEmbedder:
    """Wraps an `embed_batch` encoder with a persistent vector cache.

    On each call: dedup inputs, serve cached texts from `store`, encode only
    the misses via `inner.embed_batch`, persist them, and reassemble results
    in the original input order (duplicates fanned back to every position).
    When `enabled` is False it is a pure pass-through to `inner`.
    """

    def __init__(
        self,
        inner,
        store: KeyValueStore,
        namespace: str,
        enabled: bool = True,
    ):
        self._inner = inner
        self._store = store
        self._namespace = namespace
        self._enabled = enabled

    def embed_batch(self, texts: list[str]) -> list[Vector]:
        if not texts:
            return []
        if not self._enabled:
            return self._inner.embed_batch(list(texts))

        unique = list(dict.fromkeys(texts))  # dedup, first-seen order
        keys = {t: make_key(self._namespace, t) for t in unique}

        resolved: dict[str, Vector] = {}
        misses: list[str] = []
        for t in unique:
            hit = self._store.get(keys[t])
            if hit is None:
                misses.append(t)
            else:
                resolved[t] = hit

        if misses:
            encoded = self._inner.embed_batch(misses)
            for t, vec in zip(misses, encoded):
                self._store.set(keys[t], vec)
                resolved[t] = vec

        return [resolved[t] for t in texts]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_embedding_cache.py -v`
Expected: PASS (all tests, ~12 passed)

- [ ] **Step 5: Commit**

```bash
git add mcrs/embeddings/embedding_cache.py tests/test_embedding_cache.py
git commit -m "feat(embeddings): CachedTextEmbedder wrapper with partial-hit batching"
```

---

## Task 3: Wire the cache into Modal encoders

**Files:**
- Modify: `modal/config.yaml`
- Modify: `modal/app.py` (constants ~52-59, volume object ~89-92, `Qwen3Encoder` decorator+setup ~433-469, `MultimodalTextEncoder` decorator+setup ~1139-1176)
- Test: `tests/test_modal_app_resources.py`

- [ ] **Step 1: Write the failing static test**

Append to `tests/test_modal_app_resources.py`:

```python
def _class_volume_dir_consts(class_name: str) -> set[str]:
    """Constant names used as keys in a Modal class's `volumes=` dict literal."""
    tree = ast.parse((PROJECT_ROOT / "modal" / "app.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    for keyword in decorator.keywords:
                        if keyword.arg == "volumes" and isinstance(keyword.value, ast.Dict):
                            return {
                                k.id
                                for k in keyword.value.keys
                                if isinstance(k, ast.Name)
                            }
    return set()


def test_gpu_encoders_mount_embedding_cache():
    assert "EMBEDDING_CACHE_DIR" in _class_volume_dir_consts("Qwen3Encoder")
    assert "EMBEDDING_CACHE_DIR" in _class_volume_dir_consts("MultimodalTextEncoder")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_modal_app_resources.py::test_gpu_encoders_mount_embedding_cache -v`
Expected: FAIL (assertion: `EMBEDDING_CACHE_DIR` not in set)

- [ ] **Step 3: Add config entries**

In `modal/config.yaml`, under `volumes:` add (after the `litellm_cache:` line):

```yaml
  # Volume v2 cache for GPU-native text embeddings (Qwen3, SigLIP-2, CLAP).
  embedding_cache: "music-crs-embedding-cache"
```

Under `container:` add (after the `litellm_cache_dir:` line):

```yaml
  embedding_cache_dir: "/root/embedding-cache"
```

- [ ] **Step 4: Add constants + volume object in app.py**

In `modal/app.py`, after the `LITELLM_CACHE_VOLUME = _cfg.volumes.litellm_cache` line (~55) add:

```python
EMBEDDING_CACHE_VOLUME = _cfg.volumes.embedding_cache
```

After the `LITELLM_CACHE_DIR = _cfg.container.litellm_cache_dir` line (~59) add:

```python
EMBEDDING_CACHE_DIR = _cfg.container.embedding_cache_dir
```

After the `litellm_cache_vol = modal.Volume.from_name(...)` line (~92) add:

```python
embedding_cache_vol = modal.Volume.from_name(
    EMBEDDING_CACHE_VOLUME, create_if_missing=True, version=2
)
```

- [ ] **Step 5: Mount + wrap in Qwen3Encoder**

In `modal/app.py`, change the `Qwen3Encoder` `@app.cls(...)` decorator's volumes (currently `volumes={HF_CACHE_DIR: hf_cache_vol},` ~433) to:

```python
    volumes={HF_CACHE_DIR: hf_cache_vol, EMBEDDING_CACHE_DIR: embedding_cache_vol},
```

In `Qwen3Encoder.setup`, after the existing `self.client._ensure_loaded()` line, append:

```python
        from mcrs.embeddings.embedding_cache import (
            CachedTextEmbedder,
            DiskVectorCache,
        )

        cache_enabled = os.environ.get("EMBEDDING_CACHE_ENABLED", "1") != "0"
        self.client = CachedTextEmbedder(
            self.client,
            DiskVectorCache(EMBEDDING_CACHE_DIR),
            f"qwen3:Qwen3-Embedding-0.6B:dtype={QWEN3_ENCODER_TORCH_DTYPE}",
            enabled=cache_enabled,
        )
```

Add a flush method to the `Qwen3Encoder` class (after `embed_batch`):

```python
    @modal.exit()
    def _commit_embedding_cache(self):
        embedding_cache_vol.commit()
```

- [ ] **Step 6: Mount + wrap in MultimodalTextEncoder**

In `modal/app.py`, change the `MultimodalTextEncoder` `@app.cls(...)` decorator's volumes (currently `volumes={HF_CACHE_DIR: hf_cache_vol},` ~1139) to:

```python
    volumes={HF_CACHE_DIR: hf_cache_vol, EMBEDDING_CACHE_DIR: embedding_cache_vol},
```

In `MultimodalTextEncoder.setup`, after the `self.clap = ClapTextEmbeddingClient(...)` + `self.clap._ensure_loaded()` lines, append:

```python
        from mcrs.embeddings.embedding_cache import (
            CachedTextEmbedder,
            DiskVectorCache,
        )

        store = DiskVectorCache(EMBEDDING_CACHE_DIR)
        cache_enabled = os.environ.get("EMBEDDING_CACHE_ENABLED", "1") != "0"
        self.siglip = CachedTextEmbedder(
            self.siglip,
            store,
            "siglip2:google/siglip2-base-patch16-224",
            enabled=cache_enabled,
        )
        self.clap = CachedTextEmbedder(
            self.clap,
            store,
            "clap:music_audioset_epoch_15_esc_90.14",
            enabled=cache_enabled,
        )
```

Add a flush method to the `MultimodalTextEncoder` class (after `embed_clap_text`):

```python
    @modal.exit()
    def _commit_embedding_cache(self):
        embedding_cache_vol.commit()
```

- [ ] **Step 7: Run the static test + full suite**

Run: `pytest tests/test_modal_app_resources.py::test_gpu_encoders_mount_embedding_cache tests/test_embedding_cache.py -v`
Expected: PASS

Run: `pytest tests/test_modal_app_resources.py -v`
Expected: PASS (existing resource tests still green — the new mount doesn't break them)

- [ ] **Step 8: Commit**

```bash
git add modal/config.yaml modal/app.py tests/test_modal_app_resources.py
git commit -m "feat(modal): mount embedding cache volume + wrap GPU encoders"
```

---

## Task 4: Manual Modal smoke verification (no automated test)

**Files:** none (operational check)

- [ ] **Step 1: Deploy**

Run: `modal deploy modal/app.py`
Expected: deploys without error; `music-crs-embedding-cache` volume auto-created on first encoder cold start.

- [ ] **Step 2: Smoke a ~50-session devset slice** (per the "Modal full-devset needs approval" rule — slice first, report metrics, await go-ahead before any full run)

Run: `python run_experiment.py --backend modal --tid llama1b_bm25_devset --batch_size 16` against a small slice.
Expected: completes; metrics unchanged vs. baseline (cache must not alter vectors).

- [ ] **Step 3: Confirm cache populated**

Run: `modal volume ls music-crs-embedding-cache`
Expected: sharded directories with `.json` files present after the run.

- [ ] **Step 4: Confirm re-run is faster**

Re-run the same slice; expect lower encode wall-time and the same metrics. Report the before/after timing.

---

## Self-Review Notes

- **Spec coverage:** `KeyValueStore`/`DiskVectorCache`/`CachedTextEmbedder` (Task 1–2); sha256 namespaced key + dtype in qwen3 namespace (Task 1 `make_key`, Task 3 wiring); partial-hit batching + dedup + order + disabled kill-switch (Task 2); new Volume v2, shared mount on both leaf encoders, `@modal.exit()` commit (Task 3); atomic writes + miss-safe reads (Task 1); tests with fake encoder + temp dir (Task 1–2) and static mount test (Task 3). Within-run cross-container limitation is accepted by design — no `reload()`, nothing to implement.
- **No double-caching:** wrapping is only at the leaf GPU encoders (`Qwen3Encoder`, `MultimodalTextEncoder`); the delegating retrieval-service `embed_batch` is untouched.
- **Type consistency:** `make_key(namespace, text)`, `DiskVectorCache.get/set`, `CachedTextEmbedder(inner, store, namespace, enabled)`, and `EMBEDDING_CACHE_DIR` are used identically across all tasks.
