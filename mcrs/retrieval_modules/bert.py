"""Dense transformer retrieval utilities for music track metadata."""

import hashlib
import json
import os
import re
from typing import Dict, List, Tuple

import torch
import torch.nn.functional as F
from datasets import concatenate_datasets, load_dataset
from transformers import AutoModel, AutoTokenizer

from mcrs.retrieval_modules.base import register_retriever


def _resolve_torch_dtype(torch_dtype):
    if torch_dtype is None:
        return None
    if isinstance(torch_dtype, torch.dtype):
        return torch_dtype
    if isinstance(torch_dtype, str):
        if not hasattr(torch, torch_dtype):
            raise ValueError(f"Unsupported torch dtype: {torch_dtype}")
        return getattr(torch, torch_dtype)
    raise TypeError(f"Unsupported torch dtype value: {torch_dtype!r}")


def _torch_dtype_name(torch_dtype) -> str:
    if torch_dtype is None:
        return "default"
    if isinstance(torch_dtype, str):
        return torch_dtype
    if isinstance(torch_dtype, torch.dtype):
        return str(torch_dtype).replace("torch.", "")
    raise TypeError(f"Unsupported torch dtype value: {torch_dtype!r}")


def _sanitize_model_name(model_name: str) -> str:
    sanitized = model_name.replace("/", "__")
    return re.sub(r"[^A-Za-z0-9._-]+", "-", sanitized)


