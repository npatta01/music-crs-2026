# v0+ Retrieval Recall-Gap Analysis — Full Devset

**Date:** 2026-05-29
**Author:** Claude (agentic analysis)
**Purpose:** Diagnose why Hit@1000 is only 0.641 on the v0+ multimodal retrieval pipeline, decompose the gap by multiple angles, and produce prioritized, actionable levers. Written to be reviewed independently (by another LLM or engineer) with no prior session context.

---

## 0. TL;DR

- **Hit@1000 = 0.641** on full devset (8000 turns). **100% of ground-truth (GT) tracks are in the catalog**, so the entire 35.9-pt gap is recoverable in principle.
- The gap splits cleanly into two mechanisms:
  - **Fusion/cutoff loss = 13.9 pts (1111 turns):** a retrieval branch *did* fetch the GT into its own top-1000, but the RRF fusion step dropped it from the final top-1000. **Cheap to recover.**
  - **Never-reach = 22.0 pts (1761 turns):** *no* branch fetched the GT. **Needs new/better retrieval signals.** (Total fused misses = 8000 − 5128 = **2872**.)
- **The single dominant predictor of a miss is whether the GT artist is named in the conversation:** named → Hit@1000 = 0.889; not-named → 0.511 (**+37.8 pts**). This one axis explains ~89% of fused misses and ~94% of never-reach.
- **Counter-intuitive findings (high-confidence, see §6):** fusion loss is a *lone-branch* problem (so agreement-reweighting would hurt, not help); popularity is wrong-signed (popular tracks recall *worse*); the never-reach core is *not* long-tail/poor-metadata.
- **Top levers by impact/effort:** (1) per-branch fusion **quota** [~14 pts, low effort]; (2) named-artist **resolver branch** [~4 pts, spans both pools]; (3) anchor-free **query-text dense** branch for cold-start/pivot [never-reach]; (4) exact-**tag-match** branch [never-reach]. De-prioritize popularity/era item features and extractor verbosity.

---

## 1. What was measured and on what data

**System under test:** `v0plus_compiler_mm_extractor_v3_devset` — the v0+ conversation-state compiler with the multimodal retrieval base (BM25 + 4 embedding branches) and the v3 extractor (gemma-4-26b-a4b-it). Retrieval branches are identical to the canonical `bm25_image_audio_cfbpr_metadata` base; the extractor is the experimental v3 prompt. **For recall (Hit@1000) on this run, the current branch/fusion limits are the binding constraint — but the extractor variant is NOT immaterial:** extracted state still controls the anchors, positive tags, release filters, and (future) branch routing that determine the branch *union* itself. Accurate framing: fusion/cutoff + missing-branch coverage dominate the gap here, while extractor-state quality sets the ceiling those branches can reach. This report is primarily about retrieval coverage, not top-K ranking.

**Branches in the fused pool (5):**
| branch | type | what it matches |
|---|---|---|
| `bm25` | sparse lexical | track/artist/album/tag text vs. query text |
| `dense.default.intent.metadata_qwen3_embedding_0_6b` | dense | qwen3 embedding of metadata vs. intent text |
| `centroid.anchor_tracks.audio_laion_clap` | centroid | CLAP audio embedding of accepted/anchor tracks → catalog audio |
| `centroid.anchor_tracks.image_siglip2` | centroid | SigLIP2 cover-art embedding of anchor tracks → catalog image |
| `centroid.anchor_tracks.cf_bpr` | centroid | collaborative-filtering BPR embedding of anchor tracks |

Fusion = weighted Reciprocal Rank Fusion (RRF), final cut at top-1000.

**Data sources (all joined into one per-turn table):**
- Predictions: `inference/devset/v0plus_compiler_mm_extractor_v3_devset.json` (8000 turns, fused top-1000 per turn).
- Per-branch rankings: the same run re-executed with `branch_trace_topk=1000`, producing `..._trace.json` with each branch's top-1000 candidate IDs per turn.
- Ground truth: `ground_truth/devset.json` (one GT track_id per turn).
- Catalog: `talkpl-ai/TalkPlayData-Challenge-Track-Metadata` (47,071 tracks: artist_id, popularity, release_date, tag_list).
- Conversation + organizer taxonomy: `talkpl-ai/TalkPlayData-Challenge-Dataset` (test split): goal `category` (A–K), `specificity` (HH/HL/LH/LL), `listener_goal`, and per-turn conversation text. (Note: the current HF schema has **no** `expertise`/`listener_expertise` field — an earlier lookup returned null for all 8000 rows, so any `expertise` slice is unsupported and dropped.)
- Extracted state: from the trace (`turn_intent`, `mentioned_entities`, `release_year_range`, `process_constraints`, `track_feedback`, `played_track_ids`).

