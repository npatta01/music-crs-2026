# Retrieval Modules

## Purpose

`mcrs/retrieval_modules/` contains pluggable retrieval backends that turn a text query into a ranked list of track IDs from the 47k-track catalog. These are retained for tests, historical baselines, and alternative tooling. Current competition inference goes through the v10 full-pipeline QU, which uses the v0+ Retriever Protocol directly instead of having `CRS_BASELINE` instantiate one of these standalone modules.

There are two distinct generations of interface in this group:

- **Legacy standalone interface** (`text_to_item_retrieval` / `batch_text_to_item_retrieval`): exposed by each concrete class for historical baselines and tools.
- **v0+ Retriever Protocol** (`search` / `search_embedding` with `FieldQuery` clauses): defined in `base.py`, implemented by `mcrs/lancedb/retriever.py::LanceDbRetriever`. The v0+ compiler (`mcrs/qu_modules/compiler_v0plus.py`) uses only this protocol.

The factory function `load_retrieval_module` (in `__init__.py`) still selects and instantiates a backend by string key for tests/tooling. It is no longer called by `CRS_BASELINE`.

---

## Files

| File | Responsibility |
|---|---|
| `base.py` | Defines the `Retriever` Protocol and `FieldQuery` dataclass — the shared v0+ interface that compiler-facing backends must satisfy. |
| `__init__.py` | `load_retrieval_module` factory: maps string keys (`"bert"`, `"dense_transformer"`, `"litellm_embedding"`, `"lancedb"`, `"modal_lancedb"`) to concrete backend constructors. The old standalone `"bm25"` backend was removed; the `"milvus"` backend (`MILVUS_MODEL`) was removed as unreachable dead code — see [Milvus indexing helpers](milvus.md) for what remains. |
| `bert.py` | `DENSE_TRANSFORMER_MODEL` + `BERT_MODEL` alias: on-device dense retrieval; encodes all tracks once and persists a `.pt` embedding matrix; cosine-searches at query time. Configurable pooling (mean / cls / last_token), query template, dtype. |
| `litellm_embedding.py` | `LITELLM_EMBEDDING_MODEL`: same index-and-search pattern as `DENSE_TRANSFORMER_MODEL` but uses a LiteLLM proxy (OpenAI-compatible endpoint) for embedding instead of a local transformer. Uses async concurrency for corpus indexing. |
| `lancedb.py` | `LANCEDB_MODEL`: thin wrapper that ignores legacy constructor arguments (`dataset_name`, `split_types`, etc.) and delegates to `mcrs.lancedb.retriever.LanceDbRetriever`. |
| `modal_lancedb.py` | `MODAL_LANCEDB_MODEL`: thin wrapper that delegates to `mcrs.lancedb.modal_client.LanceDbModalClient`, issuing retrieval RPCs to a Modal-hosted service rather than running locally. |

---

## Public API

### `base.py`

```python
@dataclass(frozen=True)
class FieldQuery:          # base.py:34
    field: str
    query: str
    boost: float = 1.0
```
One field-targeted BM25 clause for the v0+ Retriever Protocol. Validates all three fields in `__post_init__`. Used by both the v0+ compiler (`compiler_v0plus.py`) and tests.

```python
@runtime_checkable
class Retriever(Protocol):  # base.py:61
    supported_text_fields: frozenset[str]   # property
    supported_vector_fields: frozenset[str] # property

    def search(
        self,
        clauses: list[FieldQuery],
        *,
        topk: int = 1000,
    ) -> list[tuple[str, float]]: ...        # base.py:74

    def search_embedding(
        self,
        query_vector: list[float],
        *,
        vector_field: str,
        topk: int = 1000,
        distance_type: str = "cosine",
        filter_missing: bool = True,
    ) -> list[tuple[str, float]]: ...        # base.py:93
```
Protocol that the v0+ compiler binds against. `search` is for BM25/FTS; `search_embedding` is for dense ANN with a caller-supplied vector (so the compiler can pre-mix centroids). Scores are always higher-is-better — backends convert distances internally.

### `__init__.py`

```python
def load_retrieval_module(
    retrieval_type: str,
    dataset_name: str,
    track_split_types: list[str],
    corpus_types: list[str] = ["track_name", "artist_name", "album_name"],
    cache_dir: str = "./cache",
    formatter=None,
    retrieval_config: dict | None = None,
) -> Any:   # __init__.py:4
```
Factory for historical standalone retriever paths. Returns a concrete model object exposing `text_to_item_retrieval` and `batch_text_to_item_retrieval`. Deferred imports are used for `lancedb` and `modal_lancedb` so their heavy dependencies are only loaded when the corresponding key is requested.

### `bert.py`

