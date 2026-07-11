from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from mcrs.embeddings.embedding_cache import CachedTextEmbedder, DiskVectorCache

DEFAULT_EMBEDDING_CACHE_DIR = "./cache/embeddings"


def _batched(items: list[str], batch_size: int):
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def _embedding_from_item(item: Any) -> list[float]:
    if isinstance(item, dict):
        value = item["embedding"]
    else:
        value = item.embedding
    return [float(number) for number in value]


def _cache_enabled_default() -> bool:
    return os.environ.get("EMBEDDING_CACHE_ENABLED", "1") != "0"


def _resolve_cache_dir(cache_dir: str | None) -> str:
    return cache_dir or os.environ.get("MCRS_EMBEDDING_CACHE_DIR") or DEFAULT_EMBEDDING_CACHE_DIR


def cache_namespace_for_client(client: "LiteLLMEmbeddingClient") -> str:
    """Cache key for this client's model identity.

    Deliberately excludes `api_base`: a self-hosted vLLM endpoint (Modal or
    local) and any other backend serving the same checkpoint produce the same
    vectors, so the cache should be portable across serving backends — this
    mirrors the b1 bi-encoder's local/Modal-interchangeable design
    (docs/architectures/biencoder.md, scripts/rerank/b1_live.py). It also lets
    a cache lookup happen without ever resolving a live endpoint URL.
    """
    payload = {
        "backend": "litellm",
        "model": client.model_name,
        "dimensions": client.dimensions,
        "encoding_format": client.encoding_format,
        "query_instruct": client.query_instruct,
        "extra_params": client.extra_params,
    }
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"litellm:{rendered}"


def _resolve_vllm_endpoint_url(model_key: str) -> str:
    """Resolve a logical Modal vLLM endpoint key (e.g. "qwen3-embedding-8b")
    to a live serving URL.

    Loaded by file path rather than `import modal.vllm_serve`: the repo's
    top-level `modal/` directory shadows the installed `modal` SDK package.
    """
    import importlib.util
    from pathlib import Path

    vs_path = Path(__file__).resolve().parents[2] / "modal" / "vllm_serve.py"
    spec = importlib.util.spec_from_file_location("mcrs_vllm_serve_lazy", vs_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.endpoint_url(model_key)


def cache_wrap(
    inner: "LiteLLMEmbeddingClient",
    *,
    cache_dir: str | None = None,
    enabled: bool | None = None,
):
    if enabled is None:
        enabled = _cache_enabled_default()
    if not enabled:
        return inner
    store = DiskVectorCache(_resolve_cache_dir(cache_dir))
    return CachedTextEmbedder(inner, store, cache_namespace_for_client(inner), enabled=True)


@dataclass
class LiteLLMEmbeddingClient:
    """Standalone LiteLLM embedding client."""

    model_name: str
    api_base: str | None = None
    api_key: str | None = None
    batch_size: int = 128
    dimensions: int | None = None
    # encoding_format: required by some providers (e.g. DeepInfra returns 422 without it).
    # Set to "float" when using DeepInfra or any provider that requires explicit format.
    encoding_format: str | None = None
    cache: dict[str, Any] | None = None
    query_instruct: str = ""
    extra_params: dict[str, Any] = field(default_factory=dict)
    # Logical Modal vLLM endpoint key (e.g. "qwen3-embedding-8b"). When set
    # and `api_base` is not, the live serving URL is resolved lazily on the
    # first actual live call rather than eagerly at construction time — a
    # cache hit (see cache_namespace_for_client) never needs Modal
    # credentials at all.
    vllm_endpoint: str | None = None

    def __post_init__(self) -> None:
        self.batch_size = int(self.batch_size)
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not self.model_name.strip():
            raise ValueError("model_name must be a non-empty string")

    def _resolve_api_base(self) -> None:
        if self.api_base is not None or not self.vllm_endpoint:
            return
        self.api_base = _resolve_vllm_endpoint_url(self.vllm_endpoint)

    def build_request_kwargs(self, texts: list[str]) -> dict[str, Any]:
        self._resolve_api_base()
        rendered_texts = [
            f"{self.query_instruct}{text}" if self.query_instruct else text
            for text in texts
        ]
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "input": rendered_texts,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.dimensions is not None:
            kwargs["dimensions"] = int(self.dimensions)
        if self.encoding_format is not None:
            kwargs["encoding_format"] = self.encoding_format
        if self.cache is not None:
            kwargs["cache"] = self.cache
        kwargs.update(self.extra_params)
        return kwargs

    def _kwargs(self, texts: list[str] | str) -> dict[str, Any]:
        input_texts = [texts] if isinstance(texts, str) else texts
        return self.build_request_kwargs(input_texts)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        import litellm

        vectors: list[list[float]] = []
        for batch in _batched(list(texts), self.batch_size):
            response = litellm.embedding(**self._kwargs(batch))
            vectors.extend(_embedding_from_item(item) for item in response.data)
        return vectors

    def embed_one(self, text: str) -> list[float]:
        import litellm

        response = litellm.embedding(**self.build_request_kwargs([text]))
        return _embedding_from_item(response.data[0])
