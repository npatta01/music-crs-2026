# Experiment: lancedb_fts_with_tag_list_devset

**Date:** 2026-05-15
**Config:** `configs/lancedb_fts_with_tag_list_devset.yaml`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | lancedb |
| qu_type | passthrough |
| retrieval_topk | 1000 |
| table_name | music_track_catalog |
| search kind | fts_bm25s_compat |
| corpus_fields | track_name, artist_name, album_name, release_date, tag_list |
| fusion.method | weighted_rrf |

## Ranking Quality

| Metric | Value |
|---|---:|
| NDCG@1 | 0.0097 |
| NDCG@5 | 0.0458 |
| NDCG@10 | 0.0746 |
| NDCG@20 | 0.0962 |
| NDCG@50 | 0.1163 |
| NDCG@100 | 0.1267 |
| NDCG@200 | 0.1351 |
| NDCG@500 | 0.1446 |
| NDCG@1000 | 0.1509 |
| MRR | 0.0557 |
| MRR@100 | 0.0549 |
| MRR@200 | 0.0553 |
| MRR@500 | 0.0556 |
| MRR@1000 | 0.0557 |

## Retrieval Coverage

| Metric | Value |
|---|---:|
| Hit@1 | 0.0097 |
| Hit@5 | 0.0860 |
| Hit@10 | 0.1750 |
| Hit@20 | 0.2602 |
| Hit@50 | 0.3609 |
| Hit@100 | 0.4249 |
| Hit@200 | 0.4849 |
| Hit@500 | 0.5639 |
| Hit@1000 | 0.6235 |
| % GT not in top-20 | 74.0% |
| % GT not in top-100 | 57.5% |
| % GT not in top-200 | 51.5% |
| % GT not in top-500 | 43.6% |
| % GT not in top-1000 | 37.6% |
| Mean rank (when found) | 140.0 |
| Median rank (when found) | 32.0 |

## Diversity

| Metric | Value |
|---|---:|
| Catalog diversity @20 | 0.4483 |
| Catalog diversity @100 | 0.7472 |
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

## BM25 Compatibility Notes

The first raw LanceDB FTS pass underperformed the direct `bm25s` baseline because the item and query analysis paths did not line up. Matching only the indexed tokenizer was not enough: native LanceDB string queries also lost the repeated-query-term signal that direct `bm25s` preserves.

This run keeps retrieval inside LanceDB FTS, but makes the sparse text path closer to the checked-in `bm25s` baseline:

- the LanceDB table build stores precomputed track embedding columns by default for later dense/hybrid experiments
- item text is pre-tokenized with `bm25s.tokenize`
- tokenized item text is indexed with a whitespace LanceDB FTS index
- query text is tokenized with the same `bm25s.tokenize`
- repeated query tokens are preserved with structured LanceDB `MatchQuery` boosts
- short FTS result sets are padded from catalog order after scored matches so every row keeps the `topk=1000` diagnostic contract

This is not a candidate reranker. LanceDB still performs the only scored retrieval step, and this FTS config does not use the stored embedding columns.

## Comparison To Direct BM25 Tag-List Baseline

Fresh comparison run: `bm25_devset_retrieval_only_with_tag_list`

| Metric | Direct BM25 | LanceDB FTS | Delta |
|---|---:|---:|---:|
| NDCG@20 | 0.0971 | 0.0962 | -0.0009 |
| Hit@20 | 0.2642 | 0.2602 | -0.0040 |
| Hit@100 | 0.4305 | 0.4249 | -0.0056 |
| Hit@1000 | 0.6310 | 0.6235 | -0.0075 |
| MRR | 0.0558 | 0.0557 | -0.0001 |

Candidate overlap against direct BM25:

| Cutoff | Mean overlap |
|---|---:|
| @20 | 0.9463 |
| @100 | 0.9511 |
| @200 | 0.9517 |
| @500 | 0.9549 |
| @1000 | 0.9582 |

## Comparison To Milvus BM25

Reference run: `milvus_bm25_with_tag_list_devset`

| Metric | Milvus BM25 | LanceDB FTS | Delta |
|---|---:|---:|---:|
| NDCG@20 | 0.0933 | 0.0962 | +0.0029 |
| Hit@20 | 0.2514 | 0.2602 | +0.0088 |
| Hit@100 | 0.4104 | 0.4249 | +0.0145 |
| Hit@1000 | 0.6048 | 0.6235 | +0.0187 |
| MRR | 0.0542 | 0.0557 | +0.0015 |

## Smoke Test

Command:

```bash
uv run python run_experiment.py --backend local --tid lancedb_fts_with_tag_list_devset --num_sessions 5 --batch_size 64 --exp_dir /tmp/music_crs_lancedb_embeddings_default_smoke
```

Result: 40 turns, `min_pool_depth=1000`, `max_pool_depth=1000`, `n_shallow_rows=0`, `NDCG@20=0.1026`, `Hit@20=0.2750`, `Hit@1000=0.6750`.

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---:|---:|---:|---:|
| 1 | 0.1322 | 0.2200 | 0.3310 | 1000 |
| 2 | 0.1406 | 0.3420 | 0.4990 | 1000 |
| 3 | 0.1045 | 0.2980 | 0.4810 | 1000 |
| 4 | 0.0932 | 0.2790 | 0.4540 | 1000 |
| 5 | 0.0794 | 0.2400 | 0.4090 | 1000 |
| 6 | 0.0774 | 0.2450 | 0.4190 | 1000 |
| 7 | 0.0756 | 0.2390 | 0.4160 | 1000 |
| 8 | 0.0666 | 0.2190 | 0.3900 | 1000 |

## Files

- Latest embedding-default verification run: `/tmp/music_crs_lancedb_embeddings_default_full`
- Inference predictions: `exp/inference/devset/lancedb_fts_with_tag_list_devset.json`
- Aggregate scores: `exp/scores/devset/lancedb_fts_with_tag_list_devset.json`
- Per-sample metrics: `exp/scores/devset/lancedb_fts_with_tag_list_devset_samples.csv`
