# Embeddings module

## Purpose

`mcrs/embeddings/` provides the embedding layer used by the v0+ query-understanding compiler to convert a natural-language query string into a dense vector for ANN retrieval against the LanceDB catalog. It defines a provider-neutral `Protocol` (`EmbeddingClient`) and three concrete backends — local HuggingFace inference, LiteLLM API proxy/direct, and a Modal-hosted GPU class — so the compiler can swap encoders via a single `encoder.backend` config key without changing retrieval logic.

In the pipeline, these clients sit between query-understanding compilation (e.g. `V0PlusQUCompiler.compile()`) and the LanceDB vector search: the compiler calls `encoder.embed_batch([query_string])` to get a float vector, then hands that vector to `LanceDbRetriever`.

---

## Files

| File | Responsibility |
|---|---|
| `base.py` | Defines the `EmbeddingClient` `Protocol` — the single method every backend must implement. |
| `litellm_client.py` | **Primary** LiteLLM-backed client: sync + optional batching, `dimensions`, `encoding_format`, LiteLLM disk-cache pass-through, `embed_one` convenience method. |
| `litellm_embedding.py` | **Older / parallel** LiteLLM client: sync + async (`aembed_batch`), reads `LITELLM_PROXY_BASE` from env, no batching loop. Intended originally for routing Qwen3-0.6B through an HF inference proxy; currently not re-exported by `__init__.py`. |
| `qwen3_embedding.py` | Local HF-backed `Qwen3EmbeddingClient` running `Qwen/Qwen3-Embedding-0.6B` in-process (CPU or CUDA). Also contains three document-template helpers that reproduce the exact string format used when the catalog vectors were generated. |
| `modal_qwen3_client.py` | Thin client that proxies `embed_batch` calls to a deployed Modal `Qwen3Encoder` GPU class, reducing per-call latency from ~1–2 s (CPU) to ~50 ms (T4 warm). |

---

## Public API

The following symbols are imported by other `mcrs` modules.

### `EmbeddingClient` protocol — `base.py:7`

```python
class EmbeddingClient(Protocol):
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

Runtime-checkable `Protocol`. Any object that implements `embed_batch` satisfies it. All three concrete clients conform to this interface. Used as a type annotation in `compiler.py:43`, `compiler_qu.py:65`, and `retrieval_services/service.py:5`.

---

### `LiteLLMEmbeddingClient` (from `litellm_client.py`) — `litellm_client.py:21`

```python
@dataclass
class LiteLLMEmbeddingClient:
    model_name: str
    api_base: str | None = None
    api_key: str | None = None
    batch_size: int = 128
    dimensions: int | None = None
    encoding_format: str | None = None        # "float" required for DeepInfra
    cache: dict[str, Any] | None = None       # passed directly to litellm (disk cache)
    extra_params: dict[str, Any] = field(default_factory=dict)

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    def embed_one(self, text: str) -> list[float]: ...
    def build_request_kwargs(self, texts: list[str]) -> dict[str, Any]: ...
```

This is the canonical LiteLLM client re-exported from `__init__.py`. It splits long input lists into `batch_size` chunks, calls `litellm.embedding()` per chunk, and flattens results. `build_request_kwargs` is public so callers can inspect or extend the kwargs dict (used in tests at `test_litellm_embedding_client.py:83`).

Default `batch_size=128` is generous; the v0+ compiler config uses `batch_size=32` when targeting DeepInfra.

---

### `Qwen3EmbeddingClient` — `qwen3_embedding.py:175`

```python
@dataclass
class Qwen3EmbeddingClient:
    model_name: str = "Qwen/Qwen3-Embedding-0.6B"
    device: str = "cpu"
    torch_dtype_name: str = "float32"         # "float32" | "float16" | "bfloat16" / fp* aliases
    max_length: int = 512
    batch_size: int = 8
    padding_side: str = "left"                # required for last_token pooling on batches
    query_instruct: str = ""                  # empty = symmetric retrieval (matches catalog)

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    def embed_one(self, text: str) -> list[float]: ...
```

Lazy-loads the HF model on first `embed_batch` call. Uses left-padding and last-token pooling followed by L2 normalisation — matching the Qwen3-Embedding convention. The model and tokenizer are stored in private fields `_model`, `_tokenizer` after first load.

---

### `ModalQwen3EmbeddingClient` — `modal_qwen3_client.py:22`

```python
@dataclass
class ModalQwen3EmbeddingClient:
    app_name: str = "music-crs"
    cls_name: str = "Qwen3Encoder"

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    async def aembed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

