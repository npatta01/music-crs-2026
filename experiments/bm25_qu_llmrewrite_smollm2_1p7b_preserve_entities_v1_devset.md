# Experiment: bm25_qu_llmrewrite_smollm2_1p7b_preserve_entities_v1_devset

**Date:** 2026-04-27
**Config:** `config/bm25_qu_llmrewrite_smollm2_1p7b_preserve_entities_v1_devset.yaml`

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
| NDCG@1 | 0.0128 |
| NDCG@5 | 0.0466 |
| NDCG@10 | 0.0753 |
| NDCG@20 | 0.0970 |
| NDCG@50 | 0.1177 |
| NDCG@100 | 0.1278 |
| NDCG@200 | 0.1367 |
| NDCG@500 | 0.1459 |
| NDCG@1000 | 0.1521 |
| MRR | 0.0571 |
| MRR@100 | 0.0563 |
| MRR@200 | 0.0568 |
| MRR@500 | 0.0570 |
| MRR@1000 | 0.0571 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0128 |
| Hit@5 | 0.0851 |
| Hit@10 | 0.1736 |
| Hit@20 | 0.2594 |
| Hit@50 | 0.3631 |
| Hit@100 | 0.4256 |
| Hit@200 | 0.4892 |
| Hit@500 | 0.5654 |
| Hit@1000 | 0.6241 |
| % GT not in top-20 | 74.1% |
| % GT not in top-100 | 57.4% |
| % GT not in top-200 | 51.1% |
| % GT not in top-500 | 43.5% |
| % GT not in top-1000 | 37.6% |
| Mean rank (when found) | 139.3 |
| Median rank (when found) | 32.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.5053 |
| Catalog diversity @100 | 0.8357 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_smollm2_1p7b_preserve_entities_v1_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_smollm2_1p7b_preserve_entities_v1_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_smollm2_1p7b_preserve_entities_v1_devset_samples.csv`