```python
class DENSE_TRANSFORMER_MODEL:   # bert.py:42
    def text_to_item_retrieval(self, query: str, topk: int) -> list[str]:         # bert.py:227
    def batch_text_to_item_retrieval(self, queries: list[str], topk: int) -> list[list[str]]:  # bert.py:235

class BERT_MODEL(DENSE_TRANSFORMER_MODEL):   # bert.py:247
```
`BERT_MODEL` is a backward-compatible subclass that hard-codes `torch_dtype="float32"` as its default. `DENSE_TRANSFORMER_MODEL` is the configurable class that all new code should use. Cache path is content-addressed via a SHA1 of template strings.

### `litellm_embedding.py`

```python
class LITELLM_EMBEDDING_MODEL:   # litellm_embedding.py:25
    def text_to_item_retrieval(self, query: str, topk: int) -> list[str]:         # litellm_embedding.py:190
    def batch_text_to_item_retrieval(self, queries: list[str], topk: int) -> list[list[str]]:  # litellm_embedding.py:198
```
Reads `LITELLM_PROXY_BASE` / `LITELLM_PROXY_KEY` env vars (or constructor args). Corpus indexing uses async batched embedding with a configurable `concurrency` semaphore.

### `lancedb.py`

```python
class LANCEDB_MODEL:   # lancedb.py:10
    def text_to_item_retrieval(self, query: str, topk: int) -> list[str]:         # lancedb.py:27
    def batch_text_to_item_retrieval(self, queries: list[str], topk: int) -> list[list[str]]:  # lancedb.py:30
```
Pass-through wrapper; all arguments except `retrieval_config` are silently discarded (`del dataset_name, split_types, ...`).

### `modal_lancedb.py`

```python
class MODAL_LANCEDB_MODEL:   # modal_lancedb.py:8
    def text_to_item_retrieval(self, query: str, topk: int) -> list[str]:         # modal_lancedb.py:31
    def batch_text_to_item_retrieval(self, queries: list[str], topk: int) -> list[list[str]]:  # modal_lancedb.py:34
```
Reads `app_name` and `class_name` from `retrieval_config` (defaults: `"music-crs"` / `"ModalRetrievalService"`); remaining keys are forwarded as `retrieval_config` to the Modal RPC.

---

## Key Data Structures / Config

### `FieldQuery` (`base.py:34`)
Frozen dataclass with `field: str`, `query: str`, `boost: float`. Built by the v0+ compiler's `_build_bm25_clauses` method and passed as a list to `Retriever.search`.

### `retrieval_config` dict
All backends except `bm25` and `bert`/`dense_transformer` accept a `retrieval_config: dict` to pass backend-specific settings. Notable sub-keys:

- **LanceDB**: `db_uri`, `table_name`, `fusion.method` (must be `"weighted_rrf"`), `searches` list. Each search entry has `name`, `kind` (`fts_compat` | `fts_bm25s_compat` | `fts_fields` | `dense_vector`), `weight`, `topk`, and kind-specific keys.
- **Modal LanceDB**: `app_name`, `class_name`, plus any keys forwarded to the remote service's `retrieval_config`.
- **LiteLLM**: `model_name`, `api_base`, `api_key`, `embedding_query_prefix`, `embedding_passage_prefix`, `batch_size`, `concurrency`, `dimensions`.

### Internal search-spec dataclasses (`mcrs/lancedb/retriever.py`)
Uses private frozen dataclasses (`_FtsCompatSearch`, `_DenseVectorSearch`, etc.) to represent parsed search entries. These are only used internally; callers interact only through `retrieval_config`.

### Dense index on-disk format (`bert.py`, `litellm_embedding.py`)
`{cache_dir}/dense/{model_name}/{index_name}/embeddings.pt` (L2-normalized `torch.Tensor`, shape `[N, D]`), plus `track_ids.json` and `config.json`. The index name is derived from corpus type, pooling, dtype, and a 12-char SHA1 of template strings so layout changes automatically invalidate the cache.

---

## Internal Flow

### Standalone retriever path (`load_retrieval_module`)

1. A test or tooling caller invokes `load_retrieval_module(retrieval_type, ...)`.
2. The factory matches the key and constructs the concrete class, forwarding `dataset_name`, `track_split_types`, `corpus_types`, `cache_dir`, `formatter`, and `retrieval_config`.
3. The caller invokes `text_to_item_retrieval(query, topk)` or `batch_text_to_item_retrieval(queries, topk)` on the returned model.
4. `DENSE_TRANSFORMER_MODEL`/`LITELLM_EMBEDDING_MODEL`: encodes the query, computes `torch.matmul(embeddings, query_emb)`, returns `topk` indices.
5. `LANCEDB_MODEL`/`MODAL_LANCEDB_MODEL`: delegate immediately to `LanceDbRetriever.retrieve` or `LanceDbModalClient.query`.

