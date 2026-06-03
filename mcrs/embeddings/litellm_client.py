from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _batched(items: list[str], batch_size: int):
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def _embedding_from_item(item: Any) -> list[float]:
    if isinstance(item, dict):
        value = item["embedding"]
    else:
        value = item.embedding
    return [float(number) for number in value]


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

    def __post_init__(self) -> None:
        self.batch_size = int(self.batch_size)
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not self.model_name.strip():
            raise ValueError("model_name must be a non-empty string")

    def build_request_kwargs(self, texts: list[str]) -> dict[str, Any]:
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
