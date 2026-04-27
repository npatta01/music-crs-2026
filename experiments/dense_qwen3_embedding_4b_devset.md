# Experiment: dense_qwen3_embedding_4b_devset

**Date:** 2026-04-27
**Config:** `config/dense_qwen3_embedding_4b_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | dense_transformer |
| retrieval_topk | 1000 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0175 |
| NDCG@5 | 0.0576 |
| NDCG@10 | 0.0788 |
| NDCG@20 | 0.0994 |
| NDCG@50 | 0.1204 |
| NDCG@100 | 0.1320 |
| NDCG@200 | 0.1420 |
| NDCG@500 | 0.1544 |
| NDCG@1000 | 0.1630 |
| MRR | 0.0635 |
| MRR@100 | 0.0625 |
| MRR@200 | 0.0630 |
| MRR@500 | 0.0633 |
| MRR@1000 | 0.0635 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0175 |
| Hit@5 | 0.1004 |
| Hit@10 | 0.1661 |
| Hit@20 | 0.2479 |
| Hit@50 | 0.3536 |
| Hit@100 | 0.4250 |
| Hit@200 | 0.4965 |
| Hit@500 | 0.5996 |
| Hit@1000 | 0.6803 |
| % GT not in top-20 | 75.2% |
| % GT not in top-100 | 57.5% |
| % GT not in top-200 | 50.3% |
| % GT not in top-500 | 40.0% |
| % GT not in top-1000 | 32.0% |
| Mean rank (when found) | 166.5 |
| Median rank (when found) | 45.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3679 |
| Catalog diversity @100 | 0.7343 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1680 | 0.3030 | 0.4740 | 1000 |
| 2 | 0.1710 | 0.3780 | 0.5700 | 1000 |
| 3 | 0.1069 | 0.2890 | 0.4960 | 1000 |
| 4 | 0.0803 | 0.2340 | 0.4230 | 1000 |
| 5 | 0.0722 | 0.2110 | 0.3930 | 1000 |
| 6 | 0.0737 | 0.2120 | 0.3650 | 1000 |
| 7 | 0.0626 | 0.1790 | 0.3490 | 1000 |
| 8 | 0.0603 | 0.1770 | 0.3300 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/dense_qwen3_embedding_4b_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/dense_qwen3_embedding_4b_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/dense_qwen3_embedding_4b_devset_samples.csv`
