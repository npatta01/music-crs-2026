# LanceDB Indexing + Retrieval

## Purpose

`mcrs/lancedb/` is the vector store layer that backs all production (v0+) retrieval.
It owns two concerns:

1. **Index build** — loading HuggingFace track metadata and embedding datasets,
   merging them into a single flat table, pinning Arrow schema types, and creating
   full-text search (FTS) indexes with tantivy.
2. **Query path** — executing BM25/FTS and dense ANN searches against that table at
   CPU runtime, fusing ranked lists via weighted RRF, and exporting a clean
   Retriever Protocol that the v0+ compiler (`mcrs/qu_modules/compiler_v0plus_qu.py`)
   can call without knowing anything about LanceDB internals.

The third file, `modal_client.py`, is a thin RPC wrapper that lets local (CPU) code
call the same `LanceDbRetriever` logic running inside a Modal class service
(`ModalRetrievalService` in `modal/app.py`) without dealing with Modal SDK boilerplate.

**Pipeline position:**

```
HuggingFace datasets
        │
        ▼
 indexing.py  ──build_track_lancedb_table──▶  ./cache/lancedb/  (disk)
                                                      │
                                       ┌──────────────┴───────────────┐
                                       │ (local)                       │ (Modal)
                                       ▼                               ▼
                              retriever.py                    modal/app.py
                          LanceDbRetriever                 ModalRetrievalService
                                       │                               │
                                       │◀──── modal_client.py ─────────┘
                                       │      LanceDbModalClient
                                       ▼
                        mcrs/qu_modules/compiler_v0plus_qu.py
                        mcrs/retrieval_modules/lancedb.py (LANCEDB_MODEL)
                        mcrs/retrieval_modules/modal_lancedb.py (MODAL_LANCEDB_MODEL)
```

---

## Files

| File | Responsibility |
|------|---------------|
| `mcrs/lancedb/indexing.py` | Build the on-disk LanceDB table from HF datasets: record assembly, schema pinning, FTS index creation, manifest write. |
| `mcrs/lancedb/retriever.py` | CPU-only query layer: FTS (compat + bm25s), dense ANN, weighted RRF fusion; implements Retriever Protocol used by the v0+ compiler. |
| `mcrs/lancedb/modal_client.py` | Thin RPC client: wraps Modal SDK class lookup so local code can call `ModalRetrievalService.retrieve` / `retrieve_batch` / `embed_batch` without Modal boilerplate. |

---

## Public API

### `mcrs/lancedb/indexing.py`

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `build_track_lancedb_table` | `(db_uri, table_name, metadata_dataset_name, embeddings_dataset_name, split, include_embeddings, drop_existing, batch_size) -> LanceDbBuildSummary` | **Entry point for index build.** Loads HF datasets, batches records, creates/overwrites the LanceDB table with pinned Arrow schema, builds FTS indexes for all text fields, runs `table.optimize()`, and writes `manifest.json`. `indexing.py:231` |
| `build_track_record` | `(metadata_row, embedding_row, vector_dims, include_embeddings) -> dict` | Merge one metadata row + optional embedding row into a flat LanceDB record dict; handles BM25S tokenization. `indexing.py:125` |
| `iter_track_records` | `(metadata_rows, embedding_rows, vector_dims, include_embeddings) -> Iterator[dict]` | Yield records; metadata-only rows get zero-padded vectors (not omitted). `indexing.py:161` |
| `connect_lancedb` | `(uri: str) -> lancedb.DBConnection` | Open a LanceDB connection; raises `ModuleNotFoundError` with a helpful message if `lancedb` is not installed. `indexing.py:203` |
| `tokenize_bm25s_text` | `(text: str) -> str` | Run `bm25s.tokenize` and join tokens as whitespace-delimited string — used to pre-tokenize index fields for whitespace FTS indexes. `indexing.py:117` |
| `LanceDbBuildSummary` | `@dataclass(frozen=True)` | Returned by `build_track_lancedb_table`; also written to `manifest.json`. Fields: `db_uri`, `table_name`, `inserted_rows`, `metadata_row_count`, `metadata_only_row_count`, `include_embeddings`, `fts_text_fields`. `indexing.py:58` |

