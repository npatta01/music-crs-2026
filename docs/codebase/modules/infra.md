# Module Group: Modal / Scripts / Infra

## Purpose

This group handles cloud GPU execution (Modal), artifact management, and operational tooling. It sits at the outermost shell of the pipeline: it does not implement retrieval or LLM logic itself, but provisions the compute environment, wires together the inference scripts, manages Modal persistent volumes, and provides local scripts for index building, result merging, split creation, and service smoke-testing.

The main interaction points with the rest of the system:

- `modal/app.py` — defines the Modal app, container image, volumes, and all remote functions/services; the `run_experiment.py` entrypoint calls it via `modal run`.
- `modal/download_results.py` — syncs completed artifacts from the `music-crs-results` Modal volume to `evaluator/exp/` on the local machine.
- `scripts/` — one-off operational utilities (index building, result merging, eval-split creation, service smoke tests, worktree initialisation).
- `infra/litellm/litellm_proxy.openrouter.yaml` — static proxy config for the local LiteLLM dev proxy that exposes OpenRouter models via an OpenAI-compatible endpoint.

---

## Files

| File | Responsibility |
|---|---|
| `modal/app.py` | Modal app definition: container image, volume mounts, remote inference functions (`_inference_devset`, `_inference_devset_cpu`, `_inference_blindset`, `_inference_blindset_cpu`), remote service classes (`ModalRetrievalService`, `Qwen3Encoder`, `ModalLiteLLMService`), utility functions (`query_lancedb`, `_evaluate`), and local entrypoints (`run_inference`, `run_inference_sharded`, `run_inference_blindset`, `run_evaluate`, `upload_lancedb_index`, `smoke_lancedb_query`). |
| `modal/config.yaml` | All Modal resource configuration: app name, volume names, container mount paths, GPU fallback list, CPU/memory sizing for each service, LiteLLM model names, Qwen3-Encoder GPU/dtype settings. |
| `modal/download_results.py` | Bulk-downloads artifacts from the `music-crs-results` Modal volume to a local `evaluator/exp/` tree; supports filtering by `tid`, split, and artifact kind (inference, traces, scores, ground-truth). |
| `scripts/build_lancedb_index.py` | CLI wrapper around `mcrs.lancedb.indexing.build_track_lancedb_table`; builds the 47k-track LanceDB index locally (with or without embeddings). |
| `scripts/create_local_split.py` | Creates a difficulty-stratified eval subset (`data/local_eval_split.json`) by scoring devset sessions on mean ground-truth track popularity. |
| `scripts/merge_shard_results.py` | Merges run-id-scoped shard outputs into a single `{tid}.json`; takes `--run_id` to select `{tid}.run_{run_id}.shard_N.json` files (omit for legacy unscoped files); merges traces only when all shards have a `_trace.json` sidecar (devset); blindset shards have none; warns on key overlap. |
| `scripts/smoke_lancedb_modal_query.py` | Smoke-tests the deployed `ModalRetrievalService` via `LanceDbModalClient`; prints returned track IDs. |
| `scripts/smoke_litellm_modal_cache.py` | Smoke-tests the deployed `ModalLiteLLMService`; calls both embedding and chat twice and asserts the second call is a LiteLLM disk-cache hit. |
| `scripts/litellm-proxy` | Shell script that starts a local LiteLLM proxy (OpenAI-compatible) backed by OpenRouter, using `infra/litellm/litellm_proxy.openrouter.yaml`. |
| `scripts/on-worktree-create.sh` | Claude Code `WorktreeCreate` hook; creates the git worktree under `.claude/worktrees/<name>`, runs `setup-worktree.sh`, and prints the worktree path. |
| `scripts/setup-worktree.sh` | Idempotent worktree setup: resolves main-repo path, symlinks entries from `.worktreeinclude` (`data/`, `.env`), and runs `uv sync`. |
| `infra/litellm/litellm_proxy.openrouter.yaml` | LiteLLM proxy model list mapping local `openai/*` names to OpenRouter endpoints (LLaMA, Gemma, Qwen3, GPT, embedding models); enables disk cache under `artifacts/cache/litellm`. |