@register_retriever("dense_transformer")
class DENSE_TRANSFORMER_MODEL:
    """Configurable dense retriever over track metadata."""

    def __init__(
        self,
        dataset_name: str,
        split_types: list[str],
        corpus_types: list[str],
        cache_dir: str = "./cache",
        model_name: str = "bert-base-uncased",
        device: str | None = None,
        batch_size: int = 32,
        max_length: int = 128,
        pooling: str = "mean",
        query_template: str = "{query}",
        document_template: str = "{text}",
        padding_side: str = "right",
        torch_dtype=None,
        formatter=None,
    ) -> None:
        from mcrs.corpus_formatters import load_corpus_formatter

        self.dataset_name = dataset_name
        self.split_types = list(split_types)
        self.corpus_types = list(corpus_types)
        self.cache_dir = cache_dir
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.pooling = pooling
        self.query_template = query_template
        self.document_template = document_template
        self.padding_side = padding_side
        self.torch_dtype = _resolve_torch_dtype(torch_dtype)
        self.torch_dtype_name = _torch_dtype_name(torch_dtype)
        self.formatter = formatter if formatter is not None else load_corpus_formatter("default")
        self.corpus_name = f"{self.formatter.name}_{'_'.join(corpus_types)}"
        self.device = device if device is not None else ("cuda" if torch.cuda.is_available() else "cpu")
        self.index_dir = self._build_index_dir()
        print(f"Dense retriever index dir: {self.index_dir}")

        self.metadata_dict = self._load_corpus()
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            use_fast=True,
            padding_side=self.padding_side,
        )
        if self.tokenizer.pad_token is None:
            if self.tokenizer.eos_token is not None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            elif self.tokenizer.unk_token is not None:
                self.tokenizer.pad_token = self.tokenizer.unk_token

        model_kwargs = {}
        if self.torch_dtype is not None:
            model_kwargs["torch_dtype"] = self.torch_dtype
        self.model = AutoModel.from_pretrained(self.model_name, **model_kwargs)
        self.model.to(self.device)
        self.model.eval()

        if self._has_cached_index():
            print("Loading cached dense index.")
            self.embeddings, self.track_ids = self._load_index()
        else:
            print("Building dense index from track metadata.")
            self.build_index()
            self.embeddings, self.track_ids = self._load_index()

    def _build_index_dir(self) -> str:
        template_hash = hashlib.sha1(
            json.dumps(
                {
                    "query_template": self.query_template,
                    "document_template": self.document_template,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:12]
        index_name = (
            f"{self.corpus_name}_{self.pooling}_{self.padding_side}_"
            f"{self.max_length}_{self.torch_dtype_name}_{template_hash}"
        )
        return os.path.join(
            self.cache_dir,
            "dense",
            _sanitize_model_name(self.model_name),
            index_name,
        )

    def _has_cached_index(self) -> bool:
        return os.path.exists(os.path.join(self.index_dir, "embeddings.pt")) and os.path.exists(
            os.path.join(self.index_dir, "track_ids.json")
        )

    def _load_index(self) -> Tuple[torch.Tensor, List[str]]:
        embeddings = torch.load(os.path.join(self.index_dir, "embeddings.pt"), map_location="cpu")
        with open(os.path.join(self.index_dir, "track_ids.json"), "r", encoding="utf-8") as f:
            track_ids = json.load(f)
        return embeddings, track_ids

    def _load_corpus(self) -> Dict[str, Dict]:
        metadata_dataset = load_dataset(self.dataset_name)
        metadata_concat_dataset = concatenate_datasets(
            [metadata_dataset[split_type] for split_type in self.split_types]
        )
        return {item["track_id"]: item for item in metadata_concat_dataset}

    def _render_document_text(self, metadata: dict) -> str:
        text = self.formatter.format(metadata, self.corpus_types)
        return self.document_template.format(text=text)

    def _render_query_text(self, query: str) -> str:
        return self.query_template.format(query=query)

    def _pool_hidden_states(
        self,
        last_hidden_states: torch.Tensor,
        attention_mask: torch.Tensor,
        pooling: str | None = None,
    ) -> torch.Tensor:
        pooling = pooling or self.pooling
        if pooling == "mean":
            mask = attention_mask.unsqueeze(-1).expand(last_hidden_states.size()).float()
            summed = torch.sum(last_hidden_states * mask, dim=1)
            counts = torch.clamp(mask.sum(dim=1), min=1e-9)
            return summed / counts
        if pooling == "cls":
            return last_hidden_states[:, 0]
        if pooling == "last_token":
            left_padding = bool((attention_mask[:, -1].sum() == attention_mask.shape[0]).item())
            if left_padding:
                return last_hidden_states[:, -1]
            sequence_lengths = attention_mask.sum(dim=1) - 1
            batch_size = last_hidden_states.shape[0]
            return last_hidden_states[
                torch.arange(batch_size, device=last_hidden_states.device),
                sequence_lengths,
            ]
        raise ValueError(f"Unsupported pooling mode: {pooling}")

    def _encode_texts(self, texts: list[str]) -> torch.Tensor:
        with torch.inference_mode():
            batch = self.tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            batch = {key: value.to(self.device) for key, value in batch.items()}
            outputs = self.model(**batch)
            pooled = self._pool_hidden_states(outputs.last_hidden_state, batch["attention_mask"])
            return F.normalize(pooled, p=2, dim=1).detach().cpu()

    def build_index(self) -> None:
        track_ids = list(self.metadata_dict.keys())
        corpus_texts = [self._render_document_text(self.metadata_dict[track_id]) for track_id in track_ids]
        os.makedirs(self.index_dir, exist_ok=True)

        embeddings: list[torch.Tensor] = []
        for start in range(0, len(corpus_texts), self.batch_size):
            batch_texts = corpus_texts[start : start + self.batch_size]
            embeddings.append(self._encode_texts(batch_texts))

        embedding_mat = torch.cat(embeddings, dim=0).contiguous()
        torch.save(embedding_mat, os.path.join(self.index_dir, "embeddings.pt"))
        with open(os.path.join(self.index_dir, "track_ids.json"), "w", encoding="utf-8") as f:
            json.dump(track_ids, f, indent=2)
        with open(os.path.join(self.index_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "model_name": self.model_name,
                    "corpus_types": self.corpus_types,
                    "pooling": self.pooling,
                    "query_template": self.query_template,
                    "document_template": self.document_template,
                    "padding_side": self.padding_side,
                    "max_length": self.max_length,
                    "batch_size": self.batch_size,
                    "torch_dtype": self.torch_dtype_name,
                },
                f,
                indent=2,
            )

    def text_to_item_retrieval(self, query: str, topk: int) -> List[str]:
        rendered_query = self._render_query_text(query)
        query_emb = self._encode_texts([rendered_query]).squeeze(0)
        scores = torch.matmul(self.embeddings, query_emb)
        topk = min(topk, scores.shape[0])
        top_indices = torch.topk(scores, k=topk).indices.tolist()
        return [self.track_ids[i] for i in top_indices]

    def batch_text_to_item_retrieval(self, queries: List[str], topk: int) -> List[List[str]]:
        rendered_queries = [self._render_query_text(query) for query in queries]
        query_embs = self._encode_texts(rendered_queries)
        scores = torch.matmul(self.embeddings, query_embs.T)
        topk = min(topk, scores.shape[0])
        results = []
        for query_idx in range(len(queries)):
            top_indices = torch.topk(scores[:, query_idx], k=topk).indices.tolist()
            results.append([self.track_ids[idx] for idx in top_indices])
        return results


@register_retriever("bert")
class BERT_MODEL(DENSE_TRANSFORMER_MODEL):
    """Backward-compatible alias for the original BERT dense retriever."""

    def __init__(
        self,
        dataset_name,
        split_types,
        corpus_types,
        cache_dir: str = "./cache",
        model_name: str = "bert-base-uncased",
        device: str | None = None,
        batch_size: int = 32,
        max_length: int = 128,
        pooling: str = "mean",
        query_template: str = "{query}",
        document_template: str = "{text}",
        padding_side: str = "right",
        torch_dtype="float32",
        formatter=None,
    ) -> None:
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