### `mcrs/lancedb/retriever.py`

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `LanceDbRetriever.__init__` | `(db_uri, table_name, searches, fusion, embedding_client, connect)` | Constructs from explicit keyword args; wraps `_init_from_config`. `retriever.py:119` |
| `LanceDbRetriever.from_retrieval_config` | `(cls, retrieval_config: dict, embedding_client, connect) -> LanceDbRetriever` | Preferred factory: builds from a YAML/dict retrieval config block. `retriever.py:139` |
| `LanceDbRetriever.text_to_item_retrieval` | `(query: str, topk: int) -> list[str]` | Declarative multi-search path: runs every configured search and fuses results via weighted RRF. Requires `searches` in config. `retriever.py:374` |
| `LanceDbRetriever.batch_text_to_item_retrieval` | `(queries: list[str], topk: int) -> list[list[str]]` | Loops `text_to_item_retrieval` over a batch. `retriever.py:441` |
| `LanceDbRetriever.retrieve` | `(query: str, topk: int) -> list[str]` | Alias for `text_to_item_retrieval`. `retriever.py:444` |
| `LanceDbRetriever.retrieve_batch` | `(queries: list[str], topk: int) -> list[list[str]]` | Alias for `batch_text_to_item_retrieval`. `retriever.py:447` |
| `LanceDbRetriever.search` | `(clauses: list[FieldQuery], *, topk: int) -> list[tuple[str, float]]` | **Retriever Protocol BM25 entry point.** Issues a single tantivy `BooleanQuery(SHOULD)` with per-clause `MatchQuery` boosts; returns `(track_id, score)` pairs. `retriever.py:469` |
| `LanceDbRetriever.search_embedding` | `(query_vector: list[float], *, vector_field: str, topk: int, distance_type: str, filter_missing: bool) -> list[tuple[str, float]]` | **Retriever Protocol dense ANN entry point.** Calls LanceDB vector search; converts distances to similarities (`cosine` → `1-d`, `l2` → `1/(1+d)`, `ip` → pass-through). `retriever.py:529` |
| `LanceDbRetriever.supported_text_fields` | `@property -> frozenset[str]` | Returns `BM25_EXPERIMENTAL_FIELDS` — the set of per-field BM25 columns the compiler may target. `retriever.py:461` |
| `LanceDbRetriever.supported_vector_fields` | `@property -> frozenset[str]` | Returns `LANCEDB_VECTOR_FIELDS` — sanitized names of all embedding columns. `retriever.py:465` |

### `mcrs/lancedb/modal_client.py`

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `LanceDbModalClient.__init__` | `(app_name: str, class_name: str = "ModalRetrievalService")` | Looks up the Modal class by app/class name via `modal.Cls.from_name` and keeps a handle. `modal_client.py:13` |
| `LanceDbModalClient.query` | `(query: str, topk: int, retrieval_config: dict | None) -> list[str]` | Single-query remote call to `ModalRetrievalService.retrieve`. `modal_client.py:19` |
| `LanceDbModalClient.query_batch` | `(queries: list[str], topk: int, retrieval_config: dict | None) -> list[list[str]]` | Batch remote call to `ModalRetrievalService.retrieve_batch`. `modal_client.py:27` |
| `LanceDbModalClient.embed_batch` | `(texts: list[str]) -> list[list[float]]` | Delegates to `ModalRetrievalService.embed_batch` — used when local code needs embeddings from the Modal-hosted embedding model. `modal_client.py:43` |

---

## Key data structures / config

### `LanceDbBuildSummary` (`indexing.py:58`)
Frozen dataclass capturing the outcome of one index build. Written verbatim to
`{db_uri}/manifest.json` via `json.dumps(asdict(...))`.

### Search spec dataclasses (`retriever.py:31–80`)
Four private frozen dataclasses parsed from the `searches` list in a retrieval config dict:

| Class | `kind` value | Description |
|-------|-------------|-------------|
| `_FtsCompatSearch` | `fts_compat` | FTS against a pre-tokenized combined text field (e.g. `bm25_compat_text`). |
| `_FtsBm25sCompatSearch` | `fts_bm25s_compat` | FTS against the bm25s-pre-tokenized variant (`bm25_compat_bm25s_tokens_text`), using a whitespace tokenizer FTS index so token weights exactly match the offline bm25s baseline. |
| `_FtsFieldsSearch` | `fts_fields` | FTS with per-field weights across any subset of `BM25_EXPERIMENTAL_FIELDS`. Expands to one `_SearchResultSet` per field internally. |
| `_DenseVectorSearch` | `dense_vector` | ANN against a named vector column, with optional `filter_missing` guard. |

### Retrieval config dict schema
Passed to `LanceDbRetriever.from_retrieval_config`:
```yaml
db_uri: "./cache/lancedb"
table_name: "music_track_catalog"
device: "cpu"           # only "cpu" is accepted
fusion:
  method: "weighted_rrf"
searches:               # optional for Retriever Protocol callers
  - name: "bm25_compat"
    kind: "fts_compat"
    corpus_fields: ["track_name", "artist_name", "album_name", "release_date"]
    weight: 1.0
    topk: 1000
  - name: "dense_siglip2"
    kind: "dense_vector"
    vector_field: "image_siglip2"
    distance_type: "cosine"
    filter_missing: true
    weight: 1.0
    topk: 1000
```

