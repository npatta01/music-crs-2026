# Experiment: dense_precomputed_lyrics_qwen3_06b_devset

**Date:** 2026-04-28
**Config:** `config/dense_precomputed_lyrics_qwen3_06b_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | precomputed_embedding |
| retrieval_topk | 1000 |
| embedding_column | lyrics-qwen3_embedding_0.6b |
| query encoder | Qwen/Qwen3-Embedding-0.6B |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0070 |
| NDCG@5 | 0.0129 |
| NDCG@10 | 0.0152 |
| NDCG@20 | 0.0179 |
| NDCG@50 | 0.0215 |
| NDCG@100 | 0.0245 |
| NDCG@200 | 0.0275 |
| NDCG@500 | 0.0334 |
| NDCG@1000 | 0.0387 |
| MRR | 0.0139 |
| MRR@100 | 0.0135 |
| MRR@200 | 0.0136 |
| MRR@500 | 0.0138 |
| MRR@1000 | 0.0139 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0070 |
| Hit@5 | 0.0188 |
| Hit@10 | 0.0260 |
| Hit@20 | 0.0369 |
| Hit@50 | 0.0550 |
| Hit@100 | 0.0733 |
| Hit@200 | 0.0950 |
| Hit@500 | 0.1444 |
| Hit@1000 | 0.1944 |
| % GT not in top-20 | 96.3% |
| % GT not in top-100 | 92.7% |
| % GT not in top-200 | 90.5% |
| % GT not in top-500 | 85.6% |
| % GT not in top-1000 | 80.6% |
| Mean rank (when found) | 301.1 |
| Median rank (when found) | 215.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.2865 |
| Catalog diversity @100 | 0.6204 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.0487 | 0.080 | 0.121 | 1000 |
| 2 | 0.0283 | 0.056 | 0.097 | 1000 |
| 3 | 0.0154 | 0.033 | 0.066 | 1000 |
| 4 | 0.0083 | 0.019 | 0.058 | 1000 |
| 5 | 0.0131 | 0.035 | 0.066 | 1000 |
| 6 | 0.0139 | 0.034 | 0.071 | 1000 |
| 7 | 0.0076 | 0.019 | 0.051 | 1000 |
| 8 | 0.0080 | 0.019 | 0.056 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/dense_precomputed_lyrics_qwen3_06b_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/dense_precomputed_lyrics_qwen3_06b_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/dense_precomputed_lyrics_qwen3_06b_devset_samples.csv`
