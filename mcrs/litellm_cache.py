from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from litellm.caching.base_cache import BaseCache
from litellm.caching.caching import Cache


DEFAULT_SUPPORTED_CALL_TYPES = ["completion", "acompletion", "embedding", "aembedding"]
DEFAULT_NAMESPACE = "music-crs"


class FileCache(BaseCache):
    """LiteLLM BaseCache backend storing one JSON file per cache key."""

    def __init__(self, directory: str | os.PathLike[str]):
        super().__init__()
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _shard(key: str) -> tuple[str, str]:
        # litellm keys look like "<namespace>:<sha256hex>". Shard on the hash, not
        # the raw key — the namespace prefix is constant ("music-crs:"), so sharding
        # on the key collapses every entry into a single directory (mu/si/).
        digest = key.rsplit(":", 1)[-1]
        return digest[:2], digest[2:4]

    def _path(self, key: str) -> Path:
        key = self._validate_key(key)
        shard_a, shard_b = self._shard(key)
        return self.directory / shard_a / shard_b / f"{key}.json"

    def migrate_legacy_layout(self) -> int:
        """Relocate entries written under the pre-fix layout (sharded on the
        namespaced key, collapsed into one directory) into the hash-sharded
        layout. One-time, idempotent; returns the number of files moved."""
        moved = 0
        for path in self.directory.rglob("*.json"):
            target = self._path(path.stem)  # filename stem is the cache key
            if path == target:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(path, target)
            moved += 1
        return moved

    @staticmethod
    def _validate_key(key: str) -> str:
        if not isinstance(key, str) or not key:
            raise ValueError("cache key must be a non-empty string")
        if "/" in key or "\\" in key:
            raise ValueError("cache key must not contain a path separator")
        if "\x00" in key:
            raise ValueError("cache key must not contain a null byte")
        return key

    def get_cache(self, key, **kwargs):
        try:
            return json.loads(self._path(key).read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return None

    def set_cache(self, key, value, **kwargs):
        temp_path: str | None = None
        try:
            path = self._path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.stem}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = handle.name
                json.dump(value, handle, separators=(",", ":"))
                handle.flush()
            os.replace(temp_path, path)
        except (OSError, TypeError, ValueError):
            return None
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    async def async_get_cache(self, key, **kwargs):
        return await asyncio.to_thread(self.get_cache, key, **kwargs)

    async def async_set_cache(self, key, value, **kwargs):
        return await asyncio.to_thread(self.set_cache, key, value, **kwargs)

    async def async_set_cache_pipeline(self, cache_list, **kwargs):
        for key, value in _iter_cache_items(cache_list):
            await self.async_set_cache(key, value, **kwargs)

    async def batch_cache_write(self, key, value, **kwargs):
        await self.async_set_cache(key, value, **kwargs)

    def get_ttl(self, **kwargs) -> None:
        return None

    async def disconnect(self):
        return None

    async def test_connection(self) -> dict:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            return {"status": "success", "message": f"File cache ready at {self.directory}"}
        except OSError as exc:
            return {"status": "failed", "message": "File cache directory unavailable", "error": str(exc)}


def setup_litellm_cache(
    *,
    backend: str | None = None,
    cache_dir: str | os.PathLike[str] | None = None,
    supported_call_types: list[str] | None = None,
    namespace: str = DEFAULT_NAMESPACE,
) -> bool:
    """Configure the process-global LiteLLM cache.

    Backend resolution:
    1. explicit ``backend`` argument
    2. ``MCRS_LITELLM_CACHE_BACKEND``
    3. ``file`` when a cache directory is set
    4. ``none``
    """

    import litellm

    cache_dir_value = str(cache_dir or os.environ.get("MCRS_LITELLM_CACHE_DIR") or "")
    backend_value = (backend or os.environ.get("MCRS_LITELLM_CACHE_BACKEND") or "").strip().lower()
    if not backend_value:
        backend_value = "file" if cache_dir_value else "none"

    if backend_value in {"", "none", "off", "disabled", "false", "0"}:
        litellm.cache = None
        return False

    call_types = list(supported_call_types or DEFAULT_SUPPORTED_CALL_TYPES)

    if backend_value == "file":
        if not cache_dir_value:
            raise ValueError("MCRS_LITELLM_CACHE_DIR is required for LiteLLM file cache")
        cache = Cache(namespace=namespace, supported_call_types=call_types)
        cache.cache = FileCache(cache_dir_value)
        litellm.cache = cache
        return True

    if backend_value == "disk":
        if not cache_dir_value:
            raise ValueError("MCRS_LITELLM_CACHE_DIR is required for LiteLLM disk cache")
        litellm.cache = Cache(
            type="disk",
            supported_call_types=call_types,
            namespace=namespace,
            disk_cache_dir=cache_dir_value,
        )
        return True

    raise ValueError(f"Unsupported LiteLLM cache backend: {backend_value}")


def _iter_cache_items(cache_list: Iterable[Any]):
    for item in cache_list:
        if isinstance(item, dict):
            yield item["key"], item["value"]
        else:
            key, value = item
            yield key, value
