from __future__ import annotations

import asyncio
import threading

import pytest


def test_file_cache_round_trips_sync_values(tmp_path):
    from mcrs.litellm_cache import FileCache

    cache = FileCache(tmp_path)
    value = {"timestamp": 1.0, "response": {"choices": [{"message": {"content": "ok"}}]}}

    cache.set_cache("abcdef123456", value)

    assert cache.get_cache("abcdef123456") == value


def test_file_cache_round_trips_async_values(tmp_path):
    from mcrs.litellm_cache import FileCache

    async def exercise_cache():
        cache = FileCache(tmp_path)
        value = {"timestamp": 2.0, "response": {"data": [{"embedding": [0.1, 0.2]}]}}

        await cache.async_set_cache("feedface1234", value)

        assert await cache.async_get_cache("feedface1234") == value

    asyncio.run(exercise_cache())


def test_file_cache_miss_and_corrupt_file_return_none(tmp_path):
    from mcrs.litellm_cache import FileCache

    cache = FileCache(tmp_path)

    assert cache.get_cache("001122334455") is None

    path = cache._path("001122334455")
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json", encoding="utf-8")

    assert cache.get_cache("001122334455") is None


def test_file_cache_uses_hash_prefixed_layout_and_rejects_path_separators(tmp_path):
    from mcrs.litellm_cache import FileCache

    cache = FileCache(tmp_path)

    assert cache._path("abcdef123456") == tmp_path / "ab" / "cd" / "abcdef123456.json"
    with pytest.raises(ValueError, match="path separator"):
        cache._path("../escape")
    with pytest.raises(ValueError, match="path separator"):
        cache._path("ab/cd")


def test_file_cache_shards_on_hash_not_namespace_prefix(tmp_path):
    from mcrs.litellm_cache import FileCache

    cache = FileCache(tmp_path)

    # litellm keys are "<namespace>:<sha256hex>". Sharding must use the hash, not
    # the constant namespace prefix — otherwise every entry collapses into one
    # directory (e.g. all "music-crs:*" keys land in mu/si/).
    k1 = "music-crs:ab12" + "0" * 60
    k2 = "music-crs:cd34" + "0" * 60
    assert cache._path(k1).parent == tmp_path / "ab" / "12"
    assert cache._path(k2).parent == tmp_path / "cd" / "34"
    assert cache._path(k1).parent != cache._path(k2).parent
    # filename keeps the full namespaced key so different namespaces don't collide
    assert cache._path(k1).name == f"{k1}.json"


def test_file_cache_migrate_legacy_layout_moves_entries(tmp_path):
    from mcrs.litellm_cache import FileCache

    cache = FileCache(tmp_path)
    key = "music-crs:ab12" + "0" * 60

    # An entry written by the OLD layout (sharded on the namespaced key).
    legacy = tmp_path / key[:2] / key[2:4] / f"{key}.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"v": 1}', encoding="utf-8")

    # get_cache reads only the hash-sharded path, so it misses pre-migration.
    assert cache.get_cache(key) is None

    moved = cache.migrate_legacy_layout()
    assert moved == 1
    assert cache.get_cache(key) == {"v": 1}  # now at the hash-sharded path
    assert not legacy.exists()  # moved, not copied
    assert cache.migrate_legacy_layout() == 0  # idempotent


def test_file_cache_async_set_cache_pipeline_writes_all_entries(tmp_path):
    from mcrs.litellm_cache import FileCache

    async def exercise_cache():
        cache = FileCache(tmp_path)

        await cache.async_set_cache_pipeline(
            [
                ("aaaabbbb", {"timestamp": 1, "response": "first"}),
                ("ccccdddd", {"timestamp": 2, "response": "second"}),
            ]
        )

        assert cache.get_cache("aaaabbbb") == {"timestamp": 1, "response": "first"}
        assert cache.get_cache("ccccdddd") == {"timestamp": 2, "response": "second"}

    asyncio.run(exercise_cache())


def test_file_cache_write_errors_degrade_to_skipped_write(tmp_path):
    from mcrs.litellm_cache import FileCache

    cache = FileCache(tmp_path)

    cache.set_cache("aaaabbbb", {"not-json": object()})

    assert cache.get_cache("aaaabbbb") is None


def test_file_cache_concurrent_same_key_writes_leave_readable_json(tmp_path):
    from mcrs.litellm_cache import FileCache

    cache = FileCache(tmp_path)

    def write_value(index: int) -> None:
        cache.set_cache("1234567890abcdef", {"timestamp": index, "response": {"index": index}})

    threads = [threading.Thread(target=write_value, args=(index,)) for index in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    stored = cache.get_cache("1234567890abcdef")
    assert isinstance(stored, dict)
    assert isinstance(stored["response"]["index"], int)


def test_setup_litellm_cache_file_backend_installs_file_storage(tmp_path, monkeypatch):
    from mcrs.litellm_cache import FileCache, setup_litellm_cache

    import litellm

    monkeypatch.setattr(litellm, "cache", None, raising=False)

    configured = setup_litellm_cache(backend="file", cache_dir=str(tmp_path))

    assert configured is True
    assert litellm.cache.namespace == "music-crs"
    assert "aembedding" in litellm.cache.supported_call_types
    assert isinstance(litellm.cache.cache, FileCache)
    assert litellm.cache.cache.directory == tmp_path


def test_setup_litellm_cache_defaults_to_file_when_cache_dir_is_set(tmp_path, monkeypatch):
    from mcrs.litellm_cache import FileCache, setup_litellm_cache

    import litellm

    monkeypatch.setattr(litellm, "cache", None, raising=False)
    monkeypatch.setenv("MCRS_LITELLM_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("MCRS_LITELLM_CACHE_BACKEND", raising=False)

    configured = setup_litellm_cache()

    assert configured is True
    assert isinstance(litellm.cache.cache, FileCache)


def test_setup_litellm_cache_wrapper_reads_values_from_file_backend(tmp_path, monkeypatch):
    from mcrs.litellm_cache import setup_litellm_cache

    import litellm

    monkeypatch.setattr(litellm, "cache", None, raising=False)

    setup_litellm_cache(backend="file", cache_dir=tmp_path)
    litellm.cache.add_cache({"ok": True}, cache_key="abc123def456")

    assert litellm.cache.get_cache(cache_key="abc123def456") == {"ok": True}


def test_setup_litellm_cache_none_backend_disables_cache(monkeypatch):
    from mcrs.litellm_cache import setup_litellm_cache

    import litellm

    monkeypatch.setattr(litellm, "cache", object(), raising=False)

    configured = setup_litellm_cache(backend="none", cache_dir="/unused")

    assert configured is False
    assert litellm.cache is None
