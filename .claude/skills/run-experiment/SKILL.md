---
name: run-experiment
description: Use when running inference, evaluating results, or running a full Music CRS experiment with a given tid (task ID) through the unified local-or-Modal wrapper.
---

# Music CRS: Run Experiment

This is a **rigid skill** — follow every step exactly.

**Announce at start:** "I'm using the run-experiment skill to run this experiment."

---

## Step 1 — Extract tid

Parse the task ID from the user's message. Examples: `llama1b_bm25_devset`, `llama1b_bert_devset`, `llama1b_bm25_blindset_A`.

If no tid is given, ask: "Which experiment tid should I run?"

---

## Step 2 — Choose backend and detect split

- Default to `local` unless the user explicitly asks for Modal.
- tid contains `"devset"` → **devset path** (inference + evaluation + markdown report)
- tid containing `blindset_` → **blindset path** (inference only)
- if the tid is ambiguous, require an explicit `--eval_dataset`

---

## Step 3 — Confirm config exists

```bash
ls config/{tid}.yaml
```

If missing, stop and tell the user: "No config found at config/{tid}.yaml — please create it first."

---

## Step 4 — Run the unified experiment command

**Local devset:**
```bash
python run_experiment.py --backend local --tid {tid}
```

**Modal devset:**
```bash
python run_experiment.py --backend modal --tid {tid}
```

**Local blindset:**
```bash
python run_experiment.py --backend local --tid {tid} --eval_dataset {eval_dataset}
```

**Modal blindset:**
```bash
python run_experiment.py --backend modal --tid {tid} --eval_dataset {eval_dataset}
```

Wait for completion. If it fails, report the error and stop.

If it fails with `Could not connect to the Modal server`, rerun the same command with network/escalated approval, then continue from this step.

If it fails with `torch.OutOfMemoryError: CUDA out of memory`, stop and report the OOM. Suggest lowering the configured runtime batch size or rerunning with a smaller `--batch-size` if the Modal entrypoint supports it.

If it fails with `{path} was modified during build process`, report that the local worktree changed while Modal packaged the app. The user may retry once the worktree is stable.

For devset runs, the wrapper also evaluates locally and writes scores into `exp/scores/devset/`.

---

## Step 7 (devset only) — Generate markdown report

Read these two files:
- `config/{tid}.yaml` — for config fields
- `exp/scores/devset/{tid}.json` — for all metrics

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
| NDCG@200 | {ndcg@200:.4f} |
| NDCG@500 | {ndcg@500:.4f} |
| NDCG@1000 | {ndcg@1000:.4f} |
| MRR | {mrr:.4f} |
| MRR@100 | {mrr@100:.4f} |
| MRR@200 | {mrr@200:.4f} |
| MRR@500 | {mrr@500:.4f} |
| MRR@1000 | {mrr@1000:.4f} |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | {hit@1:.4f} |
| Hit@5 | {hit@5:.4f} |
| Hit@10 | {hit@10:.4f} |
| Hit@20 | {hit@20:.4f} |
| Hit@50 | {hit@50:.4f} |
| Hit@100 | {hit@100:.4f} |
| Hit@200 | {hit@200:.4f} |
| Hit@500 | {hit@500:.4f} |
| Hit@1000 | {hit@1000:.4f} |
| % GT not in top-20 | {pct_gt_not_in_top20:.1%} |
| % GT not in top-100 | {pct_gt_not_in_top100:.1%} |
| % GT not in top-200 | {pct_gt_not_in_top200:.1%} |
| % GT not in top-500 | {pct_gt_not_in_top500:.1%} |
| % GT not in top-1000 | {pct_gt_not_in_top1000:.1%} |
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

- Inference predictions: `exp/inference/devset/{tid}.json`
- Aggregate scores: `exp/scores/devset/{tid}.json`
- Per-sample metrics: `exp/scores/devset/{tid}_samples.csv`
```

Create the `experiments/` directory if it doesn't exist.

---

## Step 8 — Summary

Report to the user:

```
Experiment {tid} complete.

Inference:  exp/inference/devset/{tid}.json
Scores:     exp/scores/devset/{tid}.json
Samples:    exp/scores/devset/{tid}_samples.csv
Report:     experiments/{tid}.md

Key metrics:
  NDCG@20:  {ndcg@20}
  Hit@20:   {hit@20}
  MRR:      {mrr}
  Catalog diversity @20: {catalog_diversity}
```
