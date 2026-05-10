"""Helpers for loading Music CRS track data into a Milvus collection."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from datasets import load_dataset
from mcrs.corpus_formatters import load_corpus_formatter

TRACK_METADATA_DATASET = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"
TRACK_EMBEDDINGS_DATASET = "talkpl-ai/TalkPlayData-Challenge-Track-Embeddings"
TRACK_SPLIT = "all_tracks"

ARRAY_METADATA_FIELDS = (
    "track_name",
    "artist_name",
    "album_name",
    "tag_list",
    "ISRC",
    "artist_id",
    "album_id",
)
SCALAR_METADATA_FIELDS = (
    "popularity",
    "release_date",
    "duration",
)
EMBEDDING_FIELDS = (
    "audio-laion_clap",
    "image-siglip2",
    "cf-bpr",
    "attributes-qwen3_embedding_0.6b",
    "lyrics-qwen3_embedding_0.6b",
    "metadata-qwen3_embedding_0.6b",
)
BM25_COMPAT_CORPUS_FIELDS = (
    "track_name",
    "artist_name",
    "album_name",
    "release_date",
)
BM25_WITH_TAG_LIST_CORPUS_FIELDS = (
    "track_name",
    "artist_name",
    "album_name",
    "release_date",
    "tag_list",
)
BM25_EXPERIMENTAL_FIELDS = (
    "track_name",
    "artist_name",
    "album_name",
    "release_date",
    "tag_list",
)
BM25_COMPAT_TEXT_FIELD = "bm25_compat_text"
BM25_COMPAT_SPARSE_FIELD = "bm25_compat_sparse"
BM25_WITH_TAG_LIST_TEXT_FIELD = "bm25_with_tag_list_text"
BM25_WITH_TAG_LIST_SPARSE_FIELD = "bm25_with_tag_list_sparse"
DEFAULT_VECTOR_INDEX_TYPE = "FLAT"
DEFAULT_VECTOR_METRIC_TYPE = "COSINE"
DEFAULT_VECTOR_INDEX_PARAMS: dict[str, Any] = {}
DEFAULT_SPARSE_VECTOR_INDEX_TYPE = "SPARSE_INVERTED_INDEX"
DEFAULT_SPARSE_VECTOR_METRIC_TYPE = "BM25"
DEFAULT_SPARSE_VECTOR_INDEX_PARAMS = {"inverted_index_algo": "DAAT_MAXSCORE"}
DEFAULT_BM25_ANALYZER_PARAMS = {
    "tokenizer": "standard",
    "filter": [
        "lowercase",
        {
            "type": "stop",
            "stop_words": ["_english_"],
        },
    ],
}

BM25_COMBINED_CORPUS_FIELDS = {
    BM25_COMPAT_CORPUS_FIELDS: BM25_COMPAT_TEXT_FIELD,
    BM25_WITH_TAG_LIST_CORPUS_FIELDS: BM25_WITH_TAG_LIST_TEXT_FIELD,
}


@dataclass(frozen=True)
class CollectionFieldSpec:
    name: str
    datatype_name: str
    nullable: bool = False
    is_primary: bool = False
    max_length: int | None = None
    element_type_name: str | None = None
    max_capacity: int | None = None
    dim: int | None = None
    enable_match: bool = False
    enable_analyzer: bool = False
    analyzer_params: dict[str, Any] | None = None


@dataclass(frozen=True)
class CollectionFunctionSpec:
    name: str
    function_type_name: str
    input_field_names: list[str]
    output_field_names: list[str]
    params: dict[str, Any] | None = None


@dataclass(frozen=True)
class CollectionPlan:
    fields: list[CollectionFieldSpec]
    vector_field_names: list[str]
    bm25_field_names: list[str]
    sparse_vector_field_names: list[str]
    functions: list[CollectionFunctionSpec]
    vector_dims: dict[str, int]
    embedding_presence_counts: dict[str, int]
    metadata_row_count: int
    metadata_only_row_count: int


@dataclass(frozen=True)
class MilvusBuildSummary:
    collection_name: str
    inserted_rows: int
    metadata_row_count: int
    metadata_only_row_count: int
    vector_field_names: list[str]
    embedding_presence_counts: dict[str, int]


def milvus_safe_field_name(name: str) -> str:
    """Normalize a dataset column into a Milvus-safe field name."""
    sanitized = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_")
    sanitized = re.sub(r"_+", "_", sanitized)
    if not sanitized:
        raise ValueError(f"Unable to sanitize field name: {name!r}")
    if sanitized[0].isdigit():
        sanitized = f"f_{sanitized}"
    return sanitized


def has_embedding_field_name(vector_field_name: str) -> str:
    return f"has_{vector_field_name}"


def sparse_bm25_field_name(text_field_name: str) -> str:
    if not text_field_name.endswith("_text"):
        raise ValueError(f"BM25 text field must end with '_text': {text_field_name}")
    return f"{text_field_name[:-5]}_sparse"


def bm25_text_field_name(corpus_field: str) -> str:
    if corpus_field not in BM25_EXPERIMENTAL_FIELDS:
        raise ValueError(f"Unsupported BM25 field: {corpus_field}")
    return f"{corpus_field}_text"


def bm25_sparse_field_name(corpus_field: str) -> str:
    return sparse_bm25_field_name(bm25_text_field_name(corpus_field))


def resolve_bm25_combined_text_field(corpus_fields: Iterable[str]) -> str:
    normalized_fields = tuple(corpus_fields)
    text_field = BM25_COMBINED_CORPUS_FIELDS.get(normalized_fields)
    if text_field is None:
        raise ValueError(
            "Unsupported combined BM25 corpus_fields: "
            f"{list(normalized_fields)}. Supported profiles are: "
            f"{[list(fields) for fields in BM25_COMBINED_CORPUS_FIELDS]}"
        )
    return text_field


def resolve_bm25_combined_sparse_field(corpus_fields: Iterable[str]) -> str:
    return sparse_bm25_field_name(resolve_bm25_combined_text_field(corpus_fields))


def _utf8_len(value: str) -> int:
    return len(value.encode("utf-8"))


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _normalize_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _normalize_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _normalize_embedding(value: Any) -> list[float] | None:
    if value is None:
        return None
    vector = [float(item) for item in value]
    if not vector:
        return None
    return vector


def render_bm25_text_fields(metadata_row: Mapping[str, Any]) -> dict[str, str]:
    """Render BM25 text fields using the same formatter style as manual BM25."""
    formatter = load_corpus_formatter("default")
    metadata = dict(metadata_row)
    text_fields = {
        text_field: formatter.format(metadata, list(corpus_fields))
        for corpus_fields, text_field in BM25_COMBINED_CORPUS_FIELDS.items()
    }
    for corpus_field in BM25_EXPERIMENTAL_FIELDS:
        text_fields[bm25_text_field_name(corpus_field)] = formatter.format(metadata, [corpus_field])
    return text_fields


def build_track_document(
    metadata_row: Mapping[str, Any],
    embedding_row: Mapping[str, Any] | None,
    vector_dims: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Merge one metadata row and one embedding row into a Milvus insert document."""
    document = {
        "track_id": str(metadata_row["track_id"]),
        "track_name": _normalize_string_list(metadata_row.get("track_name")),
        "artist_name": _normalize_string_list(metadata_row.get("artist_name")),
        "album_name": _normalize_string_list(metadata_row.get("album_name")),
        "tag_list": _normalize_string_list(metadata_row.get("tag_list")),
        "popularity": _normalize_optional_float(metadata_row.get("popularity")),
        "release_date": str(metadata_row.get("release_date") or ""),
        "duration": _normalize_optional_int(metadata_row.get("duration")),
        "ISRC": _normalize_string_list(metadata_row.get("ISRC")),
        "artist_id": _normalize_string_list(metadata_row.get("artist_id")),
        "album_id": _normalize_string_list(metadata_row.get("album_id")),
    }
    document.update(render_bm25_text_fields(metadata_row))

    for raw_name in EMBEDDING_FIELDS:
        normalized_name = milvus_safe_field_name(raw_name)
        vector = None if embedding_row is None else _normalize_embedding(embedding_row.get(raw_name))
        has_vector = vector is not None
        if vector is None:
            if vector_dims is None or normalized_name not in vector_dims:
                raise ValueError(f"Missing inferred dimension for vector field {normalized_name}")
            vector = [0.0] * vector_dims[normalized_name]
        document[normalized_name] = vector
        document[has_embedding_field_name(normalized_name)] = has_vector

    return document


