# Experiment: bm25_qu_llmrewrite_qwen25_3b_catalog_terms_v2_devset

**Date:** 2026-04-27
**Config:** `configs/archive/bm25_qu_llmrewrite_qwen25_3b_catalog_terms_v2_devset.yaml`

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
| NDCG@1 | 0.0201 |
| NDCG@5 | 0.0623 |
| NDCG@10 | 0.0836 |
| NDCG@20 | 0.1008 |
| NDCG@50 | 0.1169 |
| NDCG@100 | 0.1254 |
| NDCG@200 | 0.1327 |
| NDCG@500 | 0.1422 |
| NDCG@1000 | 0.1496 |
| MRR | 0.0660 |
| MRR@100 | 0.0653 |
| MRR@200 | 0.0656 |
| MRR@500 | 0.0659 |
| MRR@1000 | 0.0660 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0201 |
| Hit@5 | 0.1049 |
| Hit@10 | 0.1707 |
| Hit@20 | 0.2390 |
| Hit@50 | 0.3198 |
| Hit@100 | 0.3725 |
| Hit@200 | 0.4245 |
| Hit@500 | 0.5035 |
| Hit@1000 | 0.5740 |
| % GT not in top-20 | 76.1% |
| % GT not in top-100 | 62.7% |
| % GT not in top-200 | 57.6% |
| % GT not in top-500 | 49.6% |
| % GT not in top-1000 | 42.6% |
| Mean rank (when found) | 164.0 |
| Median rank (when found) | 35.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.7166 |
| Catalog diversity @100 | 0.9710 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_qwen25_3b_catalog_terms_v2_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen25_3b_catalog_terms_v2_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen25_3b_catalog_terms_v2_devset_samples.csv`
