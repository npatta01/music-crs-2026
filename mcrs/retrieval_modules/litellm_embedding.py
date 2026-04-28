"""LiteLLM-backed dense retrieval over track metadata."""

import hashlib
import json
import os
import re
from typing import Dict, List, Tuple

import torch
import torch.nn.functional as F
from datasets import concatenate_datasets, load_dataset


def _sanitize_model_name(model_name: str) -> str:
    sanitized = model_name.replace("/", "__")
    return re.sub(r"[^A-Za-z0-9._-]+", "-", sanitized)


class LITELLM_EMBEDDING_MODEL:
    """Dense retriever that calls embeddings via LiteLLM (OpenAI-compatible)."""

    def __init__(
        self,
        dataset_name: str,
        split_types: list[str],
        corpus_types: list[str],
        cache_dir: str = "./cache",
        model_name: str = "text-embedding-3-small",
        api_base: str | None = None,
        api_key: str | None = None,
        embedding_query_prefix: str = "",
        embedding_passage_prefix: str = "",
        batch_size: int = 64,
        dimensions: int | None = None,
        formatter=None,
        **_unused,
    ) -> None:
        from mcrs.corpus_formatters import load_corpus_formatter

        self.dataset_name = dataset_name
        self.split_types = list(split_types)
        self.corpus_types = list(corpus_types)
        self.cache_dir = cache_dir
        self.model_name = model_name
        self.api_base = api_base or os.environ.get("LITELLM_PROXY_BASE", "http://localhost:4000")
        self.api_key = api_key or os.environ.get("LITELLM_PROXY_KEY", "sk-anything")
        self.embedding_query_prefix = embedding_query_prefix
        self.embedding_passage_prefix = embedding_passage_prefix
        self.batch_size = batch_size
        self.dimensions = dimensions
        self.formatter = formatter if formatter is not None else load_corpus_formatter("default")
        self.corpus_name = f"{self.formatter.name}_{'_'.join(corpus_types)}"
        self.index_dir = self._build_index_dir()
        print(f"LiteLLM embedding index dir: {self.index_dir}")

        self.metadata_dict = self._load_corpus()

        if self._has_cached_index():
            print("Loading cached LiteLLM embedding index.")
        else:
            print("Building LiteLLM embedding index from track metadata.")
            self.build_index()
        self.embeddings, self.track_ids = self._load_index()

    def _build_index_dir(self) -> str:
        config_hash = hashlib.sha1(
            json.dumps(
                {
                    "query_prefix": self.embedding_query_prefix,
                    "passage_prefix": self.embedding_passage_prefix,
                    "dimensions": self.dimensions,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:12]
        index_name = f"{self.corpus_name}_{config_hash}"
        return os.path.join(
            self.cache_dir,
            "dense_litellm",
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
        return f"{self.embedding_passage_prefix}{text}"

    def _render_query_text(self, query: str) -> str:
        return f"{self.embedding_query_prefix}{query}"

    def _embed(self, texts: list[str]) -> torch.Tensor:
        import litellm

        kwargs = {
            "model": self.model_name,
            "input": texts,
            "api_base": self.api_base,
            "api_key": self.api_key,
        }
        if self.dimensions is not None:
            kwargs["dimensions"] = self.dimensions
        response = litellm.embedding(**kwargs)
        # response.data is a list of {"embedding": [...], "index": i}
        vectors = [item["embedding"] for item in response.data]
        tensor = torch.tensor(vectors, dtype=torch.float32)
        return F.normalize(tensor, p=2, dim=1)

    def _embed_in_batches(self, texts: list[str]) -> torch.Tensor:
        chunks: list[torch.Tensor] = []
        for start in range(0, len(texts), self.batch_size):
            chunks.append(self._embed(texts[start : start + self.batch_size]))
        return torch.cat(chunks, dim=0).contiguous()

    def build_index(self) -> None:
        track_ids = list(self.metadata_dict.keys())
        corpus_texts = [self._render_document_text(self.metadata_dict[track_id]) for track_id in track_ids]
        os.makedirs(self.index_dir, exist_ok=True)

        embedding_mat = self._embed_in_batches(corpus_texts)
        torch.save(embedding_mat, os.path.join(self.index_dir, "embeddings.pt"))
        with open(os.path.join(self.index_dir, "track_ids.json"), "w", encoding="utf-8") as f:
            json.dump(track_ids, f, indent=2)
        with open(os.path.join(self.index_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "model_name": self.model_name,
                    "corpus_types": self.corpus_types,
                    "embedding_query_prefix": self.embedding_query_prefix,
                    "embedding_passage_prefix": self.embedding_passage_prefix,
                    "dimensions": self.dimensions,
                    "batch_size": self.batch_size,
                },
                f,
                indent=2,
            )

    def text_to_item_retrieval(self, query: str, topk: int) -> List[str]:
        rendered = self._render_query_text(query)
        query_emb = self._embed([rendered]).squeeze(0)
        scores = torch.matmul(self.embeddings, query_emb)
        topk = min(topk, scores.shape[0])
        top_indices = torch.topk(scores, k=topk).indices.tolist()
        return [self.track_ids[i] for i in top_indices]

    def batch_text_to_item_retrieval(self, queries: List[str], topk: int) -> List[List[str]]:
        rendered = [self._render_query_text(q) for q in queries]
        query_embs = self._embed_in_batches(rendered)
        scores = torch.matmul(self.embeddings, query_embs.T)
        topk = min(topk, scores.shape[0])
        results = []
        for query_idx in range(len(queries)):
            top_indices = torch.topk(scores[:, query_idx], k=topk).indices.tolist()
            results.append([self.track_ids[idx] for idx in top_indices])
        return results
