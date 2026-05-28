# Experiment: v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset

**Date:** 2026-05-27
**Status:** `analyzed`
**Config:** [`configs/v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset.yaml`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/configs/v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset.yaml)

## What's new

First run that exercises:

1. **The "no-drag" multimodal branch set** — BM25 + image_siglip2 + audio_laion_clap + cf_bpr + metadata_qwen3. Drops attributes_qwen3 (-7% NDCG@20 in the 2026-05-26 ablation) and lyrics_qwen3 (-9%).
2. **The new `process_constraints.exploration_policy` field** added to the LLM extractor schema (smoke test showed 92% extraction accuracy on hand-built cases).
3. **The new `PostFusionReranker` framework** ([mcrs/qu_modules/post_fusion_features.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/qu_modules/post_fusion_features.py)) wired into the compiler.

Default behavior preserved when `exploration_policy=balanced` (the most common LLM extraction) — no policy-driven artist demote unless `diversify_artists` fires.

## Headline metrics (1000 sessions × 8 turns)

Macro avg, full-pool rows only (7948/8000 = 99.4%). Re-run on 2026-05-27 after
the Pydantic `between` validator + `album_id_of` fixes — empty rows dropped
from 12 to 4, but macro metrics moved <0.1pp (the recovered turns are mostly
hardest cases where the LLM struggled, so their per-turn scores are low).

| Metric | Value |
|---|---:|
| **NDCG@20** (competition target) | **0.1411** |
| **Hit@20** | **0.3098** |
| Hit@1 | 0.0425 |
| Hit@5 | 0.1469 |
| Hit@10 | 0.2255 |
| Hit@50 | 0.4055 |
| Hit@100 | 0.4587 |
| Hit@200 | 0.5086 |
| Hit@500 | 0.5834 |
| Hit@1000 | 0.6429 |
| MRR | 0.0985 |
| NDCG@1000 | 0.1914 |
| Mean rank (when found) | 131 |
| Median rank (when found) | 23 |
| Empty predictions | 12 / 8000 (0.15%) |
| Shallow rows (<1000 pool) | 50 / 8000 (0.6%) |

## vs prior best configs

| Config | NDCG@20 | Hit@20 | Hit@100 | Hit@1000 | MRR |
|---|---:|---:|---:|---:|---:|
| BM25 baseline (`v0plus_compiler_devset`) | 0.0984 | 0.233 | 0.404 | 0.571 | 0.066 |
| Image-only (`v0plus_compiler_image_devset`) — prior best | **0.1461** | 0.300 | 0.440 | 0.598 | **0.107** |
| All-embeddings (`v0plus_compiler_all_devset`) | 0.1428 | 0.309 | **0.478** | **0.673** | 0.101 |
| **This (no-drag)** | 0.1415 | **0.310** | 0.459 | 0.643 | 0.099 |

**Verdict: roughly tied with image-only on NDCG@20, slightly weaker on MRR, +5pp Hit@1000 coverage.**

The "no-drag" hypothesis (drop the regressing qwen3 attributes + lyrics branches, keep the value-additive ones) did NOT translate into a macro NDCG@20 lift over the singular image branch. Image alone really is the dominant lever; the audio + cf_bpr + metadata_qwen3 branches add ~5pp pool coverage but don't sharpen top-K ranking precision.

## Per-turn breakdown

| Turn | n | Hit@20 | Hit@100 | NDCG@20 |
|---:|---:|---:|---:|---:|
| 1 | 978 | 0.231 | 0.313 | 0.124 |
| 2 | 989 | **0.380** | **0.513** | **0.187** |
| 3 | 992 | 0.350 | 0.502 | 0.161 |
| 4 | 992 | 0.325 | 0.476 | 0.136 |
| 5 | 996 | 0.317 | 0.483 | 0.139 |
| 6 | 997 | 0.286 | 0.451 | 0.127 |
| 7 | 997 | 0.292 | 0.449 | 0.131 |
| 8 | 997 | 0.301 | 0.480 | 0.128 |

**Notable: no late-turn decay.** Image-only had this property too (turn 8 NDCG@20 ≈ 0.139). The additional branches maintain the late-turn precision rather than fighting it.

## Findings

### 1. Image is still doing most of the work

Adding 3 more branches (audio + cf_bpr + metadata_qwen3) to the image-only baseline lifted Hit@1000 by +5pp but **did not lift NDCG@20 above image-only**. The fused top-20 is dominated by image's high-precision continuation matches; the extra branches' candidates mostly land in ranks 20–1000.

This says: **what we add via more branches is *coverage*, not *ranking precision*.** A reranker over the deeper pool can convert that coverage to NDCG; without one, more branches yield marginal returns above top-K.

### 2. The metadata_qwen3 +21% lift didn't compound

In isolation, `metadata_qwen3` boosted NDCG@20 by +21% over BM25-only baseline (`v0plus_compiler_metadata_devset` = 0.1191). Stacked on top of image + audio + cf_bpr in this config, it doesn't add meaningfully. Likely the same surface-form information is already captured by BM25's `artist_name` + `track_name` + `album_name` boosts.

### 3. cf_bpr (anchor) confirms its previous behavior

cf_bpr was known to concentrate on same-artist tracks (per the 2026-05-26 ablation). In this stacked config, it doesn't help — its same-artist contribution overlaps with image_siglip2's. The marginal value over image-only is essentially zero.

