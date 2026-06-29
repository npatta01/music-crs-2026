# Staged Experiment Pipeline

The staged pipeline is a config-driven wrapper around the existing inference,
rerank, explanation, and evaluation scripts. It is for experiment iteration: run
slow retrieval/state extraction once, then replay rerank/evaluation changes over
saved traces.

Training remains outside this runner. Use `docs/reproduce_reranker.md` for the
full LambdaMART training path.

## Stages

`run_pipeline.py` runs these stages in order:

| Stage | Input | Output | Notes |
|---|---|---|---|
| `retrieval` | `configs/{retrieval.tid}.yaml` | `retrieval/inference/{split}/{tid}.json` and `_trace.jsonl` | Delegates to `run_experiment.py`; can use local or Modal retrieval. |
| `rerank` | retrieval trace JSONL | `rerank/inference/{split}/{out_tid}.json` and optional `_trace.jsonl` | Local LambdaMART replay via `scripts/rerank/replay_lgbm.py`; can shard workers and skip trace rewrites for faster iteration. |
| `explanation` | rerank prediction JSON | same prediction JSON | Currently supports `lm_type: dummy` only, which preserves blank responses for ranking experiments. |
| `evaluation` | rerank prediction JSON + ground truth | `rerank/scores/{split}/{out_tid}.json` and sample CSV | Devset only; also runs branch diagnostics when a trace is present. |

Each run writes under:

```text
exp/pipeline/runs/<run_id>/
  manifest.json
  retrieval/
  rerank/
```

The manifest records the pipeline id, config hash, retrieval source, and stage
artifact roots so later stages can be replayed without guessing paths.

## Config

The active staged config is:

```text
configs/pipelines/state_ranker_v10_lgbm_devset.yaml
```

It runs local RRF/candidate-fusion retrieval with local shards, then replays
the committed `models/reranker_v12_goalfree` LightGBM bundle with local rerank
shards. Trace rewrites are disabled by default for faster ranking/evaluation loops.

Important knobs:

| Config key | Meaning |
|---|---|
| `retrieval.tid` | The online config used to produce retrieval traces, usually `state_ranker_v10_rrf_devset`. |
| `retrieval.backend` | `local` or `modal`; Modal can be used for the slow retrieval stage. |
| `retrieval.num_shards` / `num_workers` | Session shards and local worker processes for devset retrieval. |
| `rerank.model_ref` | Model bundle directory containing `model.txt`, `meta.json`, `cat_maps.json`, and `branch_names.json`. |
| `rerank.pool_k` | Candidate pool depth used to compute pool-normalized rerank features. Keep aligned with training/serving. |
| `rerank.num_shards` / `num_workers` | Parallel replay workers. Each worker writes a run-scoped prediction shard, then `scripts/merge_shard_results.py` merges the final JSON. |
| `rerank.write_trace` | `false` writes predictions only and skips expensive rerank trace reconstruction; set `true` when branch diagnostics or replay trace inspection are needed. |
| `rerank.output_topk` | Number of recommendations written to the final prediction JSON. |

## Common Commands

Run the full staged local devset pipeline:

```bash
python run_pipeline.py --config configs/pipelines/state_ranker_v10_lgbm_devset.yaml
```

Run only retrieval and keep the trace for later:

```bash
python run_pipeline.py \
  --config configs/pipelines/state_ranker_v10_lgbm_devset.yaml \
  --only retrieval \
  --run-id retrieval-v10-local
```

Replay rerank, dummy explanation, and evaluation from an existing retrieval run:

```bash
python run_pipeline.py \
  --config configs/pipelines/state_ranker_v10_lgbm_devset.yaml \
  --from rerank \
  --retrieval-run exp/pipeline/runs/retrieval-v10-local \
  --run-id rerank-v10-candidate
```

Replay only rerank with a different model bundle:

