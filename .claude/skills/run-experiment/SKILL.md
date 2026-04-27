---
name: run-experiment
description: Use when running inference, evaluating results, or running a full Music CRS experiment with a given tid (task ID).
---

# Music CRS: Run Experiment

This is a **rigid skill** — follow every step exactly.

**Announce at start:** "I'm using the run-experiment skill to run this experiment."

---

## Step 1 — Extract tid

Parse the task ID from the user's message. Examples: `llama1b_bm25_devset`, `llama1b_bert_devset`, `llama1b_bm25_blindset_A`.

If no tid is given, ask: "Which experiment tid should I run?"

---

## Step 2 — Detect split

- tid contains `"devset"` → **devset path** (inference + evaluation + markdown report)
- otherwise → **blindset path** (inference only)

---

## Step 3 — Confirm config exists

```bash
ls config/{tid}.yaml
```

If missing, stop and tell the user: "No config found at config/{tid}.yaml — please create it first."

---

## Step 4 — Run Modal inference

**Devset:**
```bash
modal run modal/app.py::run_inference --tid {tid}
```

**Blindset:**
```bash
modal run modal/app.py::run_inference_blindset --tid {tid}
```

Wait for completion. If it fails, report the error and stop.

If it fails with `Could not connect to the Modal server`, rerun the same command with network/escalated approval, then continue from this step.

If it fails with `torch.OutOfMemoryError: CUDA out of memory`, stop and report the OOM. Suggest lowering the configured runtime batch size or rerunning with a smaller `--batch-size` if the Modal entrypoint supports it.

If it fails with `{path} was modified during build process`, report that the local worktree changed while Modal packaged the app. The user may retry once the worktree is stable.

Log: `Inference complete. Results saved to Modal volume: inference/devset/{tid}.json`

---

## Step 5 — Download inference results

Download to `evaluator/exp/` so the evaluation script can find them:

```bash
python modal/download_results.py --tid {tid} --out_dir evaluator/exp
```

For blindset, also pass `--split {eval_dataset}` (the non-devset part of the tid, e.g. `blindset_A`).

If download fails with `Could not connect to the Modal server`, rerun the same download command with network/escalated approval.

The download script uses `modal.Volume.from_name("music-crs-results")`, which is the correct API for the current Modal SDK used by this repo.

Log the local path: `Downloaded → evaluator/exp/inference/devset/{tid}.json`

---

## Step 6 (devset only) — Run evaluation locally

```bash
cd evaluator && PYTHONPATH=. python evaluate_devset.py --tid {tid}
```

This saves:
- `evaluator/exp/scores/devset/{tid}.json` — aggregate metrics
- `evaluator/exp/scores/devset/{tid}_samples.csv` — per-sample metrics (~8k rows)

If evaluation fails because ground truth is missing, generate it first:
```bash
cd evaluator && PYTHONPATH=. python make_ground_truth.py
```
Then re-run the evaluation.

If `make_ground_truth.py` or `evaluate_devset.py` fails with Hugging Face network/cache errors such as `nodename nor servname provided`, `Could not connect`, or `PermissionError` for a path under `~/.cache/huggingface`, rerun the same command with network/filesystem escalation so the cached dataset lock files and metadata can be accessed.

---

## Step 7 (devset only) — Generate markdown report

Read these two files:
- `config/{tid}.yaml` — for config fields
- `evaluator/exp/scores/devset/{tid}.json` — for all metrics

Create `experiments/{tid}.md` at the project root using this template (fill in all `{…}` placeholders from the JSON/YAML):

```markdown
# Experiment: {tid}

**Date:** {today's date as YYYY-MM-DD}
**Config:** `config/{tid}.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | {lm_type} |
| retrieval_type | {retrieval_type} |
| retrieval_topk | {retrieval_topk} |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | {ndcg@1:.4f} |
| NDCG@5 | {ndcg@5:.4f} |
| NDCG@10 | {ndcg@10:.4f} |
| NDCG@20 | {ndcg@20:.4f} |
| NDCG@50 | {ndcg@50:.4f} |
| NDCG@100 | {ndcg@100:.4f} |
| MRR | {mrr:.4f} |
| MRR@100 | {mrr@100:.4f} |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | {hit@1:.4f} |
| Hit@5 | {hit@5:.4f} |
| Hit@10 | {hit@10:.4f} |
| Hit@20 | {hit@20:.4f} |
| Hit@50 | {hit@50:.4f} |
| Hit@100 | {hit@100:.4f} |
| % GT not in top-20 | {pct_gt_not_in_top20:.1%} |
| % GT not in top-100 | {pct_gt_not_in_top100:.1%} |
| Mean rank (when found) | {mean_rank_when_found:.1f} |
| Median rank (when found) | {median_rank_when_found:.1f} |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | {catalog_diversity:.4f} |
| Catalog diversity @100 | {catalog_diversity@100:.4f} |
| Lexical diversity | {lexical_diversity:.4f} |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
{per_turn rows: one row per turn key 1–8}

## Files

- Inference predictions: `evaluator/exp/inference/devset/{tid}.json`
- Aggregate scores: `evaluator/exp/scores/devset/{tid}.json`
- Per-sample metrics: `evaluator/exp/scores/devset/{tid}_samples.csv`
```

Create the `experiments/` directory if it doesn't exist.

---

## Step 8 — Summary

Report to the user:

```
Experiment {tid} complete.

Inference:  evaluator/exp/inference/devset/{tid}.json
Scores:     evaluator/exp/scores/devset/{tid}.json
Samples:    evaluator/exp/scores/devset/{tid}_samples.csv
Report:     experiments/{tid}.md

Key metrics:
  NDCG@20:  {ndcg@20}
  Hit@20:   {hit@20}
  MRR:      {mrr}
  Catalog diversity @20: {catalog_diversity}
```
