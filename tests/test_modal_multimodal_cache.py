"""Client-side embedding cache for the modal_multimodal encoder.

The `MultimodalTextEncoder` (CLAP / SigLIP text side) is reached over a Modal
RPC. Unlike the litellm Qwen path — which has a process-global litellm cache
consulted *before* the network call — the raw Modal client embeds one query
text per `.remote()` call with no client-side dedup, so repeated query texts
each pay a full RPC against a cold, 2-container GPU pool.

`cache_wrap` fixes that asymmetry: it wraps the raw client in a
`CachedTextEmbedder` backed by a `DiskVectorCache`, so a query text already
seen in this process (or already committed to the shared volume by the
server) never leaves the process.
"""

from __future__ import annotations

import pytest

from mcrs.embeddings.modal_multimodal_client import (
    EMBEDDING_CACHE_NAMESPACES,
    cache_namespace_for_method,
    cache_wrap,
)


class _CountingInner:
    """Fake encoder that records every text it is asked to embed."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        # Deterministic per-text vector so we can assert ordering.
        return [[float(len(t)), 1.0] for t in texts]

    @property
    def encoded(self) -> list[str]:
        return [t for batch in self.calls for t in batch]


def test_cache_namespace_matches_server_strings():
    # These must stay byte-identical to the namespaces the server-side
    # MultimodalTextEncoder uses, or the shared volume cache won't collide.
    assert cache_namespace_for_method("embed_clap_text") == (
        "clap:music_audioset_epoch_15_esc_90.14"
    )
    assert cache_namespace_for_method("embed_siglip_text") == (
        "siglip2:google/siglip2-base-patch16-224"
    )
    assert set(EMBEDDING_CACHE_NAMESPACES) == {
        "embed_clap_text",
        "embed_siglip_text",
    }


def test_cache_namespace_rejects_unknown_method():
    with pytest.raises(ValueError, match="cache namespace"):
        cache_namespace_for_method("embed_audio_text")


def test_cache_wrap_serves_repeats_without_recalling_inner(tmp_path):
    inner = _CountingInner()
    enc = cache_wrap(
        inner, "embed_clap_text", cache_dir=str(tmp_path), enabled=True
    )

    first = enc.embed_batch(["sunny day", "sad song", "sunny day"])

    # Inner only sees each unique text once; the duplicate is deduped.
    assert inner.encoded == ["sunny day", "sad song"]
    # Result is reassembled in input order, duplicate fanned back out.
    assert first[0] == first[2] == [float(len("sunny day")), 1.0]
    assert first[1] == [float(len("sad song")), 1.0]

    # A second call for an already-seen text makes no further inner calls.
    enc.embed_batch(["sunny day"])
    assert inner.encoded == ["sunny day", "sad song"]


def test_cache_wrap_persists_across_instances_via_disk(tmp_path):
    first_inner = _CountingInner()
    cache_wrap(
        first_inner, "embed_clap_text", cache_dir=str(tmp_path), enabled=True
    ).embed_batch(["warm pads"])
    assert first_inner.encoded == ["warm pads"]

    # A fresh wrapper over the same dir reads the committed vector — no RPC.
    second_inner = _CountingInner()
    enc = cache_wrap(
        second_inner, "embed_clap_text", cache_dir=str(tmp_path), enabled=True
    )
    out = enc.embed_batch(["warm pads"])
    assert second_inner.encoded == []
    assert out == [[float(len("warm pads")), 1.0]]


def test_cache_wrap_disabled_returns_inner_unchanged(tmp_path):
    inner = _CountingInner()
    enc = cache_wrap(
        inner, "embed_clap_text", cache_dir=str(tmp_path), enabled=False
    )
    assert enc is inner


def test_cache_wrap_enabled_defaults_to_env(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBEDDING_CACHE_ENABLED", "0")
    inner = _CountingInner()
    enc = cache_wrap(inner, "embed_clap_text", cache_dir=str(tmp_path))
    assert enc is inner

    monkeypatch.setenv("EMBEDDING_CACHE_ENABLED", "1")
    enc = cache_wrap(inner, "embed_clap_text", cache_dir=str(tmp_path))
    assert enc is not inner


def test_cache_wrap_dir_resolves_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MCRS_EMBEDDING_CACHE_DIR", str(tmp_path))
    inner = _CountingInner()
    enc = cache_wrap(inner, "embed_clap_text", enabled=True)
    enc.embed_batch(["env dir text"])
    # The vector landed under the env-provided directory.
    assert any(tmp_path.rglob("*.json"))
