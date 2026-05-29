"""Client for the Modal-deployed `MultimodalTextEncoder` class.

Hosts SigLIP-2 (text -> image-siglip2 space, 768d) and LAION-CLAP music
(text -> audio-laion_clap space, 512d) in one warm container. The
underlying class is defined in `modal/app.py`; deploy with
`modal deploy modal/app.py` before use.

Each modality is exposed as a separate `EmbeddingClient` instance via
the `method` field, so the v0+ compiler can register them under distinct
encoder_ids (`siglip2_text`, `clap_text`) while still hitting one
warm container for both.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModalMultimodalTextEmbeddingClient:
    """Looks up the deployed Modal class and forwards `embed_batch` calls
    to the named method (`embed_siglip_text` or `embed_clap_text`)."""

    app_name: str = "music-crs"
    cls_name: str = "MultimodalTextEncoder"
    method: str = "embed_siglip_text"  # or "embed_clap_text"

    def __post_init__(self) -> None:
        import modal

        if self.method not in {"embed_siglip_text", "embed_clap_text"}:
            raise ValueError(
                f"method must be 'embed_siglip_text' or 'embed_clap_text', "
                f"got {self.method!r}"
            )
        self._cls = modal.Cls.from_name(self.app_name, self.cls_name)
        self._instance = self._cls()
        self._method = getattr(self._instance, self.method)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._method.remote(texts)

    async def aembed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._method.remote.aio(texts)
