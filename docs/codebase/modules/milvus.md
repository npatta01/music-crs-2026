# Milvus Indexing Helpers (LanceDB dependency)

## Purpose

`mcrs/milvus/indexing.py` is a legacy-named module: it was originally built as
the offline collection builder for a standalone Milvus retrieval backend. That
backend (`mcrs/retrieval_modules/milvus.py`, the `MILVUS_MODEL` retrieval
class, and `retrieval_type: "milvus"` configs) was **removed** — it was
unreachable from any active competition config, since v10 state-ranker configs
use LanceDB inside the full-pipeline QU and never instantiate standalone
retrieval modules.

This file itself was **not** removed, because a handful of its field-naming
helpers and constants are genuinely load-bearing for the current LanceDB path:

- `mcrs/lancedb/indexing.py` imports `milvus_safe_field_name`,
  `EMBEDDING_FIELDS`, `build_track_document`, and related helpers.
- `mcrs/lancedb/retriever.py` imports `milvus_safe_field_name` and
  `EMBEDDING_FIELDS` to derive `LANCEDB_VECTOR_FIELDS`.
- `modal/app.py`'s `_default_lancedb_retrieval_config` imports
  `BM25_WITH_TAG_LIST_CORPUS_FIELDS`.

The rest of the file — actual `pymilvus` collection/schema/index creation
(`build_track_milvus_collection`, `create_pymilvus_schema`,
`create_pymilvus_index_params`, `connect_milvus`, `recreate_track_collection`,
`insert_track_documents`, `wait_for_collection_indexes`) — is dead code from
the removed backend, kept as-is rather than excised mid-file to avoid
disturbing the still-used constants/helpers above it. `pymilvus` stays a
listed dependency for this reason; it is not imported at module level (see
Gotchas below), so it costs nothing at import time even though it's unused in
the current submission.

---

## Files

| File | Responsibility |
|------|---------------|
| `mcrs/milvus/indexing.py` | Field-naming helpers/constants used by the active LanceDB path, plus unused `pymilvus` collection-building code from the removed Milvus retrieval backend. |

---

## Public API actually used by the active pipeline

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `milvus_safe_field_name` | `(name: str) -> str` | Normalizes a dataset column name to a Milvus-safe identifier (e.g. `"audio-laion_clap"` → `"audio_laion_clap"`). Reused by `mcrs/lancedb/*` for LanceDB column naming. `indexing.py:133` |
| `EMBEDDING_FIELDS` | constant | The six embedding column names in the HF dataset: `audio-laion_clap`, `image-siglip2`, `cf-bpr`, `attributes-qwen3_embedding_0.6b`, `lyrics-qwen3_embedding_0.6b`, `metadata-qwen3_embedding_0.6b`. |
| `build_track_document` | `(metadata_row, embedding_row, vector_dims) -> dict[str, Any]` | Merges one metadata row + one embedding row into an insert document; fills zero-vectors for tracks without embeddings. Reused by `mcrs/lancedb/indexing.py`. `indexing.py:226` |
| `BM25_WITH_TAG_LIST_CORPUS_FIELDS` | constant | Tuple defining a combined-BM25 field profile, used by `modal/app.py`'s default LanceDB retrieval config. |

The rest of the file's public API (schema/collection-plan builders, `pymilvus`
schema/index/insert functions) is unused dead code from the removed retrieval
backend — not documented further here.

---

## Gotchas

1. **`pymilvus` is a soft dependency** — `_require_pymilvus()` (`indexing.py`)
   wraps the import and raises a friendly `ModuleNotFoundError`. All the
   field-naming helpers above are purely Python and work without `pymilvus`
   installed; only the (now-unused) schema/collection-building functions need
   it, and it's imported lazily inside those functions, not at module level.
2. **`milvus_safe_field_name` is used by the LanceDB module** — even though
   this function lives in `mcrs/milvus/indexing.py`, both
   `mcrs/lancedb/indexing.py` and `mcrs/lancedb/retriever.py` import it
   directly. It is effectively a shared utility, not Milvus-specific — the
   module name is a naming artifact from before the LanceDB migration.
