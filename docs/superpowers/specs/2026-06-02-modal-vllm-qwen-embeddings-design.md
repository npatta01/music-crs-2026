# Self-hosted Qwen embeddings via vLLM on Modal

**Date:** 2026-06-02
**Status:** Approved design (pre-implementation)
**Author:** brainstormed with Claude

## Goal

Give the project a **self-hosted, scale-to-zero alternative to paid embedding APIs**
(currently DeepInfra for `Qwen/Qwen3-Embedding-0.6B`). Serve
`Qwen/Qwen3-Embedding-4B` and `Qwen/Qwen3-Embedding-8B` on Modal via vLLM behind an
OpenAI-compatible `/v1/embeddings` endpoint, reached through LiteLLM so that the
**existing LiteLLM file cache applies unchanged** ("cached like LiteLLM").

This is reusable infrastructure — there is no committed use case yet beyond a wired,
verified embedding path. The harness is intentionally built so it can later extend to
generative serving (extractor / explanation), but **only embeddings are wired now**.

### Non-goals (YAGNI)

- Chat/generative serving for the extractor or response generation. The serving harness
  is shaped to extend to it (swap `--task embed` for a generative model and use
  `/v1/chat/completions`), but no generative endpoint is built in this pass.
- Replacing the canonical `v0plus_compiler_image_devset` pipeline. The vLLM path is
  added as a **separate, A/B-able experiment config**; the canonical config is untouched.
- Any change to the #90 GPU-native `DiskVectorCache` layer. That is a different code path
  (the in-process `Qwen3Encoder`); this design routes through LiteLLM instead and does not
  touch it.

## Background — how things work today

- All LLM/embedding calls flow through **LiteLLM**. `setup_litellm_cache()`
  (`mcrs/litellm_cache.py`) installs a process-global `litellm.cache` = a `FileCache`
  backed by the Modal volume `music-crs-litellm-cache-v2` (mounted at `/root/litellm-cache`).
  Supported call types already include `embedding` / `aembedding`.
- The cache key is computed by LiteLLM from the **request** (model string, input, params),
  independent of *where* the model is hosted. A cache hit short-circuits **before** the
  HTTP call. `api_base` / `api_key` are **not** part of the key.
- The v0+ encoder (`mcrs/qu_modules/compiler_v0plus_qu.py`, `backend: litellm`) already
  builds a `LiteLLMEmbeddingClient` from `model_name` + `api_base` + `api_key`. Today:
  `model_name: openai/Qwen/Qwen3-Embedding-0.6B`, `api_base: https://api.deepinfra.com/v1/openai`.
- Modal GPU services (`Qwen3Encoder`, `MultimodalTextEncoder`, `ModalLiteLLMService`) are
  already `@app.cls(min_containers=0, scaledown_window=…)` — **scale-to-zero is the house style**.
- Modal 1.4.2 is installed; vLLM is not yet a dependency. Modal's canonical vLLM pattern is
  `@app.function(image, gpu, volumes, scaledown_window, timeout)` + `@modal.concurrent(max_inputs=…)`
  + `@modal.web_server(port=8000, startup_timeout=…)` running `subprocess.Popen(["vllm","serve",…])`,
  with weights on a Volume.

## Chosen approach (Approach A)

vLLM OpenAI web endpoint + LiteLLM `api_base`. Downstream code reaches the GPU **only**
through `litellm.embedding`, so caching is free and the GPU stays asleep on cache hits.

```
v0+ encoder (backend: litellm)
   → litellm.embedding(model="openai/Qwen/Qwen3-Embedding-4B",
                       api_base=<resolved-modal-url>/v1, api_key=$VLLM_API_KEY)
       → [litellm.cache FileCache hit?] ──hit──► return (GPU stays asleep)
                    │ miss
                    ▼
       Modal app "music-crs-vllm" web_server (scale-to-zero)
         → vllm serve <hf_id> --task embed → /v1/embeddings
```

