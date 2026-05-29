"""LAION-CLAP text-side encoder for the music checkpoint.

Encodes text into the 512d shared space used by the catalog's
`audio-laion_clap` column. The catalog was built with:

    laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-base", tmodel="roberta")
    model.load_ckpt("music_audioset_epoch_15_esc_90.14.pt")

and `model.get_audio_embedding_from_filelist(use_tensor=True)`, output
squeezed and saved as raw .npy with NO explicit L2 normalization
(see talkpl-ai/talkplay-environment/talkenv/extractor/audio/clap.py).

This client mirrors that convention via `model.get_text_embedding([...])`,
no L2 normalization by default. LanceDB's `distance_type: "cosine"`
handles per-query normalization.

The music checkpoint is the music-specialized LAION-CLAP variant
(NOT the generic CLAP). Hosted at https://huggingface.co/lukewys/laion_clap
filename `music_audioset_epoch_15_esc_90.14.pt`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ClapTextEmbeddingClient:
    ckpt_path: str  # local path to music_audioset_epoch_15_esc_90.14.pt
    device: str = "cuda"
    batch_size: int = 32
    l2_normalize: bool = False  # flip after verification

    _model: object = field(default=None, init=False, repr=False)

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import laion_clap
        import torch

        model = laion_clap.CLAP_Module(
            enable_fusion=False,
            amodel="HTSAT-base",
            tmodel="roberta",
            device=self.device,
        )
        # CLAP_Module.load_ckpt() accepts either a HF-style id, a URL, or a
        # local path. Use a local path under the HF cache volume to avoid
        # re-downloading on every cold start.
        ckpt = Path(self.ckpt_path)
        if not ckpt.exists():
            raise FileNotFoundError(
                f"CLAP music checkpoint not found at {ckpt}. "
                f"Download from https://huggingface.co/lukewys/laion_clap "
                f"(filename music_audioset_epoch_15_esc_90.14.pt)."
            )
        model.load_ckpt(str(ckpt))
        model.eval()
        self._model = model

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        import torch

        self._ensure_loaded()

        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            with torch.no_grad():
                features = self._model.get_text_embedding(chunk, use_tensor=True)
            if self.l2_normalize:
                features = features / features.norm(p=2, dim=-1, keepdim=True).clamp(min=1e-12)
            out.extend(features.detach().to(torch.float32).cpu().tolist())
        return out