---

## Public API

The classes and functions below are the entry points that other modules (or `run_experiment.py`) interact with.

### `modal/app.py`

| Symbol | Signature | Description |
|---|---|---|
| `run_inference` | `(tid, batch_size, num_sessions, clear_cache, session_ids_json)` — local entrypoint | Dispatches devset inference to `_inference_devset` (GPU) or `_inference_devset_cpu` (CPU) based on whether the config sets `device: cpu`. |
| `run_inference_sharded` | `(tid, eval_dataset, num_shards, run_id, batch_size, clear_cache)` — local entrypoint | Split-generic: `eval_dataset == "devset"` fans out devset workers; anything else fans out blindset workers. GPU vs CPU chosen internally via `_tid_uses_cpu`. Each shard writes run-id-scoped artifacts `inference/{split}/{tid}.run_{run_id}.shard_{i}.json` (plus a `_trace.json` sidecar for devset). Requires a non-empty `run_id`. |
| `run_inference_blindset` | `(tid, batch_size, eval_dataset)` — local entrypoint | Dispatches blindset inference to `_inference_blindset` or `_inference_blindset_cpu`. |
| `run_evaluate` | `(tid, split)` — local entrypoint | Runs `evaluator/make_ground_truth.py` (if needed) and `evaluator/evaluate_devset.py` on the results volume. |
| `upload_lancedb_index` | `(local_db_dir, remote_dir, overwrite)` — local entrypoint | Uploads a locally built LanceDB directory to the `music-crs-models` Modal volume; `overwrite=True` removes the target directory first. |
| `smoke_lancedb_query` | `(query, topk)` — local entrypoint | Calls `query_lancedb.remote` and prints returned track IDs. |
| `query_lancedb` | `(query, topk, retrieval_config) -> list[str]` — Modal function | FTS-only LanceDB query on the models volume; raises `ValueError` if a `dense_vector` search is requested. `modal/app.py:631` |
| `ModalRetrievalService` | Modal class | Stateful retrieval service backed by `LanceDbRetriever`; exposes `retrieve`, `retrieve_batch`, `embed_batch`. LRU cache of up to 8 `RetrievalService` instances keyed by serialised `retrieval_config`. `modal/app.py:344` |
| `ModalRetrievalService.retrieve` | `(query, topk, retrieval_config) -> list[str]` | Single-query retrieval. `modal/app.py:398` |
| `ModalRetrievalService.retrieve_batch` | `(queries, topk, retrieval_config) -> list[list[str]]` | Batch retrieval. `modal/app.py:408` |
| `ModalRetrievalService.embed_batch` | `(texts) -> list[list[float]]` | Forwards to the underlying `RetrievalService.embed_batch`. `modal/app.py:418` |
| `Qwen3Encoder` | Modal class | GPU-backed (T4) Qwen3-Embedding-0.6B encoder; cold-start ~30 s; warm latency ~50 ms. `modal/app.py:434` |
| `Qwen3Encoder.embed_batch` | `(texts) -> list[list[float]]` | Runs embeddings on GPU via `Qwen3EmbeddingClient`. `modal/app.py:464` |
| `ModalLiteLLMService` | Modal class | CPU-backed LiteLLM proxy with shared disk cache; used for smoke-testing cache behaviour. `modal/app.py:481` |
| `ModalLiteLLMService.embed_once_with_cache_status` | `(text, model_name, api_base) -> dict` | Embeds one text and returns `{kind, ok, model, cache_hit, dimensions}`. `modal/app.py:517` |
| `ModalLiteLLMService.chat_once_with_cache_status` | `(prompt, model_name, api_base) -> dict` | Single chat completion; returns `{kind, ok, model, cache_hit, content}`. `modal/app.py:549` |

### `modal/download_results.py`

