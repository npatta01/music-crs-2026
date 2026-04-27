# Experiment: dense_bge_base_en_v1_5_devset

**Date:** 2026-04-27
**Config:** `config/dense_bge_base_en_v1_5_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | dense_transformer |
| retrieval_topk | 1000 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0110 |
| NDCG@5 | 0.0486 |
| NDCG@10 | 0.0674 |
| NDCG@20 | 0.0836 |
| NDCG@50 | 0.1007 |
| NDCG@100 | 0.1094 |
| NDCG@200 | 0.1167 |
| NDCG@500 | 0.1254 |
| NDCG@1000 | 0.1320 |
| MRR | 0.0525 |
| MRR@100 | 0.0518 |
| MRR@200 | 0.0521 |
| MRR@500 | 0.0524 |
| MRR@1000 | 0.0525 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0110 |
| Hit@5 | 0.0875 |
| Hit@10 | 0.1456 |
| Hit@20 | 0.2097 |
| Hit@50 | 0.2951 |
| Hit@100 | 0.3484 |
| Hit@200 | 0.4006 |
| Hit@500 | 0.4726 |
| Hit@1000 | 0.5351 |
| % GT not in top-20 | 79.0% |
| % GT not in top-100 | 65.2% |
| % GT not in top-200 | 59.9% |
| % GT not in top-500 | 52.7% |
| % GT not in top-1000 | 46.5% |
| Mean rank (when found) | 158.1 |
| Median rank (when found) | 36.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3611 |
| Catalog diversity @100 | 0.7155 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1342 | 0.2320 | 0.3510 | 1000 |
| 2 | 0.1264 | 0.3040 | 0.4510 | 1000 |
| 3 | 0.0821 | 0.2190 | 0.3740 | 1000 |
| 4 | 0.0710 | 0.1990 | 0.3490 | 1000 |
| 5 | 0.0661 | 0.1840 | 0.3170 | 1000 |
| 6 | 0.0664 | 0.1910 | 0.3320 | 1000 |
| 7 | 0.0652 | 0.1830 | 0.3140 | 1000 |
| 8 | 0.0577 | 0.1660 | 0.2990 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/dense_bge_base_en_v1_5_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/dense_bge_base_en_v1_5_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/dense_bge_base_en_v1_5_devset_samples.csv`
