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
        except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError):
            # Missing file / unreadable / corrupt JSON or UTF-8 -> treat as miss.
            # A bare ValueError (invalid key from _validate_key) is NOT caught here:
            # it is a programming error and must propagate, matching set()'s behavior.
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
            if len(encoded) != len(misses):
                raise ValueError(
                    f"encoder returned {len(encoded)} vectors for {len(misses)} inputs"
                )
            for t, vec in zip(misses, encoded):
                self._store.set(keys[t], vec)
                resolved[t] = vec

        return [resolved[t] for t in texts]
