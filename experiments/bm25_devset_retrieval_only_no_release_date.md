# Experiment: bm25_devset_retrieval_only_no_release_date

**Date:** 2026-04-27
**Config:** `configs/archive/bm25_devset_retrieval_only_no_release_date.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0099 |
| NDCG@5 | 0.0389 |
| NDCG@10 | 0.0649 |
| NDCG@20 | 0.0829 |
| NDCG@50 | 0.0986 |
| NDCG@100 | 0.1046 |
| NDCG@200 | 0.1086 |
| NDCG@500 | 0.1126 |
| NDCG@1000 | 0.1156 |
| MRR | 0.0477 |
| MRR@100 | 0.0473 |
| MRR@200 | 0.0475 |
| MRR@500 | 0.0476 |
| MRR@1000 | 0.0477 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0099 |
| Hit@5 | 0.0711 |
| Hit@10 | 0.1515 |
| Hit@20 | 0.2230 |
| Hit@50 | 0.3014 |
| Hit@100 | 0.3379 |
| Hit@200 | 0.3665 |
| Hit@500 | 0.3995 |
| Hit@1000 | 0.4280 |
| % GT not in top-20 | 77.7% |
| % GT not in top-100 | 66.2% |
| % GT not in top-200 | 63.3% |
| % GT not in top-500 | 60.1% |
| % GT not in top-1000 | 57.2% |
| Mean rank (when found) | 99.0 |
| Median rank (when found) | 18.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3906 |
| Catalog diversity @100 | 0.7146 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1129 | 0.1840 | 0.2550 | 1000 |
| 2 | 0.1201 | 0.2940 | 0.4170 | 1000 |
| 3 | 0.0928 | 0.2520 | 0.3760 | 1000 |
| 4 | 0.0743 | 0.2200 | 0.3480 | 1000 |
| 5 | 0.0713 | 0.2230 | 0.3340 | 1000 |
| 6 | 0.0670 | 0.2130 | 0.3300 | 1000 |
| 7 | 0.0617 | 0.1970 | 0.3120 | 1000 |
| 8 | 0.0634 | 0.2010 | 0.3310 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_devset_retrieval_only_no_release_date.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_devset_retrieval_only_no_release_date.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_devset_retrieval_only_no_release_date_samples.csv`
