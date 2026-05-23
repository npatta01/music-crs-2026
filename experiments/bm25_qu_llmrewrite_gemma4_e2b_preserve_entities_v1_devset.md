# Experiment: bm25_qu_llmrewrite_gemma4_e2b_preserve_entities_v1_devset

**Date:** 2026-04-27
**Config:** `configs/archive/bm25_qu_llmrewrite_gemma4_e2b_preserve_entities_v1_devset.yaml`

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
| NDCG@1 | 0.0185 |
| NDCG@5 | 0.0656 |
| NDCG@10 | 0.0879 |
| NDCG@20 | 0.1048 |
| NDCG@50 | 0.1220 |
| NDCG@100 | 0.1302 |
| NDCG@200 | 0.1367 |
| NDCG@500 | 0.1447 |
| NDCG@1000 | 0.1512 |
| MRR | 0.0686 |
| MRR@100 | 0.0679 |
| MRR@200 | 0.0683 |
| MRR@500 | 0.0685 |
| MRR@1000 | 0.0686 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0185 |
| Hit@5 | 0.1116 |
| Hit@10 | 0.1805 |
| Hit@20 | 0.2475 |
| Hit@50 | 0.3335 |
| Hit@100 | 0.3841 |
| Hit@200 | 0.4307 |
| Hit@500 | 0.4974 |
| Hit@1000 | 0.5584 |
| % GT not in top-20 | 75.2% |
| % GT not in top-100 | 61.6% |
| % GT not in top-200 | 56.9% |
| % GT not in top-500 | 50.3% |
| % GT not in top-1000 | 44.2% |
| Mean rank (when found) | 146.7 |
| Median rank (when found) | 28.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.7095 |
| Catalog diversity @100 | 0.9701 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_gemma4_e2b_preserve_entities_v1_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_gemma4_e2b_preserve_entities_v1_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_gemma4_e2b_preserve_entities_v1_devset_samples.csv`
