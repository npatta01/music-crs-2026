"""Private Modal SDK client for deployed LanceDB query functions."""

from __future__ import annotations

from typing import Any

import modal


class LanceDbModalClient:
    """Small wrapper around Modal function lookup so callers do not handle HTTP/auth."""

    def __init__(self, app_name: str, function_name: str = "query_lancedb") -> None:
        self.app_name = app_name
        self.function_name = function_name
        self._function = modal.Function.from_name(app_name, function_name)

    def query(
        self,
        query: str,
        topk: int,
        retrieval_config: dict[str, Any],
    ) -> list[str]:
        return self._function.remote(
            query=query,
            topk=topk,
            retrieval_config=retrieval_config,
        )
