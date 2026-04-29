# Experiment: dense_precomputed_attributes_qwen3_06b_devset

**Date:** 2026-04-28
**Config:** `config/dense_precomputed_attributes_qwen3_06b_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | precomputed_embedding |
| retrieval_topk | 1000 |
| embedding_column | attributes-qwen3_embedding_0.6b |
| query encoder | Qwen/Qwen3-Embedding-0.6B |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0096 |
| NDCG@5 | 0.0198 |
| NDCG@10 | 0.0257 |
| NDCG@20 | 0.0317 |
| NDCG@50 | 0.0408 |
| NDCG@100 | 0.0474 |
| NDCG@200 | 0.0550 |
| NDCG@500 | 0.0659 |
| NDCG@1000 | 0.0751 |
| MRR | 0.0233 |
| MRR@100 | 0.0225 |
| MRR@200 | 0.0229 |
| MRR@500 | 0.0232 |
| MRR@1000 | 0.0233 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0096 |
| Hit@5 | 0.0301 |
| Hit@10 | 0.0483 |
| Hit@20 | 0.0723 |
| Hit@50 | 0.1188 |
| Hit@100 | 0.1591 |
| Hit@200 | 0.2135 |
| Hit@500 | 0.3041 |
| Hit@1000 | 0.3915 |
| % GT not in top-20 | 92.8% |
| % GT not in top-100 | 84.1% |
| % GT not in top-200 | 78.7% |
| % GT not in top-500 | 69.6% |
| % GT not in top-1000 | 60.9% |
| Mean rank (when found) | 272.9 |
| Median rank (when found) | 161.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3087 |
| Catalog diversity @100 | 0.6217 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.0393 | 0.084 | 0.162 | 1000 |
| 2 | 0.0357 | 0.082 | 0.190 | 1000 |
| 3 | 0.0396 | 0.084 | 0.195 | 1000 |
| 4 | 0.0328 | 0.077 | 0.172 | 1000 |
| 5 | 0.0348 | 0.082 | 0.158 | 1000 |
| 6 | 0.0266 | 0.059 | 0.145 | 1000 |
| 7 | 0.0237 | 0.056 | 0.134 | 1000 |
| 8 | 0.0208 | 0.054 | 0.117 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/dense_precomputed_attributes_qwen3_06b_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/dense_precomputed_attributes_qwen3_06b_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/dense_precomputed_attributes_qwen3_06b_devset_samples.csv`
