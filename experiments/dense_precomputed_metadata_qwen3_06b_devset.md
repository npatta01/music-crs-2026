# Experiment: dense_precomputed_metadata_qwen3_06b_devset

**Date:** 2026-04-28
**Config:** `config/dense_precomputed_metadata_qwen3_06b_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | precomputed_embedding |
| retrieval_topk | 1000 |
| embedding_column | metadata-qwen3_embedding_0.6b |
| query encoder | Qwen/Qwen3-Embedding-0.6B |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0176 |
| NDCG@5 | 0.0392 |
| NDCG@10 | 0.0534 |
| NDCG@20 | 0.0665 |
| NDCG@50 | 0.0787 |
| NDCG@100 | 0.0853 |
| NDCG@200 | 0.0911 |
| NDCG@500 | 0.0975 |
| NDCG@1000 | 0.1029 |
| MRR | 0.0443 |
| MRR@100 | 0.0437 |
| MRR@200 | 0.0440 |
| MRR@500 | 0.0442 |
| MRR@1000 | 0.0443 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0176 |
| Hit@5 | 0.0623 |
| Hit@10 | 0.1065 |
| Hit@20 | 0.1580 |
| Hit@50 | 0.2195 |
| Hit@100 | 0.2598 |
| Hit@200 | 0.3011 |
| Hit@500 | 0.3543 |
| Hit@1000 | 0.4060 |
| % GT not in top-20 | 84.2% |
| % GT not in top-100 | 74.0% |
| % GT not in top-200 | 69.9% |
| % GT not in top-500 | 64.6% |
| % GT not in top-1000 | 59.4% |
| Mean rank (when found) | 165.9 |
| Median rank (when found) | 39.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3619 |
| Catalog diversity @100 | 0.6961 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1302 | 0.213 | 0.300 | 1000 |
| 2 | 0.0978 | 0.208 | 0.323 | 1000 |
| 3 | 0.0734 | 0.176 | 0.280 | 1000 |
| 4 | 0.0535 | 0.152 | 0.270 | 1000 |
| 5 | 0.0540 | 0.152 | 0.237 | 1000 |
| 6 | 0.0466 | 0.138 | 0.233 | 1000 |
| 7 | 0.0396 | 0.117 | 0.214 | 1000 |
| 8 | 0.0367 | 0.108 | 0.221 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/dense_precomputed_metadata_qwen3_06b_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/dense_precomputed_metadata_qwen3_06b_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/dense_precomputed_metadata_qwen3_06b_devset_samples.csv`
