"""Dense retrieval using precomputed track embeddings from a HuggingFace dataset."""

import json
import os
import re

import torch
import torch.nn.functional as F
from datasets import concatenate_datasets, load_dataset

from mcrs.retrieval_modules.base import register_retriever
from mcrs.retrieval_modules.bert import DENSE_TRANSFORMER_MODEL, _sanitize_model_name


@register_retriever("precomputed_embedding")
class PRECOMPUTED_EMBEDDING_MODEL(DENSE_TRANSFORMER_MODEL):
    """Dense retriever that loads track embeddings from a precomputed HF dataset column.

    Document embeddings are read directly from
    ``talkpl-ai/TalkPlayData-Challenge-Track-Embeddings`` (or a custom dataset),
    so only the query encoder is run at inference time.  All retrieval logic
    (dot-product scoring, top-k selection) is inherited from
    ``DENSE_TRANSFORMER_MODEL``.
    """

    def __init__(
        self,
        dataset_name: str,
        split_types: list[str],
        corpus_types: list[str],
        cache_dir: str = "./cache",
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        device: str | None = None,
        batch_size: int = 16,
        max_length: int = 512,
        pooling: str = "last_token",
        query_template: str = "{query}",
        document_template: str = "{text}",
        padding_side: str = "left",
        torch_dtype=None,
        formatter=None,
        embeddings_dataset_name: str = "talkpl-ai/TalkPlayData-Challenge-Track-Embeddings",
        embedding_column: str = "metadata-qwen3_embedding_0.6b",
        **kwargs,
    ) -> None:
        self.embeddings_dataset_name = embeddings_dataset_name
        self.embedding_column = embedding_column
        super().__init__(
            dataset_name=dataset_name,
            split_types=split_types,
            corpus_types=corpus_types,
            cache_dir=cache_dir,
            model_name=model_name,
            device=device,
            batch_size=batch_size,
            max_length=max_length,
            pooling=pooling,
            query_template=query_template,
            document_template=document_template,
            padding_side=padding_side,
            torch_dtype=torch_dtype,
            formatter=formatter,
        )

    def _sanitize_column_name(self) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", self.embedding_column)

    def _build_index_dir(self) -> str:
        return os.path.join(
            self.cache_dir,
            "dense_precomputed",
            self._sanitize_column_name(),
            _sanitize_model_name(self.model_name),
        )

    def _load_corpus(self) -> dict:
        # Track metadata text is not needed — embeddings come from the precomputed dataset.
        return {}

    def build_index(self) -> None:
        emb_ds = load_dataset(self.embeddings_dataset_name)
        available_splits = [s for s in self.split_types if s in emb_ds]
        if not available_splits:
            available_splits = list(emb_ds.keys())
        emb_concat = concatenate_datasets([emb_ds[s] for s in available_splits])

        all_track_ids = emb_concat["track_id"]
        all_raw = emb_concat[self.embedding_column]
        # Filter out tracks whose embedding is empty/null (not all columns are fully populated).
        pairs = [(tid, emb) for tid, emb in zip(all_track_ids, all_raw) if emb]
        if not pairs:
            raise ValueError(
                f"No non-empty embeddings found for column '{self.embedding_column}' "
                f"in {self.embeddings_dataset_name}"
            )
        track_ids, raw = zip(*pairs)
        track_ids = list(track_ids)
        target_dtype = self.torch_dtype if self.torch_dtype is not None else torch.float32
        mat = torch.tensor(list(raw), dtype=torch.float32)
        mat = F.normalize(mat, p=2, dim=1).to(target_dtype).contiguous()
        n_skipped = len(all_track_ids) - len(track_ids)
        if n_skipped:
            print(f"Skipped {n_skipped} tracks with empty '{self.embedding_column}' embeddings.")

        os.makedirs(self.index_dir, exist_ok=True)
        torch.save(mat, os.path.join(self.index_dir, "embeddings.pt"))
        with open(os.path.join(self.index_dir, "track_ids.json"), "w", encoding="utf-8") as f:
            json.dump(track_ids, f, indent=2)
        with open(os.path.join(self.index_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "embeddings_dataset_name": self.embeddings_dataset_name,
                    "embedding_column": self.embedding_column,
                    "model_name": self.model_name,
                    "pooling": self.pooling,
                    "query_template": self.query_template,
                    "padding_side": self.padding_side,
                    "max_length": self.max_length,
                    "torch_dtype": self.torch_dtype_name,
                },
                f,
                indent=2,
            )
