# Experiment: bm25_qu_llmrewrite_qwen3_4b_catalog_terms_v2_devset

**Date:** 2026-04-27
**Config:** `config/bm25_qu_llmrewrite_qwen3_4b_catalog_terms_v2_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |
| qu_type | llm_rewrite |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0253 |
| NDCG@5 | 0.0665 |
| NDCG@10 | 0.0878 |
| NDCG@20 | 0.1055 |
| NDCG@50 | 0.1256 |
| NDCG@100 | 0.1360 |
| NDCG@200 | 0.1453 |
| NDCG@500 | 0.1556 |
| NDCG@1000 | 0.1626 |
| MRR | 0.0713 |
| MRR@100 | 0.0705 |
| MRR@200 | 0.0710 |
| MRR@500 | 0.0713 |
| MRR@1000 | 0.0713 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0253 |
| Hit@5 | 0.1087 |
| Hit@10 | 0.1749 |
| Hit@20 | 0.2451 |
| Hit@50 | 0.3459 |
| Hit@100 | 0.4096 |
| Hit@200 | 0.4767 |
| Hit@500 | 0.5623 |
| Hit@1000 | 0.6281 |
| % GT not in top-20 | 75.5% |
| % GT not in top-100 | 59.0% |
| % GT not in top-200 | 52.3% |
| % GT not in top-500 | 43.8% |
| % GT not in top-1000 | 37.2% |
| Mean rank (when found) | 151.0 |
| Median rank (when found) | 38.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.5769 |
| Catalog diversity @100 | 0.8845 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_qwen3_4b_catalog_terms_v2_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen3_4b_catalog_terms_v2_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen3_4b_catalog_terms_v2_devset_samples.csv`
