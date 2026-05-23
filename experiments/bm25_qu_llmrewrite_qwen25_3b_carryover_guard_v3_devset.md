# Experiment: bm25_qu_llmrewrite_qwen25_3b_carryover_guard_v3_devset

**Date:** 2026-04-27
**Config:** `configs/archive/bm25_qu_llmrewrite_qwen25_3b_carryover_guard_v3_devset.yaml`

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
| NDCG@1 | 0.0236 |
| NDCG@5 | 0.0610 |
| NDCG@10 | 0.0783 |
| NDCG@20 | 0.0936 |
| NDCG@50 | 0.1103 |
| NDCG@100 | 0.1190 |
| NDCG@200 | 0.1256 |
| NDCG@500 | 0.1331 |
| NDCG@1000 | 0.1392 |
| MRR | 0.0640 |
| MRR@100 | 0.0634 |
| MRR@200 | 0.0637 |
| MRR@500 | 0.0639 |
| MRR@1000 | 0.0640 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0236 |
| Hit@5 | 0.0991 |
| Hit@10 | 0.1525 |
| Hit@20 | 0.2131 |
| Hit@50 | 0.2971 |
| Hit@100 | 0.3505 |
| Hit@200 | 0.3978 |
| Hit@500 | 0.4604 |
| Hit@1000 | 0.5185 |
| % GT not in top-20 | 78.7% |
| % GT not in top-100 | 65.0% |
| % GT not in top-200 | 60.2% |
| % GT not in top-500 | 54.0% |
| % GT not in top-1000 | 48.1% |
| Mean rank (when found) | 151.3 |
| Median rank (when found) | 33.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.6839 |
| Catalog diversity @100 | 0.9495 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_qwen25_3b_carryover_guard_v3_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen25_3b_carryover_guard_v3_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen25_3b_carryover_guard_v3_devset_samples.csv`
