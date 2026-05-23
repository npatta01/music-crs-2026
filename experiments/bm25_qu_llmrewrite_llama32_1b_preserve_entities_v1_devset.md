# Experiment: bm25_qu_llmrewrite_llama32_1b_preserve_entities_v1_devset

**Date:** 2026-04-27
**Config:** `configs/archive/bm25_qu_llmrewrite_llama32_1b_preserve_entities_v1_devset.yaml`

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
| NDCG@1 | 0.0090 |
| NDCG@5 | 0.0443 |
| NDCG@10 | 0.0734 |
| NDCG@20 | 0.0946 |
| NDCG@50 | 0.1153 |
| NDCG@100 | 0.1253 |
| NDCG@200 | 0.1342 |
| NDCG@500 | 0.1432 |
| NDCG@1000 | 0.1492 |
| MRR | 0.0544 |
| MRR@100 | 0.0537 |
| MRR@200 | 0.0541 |
| MRR@500 | 0.0544 |
| MRR@1000 | 0.0544 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0090 |
| Hit@5 | 0.0838 |
| Hit@10 | 0.1738 |
| Hit@20 | 0.2577 |
| Hit@50 | 0.3614 |
| Hit@100 | 0.4234 |
| Hit@200 | 0.4865 |
| Hit@500 | 0.5616 |
| Hit@1000 | 0.6181 |
| % GT not in top-20 | 74.2% |
| % GT not in top-100 | 57.7% |
| % GT not in top-200 | 51.3% |
| % GT not in top-500 | 43.8% |
| % GT not in top-1000 | 38.2% |
| Mean rank (when found) | 137.1 |
| Median rank (when found) | 31.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.4940 |
| Catalog diversity @100 | 0.8333 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_llama32_1b_preserve_entities_v1_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_llama32_1b_preserve_entities_v1_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_llama32_1b_preserve_entities_v1_devset_samples.csv`