Rejected alternatives:
- **B — in-process vLLM `@app.cls` + #90 `DiskVectorCache`:** no HTTP hop and reuses #90's
  cache, but it is *not* "cached like LiteLLM" (different layer), exposes no OpenAI endpoint
  for the later generative use cases, and is more bespoke.
- **C — vLLM OpenAI server called directly (no LiteLLM):** loses caching. Rejected.

## Components

### 1. Serving app — `modal/vllm_serve.py` (new, separate Modal app)

Separate app `modal.App("music-crs-vllm")`, deployed independently
(`modal deploy modal/vllm_serve.py`), so the heavy vLLM/CUDA image never bloats the main
`music-crs` app build and the serving lifecycle is managed on its own.

- **Image** `_vllm_image`: `modal.Image.debian_slim().pip_install("vllm==<pinned>",
  "huggingface_hub[hf_transfer]")` with `HF_HUB_ENABLE_HF_TRANSFER=1`. vLLM version pinned
  at implementation time against the latest stable that supports Qwen3-Embedding pooling.
- **Model registry** (read from `modal/config.yaml`, see §5 — not hardcoded URLs). Each
  entry: `{key, hf_id, served_name, task: "embed", gpu, dtype, max_model_len,
  scaledown_window, max_inputs, timeout}`.
- **Endpoints** — one thin function per model: `serve_qwen3_embedding_4b`,
  `serve_qwen3_embedding_8b`. Each:
  ```python
  @app.function(image=_vllm_image, gpu=ENTRY.gpu,
                volumes={"/root/.cache/huggingface": hf_cache_vol,
                         "/root/.cache/vllm": vllm_cache_vol},
                secrets=[ENV_SECRET], timeout=ENTRY.timeout,
                scaledown_window=ENTRY.scaledown_window)   # min_containers defaults to 0
  @modal.concurrent(max_inputs=ENTRY.max_inputs)
  @modal.web_server(port=8000, startup_timeout=10*60)
  def serve_…(): _run_vllm_serve(ENTRY)
  ```
- **`_run_vllm_serve(entry)`** (shared): builds and `subprocess.Popen`s
  ```
  vllm serve <hf_id> --task embed --served-model-name <served_name>
    --host 0.0.0.0 --port 8000 --api-key $VLLM_API_KEY
    --dtype <dtype> [--max-model-len <n>] [--tensor-parallel-size 1]
  ```
  This is the single unit under test for command construction.
- **GPU sizing (initial, tunable in config):** 4B → `L4`, 8B → `L40S`.

### 2. Weights on a Volume — lazy populate (chosen)

- Reuse the existing `music-crs-hf-cache` volume at `/root/.cache/huggingface`. The first
  container's `vllm serve` downloads weights from HF into the mounted volume; Modal persists
  it so later cold starts load from local disk.
- Add a `vllm-cache` volume at `/root/.cache/vllm` for torch-compile artifacts to further
  cut cold-start time.
- **Optional pre-warm:** `modal run modal/vllm_serve.py::download --model {4b,8b}` performs an
  explicit `huggingface_hub.snapshot_download` into the volume and `commit()`s, for when the
  lazy first-hit cost is undesirable. Lazy remains the default path.

### 3. Endpoint URL resolution — resolver helper (chosen)

No hardcoded `modal.run` URLs in configs. A logical name (e.g. `qwen3-embedding-4b`) is
resolved to the live web URL at runtime.

- Helper in `modal/vllm_serve.py`: `endpoint_url(key) ->` resolves via the Modal SDK
  (`modal.Function.from_name("music-crs-vllm", fn_name).get_web_url()`; exact accessor
  confirmed against modal 1.4.2 during implementation) and appends `/v1`.
- **Resolution happens at the entrypoint layer**, keeping `mcrs/` free of any Modal import:
  a small `resolve_vllm_endpoints(config)` pass runs at inference startup
  (`run_inference_devset.py` / `run_experiment.py` / the Modal inference function). It expands
  an encoder config that names a logical endpoint into a concrete `api_base` before the
  config reaches `mcrs`. Encoder configs declare e.g. `vllm_endpoint: qwen3-embedding-4b`
  (resolved) rather than a literal `api_base`.

