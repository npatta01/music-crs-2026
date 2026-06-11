# Review Handoff: Trained Union-Pool Reranker — Work, Findings, Plan

**Date:** 2026-06-11 · **Branch:** `claude/busy-ishizaka-f3d4a7` (pushed) · **Author:** Claude session
**Requested review:** methodology holes, leakage audit, feature gaps, model-class opinion, eval design. Be adversarial.

## 0. Task context

RecSys Challenge 2026 (Music CRS): given a multi-turn conversation, retrieve 20
tracks from a 47k catalog. CodaBench score = 0.50·nDCG@20 + 0.10 catalog +
0.10 Distinct-2 + 0.30 LLM-judge response. Devset = 1000 sessions × 8 turns.
Data is SYNTHETIC (organizer LLM pipeline). **GT = the track the generating
system recommended and "played" at that turn — not a platonic "what the user
wanted".** A competitor reports nDCG@20 ≈ 0.65.

## 1. What was done this session (chronological)

### 1.1 Retrieval baseline promotion (paired-smoke methodology)
- Methodology: seeded session slices via `run_experiment.py --num_sessions N`
  (same `SUBSET_RANDOM_SEED` → byte-identical sessions across configs), paired
  per-turn t-tests from per-sample CSVs. Established after an earlier invalid
  slice-vs-full comparison.
- Result: pruning duplicate Qwen-0.6B dense branches = +0.0137 ndcg@20
  (t=3.1, n=800 paired turns). `catalog_exact` BM25 policy = consistent small
  regression, retired. Full devset: **`v0plus_compiler_pruned_resolved_tags_devset`
  NDCG@20 0.1374** (prior baseline 0.1255). Reports:
  `experiments/seed50_paired_smoke_matrix.md`,
  `experiments/v0plus_compiler_pruned_resolved_tags_devset.md`.

### 1.2 Tiered tag resolver (`mcrs/qu_modules/tag_resolver.py`)
exact(1.0)→alias(0.9)→substring(0.8)→embedding(cosine) phrase→catalog-tag
grounding; 27k frequency-filtered tag-embedding index. Retrieval-neutral
(paired +0.0006) but supplies scored tag features. LLM tier rejected on
fire-rate data (lexical tiers ground 97% of real phrases).

### 1.3 Miss audit (`experiments/miss_audit_2026_06_11.md`)
All 3,429 in-pool misses (GT in union@200, not in final top-20; 42.9% of
turns). Per-feature "GT beats median of current top-20" rates:
era-relative popularity 46%, popularity 44%, cf-to-last-played 38%,
cf-centroid 36%, user_cf 35%, same-artist 23%, tag overlap 15–18%.
No single feature beats the whole top-20 >10% → combination problem.
132-row LLM judgment: 84% of GTs plausible, 10% contradictory (7/13 of those
= "asked for different artist, GT is same artist again"), 6% taste.

### 1.4 LambdaMART v1 (`scripts/rerank/`, report `experiments/rerank_lambdamart_v1_2026_06_11.md`)
- Features: 98 cols/candidate over union@200 pools of the baseline's full
  devset trace (7.72M rows, 7,182 playable turns). Groups: per-branch
  rank/score/hit (11 branches; dense scores = query↔candidate cosines),
  catalog priors (popularity, era-relative popularity, year, duration,
  tag_count, artist size), session similarity (cf/CLAP/SigLIP to last-played
  and centroid, cf drift), user (user-cf cosine, demographics-derived),
  organizer fields (goal category/specificity, listener_goal embedding
  cosine), state-derived (grounded-tag overlap ×3 forms incl. soft
  tag-embedding cosine, request/intent categoricals, temporal), 0.6B
  query-string cosines computed for ALL candidates, 3 named crosses,
  8 within-pool percentiles.
- Trainer: LightGBM lambdarank@20, session-split 700/150/150, early stopping.
- **Held-out test (150 sessions, 895 playable turns): NDCG@20 0.2554 vs RRF
  0.1786 (+43%, paired t=8.46); hit@20 0.508 vs 0.380; hit@1 0.097 vs 0.057.**
- Ablation: no-pool-features arm = 0.2362 (+32% vs RRF) → lift is
  content-driven, not consensus re-derivation.
- Projected overall devset ≈ 0.19 (= 0.746 playable share × 0.34 conversion).

### 1.5 Bug checks performed after owner challenge
1. Replay leakage: 0/8000 GTs were previously-played tracks.
2. Eval consistency: standalone RRF heuristic reproduces trainer baseline to
   4 decimals.
3. Triviality: best simple heuristic (same_artist×10 + cf_last + user_cf)
   scores 0.122 < RRF 0.179 < model 0.255 — not one pattern.
