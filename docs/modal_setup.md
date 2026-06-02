# Modal Setup

[Modal](https://modal.com) is used to run inference on cloud GPUs.

## Authenticate

```bash
uv run python -m modal setup
```

This opens a browser for OAuth. After completing it, your token is saved to `~/.modal.toml`.

## Verify setup

Run the smoke test to confirm your token works and a remote worker spins up:

```bash
uv run modal run other/modal_get_started.py
```

Expected output:

```
This code is running on a remote worker!
the square is 1764
```

---

## Cloud Pipeline

### One-time setup

Add API tokens to a `.env` file in the project root (already in `.gitignore`):

```
HF_TOKEN=hf_...
OPENROUTER_API_KEY=sk-or-...
```

Modal reads this automatically via `modal.Secret.from_dotenv()`. Volumes are created automatically on first run — no manual setup needed. Volume names and container paths are configured in `modal/config.yaml`.

---

### Run experiments

**Smoke test (5 random sessions, fast)**

```bash
python run_experiment.py --backend modal --tid v0plus_compiler_image_devset --num_sessions 5
```

**Full devset**

```bash
python run_experiment.py --backend modal --tid v0plus_compiler_all_retrievers_devset --batch_size 64
```

**Blindset (submission)**

```bash
python run_experiment.py --backend modal --tid v0plus_compiler_blindset_A --eval_dataset blindset_A --batch_size 64
```

The wrapper runs Modal inference, downloads artifacts back into your local `exp/` tree, and evaluates devset runs locally. The second Modal run skips re-downloading model weights because the HF cache is persisted in the `music-crs-hf-cache` volume.

---

### LanceDB CPU retrieval

LanceDB FTS runs do not need a GPU. Build the DB locally, upload it to the `music-crs-models` volume, then run the CPU Modal path:

```bash
uv run python scripts/build_lancedb_index.py --out-dir cache/lancedb --drop-existing
uv run modal run modal/app.py::upload_lancedb_index --local-db-dir cache/lancedb --remote-dir lancedb --overwrite
uv run modal run modal/app.py::smoke_lancedb_query --query "dark atmospheric synthwave" --topk 3
uv run python run_experiment.py --backend modal --tid v0plus_compiler_image_devset --num_sessions 5
```

Use `--overwrite` when replacing an existing Modal index. Modal volume uploads
do not overwrite LanceDB manifest files in place, so a rebuild upload can fail
with `FileExistsError` unless the old `music-crs-models:/lancedb` directory is
removed first. The upload entrypoint only removes the target directory when
`--overwrite` is set and rejects `remote_dir=/` to avoid clearing the volume
root.

The same local build/upload/smoke flow is available as
`notebooks/05_lancedb_indexing.ipynb`; the notebook calls the checked-in scripts
and Modal entrypoints rather than embedding indexing logic in notebook cells.

The default LanceDB build stores precomputed track embedding columns too. The
current FTS config still queries only sparse text fields; use `--metadata-only`
on `scripts/build_lancedb_index.py` only when you explicitly want a smaller
sparse-only DB artifact.

The wrapper materializes a deterministic session-id subset for `--num_sessions`, so inference and local evaluation use the same smoke rows.

The LanceDB CPU resource sizes live in `modal/config.yaml`. Current defaults request 8 CPU / 32 GiB for full inference and 4 CPU / 16 GiB for the private query endpoint.

For a private Modal SDK query smoke after deployment:

```bash
uv run modal deploy modal/app.py
uv run python scripts/smoke_lancedb_modal_query.py --query "dark atmospheric synthwave" --topk 20
```

### Scale-to-zero retrieval service

The class-backed retrieval service is private to Modal SDK callers and is cost
controlled by:

```yaml
lancedb:
  query_scaledown_window: 300
  query_max_containers: 1
```

The service decorator hard-codes `min_containers=0`. Do not change this unless
intentionally paying for an always-warm retriever.

### LiteLLM cache service

`ModalLiteLLMService` smoke-tests paid API caching for both embeddings and chat.
It uses the file-per-key LiteLLM cache on a separate Volumes v2 volume,
`music-crs-litellm-cache-v2`, mounted at `/root/litellm-cache`, so LiteLLM
cache files can be cleared without touching LanceDB or model artifacts.

```bash
uv run modal deploy modal/app.py
uv run python scripts/smoke_litellm_modal_cache.py
```

The default smoke calls OpenRouter embeddings
(`openrouter/openai/text-embedding-3-small`) and OpenRouter Gemma
(`openrouter/google/gemma-3-4b-it`) twice and fails unless the second identical
call reports `cache_hit: true`. You can still test provider-specific options
with `--embedding-model` and `--chat-model`.

To smoke the 0.6B Qwen chat route through HF Inference Providers:

```bash
uv run python scripts/smoke_litellm_modal_cache.py --skip-embedding --chat-profile qwen-0.6b
```

---

### Advanced manual commands

If you want to bypass the unified wrapper, the underlying Modal entrypoints are still available:

```bash
modal run modal/app.py::run_inference --tid v0plus_compiler_image_devset --batch-size 16
modal run modal/app.py::run_inference_blindset --tid v0plus_compiler_blindset_A --batch-size 16 --eval-dataset blindset_A
```

---

### Download results locally

Use the repo downloader to mirror artifacts from the Modal volume into a chosen local output directory. The unified wrapper uses `exp/`.

```bash
# Download one run into exp/
python modal/download_results.py --tid v0plus_compiler_all_retrievers_devset --out-dir exp

# Download all missing remote artifacts
python modal/download_results.py

# Preview what would be downloaded first
python modal/download_results.py --dry-run --verbose

# Restrict to scores only
python modal/download_results.py --kind scores
```

The downloader mirrors the remote artifact tree under your chosen `--out-dir`:

- `inference/<split>/<tid>.json`
- `inference/<split>/<tid>_trace.json`
- `inference/<split>/<tid>_rewrite_audit.jsonl`
- `inference/<split>/<tid>_rewrite_stats.json`
- `scores/<split>/<tid>.json`
- `ground_truth/...`

If remote `scores/` or `ground_truth/` directories do not exist yet, the downloader skips them cleanly.

---

## vLLM embedding services

`modal/vllm_serve.py` deploys a separate Modal app (`music-crs-vllm`) serving Qwen3-Embedding-4B and 8B models behind scale-to-zero `/v1/embeddings` endpoints reachable through LiteLLM.

### Deploy both endpoints

```bash
modal deploy modal/vllm_serve.py
```

This creates (or updates) two web endpoints: `serve_qwen3_embedding_4b` and `serve_qwen3_embedding_8b`.

### Scale-to-zero behavior

Both endpoints run with `min_containers=0`. The `scaledown_window` for each model is configured in the `vllm:` block of `modal/config.yaml`. When idle for longer than that window, the container shuts down. **The first request after an idle period pays a cold-start cost** (downloading/loading the model into GPU memory), which is why encoder configs set `extra_params.timeout: 600`.

Because all calls go through LiteLLM, a cache hit (served from the local file cache) **never wakes the GPU** — the request never reaches Modal.

### Secret setup

`VLLM_API_KEY` must be present in your `.env` file (already in `.gitignore`). It is used both by the vLLM server (`--api-key`) and by the LiteLLM client. Copy the placeholder from `.env.example`:

```
VLLM_API_KEY=change-me   # replace with a strong random string
```

Modal reads `.env` automatically via `modal.Secret.from_dotenv()`.

### Optional pre-warm

To download model weights into the persistent `music-crs-hf-cache` volume before the first inference request (makes subsequent cold starts faster):

```bash
modal run modal/vllm_serve.py::download --model qwen3-embedding-4b
modal run modal/vllm_serve.py::download --model qwen3-embedding-8b
```

### Smoke / cache verification

To verify the endpoint is reachable and LiteLLM caching works end-to-end (embeds the same text twice and asserts the second call is a cache hit):

```bash
modal run modal/vllm_serve.py::smoke --model qwen3-embedding-4b
```

Expected output:

```
dim=2560 cache_hit_second=True vectors_match=True
```

**This wakes the GPU.** Only run it with explicit approval or after deploying a new model variant.

### Using in experiment configs

Set `encoder.vllm_endpoint: qwen3-embedding-4b` (or `qwen3-embedding-8b`) in a config YAML. At inference start, `resolve_vllm_endpoints_in_qu_kwargs` resolves this key to the live `api_base` URL. LiteLLM then routes embedding calls through the file cache first; only a cache miss reaches the vLLM endpoint (and wakes the GPU if it has scaled to zero).

### Important caveat: re-indexing required for devset A/B runs

The current canonical config (`v0plus_compiler_image_devset`) has `enable_dense: false`. Its dense LanceDB columns were indexed with the 0.6B model (1024-dim vectors).

The provided A/B configs (`v0plus_compiler_image_qwen3emb4b_vllm_devset` / `_8b_`) point the encoder at the 4B (2560-dim) or 8B (4096-dim) Qwen3 models. **These configs will NOT exercise the text dense encoder during a devset run unless two conditions are met:**

1. `enable_dense: true` is set in the config.
2. The LanceDB catalog has been re-indexed with matching embedding columns (2560-dim for 4B, 4096-dim for 8B).

Without re-indexing, the dense retrieval branch will either be skipped or produce dimension-mismatch errors. The `smoke` entrypoint is the direct, cost-controlled way to verify that serving and caching are working — do not expect meaningful devset A/B numbers without a full catalog re-index.
