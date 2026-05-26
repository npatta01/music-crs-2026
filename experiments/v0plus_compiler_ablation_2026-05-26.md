# v0+ Compiler embedding ablation — 2026-05-26

**Status:** `analyzed`
**Question:** Which embedding signals lift v0+ retrieval over the BM25-only baseline, and where do the remaining gaps lie?

## TL;DR

- **`image_siglip2` is the single biggest lever** — +48% NDCG@20, +107% Hit@1, +61% MRR over BM25-only baseline. Cover-art embeddings are a remarkably strong same-artist / same-era signal.
- **No single modality fully solves the novel-artist gap** (64% of devset turns, baseline Hit@20 = 0.093). The best single signal lifts novel-artist Hit@20 by only +8%.
- **All-embeddings combination** is the best for novel-artist Hit@20 (+29%) and overall pool coverage (Hit@1000 +18%) but slightly trails image-only on NDCG@20.
- **Two qwen3 dense branches actively hurt** at the macro level (attributes -7%, lyrics -9% NDCG@20). Only `metadata_qwen3` is positive (+21%).
- **`user_cf_bpr` is essentially neutral** (+1% NDCG@20) despite firing on every turn including turn 1. User preferences are too coarse without conversational context.

## Setup

All runs share an identical pipeline EXCEPT the set of retrieval branches fused into RRF:
- LLM extractor: `gemma-3-12b-it` via OpenRouter (cached responses across all runs after the first)
- Resolver: same fuzzy-match settings
- BM25 corpus: track_name, artist_name, album_name, tag_list (always on)
- LanceDB: same index, same fixed_size_list embedding columns
- RRF k=60, uniform weights across branches except where noted
- Devset: 1000 sessions × 8 turns = 8000 turns

The only difference per config is the `dense_branches` and `centroid_only_branches` lists. See [`configs/v0plus_compiler_*_devset.yaml`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/configs).

## Headline metrics — 10 configs, ranked by NDCG@20

| # | Config | Hit@1 | Hit@10 | Hit@20 | Hit@100 | Hit@1000 | NDCG@20 | MRR | Δ NDCG@20 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **+ image_siglip2** | **0.052** | 0.224 | 0.300 | 0.440 | 0.598 | **0.146** | **0.107** | **+48.4%** |
| 2 | + all embeddings | 0.044 | 0.224 | 0.309 | **0.478** | **0.673** | 0.143 | 0.101 | +45.1% |
| 3 | + audio + image | 0.045 | 0.224 | **0.303** | 0.447 | 0.633 | 0.142 | 0.101 | +44.4% |
| 4 | + metadata_qwen3 | 0.039 | 0.184 | 0.259 | 0.417 | 0.583 | 0.119 | 0.085 | +21.0% |
| 5 | + audio_laion_clap | 0.034 | 0.169 | 0.239 | 0.421 | 0.643 | 0.108 | 0.077 | +10.0% |
| 6 | + cf_bpr (anchor) | 0.031 | 0.159 | 0.230 | 0.371 | 0.528 | 0.104 | 0.073 | +5.3% ¹ |
| 7 | + user_cf_bpr | 0.027 | 0.158 | 0.230 | 0.409 | 0.618 | 0.100 | 0.069 | +1.2% |
| 8 | **baseline (BM25)** | 0.025 | 0.156 | 0.233 | 0.404 | 0.571 | 0.098 | 0.066 | — |
| 9 | + attributes_qwen3 | 0.025 | 0.142 | 0.214 | 0.419 | 0.635 | 0.092 | 0.064 | -6.7% |
| 10 | + lyrics_qwen3 | 0.021 | 0.142 | 0.216 | 0.396 | 0.587 | 0.090 | 0.060 | -8.9% |

¹ cf_bpr (anchor) ran with a partially-cold LLM cache and had a 12.72% extractor `state=None` rate; every other run had ~0.14%. The 12.6 pp reliability gap drags cf_bpr's macro down. A cache-warm re-run would likely score 3–5% higher.

## Cohort breakdown — novel-artist vs continuation

