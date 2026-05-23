# Experiment: bm25_qu_llmrewrite_qwen3_4b_carryover_guard_v3_devset

**Date:** 2026-04-27
**Config:** `configs/archive/bm25_qu_llmrewrite_qwen3_4b_carryover_guard_v3_devset.yaml`

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
| NDCG@1 | 0.0239 |
| NDCG@5 | 0.0642 |
| NDCG@10 | 0.0860 |
| NDCG@20 | 0.1049 |
| NDCG@50 | 0.1238 |
| NDCG@100 | 0.1347 |
| NDCG@200 | 0.1431 |
| NDCG@500 | 0.1528 |
| NDCG@1000 | 0.1599 |
| MRR | 0.0700 |
| MRR@100 | 0.0692 |
| MRR@200 | 0.0696 |
| MRR@500 | 0.0699 |
| MRR@1000 | 0.0700 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0239 |
| Hit@5 | 0.1045 |
| Hit@10 | 0.1722 |
| Hit@20 | 0.2467 |
| Hit@50 | 0.3417 |
| Hit@100 | 0.4087 |
| Hit@200 | 0.4685 |
| Hit@500 | 0.5491 |
| Hit@1000 | 0.6164 |
| % GT not in top-20 | 75.3% |
| % GT not in top-100 | 59.1% |
| % GT not in top-200 | 53.1% |
| % GT not in top-500 | 45.1% |
| % GT not in top-1000 | 38.4% |
| Mean rank (when found) | 151.7 |
| Median rank (when found) | 37.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.6002 |
| Catalog diversity @100 | 0.8996 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_qwen3_4b_carryover_guard_v3_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen3_4b_carryover_guard_v3_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen3_4b_carryover_guard_v3_devset_samples.csv`