```bash
python run_pipeline.py \
  --config configs/pipelines/state_ranker_v10_lgbm_devset.yaml \
  --only rerank \
  --retrieval-run exp/pipeline/runs/retrieval-v10-local \
  --model-ref models/<candidate_bundle> \
  --run-id rerank-v10-candidate
```

Use a session subset for smoke tests:

```bash
python run_pipeline.py \
  --config configs/pipelines/state_ranker_v10_lgbm_devset.yaml \
  --num-sessions 2 \
  --run-id smoke-staged
```

Subset smoke runs are forced through a single retrieval process even when the
pipeline config has `retrieval.num_shards > 1`; `run_experiment.py` intentionally
rejects `--num_sessions` plus sharding.

## Local Sharding

`run_experiment.py --backend local` now supports devset sharding:

```bash
MCRS_MAX_IN_FLIGHT=24 MCRS_COMPILE_MAX_IN_FLIGHT=8 \
python run_experiment.py \
  --backend local \
  --tid state_ranker_v10_lgbm_devset \
  --batch_size 128 \
  --num_shards 4 \
  --num_workers 4 \
  --exp_dir exp_local_verify
```

(The old `_fastlocal` config is now the canonical devset config with concurrency
raised via `MCRS_MAX_IN_FLIGHT` / `MCRS_COMPILE_MAX_IN_FLIGHT`.)

This launches one `run_inference_devset.py` process per shard, writes per-shard
logs under `logs/local_shards/<run_id>/`, merges the shard outputs with
`scripts/merge_shard_results.py`, then evaluates the merged devset output.

Local sharding is intentionally devset-only. It cannot be combined with
`--num_sessions` or `--clear_cache`; use `--session_ids_file` for fixed subsets.


## Rerank Replay Sharding

The staged rerank stage can run multiple local replay workers over the saved
retrieval trace. Shards write run-scoped files such as
`{out_tid}.run_<run_id>.shard_0.json`; the pipeline merges them into the normal
`{out_tid}.json` prediction file before explanation/evaluation.

For fast ranking experiments, keep `rerank.write_trace: false`. This avoids
rebuilding and serializing a large rerank trace for every turn. Evaluation still
runs from the prediction JSON, but branch diagnostics are skipped because there
is no merged `_trace.jsonl`. Set `write_trace: true` when you need trace
inspection or branch diagnostics. Per-shard logs are written under
`logs/pipeline_rerank/<run_id>/`.

## Modal Retrieval, Local Rerank

For mixed runs, set `retrieval.backend: modal` in the pipeline config and keep
`rerank.backend: local`. Do not pass `--backend modal` to `run_pipeline.py` for a
mixed retrieval/local-rerank run, because the CLI override applies to every
stage and the offline LGBM replay is local-only.

## Frozen Modal Anchors

Use run-id-scoped Modal artifacts when comparing against a historical score. The
plain `{tid}.json` path can be overwritten by later smoke runs.

```bash
python modal/download_results.py \
  --tid state_ranker_v10_lgbm_devset \
  --split devset \
  --kind all \
  --run-id 20260615T020857Z-b8ec83 \
  --out-dir exp_modal_anchor_run_20260615

python scripts/merge_shard_results.py \
  --tid state_ranker_v10_lgbm_devset \
  --num_shards 50 \
  --run_id 20260615T020857Z-b8ec83 \
  --exp-dir exp_modal_anchor_run_20260615 \
  --split devset

python evaluator/evaluate_devset.py \
  --tid state_ranker_v10_lgbm_devset \
  --eval_dataset devset \
  --exp_dir exp_modal_anchor_run_20260615
```

The `20260615T020857Z-b8ec83` anchor scores `NDCG@20=0.4562`,
`Hit@20=0.6138`, and `MRR=0.4102` after local merge/evaluation.

## Limits

- The runner is for experiment orchestration, not model training.
- Rerank replay currently supports LightGBM LambdaMART bundles only.
- Explanation replay only supports `lm_type: dummy`; use the online inference
  path for non-dummy response generation.
- Blindset evaluation is skipped because there is no public ground truth.