The dataset has 64.3% novel-artist turns (GT artist not seen in prior turns of this session) and 35.7% continuation. Baseline Hit@20 is **5x worse** on novel-artist (0.093 vs 0.486). Every embedding does something different to these cohorts:

| Config | Novel Hit@20 | Novel Hit@100 | Novel NDCG@20 | Cont Hit@20 | Cont NDCG@20 |
|---|---:|---:|---:|---:|---:|
| baseline (BM25) | 0.093 | 0.181 | 0.044 | 0.486 | 0.197 |
| + user_cf_bpr | 0.091 (-2%) | 0.193 (+7%) | 0.041 (-6%) | 0.479 (-1%) | 0.206 (+5%) |
| + cf_bpr (anchor) | 0.085 (-8%) | 0.173 (-5%) | 0.039 (-10%) | 0.491 (+1%) | 0.219 (+11%) |
| + audio | 0.098 (+6%) | 0.210 (+16%) | 0.047 (+8%) | 0.493 (+1%) | 0.218 (+11%) |
| + image | 0.100 (+8%) | 0.193 (+7%) | 0.048 (+9%) | **0.661 (+36%)** | **0.324 (+64%)** |
| + audio + image | 0.108 (+16%) | 0.214 (+18%) | 0.050 (+14%) | 0.654 (+35%) | 0.308 (+57%) |
| + attributes_qwen3 | 0.094 (+1%) | 0.216 (+19%) | 0.039 (-10%) | 0.430 (-12%) | 0.187 (-5%) |
| + lyrics_qwen3 | 0.094 (+1%) | 0.182 (+1%) | 0.042 (-3%) | 0.434 (-11%) | 0.175 (-11%) |
| + metadata_qwen3 | 0.093 (+0%) | 0.185 (+2%) | 0.044 (+0%) | 0.558 (+15%) | 0.255 (+29%) |
| **+ all embeddings** | **0.120 (+29%)** | **0.260 (+44%)** | **0.052 (+19%)** | 0.649 (+34%) | 0.307 (+56%) |

**Key insight:** image_siglip2's massive macro lift is almost entirely a *continuation* lift (Cont NDCG@20 +64%). It barely helps the novel-artist cohort (+9% NDCG@20). The dataset's structure (64% novel-artist) caps how much image can win unless paired with novel-artist coverage.

The "+ all embeddings" config is the **only one that materially moves novel-artist Hit@20** (+29%) and Hit@100 (+44%). It pays for that with a slightly weaker continuation lift than image-only — diversification at the cost of peak precision.

## Per-turn NDCG@20 — where each modality fires

| Turn | base | user | cfbpr | audio | image | a+i | attr | lyr | meta | all |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.125 | 0.105 | 0.108 | 0.129 | 0.128 | 0.128 | 0.094 | 0.106 | 0.129 | 0.122 |
| 2 | 0.148 | 0.126 | 0.138 | 0.133 | **0.185** | 0.166 | 0.123 | 0.121 | 0.168 | **0.185** |
| 3 | 0.113 | 0.122 | 0.111 | 0.120 | 0.157 | 0.157 | 0.111 | 0.102 | 0.149 | 0.159 |
| 4 | 0.097 | 0.100 | 0.108 | 0.103 | 0.143 | 0.138 | 0.097 | 0.085 | 0.116 | 0.145 |
| 5 | 0.091 | 0.099 | 0.096 | 0.108 | 0.143 | 0.143 | 0.092 | 0.089 | 0.111 | 0.147 |
| 6 | 0.078 | 0.084 | 0.088 | 0.096 | 0.133 | 0.130 | 0.077 | 0.081 | 0.098 | 0.122 |
| 7 | 0.073 | 0.081 | 0.089 | 0.094 | 0.142 | 0.142 | 0.075 | 0.073 | 0.093 | **0.130** |
| 8 | 0.062 | 0.080 | 0.091 | 0.083 | 0.139 | 0.132 | 0.066 | 0.061 | 0.088 | **0.131** |