| Symbol | Signature | Description |
|---|---|---|
| `discover_remote_artifacts` | `(volume, splits, verbose) -> list[RemoteArtifact]` | Lists the `music-crs-results` volume tree and returns typed `RemoteArtifact` records. `modal/download_results.py:192` |
| `select_artifacts` | `(artifacts, tids, kinds, overwrite, out_dir) -> list[RemoteArtifact]` | Filters discovered artifacts by tid, kind, and whether the local file already exists. `modal/download_results.py:275` |
| `sync_artifacts` | `(volume, artifacts, out_dir, dry_run, verbose) -> SyncSummary` | Downloads each selected artifact via `volume.read_file`; uses `.part` temp files for atomic writes. `modal/download_results.py:295` |
| `main` | `(argv) -> int` | CLI entry point; wires parser → discover → select → sync. `modal/download_results.py:325` |

### `mcrs/lancedb/modal_client.py` (consumed by inference scripts / smoke tests)

| Symbol | Signature | Description |
|---|---|---|
| `LanceDbModalClient.__init__` | `(app_name, class_name)` | Resolves the deployed `ModalRetrievalService` class via `modal.Cls.from_name`. |
| `LanceDbModalClient.query` | `(query, topk, retrieval_config) -> list[str]` | Single-query remote call to `ModalRetrievalService.retrieve`. |
| `LanceDbModalClient.query_batch` | `(queries, topk, retrieval_config) -> list[list[str]]` | Batch remote call. |
| `LanceDbModalClient.embed_batch` | `(texts) -> list[list[float]]` | Remote embed call. |

### `mcrs/embeddings/modal_qwen3_client.py` (consumed by v0+ compiler)

| Symbol | Signature | Description |
|---|---|---|
| `ModalQwen3EmbeddingClient` | `(app_name, cls_name)` — dataclass | On `__post_init__`, resolves the deployed `Qwen3Encoder` class. |
| `ModalQwen3EmbeddingClient.embed_batch` | `(texts) -> list[list[float]]` | Synchronous remote call to `Qwen3Encoder.embed_batch`. |
| `ModalQwen3EmbeddingClient.aembed_batch` | `(texts) -> list[list[float]]` (async) | Async variant; used by the v0+ async compiler pipeline. |

---

## Key Data Structures / Config

### `RemoteArtifact` (`modal/download_results.py:34`)

```python
@dataclass(frozen=True)
class RemoteArtifact:
    remote_path: str      # path on the Modal volume, e.g. "inference/devset/my_tid.json"
    size: int             # bytes
    kind: str             # "inference" | "trace" | "scores" | "ground-truth"
    split: str | None     # "devset" | "blindset_A" | ...
    tid: str | None       # experiment id, None for ground-truth
```

### `SyncSummary` (`modal/download_results.py:42`)

```python
@dataclass(frozen=True)
class SyncSummary:
    planned: int
    downloaded: int
    skipped: int
    total_bytes: int
```

### `KIND_ALIASES` (`modal/download_results.py:25`)

Maps CLI `--kind` values to internal kind sets:

```python
KIND_ALIASES = {
    "all":          {"inference", "trace", "scores", "ground-truth"},
    "inference":    {"inference"},
    "traces":       {"trace"},
    "scores":       {"scores"},
    "ground-truth": {"ground-truth"},
}
```

### `modal/config.yaml` — key fields

