# Experiment: v0plus_compiler_all_retrievers_devset

**Date:** 2026-06-01
**Config:** `configs/v0plus_compiler_all_retrievers_devset.yaml`
**Backend:** Modal, 5-shard full devset run
**Prediction git head:** `9f4904aece3ff96a397e365bac4252dbb5ac0d0f`
**Modal app:** `ap-S5AIqzgpDsonLgw1NcW0K9`
**Status:** `analyzed`

## Summary

This run exercises the prompt-v4 extractor plus every currently wired v0+ retriever branch:
BM25 field boosts, release-year BM25 boosts, Qwen3 metadata/lyrics/attributes dense text,
CLAP text-to-audio, image/audio/cf-bpr centroid branches, user cf-bpr centroid, resolved-artist
discography, and era/popularity retrieval.

The result is the best v0+ candidate coverage so far, but not the best top-20 ranking. Hit@1000
improves over the prior `v0plus_compiler_all_devset` coverage run (`0.6967` vs `0.6730`), while
NDCG@20 falls well below the image-only canonical config (`0.1219` vs `0.1452`). More branches are
finding more gold tracks somewhere in the 1000-deep pool, but the fused order is too noisy for
headline top-K quality.

| Comparison | NDCG@20 | Hit@20 | Hit@1000 | MRR |
|---|---:|---:|---:|---:|
| `v0plus_compiler_image_devset` | 0.1452 | 0.2989 | 0.6261 | 0.1062 |
| `v0plus_compiler_all_devset` | 0.1432 | 0.3090 | 0.6730 | 0.1010 |
| `v0plus_compiler_all_retrievers_devset` | 0.1219 | 0.2660 | 0.6967 | 0.0871 |

Verdict: keep this run as the best coverage / candidate-pool reference, not as the canonical
ranking config. The natural follow-up is branch quota/survivor-set tuning or a reranker over this
larger pool.

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| qu_type | v0plus_compiler |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |
| compiler.final_topk | 1000 |
| dense branches | `metadata_qwen3_embedding_0_6b`, `lyrics_qwen3_embedding_0_6b`, `attributes_qwen3_embedding_0_6b`, `audio_laion_clap` via CLAP text |
| centroid-only branches | `image_siglip2`, `audio_laion_clap`, `cf_bpr`, `cf_bpr:user` |
| extra branches | resolved-artist discography, era/popularity |

## Diagnostic Depth

| Field | Value |
|---|---:|
| Turns evaluated | 8000 |
| require_full_diagnostic_depth | false |
| Target diagnostic depth | 1000 |
| Min pool depth | 0 |
| Max pool depth | 1000 |
| Shallow rows | 1 |
| Extractor returned None | 1 |
| Available cutoffs | 1, 5, 10, 20, 50, 100, 200, 500, 1000 |

The single shallow row corresponds to the single `extractor_returned_none` trace row. The other
7999 turns returned a 1000-candidate pool.

## Ranking Quality

| Metric | Value |
|---|---:|
| NDCG@1 | 0.0380 |
| NDCG@5 | 0.0817 |
| NDCG@10 | 0.1024 |
| NDCG@20 | 0.1219 |
| NDCG@50 | 0.1430 |
| NDCG@100 | 0.1556 |
| NDCG@200 | 0.1653 |
| NDCG@500 | 0.1771 |
| NDCG@1000 | 0.1855 |
| MRR | 0.0871 |
| MRR@100 | 0.0861 |
| MRR@200 | 0.0866 |
| MRR@500 | 0.0869 |
| MRR@1000 | 0.0871 |

## Retrieval Coverage

| Metric | Value |
|---|---:|
| Hit@1 | 0.0380 |
| Hit@5 | 0.1241 |
| Hit@10 | 0.1884 |
| Hit@20 | 0.2660 |
| Hit@50 | 0.3719 |
| Hit@100 | 0.4496 |
| Hit@200 | 0.5192 |
| Hit@500 | 0.6167 |
| Hit@1000 | 0.6967 |
| % GT not in top-20 | 73.4% |
| % GT not in top-100 | 55.0% |
| % GT not in top-200 | 48.1% |
| % GT not in top-500 | 38.3% |
| % GT not in top-1000 | 30.3% |
| Mean rank when found | 159.9 |
| Median rank when found | 41.0 |

## Diversity

| Metric | Value |
|---|---:|
| Catalog diversity @20 | 0.5261 |
| Catalog diversity @100 | 0.8924 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---:|---:|---:|---:|---:|
| 1 | 0.1552 | 0.2900 | 0.4360 | 1000 |
| 2 | 0.1909 | 0.3970 | 0.5790 | 1000 |
| 3 | 0.1503 | 0.3260 | 0.5370 | 1000 |
| 4 | 0.1263 | 0.2800 | 0.4760 | 1000 |
| 5 | 0.1019 | 0.2370 | 0.4280 | 1000 |
| 6 | 0.0916 | 0.2170 | 0.4050 | 1000 |
| 7 | 0.0869 | 0.2070 | 0.3880 | 1000 |
| 8 | 0.0722 | 0.1740 | 0.3480 | 1000 |

## Findings

1. Coverage improved, ranking did not.

   The all-retrievers pool recovers the gold track at top-1000 on 69.7% of turns, the best number
   in the tracked v0+ runs. But Hit@20 is only 26.6%, below both image-only and the previous
   all-embeddings run. The extra branches are mostly adding recoverable candidates at mid/deep
   ranks rather than promoting them into the top 20.

2. Turn-2 is strong; late-turn precision still decays.

   Turn 2 reaches `NDCG@20 0.1909` / `Hit@20 0.3970`, but by turn 8 the run is down to
   `NDCG@20 0.0722` / `Hit@20 0.1740`. This is the opposite shape from the canonical image config,
   whose late turns stay much flatter. The branch set appears to over-broaden as history accumulates.

3. Extractor reliability was acceptable.

   The Modal logs showed noisy LiteLLM provider-list footers and a few schema/JSON warnings, but the
   merged trace has only one `extractor_returned_none` row out of 8000. The metric drop is therefore
   not an extractor-outage artifact.

4. This is useful as a reranker input.

   Hit@1000 `0.6967` gives a bigger candidate reservoir than the prior tracked configs. If a reranker
   or survivor-set policy can preserve the high-value branch candidates while suppressing noisy tails,
   this run is a better source pool than its NDCG@20 alone suggests.

## Operational Notes

- Successful full run: `uv run python -m modal run modal/app.py::run_inference_sharded --tid v0plus_compiler_all_retrievers_devset --num-shards 5 --batch-size 64`.
- A first full attempt with `--batch-size 4` was stopped early because each shard had 400 batches and projected too close to the Modal timeout. No shard artifacts were left behind.
- Sharded inference completed in about 39 minutes wall time, then shards were downloaded and merged locally.
- The worktree needed an ignored `.env` symlink to the main project checkout for Modal secrets; it was removed after the run.

## Files

- Inference predictions: `exp/inference/devset/v0plus_compiler_all_retrievers_devset.json`
- Trace: `exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl`
- Per-shard predictions/traces: `exp/inference/devset/v0plus_compiler_all_retrievers_devset.shard_{0..4}*.json`
- Aggregate scores: `exp/scores/devset/v0plus_compiler_all_retrievers_devset.json`
- Per-sample metrics: `exp/scores/devset/v0plus_compiler_all_retrievers_devset_samples.csv`