**Turn 1 is the floor for every config** — the anchor-track-centroid branches all skip (no anchors yet), and user_cf_bpr / qwen3 actually *hurt* turn 1 (the broad user prior conflicts with a specific first-turn query like "Play 'Heart-Shaped Box' by Nirvana").

**Turn 2 is the peak for image-only / all-embeddings** (NDCG@20 = 0.185) — exactly one positive anchor, no state-accumulation noise yet, image's centroid is tightest.

**By turn 8, only image / a+i / all maintain >0.13 NDCG@20** — the rest fall off with the conversation depth. This is where image's "find more of what they like" pattern is most useful: the user's preferences have crystallized and the cover-art clusters are coherent.

## Modality analysis — what each signal actually does

### image_siglip2 (cover art, 768d)
- **What it captures:** genre cluster + era + visual aesthetic. Cover art for 90s grunge has very different visual style from 2010s pop.
- **What it does well:** continuation (find more of the same artist / aesthetic — Cont NDCG@20 +64%). Pool depth in top-20 (Hit@1 +107%).
- **What it doesn't do:** bridge to genuinely-different artists. Novel-artist Hit@20 only +9%. It clusters tightly, which is great when you want more of the same and bad when you want variety.
- **Verdict:** ship it.

### audio_laion_clap (sonic, 512d)
- **What it captures:** acoustic similarity from raw audio waveform.
- **What it does well:** pool coverage (Hit@1000 +12.6%, second only to "all embeddings"). Novel-artist Hit@100 +16% (bridges artists with similar sound).
- **What it doesn't do:** top-of-list precision is weaker than image (Hit@1 +37% vs image's +107%).
- **Verdict:** complementary to image — combine for the novel-artist cohort.

### cf_bpr (anchor) — track-side, co-listening
- **What it captures:** "users who listened to anchor track A also listened to track B" — co-listening behavior from training data.
- **What it does well:** modest lift on continuation (+11% Cont NDCG@20).
- **What it doesn't do:** novel-artist coverage *regresses* (-10% novel NDCG@20). cf_bpr neighborhoods are dominated by same-artist tracks (because the user-track factorization concentrates on within-artist co-listening). Hit@100 actually drops -8% (collateral damage from the narrowed pool).
- **Reliability handicap:** 12.7% extractor failure rate inflates this run's negative numbers. Probably the true effect is closer to neutral than -10%, but still doesn't move the needle.
- **Verdict:** keep only if "+ all embeddings" measurably wins over "image + audio".

### user_cf_bpr — user-side, history-based
- **What it captures:** user's historical taste cluster (mean of tracks they've listened to over time).
- **What it does well:** Hit@1000 +8.4% — modest pool expansion.
- **What it doesn't do:** turn-1 (where it should shine the most — no anchors) actually *regresses* -16%. The user's broad historical taste conflicts with a specific turn-1 query. Novel-artist NDCG@20 -6%.
- **Why it underperforms:** user vectors are aggregated over months/years of listening — too coarse to inform a single conversational turn. Even on turn 1 where it's the only personalization signal, BM25's literal text match wins.
- **Verdict:** weak signal. Could plausibly contribute as a tiny-weight backbone in a multi-signal RRF, but standalone it's basically neutral.

### attributes_qwen3 (genre/mood text, 1024d)
- **What it captures:** dense semantic embedding of the track's attributes-style tag list.
- **What it does:** **regresses NDCG@20 -7%**. Continuation Hit@20 drops -12%. Pool depth lifts (Hit@1000 +11.3%, Hit@100 +19% on novel) but the ranking inside is worse.
- **Why it fails:** the encoded query text (from `turn_intent`) and the track's attributes embedding don't align — the model embeds different aspects of music. Lots of false-positive matches in the top-20.
- **Verdict:** drop.

### lyrics_qwen3 (lyric content, 1024d)
- **What it does:** **regresses NDCG@20 -9%, Hit@1 -17%**. Worst single modality.
- **Why it fails:** lyrical similarity is barely correlated with what users *say they want* in a conversation. A user asking for "energetic 90s grunge" doesn't care about Cobain's specific lyrics.
- **Verdict:** drop.

