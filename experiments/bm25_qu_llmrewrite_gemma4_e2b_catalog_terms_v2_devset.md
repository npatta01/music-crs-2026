# Experiment: bm25_qu_llmrewrite_gemma4_e2b_catalog_terms_v2_devset

**Date:** 2026-04-27
**Config:** `config/bm25_qu_llmrewrite_gemma4_e2b_catalog_terms_v2_devset.yaml`

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
| NDCG@1 | 0.0250 |
| NDCG@5 | 0.0702 |
| NDCG@10 | 0.0919 |
| NDCG@20 | 0.1089 |
| NDCG@50 | 0.1261 |
| NDCG@100 | 0.1346 |
| NDCG@200 | 0.1412 |
| NDCG@500 | 0.1498 |
| NDCG@1000 | 0.1565 |
| MRR | 0.0732 |
| MRR@100 | 0.0725 |
| MRR@200 | 0.0729 |
| MRR@500 | 0.0731 |
| MRR@1000 | 0.0732 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0250 |
| Hit@5 | 0.1157 |
| Hit@10 | 0.1826 |
| Hit@20 | 0.2500 |
| Hit@50 | 0.3366 |
| Hit@100 | 0.3886 |
| Hit@200 | 0.4355 |
| Hit@500 | 0.5074 |
| Hit@1000 | 0.5713 |
| % GT not in top-20 | 75.0% |
| % GT not in top-100 | 61.1% |
| % GT not in top-200 | 56.5% |
| % GT not in top-500 | 49.3% |
| % GT not in top-1000 | 42.9% |
| Mean rank (when found) | 150.6 |
| Median rank (when found) | 29.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.6888 |
| Catalog diversity @100 | 0.9625 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_gemma4_e2b_catalog_terms_v2_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_gemma4_e2b_catalog_terms_v2_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_gemma4_e2b_catalog_terms_v2_devset_samples.csv`
