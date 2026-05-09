# Agentic Hardened Handoff — 2026-05-05

## What We Are Working On

We are adapting the TalkPlay-style retrieval flow into the main repo as a **native Chat Completions tool-calling** path, not the old text-parsed `<tool_call>` path.

The current goal is:

- keep the baseline path intact
- add a repo-native `pipeline_type: agentic`
- use native `tools` via LiteLLM/OpenRouter
- make the tool-calling loop reliable enough for real devset runs

This work is currently centered on:

- [mcrs/agentic.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/agentic.py)
- [mcrs/__init__.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/__init__.py)
- [run_inference_devset.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/run_inference_devset.py)
- [run_inference_blindset.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/run_inference_blindset.py)

## What Changed

### Core implementation

Implemented a hardened native tool-calling pipeline in [mcrs/agentic.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/agentic.py):

- native Chat Completions `tools`
- one-tool-at-a-time planning
- terminal `submit_ranking`
- bounded repair when the model returns no tool call
- terminal repair when the model fails to submit a final ranking
- constrained `sql_filter`
- SQL validation for:
  - only `SELECT track_id FROM tracks ...`
  - only `tracks` table
  - rejection of malformed tag-list patterns like `'instrumental' IN tag_list`
- structured tool errors returned back into the planning loop
- richer `tool_trace` with per-step details

### Tool surface

Current relevant tools:

- `sql_filter`
- `bm25_search`
- `text_to_item_similarity`
- `item_to_item_similarity`
- `user_to_item_similarity`
- `submit_ranking`

`semantic_id_matching` was intentionally not added in this pass.

### Runner plumbing

The standard runners now support the agentic path and trace sidecars:

- [run_inference_devset.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/run_inference_devset.py)
- [run_inference_blindset.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/run_inference_blindset.py)

### Tests

Added/updated tests:

- [tests/test_agentic_pipeline.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/tests/test_agentic_pipeline.py)
- [tests/test_inference_scripts.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/tests/test_inference_scripts.py)

Verified locally on May 4, 2026:

```bash
uv run pytest tests/test_agentic_pipeline.py tests/test_inference_scripts.py -q
```

Result: `13 passed`

## Naming Cleanup Already Done

To avoid confusion between old and current artifacts, files were renamed.

### Current hardened configs

- [config/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke.yaml](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/config/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke.yaml)
- [config/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_full.yaml](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/config/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_full.yaml)
- [config/talkplay_openrouter_gpt54_mini_agentic_hardened_devset_smoke.yaml](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/config/talkplay_openrouter_gpt54_mini_agentic_hardened_devset_smoke.yaml)
- [config/talkplay_openrouter_gpt54_mini_agentic_hardened_devset_full.yaml](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/config/talkplay_openrouter_gpt54_mini_agentic_hardened_devset_full.yaml)
- [config/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_smoke.yaml](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/config/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_smoke.yaml)
- [config/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_full.yaml](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/config/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_full.yaml)

### Current hardened smoke artifacts

- [exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke.json](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke.json)
- [exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke_trace.json](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke_trace.json)
- [exp/inference/devset/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_smoke.json](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_smoke.json)
- [exp/inference/devset/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_smoke_trace.json](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_smoke_trace.json)

### Old artifact clearly marked

- [exp/inference/devset/talkplay_openrouter_qwen35_9b_pre_hardening_devset_full.json](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/talkplay_openrouter_qwen35_9b_pre_hardening_devset_full.json)

This old full file is **not** the successful full run of the hardened path.

## Current Status

### 2026-05-05 continuation update

Follow-up work completed on May 5, 2026:

- relaxed [evaluator/evaluate_devset.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/evaluator/evaluate_devset.py) so shallow devset runs no longer fail at depth `<1000`
- added evaluator regression coverage in [tests/test_evaluate_devset.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/tests/test_evaluate_devset.py)
- updated [docs/evaluation.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/docs/evaluation.md) and [evaluator/readme.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/evaluator/readme.md) to document shallow-run scoring
- fixed LiteLLM proxy model naming for SDK-based proxy calls in:
  - [mcrs/litellm_utils.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/litellm_utils.py)
  - [mcrs/agentic.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/agentic.py)
  - [mcrs/retrieval_modules/litellm_embedding.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/retrieval_modules/litellm_embedding.py)
  - [mcrs/lm_modules/litellm_chat.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/lm_modules/litellm_chat.py)
  - [mcrs/qu_modules/llm_rewrite.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/qu_modules/llm_rewrite.py)

The evaluator now:

- scores only cutoffs supported by the smallest prediction depth in the file
- reports unsupported deeper metrics as unavailable instead of raising
- emits depth metadata including:
  - `min_pool_depth`
  - `max_pool_depth`
  - `supported_k_values`
  - `supported_mrr_k_values`

### Smoke re-verification on May 5, 2026

Proxy listener on `127.0.0.1:4001` was present, and the hardened 9b smoke run was executed again with repo-local writable Hugging Face caches.

First rerun outcome for:

- [exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke.json](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke.json)
- [exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke_trace.json](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke_trace.json)

- `8/8` turns completed as fallback outputs
- `0/8` turns reached `submit_ranking`
- fallback reason on every turn was runtime connection failure from LiteLLM / OpenAI-compatible upstream
- representative error: `litellm.InternalServerError: InternalServerError: OpenAIException - Connection error.`

Root cause investigation after that rerun found:

- the proxy itself was healthy
- the repo’s LiteLLM SDK calls needed OpenAI-provider-prefixed model names when targeting the proxy
- direct HTTP calls with bare aliases worked, but SDK calls with bare aliases failed before reaching the proxy

Second rerun outcome after the LiteLLM model-name fix:

- `7/8` turns finished with `submit_ranking`
- `1/8` turn fell back
- `4/8` turns used the bounded repair path
- the remaining fallback was `tool_call_missing` after repair, not a connectivity failure

Updated conclusion:

- the shallow evaluator is ready for top-20 agentic runs
- the proxy/model-name connectivity blocker is resolved
- the hardened 9b smoke path is mostly working again, but still not at the earlier `8/8, 0 fallback` reliability mark

Because the latest smoke still had `1/8` fallback, a hardened full devset run was **not** launched in this session.

### Smoke status

#### `qwen3.5-9b` hardened smoke

File:

- [exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke_trace.json](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke_trace.json)

This is the best current evidence for the new path.

Observed on May 4, 2026:

- `8/8` turns finished with `submit_ranking`
- `0` fallbacks
- `0` SQL validation/runtime tool errors
- `3/8` turns used the bounded repair path

Conclusion:

- the hardened native tool-calling path works in smoke for `qwen3.5-9b`

#### `qwen3.6-35b-a3b` hardened smoke

Files:

- [exp/inference/devset/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_smoke.json](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_smoke.json)
- [exp/inference/devset/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_smoke_trace.json](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_smoke_trace.json)

Observed on May 4, 2026:

- much less reliable than `qwen3.5-9b`
- multiple failures were malformed native tool-call arguments
- example error pattern: `Unterminated string...`
- some turns also missed tool calls entirely even after repair

Conclusion:

- with the current OpenRouter/LiteLLM path, `qwen3.5-9b` is more reliable than `qwen3.6-35b-a3b`

### Full devset status

There is **no completed hardened full-devset output yet**.

What exists:

- [exp/inference/devset/talkplay_openrouter_qwen35_9b_pre_hardening_devset_full.json](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/talkplay_openrouter_qwen35_9b_pre_hardening_devset_full.json)

This file:

- has `8000` rows
- is from May 4, 2026 at `01:47`
- belongs to the older pre-hardening implementation
- should not be used as the result of the current work

We also attempted a fresh 4-shard hardened full rerun on the evening of May 4, 2026.

Outcome:

- worker processes disappeared by the next morning
- no new shard outputs were written under `/private/tmp/talkplay_qwen35_full_shards/out_*`
- root cause was **not** captured yet

