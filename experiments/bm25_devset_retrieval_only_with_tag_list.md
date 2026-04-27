# Experiment: bm25_devset_retrieval_only_with_tag_list

**Date:** 2026-04-27
**Config:** `config/bm25_devset_retrieval_only_with_tag_list.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0095 |
| NDCG@5 | 0.0453 |
| NDCG@10 | 0.0752 |
| NDCG@20 | 0.0970 |
| NDCG@50 | 0.1171 |
| NDCG@100 | 0.1277 |
| NDCG@200 | 0.1363 |
| NDCG@500 | 0.1459 |
| NDCG@1000 | 0.1522 |
| MRR | 0.0558 |
| MRR@100 | 0.0550 |
| MRR@200 | 0.0554 |
| MRR@500 | 0.0557 |
| MRR@1000 | 0.0558 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0095 |
| Hit@5 | 0.0851 |
| Hit@10 | 0.1774 |
| Hit@20 | 0.2640 |
| Hit@50 | 0.3646 |
| Hit@100 | 0.4305 |
| Hit@200 | 0.4919 |
| Hit@500 | 0.5714 |
| Hit@1000 | 0.6311 |
| % GT not in top-20 | 73.6% |
| % GT not in top-100 | 57.0% |
| % GT not in top-200 | 50.8% |
| % GT not in top-500 | 42.9% |
| % GT not in top-1000 | 36.9% |
| Mean rank (when found) | 140.5 |
| Median rank (when found) | 32.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.4542 |
| Catalog diversity @100 | 0.7626 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1330 | 0.2280 | 0.3350 | 1000 |
| 2 | 0.1400 | 0.3410 | 0.5060 | 1000 |
| 3 | 0.1054 | 0.3000 | 0.4870 | 1000 |
| 4 | 0.0928 | 0.2770 | 0.4560 | 1000 |
| 5 | 0.0804 | 0.2470 | 0.4150 | 1000 |
| 6 | 0.0799 | 0.2530 | 0.4240 | 1000 |
| 7 | 0.0765 | 0.2430 | 0.4190 | 1000 |
| 8 | 0.0680 | 0.2230 | 0.4020 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_devset_retrieval_only_with_tag_list.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_devset_retrieval_only_with_tag_list.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_devset_retrieval_only_with_tag_list_samples.csv`