Resolves the Modal class on `__post_init__` via `modal.Cls.from_name`. The lookup does not spin up a container; only the first `.remote()` call triggers cold-start if needed. `aembed_batch` is available for async contexts (not currently used by the compiler, which is synchronous).

---

### Document template helpers — `qwen3_embedding.py`

These reproduce the exact string format used by talkpl-ai when generating the three Qwen3 catalog vector columns. Using different templates would silently break cosine similarity.

| Function | Catalog column matched | Line |
|---|---|---|
| `talkplay_metadata_document_template(metadata: dict) -> str` | `metadata-qwen3_embedding_0.6b` | `qwen3_embedding.py:125` |
| `talkplay_attributes_document_template(attributes: dict) -> str` | `attributes-qwen3_embedding_0.6b` | `qwen3_embedding.py:67` |
| `talkplay_lyrics_document_template(lyrics: str | None) -> str` | `lyrics-qwen3_embedding_0.6b` | `qwen3_embedding.py:107` |

All three return an empty string when all fields are absent (matching upstream behaviour of skipping the embedding for such tracks).

---

## Key data structures / config

### Backend selection in YAML config (`encoder` block)

The `compiler_qu.py` factory reads an `encoder` dict from the experiment YAML config:

```yaml
encoder:
  backend: "local"    # "local" | "litellm" | "modal"
  device: "cpu"
  torch_dtype: "float32"
  max_length: 512
  batch_size: 8
  padding_side: "left"
  query_instruct: ""
  # litellm-only:
  model_name: "openai/Qwen/Qwen3-Embedding-0.6B"
  api_base: "https://api.deepinfra.com/v1/openai"
  api_key: null          # falls back to DEEPINFRA_API_KEY env var
  encoding_format: "float"
  # modal-only:
  modal_app_name: "music-crs"
  modal_cls_name: "Qwen3Encoder"
```

Unknown `backend` values raise `ValueError` at construction time (`compiler_qu.py:635`).

### Module `__init__.py` exports

```python
from .base import EmbeddingClient
from .litellm_client import LiteLLMEmbeddingClient
__all__ = ["EmbeddingClient", "LiteLLMEmbeddingClient"]
```

Only `EmbeddingClient` and the canonical `LiteLLMEmbeddingClient` (from `litellm_client.py`) are part of the public namespace. `Qwen3EmbeddingClient` and `ModalQwen3EmbeddingClient` must be imported directly from their modules.

---

## Internal flow

1. **Config read** (`compiler_qu.py:599–637`): the factory function inspects `encoder.backend` and instantiates the appropriate concrete client.
2. **Client passed to compiler**: the resulting `EmbeddingClient` is stored on `V0PlusQUCompiler.encoder` (`compiler_qu.py:305`).
3. **Query encoding** (`compiler.py:356`): `compiler.compile()` calls `self.encoder.embed_batch([query_string])[0]` to get a single float vector.
4. **Backend dispatch**:
   - `local`: `Qwen3EmbeddingClient._ensure_loaded()` lazy-loads the HF model; `_encode_chunk()` tokenises, runs forward pass, last-token-pools, L2-normalises.
   - `litellm`: `LiteLLMEmbeddingClient.embed_batch()` splits into `batch_size` sub-lists, calls `litellm.embedding(**kwargs)` per chunk, extracts `item["embedding"]` or `item.embedding`.
   - `modal`: `ModalQwen3EmbeddingClient.embed_batch()` dispatches to `self._instance.embed_batch.remote(texts)`, which runs in the deployed T4 container (`modal/app.py`).
