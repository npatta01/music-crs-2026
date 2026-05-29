"""Standalone LanceDB-backed CPU retrieval over BM25-style FTS fields."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Iterable

from lancedb.query import BooleanQuery, MatchQuery, Occur

from mcrs.lancedb.indexing import (
    BM25S_TOKENIZED_TEXT_FIELDS,
    DEFAULT_LANCEDB_TABLE_NAME,
    connect_lancedb,
)
from mcrs.milvus.indexing import (
    BM25_EXPERIMENTAL_FIELDS,
    EMBEDDING_FIELDS,
    bm25_text_field_name,
    has_embedding_field_name,
    milvus_safe_field_name,
    resolve_bm25_combined_text_field,
)
from mcrs.retrieval_modules.base import FieldQuery

LANCEDB_VECTOR_FIELDS = frozenset(milvus_safe_field_name(name) for name in EMBEDDING_FIELDS)
LANCEDB_DISTANCE_TYPES = frozenset({"l2", "cosine", "dot"})


@dataclass(frozen=True)
class _FtsCompatSearch:
    name: str
    kind: str
    corpus_fields: tuple[str, ...]
    text_field: str
    weight: float
    topk: int


@dataclass(frozen=True)
class _FtsBm25sCompatSearch:
    name: str
    kind: str
    corpus_fields: tuple[str, ...]
    text_field: str
    weight: float
    topk: int


@dataclass(frozen=True)
class _FtsFieldWeight:
    name: str
    weight: float


@dataclass(frozen=True)
class _FtsFieldsSearch:
    name: str
    kind: str
    fields: tuple[_FtsFieldWeight, ...]
    weight: float
    topk: int


@dataclass(frozen=True)
class _DenseVectorSearch:
    name: str
    kind: str
    vector_field: str
    distance_type: str
    filter_missing: bool
    weight: float
    topk: int


@dataclass(frozen=True)
class _SearchResultSet:
    hits: list[dict[str, Any]]
    weight: float


def _weighted_rrf(result_sets: Iterable[_SearchResultSet], topk: int, rank_constant: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    order = 0
    for result_set in result_sets:
        for rank, hit in enumerate(result_set.hits, start=1):
            track_id = _hit_track_id(hit)
            if track_id is None:
                continue
            if track_id not in first_seen:
                first_seen[track_id] = order
                order += 1
            scores[track_id] = scores.get(track_id, 0.0) + result_set.weight / (rank_constant + rank)
    ranked = sorted(scores, key=lambda track_id: (-scores[track_id], first_seen[track_id]))
    return ranked[:topk]


def _hit_track_id(hit: dict[str, Any]) -> str | None:
    track_id = hit.get("track_id")
    if track_id is None and isinstance(hit.get("entity"), dict):
        track_id = hit["entity"].get("track_id")
    if track_id is None and "id" in hit:
        track_id = hit["id"]
    if track_id is None:
        return None
    return str(track_id)


class LanceDbRetriever:
    """Standalone CPU-only LanceDB retriever.

    The class has no dependency on CRS baseline objects or Modal. It opens the
    database table once at construction time and can be reused by local code,
    Modal class services, or future self-hosted endpoints.
    """

    def __init__(
        self,
        db_uri: str,
        table_name: str,
        searches: list[dict[str, Any]],
        fusion: dict[str, Any],
        embedding_client: Any | None = None,
        connect: Callable[[str], Any] | None = None,
    ) -> None:
        self._init_from_config(
            {
                "db_uri": db_uri,
                "table_name": table_name,
                "searches": searches,
                "fusion": fusion,
                "device": "cpu",
            },
            embedding_client=embedding_client,
            connect=connect,
        )

    @classmethod
    def from_retrieval_config(
        cls,
        retrieval_config: dict[str, Any],
        embedding_client: Any | None = None,
        connect: Callable[[str], Any] | None = None,
    ) -> "LanceDbRetriever":
        instance = cls.__new__(cls)
        instance._init_from_config(
            dict(retrieval_config),
            embedding_client=embedding_client,
            connect=connect,
        )
        return instance

    def _init_from_config(
        self,
        config: dict[str, Any],
        embedding_client: Any | None = None,
        connect: Callable[[str], Any] | None = None,
    ) -> None:
        device = str(config.get("device", "cpu"))
        if device != "cpu":
            raise ValueError("LanceDB retrieval is CPU-only for this experiment; set device: cpu")

        self.db_uri = self._require_str(config, "db_uri")
        self.table_name = str(config.get("table_name", DEFAULT_LANCEDB_TABLE_NAME))
        if not self.table_name.strip():
            raise ValueError("retrieval_config.table_name must be a non-empty string")

        fusion = config.get("fusion")
        if not isinstance(fusion, dict) or fusion.get("method") != "weighted_rrf":
            raise ValueError("retrieval_config.fusion.method must be 'weighted_rrf'")

        # `searches` is optional: callers that use the imperative
        # `text_to_item_retrieval_channels` API don't need a declarative search
        # list. When `searches` is provided it must be a non-empty list of
        # well-formed search specs (validated below).
        searches = config.get("searches")
        if searches is None:
            self.searches: tuple = ()
        else:
            if not isinstance(searches, list) or not searches:
                raise ValueError("retrieval_config.searches, when present, must be a non-empty list")
            self.searches = tuple(self._parse_search(search) for search in searches)

        connect_fn = connect or connect_lancedb
        self.db = connect_fn(self.db_uri)
        self.table = self.db.open_table(self.table_name)
        self.embedding_client = embedding_client
        self._catalog_track_ids: list[str] | None = None

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

    @staticmethod
    def _require_distance_type(value: Any) -> str:
        distance_type = str(value)
        if distance_type not in LANCEDB_DISTANCE_TYPES:
            raise ValueError(
                f"Unsupported LanceDB distance type: {distance_type!r}. "
                f"Valid options: {sorted(LANCEDB_DISTANCE_TYPES)}"
            )
        return distance_type

    def _parse_search(self, raw_search: dict[str, Any]):
        if not isinstance(raw_search, dict):
            raise ValueError("Each retrieval_config.searches entry must be a mapping")

        name = self._require_str(raw_search, "name")
        kind = self._require_str(raw_search, "kind")
        weight = self._require_positive_weight(raw_search.get("weight", 1.0), f"Search weight for {name}")
        topk = self._require_positive_topk(raw_search.get("topk"), f"Search topk for {name}")

        if kind == "fts_compat":
            corpus_fields = tuple(raw_search.get("corpus_fields") or [])
            text_field = resolve_bm25_combined_text_field(corpus_fields)
            return _FtsCompatSearch(
                name=name,
                kind=kind,
                corpus_fields=corpus_fields,
                text_field=text_field,
                weight=weight,
                topk=topk,
            )

        if kind == "fts_bm25s_compat":
            corpus_fields = tuple(raw_search.get("corpus_fields") or [])
            source_text_field = resolve_bm25_combined_text_field(corpus_fields)
            text_field = BM25S_TOKENIZED_TEXT_FIELDS[source_text_field]
            return _FtsBm25sCompatSearch(
                name=name,
                kind=kind,
                corpus_fields=corpus_fields,
                text_field=text_field,
                weight=weight,
                topk=topk,
            )

        if kind == "fts_fields":
            raw_fields = raw_search.get("fields")
            if not isinstance(raw_fields, list) or not raw_fields:
                raise ValueError(f"fts_fields search {name} requires a non-empty fields list")
            fields = []
            seen = set()
            for field in raw_fields:
                field_name = self._require_str(field, "name")
                if field_name not in BM25_EXPERIMENTAL_FIELDS:
                    raise ValueError(f"Unsupported FTS field: {field_name}")
                if field_name in seen:
                    raise ValueError(f"Duplicate FTS field in {name}: {field_name}")
                seen.add(field_name)
                field_weight = self._require_positive_weight(
                    field.get("weight"),
                    f"Field weight for {name}.{field_name}",
                )
                fields.append(_FtsFieldWeight(name=field_name, weight=field_weight))
            return _FtsFieldsSearch(name=name, kind=kind, fields=tuple(fields), weight=weight, topk=topk)

        if kind == "dense_vector":
            vector_field = self._require_str(raw_search, "vector_field")
            if vector_field not in LANCEDB_VECTOR_FIELDS:
                raise ValueError(f"Unsupported LanceDB vector field: {vector_field}")
            distance_type = self._require_distance_type(raw_search.get("distance_type", "cosine"))
            filter_missing = bool(raw_search.get("filter_missing", True))
            return _DenseVectorSearch(
                name=name,
                kind=kind,
                vector_field=vector_field,
                distance_type=distance_type,
                filter_missing=filter_missing,
                weight=weight,
                topk=topk,
            )

        raise ValueError(f"Unsupported LanceDB search kind: {kind}")

    @staticmethod
    def _request_limit(config_topk: int, requested_topk: int) -> int:
        return max(config_topk, requested_topk)

    @staticmethod
    def _bm25s_query_object(query: str, text_field: str) -> BooleanQuery | None:
        import bm25s

        tokens = bm25s.tokenize([query], return_ids=False, show_progress=False)[0]
        counts = Counter(tokens)
        if not counts:
            return None
        # Match the direct bm25s baseline: repeated query tokens become term-frequency boosts.
        return BooleanQuery(
            [
                (Occur.SHOULD, MatchQuery(token, text_field, boost=float(count)))
                for token, count in counts.items()
            ]
        )

    def _load_catalog_track_ids(self) -> list[str]:
        if self._catalog_track_ids is None:
            rows = self.table.to_arrow().select(["track_id"]).to_pylist()
            self._catalog_track_ids = [str(row["track_id"]) for row in rows]
        return self._catalog_track_ids

    def _pad_short_hits(self, hits: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        if len(hits) >= limit:
            return hits
        try:
            catalog_track_ids = self._load_catalog_track_ids()
        except AttributeError:
            return hits

        padded = list(hits)
        seen = {_hit_track_id(hit) for hit in hits}
        for track_id in catalog_track_ids:
            if track_id in seen:
                continue
            padded.append({"track_id": track_id, "_score": 0.0})
            seen.add(track_id)
            if len(padded) >= limit:
                break
        return padded

    def _fts_search(self, query: str, text_field: str, limit: int, *, pad_short: bool) -> list[dict[str, Any]]:
        hits = (
            self.table.search(query, query_type="fts", fts_columns=text_field)
            .limit(limit)
            .select(["track_id", "_score"])
            .to_list()
        )
        return self._pad_short_hits(hits, limit) if pad_short else hits

    def _fts_bm25s_search(self, query: str, text_field: str, limit: int, *, pad_short: bool) -> list[dict[str, Any]]:
        query_object = self._bm25s_query_object(query, text_field)
        if query_object is None:
            return self._pad_short_hits([], limit) if pad_short else []
        hits = (
            self.table.search(query_object, query_type="fts")
            .limit(limit)
            .select(["track_id", "_score"])
            .to_list()
        )
        return self._pad_short_hits(hits, limit) if pad_short else hits

    def _embed_query(self, query: str) -> list[float]:
        if self.embedding_client is None:
            raise RuntimeError("dense_vector search requires an embedding client")
        vectors = self.embedding_client.embed_batch([query])
        if not vectors:
            raise RuntimeError("embedding client returned no vectors")
        return [float(value) for value in vectors[0]]

    def _dense_vector_search(self, query: str, search: _DenseVectorSearch, limit: int) -> list[dict[str, Any]]:
        query_builder = self.table.search(
            self._embed_query(query),
            query_type="vector",
            vector_column_name=search.vector_field,
        ).distance_type(search.distance_type)
        if search.filter_missing:
            query_builder = query_builder.where(f"{has_embedding_field_name(search.vector_field)} = true")
        hits = (
            query_builder
            .limit(limit)
            .select(["track_id", "_distance"])
            .to_list()
        )
        return hits

    def text_to_item_retrieval(self, query: str, topk: int) -> list[str]:
        if not self.searches:
            raise RuntimeError(
                "text_to_item_retrieval requires `searches` in the retrieval config. "
                "For the Retriever-Protocol API (FieldQuery clauses + dense), use "
                "`search` or `search_embedding` instead."
            )
        result_sets = []
        pad_single_search = len(self.searches) == 1 and isinstance(
            self.searches[0],
            (_FtsCompatSearch, _FtsBm25sCompatSearch),
        )
        for search in self.searches:
            limit = self._request_limit(search.topk, topk)
            if isinstance(search, _FtsCompatSearch):
                result_sets.append(
                    _SearchResultSet(
                        hits=self._fts_search(query, search.text_field, limit, pad_short=pad_single_search),
                        weight=search.weight,
                    )
                )
                continue

            if isinstance(search, _FtsBm25sCompatSearch):
                result_sets.append(
                    _SearchResultSet(
                        hits=self._fts_bm25s_search(query, search.text_field, limit, pad_short=pad_single_search),
                        weight=search.weight,
                    )
                )
                continue

            if isinstance(search, _FtsFieldsSearch):
                for field in search.fields:
                    result_sets.append(
                        _SearchResultSet(
                            hits=self._fts_search(
                                query,
                                bm25_text_field_name(field.name),
                                limit,
                                pad_short=False,
                            ),
                            weight=round(search.weight * field.weight, 12),
                        )
                    )
                continue

            if isinstance(search, _DenseVectorSearch):
                result_sets.append(
                    _SearchResultSet(
                        hits=self._dense_vector_search(query, search, limit),
                        weight=search.weight,
                    )
                )
                continue

            raise TypeError(f"Unhandled LanceDB search spec: {search!r}")

        if len(result_sets) == 1:
            track_ids = []
            for hit in result_sets[0].hits:
                track_id = _hit_track_id(hit)
                if track_id is not None:
                    track_ids.append(track_id)
            return track_ids[:topk]
        return _weighted_rrf(result_sets, topk=topk)

    def batch_text_to_item_retrieval(self, queries: list[str], topk: int) -> list[list[str]]:
        return [self.text_to_item_retrieval(query, topk=topk) for query in queries]

    def retrieve(self, query: str, topk: int) -> list[str]:
        return self.text_to_item_retrieval(query, topk=topk)

    def retrieve_batch(self, queries: list[str], topk: int) -> list[list[str]]:
        return self.batch_text_to_item_retrieval(queries, topk=topk)

    # ---------------------------------------------------------------------
    # Retriever Protocol implementation (see mcrs/retrieval_modules/base.py).
    #
    # The compiler issues exactly two calls per turn: one `search` with N
    # FieldQuery clauses (BM25 across whichever fields have content) and one
    # `search_embedding`. Cross-modal fusion of those two ranked lists is the
    # compiler's job; intra-BM25 fusion across clauses lives here because the
    # backend can decide whether to use native multi-field BM25 (Tantivy,
    # Milvus) or simulate via per-field calls + weighted RRF.
    # ---------------------------------------------------------------------

    @property
    def supported_text_fields(self) -> frozenset[str]:
        return frozenset(BM25_EXPERIMENTAL_FIELDS)

    @property
    def supported_vector_fields(self) -> frozenset[str]:
        return LANCEDB_VECTOR_FIELDS

    def search(
        self,
        clauses: list[FieldQuery],
        *,
        topk: int = 1000,
    ) -> list[tuple[str, float]]:
        """BM25/FTS over one or more field-targeted clauses.

        Issues a SINGLE tantivy Boolean(SHOULD) query with one MatchQuery per
        clause — true Solr-style multi-field BM25 in one call. Per-field
        boosts are honored via MatchQuery's `boost` parameter; tantivy
        computes BM25 across all fields and produces a single ranked list.

        Empty / whitespace-only clauses are skipped. Returns ranked
        `(track_id, score)` pairs (higher score = more relevant).
        """
        if not clauses:
            return []
        valid: list[FieldQuery] = []
        for c in clauses:
            if not c.query.strip():
                continue
            if c.field not in BM25_EXPERIMENTAL_FIELDS:
                raise ValueError(
                    f"Unsupported BM25 field: {c.field!r}. "
                    f"Valid options: {sorted(BM25_EXPERIMENTAL_FIELDS)}"
                )
            valid.append(c)
        if not valid:
            return []

        # Build one MatchQuery per clause — phrase is the whole query string;
        # tantivy tokenizes per-column internally. Boost = field weight.
        match_clauses = [
            (
                Occur.SHOULD,
                MatchQuery(
                    c.query,
                    bm25_text_field_name(c.field),
                    boost=float(c.boost),
                ),
            )
            for c in valid
        ]
        bool_query = BooleanQuery(match_clauses)

        hits = (
            self.table.search(bool_query, query_type="fts")
            .limit(topk)
            .select(["track_id", "_score"])
            .to_list()
        )
        out: list[tuple[str, float]] = []
        for hit in hits:
            tid = _hit_track_id(hit)
            if tid is None:
                continue
            out.append((tid, float(hit.get("_score", 0.0))))
        return out

    def search_embedding(
        self,
        query_vector: list[float],
        *,
        vector_field: str,
        topk: int = 1000,
        distance_type: str = "cosine",
        filter_missing: bool = True,
    ) -> list[tuple[str, float]]:
        """Dense ANN against one vector column with a caller-supplied vector.

        Returns ranked (track_id, similarity) pairs. Higher = more similar;
        backend converts native distances per `distance_type` so the caller
        never has to remember which conventions are flipped.
        """
        if vector_field not in LANCEDB_VECTOR_FIELDS:
            raise ValueError(
                f"Unsupported LanceDB vector field: {vector_field!r}. "
                f"Valid options: {sorted(LANCEDB_VECTOR_FIELDS)}"
            )
        distance_type = self._require_distance_type(distance_type)
        query_builder = self.table.search(
            list(query_vector),
            query_type="vector",
            vector_column_name=vector_field,
        ).distance_type(distance_type)
        if filter_missing:
            query_builder = query_builder.where(
                f"{has_embedding_field_name(vector_field)} = true"
            )
        hits = (
            query_builder
            .limit(topk)
            .select(["track_id", "_distance"])
            .to_list()
        )
        out: list[tuple[str, float]] = []
        for hit in hits:
            tid = _hit_track_id(hit)
            if tid is None:
                continue
            distance = float(hit.get("_distance", 0.0))
            out.append((tid, _distance_to_similarity(distance, distance_type)))
        return out


def _distance_to_similarity(distance: float, distance_type: str) -> float:
    """Backend-side flip so the Retriever Protocol contract holds:
    higher = more similar."""
    if distance_type in ("cosine", "dot"):
        # LanceDB cosine returns 1 - cos_sim, and dot returns 1 - dot_product.
        # Invert both so callers get "higher = more similar".
        return 1.0 - distance
    # l2 has "lower = closer" semantics.
    return 1.0 / (1.0 + distance)
