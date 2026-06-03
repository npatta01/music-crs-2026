"""Client for the Modal-deployed `MultimodalTextEncoder` class.

Hosts SigLIP-2 (text -> image-siglip2 space, 768d) and LAION-CLAP music
(text -> audio-laion_clap space, 512d) in one warm container. The
underlying class is defined in `modal/app.py`; deploy with
`modal deploy modal/app.py` before use.

Each modality is exposed as a separate `EmbeddingClient` instance via
the `method` field, so the v0+ compiler can register them under distinct
encoder_ids (`siglip2_text`, `clap_text`) while still hitting one
warm container for both.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from mcrs.embeddings.embedding_cache import CachedTextEmbedder, DiskVectorCache

# Cache namespaces keyed by the Modal method. These pin model identity into the
# cache key and MUST stay byte-identical to the namespaces the server-side
# `MultimodalTextEncoder` uses in `modal/app.py` — they back the same
# `DiskVectorCache` on the shared volume, so a mismatch would silently split
# the cache instead of colliding. The server imports these constants from here.
EMBEDDING_CACHE_NAMESPACES = {
    "embed_siglip_text": "siglip2:google/siglip2-base-patch16-224",
    "embed_clap_text": "clap:music_audioset_epoch_15_esc_90.14",
}

# Fallback used when neither the caller nor MCRS_EMBEDDING_CACHE_DIR pins a dir
# (e.g. local runs). On Modal the inference container exports
# MCRS_EMBEDDING_CACHE_DIR pointing at the shared cache volume.
DEFAULT_EMBEDDING_CACHE_DIR = "./cache/embeddings"


def cache_namespace_for_method(method: str) -> str:
    """Return the `DiskVectorCache` namespace for a multimodal encoder method."""
    try:
        return EMBEDDING_CACHE_NAMESPACES[method]
    except KeyError as exc:
        raise ValueError(
            f"no cache namespace for method {method!r}; expected one of "
            f"{sorted(EMBEDDING_CACHE_NAMESPACES)}"
        ) from exc


def _cache_enabled_default() -> bool:
    # Mirror the server's EMBEDDING_CACHE_ENABLED kill switch.
    return os.environ.get("EMBEDDING_CACHE_ENABLED", "1") != "0"


def _resolve_cache_dir(cache_dir: str | None) -> str:
    return cache_dir or os.environ.get("MCRS_EMBEDDING_CACHE_DIR") or DEFAULT_EMBEDDING_CACHE_DIR


def cache_wrap(
    inner,
    method: str,
    *,
    cache_dir: str | None = None,
    enabled: bool | None = None,
):
    """Wrap a raw multimodal embedding client in a client-side vector cache.

    Repeated query texts are served from a `DiskVectorCache` without issuing a
    Modal RPC, mirroring the litellm Qwen path (whose process-global cache is
    consulted before the network call). The cache dir defaults to the shared
    volume via MCRS_EMBEDDING_CACHE_DIR so committed server-side vectors are
    reused too. When disabled, returns `inner` unchanged (pure pass-through).
    """
    if enabled is None:
        enabled = _cache_enabled_default()
    if not enabled:
        return inner
    namespace = cache_namespace_for_method(method)
    store = DiskVectorCache(_resolve_cache_dir(cache_dir))
    return CachedTextEmbedder(inner, store, namespace, enabled=True)


@dataclass
class ModalMultimodalTextEmbeddingClient:
    """Looks up the deployed Modal class and forwards `embed_batch` calls
    to the named method (`embed_siglip_text` or `embed_clap_text`)."""

    app_name: str = "music-crs"
    cls_name: str = "MultimodalTextEncoder"
    method: str = "embed_siglip_text"  # or "embed_clap_text"

    def __post_init__(self) -> None:
        import modal

        if self.method not in {"embed_siglip_text", "embed_clap_text"}:
            raise ValueError(
                f"method must be 'embed_siglip_text' or 'embed_clap_text', "
                f"got {self.method!r}"
            )
        self._cls = modal.Cls.from_name(self.app_name, self.cls_name)
        self._instance = self._cls()
        self._method = getattr(self._instance, self.method)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._method.remote(texts)

    async def aembed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._method.remote.aio(texts)
