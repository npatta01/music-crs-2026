# Experiment: bm25_qu_last_3_user_turns_devset

**Date:** 2026-04-27
**Config:** `config/bm25_qu_last_3_user_turns_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |
| qu_type | last_3_user_turns |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0153 |
| NDCG@5 | 0.0292 |
| NDCG@10 | 0.0372 |
| NDCG@20 | 0.0461 |
| NDCG@50 | 0.0537 |
| NDCG@100 | 0.0587 |
| NDCG@200 | 0.0632 |
| NDCG@500 | 0.0690 |
| NDCG@1000 | 0.0739 |
| MRR | 0.0324 |
| MRR@100 | 0.0320 |
| MRR@200 | 0.0322 |
| MRR@500 | 0.0324 |
| MRR@1000 | 0.0324 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0153 |
| Hit@5 | 0.0434 |
| Hit@10 | 0.0683 |
| Hit@20 | 0.1033 |
| Hit@50 | 0.1414 |
| Hit@100 | 0.1723 |
| Hit@200 | 0.2050 |
| Hit@500 | 0.2526 |
| Hit@1000 | 0.2996 |
| % GT not in top-20 | 89.7% |
| % GT not in top-100 | 82.8% |
| % GT not in top-200 | 79.5% |
| % GT not in top-500 | 74.7% |
| % GT not in top-1000 | 70.0% |
| Mean rank (when found) | 199.0 |
| Median rank (when found) | 60.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3065 |
| Catalog diversity @100 | 0.6166 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1101 | 0.1810 | 0.2550 | 1000 |
| 2 | 0.0771 | 0.1480 | 0.2480 | 1000 |
| 3 | 0.0476 | 0.1190 | 0.1990 | 1000 |
| 4 | 0.0331 | 0.0900 | 0.1480 | 1000 |
| 5 | 0.0291 | 0.0790 | 0.1380 | 1000 |
| 6 | 0.0241 | 0.0730 | 0.1260 | 1000 |
| 7 | 0.0210 | 0.0600 | 0.1290 | 1000 |
| 8 | 0.0263 | 0.0760 | 0.1350 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_last_3_user_turns_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_last_3_user_turns_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_last_3_user_turns_devset_samples.csv`
