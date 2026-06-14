# Experiment: v0plus_compiler_devset_rr2

**Date:** 2026-06-13
**Config:** `configs/v0plus_compiler_devset_rr2.yaml`
**Backend:** Modal, 50-shard full devset run
**Modal app:** `ap-yGC8XRyqWw701zWnoujA7Q` (run id `20260613T164013Z-bf39ef`)
**Git SHA:** `06229863e52a2aa5262fbfc558af8763c1c8cdab`

## Summary

Full devset run for the current LambdaMART v9 reranker submission path. The
wrapper merged 8,000 unique prediction rows and 8,000 unique trace rows from 50
shards, then evaluated locally and merged branch union diagnostics into the
scores JSON.

One warning appeared during inference: `v0+ empty result: compiler returned 0
candidates (async)` for a single turn with hard filters. The merged artifact
still has 8,000 prediction rows; the evaluator reports all rows are shallow only
because this reranker config intentionally emits top-20 output.

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| qu_type | v0plus_compiler |
| retrieval_topk | 20 |
| compiler.final_topk | 1000 |
| reranker | `lgbm_v9`, `models/reranker_v9/model.txt` |

## Diagnostic Depth

| Field | Value |
|---|---:|
| Turns evaluated | 8000 |
| Min / Max pool depth | 20 / 20 |
| Shallow rows | 8000 |
| Full diagnostic depth required | false |

## Ranking Quality

| Metric | Value |
|---|---:|
| NDCG@1 | 0.2127 |
| NDCG@5 | 0.3024 |
| NDCG@10 | 0.3259 |
| NDCG@20 | 0.3450 |
| NDCG@50 | 0.3450 |
| NDCG@100 | 0.3450 |
| NDCG@200 | 0.3450 |
| NDCG@500 | 0.3450 |
| NDCG@1000 | 0.3450 |
| MRR | 0.2908 |
| MRR@100 | 0.2908 |
| MRR@200 | 0.2908 |
| MRR@500 | 0.2908 |
| MRR@1000 | 0.2908 |

## Retrieval Coverage

| Metric | Value |
|---|---:|
| Hit@1 | 0.2127 |
| Hit@5 | 0.3828 |
| Hit@10 | 0.4551 |
| Hit@20 | 0.5305 |
| Hit@50 | 0.5305 |
| Hit@100 | 0.5305 |
| Hit@200 | 0.5305 |
| Hit@500 | 0.5305 |
| Hit@1000 | 0.5305 |
| % GT not in top-20 | 46.9% |
| % GT not in top-100 | 46.9% |
| % GT not in top-200 | 46.9% |
| % GT not in top-500 | 46.9% |
| % GT not in top-1000 | 46.9% |
| Mean rank when found | 4.5 |
| Median rank when found | 2.0 |

## Branch Union Coverage

For reranker runs, `union@20` is not a strict ceiling for final Hit@20: the
reranker scores a deeper branch-pool union and can move candidates from deeper
branch ranks into the submitted top 20.

| k | union@k | final Hit@k | final / union |
|---|---:|---:|---:|
| 20 | 0.4304 | 0.5305 | 1.233 |
| 50 | 0.5397 | 0.5305 | 0.983 |
| 100 | 0.6259 | 0.5305 | 0.848 |
| 200 | 0.7218 | 0.5305 | 0.735 |
| 1000 | 0.8924 | 0.5305 | 0.594 |

## Diversity

| Metric | Value |
|---|---:|
| Catalog diversity @20 | 0.5303 |
| Catalog diversity @100 | 0.5303 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---:|---:|---:|---:|---:|
| 1 | 0.3255 | 0.5220 | 0.5220 | 1000 |
| 2 | 0.4175 | 0.6130 | 0.6130 | 1000 |
| 3 | 0.3656 | 0.5540 | 0.5540 | 1000 |
| 4 | 0.3531 | 0.5410 | 0.5410 | 1000 |
| 5 | 0.3349 | 0.5300 | 0.5300 | 1000 |
| 6 | 0.3174 | 0.4980 | 0.4980 | 1000 |
| 7 | 0.3116 | 0.4820 | 0.4820 | 1000 |
| 8 | 0.3347 | 0.5040 | 0.5040 | 1000 |

## Files

- Inference predictions: `exp/inference/devset/v0plus_compiler_devset_rr2.json`
- Trace: `exp/inference/devset/v0plus_compiler_devset_rr2_trace.jsonl`
- Aggregate scores: `exp/scores/devset/v0plus_compiler_devset_rr2.json`
- Branch diagnostics: `exp/scores/devset/v0plus_compiler_devset_rr2_branch_diagnostics.json`
- Per-sample metrics: `exp/scores/devset/v0plus_compiler_devset_rr2_samples.csv`