### 4. Caching — reuses existing LiteLLM FileCache, no new cache code

Calls go through `litellm.embedding` with `litellm.cache` already configured on the
`music-crs-litellm-cache-v2` volume. Identical `(model, input, params)` requests hit the
file cache and skip the HTTP call, so a fully-cached run never wakes the GPU. The model
string (`…-4B` vs `…-8B`) is in the key, so the two models cache separately. `api_key` /
`api_base` are not in the key, so rotating the key or redeploying the URL does not
invalidate the cache.

### 5. Config & experiment wiring (additive)

- New `vllm:` block in `modal/config.yaml` holding the model registry (§1).
- Two new experiment configs, copies of `configs/v0plus_compiler_image_devset.yaml` with
  only the `encoder` block changed:
  - `configs/v0plus_compiler_image_qwen3emb4b_vllm_devset.yaml`
  - `configs/v0plus_compiler_image_qwen3emb8b_vllm_devset.yaml`
  Each sets `encoder.backend: litellm`, `encoder.model_name: openai/Qwen/Qwen3-Embedding-{4B,8B}`,
  `encoder.vllm_endpoint: qwen3-embedding-{4b,8b}` (resolved to `api_base`),
  and `encoder.api_key` sourced from the `VLLM_API_KEY` secret. The canonical config is untouched.
- **Auth:** vLLM `--api-key $VLLM_API_KEY` (from `ENV_SECRET`); LiteLLM passes it as `api_key`.
  Keeps the public `modal.run` endpoint from being openly callable without affecting the cache.

### 6. Error handling & cold start

- `@modal.web_server(startup_timeout=10*60)` covers first-boot model load.
- The encoder's LiteLLM embedding **timeout is raised** (cold start can be 30–90s+) with a
  bounded retry, so the first post-idle embed does not hard-fail. Concretely: the
  `LiteLLMEmbeddingClient` request timeout for the vLLM path is configurable and defaulted
  high enough to absorb a cold start.
- vLLM OOM → addressed by GPU sizing in config. HF download flakiness → `hf_transfer` + retry.
  Registry/URL mismatch → caught by the smoke test (§7).

### 7. Testing

- **Unit (no GPU, CI-safe):** registry validation + `_run_vllm_serve` command-builder test
  (asserts `--task embed`, correct `--served-model-name`, port 8000, `--api-key` present,
  dtype/max-model-len plumbed). Lives alongside `tests/test_modal_app_resources.py`. Plus a
  `resolve_vllm_endpoints` test with the Modal resolver mocked.
- **Smoke (GPU, cost-gated — per the "Modal full-devset runs need approval" rule):**
  `modal run modal/vllm_serve.py::smoke` deploys, embeds one text twice through LiteLLM
  against the vLLM `api_base`, and asserts the **second call is a cache hit** and vectors
  match, reusing the existing `*_with_cache_status` machinery in `ModalLiteLLMService`.
  Run only on explicit go-ahead.

## Deliverables

1. `modal/vllm_serve.py` — serving app (2 embedding endpoints, `_run_vllm_serve`,
   `endpoint_url`, optional `download`, `smoke`).
2. `vllm:` registry block in `modal/config.yaml`; `vllm-cache` volume entry.
3. `resolve_vllm_endpoints` entrypoint pass + encoder config support for `vllm_endpoint`.
4. Two A/B experiment configs (`…_qwen3emb4b_vllm_devset.yaml`, `…_qwen3emb8b_vllm_devset.yaml`).
5. Unit tests (command builder, registry, resolver) + cost-gated GPU smoke entrypoint.
6. Docs: a short section in `docs/modal_setup.md` on deploying/using the vLLM embedding service.

## Open items to confirm during implementation

- Exact pinned vLLM version and the Modal 1.4.2 accessor for a `@modal.web_server` function's
  web URL (`get_web_url()` vs `.web_url`).
- Final GPU choices for 4B/8B after a throughput/memory check.
- Whether `--task embed` is needed explicitly or vLLM auto-detects Qwen3-Embedding as pooling.
