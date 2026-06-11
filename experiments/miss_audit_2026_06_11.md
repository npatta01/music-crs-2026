# Miss Audit — Reranker Feature Validation (2026-06-11)

Population analysis over **all** in-pool misses of the new baseline
(`pruned_resolved_tags`, full 8000-turn devset): turns where the GT is inside
union@200 of the branch pools but not in the final top-20. Script:
`scripts/miss_audit.py`; artifacts under `exp/analysis/miss_audit/`.

## Population

| bucket | n | % |
|---|---:|---:|
| hit@20 | 2,345 | 29.3% |
| **in-pool miss (addressable by reranker)** | **3,429** | **42.9%** |
| unreachable @200 | 2,225 | 27.8% |

## Feature rescue rates (n=3,429 misses)

"Beats median" = GT's feature value exceeds the median of the 20 tracks
currently occupying the final list — positive discrimination in combination.
"Beats max" = single-feature silver bullet.

| feature | beats median | beats max |
|---|---:|---:|
| **era_pop_pct** (popularity percentile within release-year cohort) | **45.7%** | 5.8% |
| **pop_pct** (global popularity percentile) | **43.8%** | 5.3% |
| **cf_last** (cf_bpr cosine to last played track) | **38.4%** | 7.2% |
| cf_centroid (cosine to session centroid) | 36.3% | 6.9% |
| **user_cf** (cosine to user embedding) | **34.9%** | 2.9% |
| same_artist_session | 23.4% | 9.9% |
| same_album_any | 20.1% | 9.1% |
| tag_overlap_idf | 18.2% | 1.1% |
| age_era_affinity | 16.4% | 2.4% |
| tag_overlap | 15.2% | 0.5% |
| same_album_last | 11.4% | 6.5% |
| culture_match | 10.1% | 0.6% |
| year_in_constraint | 1.1% | 0.0% |
| recent_at_session | 0.0% | 0.0% |

Strata highlights (full table in `exp/analysis/miss_audit/aggregates.json`):

- Shallow misses (rank 21–50, 58% of population): momentum/centroid CF
  strongest (42–43%).
- Deep misses (51–200): **user_cf rises to 33–37%** — the user prior takes
  over where session evidence is thin.
- Goal-category shifts the mix: cat_C is user_cf-led (49%), cat_B
  momentum-led, cat_H/J popularity-led (51%) → `conversation_goal.category`
  earns its place as a conditioning feature.
- No feature beats the entire top-20 more than 10% of the time → combination
  problem, i.e., a trained ranker, not another hand boost.

## LLM judgment pass (132-row stratified sample)

- **GT plausibility: 84% plausible / 10% contradictory / 6% taste.** The
  addressable set is real ranking loss, not label noise.
- Request kinds: 68% continuation, 18% new-artist, 8% specific, 6% vague.
- 7 of 13 contradictory GTs are one pattern: user explicitly asks for a
  *different* artist, GT is the same artist again (matches the state-audit
  finding; argues for a `same_artist × wants_new_artist` interaction feature
  rather than excluding these turns).

## Decision: training data needs NO state extraction and NO retrieval

Every top-tier feature is computable from **raw data only**: catalog
(popularity, year, artist/album ids, cf_bpr), the session's played-track
sequence (raw dataset rows), user embeddings, and organizer fields
(goal category/specificity, user profile). The state-derived features
(tag_overlap, year_in_constraint) are the weakest tier.

Consequences for the trained ranker:

1. **Train-set feature extraction is free** — no LLM extraction
   (~$50–300 saved on 121,592 turns at deepseek-v4-flash live pricing,
   depending on prompt-cache hit rate), no retrieval runs.
2. **Negatives** are sampled synthetically per turn to mimic branch pools:
   cf-neighbors of the last played track, popularity/era-matched tracks,
   same-artist tracks, random — no retrieval needed.
3. State/tag features can join later as a v2 ablation using the **devset
   pools already on disk** (8000 turns with full state + pools + GT), which
   cost nothing more.
4. At inference the production pipeline extracts state anyway, so any v2
   state features are free at serving time.
