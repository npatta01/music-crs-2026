# Experiment: bm25_qu_llmrewrite_qwen3_4b_preserve_entities_v1_devset

**Date:** 2026-04-27
**Config:** `config/bm25_qu_llmrewrite_qwen3_4b_preserve_entities_v1_devset.yaml`

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
| NDCG@1 | 0.0246 |
| NDCG@5 | 0.0653 |
| NDCG@10 | 0.0867 |
| NDCG@20 | 0.1061 |
| NDCG@50 | 0.1260 |
| NDCG@100 | 0.1365 |
| NDCG@200 | 0.1455 |
| NDCG@500 | 0.1555 |
| NDCG@1000 | 0.1624 |
| MRR | 0.0710 |
| MRR@100 | 0.0701 |
| MRR@200 | 0.0706 |
| MRR@500 | 0.0709 |
| MRR@1000 | 0.0710 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0246 |
| Hit@5 | 0.1065 |
| Hit@10 | 0.1726 |
| Hit@20 | 0.2498 |
| Hit@50 | 0.3500 |
| Hit@100 | 0.4144 |
| Hit@200 | 0.4784 |
| Hit@500 | 0.5616 |
| Hit@1000 | 0.6273 |
| % GT not in top-20 | 75.0% |
| % GT not in top-100 | 58.6% |
| % GT not in top-200 | 52.2% |
| % GT not in top-500 | 43.8% |
| % GT not in top-1000 | 37.3% |
| Mean rank (when found) | 150.3 |
| Median rank (when found) | 37.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.5763 |
| Catalog diversity @100 | 0.8879 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|


## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_llmrewrite_qwen3_4b_preserve_entities_v1_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen3_4b_preserve_entities_v1_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_llmrewrite_qwen3_4b_preserve_entities_v1_devset_samples.csv`