| Key path | Value / notes |
|---|---|
| `app_name` | `"music-crs"` — Modal app identifier |
| `volumes.hf_cache` | `"music-crs-hf-cache"` — HuggingFace model weights |
| `volumes.results` | `"music-crs-results"` — inference outputs, scores, ground truth |
| `volumes.models` | `"music-crs-models"` — LanceDB index |
| `volumes.cache` | `"music-crs-cache"` — unified Volumes v2 cache mounted at `container.cache_dir` (`/root/cache`); holds the file-per-key LiteLLM cache (`/root/cache/litellm`, shared between `ModalLiteLLMService` and `_inference_*`) and the GPU-encoder DiskVectorCache (`/root/cache/embedding`) |
| `container.exp_dir` | `"/root/exp"` — maps to `results_vol`; inference scripts write here |
| `inference.gpu` | `["H200","H100","L40S","A100-80GB","A100-40GB"]` — fallback list for GPU jobs |
| `inference.devset_batch_size` | `64` |
| `lancedb.inference_cpu/memory` | `2.0 CPU / 16 GiB` — sized for `max_in_flight=8` async LLM calls |
| `qwen3_encoder.gpu` | `"T4"` — cheapest GPU that fits 0.6B model |
| `qwen3_encoder.torch_dtype` | `"bfloat16"` |
| `litellm.chat_model` | `"openrouter/google/gemma-3-4b-it"` |
| `litellm.embedding_model` | `"openrouter/openai/text-embedding-3-small"` |

### `_VOLUME_MOUNTS` (`modal/app.py:107`)

```python
_VOLUME_MOUNTS = {
    HF_CACHE_DIR:      hf_cache_vol,
    EXP_DIR:           results_vol,
    MODELS_DIR:        models_vol,
    LITELLM_CACHE_DIR: litellm_cache_vol,
}
```

Used by inference functions to mount all four volumes simultaneously.

### `DEFAULT_REMOTE_LANCEDB_URI` (`modal/app.py:114`)

`"/root/models/lancedb"` — the path inside the `music-crs-models` volume where the LanceDB index lives.

---

## Internal Flow

### Devset inference (Modal path, single container)

1. User calls `python run_experiment.py --backend modal --tid <tid>`.
2. `run_experiment.py:run_modal` builds the `modal run modal/app.py::run_inference` subprocess command and calls it.
3. `run_inference` (local entrypoint, `modal/app.py:700`) checks `_tid_uses_cpu(tid)`: if `device: cpu` is set in `configs/{tid}.yaml`, it dispatches to `_inference_devset_cpu`, otherwise `_inference_devset`.
4. The chosen function runs inside a Modal container (GPU or CPU+memory-sized) with all four volumes mounted. It assembles a `python run_inference_devset.py ...` subprocess command and calls `_run_inference_command`, which injects `MCRS_LANCEDB_URI` (CPU path only), `MCRS_LITELLM_CACHE_BACKEND=file`, and `MCRS_LITELLM_CACHE_DIR` into the environment.
5. After inference, the function calls `results_vol.commit()` to flush writes.
6. Back locally, `run_experiment.py:run_modal` calls `modal/download_results.py` as a subprocess to pull the outputs to `evaluator/exp/`.
7. `run_experiment.py` then calls `evaluator/make_ground_truth.py` (if needed) and `evaluator/evaluate_devset.py`.

### Sharded inference (devset or blindset)

1. `run_inference_sharded` (local entrypoint, `modal/app.py:773`) receives `eval_dataset` and `run_id`; it selects the devset or blindset inference function and applies `_tid_uses_cpu(tid)` to choose GPU vs CPU — callers do not pick a resource flavor.
2. It loops over `shard_id` in `range(num_shards)`, calling `.spawn(...)` for each; this returns immediately with a call handle.
3. `output_suffix=f".run_{run_id}.shard_{shard_id}"` causes each shard to write `inference/{split}/{tid}.run_{run_id}.shard_{N}.json` (plus a `_trace.json` sidecar for devset shards).
4. A resilient join collects results: failed shards are retried once; any remaining failures abort loudly after all shards have been awaited.
5. When invoked via `run_experiment.py --num_shards N`, the wrapper auto-runs `modal/download_results.py` (run-scoped) → `scripts/merge_shard_results.py` → evaluator (devset only). The manual `scripts/merge_shard_results.py` path remains available for direct `modal run` use.

### LanceDB index upload