### Proxy status

The LiteLLM proxies on ports `4000` and `4001` were explicitly killed during cleanup.

If a new session wants to run live inference again, the proxy must be restarted first.

## Important Caveat About Evaluation

The current hardened agentic config still returns only **top-20** predictions.

That means the standard offline devset evaluator in this repo:

- [evaluator/evaluate_devset.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/evaluator/evaluate_devset.py)

will **not** evaluate this path as-is, because it requires prediction depth `1000`.

So today:

- smoke can be scored as a shallow top-20 run
- deep-cutoff diagnostics above the supported pool depth are reported as unavailable

This is not a bug in the smoke artifacts; it is a contract mismatch between:

- agentic retrieval output depth = `20`
- evaluator required devset depth = `1000`

## Local Repo State To Be Careful With

The working tree is not clean. At the time of handoff, `git status --short` showed multiple modified files beyond the new agentic work, including:

- `configs/litellm_proxy.openrouter.yaml`
- `mcrs/__init__.py`
- `mcrs/retrieval_modules/litellm_embedding.py`
- `run_inference_devset.py`
- `run_inference_blindset.py`
- `tests/test_inference_scripts.py`
- plus several other modified files unrelated to this exact handoff

Do **not** assume every modified file belongs only to the latest agentic patch. Read before reverting anything.

## Recommended Next Steps

### 1. Reproduce the full-run failure on one shard in the foreground

Best next debugging step:

- restart the LiteLLM proxy
- run a single shard with the hardened 9b config
- capture stdout/stderr directly

Why:

- the last full rerun died before writing outputs
- we need the failure message before trying another 1000-session run

### 2. Decide whether to keep top-20 or support deep devset evaluation

Need an explicit choice:

- if the goal is challenge-like top-20 behavior, keep the current agentic path as-is
- if the goal is offline devset scoring with the stock evaluator, the pipeline must produce deeper candidate pools

### 3. If live runs are needed, restart the proxy first

Both LiteLLM proxies were stopped during cleanup, so a new session must restart them before smoke/full inference.

### 4. Prefer `qwen3.5-9b` over `qwen3.6-35b-a3b` for now

Current evidence says:

- `qwen3.5-9b` is the working planner for this setup
- `qwen3.6-35b-a3b` is less tool-compliant in this path

## Useful Commands For The Next Session

Restart proxy on `4001`:

```bash
uv tool run --python 3.12 --env-file .env --from litellm[proxy,caching] --with uvloop>=0.21 litellm --config configs/litellm_proxy.openrouter.yaml --host 0.0.0.0 --port 4001
```

Run hardened 9b smoke:

```bash
env LITELLM_PROXY_BASE=http://127.0.0.1:4001 \
uv run python run_inference_devset.py \
  --tid talkplay_openrouter_qwen35_9b_agentic_hardened_devset_smoke \
  --batch_size 1 \
  --num_sessions 1
```

Run hardened 35b smoke:

```bash
env LITELLM_PROXY_BASE=http://127.0.0.1:4001 \
uv run python run_inference_devset.py \
  --tid talkplay_openrouter_qwen36_35b_a3b_agentic_hardened_devset_smoke \
  --batch_size 1 \
  --num_sessions 1
```

Run one shard manually:

```bash
env LITELLM_PROXY_BASE=http://127.0.0.1:4001 \
uv run python run_inference_devset.py \
  --tid talkplay_openrouter_qwen35_9b_agentic_hardened_devset_full \
  --batch_size 1 \
  --session_ids_file /private/tmp/talkplay_qwen35_full_shards/shard_00.json \
  --exp_dir /private/tmp/talkplay_qwen35_full_shards/out_00
```

## Short Version

- native tool-calling path is implemented
- hardened smoke works for `qwen3.5-9b`
- `qwen3.6-35b-a3b` is less reliable in this setup
- old full file was renamed to `pre_hardening`
- no successful hardened full-devset run exists yet
- last full rerun died before writing outputs
- proxy is currently stopped
