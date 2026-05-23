# Experiment: bm25_qu_llmrewrite_qwen25_3b_preserve_entities_v1_devset

**Date:** 2026-04-27
**Config:** `configs/archive/bm25_qu_llmrewrite_qwen25_3b_preserve_entities_v1_devset.yaml`

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
| NDCG@1 | 0.0203 |
| NDCG@5 | 0.0648 |
| NDCG@10 | 0.0846 |
| NDCG@20 | 0.1001 |
| NDCG@50 | 0.1160 |
| NDCG@100 | 0.1245 |
| NDCG@200 | 0.1308 |
| NDCG@500 | 0.1389 |
| NDCG@1000 | 0.1454 |
| MRR | 0.0667 |
| MRR@100 | 0.0661 |
| MRR@200 | 0.0664 |
| MRR@500 | 0.0666 |
| MRR@1000 | 0.0667 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0203 |
| Hit@5 | 0.1090 |
| Hit@10 | 0.1703 |
| Hit@20 | 0.2319 |
| Hit@50 | 0.3112 |
| Hit@100 | 0.3639 |
| Hit@200 | 0.4089 |
| Hit@500 | 0.4761 |
| Hit@1000 | 0.5383 |
| % GT not in top-20 | 76.8% |
| % GT not in top-100 | 63.6% |
| % GT not in top-200 | 59.1% |
| % GT not in top-500 | 52.4% |
| % GT not in top-1000 | 46.2% |
| Mean rank (when found) | 155.0 |
| Median rank (when found) | 31.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.7295 |
| Catalog diversity @100 | 0.9719 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_qwen25_3b_preserve_entities_v1_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen25_3b_preserve_entities_v1_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen25_3b_preserve_entities_v1_devset_samples.csv`
