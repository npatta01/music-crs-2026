# Experiment: bm25_qu_llmrewrite_smollm2_1p7b_catalog_terms_v2_devset

**Date:** 2026-04-27
**Config:** `config/bm25_qu_llmrewrite_smollm2_1p7b_catalog_terms_v2_devset.yaml`

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
| NDCG@1 | 0.0116 |
| NDCG@5 | 0.0463 |
| NDCG@10 | 0.0756 |
| NDCG@20 | 0.0976 |
| NDCG@50 | 0.1185 |
| NDCG@100 | 0.1286 |
| NDCG@200 | 0.1375 |
| NDCG@500 | 0.1469 |
| NDCG@1000 | 0.1531 |
| MRR | 0.0569 |
| MRR@100 | 0.0561 |
| MRR@200 | 0.0566 |
| MRR@500 | 0.0568 |
| MRR@1000 | 0.0569 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0116 |
| Hit@5 | 0.0858 |
| Hit@10 | 0.1761 |
| Hit@20 | 0.2632 |
| Hit@50 | 0.3678 |
| Hit@100 | 0.4303 |
| Hit@200 | 0.4941 |
| Hit@500 | 0.5717 |
| Hit@1000 | 0.6309 |
| % GT not in top-20 | 73.7% |
| % GT not in top-100 | 57.0% |
| % GT not in top-200 | 50.6% |
| % GT not in top-500 | 42.8% |
| % GT not in top-1000 | 36.9% |
| Mean rank (when found) | 139.7 |
| Median rank (when found) | 31.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.5157 |
| Catalog diversity @100 | 0.8537 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_smollm2_1p7b_catalog_terms_v2_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_smollm2_1p7b_catalog_terms_v2_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_smollm2_1p7b_catalog_terms_v2_devset_samples.csv`