def build_track_collection_plan(
    metadata_rows: Iterable[Mapping[str, Any]],
    embedding_rows: Iterable[Mapping[str, Any]],
) -> CollectionPlan:
    """Infer a Milvus schema plan from track metadata and embedding rows."""
    metadata_rows = list(metadata_rows)
    bm25_text_field_names = list(BM25_COMBINED_CORPUS_FIELDS.values()) + [
        bm25_text_field_name(field_name) for field_name in BM25_EXPERIMENTAL_FIELDS
    ]
    metadata_track_ids = set()
    max_track_id_length = 1
    max_release_date_length = 1
    max_array_capacities = {field: 1 for field in ARRAY_METADATA_FIELDS}
    max_array_value_lengths = {field: 1 for field in ARRAY_METADATA_FIELDS}
    max_bm25_text_lengths = {field: 1 for field in bm25_text_field_names}

    for row in metadata_rows:
        track_id = str(row["track_id"])
        metadata_track_ids.add(track_id)
        max_track_id_length = max(max_track_id_length, _utf8_len(track_id))
        release_date = str(row.get("release_date") or "")
        max_release_date_length = max(max_release_date_length, _utf8_len(release_date))
        for field_name in ARRAY_METADATA_FIELDS:
            values = _normalize_string_list(row.get(field_name))
            max_array_capacities[field_name] = max(max_array_capacities[field_name], len(values) or 1)
            for value in values:
                max_array_value_lengths[field_name] = max(
                    max_array_value_lengths[field_name],
                    _utf8_len(value),
                )
        for field_name, text_value in render_bm25_text_fields(row).items():
            max_bm25_text_lengths[field_name] = max(max_bm25_text_lengths[field_name], _utf8_len(text_value))

    vector_dims: dict[str, int] = {}
    embedding_presence_counts = {milvus_safe_field_name(name): 0 for name in EMBEDDING_FIELDS}
    embedding_track_ids = set()
    for row in embedding_rows:
        track_id = str(row["track_id"])
        embedding_track_ids.add(track_id)
        for raw_name in EMBEDDING_FIELDS:
            normalized_name = milvus_safe_field_name(raw_name)
            vector = _normalize_embedding(row.get(raw_name))
            if vector is None:
                continue
            embedding_presence_counts[normalized_name] += 1
            current_dim = vector_dims.get(normalized_name)
            if current_dim is None:
                vector_dims[normalized_name] = len(vector)
            elif current_dim != len(vector):
                raise ValueError(
                    f"Inconsistent dimension for {raw_name}: expected {current_dim}, got {len(vector)}"
                )

    missing_dims = [raw_name for raw_name in EMBEDDING_FIELDS if milvus_safe_field_name(raw_name) not in vector_dims]
    if missing_dims:
        raise ValueError(f"Unable to infer dimensions for embedding fields: {missing_dims}")

    fields = [
        CollectionFieldSpec(
            name="track_id",
            datatype_name="VARCHAR",
            is_primary=True,
            max_length=max_track_id_length,
        )
    ]
    for field_name in ARRAY_METADATA_FIELDS:
        fields.append(
            CollectionFieldSpec(
                name=field_name,
                datatype_name="ARRAY",
                nullable=True,
                element_type_name="VARCHAR",
                max_capacity=max_array_capacities[field_name],
                max_length=max_array_value_lengths[field_name],
            )
        )
    fields.extend(
        [
            CollectionFieldSpec(name="popularity", datatype_name="DOUBLE", nullable=True),
            CollectionFieldSpec(
                name="release_date",
                datatype_name="VARCHAR",
                nullable=True,
                max_length=max_release_date_length,
            ),
            CollectionFieldSpec(name="duration", datatype_name="INT64", nullable=True),
        ]
    )
    for field_name in bm25_text_field_names:
        fields.append(
            CollectionFieldSpec(
                name=field_name,
                datatype_name="VARCHAR",
                max_length=max_bm25_text_lengths[field_name],
                enable_match=True,
                enable_analyzer=True,
                analyzer_params=DEFAULT_BM25_ANALYZER_PARAMS,
            )
        )
    sparse_vector_field_names = []
    functions = []
    for field_name in bm25_text_field_names:
        sparse_field_name = sparse_bm25_field_name(field_name)
        sparse_vector_field_names.append(sparse_field_name)
        fields.append(CollectionFieldSpec(name=sparse_field_name, datatype_name="SPARSE_FLOAT_VECTOR"))
        functions.append(
            CollectionFunctionSpec(
                name=f"{field_name}_bm25",
                function_type_name="BM25",
                input_field_names=[field_name],
                output_field_names=[sparse_field_name],
            )
        )
    vector_field_names = []
    for raw_name in EMBEDDING_FIELDS:
        normalized_name = milvus_safe_field_name(raw_name)
        vector_field_names.append(normalized_name)
        fields.append(
            CollectionFieldSpec(name=has_embedding_field_name(normalized_name), datatype_name="BOOL")
        )
        fields.append(
            CollectionFieldSpec(
                name=normalized_name,
                datatype_name="FLOAT_VECTOR",
                nullable=False,
                dim=vector_dims[normalized_name],
            )
        )

    return CollectionPlan(
        fields=fields,
        vector_field_names=vector_field_names,
        bm25_field_names=bm25_text_field_names,
        sparse_vector_field_names=sparse_vector_field_names,
        functions=functions,
        vector_dims=vector_dims,
        embedding_presence_counts=embedding_presence_counts,
        metadata_row_count=len(metadata_rows),
        metadata_only_row_count=len(metadata_track_ids - embedding_track_ids),
    )


