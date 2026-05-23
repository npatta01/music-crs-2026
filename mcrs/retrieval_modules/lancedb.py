"""Compatibility wrapper for the standalone LanceDB retriever."""

from __future__ import annotations

from typing import Any

from mcrs.lancedb.retriever import LanceDbRetriever


class LANCEDB_MODEL:
    """CPU-only LanceDB retriever used by the existing CRS loader."""

    def __init__(
        self,
        dataset_name: str,
        split_types: list[str],
        corpus_types: list[str],
        cache_dir: str = "./cache",
        formatter=None,
        retrieval_config: dict[str, Any] | None = None,
    ) -> None:
        del dataset_name, split_types, corpus_types, cache_dir, formatter
        self.retriever = LanceDbRetriever.from_retrieval_config(
            dict(retrieval_config or {}),
        )

    def text_to_item_retrieval(self, query: str, topk: int) -> list[str]:
        return self.retriever.retrieve(query, topk=topk)

    def batch_text_to_item_retrieval(self, queries: list[str], topk: int) -> list[list[str]]:
        return self.retriever.retrieve_batch(queries, topk=topk)
