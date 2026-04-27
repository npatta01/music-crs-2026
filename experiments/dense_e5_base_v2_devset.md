# Experiment: dense_e5_base_v2_devset

**Date:** 2026-04-27
**Config:** `config/dense_e5_base_v2_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | dense_transformer |
| retrieval_topk | 1000 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0115 |
| NDCG@5 | 0.0511 |
| NDCG@10 | 0.0728 |
| NDCG@20 | 0.0906 |
| NDCG@50 | 0.1064 |
| NDCG@100 | 0.1144 |
| NDCG@200 | 0.1216 |
| NDCG@500 | 0.1302 |
| NDCG@1000 | 0.1375 |
| MRR | 0.0552 |
| MRR@100 | 0.0545 |
| MRR@200 | 0.0548 |
| MRR@500 | 0.0551 |
| MRR@1000 | 0.0552 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0115 |
| Hit@5 | 0.0938 |
| Hit@10 | 0.1605 |
| Hit@20 | 0.2310 |
| Hit@50 | 0.3099 |
| Hit@100 | 0.3593 |
| Hit@200 | 0.4113 |
| Hit@500 | 0.4825 |
| Hit@1000 | 0.5520 |
| % GT not in top-20 | 76.9% |
| % GT not in top-100 | 64.1% |
| % GT not in top-200 | 58.9% |
| % GT not in top-500 | 51.7% |
| % GT not in top-1000 | 44.8% |
| Mean rank (when found) | 163.6 |
| Median rank (when found) | 33.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3612 |
| Catalog diversity @100 | 0.6973 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1467 | 0.2500 | 0.3600 | 1000 |
| 2 | 0.1361 | 0.3250 | 0.4450 | 1000 |
| 3 | 0.0926 | 0.2500 | 0.3910 | 1000 |
| 4 | 0.0733 | 0.2120 | 0.3650 | 1000 |
| 5 | 0.0707 | 0.2130 | 0.3400 | 1000 |
| 6 | 0.0723 | 0.2060 | 0.3390 | 1000 |
| 7 | 0.0700 | 0.2080 | 0.3130 | 1000 |
| 8 | 0.0631 | 0.1840 | 0.3210 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/dense_e5_base_v2_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/dense_e5_base_v2_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/dense_e5_base_v2_devset_samples.csv`
