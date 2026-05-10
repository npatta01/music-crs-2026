"""Milvus-backed retrieval over sparse BM25 and dense embedding fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from mcrs.milvus.indexing import (
    BM25_COMPAT_CORPUS_FIELDS,
    BM25_EXPERIMENTAL_FIELDS,
    bm25_sparse_field_name,
    connect_milvus,
    has_embedding_field_name,
    resolve_bm25_combined_sparse_field,
)
from mcrs.retrieval_modules.bert import _resolve_torch_dtype


@dataclass(frozen=True)
class _Bm25FieldWeight:
    name: str
    weight: float


@dataclass(frozen=True)
class _Bm25CompatSearch:
    name: str
    kind: str
    corpus_fields: tuple[str, ...]
    sparse_field: str
    weight: float
    topk: int


@dataclass(frozen=True)
class _Bm25FieldsSearch:
    name: str
    kind: str
    fields: tuple[_Bm25FieldWeight, ...]
    weight: float
    topk: int


@dataclass(frozen=True)
class _DenseSearch:
    name: str
    kind: str
    vector_field: str
    weight: float
    topk: int
    query_encoder: dict[str, Any]
    metric_type: str


@dataclass(frozen=True)
class _SearchRequestSpec:
    anns_field: str
    data: list[Any]
    search_params: dict[str, Any]
    limit: int
    weight: float
    filter: str = ""


class _DenseQueryEncoder:
    def __init__(
        self,
        *,
        model_name: str,
        device: str,
        pooling: str,
        query_template: str,
        max_length: int,
        padding_side: str,
        torch_dtype=None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.pooling = pooling
        self.query_template = query_template
        self.max_length = int(max_length)
        self.padding_side = padding_side
        self.torch_dtype = _resolve_torch_dtype(torch_dtype)

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

    @classmethod
    def from_config(cls, config: dict[str, Any], device: str):
        return cls(
            model_name=config["model_name"],
            device=device,
            pooling=config["pooling"],
            query_template=config["query_template"],
            max_length=config["max_length"],
            padding_side=config["padding_side"],
            torch_dtype=config.get("torch_dtype"),
        )

    def _pool_hidden_states(self, last_hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        if self.pooling == "mean":
            mask = attention_mask.unsqueeze(-1).expand(last_hidden_states.size()).float()
            summed = torch.sum(last_hidden_states * mask, dim=1)
            counts = torch.clamp(mask.sum(dim=1), min=1e-9)
            return summed / counts
        if self.pooling == "cls":
            return last_hidden_states[:, 0]
        if self.pooling == "last_token":
            left_padding = bool((attention_mask[:, -1].sum() == attention_mask.shape[0]).item())
            if left_padding:
                return last_hidden_states[:, -1]
            sequence_lengths = attention_mask.sum(dim=1) - 1
            batch_size = last_hidden_states.shape[0]
            return last_hidden_states[
                torch.arange(batch_size, device=last_hidden_states.device),
                sequence_lengths,
            ]
        raise ValueError(f"Unsupported pooling mode: {self.pooling}")

    def encode(self, query: str) -> list[float]:
        rendered = self.query_template.format(query=query)
        with torch.inference_mode():
            batch = self.tokenizer(
                [rendered],
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            batch = {key: value.to(self.device) for key, value in batch.items()}
            outputs = self.model(**batch)
            pooled = self._pool_hidden_states(outputs.last_hidden_state, batch["attention_mask"])
            normalized = F.normalize(pooled, p=2, dim=1).detach().cpu()
        return normalized.squeeze(0).tolist()


class MILVUS_MODEL:
    def __init__(
        self,
        dataset_name: str,
        split_types: list[str],
        corpus_types: list[str],
        cache_dir: str = "./cache",
        formatter=None,
        retrieval_config: dict[str, Any] | None = None,
    ) -> None:
        del corpus_types, cache_dir, formatter

        config = dict(retrieval_config or {})
        self.uri = self._require_str(config, "uri")
        self.db_name = self._require_str(config, "db_name")
        self.collection_name = self._require_str(config, "collection_name")
        self.device = str(config.get("device", "cpu"))

        fusion = config.get("fusion")
        if not isinstance(fusion, dict) or fusion.get("method") != "weighted":
            raise ValueError("retrieval_config.fusion.method must be 'weighted'")

        searches = config.get("searches")
        if not isinstance(searches, list) or not searches:
            raise ValueError("retrieval_config.searches must be a non-empty list")
        self.searches = tuple(self._parse_search(search) for search in searches)
        self._dense_encoder_cache: dict[tuple[tuple[str, Any], ...], _DenseQueryEncoder] = {}

        self.client = connect_milvus(uri=self.uri, db_name=self.db_name, token=config.get("token"))
        if hasattr(self.client, "load_collection"):
            self.client.load_collection(collection_name=self.collection_name)

    @staticmethod
    def _require_str(config: dict[str, Any], key: str) -> str:
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"retrieval_config.{key} must be a non-empty string")
        return value

    @staticmethod
    def _require_positive_weight(value: Any, label: str) -> float:
        weight = float(value)
        if weight <= 0:
            raise ValueError(f"{label} must be positive")
        return weight

    @staticmethod
    def _require_positive_topk(value: Any, label: str) -> int:
        topk = int(value)
        if topk <= 0:
            raise ValueError(f"{label} must be positive")
        return topk

    def _parse_search(self, raw_search: dict[str, Any]):
        if not isinstance(raw_search, dict):
            raise ValueError("Each retrieval_config.searches entry must be a mapping")

        name = self._require_str(raw_search, "name")
        kind = self._require_str(raw_search, "kind")
        weight = self._require_positive_weight(raw_search.get("weight", 1.0), f"Search weight for {name}")
        topk = self._require_positive_topk(raw_search.get("topk"), f"Search topk for {name}")

        if kind == "bm25_compat":
            corpus_fields = tuple(raw_search.get("corpus_fields") or [])
            sparse_field = resolve_bm25_combined_sparse_field(corpus_fields)
            return _Bm25CompatSearch(
                name=name,
                kind=kind,
                corpus_fields=corpus_fields,
                sparse_field=sparse_field,
                weight=weight,
                topk=topk,
            )

        if kind == "bm25_fields":
            raw_fields = raw_search.get("fields")
            if not isinstance(raw_fields, list) or not raw_fields:
                raise ValueError(f"bm25_fields search {name} requires a non-empty fields list")
            fields = []
            seen = set()
            for field in raw_fields:
                field_name = self._require_str(field, "name")
                if field_name not in BM25_EXPERIMENTAL_FIELDS:
                    raise ValueError(f"Unsupported BM25 field: {field_name}")
                if field_name in seen:
                    raise ValueError(f"Duplicate BM25 field in {name}: {field_name}")
                seen.add(field_name)
                field_weight = self._require_positive_weight(
                    field.get("weight"),
                    f"Field weight for {name}.{field_name}",
                )
                fields.append(_Bm25FieldWeight(name=field_name, weight=field_weight))
            return _Bm25FieldsSearch(name=name, kind=kind, fields=tuple(fields), weight=weight, topk=topk)

        if kind == "dense":
            vector_field = self._require_str(raw_search, "vector_field")
            query_encoder = raw_search.get("query_encoder")
            if not isinstance(query_encoder, dict) or not query_encoder:
                raise ValueError(f"dense search {name} requires query_encoder")
            metric_type = str(raw_search.get("metric_type", "COSINE"))
            return _DenseSearch(
                name=name,
                kind=kind,
                vector_field=vector_field,
                weight=weight,
                topk=topk,
                query_encoder=query_encoder,
                metric_type=metric_type,
            )

        raise ValueError(f"Unsupported Milvus search kind: {kind}")

    def _encoder_cache_key(self, config: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
        normalized = []
        for key, value in sorted(config.items()):
            if isinstance(value, list):
                normalized.append((key, tuple(value)))
            else:
                normalized.append((key, value))
        return tuple(normalized)

    def _get_dense_encoder(self, search: _DenseSearch) -> _DenseQueryEncoder:
        cache_key = self._encoder_cache_key(search.query_encoder)
        encoder = self._dense_encoder_cache.get(cache_key)
        if encoder is None:
            encoder = _DenseQueryEncoder.from_config(search.query_encoder, device=self.device)
            self._dense_encoder_cache[cache_key] = encoder
        return encoder

    @staticmethod
    def _request_limit(config_topk: int, requested_topk: int) -> int:
        return max(config_topk, requested_topk)

    def _build_request_specs(self, query: str, topk: int) -> list[_SearchRequestSpec]:
        specs: list[_SearchRequestSpec] = []
        for search in self.searches:
            limit = self._request_limit(search.topk, topk)
            if isinstance(search, _Bm25CompatSearch):
                specs.append(
                    _SearchRequestSpec(
                        anns_field=search.sparse_field,
                        data=[query],
                        search_params={"metric_type": "BM25", "params": {}},
                        limit=limit,
                        weight=search.weight,
                    )
                )
                continue

            if isinstance(search, _Bm25FieldsSearch):
                for field in search.fields:
                    specs.append(
                        _SearchRequestSpec(
                            anns_field=bm25_sparse_field_name(field.name),
                            data=[query],
                            search_params={"metric_type": "BM25", "params": {}},
                            limit=limit,
                            weight=round(search.weight * field.weight, 12),
                        )
                    )
                continue

            if isinstance(search, _DenseSearch):
                query_vector = self._get_dense_encoder(search).encode(query)
                specs.append(
                    _SearchRequestSpec(
                        anns_field=search.vector_field,
                        data=[query_vector],
                        search_params={"metric_type": search.metric_type, "params": {}},
                        limit=limit,
                        weight=search.weight,
                        filter=f"{has_embedding_field_name(search.vector_field)} == true",
                    )
                )
                continue

            raise TypeError(f"Unhandled Milvus search spec: {search!r}")
        return specs

    @staticmethod
    def _extract_track_ids(results: Iterable[dict[str, Any]], topk: int) -> list[str]:
        track_ids = []
        for hit in results:
            track_id = hit.get("track_id")
            if track_id is None and isinstance(hit.get("entity"), dict):
                track_id = hit["entity"].get("track_id")
            if track_id is None and "id" in hit:
                track_id = hit["id"]
            if track_id is not None:
                track_ids.append(str(track_id))
        return track_ids[:topk]

    def text_to_item_retrieval(self, query: str, topk: int) -> list[str]:
        request_specs = self._build_request_specs(query, topk)
        if len(request_specs) == 1:
            request = request_specs[0]
            results = self.client.search(
                collection_name=self.collection_name,
                data=request.data,
                anns_field=request.anns_field,
                search_params=request.search_params,
                limit=request.limit,
                output_fields=["track_id"],
                filter=request.filter,
            )
            return self._extract_track_ids(results[0], topk)

        from pymilvus import AnnSearchRequest, WeightedRanker

        requests = [
            AnnSearchRequest(
                data=request.data,
                anns_field=request.anns_field,
                param=request.search_params,
                limit=request.limit,
                filter=request.filter or None,
            )
            for request in request_specs
        ]
        ranker = WeightedRanker(*[request.weight for request in request_specs])
        results = self.client.hybrid_search(
            collection_name=self.collection_name,
            reqs=requests,
            ranker=ranker,
            limit=topk,
            output_fields=["track_id"],
        )
        return self._extract_track_ids(results[0], topk)

    def batch_text_to_item_retrieval(self, queries: list[str], topk: int) -> list[list[str]]:
        return [self.text_to_item_retrieval(query, topk=topk) for query in queries]
