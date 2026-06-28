# Mac / Local Dev

Mac local runs can use the CPU-compatible retrieval-only configs in `configs/`.

## One-time setup

```bash
# Create difficulty-stratified local eval split (3 easy / 3 medium / 3 hard = 9 sessions)
uv run python scripts/create_local_split.py --n_per_tier 3 --seed 42
# saves data/local_eval_split.json (gitignored)
```

## Shared worktree caches

Use one shared cache-owner checkout for large ignored local artifacts, then link
those artifacts into each additional git worktree:

```bash
git config --global mcrs.sharedRoot /path/to/music-crs-cache-owner
uv run python scripts/setup_worktree_cache.py
```

For Codex worktrees on this machine, use the main checkout as the standard
cache owner:

```bash
git config --global mcrs.sharedRoot /home/nidhin/projects/music-conversational-music-recomender-2026
uv run python scripts/setup_worktree_cache.py
```

`scripts/setup_worktree_cache.py` links `cache`, `exp/analysis/rerank`, and
`.env`. It never hardcodes a machine path; source lookup is `--source`, then
`MCRS_SHARED_ROOT`, then `git config mcrs.sharedRoot`.

If a worktree already has local ignored cache artifacts from a failed run,
replace them with the shared links:

```bash
uv run python scripts/setup_worktree_cache.py --force
```

## State extraction cache

State files should be materialized into the shared `cache/` tree, not `exp/`.
Use `--skip-existing` for backfill runs so existing turn files are reused and
only missing turns call LiteLLM. Blind sets only need the final turn per session;
devset and trainset cache materialization use all turns.

See [State Extraction Cache](state_extraction_cache.md) for the standard GitHub
Release packaging, install, checksum verification, and override-file workflow.

```bash
uv run python scripts/extract_state.py \
  --tid state_ranker_v10_lgbm_blindset_A \
  --turn-scope final \
  --output-dir cache/state_extraction/blindset_A \
  --skip-existing

uv run python scripts/extract_state.py \
  --tid state_ranker_v10_lgbm_blindset_B \
  --turn-scope final \
  --output-dir cache/state_extraction/blindset_B \
  --skip-existing

uv run python scripts/extract_state.py \
  --tid state_ranker_v10_lgbm_devset \
  --turn-scope all \
  --output-dir cache/state_extraction/devset \
  --skip-existing
```

The trainset cache is materialized from the existing extracted-state artifact
`exp/state_extraction/deepseek_train_all.jsonl` into `cache/state_extraction/trainset`.

Manual corrections go next to the raw file as `turn_<n>_override.json`.

## Run the local split

```bash
uv run python run_experiment.py \
  --backend local \
  --tid state_ranker_v10_rrf_devset \
  --batch_size 2 \
  --exp_dir exp \
  --session_ids_file data/local_eval_split.json
```

The wrapper will run inference, generate ground truth in `exp/ground_truth/` if needed, and write scores to `exp/scores/devset/{tid}.json`.
Use `--tid state_ranker_v10_lgbm_devset` for the learned-ranker path after the v10 model bundle and feature sidecars are available locally.

## Local devset sharding

For full-devset local runs, use session shards to keep the CPU and API clients
busier. Four workers is the current default balance for the staged devset config;
reduce it if memory, API rate limits, or disk pressure become the bottleneck.

```bash
uv run python run_experiment.py \
  --backend local \
  --tid state_ranker_v10_lgbm_devset_fastlocal \
  --batch_size 128 \
  --num_shards 4 \
  --num_workers 4 \
  --exp_dir exp_local_verify
```

Local sharding is devset-only. It writes per-shard logs under
`logs/local_shards/<run_id>/`, merges shard artifacts, then evaluates the merged
prediction file.

## Staged local iteration

Use the staged pipeline when you want faster reranker iteration. Retrieval and
state extraction write a trace once; later runs can replay rerank/evaluation over
that trace without rerunning extraction. The default staged devset config uses
four rerank workers and `write_trace: false` so evaluation loops do not spend
time rebuilding the large rerank trace sidecar.

```bash
# Full staged run: retrieval -> rerank replay -> dummy explanation -> eval
uv run python run_pipeline.py \
  --config configs/pipelines/state_ranker_v10_lgbm_devset.yaml

# Rerank/eval only from an existing retrieval run
uv run python run_pipeline.py \
  --config configs/pipelines/state_ranker_v10_lgbm_devset.yaml \
  --from rerank \
  --retrieval-run exp/pipeline/runs/<run_id> \
  --run-id <rerank_run_id>
```

Set `rerank.write_trace: true` in the pipeline config when you need branch
diagnostics or trace inspection. See [Staged Experiment Pipeline](architectures/staged_pipeline.md)
for stage outputs, config keys, Modal-anchor comparisons, and current limitations.