1. `scripts/build_lancedb_index.py` calls `mcrs.lancedb.indexing.build_track_lancedb_table` to produce `cache/lancedb/`.
2. `upload_lancedb_index` (local entrypoint) optionally removes the target directory when `--overwrite` is set, then calls `models_vol.batch_upload()` to push the local directory to `/lancedb` inside the `music-crs-models` volume. The entrypoint rejects `remote_dir=/` so overwrite cannot clear the volume root.

### Retrieval service (deployed, persistent)

1. `ModalRetrievalService.setup` (`@modal.enter`, `modal/app.py:346`) runs once per container start. It reads `MCRS_EMBEDDING_MODEL` from env to optionally create a `LiteLLMEmbeddingClient`, builds a `LanceDbRetriever`, and wraps it in a `RetrievalService`.
2. On each `retrieve` / `retrieve_batch` call, `_service_for_retrieval_config` checks an LRU cache (max 8 entries) keyed by a JSON-serialised config hash. Cache miss builds a new `LanceDbRetriever` + `RetrievalService`.
3. `LanceDbModalClient` (in `mcrs/lancedb/modal_client.py`) wraps `modal.Cls.from_name` to hide SDK details from callers.

### Qwen3 encoder path

1. v0+ compiler config sets `encoder.backend: "modal"`.
2. `ModalQwen3EmbeddingClient.__post_init__` resolves `Qwen3Encoder` via `modal.Cls.from_name`.
3. Each encode call dispatches to `Qwen3Encoder.embed_batch.remote` (or `.remote.aio` for async), which runs on a T4 GPU.
4. `Qwen3Encoder.setup` pre-loads the model via `_ensure_loaded()` on container start.

### Artifact download

1. `download_results.py:main` connects to `modal.Volume.from_name("music-crs-results")`.
2. `discover_remote_artifacts` lists `/inference`, `/scores`, and `/ground_truth` trees, classifying each file as `inference`, `trace`, `scores`, or `ground-truth` based on path prefix and suffix.
3. `select_artifacts` filters by `tid`, `kind`, and local-file existence.
4. `sync_artifacts` streams each file via `volume.read_file` in chunks, writing to a `.part` file then atomically renaming.

---

## Dependencies

### External libraries

| Library | Used in |
|---|---|
| `modal` | `modal/app.py`, `modal/download_results.py`, `mcrs/lancedb/modal_client.py`, `mcrs/embeddings/modal_qwen3_client.py`, `scripts/smoke_litellm_modal_cache.py` |
| `omegaconf` | `modal/app.py` (config loading), `run_experiment.py` |
| `litellm` | `modal/app.py` (`ModalLiteLLMService`) |
| `datasets` | `scripts/create_local_split.py` |

### Internal `mcrs` modules

| Module | Used in |
|---|---|
| `mcrs.lancedb.retriever.LanceDbRetriever` | `modal/app.py` (`ModalRetrievalService.setup`, `_service_for_retrieval_config`) |
| `mcrs.retrieval_services.RetrievalService` | `modal/app.py` (`ModalRetrievalService`) |
| `mcrs.embeddings.LiteLLMEmbeddingClient` | `modal/app.py` (`ModalRetrievalService.setup`, `ModalLiteLLMService.embed_once_with_cache_status`) |
| `mcrs.embeddings.qwen3_embedding.Qwen3EmbeddingClient` | `modal/app.py` (`Qwen3Encoder.setup`) |
| `mcrs.lm_modules.litellm_client.LiteLLMChatClient` | `modal/app.py` (`ModalLiteLLMService.chat_once_with_cache_status`) |
| `mcrs.retrieval_modules.lancedb.LANCEDB_MODEL` | `modal/app.py` (`query_lancedb`) |
| `mcrs.milvus.indexing.BM25_WITH_TAG_LIST_CORPUS_FIELDS` | `modal/app.py` (`_default_lancedb_retrieval_config`) |
| `mcrs.lancedb.indexing.build_track_lancedb_table` | `scripts/build_lancedb_index.py` |
| `mcrs.lancedb.modal_client.LanceDbModalClient` | `scripts/smoke_lancedb_modal_query.py` |

