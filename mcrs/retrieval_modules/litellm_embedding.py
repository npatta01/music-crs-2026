"""LiteLLM-backed dense retrieval over track metadata."""

import asyncio
import hashlib
import json
import os
import re
import time
from typing import Dict, List, Tuple

import torch
import torch.nn.functional as F
from datasets import concatenate_datasets, load_dataset
from tqdm.auto import tqdm


def _proxy_model_name(model_name: str) -> str:
    return model_name if "/" in model_name else f"openai/{model_name}"


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
        batch_size: int = 128,
        concurrency: int = 8,
        max_retries: int = 4,
        retry_base_seconds: float = 2.0,
        dimensions: int | None = None,
        formatter=None,
        **_unused,
    ) -> None:
        from mcrs.corpus_formatters import load_corpus_formatter

        self.dataset_name = dataset_name
        self.split_types = list(split_types)
        self.corpus_types = list(corpus_types)
        self.cache_dir = cache_dir
        self.model_name = _proxy_model_name(model_name)
        self.api_base = api_base or os.environ.get("LITELLM_PROXY_BASE", "http://localhost:4000")
        self.api_key = (
            api_key
            or os.environ.get("LITELLM_PROXY_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or "sk-anything"
        )
        self.embedding_query_prefix = embedding_query_prefix
        self.embedding_passage_prefix = embedding_passage_prefix
        self.batch_size = batch_size
        self.concurrency = max(1, int(concurrency))
        self.max_retries = max(0, int(max_retries))
        self.retry_base_seconds = float(retry_base_seconds)
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

    def _embed_kwargs(self, texts: list[str]) -> dict:
        kwargs = {
            "model": self.model_name,
            "input": texts,
            "api_base": self.api_base,
            "api_key": self.api_key,
        }
        if self.dimensions is not None:
            kwargs["dimensions"] = self.dimensions
        return kwargs

    @staticmethod
    def _response_to_tensor(response) -> torch.Tensor:
        vectors = [item["embedding"] for item in response.data]
        tensor = torch.tensor(vectors, dtype=torch.float32)
        return F.normalize(tensor, p=2, dim=1)

    def _embed(self, texts: list[str]) -> torch.Tensor:
        import litellm

        for attempt in range(self.max_retries + 1):
            try:
                response = litellm.embedding(**self._embed_kwargs(texts))
                return self._response_to_tensor(response)
            except Exception:
                if attempt >= self.max_retries:
                    raise
                time.sleep(self.retry_base_seconds * (2**attempt))
        raise RuntimeError("unreachable embedding retry state")

    async def _aembed_batches(self, batches: list[list[str]], desc: str) -> list[torch.Tensor]:
        import litellm

        semaphore = asyncio.Semaphore(self.concurrency)
        progress = tqdm(total=len(batches), desc=desc)

        async def run(batch: list[str]) -> torch.Tensor:
            async with semaphore:
                for attempt in range(self.max_retries + 1):
                    try:
                        response = await litellm.aembedding(**self._embed_kwargs(batch))
                        progress.update(1)
                        return self._response_to_tensor(response)
                    except Exception:
                        if attempt >= self.max_retries:
                            raise
                        await asyncio.sleep(self.retry_base_seconds * (2**attempt))
                raise RuntimeError("unreachable embedding retry state")

        try:
            return await asyncio.gather(*(run(batch) for batch in batches))
        finally:
            progress.close()

    def _embed_in_batches(self, texts: list[str]) -> torch.Tensor:
        if not texts:
            return torch.empty(0)
        batches = [texts[i : i + self.batch_size] for i in range(0, len(texts), self.batch_size)]
        if len(batches) == 1:
            return self._embed(batches[0]).contiguous()
        desc = f"Embedding ({self.model_name}, {len(batches)} batches × {self.batch_size}, conc={self.concurrency})"
        chunks = asyncio.run(self._aembed_batches(batches, desc))
        return torch.cat(chunks, dim=0).contiguous()

    def _chunk_paths(self, start: int) -> tuple[str, str]:
        chunk_dir = os.path.join(self.index_dir, "chunks")
        stem = f"{start:08d}"
        return (
            os.path.join(chunk_dir, f"{stem}.pt"),
            os.path.join(chunk_dir, f"{stem}.track_ids.json"),
        )

    @staticmethod
    def _chunk_is_complete(embedding_path: str, track_ids_path: str) -> bool:
        return os.path.exists(embedding_path) and os.path.exists(track_ids_path)

    def _build_index_specs(self, track_ids: list[str], corpus_texts: list[str]) -> list[dict]:
        specs = []
        for start in range(0, len(corpus_texts), self.batch_size):
            embedding_path, track_ids_path = self._chunk_paths(start)
            end = min(start + self.batch_size, len(corpus_texts))
            specs.append(
                {
                    "start": start,
                    "texts": corpus_texts[start:end],
                    "track_ids": track_ids[start:end],
                    "embedding_path": embedding_path,
                    "track_ids_path": track_ids_path,
                }
            )
        return specs

    def _load_index_chunks(self, specs: list[dict]) -> tuple[torch.Tensor, list[str]]:
        embeddings = []
        track_ids = []
        for spec in specs:
            embeddings.append(torch.load(spec["embedding_path"], map_location="cpu"))
            with open(spec["track_ids_path"], "r", encoding="utf-8") as f:
                track_ids.extend(json.load(f))
        return torch.cat(embeddings, dim=0).contiguous(), track_ids

    async def _aembed_index_specs(self, specs: list[dict], desc: str) -> None:
        import litellm

        semaphore = asyncio.Semaphore(self.concurrency)
        progress = tqdm(total=len(specs), desc=desc)

        async def run(spec: dict) -> None:
            async with semaphore:
                for attempt in range(self.max_retries + 1):
                    try:
                        response = await litellm.aembedding(**self._embed_kwargs(spec["texts"]))
                        torch.save(self._response_to_tensor(response).contiguous(), spec["embedding_path"])
                        with open(spec["track_ids_path"], "w", encoding="utf-8") as f:
                            json.dump(spec["track_ids"], f, indent=2)
                        progress.update(1)
                        return
                    except Exception:
                        if attempt >= self.max_retries:
                            raise
                        await asyncio.sleep(self.retry_base_seconds * (2**attempt))
                raise RuntimeError("unreachable embedding retry state")

        try:
            await asyncio.gather(*(run(spec) for spec in specs))
        finally:
            progress.close()

    def _embed_index_specs(self, specs: list[dict], desc: str) -> None:
        if not specs:
            return
        if len(specs) == 1:
            spec = specs[0]
            torch.save(self._embed(spec["texts"]).contiguous(), spec["embedding_path"])
            with open(spec["track_ids_path"], "w", encoding="utf-8") as f:
                json.dump(spec["track_ids"], f, indent=2)
            return
        asyncio.run(self._aembed_index_specs(specs, desc))

    def build_index(self) -> None:
        track_ids = list(self.metadata_dict.keys())
        corpus_texts = [self._render_document_text(self.metadata_dict[track_id]) for track_id in track_ids]
        os.makedirs(self.index_dir, exist_ok=True)
        os.makedirs(os.path.join(self.index_dir, "chunks"), exist_ok=True)

        specs = self._build_index_specs(track_ids, corpus_texts)
        missing_specs = [
            spec
            for spec in specs
            if not self._chunk_is_complete(spec["embedding_path"], spec["track_ids_path"])
        ]
        if missing_specs:
            desc = (
                f"Embedding missing chunks ({self.model_name}, {len(missing_specs)} chunks x "
                f"{self.batch_size}, conc={self.concurrency})"
            )
            self._embed_index_specs(missing_specs, desc)

        embedding_mat, track_ids = self._load_index_chunks(specs)
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
                    "max_retries": self.max_retries,
                    "retry_base_seconds": self.retry_base_seconds,
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
