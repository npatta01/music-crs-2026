# Experiment: bm25_qu_llmrewrite_smollm2_1p7b_carryover_guard_v3_devset

**Date:** 2026-04-27
**Config:** `configs/archive/bm25_qu_llmrewrite_smollm2_1p7b_carryover_guard_v3_devset.yaml`

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
| NDCG@1 | 0.0123 |
| NDCG@5 | 0.0462 |
| NDCG@10 | 0.0755 |
| NDCG@20 | 0.0969 |
| NDCG@50 | 0.1179 |
| NDCG@100 | 0.1279 |
| NDCG@200 | 0.1367 |
| NDCG@500 | 0.1461 |
| NDCG@1000 | 0.1524 |
| MRR | 0.0568 |
| MRR@100 | 0.0560 |
| MRR@200 | 0.0565 |
| MRR@500 | 0.0567 |
| MRR@1000 | 0.0568 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0123 |
| Hit@5 | 0.0850 |
| Hit@10 | 0.1757 |
| Hit@20 | 0.2605 |
| Hit@50 | 0.3653 |
| Hit@100 | 0.4276 |
| Hit@200 | 0.4900 |
| Hit@500 | 0.5679 |
| Hit@1000 | 0.6278 |
| % GT not in top-20 | 74.0% |
| % GT not in top-100 | 57.2% |
| % GT not in top-200 | 51.0% |
| % GT not in top-500 | 43.2% |
| % GT not in top-1000 | 37.2% |
| Mean rank (when found) | 140.0 |
| Median rank (when found) | 32.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.4812 |
| Catalog diversity @100 | 0.8085 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_smollm2_1p7b_carryover_guard_v3_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_smollm2_1p7b_carryover_guard_v3_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_smollm2_1p7b_carryover_guard_v3_devset_samples.csv`
