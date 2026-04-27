# Experiment: bm25_devset_retrieval_only_tag_list_no_release_date

**Date:** 2026-04-27
**Config:** `config/bm25_devset_retrieval_only_tag_list_no_release_date.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |
| qu_type | passthrough |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0096 |
| NDCG@5 | 0.0457 |
| NDCG@10 | 0.0755 |
| NDCG@20 | 0.0972 |
| NDCG@50 | 0.1181 |
| NDCG@100 | 0.1283 |
| NDCG@200 | 0.1373 |
| NDCG@500 | 0.1468 |
| NDCG@1000 | 0.1531 |
| MRR | 0.0561 |
| MRR@100 | 0.0553 |
| MRR@200 | 0.0557 |
| MRR@500 | 0.0560 |
| MRR@1000 | 0.0561 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0096 |
| Hit@5 | 0.0859 |
| Hit@10 | 0.1781 |
| Hit@20 | 0.2640 |
| Hit@50 | 0.3686 |
| Hit@100 | 0.4320 |
| Hit@200 | 0.4959 |
| Hit@500 | 0.5749 |
| Hit@1000 | 0.6341 |
| % GT not in top-20 | 73.6% |
| % GT not in top-100 | 56.8% |
| % GT not in top-200 | 50.4% |
| % GT not in top-500 | 42.5% |
| % GT not in top-1000 | 36.6% |
| Mean rank (when found) | 139.2 |
| Median rank (when found) | 32.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.4599 |
| Catalog diversity @100 | 0.7745 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1341 | 0.2290 | 0.3310 | 1000 |
| 2 | 0.1392 | 0.3380 | 0.5100 | 1000 |
| 3 | 0.1056 | 0.2990 | 0.4910 | 1000 |
| 4 | 0.0926 | 0.2770 | 0.4580 | 1000 |
| 5 | 0.0813 | 0.2490 | 0.4200 | 1000 |
| 6 | 0.0807 | 0.2560 | 0.4250 | 1000 |
| 7 | 0.0760 | 0.2410 | 0.4170 | 1000 |
| 8 | 0.0681 | 0.2230 | 0.4040 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_devset_retrieval_only_tag_list_no_release_date.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_devset_retrieval_only_tag_list_no_release_date.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_devset_retrieval_only_tag_list_no_release_date_samples.csv`