def _default_dense_index_params(index_type: str) -> dict[str, Any]:
    if index_type.upper() == "HNSW":
        return {"M": 16, "efConstruction": 200}
    return {}


def build_vector_index_plan(
    collection_plan: CollectionPlan,
    dense_index_type: str = DEFAULT_VECTOR_INDEX_TYPE,
    dense_metric_type: str = DEFAULT_VECTOR_METRIC_TYPE,
    dense_params: dict[str, Any] | None = None,
    sparse_index_type: str = DEFAULT_SPARSE_VECTOR_INDEX_TYPE,
    sparse_metric_type: str = DEFAULT_SPARSE_VECTOR_METRIC_TYPE,
    sparse_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return the vector index definitions for a collection plan."""
    dense_params = dict(_default_dense_index_params(dense_index_type) if dense_params is None else dense_params)
    sparse_params = dict(DEFAULT_SPARSE_VECTOR_INDEX_PARAMS if sparse_params is None else sparse_params)
    dense_indexes = [
        {
            "field_name": field_name,
            "index_type": dense_index_type,
            "metric_type": dense_metric_type,
            "params": dense_params,
        }
        for field_name in collection_plan.vector_field_names
    ]
    sparse_indexes = [
        {
            "field_name": field_name,
            "index_type": sparse_index_type,
            "metric_type": sparse_metric_type,
            "params": sparse_params,
        }
        for field_name in collection_plan.sparse_vector_field_names
    ]
    return dense_indexes + sparse_indexes


def load_track_metadata_rows(
    dataset_name: str = TRACK_METADATA_DATASET,
    split: str = TRACK_SPLIT,
):
    return load_dataset(dataset_name)[split]


def load_track_embedding_rows(
    dataset_name: str = TRACK_EMBEDDINGS_DATASET,
    split: str = TRACK_SPLIT,
):
    return load_dataset(dataset_name)[split]


def _require_pymilvus():
    try:
        from pymilvus import DataType, Function, FunctionType, MilvusClient
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only in real envs
        raise ModuleNotFoundError(
            "pymilvus is required for Milvus indexing. Install the project dependencies first."
        ) from exc
    return MilvusClient, DataType, Function, FunctionType


def create_pymilvus_schema(collection_plan: CollectionPlan):
    """Convert a collection plan into a pymilvus schema object."""
    MilvusClient, DataType, Function, FunctionType = _require_pymilvus()
    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    for field in collection_plan.fields:
        kwargs: dict[str, Any] = {
            "field_name": field.name,
            "datatype": getattr(DataType, field.datatype_name),
            "nullable": field.nullable,
        }
        if field.is_primary:
            kwargs["is_primary"] = True
        if field.max_length is not None:
            kwargs["max_length"] = field.max_length
        if field.element_type_name is not None:
            kwargs["element_type"] = getattr(DataType, field.element_type_name)
        if field.max_capacity is not None:
            kwargs["max_capacity"] = field.max_capacity
        if field.dim is not None:
            kwargs["dim"] = field.dim
        if field.enable_match:
            kwargs["enable_match"] = True
        if field.enable_analyzer:
            kwargs["enable_analyzer"] = True
        if field.analyzer_params is not None:
            kwargs["analyzer_params"] = field.analyzer_params
        schema.add_field(**kwargs)
    for function in collection_plan.functions:
        schema.add_function(
            Function(
                name=function.name,
                function_type=getattr(FunctionType, function.function_type_name),
                input_field_names=function.input_field_names,
                output_field_names=function.output_field_names,
                params=function.params,
            )
        )
    return schema


def create_pymilvus_index_params(
    collection_plan: CollectionPlan,
    index_type: str = DEFAULT_VECTOR_INDEX_TYPE,
    metric_type: str = DEFAULT_VECTOR_METRIC_TYPE,
    params: dict[str, Any] | None = None,
):
    """Convert a collection plan into pymilvus index params."""
    MilvusClient, _, _, _ = _require_pymilvus()
    index_params = MilvusClient.prepare_index_params()
    for index_definition in build_vector_index_plan(
        collection_plan,
        dense_index_type=index_type,
        dense_metric_type=metric_type,
        dense_params=params,
    ):
        index_params.add_index(**index_definition)
    return index_params


def iter_track_documents(
    metadata_rows: Iterable[Mapping[str, Any]],
    embedding_rows: Iterable[Mapping[str, Any]],
    vector_dims: Mapping[str, int],
):
    """Yield full-row Milvus documents, including metadata-only tracks."""
    metadata_map = {str(row["track_id"]): row for row in metadata_rows}
    seen_track_ids = set()

    for embedding_row in embedding_rows:
        track_id = str(embedding_row["track_id"])
        metadata_row = metadata_map.get(track_id)
        if metadata_row is None:
            raise KeyError(f"Embedding row {track_id} has no matching metadata row.")
        seen_track_ids.add(track_id)
        yield build_track_document(metadata_row, embedding_row, vector_dims=vector_dims)

    for track_id, metadata_row in metadata_map.items():
        if track_id not in seen_track_ids:
            yield build_track_document(metadata_row, embedding_row=None, vector_dims=vector_dims)


def connect_milvus(
    uri: str = "http://localhost:19530",
    db_name: str = "default",
    token: str | None = None,
):
    """Create a Milvus client instance."""
    MilvusClient, _, _, _ = _require_pymilvus()
    kwargs: dict[str, Any] = {"uri": uri, "db_name": db_name}
    if token:
        kwargs["token"] = token
    return MilvusClient(**kwargs)


def recreate_track_collection(
    client,
    collection_name: str,
    collection_plan: CollectionPlan,
    drop_existing: bool = False,
    index_type: str = DEFAULT_VECTOR_INDEX_TYPE,
    metric_type: str = DEFAULT_VECTOR_METRIC_TYPE,
    index_params: dict[str, Any] | None = None,
) -> None:
    """Create or replace the Milvus collection backing the track catalog."""
    if client.has_collection(collection_name=collection_name):
        if not drop_existing:
            raise ValueError(
                f"Collection {collection_name!r} already exists. Pass drop_existing=True to replace it."
            )
        client.drop_collection(collection_name=collection_name)

    schema = create_pymilvus_schema(collection_plan)
    pymilvus_index_params = create_pymilvus_index_params(
        collection_plan,
        index_type=index_type,
        metric_type=metric_type,
        params=index_params,
    )
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=pymilvus_index_params,
    )


def insert_track_documents(
    client,
    collection_name: str,
    documents: Iterable[Mapping[str, Any]],
    batch_size: int = 128,
) -> int:
    """Insert Milvus documents in batches."""
    batch: list[Mapping[str, Any]] = []
    inserted = 0
    for document in documents:
        batch.append(document)
        if len(batch) >= batch_size:
            client.insert(collection_name=collection_name, data=batch)
            inserted += len(batch)
            batch = []
    if batch:
        client.insert(collection_name=collection_name, data=batch)
        inserted += len(batch)
    return inserted


def wait_for_collection_indexes(
    client,
    collection_name: str,
    index_names: Iterable[str] | None = None,
    timeout: float = 600.0,
    poll_interval: float = 1.0,
) -> None:
    """Block until the requested collection indexes finish building."""
    if index_names is None:
        index_names = client.list_indexes(collection_name=collection_name)
    index_names = list(index_names)
    if not index_names:
        return

    deadline = time.monotonic() + timeout
    while True:
        pending_indexes = []
        for index_name in index_names:
            description = client.describe_index(collection_name=collection_name, index_name=index_name)
            state = str(description.get("state", "")).lower()
            pending_rows = int(description.get("pending_index_rows", 0))
            if state != "finished" or pending_rows != 0:
                pending_indexes.append(index_name)
        if not pending_indexes:
            return
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Timed out waiting for Milvus indexes on {collection_name!r}: {pending_indexes}"
            )
        time.sleep(poll_interval)


def build_track_milvus_collection(
    collection_name: str = "music_track_catalog",
    milvus_uri: str = "http://localhost:19530",
    db_name: str = "default",
    token: str | None = None,
    metadata_dataset_name: str = TRACK_METADATA_DATASET,
    embeddings_dataset_name: str = TRACK_EMBEDDINGS_DATASET,
    split: str = TRACK_SPLIT,
    drop_existing: bool = False,
    batch_size: int = 128,
    index_type: str = DEFAULT_VECTOR_INDEX_TYPE,
    metric_type: str = DEFAULT_VECTOR_METRIC_TYPE,
    index_params: dict[str, Any] | None = None,
    index_build_timeout: float = 600.0,
) -> MilvusBuildSummary:
    """End-to-end helper to create and populate the Music CRS Milvus collection."""
    metadata_rows = load_track_metadata_rows(metadata_dataset_name, split)
    embedding_rows = load_track_embedding_rows(embeddings_dataset_name, split)
    collection_plan = build_track_collection_plan(metadata_rows, embedding_rows)
    client = connect_milvus(uri=milvus_uri, db_name=db_name, token=token)
    recreate_track_collection(
        client=client,
        collection_name=collection_name,
        collection_plan=collection_plan,
        drop_existing=drop_existing,
        index_type=index_type,
        metric_type=metric_type,
        index_params=index_params,
    )
    inserted_rows = insert_track_documents(
        client=client,
        collection_name=collection_name,
        documents=iter_track_documents(
            metadata_rows,
            embedding_rows,
            vector_dims=collection_plan.vector_dims,
        ),
        batch_size=batch_size,
    )
    client.flush(collection_name=collection_name)
    wait_for_collection_indexes(
        client=client,
        collection_name=collection_name,
        timeout=index_build_timeout,
    )
    client.load_collection(collection_name=collection_name)
    return MilvusBuildSummary(
        collection_name=collection_name,
        inserted_rows=inserted_rows,
        metadata_row_count=collection_plan.metadata_row_count,
        metadata_only_row_count=collection_plan.metadata_only_row_count,
        vector_field_names=collection_plan.vector_field_names,
        embedding_presence_counts=collection_plan.embedding_presence_counts,
    )
