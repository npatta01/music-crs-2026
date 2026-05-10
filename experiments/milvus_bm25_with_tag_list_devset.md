# Experiment: milvus_bm25_with_tag_list_devset

**Date:** 2026-05-10
**Config:** `config/milvus_bm25_with_tag_list_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | milvus |
| qu_type | passthrough |
| retrieval_topk | 1000 |
| collection_name | music_track_catalog |
| search kind | bm25_compat |
| corpus_fields | track_name, artist_name, album_name, release_date, tag_list |
| fusion.method | weighted |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0095 |
| NDCG@5 | 0.0447 |
| NDCG@10 | 0.0721 |
| NDCG@20 | 0.0933 |
| NDCG@50 | 0.1123 |
| NDCG@100 | 0.1226 |
| NDCG@200 | 0.1308 |
| NDCG@500 | 0.1403 |
| NDCG@1000 | 0.1463 |
| MRR | 0.0542 |
| MRR@100 | 0.0535 |
| MRR@200 | 0.0539 |
| MRR@500 | 0.0541 |
| MRR@1000 | 0.0542 |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0095 |
| Hit@5 | 0.0831 |
| Hit@10 | 0.1676 |
| Hit@20 | 0.2514 |
| Hit@50 | 0.3468 |
| Hit@100 | 0.4104 |
| Hit@200 | 0.4691 |
| Hit@500 | 0.5478 |
| Hit@1000 | 0.6048 |
| % GT not in top-20 | 74.9% |
| % GT not in top-100 | 59.0% |
| % GT not in top-200 | 53.1% |
| % GT not in top-500 | 45.2% |
| % GT not in top-1000 | 39.5% |
| Mean rank (when found) | 141.1 |
| Median rank (when found) | 33.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.4247 |
| Catalog diversity @100 | 0.7045 |
| Lexical diversity | 0.0000 |

## Depth Diagnostics

| Metric | Value |
|---|---|
| require_full_diagnostic_depth | true |
| full_diagnostic_depth | 1000 |
| available_cutoffs | 1, 5, 10, 20, 50, 100, 200, 500, 1000 |
| min_pool_depth | 1000 |
| max_pool_depth | 1000 |
| n_shallow_rows | 0 |

## Comparison To Non-Milvus Sparse Baseline

Reference baseline: `bm25_devset_retrieval_only_with_tag_list`

| Metric | Non-Milvus BM25 | Milvus BM25 | Delta |
|---|---:|---:|---:|
| NDCG@20 | 0.0970 | 0.0933 | -0.0037 |
| Hit@20 | 0.2640 | 0.2514 | -0.0126 |
| Hit@1000 | 0.6311 | 0.6048 | -0.0263 |
| MRR | 0.0558 | 0.0542 | -0.0016 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1287 | 0.2150 | 0.3210 | 1000 |
| 2 | 0.1362 | 0.3270 | 0.4960 | 1000 |
| 3 | 0.1014 | 0.2870 | 0.4670 | 1000 |
| 4 | 0.0906 | 0.2700 | 0.4400 | 1000 |
| 5 | 0.0761 | 0.2290 | 0.3880 | 1000 |
| 6 | 0.0769 | 0.2460 | 0.3990 | 1000 |
| 7 | 0.0725 | 0.2300 | 0.3910 | 1000 |
| 8 | 0.0640 | 0.2070 | 0.3810 | 1000 |

## Files

- Inference predictions: `exp/inference/devset/milvus_bm25_with_tag_list_devset.json`
- Aggregate scores: `exp/scores/devset/milvus_bm25_with_tag_list_devset.json`
- Per-sample metrics: `exp/scores/devset/milvus_bm25_with_tag_list_devset_samples.csv`
