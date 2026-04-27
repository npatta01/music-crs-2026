# Experiment: llama1b_bm25_devset

**Date:** 2026-04-27
**Config:** `config/llama1b_bm25_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | meta-llama/Llama-3.2-1B-Instruct |
| retrieval_type | bm25 |
| retrieval_topk | 100 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0096 |
| NDCG@5 | 0.0379 |
| NDCG@10 | 0.0625 |
| NDCG@20 | 0.0813 |
| NDCG@50 | 0.0965 |
| NDCG@100 | 0.1028 |
| MRR | 0.0462 |
| MRR@100 | 0.0462 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0096 |
| Hit@5 | 0.0692 |
| Hit@10 | 0.1454 |
| Hit@20 | 0.2193 |
| Hit@50 | 0.2953 |
| Hit@100 | 0.3339 |
| % GT not in top-20 | 78.1% |
| % GT not in top-100 | 66.6% |
| Mean rank (when found) | 21.3 |
| Median rank (when found) | 13.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3795 |
| Catalog diversity @100 | 0.6958 |
| Lexical diversity | 0.2557 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1091 | 0.1780 | 0.2560 | 1000 |
| 2 | 0.1195 | 0.2950 | 0.4130 | 1000 |
| 3 | 0.0922 | 0.2520 | 0.3740 | 1000 |
| 4 | 0.0738 | 0.2210 | 0.3430 | 1000 |
| 5 | 0.0702 | 0.2210 | 0.3350 | 1000 |
| 6 | 0.0646 | 0.2050 | 0.3220 | 1000 |
| 7 | 0.0600 | 0.1900 | 0.3050 | 1000 |
| 8 | 0.0607 | 0.1920 | 0.3230 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/llama1b_bm25_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/llama1b_bm25_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/llama1b_bm25_devset_samples.csv`
