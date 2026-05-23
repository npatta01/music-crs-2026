# Experiment: dense_e5_large_v2_devset

**Date:** 2026-04-27
**Config:** `configs/archive/dense_e5_large_v2_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | dense_transformer |
| retrieval_topk | 1000 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0105 |
| NDCG@5 | 0.0493 |
| NDCG@10 | 0.0725 |
| NDCG@20 | 0.0895 |
| NDCG@50 | 0.1041 |
| NDCG@100 | 0.1120 |
| NDCG@200 | 0.1178 |
| NDCG@500 | 0.1266 |
| NDCG@1000 | 0.1333 |
| MRR | 0.0537 |
| MRR@100 | 0.0531 |
| MRR@200 | 0.0534 |
| MRR@500 | 0.0537 |
| MRR@1000 | 0.0537 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0105 |
| Hit@5 | 0.0913 |
| Hit@10 | 0.1629 |
| Hit@20 | 0.2300 |
| Hit@50 | 0.3029 |
| Hit@100 | 0.3513 |
| Hit@200 | 0.3931 |
| Hit@500 | 0.4664 |
| Hit@1000 | 0.5290 |
| % GT not in top-20 | 77.0% |
| % GT not in top-100 | 64.9% |
| % GT not in top-200 | 60.7% |
| % GT not in top-500 | 53.4% |
| % GT not in top-1000 | 47.1% |
| Mean rank (when found) | 156.7 |
| Median rank (when found) | 31.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3509 |
| Catalog diversity @100 | 0.6394 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1444 | 0.2490 | 0.3620 | 1000 |
| 2 | 0.1354 | 0.3300 | 0.4430 | 1000 |
| 3 | 0.0949 | 0.2610 | 0.3930 | 1000 |
| 4 | 0.0775 | 0.2200 | 0.3500 | 1000 |
| 5 | 0.0695 | 0.2080 | 0.3280 | 1000 |
| 6 | 0.0705 | 0.2070 | 0.3360 | 1000 |
| 7 | 0.0641 | 0.1890 | 0.3050 | 1000 |
| 8 | 0.0599 | 0.1760 | 0.2930 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/dense_e5_large_v2_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/dense_e5_large_v2_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/dense_e5_large_v2_devset_samples.csv`
