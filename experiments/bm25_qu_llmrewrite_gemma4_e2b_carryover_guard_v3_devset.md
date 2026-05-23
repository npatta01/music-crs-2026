# Experiment: bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset

**Date:** 2026-04-27
**Config:** `configs/archive/bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.yaml`

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
| NDCG@1 | 0.0143 |
| NDCG@5 | 0.0684 |
| NDCG@10 | 0.0921 |
| NDCG@20 | 0.1092 |
| NDCG@50 | 0.1254 |
| NDCG@100 | 0.1320 |
| NDCG@200 | 0.1386 |
| NDCG@500 | 0.1468 |
| NDCG@1000 | 0.1529 |
| MRR | 0.0695 |
| MRR@100 | 0.0689 |
| MRR@200 | 0.0692 |
| MRR@500 | 0.0695 |
| MRR@1000 | 0.0695 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0143 |
| Hit@5 | 0.1212 |
| Hit@10 | 0.1941 |
| Hit@20 | 0.2617 |
| Hit@50 | 0.3425 |
| Hit@100 | 0.3834 |
| Hit@200 | 0.4301 |
| Hit@500 | 0.4985 |
| Hit@1000 | 0.5561 |
| % GT not in top-20 | 73.8% |
| % GT not in top-100 | 61.7% |
| % GT not in top-200 | 57.0% |
| % GT not in top-500 | 50.1% |
| % GT not in top-1000 | 44.4% |
| Mean rank (when found) | 142.6 |
| Median rank (when found) | 24.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.7314 |
| Catalog diversity @100 | 0.9756 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset_samples.csv`