**Derived per-turn fields** (the analysis table, 8000 rows): GT rank in fused pool; per-branch hit booleans; `in_any_branch`; `fusion_loss` (in a branch but not fused); GT artist catalog size + bucket; GT popularity; GT release year; GT tag count; goal category/specificity/expertise; extracted intent_mode/exploration_policy/tag&artist counts/has_year_range/turn_number; and three state↔GT bridges: `tag_overlap` (extracted positive-tag tokens present in GT's catalog tags), `gt_artist_named_in_conv` (GT artist name appears literally in the conversation), `year_in_range` (GT release year inside extracted release_year_range).

**Method:** one compact table built on Modal (reads the ~1 GB trace in-container to avoid a slow download), then 5 independent analysis agents each sliced the table with Python and reported computed numbers, followed by a synthesis agent. All numbers below are computed from the table, not estimated.

---

## 2. DATA-INTEGRITY CAVEATS (read before trusting any number)

This analysis had two false starts that produced wrong numbers earlier in the session. They are **corrected** here, but a reviewer should know:

1. **Premature trace read.** An initial pass computed per-branch recall *before* the branch-trace re-run finished, yielding all-zero branch recalls and a bogus "union = fused = 0.641, fusion_loss = 0%, gap is 100% never-reach." **This is wrong and is superseded.** The correct figures (union=0.780, fusion_loss=0.139) come from the completed trace.
2. **Transcription error.** A subsequent manual summary mis-stated per-branch recalls (e.g. "bm25 0.612, metadata 0.480"). The byte-verified values are in §3.
3. **Centroid-key trap (important for re-validation).** On turn-1 and pure-`pivot` turns there are no anchor tracks, so the three `centroid.*` branch keys are **absent** from the trace row (not `False`). Any re-computation must use `row.get(branch, False)`, not `row[branch]` or key-discovery from `row[0]`, or it will silently undercount centroid recall on ~1891 turns.

**Confidence:** the headline decomposition (§3) and the named-artist effect (§5) reproduced consistently across 4–5 independent agents and are high-confidence. Per-cell taxonomy numbers (§4) are single-pass computed; directionally reliable, exact values worth a spot re-check.

---

## 3. The gap, decomposed (headline numbers)

All on n = 8000 turns.

| quantity | value | turns | meaning |
|---|---:|---:|---|
| **Fused Hit@1000** | **0.641** | 5128 | what the system actually returns |
| **Union of all 5 branches** | **0.780** | 6239 | GT in *some* branch's top-1000 (recall ceiling of current branches) |
| **Fusion/cutoff loss** | **0.139** | 1111 | GT in a branch but dropped from fused top-1000 — **recoverable** |
| **Never-reach** | **0.220** | 1761 | GT in *no* branch — **needs new retrieval** |
| GT in catalog | 1.000 | 8000 | every miss is reachable in principle |

**Per-branch recall** (GT in that branch's own top-1000):

| branch | recall | turns | unique contribution (only branch with GT) |
|---|---:|---:|---:|
| bm25 | **0.609** | 4872 | 1015 turns (12.7%) — the workhorse |
| audio_clap (centroid) | 0.358 | 2868 | 346 (4.32%) — best secondary |
| image_siglip2 (centroid) | 0.352 | 2816 | 127 (1.59%) |
| metadata_qwen3 (dense) | 0.350 | 2797 | 177 (2.21%) |
| cf_bpr (centroid) | 0.298 | 2383 | 175 (2.19%) |

**Reading:** BM25 alone gets 60.9% and uniquely contributes ~13% of all turns (1015 lone-branch turns; this corrects an earlier 27% figure that was inflated by the centroid-key trap — it matches Codex's independent `bm25_only=1015`). The four embedding branches each add only 1.6–4.3% unique recall — they are largely redundant with BM25 and with each other (audio is the most valuable secondary). The realistic recall ceiling of the *current* branch set is the union, **0.780**.

---

## 4. Gap by organizer taxonomy (goal category & specificity)

**Specificity legend:** the 2-letter code is `<query-specificity><target-specificity>` — first letter = how specific the user's *request* is, second = how specific the *target* (the one right answer) is. So **HL** = specific query, broad/any acceptable target; **LH** = vague query, one specific hidden target; **LL** = vague both; **HH** = specific both.

Hit@1000 by goal category (all values recomputed directly from `gap_table_v3.jsonl`):

| cat | meaning | Hit@1000 | n | never-reach | fusion-loss | lean |
|---|---|---:|---:|---:|---:|---|
| F | metadata | 0.692 | 760 | 0.187 | 0.121 | — |
| H | artist | 0.689 | 1080 | 0.185 | 0.126 | — |
| A | audio | 0.682 | 488 | 0.201 | 0.117 | — |
| E | refinement | 0.646 | 760 | 0.207 | 0.147 | — |
| D | context | 0.645 | 688 | 0.213 | 0.142 | — |
| B | lyrics | 0.638 | 1136 | 0.217 | 0.145 | — |
| G | mood | 0.630 | 616 | 0.234 | 0.136 | — |
| J | popularity | 0.617 | 616 | 0.232 | 0.151 | **fusion-loss** |
| K | era | 0.609 | 1248 | 0.240 | 0.151 | mixed (both high) |
| I | geography | 0.569 | 144 | 0.326 | 0.104 | **never-reach** |
| C | visual | 0.554 | 464 | 0.310 | 0.138 | **never-reach** |

By specificity: HH=0.721 (never 0.161), HL=0.654 (never 0.201), LH=0.643 (never 0.232), **LL=0.595** (never 0.258). HH is well above mean; LL is the weakest. Worst single cell: **J|LL = 0.405** (popularity + vague — fails both ways).

**Reading:** category is a real axis. Visual (C) and geography (I) are **never-reach-dominated** — the current branches have no signal for "looks colorful" or "music from Alaska." Lyrics (B) has the highest *count* of never-reach but a moderate rate, and the catalog ships no *raw* lyric text (though a `lyrics_qwen3` embedding column exists — see §11). Popularity (J) leans **fusion-loss** (high floss, lower never); era (K) is mixed (both elevated). Note B and D were mis-stated in an earlier draft (0.563 / 0.685) — the verified values are 0.638 / 0.645.

---

## 5. Gap by ground-truth properties & the dominant axis

**By GT artist catalog size:** head (20+ tracks) = 0.690 (n=3554); mid (5–19) = 0.644 (n=2405); long-tail (<5) = 0.537 (n=2041). Long-tail also shows fusion loss (union 0.70 vs fused 0.537), so it's not purely a coverage problem.

**By GT popularity:** <30 = 0.605; 30–60 = **0.668**; 60+ = **0.584**. **Non-monotonic and wrong-signed** at the top — popular tracks recall *worse*.

**By GT tag count:** more catalog tags → higher recall (0 tags lowest, 11+ highest), consistent with BM25/dense leaning on tag text.

**THE DOMINANT AXIS — GT artist named in conversation:**

| | Hit@1000 | explains |
|---|---:|---|
| GT artist named | **0.889** | — |
| GT artist NOT named | **0.511** | — |
| **delta** | **+37.8 pts** | ~89% of fused misses, ~94% of never-reach |

**Leakage check (done — this is the headline, so it was verified per reviewer request).** `gt_artist_named_in_conv` is computed on the **visible prefix only**: the builder accumulates user-turn text up to and including the target turn (`convtext[sid][tn]`, cumulative), never future turns. Independent recompute: **0/7987 mismatches** vs a strict prefix-only reconstruction, and **0** turns where the artist appears *only* in future text were counted. (For context, 2029 turns DO have the GT artist mentioned *only* in later turns — and the feature correctly excludes all of them.) So the +37.8 pt effect is **real, not future-leakage.** n: named=2754, not-named=5246.

When you control for named-artist, **every other item property collapses to ~0.47–0.55** — artist size, popularity, tag count become near-useless predictors. The miss is fundamentally about whether the user gave us a resolvable artist anchor, not about the GT track's intrinsic properties.

**Corroborating extraction signal:** going from 0 → 1 extracted positive artists is worth **+15.6 pts** Hit@1000 (and −15.2 pts never-reach). Extracted *tag* count is flat/non-monotone, and `has_year_range` has ~zero effect (0.645 vs 0.631) — i.e. extractor *verbosity* doesn't help; resolvable *entities* do.

---

## 6. "We had the signal but missed it" (highest-leverage, knew-but-missed)

Among the 2872 fused misses:

- **Named-but-missed = 307 turns.** Of these, **146 had the GT inside BM25's own top-1000** (an exact lexical artist match) and RRF still dropped it — **~half of named-misses are a pure fusion cutoff bug, not a fetch gap.** 205 are fusion-recoverable, 102 are never-reach (artist named but never made it into any branch's query — a query-construction leak).
- **tag_overlap > 0 but missed = 1183 turns (never-reach).** The extractor produced a positive tag that is *literally* a catalog tag on the GT track, yet no branch fetched it. Dose-response: tag_overlap 0→1→2→3+ gives Hit@1000 0.539→0.534→0.627→**0.799**. The embedding branches are not exploiting exact tag-token matches.

**Surprises (all data-verified):**
1. **Fusion loss is a lone-branch problem:** 863/1111 (77.7%) of dropped turns had the GT in *exactly one* branch; only 50 in ≥3. RRF rewards cross-branch agreement, so it structurally evicts single-branch finds. **→ Reweighting toward agreement would make recall worse; the fix is a per-branch quota that protects lone finds.**
2. **~Half of named-artist misses are a pure cutoff bug** (GT was in BM25 top-1000, dropped in fusion).
3. **Never-reach is NOT long-tail/poor-metadata:** 57.6% of never-reach GTs have 11+ tags; ~65% are head/mid artists. The miss is upstream signal availability (no named/anchorable entity), not catalog poverty.
4. **Popularity is wrong-signed** — "boost popular tracks" is counterproductive.
5. **Specificity is a weak axis** vs. goal category; the real structure is per-category (visual/geography never-reach; era/popularity fusion-loss).

**TWO DISTINCT FAILURE REGIMES by turn depth (recomputed from the table):**

| turn | n | Hit@1000 | union | RRF/cutoff loss |
|---|---:|---:|---:|---:|
| 1 (cold-start) | 1000 | 0.549 | **0.598** | 0.049 |
| 2 | 1000 | 0.728 | 0.842 | 0.114 |
| 3 | 1000 | 0.692 | 0.815 | 0.123 |
| 4 | 1000 | 0.670 | 0.820 | 0.150 |
| 5 | 1000 | 0.634 | 0.781 | 0.147 |
| 6 | 1000 | 0.645 | 0.804 | 0.159 |
| 7 | 1000 | 0.615 | 0.788 | 0.173 |
| 8 (late) | 1000 | 0.595 | 0.791 | **0.196** |

- **Cold-start (turn 1):** union is *low* (0.598) → the failure is **never-reach** (no anchors yet, 3 centroid branches dead); RRF loss is tiny (0.049). Fix = anchor-free signal (Lever 3).
- **Late-turn (turn ≥6):** union stays ~0.79–0.80 but **RRF/cutoff loss climbs to ~0.16–0.20** → the failure is **fusion** (many branches + accumulated history compete, RRF evicts good candidates) and **carryover policy**. Fix = fusion quota (Lever 1) + history/carryover handling.
RRF loss grows ~monotonically with depth (0.049→0.196). So the single "0.139 fusion-loss" headline is really *concentrated in mid/late turns*; cold-start is almost pure never-reach. (Matches the independent reviewer exactly: turn-8 = 0.595/0.791/0.196.)

---

## 7. Prioritized action plan

Ordered by impact / effort. "Fusion pool" = the 13.9 recoverable pts; "never-reach pool" = the 22.0 hard pts.

### Rank 1 — Per-branch fusion QUOTA (cheap, ~up to 14 pts)
**Evidence:** union 0.780 vs fused 0.641 = 1111 turns fetched-but-dropped; 77% were lone-branch finds; 363 were bm25-sole; 574 were embedding-only (bm25 missed).
**Implementation:** in the compiler's fusion stage, reserve N top slots per branch from its *own* ranking before RRF merge (a quota union), then fill the rest by RRF; concurrently raise `final_topk`. Pure fusion/config change, no new model. This is **not** RRF reweighting — it must protect single-branch finds.
**Expected:** recovering even half the 13.9-pt pool lifts Hit@1000 from 0.641 toward ~0.69–0.71. Hard ceiling = union = 0.780.
**Effort:** Low. Isolated and independently A/B-able on a 50-session slice.

### Rank 2 — Named-artist resolver branch + reserved quota (~4 pts, spans both pools)
**Evidence:** named-artist is the +37.8-pt dominant axis; 307 named-but-missed (205 fusion-recoverable, 102 never-reach); 146 were a pure bm25 cutoff bug; n_pos_artists 0→1 = +15.6 pts.
**Implementation:** deterministic branch — resolve the extracted/normalized artist entity → catalog `artist_id` → fetch all that artist's track_ids → inject with reserved fusion slots so RRF can't evict an exact-artist match. Plus a cheap audit of the 102 "named but never reached" turns (likely a single query-building bug where the extracted artist token doesn't reach the bm25 query / dense intent text).
**Expected:** caps ~3.8 pts (307 turns); high confidence (signal unambiguous). The audit may surface a broader leak.
**Effort:** Low–Medium (catalog inversion + entity resolution).

### Rank 3 — Anchor-free query-text dense branch (never-reach pool, multi-pt)
**Evidence:** all 3 centroid branches have **exactly 0.000 recall on turn-1** (no anchors), so cold-start collapses to bm25+metadata only; turn-1/pivot never-reach is 40.2% vs 19.4% later (~402 of 1761 never-reach turns). Mirrors open_explore (n=1093, never=0.382) and pivot (n=727, never=0.418).
**Implementation:** add a query-text dense branch (CLAP-text and/or SigLIP-text encoder over the raw conversation turn) that fires even with no anchor tracks, with its own fusion quota. (This is the project's already-noted "anchor-free SigLIP-text + CLAP-text" direction.)
**Expected:** multi-point; the only lever that reaches open_explore/pivot/cold-start turns.
**Effort:** Medium (new encoder branch + indexing; reuses existing perceptual-embedding infra).

### Rank 4 — Exact tag-match branch (never-reach pool, multi-pt)
**Evidence:** 1183 never-reach turns have a positive extracted tag that is literally on the GT track; tag_overlap dose-response 0.539→0.799.
**⚠ GOLD-CONDITIONING CAVEAT (per reviewer):** `tag_overlap` is computed using the **GT track's own catalog tags**, so the 1183-turn / 0.799 figures are a **diagnostic upper bound**, not a guaranteed yield. In production you only know the *extracted* tags, not which match the (hidden) GT. The real question the implementation must answer empirically: does "fetch all tracks carrying the extracted tags" produce a *useful* candidate set, or does a broad tag (e.g. "pop", "rock") **flood** the pool with thousands of tracks and bury the GT? Must be validated with a tag-rarity / IDF weighting and a cap, not assumed.
**Implementation:** build a tag-token inverted index over the 47k catalog; for each positive extracted tag that is a literal catalog tag, fetch matching track_ids into the pool with reserved slots, **weighted by tag rarity** (down-weight high-frequency tags). Deterministic, no model. Also synthesizes soft anchors that feed the otherwise-no-op centroid branches on low-specificity turns.
**Expected:** *upper bound* ~14.8% of turns (1183); realistic yield unknown until the flooding/rarity question is tested. Concentrated in LL/open buckets.
**Effort:** Low–Medium.

### Rank 5 — DO NOT INVEST (de-scope to free effort)
**Evidence:** popularity is non-monotonic/wrong-signed (60+ = 0.584); release-year is flat (<9-pt spread); `has_year_range` ~zero effect; extractor tag verbosity flat; conditioning on not-named flattens all item-property effects to ~0.5. cf_bpr and image_siglip2 are the most redundant pair (lowest unique contribution 2.19 / 1.59 pts).
**Action:** de-scope a **naive global** popularity boost (it is wrong-signed in aggregate, so boosting popular tracks everywhere *hurts*), era/year item features, and extractor-verbosity work. **Important nuance (per reviewer):** wrong-signed *globally* ≠ useless — popularity should be applied **only when the query/goal asks for popular/classic/well-known tracks** (category J = popularity, and "classic"/"hits" intents), as a *routed* prior, not a global one. That routed version is a candidate lever, not a de-scope. Also consider an ablation dropping cf_bpr or image_siglip2 and reallocating compute to Ranks 3–4. **Keep audio_clap** (4.32 unique pts — the real secondary branch). New signals should be *orthogonal*, not another correlated embedding.

---

## 7a. Does our extracted STATE already contain the info? (state vs. ideal-schema vs. new-extraction)

This is the crux: for each lever, is the needed signal **already in our current extracted state** (so the fix is purely downstream retrieval/compiler), does it need the **ideal v3 schema** (a field we don't currently emit), or does it need **brand-new extraction** the LLM isn't doing? Measured from the table:

| signal the lever needs | already in current state? | evidence | what's actually needed |
|---|---|---|---|
| **Named artist** (lever 2) | **YES, mostly** — when the GT artist is named in the conversation, our state already has ≥1 positive artist entity on **84.9%** of those turns (2339/2754). | Among the 307 named-artist misses, **59% (182) had the artist in our state already** — retrieval failed despite the state being correct. | **Downstream only** (resolve state artist → catalog tracks + fusion quota). NOT an extraction problem for the majority. The other 15% (415 turns) where the artist is named but our state missed it → that IS an extraction gap (the v3 "embedded-artist" rule helps here). |
| **Exact tag** (lever 4) | **YES** — 67.2% of never-reach turns (1183/1761) already have a positive tag in our state that is *literally* a catalog tag on the GT track (`tag_overlap>0`). | The signal is in the state; no branch consumes it. | **Downstream only** (exact-tag inverted-index branch). Pure retrieval gap, zero new extraction. |
| **Fusion recovery** (lever 1) | **N/A — needs no state at all.** | 1111 turns: GT already fetched by a branch, dropped by RRF. | **Pure fusion/compiler change.** No state, no schema, no extraction. |
| **Per-turn modality / routing** (lever 3 + branch routing) | **NO — not extracted today.** Our state has `intent_mode` and `exploration_policy` but **no per-turn modality tag** (image / audio / era / lyric / popularity). | §7b: session `category` carries this but is per-session and 100%-drifts; we don't emit a per-turn equivalent. | **NEW extraction** — this is the one place we genuinely need to extract *more*. It maps to the ideal schema's `routing_tags`. The LLM already reads the dialogue where modality lives, so it's in reach. |
| **Profile facets** (culture/lang/country) | **NO — not in state and not from dialogue.** | §7b: pipeline ingests only `user_id`/`user_split`; culture comes from `user_profile`, not the conversation. | **NEW plumbing** (pass `user_profile` into compiler), not extraction. Low priority (confounded, English-only on Blind-A). |

**Headline answer to "does our state have the info?":**
- For the **two biggest recoverable pools** (named-artist resolve + exact-tag, plus the fusion-loss pool), **the information is ALREADY in our current extracted state** (or needs no state). These are **retrieval/compiler fixes, not extraction or schema work.** Only **392 of 2872 misses (13.6%)** are "barren" — no usable artist AND no GT-matching tag in our state.
- The **one place we need new extraction** is a **per-turn modality/routing tag** (lever 3) — this is exactly the ideal-schema `routing_tags` field, and it's worth adding because session `category` proves the signal is real but its granularity is wrong (§7b).
- So: **for the immediate recall levers, the ideal schema is needed mainly for routing_tags; the rest is downstream.** We should not over-invest in extractor richness *first* — the named-artist and tag signals we already extract are not being *used*, which is higher-ROI than extracting more.
- **But "only one lever needs ideal state" is too narrow as a general claim (per reviewer).** Beyond `routing_tags`, the ideal/v3 state would also help with: **target-vs-history entity separation** (which named entity is the *current* ask vs. carried-over context), **`target_entities.exactness`** (exact title vs. fuzzy recall vs. "something like"), **`history_policy`/carryover** (when to keep vs. drop anchors — directly relevant to the pivot/diversify turns that fail most), **aspect-level feedback**, and the **hidden-target vs. open-set** distinction. Those don't show up as top *recall* levers in this devset analysis, but they are the right structure for the ranking/precision and carryover problems. Net: don't reduce the ideal schema to `routing_tags` — it's the lowest-priority-for-recall but not the only useful field.

(All figures recomputed from `gap_table_v3.jsonl`; `n_pos_artists`/`tag_overlap` are direct state fields, so "in our state" here means literally present in the v3-extracted `ConversationState`.)

---

## 7b. Untapped organizer & profile fields — what's available, used, and exploitable

This section answers three reviewer questions: (1) what other fields exist in the data, (2) are they available in the **blindset** (i.e. exploitable at submission time, not just diagnostic), and (3) does the pipeline currently use them.

### ⚠ Blind-A turn distribution (verified) — cold-start is a large slice, not all of it

Correcting an earlier overstatement of mine: Blind-A (80 sessions) is **NOT** all turn-1. **20/80 (25%) are turn-1-only; 60/80 (75%) are multi-turn (2–8 user turns)**, and `conversations[].thought` IS populated on the later turns (213/290 user turns carry non-empty thought) — so the `thought`-leakage concern is **live**, not moot. But the cold-start regime still matters a lot: every session's earliest prediction is a turn-1, and on the devset turn-1 cohort (n=1000, the analog) Hit@1000 = **0.549**, union = **0.598**, never-reach = **0.402**, with the **3 centroid branches at 0.000 recall** (no anchors) — cold-start runs on BM25 + metadata-dense only. So the anchor-free query-text branch (Lever 3) is especially valuable for turn-1, while history/centroid/carryover levers pay off on the multi-turn majority.

### What the dataset actually exposes (verified on both splits)

Devset (`...-Challenge-Dataset` test) and **Blind-A** (`...-Challenge-Blind-A` test, n=80) have the **identical 7-column schema**:
`session_id, user_id, session_date, user_profile, conversation_goal, conversations, goal_progress_assessments`.

- `conversation_goal` = `{category (A–K), specificity (HH/HL/LH/LL), listener_goal (free text)}` — present in Blind-A ✓
- `user_profile` = `{age, age_group, country_code, country_name, gender, preferred_language, preferred_musical_culture, user_split}` — present in Blind-A ✓
- `goal_progress_assessments` = per-turn MOVES_TOWARD_GOAL / DOES_NOT — present, but only meaningful for *prior* turns (the current turn's GT is what we predict), so limited retrieval value.
- `conversations[].thought` — each user/assistant turn carries a `thought` field; **Blind-A populates the user `thought`** (the simulator's internal reasoning) and prior assistant `thought`s. The current runner ignores them.

**⚠ LEAKAGE TIERS (do NOT lump these together — per reviewer):**
| field | leakage risk | stance |
|---|---|---|
| `conversation_goal` (category/specificity/**listener_goal**) | **HIGH** — it is the per-session objective; `listener_goal` is essentially a paraphrase of the hidden target intent | **analyzer/teacher-only** unless challenge rules explicitly permit it as model input; confirm Blind-B parity first |
| `conversations[].thought` | **HIGHEST** — the simulator's private reasoning about what it wants | **analyzer/teacher-only**, never a production input |
| `goal_progress_assessments` | **HIGH** — encodes whether prior recs approached the hidden target | analyzer/teacher-only |
| `user_profile` (age/country/language/culture) | **LOW** — ordinary personalization metadata, not target-revealing | likely a legitimate production input; still confirm rules, but do NOT treat like `conversation_goal` |

Net: the *only* organizer field I'd consider for production retrieval is `user_profile`. `category`/`specificity`/`listener_goal`/`thought`/`goal_progress` should be used **only for offline analysis or as a teacher signal to train/distill**, not as live model inputs — pending an explicit rules check.

**Blind-A (n=80) field distribution (verified):** category B 14 / C 11 / G 9 / D 9 / F 8 / H 7 / J 6 / E 6 / K 4 / A 4 / I 2; specificity LL 27 / HL 23 / LH 21 / HH 9; language **English on all 80** (so language is NOT a usable axis on Blind-A). `preferred_musical_culture` is a free-text, **unnormalized** field — Blind-A values are fine-grained strings like "American Hip-Hop Culture", "Japanese", "Brazilian", "Video Game Music Culture", "Korean Pop Culture", "Metal Culture" (mostly n=1–3 each). So culture is high-cardinality and inconsistent, not a clean enum.

### Does the pipeline use any of these today? NO.

Verified by code grep: `user_profile` is parsed but **"only user_id/user_split surface in the v0+ state; the rest is dropped."** `conversation_goal` (category/specificity/listener_goal), `preferred_musical_culture`, `preferred_language`, `country` are **not read anywhere** in `mcrs/`. The extractor sees only the conversation text. **This is free, blindset-available signal currently thrown away.**

### Gap by these fields (devset table joined to user_profile)

**`preferred_musical_culture` — REAL devset values (field is unnormalized/high-cardinality; ~80+ distinct strings, showing the largest n≥40 buckets, Hit@1000 / union). These are the actual strings, NOT grouped:**
| culture string | n | Hit@1000 | union |
|---|---:|---:|---:|
| Gaming Culture | 120 | **0.917** | 0.950 |
| Western Classical | 48 | 0.833 | 0.958 |
| American Hip Hop Culture | 48 | 0.792 | 0.917 |
| Synthwave Culture | 40 | 0.775 | 0.825 |
| Brazilian Music | 48 | 0.771 | 0.833 |
| African-American music culture | 48 | 0.771 | 0.812 |
| American Hip Hop | 64 | 0.750 | 0.906 |
| Christian Music | 48 | 0.750 | 0.938 |
| African American Music Culture | 80 | 0.713 | 0.887 |
| North American | 184 | 0.668 | 0.755 |
| Hip-Hop Culture | 120 | 0.658 | 0.800 |
| Metal Culture | 152 | 0.658 | 0.763 |
| Latin American | 96 | 0.646 | 0.802 |
| Electronic Music Culture | 112 | 0.607 | 0.741 |
| American Hip-Hop | 200 | 0.585 | 0.760 |
| Western Pop Culture | 104 | 0.577 | 0.673 |
| Western | 448 | 0.556 | 0.676 |
| Anglo-American | 104 | 0.529 | 0.683 |
| American | 264 | 0.523 | 0.674 |
| North American Hip-Hop | 48 | 0.500 | 0.771 |
| Alternative Music Culture | 56 | 0.482 | 0.661 |
| Western Alternative | 40 | 0.450 | 0.650 |
| Anglo-American Rock | 32 | 0.406 | 0.562 |
| Latin | 40 | 0.400 | 0.750 |

**Two honest reads.** (1) There IS a large spread (0.40 → 0.92), but it is **confounded with goal/genre**, not a clean "Anglo vs non-Anglo" story — e.g. "Gaming Culture" and "Western Classical" are the *best*, while "Western"/"American"/"Anglo-American Rock" are among the *worst*. So the earlier framing (non-Anglo under-served) is **NOT supported by the raw data** and I retract it. (2) The field is **unnormalized free text** ("American Hip Hop" / "American Hip-Hop" / "American Hip Hop Culture" are 3 separate buckets), so it is a weak, messy axis to exploit directly. The notable low-recall + low-union cells (Anglo-American Rock 0.41/0.56, Western Alternative 0.45/0.65, Latin 0.40/union 0.75 — the last is fusion-loss-heavy) are real but small-n.

**Conclusion on culture:** interesting but lower-priority and confounded; do not build a "non-Anglo boost." Worth at most feeding the raw culture/genre string as an extra soft query term. The clean, high-confidence axis remains **named-artist** (§5), not culture.

**`expertise` — not analyzable in our table:** the `expertise` column is `None` for all 8000 rows in `gap_table_v3.jsonl` (it was not populated when the table was built), so we have **no evidence either way** on it. Any earlier "expertise is flat/useless" wording was unsupported and is retracted. If we want to test it, rebuild the table pulling `conversation_goal.listener_expertise` (the raw dataset does carry it).

**`category` / `specificity`** — already in §4 (category is a real axis: C/I/B never-reach, K/J fusion; specificity weak except LL). Both blindset-available.

### Exploitability & the ideal-state-schema question

- **Granularity caveat on `conversation_goal` (important):** the goal/`category` is **per-session, not per-turn**, and the data shows this matters — **100% of sessions (1000/1000) have the per-turn intent change** across turns (647 sessions span 3 distinct intent-modes, 178 span all 4, 174 span 2). Meanwhile our **per-turn extracted `intent_mode` has a 0.349 recall spread vs only 0.142 for the session `category`** — i.e. the per-turn signal we already produce is ~2.5× more predictive of recall than the static session label. So routing should be driven by **per-turn extraction**, not the per-session field.
- **But category is complementary, not redundant:** within a fixed `intent_mode`, the session `category` still splits recall by 0.16–0.27. It carries orthogonal *modality* info (visual / audio / era / lyric) that `intent_mode` (refine/pivot/explore) does not. So the right design is to **extract a per-turn modality/routing tag** (the north-star schema's `routing_tags`: image/audio/era/lyric/popularity) and route branches on it (visual→image, audio→clap, era→date filter, popularity→prior); keep the session `category` only as a cheap **weak prior/fallback** (it's free in the blindset).
- **`preferred_musical_culture`** could be appended as a soft query term, but it's unnormalized and confounded (see above), so low priority. **`preferred_language` is English-only on Blind-A → not usable.** All of the above are config/query-construction changes, not training.
- **Confounding caveat:** these are recall *correlations*, not proof that conditioning improves retrieval (e.g. `pivot` is hard partly because it drops anchors, zeroing the centroid branches — a structural cause, not a routing error). Confirm any routing lever with an A/B, not the spread alone.
- **Would the ideal v3 state schema fix this?** The north-star schema (`experiments/analysis/conversation_state_design_v2`) has the right slots: `process_constraints`, facet-typed `constraints` (incl. `language`, `geography`), and `routing_tags`. Two distinct cases:
  - **Goal/modality (category):** the right fix is to **extract a per-turn `routing_tags`** (image/audio/era/lyric/popularity) — NOT to read the static per-session `category`, because the goal granularity is wrong (100% per-turn intent drift, above). This is genuinely "extract it per-turn if useful," and the data says it IS useful (complementary to intent_mode). The extractor already reads the dialogue, which is where per-turn modality lives, so this is squarely in scope for the extractor.
  - **Profile facets (culture/language/country):** these come from `user_profile`, **not the dialogue**, so adding schema fields doesn't help unless the pipeline also **passes user_profile into the compiler/query-builder**. Today it ingests only `user_id`/`user_split`. (And per above, culture is messy/confounded and language is constant on Blind-A, so this is lower priority anyway.)
  - **Net:** the ideal schema is necessary plumbing; the binding constraints are (a) extract a per-turn routing tag and route branches on it, and (b) for profile signals, actually feed `user_profile` into retrieval. The goal-routing half is fully in the extractor's reach; the profile half needs new plumbing.

**Caveat:** the culture cut is single-pass computed from the devset table joined to `user_profile`; directionally strong (large n, large spread) but exact per-bucket values worth a spot re-check. The blindset-schema facts are byte-verified.

---

## 8. Suggested validation sequence

1. **Rank 1 (fusion quota)** on a 50-session slice → measure Hit@1000 lift in isolation; confirm it approaches the union ceiling. Cheapest, highest-confidence first.
2. **Rank 2 (named-artist resolver)** — implement + the 102-turn leak audit; measure on the same slice.
3. Re-run the branch-trace + this table after 1–2 land, to confirm the fusion pool actually shrinks and to re-measure the new union ceiling.
4. **Ranks 3–4 (anchor-free + tag-match branches)** attack never-reach; each needs its own branch + index, validate on cold-start / LL / open_explore slices specifically.

Each lever is independently measurable. Ranks 1–2 are config/deterministic (no training); Ranks 3–4 add branches but reuse existing infra.

---

## 9. Open questions for the reviewer

- Is the per-branch **quota** the right mechanism, or would a learned fusion (e.g. weighted RRF with per-branch reliability priors) recover the lone-branch finds better without hurting the agreement cases? (Data says lone-branch dominates, which argues for quota.)
- The 102 "named-but-never-reached" turns imply the extracted artist token sometimes doesn't reach the BM25 query / dense intent string. Is that a query-builder bug worth fixing before adding the resolver branch?
- Lyrics (B, 1136 turns, Hit@1000 0.638) and visual (C, 0.554, never-reach 0.31): **correction (per code-grounded deep-dive)** — the catalog DOES ship a `lyrics_qwen3_embedding_0_6b` vector column (and `attributes_qwen3`), so a lyrics/theme-embedding branch IS possible; only *raw lyric-string* matching is unavailable. Lyrics/attributes branches were tried and *dropped globally for macro regressions*, so the open question is whether a **routed** lyrics branch (fired only on category-B/lyric-theme turns) helps without the global cost.
- Does the ~14-pt fusion ceiling assume the GT, once protected, also *ranks* well enough to matter for NDCG@20 — or is this purely a recall (Hit@1000) play that still needs the reranker downstream for top-K?

---

## 10. Cross-analysis additions (from an independent reviewer / Codex)

An independent pass agreed with the core decomposition (Hit@1000 0.641, union ~0.780, large fusion-loss, exact-artist/state/history strongest) and added points worth folding in. **A third, multimodal-focused Codex pass (`/private/tmp/mm_deep_dive_summary.md`) independently re-confirmed the whole decomposition** — fused ~0.64, union ~0.78, fusion-loss ~0.14, per-branch bm25 ~0.61 / audio ~0.36 / metadata ~0.35 / image ~0.35 / cf ~0.30 — and **surfaced real corrections** to this report (the bm25 unique-contribution error above; the lyrics-scope error below) — see §11 for the full reconciliation. Its one extra prescription: **audio is the non-lexical branch to keep; cf + image are the redundant centroid pair and could be dropped to save compute.** My unique-contribution data supports this (audio 4.32% vs image 1.59% / cf 2.19%) **with one caveat: keep `metadata_qwen3` despite its low unique-contribution (2.21%), because it is the *only* non-lexical branch that fires at cold-start (turn 1, no anchors) — dropping it would worsen the turn-1 regime.** Numbers in items 1 & 3 are the **reviewer's** independent slices — NOT recomputed from this report's table (my table stores top-1000 branch booleans only, so I cannot reproduce union@100 or the prior-history cut); flagged accordingly.

1. **History-specific slicing (complements §5's "named-in-conversation").** Reviewer: GT artist in *prior history* → Hit@1000 **0.871**; extracted state has GT artist → **0.969**; both → **0.965**; neither → **0.447**; "different/new artist" + novel artist → **0.262**. Reading: history helps *only when it becomes a correct state-artist bridge*, and many turns deliberately ask to diversify/pivot (history *shouldn't* be reused there). This is a **carryover-policy** problem distinct from my `gt_artist_named_in_conv` axis — central for the multi-turn majority, moot for the turn-1 cold-start portion.

2. **Fusion-quota precision.** A *small* per-branch quota will NOT recover deep branch hits — some lost GTs sit at branch-rank 600–1000. The 0.780 union is not an automatic ceiling unless the survivor/top-1000 set actually carries those deep candidates. Better framing: **quota/survivor-set sizing + reranker, measured by Hit@1000 AND Hit@100/NDCG@20**. (My report already flags we lack per-branch rank/depth instrumentation — needed to size the quota.)

3. **Top-K conversion is a separate problem.** Reviewer: fused Hit@100 ≈ **0.406** vs branch-union@100 ≈ **0.526** — a real top-100/top-20 conversion loss on top of the Hit@1000 loss (I cannot recompute @100 union from my table). Implication: after recall-preserving fusion, a **cross-encoder / learned reranker** is a concrete, separately-measured follow-up (the offline Qwen3-Reranker-0.6B run on the v3 pool is the starting point).

4. **Leakage tiering & `thought`** — folded into §7b (leakage-tiers table; Blind-A `thought` IS populated on its multi-turn sessions — 213/290 user turns — so it's a live concern, not moot).
5. **Popularity stays routed, not dropped** — folded into Rank 5.
6. **Exact-tag is gold-conditioned** — folded into Rank 4 (1183/0.799 is an upper bound; needs rarity-weighting + flood test).


---

## 11. Code-grounded deep-dive reconciliation (Codex MM pass, `/private/tmp/mm_deep_dive_summary.md`)

A third Codex pass joined the trace to the **actual compiler + catalog code**. It confirmed the corrected category table (B=0.638, D=0.645, HH=0.721), turn-depth table, fusion-loss lone-branch finding, leakage tiers, and the absent `expertise` field. Beyond confirmation it **corrects and reframes** several things — folded in here:

**A. Corrections to THIS report (verified):**
- **bm25 unique-contribution was wrong:** I had 2169 (27.1%); the correct value is **1015 (12.7%)**, matching Codex's independent `bm25_only=1015`. My number was inflated by the centroid-key trap. (metadata unique likewise 121→**177**.) Fixed in §3.
- **Lyrics is NOT out of scope:** the catalog ships a `lyrics_qwen3_embedding_0_6b` column; only raw lyric text is missing. Fixed in §4/§9.

**B. The bigger reframe — optimize top-100 branch COVERAGE, not the 0.78 ceiling:**
- Final **Hit@100 = 0.406**, branch **union@100 = 0.526**, but union@1000 = 0.780. VRank can take only ~1000 candidates, so **union@1000 is a *diagnostic* ceiling, not the operating target.** The near-term target is **raising branch/any-action Hit@100 with a ≤1000 selected pool.** This refines Lever 1: a fusion quota helps, but the real scorecard must be Hit@20/100 per branch, not just Hit@1000.

**C. Sharper named-artist decomposition (3-way, prefix-safe) + root cause:**
- `state_artist_match` (n=2346): Hit@1000 **0.968**, union@100 0.969 — effectively solved.
- `no_state+visible` (n=1335): artist IS in the visible prefix but state missed it → Hit@100 0.395, union@100 0.662. **Actionable extractor/resolver miss** (the carryover bucket; 92% have the artist in a prior played track).
- `no_state+not_visible` (n=4319): truly novel → Hit@100 0.174, union@100 0.243. Needs new non-artist retrieval.
- **Concrete root cause:** the resolver **does not ground positive `mentioned_entities`** (it only resolves rejections + feedback artist IDs). So even a correctly-extracted artist isn't turned into an artist-discography fetch. This is *the* mechanism behind my "named-but-missed" finding — fix the resolver before adding branches.

**D. Tag branch demoted (my Rank 4):**
- The compiler ALREADY uses positive tags in 4 places (BM25 `tag_list`, anchor-tag expansion, dense query text, post-fusion boost). So a separate exact-tag branch is **an audit/ablation, not a first move** — first check whether existing tag paths miss the GT or just under-rank it. (`tag_list` is noisy: mean 33.5 tags/track, 164k unique tags — broad-tag flooding is the risk.)

**E. Revised priority order (code-grounded, coverage-first):**
1. Branch-action Hit@100 diagnostics as the standing scorecard.
2. Promote only the v3 state fields that drive a retriever (`target_entities`+`exactness`, `routing_tags`, `history_policy`).
3. **Fix the resolver** to ground positive artist/track mentions → discography/exact branches (highest-confidence concrete fix).
4. Add cheap action retrievers (exact-title, resolved-artist discography, current-turn/recency BM25, anchor-free dense, routed lyrics/popularity) and gate each on its own Hit@100.
5. History/carryover policy where coverage already exists (`no_state+visible`, `prev_artist_match` union 0.86 vs final 0.67).
6. Tag-IDF as audit/ablation only.

This supersedes the §7/§8 ordering for *implementation* purposes (those remain valid for the recall-only view); the deep-dive's coverage-first, code-grounded plan is the one to execute.

## Appendix: reproduction

- Table builder: `experiments/analysis/extractor_prompt_v2/scripts/build_gap_table_on_modal.py` (run on Modal; writes `analysis/gap_table_v3.jsonl` to the results volume).
- Per-turn table (8000 rows): `experiments/analysis/extractor_prompt_v2/artifacts/gap/gap_table_v3.jsonl`.
- Branch-traced run config: `configs/v0plus_compiler_mm_extractor_v3_devset.yaml` (`branch_trace_topk: 1000`).
- Scoring helper: `experiments/analysis/extractor_prompt_v2/scripts/score_on_modal.py`.
- All §3 numbers recomputable from the table with: hit = GT in fused top-1000; per-branch = `row.get("in_<branch>", False)`; union = any branch; fusion_loss = union AND NOT hit; never-reach = NOT union.
