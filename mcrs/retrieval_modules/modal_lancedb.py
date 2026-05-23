from __future__ import annotations

from typing import Any

from mcrs.lancedb.modal_client import LanceDbModalClient


class MODAL_LANCEDB_MODEL:
    """CRS retrieval module that delegates retrieval to a private Modal class."""

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
        config = dict(retrieval_config or {})
        app_name = str(config.get("app_name", "music-crs"))
        class_name = str(config.get("class_name", "ModalRetrievalService"))
        self.retrieval_config = {
            key: value
            for key, value in config.items()
            if key not in {"app_name", "class_name"}
        } or None
        self.client = LanceDbModalClient(app_name=app_name, class_name=class_name)

    def text_to_item_retrieval(self, query: str, topk: int) -> list[str]:
        return self.client.query(query, topk=topk, retrieval_config=self.retrieval_config)

    def batch_text_to_item_retrieval(self, queries: list[str], topk: int) -> list[list[str]]:
        return self.client.query_batch(
            queries,
            topk=topk,
            retrieval_config=self.retrieval_config,
        )