### v0+ Compiler path (`compiler_v0plus.py` → `Retriever` Protocol)

1. `V0PlusCompiler.__init__` receives a `retriever: Retriever` (always a `LanceDbRetriever` instance in practice) and introspects `supported_text_fields` / `supported_vector_fields` at construction time.
2. Per turn, `compile(state, ...)` calls:
   - `retriever.search(bm25_clauses, topk=cfg.bm25_k)` — one call passing all `FieldQuery` clauses; `LanceDbRetriever.search` builds a single tantivy `BooleanQuery(SHOULD, [MatchQuery per clause])` with per-field boost.
   - `retriever.search_embedding(query_vector, vector_field=..., topk=...)` — one call per enabled dense branch; caller pre-computes or mixes centroids before calling.
3. `LanceDbRetriever.search_embedding` converts the native LanceDB `_distance` to a similarity score via `_distance_to_similarity` before returning.
4. Cross-modal RRF fusion of BM25 and dense hit lists is done by the compiler, not the retriever.

---

## Dependencies

### Within `mcrs`
- `mcrs.corpus_formatters.load_corpus_formatter` — used by `DENSE_TRANSFORMER_MODEL` and `LITELLM_EMBEDDING_MODEL` to format track metadata into corpus strings.
- `mcrs.lancedb.retriever.LanceDbRetriever` — the actual implementation behind `LANCEDB_MODEL`.
- `mcrs.lancedb.modal_client.LanceDbModalClient` — the Modal RPC client behind `MODAL_LANCEDB_MODEL`.
- `mcrs.lancedb.indexing` — `connect_lancedb`, field-name constants, used inside `LanceDbRetriever`.
- `mcrs.milvus.indexing` — legacy-named module; `LanceDbRetriever` and `mcrs/lancedb/indexing.py` reuse its `milvus_safe_field_name`/`EMBEDDING_FIELDS`/`build_track_document` helpers. See [Milvus indexing helpers](milvus.md).

### External libraries
| Library | Used by |
|---|---|
| `bm25s` | `lancedb/retriever.py` (bm25s tokenization for `fts_bm25s_compat` kind) |
| `datasets` (HuggingFace) | `bert.py`, `litellm_embedding.py` for catalog loading |
| `torch`, `transformers` | `bert.py` |
| `litellm` | `litellm_embedding.py` |
| `lancedb` | `lancedb/retriever.py` (`BooleanQuery`, `MatchQuery`, `Occur`) |

---

## Gotchas

1. **Two separate interfaces coexist.** The standalone `text_to_item_retrieval` / `batch_text_to_item_retrieval` interface is what `load_retrieval_module` returns. The v0+ `Retriever` Protocol (`search` / `search_embedding`) is used by the v0+ compiler and is implemented by `LanceDbRetriever` — none of `DENSE_TRANSFORMER_MODEL`, `LITELLM_EMBEDDING_MODEL`, etc. satisfy it.

2. **`LANCEDB_MODEL` and `MODAL_LANCEDB_MODEL` silently discard constructor arguments.** Both classes open with `del dataset_name, split_types, corpus_types, cache_dir, formatter` (`lancedb.py:22`, `modal_lancedb.py:21`). Passing non-default values for these parameters has no effect. All meaningful configuration comes through `retrieval_config`.

3. **`BERT_MODEL` is a deprecated alias, not a distinct implementation.** It just hard-codes `torch_dtype="float32"` (previously the only supported dtype) and delegates to `DENSE_TRANSFORMER_MODEL`. New experiment configs should use `dense_transformer` directly.

4. **`LANCEDB_MODEL.batch_text_to_item_retrieval` and `MODAL_LANCEDB_MODEL.batch_text_to_item_retrieval` are serial loops** — no native backend batching.

5. **Dense index cache invalidation is content-addressed but partial.** `DENSE_TRANSFORMER_MODEL` and `LITELLM_EMBEDDING_MODEL` hash the query/document templates and a few config fields to produce the cache directory name. Changing `corpus_types` or `formatter.name` is also encoded, but changing the underlying HF dataset content without changing `dataset_name` will not bust the cache — stale embeddings will be reused silently.

6. **LiteLLM proxy defaults.** `LITELLM_EMBEDDING_MODEL` defaults `api_base` to `http://localhost:4000` and `api_key` to `"sk-anything"` if the corresponding env vars (`LITELLM_PROXY_BASE`, `LITELLM_PROXY_KEY`) are unset. Missing a running proxy will cause a connection error only at index-build or query time, not at construction.

7. **`LanceDbRetriever.text_to_item_retrieval` raises if `searches` is empty.** If the retriever was constructed without a `searches` list in the config (valid for the pure Protocol path), calling the legacy method raises `RuntimeError` with a diagnostic message pointing at the Protocol methods instead (`retriever.py:375`).