4. Importance artifact found: gain importance ranked `artist_track_count` #1
   despite ~zero marginal separation (GT 31.6 vs pool 30.5) — high-cardinality
   split noise. True separators: same_artist (0.52 vs 0.03), cf_last (0.153
   vs 0.046), user_cf (0.136 vs 0.081), clap/siglip centroid (+0.15 each).
   v2 should report permutation importance.

### 1.6 v2 (in flight at handoff time)
- **Null-free features** (owner requirement): rank sentinel pool_k+1; score
  imputed below branch's lowest retrieved score; has_history / has_user_vec /
  has_year flags; all cosines default 0. Rationale: v1 NaN asymmetry (GT
  rrf_rank NaN 7% vs pool 32%) let the model read missingness as a GT tell.
- **RRF features removed from model inputs** (owner decision): rrf_rank /
  rrf_score / pct_rrf_score are eval-baseline only. Per-branch raw
  ranks/scores retained.
- New: within_artist_pop (head-ordering), title_request_overlap,
  x_pop_within_artist.

## 2. Owner corrections that bound the plan (treat as constraints)

1. **#95 LLM-listwise (gpt-4o, +21% NDCG on devset pools) did NOT confirm on
   a blindset experiment.** Do not treat LLM rerank/distillation as proven.
2. **Response generation is DONE** (PR #114 on main: state-conditioned
   qwen3-30b-a3b for Blind-A). Not an open workstream.
3. **Don't widen pools before conversion improves**: at 0.34 conversion on
   @200, the rank-201–1000 GTs (hardest) would convert worse while diluting;
   union@200 ceiling 0.746 is not the binding constraint.
4. GT = generator's recommendation → "recommendability" priors (popularity,
   within-artist fame) are legitimate signal, and contradictory-GT turns are
   signal, not noise.

## 3. Gap decomposition (why 0.19 vs competitor 0.65)

overall = playable_share × conversion. Now: 0.746 × 0.34 = 0.19 (v1).
Perfect ranker on @200 = 0.746. Competitor 0.65 ⇒ near-perfect conversion on
deep pools ⇒ almost certainly train-split-scale learning (121,592 turns vs
our 5.6k) and/or sequence modeling of the generator's next-play distribution.

## 4. Plan (priority order)

1. v2 retrain (null-free, no-RRF) — running.
2. **Train-split scale-up**: the no-pool model's features need NO state
   extraction and NO retrieval (verified in miss audit) → 121,592 training
   turns for free. Negatives sampled to mimic pools (cf-neighbors of last
   played, popularity/era-matched, same-artist, random).
3. Head-ordering features (hit@20 0.508 but hit@1 0.097): within-artist
   popularity (added), title↔request (added), album sequencing (album_id
   membership only — no track order data), prior-turn assistant-text
   embedding cosine (deferred; prior turns only, no leak).
4. Sequence model over played-track embedding history (SASRec-style, items =
   provided cf/audio vectors) when GBDT plateaus.
5. Production integration: deferred rerank pass behind config flag; paired
   seeded smoke; blind-A as honest test.

## 5. Specific review questions

1. **Leakage**: organizer cf_bpr track/user embeddings were trained on
   interaction data that plausibly INCLUDES devset sessions' plays — user_cf
   cosine to GT may partially memorize the answer. Is this exploitable
   legitimately (everyone has it; blind users have embeddings, test_cold
   users lack history) or will it inflate devset vs blind delta? How to
   bound this risk empirically?
2. Is the session-split eval sufficient, or do turn-level temporal effects
   (later turns share more history with train turns of OTHER sessions) leak?
3. Negative-sampling design for train-split scale-up: pool-mimicking
   negatives vs uniform — failure modes?
4. Feature gaps you'd add (we have no: BM25 score fill-in for non-retrieved,
   8B/CLAP query cosine fill-in for non-retrieved, album track order, artist
   embedding centroids, lyric text).
5. Model class: GBDT → sequence model jump now or after train-split GBDT?
6. Any reason the +43%-over-RRF result is still too good (what would you
   check next)?

## 6. Key artifacts

| What | Path |
|---|---|
| Feature extractor | `scripts/rerank/build_features.py` |
| Trainer | `scripts/rerank/train_lgbm.py` |
| v1 features (98 cols, has NaN, incl. RRF) | `exp/analysis/rerank/features/` |
| v2 features (105 cols, null-free) | `exp/analysis/rerank/features_v2/` |
| v1 model + report | `exp/analysis/rerank/model_v1/`, `experiments/rerank_lambdamart_v1_2026_06_11.md` |
| Miss audit | `scripts/miss_audit.py`, `experiments/miss_audit_2026_06_11.md`, `exp/analysis/miss_audit/` |
| Devset trace (pools+state, 4.4GB) | `exp/inference/devset/v0plus_compiler_pruned_resolved_tags_devset_trace.jsonl` |
| Baseline report | `experiments/v0plus_compiler_pruned_resolved_tags_devset.md` |
| Smoke-matrix methodology | `experiments/seed50_paired_smoke_matrix.md` |
