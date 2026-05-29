# Milvus Module Group

## Purpose

This module group implements an **alternative vector store path** for the Music-CRS retrieval pipeline, using [Milvus](https://milvus.io/) as the backend instead of LanceDB (the current canonical store). It covers two concerns:

1. **Offline indexing** (`mcrs/milvus/indexing.py`): builds the 47k-track Milvus collection from HuggingFace datasets, infers the schema, constructs BM25 sparse fields and dense embedding fields, inserts rows in batches, and waits for indexes to become ready.
2. **Online retrieval** (`mcrs/retrieval_modules/milvus.py`): implements the `MILVUS_MODEL` retrieval class, which accepts a config-driven mix of BM25-sparse and dense ANN searches, fuses results with a `WeightedRanker`, and returns ranked `track_id` lists for each query.

In the pipeline, `MILVUS_MODEL` is instantiated by `mcrs/retrieval_modules/__init__.py:load_retrieval_module` when `retrieval_type == "milvus"`. It satisfies the same interface as `BM25_MODEL`, `BERT_MODEL`, and `LANCEDB_MODEL`.

---

## Files

| File | Responsibility |
|------|---------------|
| `mcrs/milvus/indexing.py` | Offline collection builder: schema inference, document assembly, index creation, batch insert, index-ready polling, and the end-to-end `build_track_milvus_collection` orchestrator. |
| `mcrs/retrieval_modules/milvus.py` | Online retrieval class `MILVUS_MODEL`: parses YAML/dict config, encodes queries (BM25 pass-through or dense transformer), issues single or hybrid Milvus searches, and returns ranked track IDs. |

---

## Public API

### `mcrs/milvus/indexing.py`

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `build_track_milvus_collection` | `(collection_name, milvus_uri, db_name, token, metadata_dataset_name, embeddings_dataset_name, split, drop_existing, batch_size, index_type, metric_type, index_params, index_build_timeout) -> MilvusBuildSummary` | End-to-end entry point: loads HF data, builds schema, creates collection, inserts all docs, flushes, waits for indexes. `indexing.py:644` |
| `build_track_collection_plan` | `(metadata_rows, embedding_rows) -> CollectionPlan` | Scans rows to infer VARCHAR lengths, ARRAY capacities, BM25 text lengths, and vector dims; returns a `CollectionPlan`. `indexing.py:261` |
| `build_track_document` | `(metadata_row, embedding_row, vector_dims) -> dict[str, Any]` | Merges one metadata row + one embedding row into a Milvus insert document; fills zero-vectors for tracks without embeddings. `indexing.py:226` |
| `iter_track_documents` | `(metadata_rows, embedding_rows, vector_dims) -> Iterable[dict]` | Yields one document per track, including metadata-only tracks (no embeddings). `indexing.py:525` |
| `build_vector_index_plan` | `(collection_plan, dense_index_type, dense_metric_type, dense_params, sparse_index_type, sparse_metric_type, sparse_params) -> list[dict]` | Returns raw index definition dicts for all dense and BM25-sparse fields. `indexing.py:409` |
| `recreate_track_collection` | `(client, collection_name, collection_plan, drop_existing, ...) -> None` | Drops (optionally) and creates the Milvus collection with schema and indexes. `indexing.py:560` |
| `insert_track_documents` | `(client, collection_name, documents, batch_size) -> int` | Batched insert; returns total inserted row count. `indexing.py:591` |
| `wait_for_collection_indexes` | `(client, collection_name, index_names, timeout, poll_interval) -> None` | Polls `describe_index` until all indexes report `state=finished` and `pending_index_rows=0`. `indexing.py:612` |
| `connect_milvus` | `(uri, db_name, token) -> MilvusClient` | Thin factory that instantiates `pymilvus.MilvusClient`. `indexing.py:547` |
| `create_pymilvus_schema` | `(collection_plan) -> schema` | Converts a `CollectionPlan` to a `pymilvus` schema object including BM25 functions. `indexing.py:466` |
| `create_pymilvus_index_params` | `(collection_plan, index_type, metric_type, params) -> index_params` | Converts a `CollectionPlan` to a `pymilvus` index-params object. `indexing.py:506` |
| `render_bm25_text_fields` | `(metadata_row) -> dict[str, str]` | Uses `load_corpus_formatter("default")` to produce the combined and per-field BM25 text strings for a single row. `indexing.py:213` |
| `milvus_safe_field_name` | `(name: str) -> str` | Normalizes a dataset column name to a Milvus-safe identifier (e.g. `"audio-laion_clap"` → `"audio_laion_clap"`). `indexing.py:133` |
| `resolve_bm25_combined_sparse_field` | `(corpus_fields: Iterable[str]) -> str` | Maps a tuple of corpus fields to the pre-defined combined sparse field name; raises on unknown combos. `indexing.py:176` |
| `has_embedding_field_name` | `(vector_field_name: str) -> str` | Returns the boolean presence-flag field name for a given vector field (e.g. `"has_audio_laion_clap"`). `indexing.py:144` |

### `mcrs/retrieval_modules/milvus.py`

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `MILVUS_MODEL` | `__init__(dataset_name, split_types, corpus_types, cache_dir, formatter, retrieval_config)` | Retrieval class. Parses config, connects to Milvus, loads dense encoders lazily. `milvus.py:156` |
| `MILVUS_MODEL.text_to_item_retrieval` | `(query: str, topk: int) -> list[str]` | Issues a single-field search or multi-field hybrid search; returns up to `topk` `track_id` strings. `milvus.py:348` |
| `MILVUS_MODEL.batch_text_to_item_retrieval` | `(queries: list[str], topk: int) -> list[list[str]]` | Loops `text_to_item_retrieval` over a batch of queries. `milvus.py:385` |

---

## Key Data Structures / Config

### Dataclasses in `mcrs/milvus/indexing.py`

| Class | Purpose |
|-------|---------|
| `CollectionFieldSpec` (line 87) | Frozen spec for a single Milvus field: name, datatype, nullable, primary, max_length, element_type, max_capacity, dim, analyzer flags. |
| `CollectionFunctionSpec` (line 101) | Frozen spec for a Milvus `Function` (e.g., BM25 text→sparse mapping): name, function_type_name, input/output field names, params. |
| `CollectionPlan` (line 111) | Full schema plan: list of `CollectionFieldSpec`, list of `CollectionFunctionSpec`, vector/sparse field name lists, inferred dims, and row counts. |
| `MilvusBuildSummary` (line 123) | Return value of `build_track_milvus_collection`: collection name, inserted row count, metadata row counts, vector field names, per-field embedding presence counts. |

### Internal search spec classes in `mcrs/retrieval_modules/milvus.py`

| Class | Purpose |
|-------|---------|
| `_Bm25CompatSearch` (line 30) | Parsed config for a combined BM25 sparse search over a fixed set of corpus fields. |
| `_Bm25FieldsSearch` (line 39) | Parsed config for per-field BM25 searches with individual field weights. |
| `_DenseSearch` (line 48) | Parsed config for a dense ANN search: vector field name, query encoder config dict, metric type. |
| `_SearchRequestSpec` (line 59) | Fully resolved search request ready for Milvus: `anns_field`, `data`, `search_params`, `limit`, `weight`, optional `filter`. |
| `_DenseQueryEncoder` (line 69) | HuggingFace-backed text encoder. Loaded once per unique `query_encoder` config via `_dense_encoder_cache`. Supports `mean`, `cls`, and `last_token` pooling. |

### Module-level constants in `indexing.py`

| Constant | Value / Purpose |
|----------|----------------|
| `EMBEDDING_FIELDS` (line 31) | The six embedding column names in the HF dataset: `audio-laion_clap`, `image-siglip2`, `cf-bpr`, `attributes-qwen3_embedding_0.6b`, `lyrics-qwen3_embedding_0.6b`, `metadata-qwen3_embedding_0.6b`. |
| `BM25_COMPAT_CORPUS_FIELDS` / `BM25_WITH_TAG_LIST_CORPUS_FIELDS` (lines 39–51) | Tuples defining the two supported combined-BM25 field profiles. |
| `BM25_EXPERIMENTAL_FIELDS` (line 52) | Fields eligible for per-field BM25 sparse indexes. |
| `BM25_COMBINED_CORPUS_FIELDS` (line 80) | `dict[tuple, str]` mapping each corpus-fields tuple to its combined text field name. Used by `resolve_bm25_combined_text_field`. |
| `DEFAULT_VECTOR_INDEX_TYPE` / `DEFAULT_VECTOR_METRIC_TYPE` (lines 63–64) | `"FLAT"` / `"COSINE"` — defaults for dense index creation. |
| `DEFAULT_SPARSE_VECTOR_INDEX_TYPE` / `DEFAULT_SPARSE_VECTOR_METRIC_TYPE` (lines 66–67) | `"SPARSE_INVERTED_INDEX"` / `"BM25"` — defaults for BM25 sparse index. |

### `retrieval_config` dict (used by `MILVUS_MODEL`)

Required keys:

```yaml
uri: "http://localhost:19530"
db_name: "default"
collection_name: "music_track_catalog"
fusion:
  method: "weighted"
searches:
  - name: "bm25_compat"
    kind: "bm25_compat"           # or "bm25_fields" or "dense"
    corpus_fields: ["track_name", "artist_name", "album_name", "release_date"]
    weight: 1.0
    topk: 100
  - name: "image_embed"
    kind: "dense"
    vector_field: "image_siglip2"
    weight: 0.5
    topk: 100
    metric_type: "COSINE"
    query_encoder:
      model_name: "..."
      pooling: "mean"
      query_template: "{query}"
      max_length: 512
      padding_side: "right"
```

Optional: `token` (Milvus auth token), `device` (default `"cpu"`).

---

## Internal Flow

### Offline index build (`build_track_milvus_collection`)

1. **Load data** (`load_track_metadata_rows`, `load_track_embedding_rows`) — fetches HF datasets `talkpl-ai/TalkPlayData-Challenge-Track-Metadata` and `talkpl-ai/TalkPlayData-Challenge-Track-Embeddings`, split `all_tracks`.
2. **Plan schema** (`build_track_collection_plan`) — iterates all metadata rows to measure max VARCHAR lengths, ARRAY capacities, and BM25 text sizes; iterates all embedding rows to discover vector dims and presence counts; returns a `CollectionPlan`.
3. **Connect** (`connect_milvus`) — creates `pymilvus.MilvusClient`.
4. **Create collection** (`recreate_track_collection`) — calls `create_pymilvus_schema` + `create_pymilvus_index_params` then `client.create_collection`.
5. **Insert** (`insert_track_documents` over `iter_track_documents`) — yields documents via `build_track_document` (which calls `render_bm25_text_fields` for BM25 text columns), batches them, and calls `client.insert`.  Tracks that have metadata but no embeddings receive zero-filled vectors and `has_<field>=False` flags.
6. **Flush + wait** — `client.flush` then `wait_for_collection_indexes` polls until `describe_index` reports all indexes finished.
7. **Load collection** — `client.load_collection` makes the collection queryable.

### Online retrieval (`MILVUS_MODEL.text_to_item_retrieval`)

1. **Build request specs** (`_build_request_specs`) — for each configured search:
   - `bm25_compat`: one `_SearchRequestSpec` pointing at the pre-built combined sparse field.
   - `bm25_fields`: one `_SearchRequestSpec` per named field, with combined weight = `search.weight * field.weight`.
   - `dense`: encodes `query` via the cached `_DenseQueryEncoder`; adds a `filter` clause `has_<field> == true` to exclude tracks with zero-padded vectors.
2. **Single vs hybrid dispatch**:
   - One spec → `client.search` (standard ANN search).
   - Multiple specs → `pymilvus.AnnSearchRequest` per spec + `WeightedRanker` + `client.hybrid_search`.
3. **Extract IDs** (`_extract_track_ids`) — handles three pymilvus result dict layouts (flat `track_id`, nested `entity.track_id`, or `id`) and returns the top `topk` strings.

---

## Dependencies

### Other `mcrs` modules

| Module | Usage |
|--------|-------|
| `mcrs.corpus_formatters` | `load_corpus_formatter("default")` is called in `render_bm25_text_fields` to produce BM25 text strings in the same format as the non-Milvus BM25 pipeline. |
| `mcrs.retrieval_modules.bert._resolve_torch_dtype` | Imported in `milvus.py:20` to normalize `torch_dtype` strings for the dense query encoder. |
| `mcrs.milvus.indexing` | Imported wholesale by `milvus.py` for field-name helpers and `connect_milvus`. |
| `mcrs.lancedb.indexing` | Imports `milvus_safe_field_name`, `EMBEDDING_FIELDS`, `build_track_document`, and related helpers from `mcrs.milvus.indexing` — the LanceDB indexer reuses the Milvus normalisation utilities. |
| `mcrs.lancedb.retriever` | Imports `milvus_safe_field_name` and `EMBEDDING_FIELDS` from `mcrs.milvus.indexing` to derive `LANCEDB_VECTOR_FIELDS`. |

### External libraries

| Library | Usage |
|---------|-------|
| `pymilvus` | `MilvusClient`, `DataType`, `Function`, `FunctionType`, `AnnSearchRequest`, `WeightedRanker`. Imported lazily at runtime; not required for import-time use of helpers. |
| `datasets` (HuggingFace) | `load_dataset` in `load_track_metadata_rows` / `load_track_embedding_rows`. |
| `transformers` | `AutoTokenizer`, `AutoModel` for the dense query encoder in `milvus.py`. |
| `torch` | Tensor ops and `torch.inference_mode` in `_DenseQueryEncoder.encode`. |

---

## Gotchas

1. **`pymilvus` is a soft dependency** — `_require_pymilvus()` (`indexing.py:456`) wraps the import and raises a friendly `ModuleNotFoundError`. All schema/document helpers in `indexing.py` are purely Python and work without `pymilvus` installed, but `create_pymilvus_schema`, `create_pymilvus_index_params`, `connect_milvus`, `recreate_track_collection`, `insert_track_documents`, and `wait_for_collection_indexes` will fail at runtime unless `pymilvus` is installed.

2. **`pymilvus` is also imported inline during `text_to_item_retrieval`** — the `AnnSearchRequest` / `WeightedRanker` import at `milvus.py:363` happens inside the method body only when `len(request_specs) > 1`. This avoids a module-level import failure but is inconsistent with the use of `connect_milvus` at `__init__` time.

3. **Zero-vector padding for tracks without embeddings** — metadata-only tracks (those absent from the embeddings dataset) get `[0.0] * dim` vectors and `has_<field>=False` booleans. Dense searches filter these out via `has_<field> == true` at query time. BM25 sparse searches return them normally, so result sets from different search branches may have different coverage.

4. **`corpus_types`, `cache_dir`, and `formatter` are silently ignored** — `MILVUS_MODEL.__init__` does `del corpus_types, cache_dir, formatter` (`milvus.py:166`). The Milvus path bypasses the local HF corpus entirely; all BM25 text is pre-built into the collection at index time.

5. **`_Bm25FieldsSearch` fan-out** — a single `bm25_fields` search config entry produces N separate `AnnSearchRequest` objects (one per named field). The effective search count can therefore exceed `len(searches)`, which matters for the Milvus hybrid-search `reqs` list length limit.

6. **`BM25_EXPERIMENTAL_FIELDS` == `BM25_WITH_TAG_LIST_CORPUS_FIELDS`** — the two tuples contain identical field names (`track_name`, `artist_name`, `album_name`, `release_date`, `tag_list`). The naming suggests `BM25_EXPERIMENTAL_FIELDS` was intended to evolve separately, but currently they are redundant.

7. **`milvus_safe_field_name` is used by the LanceDB module** — even though this function lives in `mcrs/milvus/indexing.py`, both `mcrs/lancedb/indexing.py` and `mcrs/lancedb/retriever.py` import it directly. It is effectively a shared utility, not Milvus-specific.

8. **This path is not used by any current experiment config** — the canonical retrieval backend is LanceDB (`v0plus_compiler_image_devset`, NDCG@20=0.146). The Milvus path is an alternative that must be provisioned separately with a running Milvus server.