### FTS index constants (`indexing.py:32–55`)
- `BM25S_TOKENIZED_TEXT_FIELDS` — mapping from source text field → pre-tokenized
  counterpart, used to build `whitespace`-tokenizer FTS indexes that replicate
  offline bm25s scoring exactly.
- `BM25S_TOKENIZED_FTS_INDEX_OPTIONS` — LanceDB FTS options applied to bm25s-
  tokenized fields: `{"base_tokenizer": "whitespace", "lower_case": false, ...}`.
- `LANCEDB_FTS_TEXT_FIELDS` — full list of fields for which FTS indexes are built
  (9 fields total).

### `LANCEDB_VECTOR_FIELDS` (`retriever.py:27`)
`frozenset` of milvus-sanitized vector column names derived from `EMBEDDING_FIELDS`
in `mcrs/milvus/indexing.py`. Includes `audio_laion_clap`, `image_siglip2`, `cf_bpr`,
and the three qwen3 embedding columns.

---

## Internal flow

### Index build (`build_track_lancedb_table`)

1. Load all metadata rows from HF dataset `TRACK_METADATA_DATASET` via `load_track_metadata_rows` (delegated to `mcrs.milvus.indexing`). `indexing.py:247`
2. Optionally load embedding rows from `TRACK_EMBEDDINGS_DATASET` and call `build_track_collection_plan` to extract `vector_dims` and `metadata_only_row_count`. `indexing.py:252–255`
3. Call `connect_lancedb(db_path)` to open (or create) the database. `indexing.py:257`
4. Pipe metadata + embedding rows through `iter_track_records` → `_batched` to produce chunks of dicts. `indexing.py:258–266`
5. Take the first batch, build a `pa.Table` from it, then apply `_pin_schema` to force `release_date → date32` and all vector columns to `fixed_size_list<float32>[dim]`. Create the table with `db.create_table(..., mode="overwrite"|"create")`. `indexing.py:299–300`
6. Add remaining batches with the same schema cast. `indexing.py:302–305`
7. Build FTS indexes for all 9 fields in `LANCEDB_FTS_TEXT_FIELDS`; bm25s-tokenized fields get `BM25S_TOKENIZED_FTS_INDEX_OPTIONS` (whitespace tokenizer, no stemming/stop-words). `indexing.py:308–314`
8. Run `table.optimize()` to compact tantivy segments. `indexing.py:315`
9. Construct `LanceDbBuildSummary`, write it to `manifest.json`, and return. `indexing.py:317–327`

### Query path — declarative (`text_to_item_retrieval`)

1. Caller calls `text_to_item_retrieval(query, topk)`. `retriever.py:374`
2. For each parsed search spec in `self.searches`, dispatch to the appropriate private method and wrap the hits in a `_SearchResultSet(hits, weight)`. `retriever.py:381–430`
   - `_FtsCompatSearch` → `_fts_search` (LanceDB `query_type="fts"`, tantivy BM25). `retriever.py:329`
   - `_FtsBm25sCompatSearch` → `_fts_bm25s_search` (builds a `BooleanQuery` of `MatchQuery` with term-frequency boosts, whitespace-tokenizer field). `retriever.py:338`
   - `_FtsFieldsSearch` → one `_fts_search` call per field, each with its own per-field weight contribution. `retriever.py:406`
   - `_DenseVectorSearch` → `_embed_query` (calls `embedding_client.embed_batch`) then `_dense_vector_search`. `retriever.py:358`
3. If only one result set, return hits directly (preserves BM25 scores, no RRF overhead). `retriever.py:432–438`
4. Otherwise call `_weighted_rrf(result_sets, topk)` which applies `weight / (60 + rank)` per hit and sorts by descending score, tie-breaking by first-seen order. `retriever.py:82–96`

### Query path — Retriever Protocol (`search` / `search_embedding`)

Used by `compiler_v0plus_qu.py` directly instead of the declarative path above.

1. `search(clauses, topk)` builds one `BooleanQuery(SHOULD)` from all non-empty `FieldQuery` clauses, mapping each to a `MatchQuery(text, bm25_text_field_name(field), boost=boost)`. Issues a single tantivy FTS call. Returns `(track_id, score)` pairs. `retriever.py:469`
2. `search_embedding(query_vector, vector_field, topk, distance_type, filter_missing)` runs an ANN query and converts the raw distance to a similarity score via `_distance_to_similarity`. Returns `(track_id, similarity)` pairs. `retriever.py:529`
3. Cross-modal fusion between the two lists is the **compiler's responsibility**, not the retriever's.

### Modal remote path (`LanceDbModalClient`)

