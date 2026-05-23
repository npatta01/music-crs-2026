# Experiment: bm25_devset_retrieval_only_tag_list_only

**Date:** 2026-04-27
**Config:** `configs/archive/bm25_devset_retrieval_only_tag_list_only.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0050 |
| NDCG@5 | 0.0317 |
| NDCG@10 | 0.0483 |
| NDCG@20 | 0.0635 |
| NDCG@50 | 0.0793 |
| NDCG@100 | 0.0886 |
| NDCG@200 | 0.0968 |
| NDCG@500 | 0.1065 |
| NDCG@1000 | 0.1135 |
| MRR | 0.0374 |
| MRR@100 | 0.0367 |
| MRR@200 | 0.0371 |
| MRR@500 | 0.0373 |
| MRR@1000 | 0.0374 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0050 |
| Hit@5 | 0.0609 |
| Hit@10 | 0.1125 |
| Hit@20 | 0.1725 |
| Hit@50 | 0.2515 |
| Hit@100 | 0.3091 |
| Hit@200 | 0.3675 |
| Hit@500 | 0.4480 |
| Hit@1000 | 0.5144 |
| % GT not in top-20 | 82.8% |
| % GT not in top-100 | 69.1% |
| % GT not in top-200 | 63.2% |
| % GT not in top-500 | 55.2% |
| % GT not in top-1000 | 48.6% |
| Mean rank (when found) | 178.8 |
| Median rank (when found) | 54.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3814 |
| Catalog diversity @100 | 0.6344 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.0604 | 0.1200 | 0.2080 | 1000 |
| 2 | 0.0928 | 0.2280 | 0.3730 | 1000 |
| 3 | 0.0732 | 0.2000 | 0.3600 | 1000 |
| 4 | 0.0698 | 0.1960 | 0.3430 | 1000 |
| 5 | 0.0578 | 0.1620 | 0.2980 | 1000 |
| 6 | 0.0546 | 0.1640 | 0.3110 | 1000 |
| 7 | 0.0552 | 0.1690 | 0.3100 | 1000 |
| 8 | 0.0444 | 0.1410 | 0.2700 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_devset_retrieval_only_tag_list_only.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_devset_retrieval_only_tag_list_only.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_devset_retrieval_only_tag_list_only_samples.csv`
