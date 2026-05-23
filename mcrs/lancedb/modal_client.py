"""Private Modal SDK client for the class-backed retrieval service."""

from __future__ import annotations

from typing import Any

import modal


class LanceDbModalClient:
    """Small wrapper around Modal class lookup so callers do not handle HTTP/auth."""

    def __init__(self, app_name: str, class_name: str = "ModalRetrievalService") -> None:
        self.app_name = app_name
        self.class_name = class_name
        service_cls = modal.Cls.from_name(app_name, class_name)
        self._service = service_cls()

    def query(
        self,
        query: str,
        topk: int,
        retrieval_config: dict[str, Any] | None = None,
    ) -> list[str]:
        return self._service.retrieve.remote(
            query=query,
            topk=topk,
            retrieval_config=retrieval_config,
        )

    def query_batch(
        self,
        queries: list[str],
        topk: int,
        retrieval_config: dict[str, Any] | None = None,
    ) -> list[list[str]]:
        return self._service.retrieve_batch.remote(
            queries=queries,
            topk=topk,
            retrieval_config=retrieval_config,
        )

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._service.embed_batch.remote(texts=texts)
