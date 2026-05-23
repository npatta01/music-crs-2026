from __future__ import annotations

from dataclasses import dataclass

from mcrs.embeddings.base import EmbeddingClient


@dataclass
class RetrievalService:
    """Small standalone service object for retrieval and optional embeddings."""

    retriever: object
    embedding_client: EmbeddingClient | None = None

    def retrieve(self, query: str, topk: int) -> list[str]:
        return self.retriever.retrieve(query, topk=topk)

    def retrieve_batch(self, queries: list[str], topk: int) -> list[list[str]]:
        return self.retriever.retrieve_batch(queries, topk=topk)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self.embedding_client is None:
            raise RuntimeError("No embedding client configured")
        return self.embedding_client.embed_batch(texts)
