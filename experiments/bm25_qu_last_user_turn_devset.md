# Experiment: bm25_qu_last_user_turn_devset

**Date:** 2026-04-27
**Config:** `config/bm25_qu_last_user_turn_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |
| qu_type | last_user_turn |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0154 |
| NDCG@5 | 0.0301 |
| NDCG@10 | 0.0380 |
| NDCG@20 | 0.0448 |
| NDCG@50 | 0.0526 |
| NDCG@100 | 0.0574 |
| NDCG@200 | 0.0619 |
| NDCG@500 | 0.0668 |
| NDCG@1000 | 0.0703 |
| MRR | 0.0325 |
| MRR@100 | 0.0321 |
| MRR@200 | 0.0323 |
| MRR@500 | 0.0325 |
| MRR@1000 | 0.0325 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0154 |
| Hit@5 | 0.0446 |
| Hit@10 | 0.0690 |
| Hit@20 | 0.0964 |
| Hit@50 | 0.1356 |
| Hit@100 | 0.1653 |
| Hit@200 | 0.1971 |
| Hit@500 | 0.2379 |
| Hit@1000 | 0.2713 |
| % GT not in top-20 | 90.4% |
| % GT not in top-100 | 83.5% |
| % GT not in top-200 | 80.3% |
| % GT not in top-500 | 76.2% |
| % GT not in top-1000 | 72.9% |
| Mean rank (when found) | 173.2 |
| Median rank (when found) | 50.5 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.4335 |
| Catalog diversity @100 | 0.7645 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1101 | 0.1810 | 0.2550 | 1000 |
| 2 | 0.0635 | 0.1220 | 0.2150 | 1000 |
| 3 | 0.0396 | 0.0870 | 0.1620 | 1000 |
| 4 | 0.0298 | 0.0740 | 0.1300 | 1000 |
| 5 | 0.0336 | 0.0880 | 0.1450 | 1000 |
| 6 | 0.0276 | 0.0720 | 0.1330 | 1000 |
| 7 | 0.0278 | 0.0740 | 0.1360 | 1000 |
| 8 | 0.0264 | 0.0730 | 0.1460 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_last_user_turn_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_last_user_turn_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_last_user_turn_devset_samples.csv`
