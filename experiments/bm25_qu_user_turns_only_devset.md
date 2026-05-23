# Experiment: bm25_qu_user_turns_only_devset

**Date:** 2026-04-27
**Config:** `configs/archive/bm25_qu_user_turns_only_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |
| qu_type | user_turns_only |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0150 |
| NDCG@5 | 0.0287 |
| NDCG@10 | 0.0379 |
| NDCG@20 | 0.0474 |
| NDCG@50 | 0.0562 |
| NDCG@100 | 0.0619 |
| NDCG@200 | 0.0663 |
| NDCG@500 | 0.0715 |
| NDCG@1000 | 0.0764 |
| MRR | 0.0329 |
| MRR@100 | 0.0325 |
| MRR@200 | 0.0327 |
| MRR@500 | 0.0328 |
| MRR@1000 | 0.0329 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0150 |
| Hit@5 | 0.0429 |
| Hit@10 | 0.0711 |
| Hit@20 | 0.1090 |
| Hit@50 | 0.1530 |
| Hit@100 | 0.1881 |
| Hit@200 | 0.2199 |
| Hit@500 | 0.2631 |
| Hit@1000 | 0.3095 |
| % GT not in top-20 | 89.1% |
| % GT not in top-100 | 81.2% |
| % GT not in top-200 | 78.0% |
| % GT not in top-500 | 73.7% |
| % GT not in top-1000 | 69.1% |
| Mean rank (when found) | 187.3 |
| Median rank (when found) | 52.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.2669 |
| Catalog diversity @100 | 0.5685 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1101 | 0.1810 | 0.2550 | 1000 |
| 2 | 0.0771 | 0.1480 | 0.2480 | 1000 |
| 3 | 0.0476 | 0.1190 | 0.1990 | 1000 |
| 4 | 0.0349 | 0.0970 | 0.1720 | 1000 |
| 5 | 0.0322 | 0.0940 | 0.1780 | 1000 |
| 6 | 0.0254 | 0.0800 | 0.1590 | 1000 |
| 7 | 0.0275 | 0.0800 | 0.1490 | 1000 |
| 8 | 0.0248 | 0.0730 | 0.1450 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_user_turns_only_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_user_turns_only_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_user_turns_only_devset_samples.csv`
