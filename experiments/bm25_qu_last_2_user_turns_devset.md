# Experiment: bm25_qu_last_2_user_turns_devset

**Date:** 2026-04-27
**Config:** `config/bm25_qu_last_2_user_turns_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |
| qu_type | last_2_user_turns |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0155 |
| NDCG@5 | 0.0302 |
| NDCG@10 | 0.0386 |
| NDCG@20 | 0.0459 |
| NDCG@50 | 0.0534 |
| NDCG@100 | 0.0581 |
| NDCG@200 | 0.0626 |
| NDCG@500 | 0.0687 |
| NDCG@1000 | 0.0734 |
| MRR | 0.0329 |
| MRR@100 | 0.0324 |
| MRR@200 | 0.0327 |
| MRR@500 | 0.0328 |
| MRR@1000 | 0.0329 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0155 |
| Hit@5 | 0.0451 |
| Hit@10 | 0.0709 |
| Hit@20 | 0.0999 |
| Hit@50 | 0.1376 |
| Hit@100 | 0.1666 |
| Hit@200 | 0.1991 |
| Hit@500 | 0.2500 |
| Hit@1000 | 0.2941 |
| % GT not in top-20 | 90.0% |
| % GT not in top-100 | 83.3% |
| % GT not in top-200 | 80.1% |
| % GT not in top-500 | 75.0% |
| % GT not in top-1000 | 70.6% |
| Mean rank (when found) | 195.2 |
| Median rank (when found) | 65.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3484 |
| Catalog diversity @100 | 0.6669 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1101 | 0.1810 | 0.2550 | 1000 |
| 2 | 0.0771 | 0.1480 | 0.2480 | 1000 |
| 3 | 0.0455 | 0.1050 | 0.1670 | 1000 |
| 4 | 0.0305 | 0.0780 | 0.1290 | 1000 |
| 5 | 0.0303 | 0.0780 | 0.1280 | 1000 |
| 6 | 0.0250 | 0.0710 | 0.1360 | 1000 |
| 7 | 0.0209 | 0.0590 | 0.1320 | 1000 |
| 8 | 0.0277 | 0.0790 | 0.1380 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_last_2_user_turns_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_last_2_user_turns_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_last_2_user_turns_devset_samples.csv`