1. On construction, resolves the Modal class via `modal.Cls.from_name(app_name, class_name)` and instantiates it. `modal_client.py:16–17`
2. `query` / `query_batch` call `self._service.retrieve.remote(...)` / `retrieve_batch.remote(...)`, forwarding an optional `retrieval_config` override dict. `modal_client.py:24–38`
3. On the Modal side, `ModalRetrievalService.setup()` constructs a `LanceDbRetriever` from a default config (with an optional `LiteLLMEmbeddingClient`), so the same retriever code executes on both local and remote paths. `modal/app.py:344–367`

---

## Dependencies

### Internal (`mcrs/`)
| Import | Used for |
|--------|---------|
| `mcrs.milvus.indexing` | `ARRAY_METADATA_FIELDS`, `EMBEDDING_FIELDS`, `BM25_EXPERIMENTAL_FIELDS`, `SCALAR_METADATA_FIELDS`, `build_track_collection_plan`, `has_embedding_field_name`, `load_track_metadata_rows`, `load_track_embedding_rows`, `milvus_safe_field_name`, `render_bm25_text_fields`, `resolve_bm25_combined_text_field`, `bm25_text_field_name`, dataset/split constants. |
| `mcrs.retrieval_modules.base` | `FieldQuery` dataclass (Retriever Protocol). |

### External
| Library | Usage |
|---------|-------|
| `lancedb` | Table create/open, FTS + vector search, `BooleanQuery`, `MatchQuery`, `Occur`. |
| `pyarrow` | Schema pinning (`pa.date32()`, `pa.list_(pa.float32(), dim)`), batch casting. |
| `bm25s` | Tokenization for `tokenize_bm25s_text` and `_bm25s_query_object`. |
| `modal` | `modal.Cls.from_name` for remote class lookup in `modal_client.py`. |
| `datasets` (HuggingFace) | Dataset loading inside `mcrs.milvus.indexing` helpers. |

---

## Gotchas

1. **Schema pinning is critical for ANN indexability** (`indexing.py:272–298`). PyArrow infers embedding columns from Python `list[float]` as `list<double>` (variable-length), which LanceDB cannot index for ANN. The `_pin_schema` inner function forces all vector columns to `fixed_size_list<float32>[dim]`. This also halves on-disk size vs. `double`. The `release_date` column is pinned to `date32` because an all-null first batch would otherwise be typed as `null`, causing schema mismatch on subsequent batches.

2. **Metadata-only tracks get zero-padded vectors** (`indexing.py:193–200`, `retriever.py:364–365`). Tracks without embeddings receive a zero vector in every embedding column, and a companion boolean field `has_{field_name}` is set to `False`. Dense searches use `.where(f"{has_embedding_field_name(...)} = true")` to skip these, avoiding spurious ANN results. This means a `filter_missing=false` config will surface zero-vector tracks.

3. **Two distinct query APIs coexist** in `LanceDbRetriever`:
   - **Declarative** (`text_to_item_retrieval` / `retrieve`): driven by the `searches` list in the config; caller passes a raw query string. Intended for the legacy CRS pipeline (`LANCEDB_MODEL`).
   - **Retriever Protocol** (`search` / `search_embedding`): no `searches` config needed; caller passes typed `FieldQuery` clauses and pre-computed vectors. Intended for the v0+ compiler. Mixing them in the same instance is fine; the `searches` field defaults to `()` when absent.

4. **`fts_bm25s_compat` replicates bm25s offline scores exactly** by pre-tokenizing the corpus at index time and using a whitespace-only FTS index. The index-time tokenizer (`tokenize_bm25s_text`, `indexing.py:117`) and the query-time token counter (`_bm25s_query_object`, `retriever.py:288`) must stay in sync with the offline `bm25s` baseline; any bm25s version upgrade risks score drift.

5. **`LANCEDB_VECTOR_FIELDS` is derived from `EMBEDDING_FIELDS`** at module load (`retriever.py:27`). `_NON_EMBEDDING_VECTOR_COLUMNS` in `v0plus_catalog_lance.py` (`cf_bpr`, `audio_laion_clap`, `image_siglip2`) are special-cased because their HF source names contain hyphens that `milvus_safe_field_name` converts to underscores — verify the sanitized names match if adding new columns.

6. **`LanceDbModalClient` is only needed for the legacy `MODAL_LANCEDB_MODEL` wrapper** (`mcrs/retrieval_modules/modal_lancedb.py`). The v0+ compiler's `compiler_v0plus_qu.py` uses `LanceDbRetriever` directly (local) or wraps it in a `RetrievalService`; it does not use `LanceDbModalClient`.

7. **`LANCEDB_MODEL` in `mcrs/retrieval_modules/lancedb.py`** silently ignores `dataset_name`, `split_types`, `corpus_types`, `cache_dir`, and `formatter` constructor arguments (`lancedb.py:21`). These are required by the CRS loader interface but meaningless for LanceDB — callers must pass `retrieval_config` instead.
