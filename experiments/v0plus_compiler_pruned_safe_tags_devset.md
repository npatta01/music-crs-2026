# Experiment: v0plus_compiler_pruned_safe_tags_devset

**Date:** 2026-06-10
**Config:** `configs/v0plus_compiler_pruned_safe_tags_devset.yaml`
**Note:** 50-session smoke test (400 turns). Not directly comparable to full-devset baseline.

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| retrieval_topk | 1000 |

**vs. all_retrievers baseline:**
- Removes duplicate Qwen 0.6B branches (0.6B kept for lyrics only; 8B owns metadata+attributes)
- `bm25_v1_attribute_tag_policy: "catalog_exact"` — V1 attribute facts only enter BM25 if they match a catalog tag exactly
- `bm25_include_turn_intent_tag_clause: false` — turn_intent no longer fans into BM25 tag_list
- `enable_similar_artist_anchors: false`

## Ranking Quality

| Metric | Smoke (50 sess) | Baseline (1000 sess) | Δ |
|---|---|---|---|
| NDCG@20 | 0.1133 | 0.1255 | -0.0122 |
| NDCG@100 | 0.1428 | — | — |
| NDCG@1000 | 0.1713 | — | — |
| MRR | 0.0779 | 0.0897 | -0.0118 |

## Retrieval Coverage

| Metric | Smoke (50 sess) | Baseline (1000 sess) | Δ |
|---|---|---|---|
| Hit@20 | 0.2575 | 0.2742 | -0.0167 |
| Hit@100 | 0.4175 | — | — |
| Hit@1000 | 0.6550 | 0.7289 | -0.0739 |
| Mean rank (found) | 173.1 | — | — |
| Median rank (found) | 38.5 | — | — |
| % GT not in top-20 | 74.3% | — | — |
| % GT not in top-1000 | 34.5% | — | — |

## Branch Union Coverage

| Metric | Smoke (50 sess) | Baseline (1000 sess) | Δ |
|---|---|---|---|
| union@20 | 0.3850 | — | — |
| union@100 | 0.5800 | — | — |
| union@200 | 0.6750 | — | — |
| union@1000 | 0.8500 | 0.905 | -0.055 |
| fusion_efficiency@200 | 0.700 | — | — |
| fusion_efficiency@1000 | 0.771 | — | — |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.0751 |
| Catalog diversity @100 | 0.2613 |
| Lexical diversity | 0.0 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.1142 | 0.26 | 0.42 | 50 |
| 2 | 0.1672 | 0.42 | 0.54 | 50 |
| 3 | 0.1569 | 0.34 | 0.54 | 50 |
| 4 | 0.1045 | 0.28 | 0.48 | 50 |
| 5 | 0.0586 | 0.16 | 0.26 | 50 |
| 6 | 0.1071 | 0.22 | 0.36 | 50 |
| 7 | 0.1310 | 0.22 | 0.36 | 50 |
| 8 | 0.0671 | 0.16 | 0.38 | 50 |

## Files

- Inference predictions: `exp/inference/devset/v0plus_compiler_pruned_safe_tags_devset.json`
- Aggregate scores: `exp/scores/devset/v0plus_compiler_pruned_safe_tags_devset.json`
- Per-sample metrics: `exp/scores/devset/v0plus_compiler_pruned_safe_tags_devset_samples.csv`

## Verdict

**Inconclusive, leaning regression.** All headline metrics are below the all_retrievers
baseline, but the comparison is not paired (different 50 sessions vs full 1000-session
devset). The union@1000 drop (0.85 vs 0.905) is the most concerning signal — it suggests
the pruned 0.6B branches were contributing unique coverage that 8B doesn't replicate.

The `catalog_exact` BM25 tag policy (the main correctness fix) and the branch pruning
are confounded in this config. Recommended next test: apply only the BM25 policy change
on top of the unmodified all_retrievers branch list to isolate the signal.
