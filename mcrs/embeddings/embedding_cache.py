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
