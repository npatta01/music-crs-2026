"""Client for the Modal-deployed `Qwen3Encoder` class.

Calls the GPU-backed Qwen3-Embedding-0.6B service defined in
`modal/app.py` instead of running the encoder on CPU in-process. Used
by the v0+ compiler when `encoder.backend: "modal"` is set; reduces
per-turn encode latency from ~1-2 s (CPU) to ~50 ms (T4).

Requires the Modal app to be deployed beforehand:
    modal deploy modal/app.py

The deployed app must be named `app_name` and contain a class
`cls_name` (defaults match `modal/app.py`). Authentication uses the
local Modal credentials (`modal token new` once per machine).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModalQwen3EmbeddingClient:
    """Looks up a deployed Modal class and forwards `embed_batch` calls."""

    app_name: str = "music-crs"
    cls_name: str = "Qwen3Encoder"

    def __post_init__(self) -> None:
        import modal

        # `Cls.from_name` resolves a deployed class by app + class name. The
        # lookup itself doesn't spin a container — that happens on the first
        # method call.
        self._cls = modal.Cls.from_name(self.app_name, self.cls_name)
        # `self._cls()` returns a parameterless instance handle; subsequent
        # `.embed_batch.remote(...)` / `.remote.aio(...)` calls dispatch to a
        # warm container (or trigger a cold start).
        self._instance = self._cls()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._instance.embed_batch.remote(texts)

    async def aembed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._instance.embed_batch.remote.aio(texts)
