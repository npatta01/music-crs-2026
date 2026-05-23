# Experiment: dense_bge_large_en_v1_5_devset

**Date:** 2026-04-27
**Config:** `configs/archive/dense_bge_large_en_v1_5_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | dense_transformer |
| retrieval_topk | 1000 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0113 |
| NDCG@5 | 0.0486 |
| NDCG@10 | 0.0689 |
| NDCG@20 | 0.0865 |
| NDCG@50 | 0.1047 |
| NDCG@100 | 0.1130 |
| NDCG@200 | 0.1207 |
| NDCG@500 | 0.1299 |
| NDCG@1000 | 0.1367 |
| MRR | 0.0537 |
| MRR@100 | 0.0529 |
| MRR@200 | 0.0533 |
| MRR@500 | 0.0536 |
| MRR@1000 | 0.0537 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0113 |
| Hit@5 | 0.0871 |
| Hit@10 | 0.1499 |
| Hit@20 | 0.2195 |
| Hit@50 | 0.3111 |
| Hit@100 | 0.3624 |
| Hit@200 | 0.4169 |
| Hit@500 | 0.4936 |
| Hit@1000 | 0.5575 |
| % GT not in top-20 | 78.0% |
| % GT not in top-100 | 63.8% |
| % GT not in top-200 | 58.3% |
| % GT not in top-500 | 50.6% |
| % GT not in top-1000 | 44.2% |
| Mean rank (when found) | 157.1 |
| Median rank (when found) | 37.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3316 |
| Catalog diversity @100 | 0.6647 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1443 | 0.2440 | 0.3620 | 1000 |
| 2 | 0.1263 | 0.3120 | 0.4610 | 1000 |
| 3 | 0.0884 | 0.2370 | 0.4070 | 1000 |
| 4 | 0.0712 | 0.2050 | 0.3570 | 1000 |
| 5 | 0.0680 | 0.1950 | 0.3400 | 1000 |
| 6 | 0.0673 | 0.1930 | 0.3340 | 1000 |
| 7 | 0.0660 | 0.1920 | 0.3250 | 1000 |
| 8 | 0.0603 | 0.1780 | 0.3130 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/dense_bge_large_en_v1_5_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/dense_bge_large_en_v1_5_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/dense_bge_large_en_v1_5_devset_samples.csv`