5. **Vector returned** to the compiler and forwarded to `LanceDbRetriever` for ANN search.

Additionally, `RetrievalService` (`retrieval_services/service.py:8`) optionally wraps an `EmbeddingClient` and exposes `embed_batch` as a service method; this path is used by the Modal-hosted inference stack.

---

## Dependencies

### Other `mcrs` modules

| Module | How used |
|---|---|
| `mcrs/qu_modules/compiler_qu.py` | Imports all three client classes; builds the encoder via a factory. |
| `mcrs/qu_modules/compiler.py` | Imports `EmbeddingClient` for type annotation; calls `encoder.embed_batch`. |
| `mcrs/retrieval_services/service.py` | Imports `EmbeddingClient`; stores an optional client; exposes `embed_batch`. |
| `modal/app.py` | Imports `LiteLLMEmbeddingClient` for the CPU-inference path. |

### External libraries

| Library | Used by | Notes |
|---|---|---|
| `litellm` | `litellm_client.py`, `litellm_embedding.py` | Imported lazily inside `embed_batch` to avoid hard dependency at import time. |
| `torch`, `transformers` | `qwen3_embedding.py` | Imported lazily inside `_ensure_loaded()`. Requires GPU/CPU PyTorch. |
| `modal` | `modal_qwen3_client.py` | Imported in `__post_init__`; requires `modal` package and active credentials. |

---

## Gotchas

1. **Two `LiteLLMEmbeddingClient` classes with the same name.** `litellm_client.py` and `litellm_embedding.py` both define a class named `LiteLLMEmbeddingClient`. Only `litellm_client.py` is re-exported by `__init__.py`. `litellm_embedding.py` has slightly different semantics (no internal batching loop, response parsed as `response["data"]` dict rather than `response.data` attribute-or-dict), and adds `aembed_batch`. Callers that do `from mcrs.embeddings import LiteLLMEmbeddingClient` get the `litellm_client.py` version. `litellm_embedding.py` appears to be an older or parallel design retained for the async path but currently unused by production callers.

2. **Catalog vectors are un-normalized float32; query vectors are L2-normalized.** `Qwen3EmbeddingClient._encode_chunk()` applies `F.normalize(..., p=2)` to queries, but the catalog's `metadata-qwen3_embedding_0.6b` column was stored without normalization (per `qwen3_embedding.py:27–28`). True cosine similarity requires normalizing both sides at compare time; LanceDB's cosine metric handles this, but any direct dot-product comparison would be asymmetric.

3. **`encoding_format="float"` is mandatory for DeepInfra** (`litellm_client.py:30`). Omitting it returns HTTP 422. The factory in `compiler_qu.py:622` sets it as the default for the `litellm` backend.

4. **`query_instruct` default is intentionally empty.** `DEFAULT_QUERY_INSTRUCT = ""` (`qwen3_embedding.py:56`). The catalog was built without an instruct prefix, so enabling `DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS` for queries would create an asymmetric embedding space. It is retained as an opt-in for experiments only.

5. **Modal cold-start cost.** `ModalQwen3EmbeddingClient.__post_init__` calls `modal.Cls.from_name` and `self._cls()` at construction, but the actual container spin-up happens on the first `.remote()` call — which can add ~30 s latency for a cold start. The `aembed_batch` async variant exists to allow concurrent calls but is not yet used by the synchronous compiler.

6. **`litellm_embedding.py` response parsing differs from `litellm_client.py`.** The former accesses `response["data"]` (dict indexing) while the latter handles both `item["embedding"]` (dict) and `item.embedding` (attribute) via `_embedding_from_item`. Mixing the two in tests would cause subtle failures.
