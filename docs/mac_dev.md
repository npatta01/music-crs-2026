# Mac / Local Dev

Mac local runs can use the CPU-compatible retrieval-only configs in `configs/`.

## One-time setup

```bash
# Create difficulty-stratified local eval split (3 easy / 3 medium / 3 hard = 9 sessions)
uv run python scripts/create_local_split.py --n_per_tier 3 --seed 42
# saves data/local_eval_split.json (gitignored)
```

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
that trace without rerunning extraction.

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

See [Staged Experiment Pipeline](architectures/staged_pipeline.md) for stage
outputs, config keys, Modal-anchor comparisons, and current limitations.
