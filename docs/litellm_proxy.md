# LiteLLM proxy (OpenRouter)

Optional path that runs query rewrite, response generation, and dense retrieval
embeddings against a LiteLLM proxy backed by OpenRouter. The local Hugging Face
GPU path for model adapters (`LLAMA_MODEL`, `TextCausalAdapter`) is unchanged.
Active competition configs no longer use CRS-level standalone retrieval modules.

## 1. Set up `.env`

```bash
echo 'OPENROUTER_API_KEY=sk-or-...' > .env
```

`scripts/litellm-proxy` reads `.env` directly. `OPENROUTER_API_KEY` is the only
required variable; the proxy itself accepts any client `api_key`.

## 2. Start the proxy

```bash
./scripts/litellm-proxy
```

This spawns `uv tool run litellm[proxy,caching]` against
`infra/litellm/litellm_proxy.openrouter.yaml`, bound to `0.0.0.0:4000` (clients reach
it at `http://localhost:4000`). Disk cache
lives under `artifacts/cache/litellm/` so repeated runs are cheap.

Override host/port/config via env:

```bash
LITELLM_PROXY_PORT=4100 ./scripts/litellm-proxy
```

## 3. Available models

`infra/litellm/litellm_proxy.openrouter.yaml` exposes proxy-side names mapped to
OpenRouter slugs (verified live at 2026-04). Old repo configs that referenced
`Qwen2.5-3B`, `gemma-3-E2B`, `SmolLM2-1.7B`, or `Qwen3-4B-Instruct-2507` keep
running through the local HF path — those slugs are not on OpenRouter.

| Proxy name | OpenRouter slug |
| --- | --- |
| `llama-3.2-1b-instruct` | `meta-llama/llama-3.2-1b-instruct` |
| `llama-3.2-3b-instruct` | `meta-llama/llama-3.2-3b-instruct` |
| `llama-3.3-70b-instruct` | `meta-llama/llama-3.3-70b-instruct` |
| `gemma-3n-e4b-it` | `google/gemma-3n-e4b-it` |
| `gemma-3-4b-it` | `google/gemma-3-4b-it` |
| `qwen3.5-9b` | `qwen/qwen3.5-9b` |
| `qwen3-30b-a3b-instruct` | `qwen/qwen3-30b-a3b-instruct-2507` |
| `qwen3-235b-a22b` | `qwen/qwen3-235b-a22b-2507` |
| `gpt-oss-20b` | `openai/gpt-oss-20b` |
| `text-embedding-3-small` | `openai/text-embedding-3-small` |
| `text-embedding-3-large` | `openai/text-embedding-3-large` |

## 4. End-to-end example

The old checked-in LiteLLM rewrite config was pruned with the experiment
archive. Recover it from Git history if you need that exact run, or create a
fresh config under `configs/`:

```bash
./scripts/litellm-proxy &
python run_inference_devset.py \
  --tid my_litellm_rewrite_devset \
  --batch_size 16 --num_sessions 4
```

First run embeds the 47k-track corpus once and persists to
`cache/dense_litellm/<sanitized_model>/<corpus_hash>/embeddings.pt`. Subsequent
runs re-use that index plus the LiteLLM disk cache.

## 5. Backend selection

| Component | Local HF (default) | LiteLLM (opt-in) |
| --- | --- | --- |
| Retrieval | full-pipeline QU retrieval/ranking | full-pipeline QU retrieval/ranking |
| Rewrite | `qu_kwargs.backend: local` (default) | `qu_kwargs.backend: litellm` |
| Generation | `lm_type: meta-llama/Llama-3.2-1B-Instruct` | `lm_type: litellm` + `lm_kwargs` |

Mix generation/rewrite backends freely. Active inference configs no longer use
the legacy CRS-level retrieval backend; retrieval/ranking is owned by the QU.
