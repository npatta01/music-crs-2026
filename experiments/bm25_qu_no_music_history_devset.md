# Experiment: bm25_qu_no_music_history_devset

**Date:** 2026-04-27
**Config:** `config/bm25_qu_no_music_history_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |
| qu_type | no_music_history |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0123 |
| NDCG@5 | 0.0278 |
| NDCG@10 | 0.0398 |
| NDCG@20 | 0.0496 |
| NDCG@50 | 0.0603 |
| NDCG@100 | 0.0659 |
| NDCG@200 | 0.0704 |
| NDCG@500 | 0.0764 |
| NDCG@1000 | 0.0807 |
| MRR | 0.0327 |
| MRR@100 | 0.0323 |
| MRR@200 | 0.0325 |
| MRR@500 | 0.0327 |
| MRR@1000 | 0.0327 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0123 |
| Hit@5 | 0.0444 |
| Hit@10 | 0.0816 |
| Hit@20 | 0.1204 |
| Hit@50 | 0.1740 |
| Hit@100 | 0.2084 |
| Hit@200 | 0.2410 |
| Hit@500 | 0.2909 |
| Hit@1000 | 0.3315 |
| % GT not in top-20 | 88.0% |
| % GT not in top-100 | 79.2% |
| % GT not in top-200 | 75.9% |
| % GT not in top-500 | 70.9% |
| % GT not in top-1000 | 66.9% |
| Mean rank (when found) | 169.2 |
| Median rank (when found) | 45.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.2663 |
| Catalog diversity @100 | 0.5569 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1095 | 0.1790 | 0.2560 | 1000 |
| 2 | 0.0767 | 0.1760 | 0.2940 | 1000 |
| 3 | 0.0507 | 0.1330 | 0.2220 | 1000 |
| 4 | 0.0405 | 0.1160 | 0.1900 | 1000 |
| 5 | 0.0350 | 0.1070 | 0.1980 | 1000 |
| 6 | 0.0296 | 0.0890 | 0.1760 | 1000 |
| 7 | 0.0271 | 0.0800 | 0.1640 | 1000 |
| 8 | 0.0277 | 0.0830 | 0.1670 | 1000 |

## Files

- Inference predictions: `evaluator/exp/inference/devset/bm25_qu_no_music_history_devset.json`
- Aggregate scores: `evaluator/exp/scores/devset/bm25_qu_no_music_history_devset.json`
- Per-sample metrics: `evaluator/exp/scores/devset/bm25_qu_no_music_history_devset_samples.csv`
