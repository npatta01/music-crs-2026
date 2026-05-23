# Experiment: dense_qwen3_embedding_8b_devset

**Date:** 2026-04-27
**Config:** `configs/dense_qwen3_embedding_8b_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | dense_transformer |
| retrieval_topk | 1000 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0136 |
| NDCG@5 | 0.0557 |
| NDCG@10 | 0.0804 |
| NDCG@20 | 0.1025 |
| NDCG@50 | 0.1246 |
| NDCG@100 | 0.1355 |
| NDCG@200 | 0.1451 |
| NDCG@500 | 0.1573 |
| NDCG@1000 | 0.1658 |
| MRR | 0.0627 |
| MRR@100 | 0.0618 |
| MRR@200 | 0.0623 |
| MRR@500 | 0.0626 |
| MRR@1000 | 0.0627 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0136 |
| Hit@5 | 0.1014 |
| Hit@10 | 0.1775 |
| Hit@20 | 0.2652 |
| Hit@50 | 0.3760 |
| Hit@100 | 0.4435 |
| Hit@200 | 0.5120 |
| Hit@500 | 0.6130 |
| Hit@1000 | 0.6934 |
| % GT not in top-20 | 73.5% |
| % GT not in top-100 | 55.6% |
| % GT not in top-200 | 48.8% |
| % GT not in top-500 | 38.7% |
| % GT not in top-1000 | 30.7% |
| Mean rank (when found) | 161.2 |
| Median rank (when found) | 39.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.4123 |
| Catalog diversity @100 | 0.8058 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1767 | 0.3220 | 0.4910 | 1000 |
| 2 | 0.1632 | 0.3830 | 0.5840 | 1000 |
| 3 | 0.1088 | 0.3070 | 0.4980 | 1000 |
| 4 | 0.0843 | 0.2470 | 0.4310 | 1000 |
| 5 | 0.0743 | 0.2240 | 0.4150 | 1000 |
| 6 | 0.0768 | 0.2310 | 0.3930 | 1000 |
| 7 | 0.0699 | 0.2060 | 0.3730 | 1000 |
| 8 | 0.0663 | 0.2020 | 0.3630 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/dense_qwen3_embedding_8b_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/dense_qwen3_embedding_8b_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/dense_qwen3_embedding_8b_devset_samples.csv`