### Implicit dependencies

- `run_inference_devset.py` / `run_inference_blindset.py` — invoked as subprocesses by `_inference_devset*` and `_inference_blindset*`.
- `evaluator/make_ground_truth.py` / `evaluator/evaluate_devset.py` — invoked as subprocesses by `_evaluate` and `run_experiment.py`.
- `.env` in project root — `modal.Secret.from_dotenv(__file__)` reads `HF_TOKEN`, `OPENROUTER_API_KEY`, `DEEPINFRA_API_KEY` from it.

---

## Gotchas

1. **`_default_lancedb_retrieval_config` imports from `mcrs.milvus`** (`modal/app.py:119`). Despite the module being named `milvus`, it provides BM25 corpus-field constants used by the LanceDB path — a legacy naming artifact from an earlier Milvus-backed retrieval prototype.

2. **`query_lancedb` is FTS-only.** `_ensure_query_lancedb_fts_only` (`modal/app.py:142`) raises `ValueError` if a `dense_vector` search is in `retrieval_config`. Dense-vector queries must go through `ModalRetrievalService.retrieve` instead. The two functions are not interchangeable despite similar signatures.

3. **`ModalRetrievalService` vs `query_lancedb`** — `ModalRetrievalService` is a persistent class (survives across calls within a container lifecycle, holds a retriever in memory) while `query_lancedb` is a stateless function that rebuilds `LANCEDB_MODEL` on every invocation. `ModalRetrievalService` is the production path; `query_lancedb` is kept for the `smoke_lancedb_query` entrypoint.

4. **LiteLLM file cache is shared between containers.** The unified `music-crs-cache` volume is mounted at `CACHE_DIR` (`/root/cache`) in `_VOLUME_MOUNTS` (used by all inference functions) and in `ModalLiteLLMService`; the LiteLLM file cache lives under `LITELLM_CACHE_DIR` (`/root/cache/litellm`). Both classes read/write distinct JSON files there, so LLM extraction calls cached during one inference run warm the cache for the next. The GPU encoders share the same volume under `EMBEDDING_CACHE_DIR` (`/root/cache/embedding`).

5. **`_inference_devset_cpu` sets `MCRS_LANCEDB_URI`; `_inference_devset` does not.** GPU inference functions expect the retrieval config to embed the DB URI (via experiment config), while CPU functions inject it via environment variable (`DEFAULT_REMOTE_LANCEDB_URI = "/root/models/lancedb"`). This asymmetry means GPU and CPU configs may need different `db_uri` handling.

6. **`run_experiment.py --num_shards N` auto-runs download → merge → evaluate.** `run_inference_sharded` itself only writes per-shard artifacts and does not merge them. The `run_experiment.py` wrapper handles the full pipeline automatically (download run-scoped shards, merge, evaluate for devset). For direct `modal run modal/app.py::run_inference_sharded` usage, callers must run `scripts/merge_shard_results.py --run_id <run_id>` manually.

7. **`_session_ids_file_arg` writes to `/tmp/session_ids.json`** (`modal/app.py:194`). If two Modal containers for different experiments run on the same instance simultaneously (unlikely given `max_containers=1` for most classes, but possible in sharded mode), they would share this temp file path.

8. **`ModalLiteLLMService` is only used for smoke testing.** It is not in the hot inference path. Production inference containers use `MCRS_LITELLM_CACHE_BACKEND=file` and `MCRS_LITELLM_CACHE_DIR` to share the same file cache but call LiteLLM directly via `mcrs.lm_modules`.

9. **`infra/litellm/litellm_proxy.openrouter.yaml` is a local dev tool only.** The `scripts/litellm-proxy` shell script is not invoked by any automated path; it is for manual local development to hit OpenRouter models through an OpenAI-compatible interface.

10. **`setup-worktree.sh` symlinks `data/` and `.env`** from the main repo. New worktrees do not contain real copies of these resources; deleting or changing them in the main repo immediately affects all active worktrees.
