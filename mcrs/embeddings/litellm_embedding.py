"""LiteLLM-backed embedding client.

Implements the `EmbeddingClient` Protocol via `litellm.embedding` /
`litellm.aembedding`. The intended use is to route Qwen3-Embedding-0.6B
calls through a LiteLLM proxy which in turn hits HuggingFace Inference
Providers — so the v0+ compiler doesn't have to run the 0.6B model on
CPU at request time.

Caveat (verify before flipping default): a remote `feature-extraction`
endpoint may apply different pooling than what produced the catalog
vectors (which were built with raw text, no instruct prefix,
last-token pooling, un-normalized float32). Run
`scripts/verify_qwen3_catalog_convention.py --backend litellm` and
check cosine ≥ 0.99 vs the precomputed
`metadata_qwen3_embedding_0_6b` column before using this in
production.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LiteLLMEmbeddingClient:
    """Sync + async embedding client that calls a LiteLLM endpoint."""

    model_name: str
    api_base: str | None = None
    api_key: str | None = None
    timeout_s: int = 60

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import litellm

        if not texts:
            return []
        kwargs = self._kwargs(texts)
        response = litellm.embedding(**kwargs)
        return [item["embedding"] for item in response["data"]]

    async def aembed_batch(self, texts: list[str]) -> list[list[float]]:
        import litellm

        if not texts:
            return []
        kwargs = self._kwargs(texts)
        response = await litellm.aembedding(**kwargs)
        return [item["embedding"] for item in response["data"]]

    def _kwargs(self, texts: list[str]) -> dict:
        kwargs: dict = {
            "model": self.model_name,
            "input": texts,
            "timeout": self.timeout_s,
        }
        # api_base: prefer explicit, else LITELLM_PROXY_BASE. When neither is
        # set, litellm dispatches directly to the provider in `model_name`
        # (e.g. `huggingface/...` hits HF Inference Providers using the
        # HF_TOKEN env that litellm picks up automatically).
        api_base = self.api_base or os.environ.get("LITELLM_PROXY_BASE")
        if api_base:
            kwargs["api_base"] = api_base
        # api_key: only forward when explicitly set. Direct provider calls
        # rely on litellm reading provider-specific env vars (HF_TOKEN,
        # OPENAI_API_KEY, etc.); proxy calls accept any non-empty key.
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return kwargs
