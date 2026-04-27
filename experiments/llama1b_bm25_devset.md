# Experiment: llama1b_bm25_devset

**Date:** 2026-04-27
**Config:** `config/llama1b_bm25_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | meta-llama/Llama-3.2-1B-Instruct |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0098 |
| NDCG@5 | 0.0381 |
| NDCG@10 | 0.0626 |
| NDCG@20 | 0.0815 |
| NDCG@50 | 0.0966 |
| NDCG@100 | 0.1028 |
| NDCG@200 | 0.1068 |
| NDCG@500 | 0.1108 |
| NDCG@1000 | 0.1141 |
| MRR | 0.0466 |
| MRR@100 | 0.0463 |
| MRR@200 | 0.0465 |
| MRR@500 | 0.0466 |
| MRR@1000 | 0.0466 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0098 |
| Hit@5 | 0.0698 |
| Hit@10 | 0.1456 |
| Hit@20 | 0.2200 |
| Hit@50 | 0.2955 |
| Hit@100 | 0.3340 |
| Hit@200 | 0.3620 |
| Hit@500 | 0.3958 |
| Hit@1000 | 0.4265 |
| % GT not in top-20 | 78.0% |
| % GT not in top-100 | 66.6% |
| % GT not in top-200 | 63.8% |
| % GT not in top-500 | 60.4% |
| % GT not in top-1000 | 57.4% |
| Mean rank (when found) | 101.8 |
| Median rank (when found) | 19.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3796 |
| Catalog diversity @100 | 0.6956 |
| Lexical diversity | 0.2554 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1095 | 0.1790 | 0.2560 | 1000 |
| 2 | 0.1202 | 0.2960 | 0.4150 | 1000 |
| 3 | 0.0923 | 0.2530 | 0.3740 | 1000 |
| 4 | 0.0733 | 0.2210 | 0.3430 | 1000 |
| 5 | 0.0706 | 0.2220 | 0.3340 | 1000 |
| 6 | 0.0648 | 0.2070 | 0.3220 | 1000 |
| 7 | 0.0602 | 0.1910 | 0.3050 | 1000 |
| 8 | 0.0607 | 0.1910 | 0.3230 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/llama1b_bm25_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/llama1b_bm25_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/llama1b_bm25_devset_samples.csv`
