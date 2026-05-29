"""SigLIP-2 text-side encoder.

Encodes text into the 768d shared space used by the catalog's
`image-siglip2` column. The catalog was built with
`google/siglip2-base-patch16-224` via `model.get_image_features(...)`,
output squeezed to [768] and saved as raw float32 .npy with NO L2
normalization (see talkpl-ai/talkplay-environment/talkenv/extractor/
image/siglip2.py).

This client mirrors that convention: `model.get_text_features(...)`,
no L2 normalization by default. LanceDB's `distance_type: "cosine"`
handles per-query normalization.

`l2_normalize=True` is available as an escape hatch but should not be
needed; flip it only if the catalog turns out to have been re-normalized
during the LanceDB indexing step (verify with
scripts/verify_textside_catalog_convention.py first).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SigLIP2TextEmbeddingClient:
    model_name: str = "google/siglip2-base-patch16-224"
    device: str = "cuda"
    # float32 matches the catalog extractor (no torch_dtype kwarg in talkpl-ai
    # source) — keeping precision identical avoids spurious drift in the
    # text↔image cosine alignment check.
    torch_dtype_name: str = "float32"
    batch_size: int = 32
    l2_normalize: bool = False  # match catalog (raw, un-normalized)

    _model: object = field(default=None, init=False, repr=False)
    _processor: object = field(default=None, init=False, repr=False)
    _torch_dtype: object = field(default=None, init=False, repr=False)

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModel, AutoProcessor

        self._torch_dtype = getattr(torch, self.torch_dtype_name)
        self._processor = AutoProcessor.from_pretrained(self.model_name, use_fast=True)
        if self.torch_dtype_name == "float32":
            model = AutoModel.from_pretrained(self.model_name)
        else:
            model = AutoModel.from_pretrained(self.model_name, torch_dtype=self._torch_dtype)
        model.to(self.device).eval()
        self._model = model

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        import torch

        self._ensure_loaded()

        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            inputs = self._processor(
                text=chunk,
                return_tensors="pt",
                padding="max_length",
                truncation=True,
            ).to(self.device)
            with torch.no_grad():
                features = self._model.get_text_features(**inputs)
            # transformers 4.51+ Siglip2Model.get_text_features may return
            # BaseModelOutputWithPooling rather than a Tensor. Unwrap to the
            # projected/pooled embedding.
            if not torch.is_tensor(features):
                if hasattr(features, "pooler_output") and features.pooler_output is not None:
                    features = features.pooler_output
                elif hasattr(features, "text_embeds"):
                    features = features.text_embeds
                else:
                    features = features.last_hidden_state[:, 0]
            if self.l2_normalize:
                features = features / features.norm(p=2, dim=-1, keepdim=True).clamp(min=1e-12)
            out.extend(features.detach().to(torch.float32).cpu().tolist())
        return out
