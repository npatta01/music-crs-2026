# Experiment: v0plus_compiler_image_devset

**Date:** 2026-05-28
**Config:** `configs/v0plus_compiler_image_devset.yaml`
**Backend:** Modal
**Prediction git head:** `05133129b7e9556eba52cc89cf6cb4f48116f444`
**Status:** `analyzed`

## Summary

`v0plus_compiler_image_devset` still behaves like the canonical image-signal config after the PR #66 bugfixes. The head metrics are essentially flat versus the prior 2026-05-26 image ablation, while deeper retrieval coverage is higher.

| Comparison | NDCG@20 | Hit@20 | Hit@100 | Hit@1000 | MRR |
|---|---:|---:|---:|---:|---:|
| Prior image ablation | 0.1461 | 0.300 | 0.440 | 0.598 | 0.107 |
| Current bugfix run | 0.1452 | 0.2989 | 0.4450 | 0.6261 | 0.1062 |
| Delta | -0.0009 | -0.0011 | +0.0050 | +0.0281 | -0.0008 |

Verdict: not materially better on headline top-20 quality after the bugfixes, but not meaningfully worse either. The useful change is correctness plus improved deep-pool coverage; this run remains far above the BM25 baseline from the ablation (`0.1452` vs `0.0984` NDCG@20, +47.6%).

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| qu_type | v0plus_compiler |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |
| dense branches | disabled |
| centroid-only branches | `image_siglip2` |

## Diagnostic Depth

| Field | Value |
|---|---:|
| Turns evaluated | 8000 |
| require_full_diagnostic_depth | false |
| Target diagnostic depth | 1000 |
| Min pool depth | 0 |
| Max pool depth | 1000 |
| Shallow rows | 81 |
| Available cutoffs | 1, 5, 10, 20, 50, 100, 200, 500, 1000 |

The evaluator now reports numeric cutoff metrics even when a row returns fewer than 1000 candidates. If the GT is in the returned pool, it receives credit at deeper cutoffs; if it is absent, the missing tail counts as a miss.

## Ranking Quality

| Metric | Value |
|---|---:|
| NDCG@1 | 0.0519 |
| NDCG@5 | 0.1038 |
| NDCG@10 | 0.1260 |
| NDCG@20 | 0.1452 |
| NDCG@50 | 0.1634 |
| NDCG@100 | 0.1724 |
| NDCG@200 | 0.1794 |
| NDCG@500 | 0.1885 |
| NDCG@1000 | 0.1944 |
| MRR | 0.1062 |
| MRR@100 | 0.1056 |
| MRR@200 | 0.1059 |
| MRR@500 | 0.1062 |
| MRR@1000 | 0.1062 |

## Retrieval Coverage

| Metric | Value |
|---|---:|
| Hit@1 | 0.0519 |
| Hit@5 | 0.1535 |
| Hit@10 | 0.2228 |
| Hit@20 | 0.2989 |
| Hit@50 | 0.3896 |
| Hit@100 | 0.4450 |
| Hit@200 | 0.4952 |
| Hit@500 | 0.5704 |
| Hit@1000 | 0.6261 |
| % GT not in top-20 | 70.1% |
| % GT not in top-100 | 55.5% |
| % GT not in top-200 | 50.5% |
| % GT not in top-500 | 43.0% |
| % GT not in top-1000 | 37.4% |
| Mean rank when found | 130.8 |
| Median rank when found | 23.0 |

## Diversity

| Metric | Value |
|---|---:|
| Catalog diversity @20 | 0.5428 |
| Catalog diversity @100 | 0.8876 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---:|---:|---:|---:|---:|
| 1 | 0.1317 | 0.2380 | 0.3520 | 1000 |
| 2 | 0.1837 | 0.3570 | 0.5030 | 1000 |
| 3 | 0.1551 | 0.3310 | 0.4870 | 1000 |
| 4 | 0.1389 | 0.3050 | 0.4570 | 1000 |
| 5 | 0.1431 | 0.3050 | 0.4510 | 1000 |
| 6 | 0.1323 | 0.2860 | 0.4370 | 1000 |
| 7 | 0.1416 | 0.2860 | 0.4240 | 1000 |
| 8 | 0.1356 | 0.2830 | 0.4490 | 1000 |

## Files

- Inference predictions: `exp/inference/devset/v0plus_compiler_image_devset.json`
- Aggregate scores: `exp/scores/devset/v0plus_compiler_image_devset.json`
- Per-sample metrics: `exp/scores/devset/v0plus_compiler_image_devset_samples.csv`