### metadata_qwen3 (title/artist/album text, 1024d)
- **What it does:** **best of the qwen3 family** at +21% NDCG@20. Hit@1 +54%.
- **Why it works (when others don't):** the metadata column contains "artist - track - album" surface forms — exactly the kind of text the LLM puts in `turn_intent`. Acts as a fuzzy semantic-BM25.
- **Verdict:** keep as the qwen3 backbone if any. Better than the other two qwen3 variants — but image still wins for less effort.

## The gaps — where are we still losing?

### Gap 1: Novel-artist coverage (64% of turns)

Baseline Hit@20 on the novel-artist cohort = **0.093**. Best config ("+ all embeddings") = **0.120** — that's +29% relative but still only **12% absolute**. Meaning even our best system fails to find the GT in the top-20 on **88% of novel-artist turns** (= **56.6% of ALL devset turns**).

**Headroom:** if a perfect ranker pushed every Hit@1000 to rank 1 on the novel-artist cohort, novel NDCG@20 would go from 0.052 → ~0.26 (the all-embeddings Hit@1000 = 0.21 on novel × NDCG-of-rank-1-when-found). That's a +0.07 macro NDCG@20 lift = **+50% over current**. The headroom is in *ranking inside the pool*, not in finding more candidates.

**Why our existing signals can't close this:** every embedding modality we have is *anchor-centric*. Each branch's query is "find tracks like the ones I've accepted so far". That works against novel-artist by construction — the GT is *deliberately different*. No amount of cf_bpr / audio / image / qwen3 will fix this; they all start from the same anchor centroid.

The signal that could actually attack this is **anchor-free conditioning** on the listener's *intent* expressed in the turn message, scored against tracks directly. That's a cross-encoder reranker over the full top-1000 pool — pair (intent_text, track_text) → relevance.

### Gap 2: Empty-pool turns (varies 0.1% – 12.7% by config)

When the LLM extractor fails (returns `state=None`), the compiler returns 0 candidates and the turn scores 0 on all metrics. Baseline-pipeline rate ~0.1%. cf_bpr-run rate spiked to 12.7% due to cold-cache provider throttling on first encounter with the new prompt. After cache warmup, all subsequent runs hold at ~0.1%.

**Fix:** add a fallback path — if the LLM extractor returns None, fall through to BM25-only retrieval using the raw last-user-turn text. Currently those turns return [] entirely, which is the worst case. Even a 20% Hit@20 on those (BM25 fallback) would lift the macro by 1-2% absolute.

### Gap 3: Turn 1 floor

Every config converges to NDCG@20 ≈ 0.125 on turn 1 (or worse). No anchor exists; the centroid-based branches all skip. **Turn 1 is 12.5% of all turns** and we're leaving its potential untapped.

**Options:**
- A weaker BM25-only ranker (already in place) handles turn 1
- Cross-encoder on top-100 would attack this directly (no anchor needed)
- user_cf_bpr was the candidate fix but it *regresses* turn 1 — coarse user prior + specific first-turn query don't mix

### Gap 4: State-accumulation collapse (turns 6–8)

NDCG@20 by turn for baseline: 0.125 (T1) → 0.062 (T8) — a 50% decay. The image config flattens this to 0.128 → 0.139, but for the other configs the decay persists.

**Root cause (per the original v0+ analysis):** by turn 8 we have 4+ "accepted" anchor tracks, and the LLM extractor faithfully includes all of them. The centroid is a blurred average. Adding recency weighting (drop anchors older than 2 turns) hasn't been tested yet.

### Gap 5: cf_bpr's same-artist tunnel vision

cf_bpr was hypothesized to bridge to behaviorally-similar *different* artists. The data shows it does the opposite — concentrates on same-artist deep cuts. Cohort-wise novel-artist Hit@20 dropped -8% vs baseline.

**Mechanism:** BPR factorization minimizes within-user pairwise loss. Users with strong artist loyalty (which the data has) get vectors that cluster tightly around their dominant artist. The "neighborhood" in cf_bpr space is mostly that artist's catalog.

**Implication:** cf_bpr is the wrong shape of signal for novel-artist coverage. Audio (sonic similarity across artist boundaries) is structurally better suited.

## Reliability — extractor failure rate per run

| Run | state=None | Note |
|---|---:|---|
| cfbpr (run 6) | 12.72% | First run with new prompt, cold LiteLLM cache, DeepInfra rate-limited |
| all other ablations | 0.14–0.15% | Cache warmed from prior runs |
| original devset (run 5) | 0.06% | (subset of full devset; baseline of comparison) |

The 12.7% spike in cf_bpr is the single largest confound across this campaign. A clean re-run would be required for a fully-apples comparison with the other modalities, but the directional story (cf_bpr hurts novel-artist, helps continuation modestly) is consistent with the cohort breakdown and isn't a cache artifact.

## Recommendations

### Ship now
- **`v0plus_compiler_image_devset` as the new canonical retrieval config.** +48% NDCG@20 over BM25 baseline with one extra branch. Negligible eval cost (single LanceDB ANN per turn that fires) and stable across the run distribution.

### Worth running next (small-effort experiments)
1. **`image + audio` weighted RRF** — measure if upweighting image (w=2.0) vs audio (w=1.0) beats equal weights. The asymmetric value (image for precision, audio for coverage) suggests asymmetric weights win.
2. **`all embeddings` minus the two failing qwen3 branches** (attributes, lyrics). Keep only metadata_qwen3 + image + audio + cf_bpr (anchor) + user_cf_bpr. Hypothesis: removes -7% drag from attributes and -9% drag from lyrics.
3. **BM25-fallback on extractor failure** — currently empty pools on those turns. Adding a passthrough BM25 lift on those rare turns should be ~free.

### Bigger lever (medium effort)
4. **Cross-encoder reranker over top-200** — paired (intent, candidate) scoring, no anchor centroid needed. Should attack the novel-artist gap directly. Expected lift: +20–40% NDCG@20 *on top of* the current image-best config.

### Don't pursue
- More user-side embeddings (we only have cf_bpr; adding more would require training a joint model)
- Tuning cf_bpr (anchor) weights further — fundamental mismatch with novel-artist
- Lyrics-based retrieval — wrong signal for this task

## Artifacts

| tid | predictions | trace | scores |
|---|---|---|---|
| v0plus_compiler_devset (BM25 baseline) | exp/inference/devset/ | exp/inference/devset/ | evaluator/exp/scores/devset/ |
| v0plus_compiler_user_devset | " | " | " |
| v0plus_compiler_cfbpr_devset | " | " | " |
| v0plus_compiler_audio_devset | " | " | " |
| v0plus_compiler_image_devset | " | " | " |
| v0plus_compiler_audio_image_devset | " | " | " |
| v0plus_compiler_attributes_devset | " | " | " |
| v0plus_compiler_lyrics_devset | " | " | " |
| v0plus_compiler_metadata_devset | " | " | " |
| v0plus_compiler_all_devset | " | " | " |

All 10 configs in [configs/v0plus_compiler_*_devset.yaml](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/configs).

## Commits

Code changes that landed during this campaign:

- `compiler_v0plus.py`: generalized cf_bpr branch into `centroid_only_branches: list[CentroidOnlyBranch]`. Added `centroid_source: "anchor_tracks" | "user"`. Pass `user_id` through `compile()`.
- `compiler_v0plus_qu.py`: parse the new YAML, plumb user_id through `batch_compile_track_ids`.
- `user_embeddings.py`: new `UserEmbeddings` catalog loading `talkpl-ai/TalkPlayData-Challenge-User-Embeddings` (8616 users with cf_bpr vectors).
- `crs_baseline.py`: forward user_ids per batch-row to QU when the QU signature accepts them.
- `mcrs/lancedb/indexing.py`: pin all embedding columns to `fixed_size_list<float32>[dim]` so audio/image/cf_bpr become native-ANN-queryable (was a prerequisite from earlier in the campaign).
- New ablation configs: `v0plus_compiler_{attributes, audio, audio_image, cfbpr, image, lyrics, metadata, user, all}_devset.yaml`.
