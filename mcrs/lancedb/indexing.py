"""Build a local LanceDB track catalog for CPU retrieval experiments."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from mcrs.milvus.indexing import (
    ARRAY_METADATA_FIELDS,
    BM25_COMPAT_TEXT_FIELD,
    BM25_WITH_TAG_LIST_TEXT_FIELD,
    BM25_EXPERIMENTAL_FIELDS,
    EMBEDDING_FIELDS,
    SCALAR_METADATA_FIELDS,
    TRACK_EMBEDDINGS_DATASET,
    TRACK_METADATA_DATASET,
    TRACK_SPLIT,
    build_track_collection_plan,
    has_embedding_field_name,
    load_track_embedding_rows,
    load_track_metadata_rows,
    milvus_safe_field_name,
    render_bm25_text_fields,
)

DEFAULT_LANCEDB_TABLE_NAME = "music_track_catalog"
DEFAULT_LANCEDB_URI = "./cache/lancedb"
DEFAULT_MANIFEST_NAME = "manifest.json"
BM25_COMPAT_BM25S_TOKENIZED_TEXT_FIELD = "bm25_compat_bm25s_tokens_text"
BM25_WITH_TAG_LIST_BM25S_TOKENIZED_TEXT_FIELD = "bm25_with_tag_list_bm25s_tokens_text"
BM25S_TOKENIZED_TEXT_FIELDS = {
    BM25_COMPAT_TEXT_FIELD: BM25_COMPAT_BM25S_TOKENIZED_TEXT_FIELD,
    BM25_WITH_TAG_LIST_TEXT_FIELD: BM25_WITH_TAG_LIST_BM25S_TOKENIZED_TEXT_FIELD,
}
BM25S_TOKENIZED_FTS_INDEX_OPTIONS = {
    "base_tokenizer": "whitespace",
    "lower_case": False,
    "stem": False,
    "remove_stop_words": False,
    "ascii_folding": False,
}
LANCEDB_FTS_TEXT_FIELDS = (
    BM25_COMPAT_TEXT_FIELD,
    BM25_COMPAT_BM25S_TOKENIZED_TEXT_FIELD,
    BM25_WITH_TAG_LIST_TEXT_FIELD,
    BM25_WITH_TAG_LIST_BM25S_TOKENIZED_TEXT_FIELD,
    "track_name_text",
    "artist_name_text",
    "album_name_text",
    "release_date_text",
    "tag_list_text",
)


@dataclass(frozen=True)
class LanceDbBuildSummary:
    db_uri: str
    table_name: str
    inserted_rows: int
    metadata_row_count: int
    metadata_only_row_count: int
    include_embeddings: bool
    fts_text_fields: list[str]


def _parse_iso_date(value):
    """Parse YYYY-MM-DD into datetime.date; return None for None / empty / malformed input.

    Indexing is strict — partial dates ("2016", "2016-06") are NOT expanded here.
    The Pydantic HardFilter validator expands partial dates on the filter side; the
    catalog itself should only store fully-qualified dates.
    """
    from datetime import date
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


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


def tokenize_bm25s_text(text: str) -> str:
    """Render text as the same token stream used by the direct bm25s baseline."""
    import bm25s

    tokens = bm25s.tokenize([text], return_ids=False, show_progress=False)[0]
    return " ".join(tokens)


def build_track_record(
    metadata_row: Mapping[str, Any],
    embedding_row: Mapping[str, Any] | None = None,
    vector_dims: Mapping[str, int] | None = None,
    include_embeddings: bool = True,
) -> dict[str, Any]:
    """Merge one metadata row and optional embedding row into a LanceDB record."""
    record: dict[str, Any] = {"track_id": str(metadata_row["track_id"])}

    for field_name in ARRAY_METADATA_FIELDS:
        record[field_name] = _normalize_string_list(metadata_row.get(field_name))
    record["popularity"] = _normalize_optional_float(metadata_row.get("popularity"))
    record["release_date"] = _parse_iso_date(metadata_row.get("release_date"))
    record["duration"] = _normalize_optional_int(metadata_row.get("duration"))
    bm25_text_fields = render_bm25_text_fields(metadata_row)
    record.update(bm25_text_fields)
    for source_field, tokenized_field in BM25S_TOKENIZED_TEXT_FIELDS.items():
        record[tokenized_field] = tokenize_bm25s_text(bm25_text_fields[source_field])

    if not include_embeddings:
        return record

    for raw_name in EMBEDDING_FIELDS:
        field_name = milvus_safe_field_name(raw_name)
        vector = None if embedding_row is None else _normalize_embedding(embedding_row.get(raw_name))
        has_vector = vector is not None
        if vector is None:
            if vector_dims is None or field_name not in vector_dims:
                raise ValueError(f"Missing inferred dimension for vector field {field_name}")
            vector = [0.0] * vector_dims[field_name]
        record[field_name] = vector
        record[has_embedding_field_name(field_name)] = has_vector

    return record


def iter_track_records(
    metadata_rows: Iterable[Mapping[str, Any]],
    embedding_rows: Iterable[Mapping[str, Any]] | None = None,
    vector_dims: Mapping[str, int] | None = None,
    include_embeddings: bool = False,
):
    """Yield LanceDB records, preserving metadata-only rows."""
    metadata_map = {str(row["track_id"]): row for row in metadata_rows}
    if not include_embeddings:
        for metadata_row in metadata_map.values():
            yield build_track_record(metadata_row, include_embeddings=False)
        return

    if embedding_rows is None:
        raise ValueError("embedding_rows are required when include_embeddings=True")
    if vector_dims is None:
        raise ValueError("vector_dims are required when include_embeddings=True")

    seen_track_ids = set()
    for embedding_row in embedding_rows:
        track_id = str(embedding_row["track_id"])
        metadata_row = metadata_map.get(track_id)
        if metadata_row is None:
            raise KeyError(f"Embedding row {track_id} has no matching metadata row.")
        seen_track_ids.add(track_id)
        yield build_track_record(
            metadata_row,
            embedding_row,
            vector_dims=vector_dims,
            include_embeddings=True,
        )

    for track_id, metadata_row in metadata_map.items():
        if track_id not in seen_track_ids:
            yield build_track_record(
                metadata_row,
                embedding_row=None,
                vector_dims=vector_dims,
                include_embeddings=True,
            )


def connect_lancedb(uri: str):
    """Open a LanceDB database at a local path or LanceDB URI."""
    try:
        import lancedb
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in real envs
        raise ModuleNotFoundError(
            "lancedb is required for LanceDB indexing. Install the project dependencies first."
        ) from exc
    return lancedb.connect(uri)


def _batched(records: Iterable[Mapping[str, Any]], batch_size: int):
    batch = []
    for record in records:
        batch.append(dict(record))
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _write_manifest(db_uri: str, summary: LanceDbBuildSummary) -> None:
    path = Path(db_uri) / DEFAULT_MANIFEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")


def build_track_lancedb_table(
    db_uri: str = DEFAULT_LANCEDB_URI,
    table_name: str = DEFAULT_LANCEDB_TABLE_NAME,
    metadata_dataset_name: str = TRACK_METADATA_DATASET,
    embeddings_dataset_name: str = TRACK_EMBEDDINGS_DATASET,
    split: str = TRACK_SPLIT,
    include_embeddings: bool = True,
    drop_existing: bool = False,
    batch_size: int = 1024,
) -> LanceDbBuildSummary:
    """Build a local LanceDB table and FTS indexes for the track catalog."""
    db_path = Path(db_uri)
    if drop_existing and db_path.exists():
        shutil.rmtree(db_path)
    db_path.mkdir(parents=True, exist_ok=True)

    metadata_rows = list(load_track_metadata_rows(metadata_dataset_name, split))
    embedding_rows = None
    vector_dims = None
    metadata_only_row_count = 0
    if include_embeddings:
        embedding_rows = list(load_track_embedding_rows(embeddings_dataset_name, split))
        plan = build_track_collection_plan(metadata_rows, embedding_rows)
        vector_dims = plan.vector_dims
        metadata_only_row_count = plan.metadata_only_row_count

    db = connect_lancedb(str(db_path))
    batches = _batched(
        iter_track_records(
            metadata_rows,
            embedding_rows=embedding_rows,
            vector_dims=vector_dims,
            include_embeddings=include_embeddings,
        ),
        batch_size=batch_size,
    )
    first_batch = next(batches, None)
    if first_batch is None:
        raise ValueError("No metadata rows available for LanceDB build")

    mode = "overwrite" if drop_existing else "create"
    # Pin the `release_date` column type to `date32` regardless of what
    # pyarrow infers from the first batch. PyArrow's normal inference picks
    # the right type when the batch has at least one non-null `datetime.date`,
    # but if a batch happens to be all-null (low-density data, small
    # batch_size, or null-first ordering) it would infer `null` and every
    # subsequent batch with real dates would fail with a schema mismatch.
    # An explicit cast on the first batch removes that fragility.
    import pyarrow as pa
    first_arrow = pa.Table.from_pylist(first_batch)
    if "release_date" in first_arrow.schema.names:
        target_schema = pa.schema([
            f.with_type(pa.date32()) if f.name == "release_date" else f
            for f in first_arrow.schema
        ])
        first_arrow = first_arrow.cast(target_schema)
    table = db.create_table(table_name, data=first_arrow, mode=mode)
    inserted_rows = len(first_batch)
    for batch in batches:
        table.add(batch)
        inserted_rows += len(batch)

    for text_field in LANCEDB_FTS_TEXT_FIELDS:
        index_options = (
            BM25S_TOKENIZED_FTS_INDEX_OPTIONS
            if text_field in BM25S_TOKENIZED_TEXT_FIELDS.values()
            else {}
        )
        table.create_fts_index(text_field, replace=True, **index_options)
    table.optimize()

    summary = LanceDbBuildSummary(
        db_uri=str(db_path),
        table_name=table_name,
        inserted_rows=inserted_rows,
        metadata_row_count=len(metadata_rows),
        metadata_only_row_count=metadata_only_row_count,
        include_embeddings=include_embeddings,
        fts_text_fields=list(LANCEDB_FTS_TEXT_FIELDS),
    )
    _write_manifest(str(db_path), summary)
    return summary
