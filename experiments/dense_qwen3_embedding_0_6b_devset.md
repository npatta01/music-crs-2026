# Experiment: dense_qwen3_embedding_0_6b_devset

**Date:** 2026-04-27
**Config:** `config/dense_qwen3_embedding_0_6b_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | dense_transformer |
| retrieval_topk | 1000 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0169 |
| NDCG@5 | 0.0497 |
| NDCG@10 | 0.0688 |
| NDCG@20 | 0.0849 |
| NDCG@50 | 0.1012 |
| NDCG@100 | 0.1098 |
| NDCG@200 | 0.1175 |
| NDCG@500 | 0.1274 |
| NDCG@1000 | 0.1343 |
| MRR | 0.0546 |
| MRR@100 | 0.0539 |
| MRR@200 | 0.0543 |
| MRR@500 | 0.0545 |
| MRR@1000 | 0.0546 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0169 |
| Hit@5 | 0.0855 |
| Hit@10 | 0.1445 |
| Hit@20 | 0.2079 |
| Hit@50 | 0.2898 |
| Hit@100 | 0.3427 |
| Hit@200 | 0.3976 |
| Hit@500 | 0.4800 |
| Hit@1000 | 0.5454 |
| % GT not in top-20 | 79.2% |
| % GT not in top-100 | 65.7% |
| % GT not in top-200 | 60.2% |
| % GT not in top-500 | 52.0% |
| % GT not in top-1000 | 45.5% |
| Mean rank (when found) | 165.7 |
| Median rank (when found) | 42.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3373 |
| Catalog diversity @100 | 0.6648 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1434 | 0.2480 | 0.3890 | 1000 |
| 2 | 0.1223 | 0.2630 | 0.4040 | 1000 |
| 3 | 0.0916 | 0.2410 | 0.3870 | 1000 |
| 4 | 0.0759 | 0.2100 | 0.3470 | 1000 |
| 5 | 0.0690 | 0.1940 | 0.3240 | 1000 |
| 6 | 0.0674 | 0.1830 | 0.3120 | 1000 |
| 7 | 0.0524 | 0.1560 | 0.2880 | 1000 |
| 8 | 0.0569 | 0.1680 | 0.2910 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/dense_qwen3_embedding_0_6b_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/dense_qwen3_embedding_0_6b_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/dense_qwen3_embedding_0_6b_devset_samples.csv`