### 4. `process_constraints.exploration_policy` is now extracted, but `balanced` dominates

The new field is in the schema and the LLM extracts it. From the smoke-time audit:
- balanced: ~66% of mid-conv turns
- exploit: ~22%
- diversify_artists: ~12%
- diversify_albums: <1%

`balanced` maps to multiplier=1.0 (no-op) in the current config — preserves legacy behavior. Only the ~12% `diversify_artists` turns get an anchor-artist demote of 0.4×. That's a small slice; macro impact on NDCG@20 is likely <1pp.

To actually move the needle from `exploration_policy`, we'd need to either:
- Tune `ANCHOR_ARTIST_DEMOTE_BY_POLICY[balanced]` away from 1.0 (apply soft demote on the dominant cohort) — but the cohort audit showed that even `balanced` turns have 38% continuation GTs, so blanket demote risks recall loss
- Improve extractor recall so more diversify-eligible turns get flagged out of `balanced`

### 5. Empty / shallow-pool tail regressed

This run has 62/8000 = 0.78% shallow + empty rows vs image_devset's 0.03%. Root cause: Pydantic `op='between' requires start` validation errors when the LLM emits a malformed `release_date` hard_filter (likely re-introduced by the new prompt section changing the cache key and surfacing rare extractor outputs).

**Action:** soften the HardFilter validator to tolerate `None`-bounded `between` filters (treat as no-op rather than crashing the whole turn). Cheap fix; recovers ~50 turns of recall.

## What didn't change vs the prior pattern

The dominant structural finding from the 2026-05-26 ablation still holds:
- **Novel-artist cohort (~64% of turns) Hit@20 ≈ 0.10** — the bottleneck is here, not in pool coverage
- **Continuation cohort Hit@20 ≈ 0.66** — strong, but only 36% of turns
- **Ranking-only headroom on the current pool: +0.13 NDCG@20** (from a cross-encoder reranker)

This run's similar shape (high pool coverage, modest top-K precision lift over image) confirms: the next high-leverage move is structural — a cross-encoder reranker over the top-200 pool, scoring (turn_intent_text, candidate_track_text) pairs directly. The `process_constraints` work just laid in the schema + framework groundwork; the actual NDCG@20 lift needs a different lever.

## Recommendations

### Ship now
- **None** — this run does not beat the canonical `v0plus_compiler_image_devset` config. Keep image_devset as the canonical until a structural change (reranker) is wired in.

### Worth running next (small effort)
1. **Fix the HardFilter `between` validator** — recover the 50 shallow rows. May lift macro NDCG@20 by ~0.5pp.
2. **Tune `ANCHOR_ARTIST_DEMOTE_BY_POLICY[balanced]`** — try 0.7 / 0.8 / 0.9 and measure. The cohort math suggests a mild demote could help novel-artist without too much continuation loss; needs measurement to confirm.
3. **BM25-fallback path on extractor failure** — turns where the LLM returns `state=None` currently return 0 candidates. Even a degenerate BM25 over last-user-text would help.

### The actual lever (medium effort)
4. **Cross-encoder reranker over top-200** — the structural change that converts our +5pp Hit@1000 coverage into NDCG@20 lift. All the framework groundwork (PostFusionReranker, FeatureTrace) is now in place to plug a reranker into.

## Operational notes

- **Sharded inference works.** 4-way sharded run completed in ~30 min total wall time (vs single-shard projected ~3 hrs). Each shard ~30 min independently.
- **Pydantic between-filter bug needs fixing** before next major run — eats ~0.6% of turns silently.
- **Local LanceDB doesn't have `album_id_of`** — caught during smoke. `SessionAnchorFeature` was patched to drop album-level demote until catalog gains the method.

## Artifacts

- Predictions: `evaluator/exp/inference/devset/v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset.json` (merged from 4 shards)
- Per-shard predictions: `..._devset.shard_{0..3}.json`
- Per-shard traces: `..._devset.shard_{0..3}_trace.json`
- Aggregate scores (strict-null): `exp/scores/devset/v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset.json`
- Per-sample metrics: `exp/scores/devset/v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset_samples.csv`
- Non-shallow rescore: [`scripts/score_nondeep.py`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/scripts/score_nondeep.py)

## Code changes that landed during this experiment

- New: [`mcrs/qu_modules/post_fusion_features.py`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/qu_modules/post_fusion_features.py) — generic feature-based reranker framework (2 features, internal sub-rule breakdown for future LTR)
- Modified: [`mcrs/qu_modules/compiler_v0plus.py`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/qu_modules/compiler_v0plus.py) — `_apply_soft_adjustments` now delegates to `PostFusionReranker`
- Modified: [`experiments/analysis/conversation_state_extraction_bakeoff/schema.py`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/conversation_state_extraction_bakeoff/schema.py) — added `ProcessConstraints` + `ExplorationPolicy` enum
- Modified: [`experiments/analysis/conversation_state_extraction_bakeoff/prompts.py`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/conversation_state_extraction_bakeoff/prompts.py) — added process_constraints rules + 2 new few-shots (diversify_artists, exploit)
- New tests: [`tests/test_post_fusion_features.py`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/tests/test_post_fusion_features.py) — 14 tests, all pass
