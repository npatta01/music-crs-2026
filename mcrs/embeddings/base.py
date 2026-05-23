from __future__ import annotations

from typing import Protocol


class EmbeddingClient(Protocol):
    """Provider-neutral synchronous embedding interface."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
