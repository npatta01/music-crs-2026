# Music CRS Recall Gap Decision Report

Generated: 2026-06-06 16:33:52 UTC
TID: `v0plus_compiler_all_retrievers_devset`

## Technical Summary

- Official-score context: NDCG@10 is 10.5%; NDCG@20 is 12.5%.
- Final Hit@20 is 27.4%; union@20 is 47.7%.
- 52.3% of turns are not in union@20, so candidate generation/state/retrieval is a real gap.
- The union@20 to final@20 opportunity is 20.3 pp, so current fusion/post-fusion/ranking is also a real gap.
- Union@100 is 66.2%; a trained ranker over union@100/200 is justified, but cannot fix not-in-union cases.
- Organizer metadata sharpens the diagnosis: LL final@20 is 20.2% vs HH final@20 41.9%; turn 8 final@20 is 17.0% while union@20 is 43.9%.
- Public challenge scoring dimensions include nDCG@20, catalog diversity, Distinct-2 lexical diversity, and Gemini LLM-as-a-judge response quality. Codabench publishes the composite formula: 0.50*nDCG@20 + 0.10*CatalogDiversity + 0.10*LexicalDiversity + 0.30*LLM-Judge. The challenge website lists the same dimensions but says the exact formula is not published there, so use Codabench as the formula source.
- Response-generation gap: This run is retrieval-only (`lm_type=dummy`), so generated responses are empty/unanalyzed. That leaves the 0.30 LLM-Judge and 0.10 LexicalDiversity lanes unoptimized, plus CatalogDiversity as a track-list diversity lane.

## Response Generation And Scoring Context

- Public dimensions: nDCG@20, catalog diversity, Distinct-2 lexical diversity, and Gemini LLM-as-a-judge response quality.
- Formula caveat: Codabench publishes the composite formula: 0.50*nDCG@20 + 0.10*CatalogDiversity + 0.10*LexicalDiversity + 0.30*LLM-Judge. The challenge website lists the same dimensions but says the exact formula is not published there, so use Codabench as the formula source.
- Current gap: This run is retrieval-only (`lm_type=dummy`), so generated responses are empty/unanalyzed. That leaves the 0.30 LLM-Judge and 0.10 LexicalDiversity lanes unoptimized, plus CatalogDiversity as a track-list diversity lane.
- Next test: Run a real response generator on dev predictions, then measure Distinct-2 and inspect Gemini-judge style/explanation quality before optimizing prose prompts.

## Task-Mode And State Audit Addendum

- Honest first-stage ranker ceiling: union@100 = 66.2%; gap@100 = 33.8% (2,701 turns).
- This preserves the user's union@20 concern, but makes union@100 the practical shallow-pool ceiling for first-stage ranker design.

### What This Adds To The Plan

- Use union@100 as the honest first-stage ranker ceiling while keeping union@20 as the primary gap boundary.
- Split the work by turn-level mode: continuation is mostly ranking/within-artist selection; new-artist is the largest candidate-generation gap.
- Add relation-typed state for named artists: seed, satisfied, contrast, history, rejected. Binary positive/negative anchoring is too blunt.
- Treat category/specificity and raw demographics as session-level context, not as candidate-varying ranker features.
- Promote album-affinity, artist-recency, is_new_artist, user-CF, and genre/popularity priors into the first ranker feature set.

### Caveats before acting

- Do not use union@1000 as the headline ranker target; it is an oracle over thousands of candidates.
- The continuation/new-artist taxonomy is partly GT-defined, so validate it with current-turn intent labels before training against it.
- New-artist popularity/CF fixes are plausible but not counterfactually verified yet.
- Album-affinity has a measured rescue pool, but the report itself corrects the upside to a prototype-before-commit estimate.
- Response text quality is a separate scored gap: Codabench weights LLM-Judge at 0.30 and LexicalDiversity at 0.10, while current lm_type=dummy produces empty responses.

### Task Mode Split

| Mode | Meaning | Turns | Share | Hit@20 | NDCG@20 | Gap@50 | Miss share | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| EXACT-named | GT = the song they named | 113 | 1.4% | 94.7% | 70.9% | 3.5% | 0.1% | solved |
| CONTINUATION | GT = deeper cut by an already-heard artist | 3,176 | 39.7% | 45.6% | 20.5% | 9.2% | 29.8% | reranker — GT in pool, ranking problem |
| NEW-ARTIST | GT = a brand-new artist | 3,765 | 47.1% | 9.8% | 3.9% | 67.1% | 58.4% | biggest+hardest — retrieval gap, intent-conditioned candidate generation |
| COLD-OPEN | turn 1, no history | 946 | 11.8% | 28.1% | 12.9% | 53.0% | 11.7% | cold start — popularity + cross-session CF |

Task-mode note: Mode mix is ~identical across all 11 categories (~46-50% NEW-ARTIST each). Category/specificity does NOT predict mode -> cannot route by category; routing must be turn-level (continuation vs novelty).

### Relation-Aware State Taxonomy

| Cue | Role | Current state | Ideal state |
| --- | --- | --- | --- |
| "similar to / like / in the vein of X" | `SEED` | +1 → anchored | anchor ON (this is the one case binary gets right) |
| "X was great, now more / other / else" | `SATISFIED` | +1 → anchored | anchor OFF, decay — user got X, wants beyond it |
| "different from / not like / besides / instead of X" | `CONTRAST` | +1 → anchored | anchor OFF, optionally repel |
| X named in an earlier turn, NOT this one | `HISTORY` | +1 → anchored | DROP entirely from current targets |
| "not X / no more X / stop X" | `REJECTED` | -1 → hard drop | hard drop (already correct) |

### State Bugs And Checks To Add

| Item | Verdict | Stat | Detail |
| --- | --- | --- | --- |
| Genre/mood tags | `good` | 78% match | positive_tags overlap a GT tag on 78% of valid turns. Extraction vocab is fine. |
| Negative refs excluded | `good` | code-verified | resolver drops sentiment<0 from anchors; negatives only feed hard-drops. |
| Entity over-extraction | `bad` | 0.5 → 2.3 / turn | positive artist targets climb to ~2.3 by turn 3+ vs ~1 actually referenced forward. Carries old artists forward. |
| Contrast as positive | `bad` | qualitative | "not as intense as Pink Floyd" → Pink Floyd tagged +1 → became an anchor. Extractor sentiment/role error. |
| Year filter over-fires | `bad` | 29% drop GT | of turns with a year_range set, GT falls OUTSIDE it 29% of the time (580 miss@20). Soft-penalizes valid answers. |
| hidden_target_search | `inert` | 391 fires; 0 weighted-routing consumption | The routing tag fires in the trace, but routing_boost is empty, so the bug is non-consumption rather than non-extraction. |
| Rejection enforcement | `dead` | ~5% leak | 769 of 14,780 returned slots were a rejected artist/track despite "hard drop". Needs verification (multi-artist) but "no Bon Jovi → Bon Jovi" happens. |

### Feature Catalog From This Audit

| Feature | Evidence | Target slice |
| --- | --- | --- |
| album-affinity | measured about +6pp Hit@20 ceiling; prototype before commit | continuation 62% |
| artist-recency (most-recent, weighted) | — | continuation diff-album |
| user-CF / demographic-popularity | — | new-artist popular ~23% of misses |
| genre/era-conditioned popularity | — | new-artist popular |
| is_new_artist | +1% reranker | novelty |
| constraint-satisfaction (year/reject/rarity-tag) | year drops GT 29% | discovery |

Do not over-invest in:
- category
- specificity
- musical_culture
- raw demographics
- intent_mode — all candidate-constant → 0 ranking lift; only condition retrieval

## What To Work On First

### P0: Train the ranker on true branch union@200, with candidate-varying state features

Why: Union@20 is 47.7% while final@20 is 27.4%; turn 8 has final@20 17.0% but union@20 43.9%.

Do: Build candidates from raw branch union@200, not branches.final. Add branch ranks, branch-count features, popularity, tag overlap, release distance, album/artist recency, candidate artist role, and candidate-varying goal/culture affinity. Keep raw category/specificity/demographics as slices or routing conditioners, not direct within-turn ranking features.

Proof: Session-grouped CV must beat the current fusion baseline on NDCG@20/Hit@20 and on LL + turn 5-8 slices; also report whether raw session constants add any lift.

### P0: Pass organizer goal/profile metadata into routing and candidate features

Why: LL goals have final@20 20.2%; HH goals have 41.9%. The field is available in dev/test and Blind-A, but current inference only passes user_query, user_id, and session_memory.

Do: Extend the batch item and compiler input with conversation_goal.category/specificity/listener_goal plus preferred_musical_culture. Use listener_goal as retrieval/routing text and transform profile/category signals into candidate-varying affinity or popularity features.

Proof: Metadata-aware routing/candidate features should improve LL/category C/K/J slices without regressing HH exact-title slices; raw constants alone are expected to be a no-lift baseline.

### P1: Build goal-family retrievers for the low-union slices

Why: LL/category C/K/I/J have low union@20 or union@100, so a ranker cannot recover enough by itself.

Do: For cover-art goals, add image/album-cover text routing; for broad instrumental/film-score goals, add mood+instrumental+OST tag-popularity retrieval; for popular/exact goals, add canonical popularity and exact-entity probes.

Proof: Raise union@20/100 for LL and categories C/K/J before evaluating final ranking.

### P1: Fix late-turn state carryover and post-fusion suppression

Why: Turns 5-8 keep decent union@20 but lose final@20, so final policy is over-demoting or over-trusting stale context.

Do: Add trusted survivor slots and learn same-artist/album diversity instead of fixed demotions. Add state QA for stale tags and release-year carryover.

Proof: Turn 5-8 final@20 and fusion_efficiency@20 should rise while turn 1-3 does not regress.

## Measured Ranker And Feature Evidence

- Adjacent reranker bakeoff: NDCG@20 0.1415 -> 0.1594 (12.7% relative); Hit@20 0.3098 -> 0.3325.
- Scope caveat: Adjacent full-devset reranker bakeoff on v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset, not the all-retrievers trace in this report.
- Decision: rank fusion helps; pure score replacement was reported as structurally harmful. Revalidate on this report's all-retrievers union pool before shipping.

- Album-affinity / album completion: measured counterfactual; 479 of 964 same-album misses are rescuable from fused rank 21-100; 326 sit at 101-1000 and 159 are absent. Reported ceiling: about +6pp Hit@20. Decision: Keep as a P0 ranker feature: same_album_recent plus artist_recency, with continuation and new-artist guardrails.
- Current trace album fused-rank anatomy: trace recount; Primary-album misses=978; fused<=20/final-missed=454, fused 21-100=301, fused 101-1000=90, absent=133; bucket sum=978. Decision: Read fused<=20 as post-fusion/finalization loss, not album-retrieval absence.
- Baseline-fused cross-encoder reranker: measured adjacent-pool bakeoff; NDCG@20 0.1415 -> 0.1594 (12.7% relative); Hit@20 0.3098 -> 0.3325. Scope: Adjacent full-devset reranker bakeoff on v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset, not the all-retrievers trace in this report. Decision: Use rank fusion or a trained scorer over current-fusion/branch features; do not replace current fusion with raw cross-encoder score.
- Candidate-level is_new_artist feature: measured small positive; +1% reranker on novelty Decision: Use as a ranker feature, but still fix candidate generation because new-artist GTs are often outside union@20.
- Raw session/category/demographic features in a within-turn ranker: measured no lift; 0 lift — candidate-constant within a turn. Decision: Do not feed raw constants directly; derive candidate-varying culture/user-CF/popularity affinity or use them for routing/slicing.
- Rarity-weighted / IDF tags: measured negative; WORSE than raw; tags cap ~0.19 hit@50. Decision: Do not prioritize IDF-tag weighting; tags are useful, but role/routing and candidate-varying behavioral features are stronger.

## Organizer Metadata Slices

| Slice | n | Final@20 | Union@20 | Union@100 | Rank gap | Not union@20 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| specificity=LL | 2,224 | 20.2% | 40.5% | 60.5% | 20.3 pp | 59.5% |
| specificity=LH | 2,504 | 29.9% | 47.8% | 65.6% | 17.9 pp | 52.2% |
| specificity=HL | 2,456 | 26.4% | 50.0% | 68.8% | 23.6 pp | 50.0% |
| specificity=HH | 816 | 41.9% | 59.7% | 76.1% | 17.8 pp | 40.3% |
| assessment=DOES_NOT_MOVE_TOWARD_GOAL | 816 | 16.1% | 38.4% | 54.7% | 22.3 pp | 61.6% |
| assessment=MOVES_TOWARD_GOAL | 6,184 | 28.1% | 50.2% | 69.0% | 22.1 pp | 49.8% |
| assessment=TURN1_OR_NONE | 1,000 | 32.0% | 39.6% | 58.6% | 7.6 pp | 60.4% |

### Goal Categories

| Category | n | Example organizer goals | Final@20 | Union@20 | Union@100 |
| --- | ---: | --- | ---: | ---: | ---: |
| I | 144 | play a specific globally popular song by exact title and artist | find modern electronic dance music that blends deep house grooves with soulful vocal elements or jazz influences. | 22.2% | 43.1% | 60.4% |
| K | 1,248 | discover multiple instrumental pieces from a broad era, particularly film scores or contemporary classical works, that evoke a timeless or classic feel. | discover multiple chill, instrumental lo-fi hip-hop tracks fro... | 24.0% | 42.6% | 62.8% |
| C | 464 | find one specific album remembered by its distinctive, dark, and abstract or unsettling cover art. | find one specific heavy metal album remembered by its distinctive, often dark or fantastical, cover art | 24.3% | 42.2% | 57.5% |
| G | 616 | find some positive and uplifting hip-hop tracks to boost my energy and put me in a good mood. | find multiple songs that convey intense emotional drama, particularly those expressing feelings of profound sadness, grie... | 25.0% | 45.5% | 66.2% |
| J | 616 | play one specific song that is known for its high popularity within its genre or era. | find a specific song from the early 90s that was a massive hit and widely recognized, but I can't recall the title or artist. | 26.5% | 45.0% | 64.1% |
| B | 1,136 | find a specific song by its exact lyrical phrase | find multiple songs by Anitta that focus on themes of female empowerment and self-confidence. | 27.2% | 48.1% | 65.5% |
| E | 760 | progress through a specific musical journey from classic EBM to modern synthpop and futurepop, emphasizing melodic elements and avoiding overly harsh industrial sounds | progress through a specific musical journey wit... | 27.9% | 48.9% | 68.4% |
| D | 688 | find one specific song from the Moana soundtrack that evokes a sense of epic journey and exploration, but the listener can't remember its exact title. | find one specific high-energy hip-hop song perfect for driving,... | 27.9% | 47.7% | 64.8% |
| A | 488 | find one specific instrumental track from "The Elder Scrolls Online Original Game Soundtrack" remembered by its distinctive orchestral sound, mood, or thematic quality (e.g., a battle theme, an exploration piece, or a... | 28.3% | 51.0% | 69.1% |
| F | 760 | find multiple electronic/dance tracks from the late 90s and early 2000s with specific characteristics (e.g., energetic, downtempo, vocal-focused) | find a specific Linkin Park song from a particular album and its orig... | 31.2% | 56.6% | 72.2% |
| H | 1,080 | find multiple songs from punk and hardcore punk artists with specific sub-genre characteristics, lyrical themes, or historical periods. | identify one specific artist (VNV Nation) or find their defining song(s) from a... | 31.5% | 50.1% | 70.6% |

## Standalone Glossary For Hard Slices

The repo docs and HF schema expose conversation_goal.category, specificity, and listener_goal, but do not provide official human-readable names for category codes. The descriptions below are derived from the observed listener_goal examples in this devset.

LL and categories C/K/I/J are called out because their union@20 or union@100 rates show a candidate-generation problem. A trained ranker can recover near misses, but it cannot recover turns where the gold track never enters the union pool.

### Specificity Codes

| Code | Plain meaning | Observed goal shape | n | Final@20 | Union@20 | Union@100 | Why it matters |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `LL` | Low / low specificity | Observed goals are broad discovery or multi-item asks with weak exact-entity constraints. Example: discover multiple instrumental pieces from a broad era or explore ambient/downtempo music. | 2,224 | 20.2% | 40.5% | 60.5% | This is the worst specificity slice: a ranker helps only after better candidates enter union@20/100. |
| `LH` | Low / high specificity | Observed goals often name a hidden target type or specific memory, but the surface clue is vague. Example: find one album remembered by cover art, or identify a composer/song from vague soundtrack memory. | 2,504 | 29.9% | 47.8% | 65.6% | Needs better goal-conditioned retrieval and structured metadata, not only exact text matching. |
| `HL` | High / low specificity | Observed goals have concrete genres, artists, eras, or journey constraints, but still ask for multiple possible tracks. Example: find multiple punk/hardcore songs with era and lyrical-theme constraints. | 2,456 | 26.4% | 50.0% | 68.8% | Candidate generation is decent, but final ranking/policy still loses many recoverable items. |
| `HH` | High / high specificity | Observed goals often identify exact titles, artists, lyrics, albums, or strongly constrained targets. Example: play a specific globally popular song by exact title and artist. | 816 | 41.9% | 59.7% | 76.1% | This is the easiest slice; it is the guardrail when adding broad-goal retrievers or metadata features. |

### Focus Categories C/K/I/J

#### Category C: Visual / cover-art remembered album targets.

- Metrics: n=464; Final@20=24.3%; Union@20=42.2%; Union@100=57.5%.
- Why it gaps: The user clue is often visual or remembered-art based, while current retrieval is mostly text/tags/embeddings from track metadata.
- Work on: Add cover-art caption/visual retrieval and album-level matching, then rerank with visual-goal features.
- Observed goals: find one specific album remembered by its distinctive, dark, and abstract or unsettling cover art. | find one specific heavy metal album remembered by its distinctive, often dark or fantastical, cover art | find one specific album remembered by its distinctive or unusual cover art, often featuring surreal or eye-catching imagery from the 70s/80s.

#### Category K: Broad instrumental, soundtrack, mood, era, or aesthetic discovery.

- Metrics: n=1,248; Final@20=24.0%; Union@20=42.6%; Union@100=62.8%.
- Why it gaps: The goal is latent and multi-answer; exact entity recall is weak and generic dense branches often bury the intended target.
- Work on: Add instrumental/OST/mood/tag-popularity retrievers and use goal text plus state tags as candidate generators.
- Observed goals: discover multiple instrumental pieces from a broad era, particularly film scores or contemporary classical works, that evoke a timeless or classic feel. | discover multiple chill, instrumental lo-fi hip-hop tracks from the mid-2010s that evoke a relaxed and nostalgic atmosphere | discover multiple songs that evoke a retro-futuristic or 80s electronic aesthetic, without needing specific constraints initially.

#### Category I: Small mixed slice: exact global-hit requests plus nuanced modern genre/style asks.

- Metrics: n=144; Final@20=22.2%; Union@20=43.1%; Union@100=60.4%.
- Why it gaps: It combines exact popularity/canonicality with style-matching, so one generic routing strategy misses both ends.
- Work on: Split routing between exact-popular probes and style/genre candidate generation; do not rely on equal current fusion weights.
- Observed goals: play a specific globally popular song by exact title and artist | find modern electronic dance music that blends deep house grooves with soulful vocal elements or jazz influences. | find one specific catchy international pop hit from the mid-2010s that gained widespread recognition.

#### Category J: Popularity, canonicality, or widely-recognized song requests within an era/genre/community.

- Metrics: n=616; Final@20=26.5%; Union@20=45.0%; Union@100=64.1%.
- Why it gaps: The clue is often 'popular/recognized' rather than a track title, but popularity is not a calibrated final-ranker feature.
- Work on: Add popularity/canonicality features and genre-community popularity lookups; train the ranker to trust them only when state asks for it.
- Observed goals: play one specific song that is known for its high popularity within its genre or era. | find a specific song from the early 90s that was a massive hit and widely recognized, but I can't recall the title or artist. | find multiple songs that are popular within specific niche music communities or subgenres.


## User Metadata Field Map

- Live inline `user_profile` fields: `age`, `age_group`, `country_code`, `country_name`, `gender`, `preferred_language`, `preferred_musical_culture`, `user_id`, `user_split`.
- Standalone user metadata fields: `age`, `age_group`, `country_code`, `country_name`, `gender`, `user_id`.
- Compact report example profile fields: `age_group`, `country_name`, `preferred_musical_culture`.
- Current pipeline summary: Current inference passes user_id and session_memory into the compiler. UserProfileDB renders only user_id, age_group, gender, and country_name for response generation; preferred_musical_culture and preferred_language are not used by retrieval/ranking.
- Ranker summary: For the trained-ranker path, preferred_musical_culture is the most actionable user-profile field. country_name/country_code can be weak context; age, age_group, and gender should be diagnostics or guarded weak features.

| Field | Where it appears | Meaning | Current use | Better use |
| --- | --- | --- | --- | --- |
| `age` | inline user_profile and standalone User Metadata | Exact user age. | Available, but not rendered by the default UserProfileDB prompt string. | Low-priority weak feature or slice only; avoid hard personalization from demographics. |
| `age_group` | inline user_profile, standalone User Metadata, and report examples | Decade bucket such as 20s or 30s. | Rendered into the response-generation profile string; carried in report examples and slices. | Use as a weak/calibrated feature and diagnostic slice, not as a filter. |
| `country_code` | inline user_profile and standalone User Metadata | ISO country code. | Available, but not rendered by the default profile string. | Use for geography/culture diagnostics or cautious localization features. |
| `country_name` | inline user_profile, standalone User Metadata, and report examples | Full country name. | Rendered into the response-generation profile string; report slices also track country. | Use cautiously for cultural priors or localized music requests; never override explicit user intent. |
| `gender` | inline user_profile and standalone User Metadata | Organizer-provided gender label. | Rendered into the response-generation profile string; not used by retrieval/ranking. | Prefer diagnostics/guardrails only; avoid ranking decisions driven by gender. |
| `preferred_language` | inline user_profile in conversation rows | Preferred language for the session/user. | Available in organizer rows but not passed into compiler retrieval/ranking. | Useful for response style and multilingual/local music cues; weak ranking feature if explicit request is ambiguous. |
| `preferred_musical_culture` | inline user_profile and report examples | Organizer cultural/music-affinity label, such as Punk/Hardcore Subculture. | Used only for this report's examples/slices; not used by current retrieval/ranking. | Highest-value user metadata feature to test for ranker/router personalization, especially culture-specific genre asks. |
| `user_id` | inline user_profile and standalone User Metadata | Stable user join key. | Passed into inference; UserProfileDB uses it to join the standalone profile. | Use only as a join key for profile/user-embedding features; avoid identity memorization in devset CV. |
| `user_split` | inline user_profile in live HF rows | Organizer split marker such as test_warm. | Not used by retrieval/ranking; not present in the standalone user metadata table. | Diagnostic only; do not train deployable ranking behavior on split labels. |

## State And Retriever Findings

### What The State Object Looks Like

The v0+ pipeline extracts a structured `ConversationStateV0Plus`, resolves surface names to catalog IDs, then compiles that state into BM25, dense, lookup, centroid, masking, fusion, and post-fusion signals.

| State field | Meaning | Retrieval/ranking use | Where to see it in examples |
| --- | --- | --- | --- |
| `turn_intent` | Natural-language active ask for this turn. | Main BM25 and dense-query text. | Shown as State turn_intent in each failed example. |
| `intent_mode` | open_explore, refinement, pivot, or playlist_build. | Controls anchor mixing and whether prior accepted tracks should influence retrieval. | Shown in the rank/evidence strip and state audit. |
| `track_feedback / anchors` | Played tracks and whether the user accepted, rejected, seeded, or reacted neutrally. | Accepted/seed tracks become centroid anchors; rejected tracks can demote artists/tracks. | The report shows n_anchor, n_played, and anchor_artist_ids when available. |
| `mentioned_entities` | Artists, albums, tracks, and tags named by the user with sentiment. | Feeds BM25 clauses, resolver targets, discography lookup, tag boosts, and state QA. | Shown as mentioned and resolved entities in failed-example details. |
| `positive / rejected tags` | Tag-like constraints extracted from the user turn and history. | Positive tags boost matching candidates; rejected tags can demote. | Shown as positive_tags, gt_tag_overlap, and rejected tags. |
| `release_year_range / hard_filters` | Soft era hints and hard catalog constraints. | Era lookup, year boosts, and candidate masks. Era should be soft because many misses are release-date mismatches. | Shown as release bucket, release year, year_range, and hard_filters. |
| `explicit_rejections` | Artists, tracks, or tags the user explicitly wants excluded. | Hard drops or post-fusion demotions. | Shown in state audit when present. |
| `process_constraints.exploration_policy` | Whether to exploit, diversify artists/albums, or stay balanced. | Post-fusion same-artist/same-album demotion policy. | Shown as policy; many recoverable misses are under diversify_artists. |
| `routing_tags` | Flags such as exact_entity_probe, lyric_search, feature_articulation, image_or_visual_search, hidden_target_search. | Should steer branch weighting/routing; current routing boost is limited. | Shown as routing in the example details. |
| `lyrical_theme` | Theme or subject requested for lyrics. | Lyric dense branch query when lyric intent is detected. | Shown in state audit when available. |

### What Failed Examples Contain

| Evidence | What we have | Why it matters |
| --- | --- | --- |
| Raw conversation | Current user turn, previous user turn, and recent conversation messages joined from the HF test split. | Lets us see whether the extracted state dropped constraints or over-carried stale context. |
| Organizer metadata | conversation_goal.category, specificity, listener_goal, goal_progress_assessments, and compact user profile. | Gives goal family and deployable metadata features for routing/ranking. |
| Ground truth and ranks | GT track/artist, final rank, fused rank, best branch, min branch rank, and per-branch ranks. | Separates candidate-generation gaps from current-fusion/post-fusion/finalization losses. |
| Extracted/resolved state audit | intent mode, mentioned/resolved entities, positive/rejected tags, hard filters, year range, lyrical theme, anchors, played count, and anchor artists. | Shows whether state is wrong, incomplete, stale, or simply not used strongly enough. |
| Action label | Case bucket, diagnosis, and smallest next test. | Turns examples into work items: retriever/state gap, ranker gap, or policy/demotion gap. |

### State often lacks the target entity

5,046 turns (63.1%) have no gold track or artist grounded in state.

Implication: This is a state/retriever coverage problem, not just a current-fusion problem. The next state should expose latent canonicality, goal, and continuation intent.

### Post-fusion policy is suppressing recoverable items

In fused-top20 demotions, same_artist_as_played appears in 659 cases and diversify_artists in 626.

Implication: Keep diversity as a feature, but stop letting it erase high-confidence branch survivors without a calibrated ranker.

### Era extraction can become a penalty

634 turns are marked release_range_excludes_gt in the current slice table.

Implication: Treat era as soft positive evidence or catalog-normalized original-era evidence, not a hard-ish demotion from release_date alone.

### Unresolved mentions are small; latent asks are bigger

Only 27 turns mention the gold artist name unresolved, while no-target-in-state is much larger.

Implication: The larger miss is not fuzzy matching names. It is representing broad requests like 'popular alternative rock' as candidate generators.

## Recommended Experiments

### P0: Trusted survivor and demotion ablation

Why: Gold items already in fused top-20 or branch top-20 should not vanish before final top-20.

How: Reserve 3-5 slots for high-confidence exact/discography/BM25/dense winners, and sweep diversify_artists and release-range demotion strengths.

Success: Raises final@20 without lowering union@20; inspect same-artist and release-excluded slices.

### P0: Train a first-stage ranker over union@200

Why: Union@20 exceeds final@20 by 20.3 pp; union@100 gives a 66.2% ceiling.

How: Use LambdaMART or logistic pairwise scoring with branch ranks, branch counts, state features, tag/release/popularity features, and policy multipliers.

Success: Improves final Hit@20/NDCG@20 and fusion_efficiency@20 on session-held-out dev evaluation.

### P1: Popularity-aware latent-target retrievers

Why: 52.3% of turns are not in union@20, and 33.8% are not in union@100.

How: Add tag+popularity, goal-conditioned, and similar-artist expansion retrievers keyed by raw user turn plus cleaned state tags.

Success: Raises union@20/100 before any ranker changes, especially broad popular/canonical requests.

### P1: State audit with raw conversation alignment

Why: Raw user turns expose sticky tags, lost constraints, and policy mistakes that compact state hides.

How: Add an audit that compares current user text, conversation_goal, prior accepted tracks, extracted state, and gold branch ranks.

Success: Reduces no_gt_track_or_artist_in_state and release_range_excludes_gt miss rates in targeted slices.

## Example Gaps

### not_in_any_branch_top1000 - Fluorescent Adolescent by Arctic Monkeys

- Session/turn: `ba3da7b0-1e81-4d2a-90fa-65ee1f4d7348` / `2`
- User turn: Perfect! That was the popular song I was looking for. Now, what are some other highly popular alternative rock tracks you have?
- Organizer goal: category `J`, specificity `HH`, listener_goal: play one specific song that is known for its high popularity within its genre or era.
- Profile: `{'age_group': '30s', 'country_name': 'Mexico', 'preferred_musical_culture': 'Anglo-American Rock'}`
- State intent: Now, what are some other highly popular alternative rock tracks you have?
- State audit: intent_mode `open_explore`, mentioned `[['artist', 'Nirvana', 1], ['track', 'Heart-Shaped Box', 1], ['tag', 'popular', 1], ['tag', 'alternative rock', 1], ['tag', 'rock', 1], ['tag', 'grunge', 1], ['tag', '90s', 1]]`, resolved `[['artist', 'Nirvana'], ['track', 'Heart-Shaped Box']]`, pos_tags `['popular', 'alternative rock', 'rock', 'grunge', '90s']`, rejected tags `[]`, year_range `None`, anchors `['Nirvana']`.
- Ranks: final `None`, fused `None`, best branch `None` via `NONE`
- Anatomy: n_pools `11`, n_anchor_tracks `1`, n_resolved_targets `2`, per_branch_rank `{'bm25': None, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': None, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': None, 'dense.clap_text.sonic.audio_laion_clap': None, 'centroid.anchor_tracks.image_siglip2': None, 'centroid.anchor_tracks.audio_laion_clap': None, 'centroid.anchor_tracks.cf_bpr': None, 'centroid.user.cf_bpr': None, 'lookup.resolved_artist_discography': None}`.
- Classification: candidate-generation gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; The ask has a popularity/canonicality signal, but final ranking has no calibrated popularity feature.; Prior-era tag appears sticky relative to the current user turn.; No retriever branch found the gold in top-1000, so a ranker cannot recover this case.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Add a tag+popularity or goal-conditioned lookup retriever and check whether the gold enters union@100.

### not_in_any_branch_top1000 - Run Like Hell by Pink Floyd

- Session/turn: `ba3da7b0-1e81-4d2a-90fa-65ee1f4d7348` / `5`
- User turn: Yes, "Mysterious Ways" is a fantastic choice! U2 is definitely a classic. Can you suggest another highly popular alternative rock track, perhaps something with a more introspective or atmospheric vibe, but still widely recognized?
- Organizer goal: category `J`, specificity `HH`, listener_goal: play one specific song that is known for its high popularity within its genre or era.
- Profile: `{'age_group': '30s', 'country_name': 'Mexico', 'preferred_musical_culture': 'Anglo-American Rock'}`
- State intent: Another highly popular alternative rock track, perhaps something with a more introspective or atmospheric vibe, but still widely recognized.
- State audit: intent_mode `refinement`, mentioned `[['tag', 'popular', 1], ['tag', 'alternative rock', 1], ['tag', 'introspective', 1], ['tag', 'atmospheric', 1], ['tag', 'widely recognized', 1]]`, resolved `[]`, pos_tags `['popular', 'alternative rock', 'introspective', 'atmospheric', 'widely recognized']`, rejected tags `[]`, year_range `None`, anchors `[]`.
- Ranks: final `None`, fused `None`, best branch `None` via `NONE`
- Anatomy: n_pools `10`, n_anchor_tracks `4`, n_resolved_targets `0`, per_branch_rank `{'bm25': None, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': None, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': None, 'dense.clap_text.sonic.audio_laion_clap': None, 'centroid.anchor_tracks.image_siglip2': None, 'centroid.anchor_tracks.audio_laion_clap': None, 'centroid.anchor_tracks.cf_bpr': None, 'centroid.user.cf_bpr': None}`.
- Classification: candidate-generation gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; The ask has a popularity/canonicality signal, but final ranking has no calibrated popularity feature.; No retriever branch found the gold in top-1000, so a ranker cannot recover this case.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Add a tag+popularity or goal-conditioned lookup retriever and check whether the gold enters union@100.

### not_in_any_branch_top1000 - On Mercury by Red Hot Chili Peppers

- Session/turn: `ba3da7b0-1e81-4d2a-90fa-65ee1f4d7348` / `6`
- User turn: Pink Floyd is iconic, and "Run Like Hell" is definitely popular. However, it's a bit more intense than the introspective vibe I was thinking of. Can you recommend another highly popular alternative rock track that truly has a more reflective or atmospheric quality?
- Organizer goal: category `J`, specificity `HH`, listener_goal: play one specific song that is known for its high popularity within its genre or era.
- Profile: `{'age_group': '30s', 'country_name': 'Mexico', 'preferred_musical_culture': 'Anglo-American Rock'}`
- State intent: Another highly popular alternative rock track with a more reflective or atmospheric quality, not as intense as Pink Floyd - Run Like Hell.
- State audit: intent_mode `refinement`, mentioned `[['artist', 'Pink Floyd', 1], ['track', 'Run Like Hell', -1], ['tag', 'popular', 1], ['tag', 'alternative rock', 1], ['tag', 'rock', 1], ['tag', 'reflective', 1], ['tag', 'atmospheric', 1], ['tag', 'introspective', 1], ['tag', 'intense', -1]]`, resolved `[['artist', 'Pink Floyd']]`, pos_tags `['popular', 'alternative rock', 'rock', 'reflective', 'atmospheric', 'introspective']`, rejected tags `['intense']`, year_range `None`, anchors `['Pink Floyd']`.
- Ranks: final `None`, fused `None`, best branch `None` via `NONE`
- Anatomy: n_pools `11`, n_anchor_tracks `4`, n_resolved_targets `1`, per_branch_rank `{'bm25': None, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': None, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': None, 'dense.clap_text.sonic.audio_laion_clap': None, 'centroid.anchor_tracks.image_siglip2': None, 'centroid.anchor_tracks.audio_laion_clap': None, 'centroid.anchor_tracks.cf_bpr': None, 'centroid.user.cf_bpr': None, 'lookup.resolved_artist_discography': None}`.
- Classification: candidate-generation gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; The ask has a popularity/canonicality signal, but final ranking has no calibrated popularity feature.; No retriever branch found the gold in top-1000, so a ranker cannot recover this case.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Add a tag+popularity or goal-conditioned lookup retriever and check whether the gold enters union@100.

### not_in_any_branch_top1000 - Perpetual by VNV Nation

- Session/turn: `8741b1b4-cd87-42fc-a56d-483e7f66494c` / `1`
- User turn: I'm trying to remember an electronic band with a really powerful, almost anthemic sound.
- Organizer goal: category `H`, specificity `LH`, listener_goal: identify one specific artist (VNV Nation) or find their defining song(s) from a vague description of their electronic, epic, and introspective style.
- Profile: `{'age_group': '20s', 'country_name': 'Argentina', 'preferred_musical_culture': 'Gothic/Industrial'}`
- State intent: An electronic band with a powerful, anthemic sound.
- State audit: intent_mode `open_explore`, mentioned `[['tag', 'electronic', 1], ['tag', 'powerful', 1], ['tag', 'anthemic', 1]]`, resolved `[]`, pos_tags `['electronic', 'powerful', 'anthemic']`, rejected tags `[]`, year_range `None`, anchors `[]`.
- Ranks: final `None`, fused `None`, best branch `None` via `NONE`
- Anatomy: n_pools `6`, n_anchor_tracks `0`, n_resolved_targets `0`, per_branch_rank `{'bm25': None, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': None, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': None, 'dense.clap_text.sonic.audio_laion_clap': None}`.
- Classification: candidate-generation gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; No retriever branch found the gold in top-1000, so a ranker cannot recover this case.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Add a tag+popularity or goal-conditioned lookup retriever and check whether the gold enters union@100.

### union20_fusion_loss - Hard Times by Cro-Mags

- Session/turn: `0979c6fc-c382-4c14-be3e-2a4711fcc532` / `1`
- User turn: I'm looking for 80s American hardcore punk bands known for their raw energy and short, intense songs.
- Organizer goal: category `H`, specificity `HL`, listener_goal: find multiple songs from punk and hardcore punk artists with specific sub-genre characteristics, lyrical themes, or historical periods.
- Profile: `{'age_group': '20s', 'country_name': 'South Africa', 'preferred_musical_culture': 'Punk/Hardcore Subculture'}`
- State intent: 80s American hardcore punk bands known for their raw energy and short, intense songs.
- State audit: intent_mode `open_explore`, mentioned `[['tag', 'hardcore punk', 1], ['tag', 'punk', 1], ['tag', 'raw', 1], ['tag', 'energetic', 1], ['tag', 'short', 1], ['tag', 'intense', 1], ['tag', '80s', 1], ['tag', 'American', 1]]`, resolved `[]`, pos_tags `['hardcore punk', 'punk', 'raw', 'energetic', 'short', 'intense', '80s', 'American']`, rejected tags `[]`, year_range `{'start': 1980, 'end': 1989}`, anchors `[]`.
- Ranks: final `134`, fused `60`, best branch `6` via `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b`
- Anatomy: n_pools `8`, n_anchor_tracks `0`, n_resolved_targets `0`, per_branch_rank `{'bm25': 215, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': 491, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': 6, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': 299, 'dense.clap_text.sonic.audio_laion_clap': None, 'centroid.user.cf_bpr': None, 'lookup.era_popularity': None}`.
- Classification: current-fusion gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; Extracted era/range excludes the catalog release year of the gold item.; A branch found the gold in top-20, but the current fusion stack did not trust that branch enough.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Score union@200 with a lightweight ranker using branch rank and state features; compare final@20 against the current fusion baseline.

### union20_fusion_loss - Electronic World Transmission - Reconstructed by [:SITD:] by Rotersand

- Session/turn: `1f1947c0-1c27-4520-9577-66af51c463f3` / `2`
- User turn: That's a good artist and the EBM sound is right, but the cover isn't quite what I'm looking for. It's a bit too literal, like a weather map. I'm thinking of something with a series of different, unsettling images, not just one big picture. Almost like a collage of dark, abstract scenes.
- Organizer goal: category `C`, specificity `LH`, listener_goal: find one specific album remembered by its distinctive, dark, and abstract or unsettling cover art.
- Profile: `{'age_group': '20s', 'country_name': 'Argentina', 'preferred_musical_culture': 'Industrial/Gothic/Electronic'}`
- State intent: An electronic/EBM album with dark, abstract cover art that is a collage of unsettling images, not a single literal picture like a weather map — Covenant's sound is right but their cover is too literal.
- State audit: intent_mode `refinement`, mentioned `[['artist', 'Covenant', 1], ['tag', 'EBM', 1], ['tag', 'electronic', 1], ['tag', 'dark', 1], ['tag', 'abstract', 1], ['tag', 'unsettling', 1], ['tag', 'collage', 1]]`, resolved `[['artist', 'Covenant']]`, pos_tags `['EBM', 'electronic', 'dark', 'abstract', 'unsettling', 'collage']`, rejected tags `['literal']`, year_range `None`, anchors `['Covenant']`.
- Ranks: final `35`, fused `45`, best branch `8` via `bm25`
- Anatomy: n_pools `7`, n_anchor_tracks `0`, n_resolved_targets `1`, per_branch_rank `{'bm25': 8, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': 167, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': None, 'dense.clap_text.sonic.audio_laion_clap': None, 'lookup.resolved_artist_discography': None}`.
- Classification: current-fusion gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; A branch found the gold in top-20, but the current fusion stack did not trust that branch enough.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Score union@200 with a lightweight ranker using branch rank and state features; compare final@20 against the current fusion baseline.

### union20_fusion_loss - Ignite by Diorama

- Session/turn: `1f1947c0-1c27-4520-9577-66af51c463f3` / `5`
- User turn: The Great Depression" is excellent! Aesthetic Perfection delivers that powerful EBM sound I love. I'm really enjoying these recommendations. Can you suggest another track that's on the darker, more atmospheric side of EBM, but still keeps that strong beat?
- Organizer goal: category `C`, specificity `LH`, listener_goal: find one specific album remembered by its distinctive, dark, and abstract or unsettling cover art.
- Profile: `{'age_group': '20s', 'country_name': 'Argentina', 'preferred_musical_culture': 'Industrial/Gothic/Electronic'}`
- State intent: Another track that's on the darker, more atmospheric side of EBM, but still keeps that strong beat.
- State audit: intent_mode `refinement`, mentioned `[['artist', 'Covenant', 1], ['artist', 'Rotersand', 1], ['artist', 'Combichrist', 1], ['artist', 'Aesthetic Perfection', 1], ['tag', 'EBM', 1], ['tag', 'electronic body music', 1], ['tag', 'dark', 1], ['tag', 'atmospheric', 1], ['tag', 'strong beat', 1], ['tag', 'driving', 1], ['tag', 'high-energy', 1]]`, resolved `[['artist', 'Covenant'], ['artist', 'Rotersand'], ['artist', 'Combichrist'], ['artist', 'Aesthetic Perfection']]`, pos_tags `['EBM', 'electronic body music', 'dark', 'atmospheric', 'strong beat', 'driving', 'high-energy']`, rejected tags `[]`, year_range `None`, anchors `['Covenant', 'Rotersand', 'Combichrist', 'Aesthetic Perfection']`.
- Ranks: final `35`, fused `50`, best branch `4` via `centroid.anchor_tracks.audio_laion_clap`
- Anatomy: n_pools `10`, n_anchor_tracks `4`, n_resolved_targets `4`, per_branch_rank `{'bm25': 133, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': None, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': 47, 'dense.clap_text.sonic.audio_laion_clap': 294, 'centroid.anchor_tracks.image_siglip2': None, 'centroid.anchor_tracks.audio_laion_clap': 4, 'centroid.anchor_tracks.cf_bpr': None, 'lookup.resolved_artist_discography': None}`.
- Classification: current-fusion gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; A branch found the gold in top-20, but the current fusion stack did not trust that branch enough.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Score union@200 with a lightweight ranker using branch rank and state features; compare final@20 against the current fusion baseline.

### union20_fusion_loss - Architect by Aesthetic Perfection

- Session/turn: `1f1947c0-1c27-4520-9577-66af51c463f3` / `6`
- User turn: Ignite" by Diorama is great! That's exactly the kind of dark, atmospheric EBM I was looking for. The melancholic vibe is really good. Do you have anything similar but maybe with a slightly more industrial or harsh edge to it?
- Organizer goal: category `C`, specificity `LH`, listener_goal: find one specific album remembered by its distinctive, dark, and abstract or unsettling cover art.
- Profile: `{'age_group': '20s', 'country_name': 'Argentina', 'preferred_musical_culture': 'Industrial/Gothic/Electronic'}`
- State intent: Another track similar to 'Ignite' by Diorama but with a more industrial or harsh edge, keeping the dark, atmospheric EBM sound.
- State audit: intent_mode `refinement`, mentioned `[['artist', 'Diorama', 1], ['track', 'Ignite', 1], ['tag', 'dark', 1], ['tag', 'atmospheric', 1], ['tag', 'EBM', 1], ['tag', 'Electronic Body Music', 1], ['tag', 'industrial', 1], ['tag', 'harsh', 1], ['tag', 'aggressive', 1], ['tag', 'industrial metal', 1]]`, resolved `[['artist', 'Diorama'], ['track', 'Ignite']]`, pos_tags `['dark', 'atmospheric', 'EBM', 'Electronic Body Music', 'industrial', 'harsh', 'aggressive', 'industrial metal']`, rejected tags `[]`, year_range `None`, anchors `['Diorama']`.
- Ranks: final `36`, fused `28`, best branch `20` via `bm25`
- Anatomy: n_pools `10`, n_anchor_tracks `6`, n_resolved_targets `2`, per_branch_rank `{'bm25': 20, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': 898, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': 20, 'dense.clap_text.sonic.audio_laion_clap': 553, 'centroid.anchor_tracks.image_siglip2': None, 'centroid.anchor_tracks.audio_laion_clap': 65, 'centroid.anchor_tracks.cf_bpr': None, 'lookup.resolved_artist_discography': None}`.
- Classification: current-fusion gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; A branch found the gold in top-20, but the current fusion stack did not trust that branch enough.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Score union@200 with a lightweight ranker using branch rank and state features; compare final@20 against the current fusion baseline.

### union20_postfusion_or_final_loss - Too Drunk to Fuck by Dead Kennedys

- Session/turn: `0979c6fc-c382-4c14-be3e-2a4711fcc532` / `4`
- User turn: Dead Kennedys, yes! "California Uber Alles" is perfect for that politically charged, critical punk sound. They're legends. Now that we've explored that, how about some more 80s American hardcore punk bands that incorporated a bit more melody or even some metallic influences into their sound, while still keeping that raw energy?
- Organizer goal: category `H`, specificity `HL`, listener_goal: find multiple songs from punk and hardcore punk artists with specific sub-genre characteristics, lyrical themes, or historical periods.
- Profile: `{'age_group': '20s', 'country_name': 'South Africa', 'preferred_musical_culture': 'Punk/Hardcore Subculture'}`
- State intent: More 80s American hardcore punk bands that incorporated a bit more melody or even some metallic influences into their sound, while still keeping that raw energy.
- State audit: intent_mode `refinement`, mentioned `[['artist', 'Dead Kennedys', 1], ['tag', '80s', 1], ['tag', 'American hardcore punk', 1], ['tag', 'hardcore punk', 1], ['tag', 'punk', 1], ['tag', 'raw energy', 1], ['tag', 'raw', 1], ['tag', 'melodic', 1], ['tag', 'melody', 1], ['tag', 'metallic', 1], ['tag', 'metal', 1], ['tag', 'crossover thrash', 1]]`, resolved `[['artist', 'Dead Kennedys']]`, pos_tags `['80s', 'American hardcore punk', 'hardcore punk', 'punk', 'raw energy', 'raw', 'melodic', 'melody', 'metallic', 'metal', 'crossover thrash']`, rejected tags `[]`, year_range `{'start': 1980, 'end': 1989}`, anchors `['Dead Kennedys']`.
- Ranks: final `74`, fused `13`, best branch `4` via `dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b`
- Anatomy: n_pools `12`, n_anchor_tracks `3`, n_resolved_targets `1`, per_branch_rank `{'bm25': 100, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': 4, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': 400, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': 126, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': 260, 'dense.clap_text.sonic.audio_laion_clap': None, 'centroid.anchor_tracks.image_siglip2': 4, 'centroid.anchor_tracks.audio_laion_clap': None, 'centroid.anchor_tracks.cf_bpr': 685, 'centroid.user.cf_bpr': None, 'lookup.resolved_artist_discography': 13, 'lookup.era_popularity': None}`.
- Classification: post-fusion or finalization gap
- Diagnosis: Gold survives fusion top-20, then post-fusion/final policy removes it from top-20.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Run a post-fusion ablation with trusted survivor slots and weaker same-artist/album demotion.

### union20_postfusion_or_final_loss - Bad Mouth by Fugazi

- Session/turn: `0979c6fc-c382-4c14-be3e-2a4711fcc532` / `7`
- User turn: Fugazi is legendary, and "Waiting Room" is a classic, but I was looking for something a bit more sonically chaotic and abrasive for that distinct 80s American hardcore sound. Can you recommend bands that pushed the boundaries with noise, feedback, or a more unhinged, dissonant style within that scene?
- Organizer goal: category `H`, specificity `HL`, listener_goal: find multiple songs from punk and hardcore punk artists with specific sub-genre characteristics, lyrical themes, or historical periods.
- Profile: `{'age_group': '20s', 'country_name': 'South Africa', 'preferred_musical_culture': 'Punk/Hardcore Subculture'}`
- State intent: Fugazi is legendary, and 'Waiting Room' is a classic, but I was looking for something a bit more sonically chaotic and abrasive for that distinct 80s American hardcore sound. Can you recommend bands that pushed the boundaries with noise, feedback, or a more un
- State audit: intent_mode `refinement`, mentioned `[['artist', 'Fugazi', 1], ['track', 'Waiting Room', 1], ['tag', '80s', 1], ['tag', 'American hardcore punk', 1], ['tag', 'hardcore punk', 1], ['tag', 'punk', 1], ['tag', 'chaotic', 1], ['tag', 'noisy', 1], ['tag', 'abrasive', 1], ['tag', 'noise', 1], ['tag', 'feedback', 1], ['tag', 'unhinged', 1], ['tag', 'dissonant', 1]]`, resolved `[['artist', 'Fugazi'], ['track', 'Waiting Room']]`, pos_tags `['80s', 'American hardcore punk', 'hardcore punk', 'punk', 'chaotic', 'noisy', 'abrasive', 'noise', 'feedback', 'unhinged', 'dissonant']`, rejected tags `[]`, year_range `{'start': 1980, 'end': 1989}`, anchors `['Fugazi']`.
- Ranks: final `47`, fused `5`, best branch `7` via `lookup.resolved_artist_discography`
- Anatomy: n_pools `12`, n_anchor_tracks `5`, n_resolved_targets `2`, per_branch_rank `{'bm25': 17, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': 43, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': 15, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': None, 'dense.clap_text.sonic.audio_laion_clap': 808, 'centroid.anchor_tracks.image_siglip2': 60, 'centroid.anchor_tracks.audio_laion_clap': 278, 'centroid.anchor_tracks.cf_bpr': None, 'centroid.user.cf_bpr': None, 'lookup.resolved_artist_discography': 7, 'lookup.era_popularity': None}`.
- Classification: post-fusion or finalization gap
- Diagnosis: Gold survives fusion top-20, then post-fusion/final policy removes it from top-20.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Run a post-fusion ablation with trusted survivor slots and weaker same-artist/album demotion.

### union20_postfusion_or_final_loss - WTF Is Wrong With You People? by Combichrist

- Session/turn: `1f1947c0-1c27-4520-9577-66af51c463f3` / `7`
- User turn: Yes, "Architect" definitely has that industrial edge I was looking for! It's a fantastic track and exactly what I like. Thank you. Can you recommend something from a different artist with a similar dark, heavy industrial electronic sound?
- Organizer goal: category `C`, specificity `LH`, listener_goal: find one specific album remembered by its distinctive, dark, and abstract or unsettling cover art.
- Profile: `{'age_group': '20s', 'country_name': 'Argentina', 'preferred_musical_culture': 'Industrial/Gothic/Electronic'}`
- State intent: Recommend something from a different artist with a similar dark, heavy industrial electronic sound.
- State audit: intent_mode `refinement`, mentioned `[['tag', 'dark', 1], ['tag', 'heavy', 1], ['tag', 'industrial', 1], ['tag', 'electronic', 1], ['tag', 'industrial electronic', 1], ['tag', 'EBM', 1]]`, resolved `[]`, pos_tags `['dark', 'heavy', 'industrial', 'electronic', 'industrial electronic', 'EBM']`, rejected tags `[]`, year_range `None`, anchors `[]`.
- Ranks: final `126`, fused `16`, best branch `2` via `centroid.anchor_tracks.image_siglip2`
- Anatomy: n_pools `9`, n_anchor_tracks `4`, n_resolved_targets `0`, per_branch_rank `{'bm25': 312, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': 696, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': None, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': 4, 'dense.clap_text.sonic.audio_laion_clap': None, 'centroid.anchor_tracks.image_siglip2': 2, 'centroid.anchor_tracks.audio_laion_clap': 135, 'centroid.anchor_tracks.cf_bpr': None}`.
- Classification: post-fusion or finalization gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; Gold survives fusion top-20, then post-fusion/final policy removes it from top-20.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Run a post-fusion ablation with trusted survivor slots and weaker same-artist/album demotion.

### union20_postfusion_or_final_loss - Moons of Evening Star by Brad Derrick

- Session/turn: `55327e13-612b-4ca0-b12c-cbfa493cd687` / `8`
- User turn: Yes, 'Echoes of Aldmeris' is exactly the kind of mysterious and atmospheric track I was thinking of! It's fantastic for those ancient ruin explorations. You've nailed it with all these recommendations from The Elder Scrolls Online. Thanks for all the great music!
- Organizer goal: category `A`, specificity `LH`, listener_goal: find one specific instrumental track from "The Elder Scrolls Online Original Game Soundtrack" remembered by its distinctive orchestral sound, mood, or thematic quality (e.g., a battle theme, an exploration piece, or a solemn melody).
- Profile: `{'age_group': '20s', 'country_name': 'Netherlands', 'preferred_musical_culture': 'Gaming Culture'}`
- State intent: Another track from The Elder Scrolls Online soundtrack that is grand and epic, but more about an inspiring journey or grand discovery, rather than a direct battle.
- State audit: intent_mode `playlist_build`, mentioned `[['tag', 'grand', 1], ['tag', 'epic', 1], ['tag', 'orchestral', 1], ['tag', 'inspiring journey', 1], ['tag', 'grand discovery', 1], ['tag', 'adventure', 1], ['tag', 'expansive', 1], ['tag', 'game soundtrack', 1], ['tag', 'video game music', 1], ['tag', 'The Elder Scrolls Online', 1], ['tag', 'Elder Scrolls Online', 1]]`, resolved `[]`, pos_tags `['grand', 'epic', 'orchestral', 'inspiring journey', 'grand discovery', 'adventure', 'expansive', 'game soundtrack', 'video game music', 'The Elder Scrolls Online', 'Elder Scrolls Online']`, rejected tags `[]`, year_range `None`, anchors `[]`.
- Ranks: final `69`, fused `13`, best branch `15` via `centroid.anchor_tracks.image_siglip2`
- Anatomy: n_pools `9`, n_anchor_tracks `7`, n_resolved_targets `0`, per_branch_rank `{'bm25': None, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': 49, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': 22, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': 18, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': 116, 'dense.clap_text.sonic.audio_laion_clap': 951, 'centroid.anchor_tracks.image_siglip2': 15, 'centroid.anchor_tracks.audio_laion_clap': 754, 'centroid.anchor_tracks.cf_bpr': 47}`.
- Classification: post-fusion or finalization gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Run a post-fusion ablation with trusted survivor slots and weaker same-artist/album demotion.

### union100_near_miss - Fuck Authority by Wasted Youth

- Session/turn: `0979c6fc-c382-4c14-be3e-2a4711fcc532` / `2`
- User turn: Yes, Cro-Mags is a great pick for that raw, intense 80s hardcore sound. Can you recommend a few more bands with that same kind of aggressive, no-frills energy and short song structures?
- Organizer goal: category `H`, specificity `HL`, listener_goal: find multiple songs from punk and hardcore punk artists with specific sub-genre characteristics, lyrical themes, or historical periods.
- Profile: `{'age_group': '20s', 'country_name': 'South Africa', 'preferred_musical_culture': 'Punk/Hardcore Subculture'}`
- State intent: Recommend a few more bands with the same aggressive, no-frills energy and short song structures as Cro-Mags, from 80s American hardcore punk.
- State audit: intent_mode `refinement`, mentioned `[['artist', 'Cro-Mags', 1], ['tag', '80s', 1], ['tag', 'American hardcore punk', 1], ['tag', 'hardcore punk', 1], ['tag', 'punk', 1], ['tag', 'raw', 1], ['tag', 'intense', 1], ['tag', 'aggressive', 1], ['tag', 'no-frills', 1], ['tag', 'short songs', 1], ['tag', 'energetic', 1]]`, resolved `[['artist', 'Cro-Mags']]`, pos_tags `['80s', 'American hardcore punk', 'hardcore punk', 'punk', 'raw', 'intense', 'aggressive', 'no-frills', 'short songs', 'energetic']`, rejected tags `[]`, year_range `{'start': 1980, 'end': 1989}`, anchors `['Cro-Mags']`.
- Ranks: final `137`, fused `110`, best branch `24` via `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b`
- Anatomy: n_pools `12`, n_anchor_tracks `1`, n_resolved_targets `1`, per_branch_rank `{'bm25': None, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': None, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': 24, 'dense.clap_text.sonic.audio_laion_clap': None, 'centroid.anchor_tracks.image_siglip2': None, 'centroid.anchor_tracks.audio_laion_clap': 33, 'centroid.anchor_tracks.cf_bpr': None, 'centroid.user.cf_bpr': None, 'lookup.resolved_artist_discography': None, 'lookup.era_popularity': None}`.
- Classification: retriever depth or state gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Evaluate union@100 ranker recovery and branch-specific calibration before adding a new retriever.

### union100_near_miss - Former Self by Icon Of Coil

- Session/turn: `8741b1b4-cd87-42fc-a56d-483e7f66494c` / `8`
- User turn: Sentinal" is fantastic, I love the energy and the powerful synths! 'Of Faith, Power and Glory' sounds like another must-listen. You've given me so many great VNV Nation tracks already. What other bands or artists have a similar powerful EBM/futurepop sound to VNV Nation that you think I might enjoy?
- Organizer goal: category `H`, specificity `LH`, listener_goal: identify one specific artist (VNV Nation) or find their defining song(s) from a vague description of their electronic, epic, and introspective style.
- Profile: `{'age_group': '20s', 'country_name': 'Argentina', 'preferred_musical_culture': 'Gothic/Industrial'}`
- State intent: What other bands or artists have a similar powerful EBM/futurepop sound to VNV Nation that you think I might enjoy?
- State audit: intent_mode `playlist_build`, mentioned `[['artist', 'VNV Nation', 1], ['track', 'Perpetual', 1], ['track', 'Arclight', 1], ['track', 'Fearless', 1], ['track', 'Carbon', 1], ['track', 'The Farthest Star', 1], ['track', 'Momentum', 1], ['track', 'Sentinal', 1], ['album', 'Empires', 1], ['album', 'Futureperfect', 1], ['album', 'Judgement', 1], ['album', 'Of Faith, Power and Glory', 1], ['tag', 'powerful', 1], ['tag', 'anthemic', 1], ['tag', 'epic', 1], ['tag', 'driving', 1], ['tag', 'introspective', 1], ['tag', 'atmospheric', 1], ['tag', 'dark', 1], ['tag', 'synths', 1], ['tag', 'EBM', 1], ['tag', 'futurepop', 1], ['tag', 'electronic', 1], ['tag', 'early 2000s', 1]]`, resolved `[['artist', 'VNV Nation'], ['track', 'Perpetual'], ['track', 'Arclight'], ['track', 'Fearless'], ['track', 'Carbon'], ['track', 'The Farthest Star'], ['track', 'Momentum'], ['track', 'Sentinal']]`, pos_tags `['powerful', 'anthemic', 'epic', 'driving', 'introspective', 'atmospheric', 'dark', 'synths', 'EBM', 'futurepop', 'electronic', 'early 2000s']`, rejected tags `[]`, year_range `None`, anchors `['VNV Nation']`.
- Ranks: final `27`, fused `30`, best branch `35` via `bm25`
- Anatomy: n_pools `10`, n_anchor_tracks `7`, n_resolved_targets `8`, per_branch_rank `{'bm25': 35, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': 54, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': None, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': 133, 'dense.clap_text.sonic.audio_laion_clap': None, 'centroid.anchor_tracks.image_siglip2': None, 'centroid.anchor_tracks.audio_laion_clap': 48, 'centroid.anchor_tracks.cf_bpr': None, 'lookup.resolved_artist_discography': None}`.
- Classification: retriever depth or state gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Evaluate union@100 ranker recovery and branch-specific calibration before adding a new retriever.

### union100_near_miss - Eple by Röyksopp

- Session/turn: `a510a742-18e9-4098-83a2-7e7f9a25aca7` / `5`
- User turn: Oh, "Teardrop" is fantastic! That's exactly the kind of deep, atmospheric electronic track with a prominent bassline I was hoping for. You're nailing these! How about something from the late 90s/early 2000s electronic scene that's more instrumental and perhaps a bit more melodic?
- Organizer goal: category `F`, specificity `HL`, listener_goal: find multiple electronic/dance tracks from the late 90s and early 2000s with specific characteristics (e.g., energetic, downtempo, vocal-focused)
- Profile: `{'age_group': '20s', 'country_name': 'Argentina', 'preferred_musical_culture': 'British Electronic'}`
- State intent: Something from the late 90s/early 2000s electronic scene that's more instrumental and perhaps a bit more melodic.
- State audit: intent_mode `refinement`, mentioned `[['tag', 'late 90s', 1], ['tag', 'early 2000s', 1], ['tag', 'electronic', 1], ['tag', 'instrumental', 1], ['tag', 'melodic', 1]]`, resolved `[]`, pos_tags `['late 90s', 'early 2000s', 'electronic', 'instrumental', 'melodic']`, rejected tags `[]`, year_range `{'start': 1995, 'end': 2004}`, anchors `[]`.
- Ranks: final `65`, fused `195`, best branch `51` via `centroid.anchor_tracks.cf_bpr`
- Anatomy: n_pools `10`, n_anchor_tracks `4`, n_resolved_targets `0`, per_branch_rank `{'bm25': None, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': 360, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': 289, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': None, 'dense.clap_text.sonic.audio_laion_clap': None, 'centroid.anchor_tracks.image_siglip2': None, 'centroid.anchor_tracks.audio_laion_clap': None, 'centroid.anchor_tracks.cf_bpr': 51, 'lookup.era_popularity': None}`.
- Classification: retriever depth or state gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Evaluate union@100 ranker recovery and branch-specific calibration before adding a new retriever.

### union100_near_miss - Miura by Metro Area

- Session/turn: `a510a742-18e9-4098-83a2-7e7f9a25aca7` / `6`
- User turn: Yes, "Eple" is fantastic! Röyksopp always delivers with those melodic, instrumental tracks. That's a perfect addition to my playlist. I'm really enjoying this journey through the late 90s and early 2000s electronic scene. Could you suggest a few more electronic tracks from that period that have a really strong, driving beat, maybe something that leans more towards house or techno?
- Organizer goal: category `F`, specificity `HL`, listener_goal: find multiple electronic/dance tracks from the late 90s and early 2000s with specific characteristics (e.g., energetic, downtempo, vocal-focused)
- Profile: `{'age_group': '20s', 'country_name': 'Argentina', 'preferred_musical_culture': 'British Electronic'}`
- State intent: A few more electronic tracks from the late 90s/early 2000s with a really strong, driving beat, leaning more towards house or techno.
- State audit: intent_mode `refinement`, mentioned `[['artist', 'Daft Punk', 1], ['artist', 'LCD Soundsystem', 1], ['artist', 'The Orb', 1], ['artist', 'Massive Attack', 1], ['artist', 'Röyksopp', 1], ['tag', 'electronic', 1], ['tag', 'late 90s', 1], ['tag', 'early 2000s', 1], ['tag', 'dance party', 1], ['tag', 'energetic', 1], ['tag', 'strong driving beat', 1], ['tag', 'driving', 1], ['tag', 'house', 1], ['tag', 'techno', 1]]`, resolved `[['artist', 'Daft Punk'], ['artist', 'LCD Soundsystem'], ['artist', 'The Orb'], ['artist', 'Massive Attack'], ['artist', 'Röyksopp']]`, pos_tags `['electronic', 'late 90s', 'early 2000s', 'dance party', 'energetic', 'strong driving beat', 'driving', 'house', 'techno']`, rejected tags `[]`, year_range `{'start': 1995, 'end': 2005}`, anchors `['Daft Punk', 'LCD Soundsystem', 'The Orb', 'Massive Attack', 'Röyksopp']`.
- Ranks: final `138`, fused `143`, best branch `22` via `dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b`
- Anatomy: n_pools `11`, n_anchor_tracks `5`, n_resolved_targets `5`, per_branch_rank `{'bm25': 221, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': 22, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': 562, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': None, 'dense.clap_text.sonic.audio_laion_clap': 448, 'centroid.anchor_tracks.image_siglip2': None, 'centroid.anchor_tracks.audio_laion_clap': None, 'centroid.anchor_tracks.cf_bpr': None, 'lookup.resolved_artist_discography': None, 'lookup.era_popularity': None}`.
- Classification: retriever depth or state gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; Extracted era/range excludes the catalog release year of the gold item.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Evaluate union@100 ranker recovery and branch-specific calibration before adding a new retriever.

### union200_deep_miss - California Uber Alles by Dead Kennedys

- Session/turn: `0979c6fc-c382-4c14-be3e-2a4711fcc532` / `3`
- User turn: Yes, Wasted Youth's "Fuck Authority" is absolutely spot on! That's exactly the kind of aggressive, no-frills 80s hardcore I'm into. These bands truly represent the core of classic punk. What about some other bands from that same era that had a particularly strong political or socially critical edge in their lyrics, even if they weren't exclusively hardcore?
- Organizer goal: category `H`, specificity `HL`, listener_goal: find multiple songs from punk and hardcore punk artists with specific sub-genre characteristics, lyrical themes, or historical periods.
- Profile: `{'age_group': '20s', 'country_name': 'South Africa', 'preferred_musical_culture': 'Punk/Hardcore Subculture'}`
- State intent: What about some other bands from that same era that had a particularly strong political or socially critical edge in their lyrics, even if they weren't exclusively hardcore?
- State audit: intent_mode `refinement`, mentioned `[['artist', 'Cro-Mags', 1], ['artist', 'Wasted Youth', 1], ['tag', '80s', 1], ['tag', 'hardcore punk', 1], ['tag', 'hardcore', 1], ['tag', 'punk', 1], ['tag', 'raw', 1], ['tag', 'aggressive', 1], ['tag', 'no-frills', 1], ['tag', 'short songs', 1], ['tag', 'intense', 1], ['tag', 'political', 1], ['tag', 'socially critical', 1], ['tag', 'American', 1]]`, resolved `[['artist', 'Cro-Mags'], ['artist', 'Wasted Youth']]`, pos_tags `['80s', 'hardcore punk', 'hardcore', 'punk', 'raw', 'aggressive', 'no-frills', 'short songs', 'intense', 'political', 'socially critical', 'American']`, rejected tags `[]`, year_range `{'start': 1980, 'end': 1989}`, anchors `['Cro-Mags', 'Wasted Youth']`.
- Ranks: final `62`, fused `161`, best branch `137` via `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b`
- Anatomy: n_pools `12`, n_anchor_tracks `2`, n_resolved_targets `2`, per_branch_rank `{'bm25': 143, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': 519, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': 212, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': 137, 'dense.clap_text.sonic.audio_laion_clap': 927, 'centroid.anchor_tracks.image_siglip2': 573, 'centroid.anchor_tracks.audio_laion_clap': 229, 'centroid.anchor_tracks.cf_bpr': 910, 'centroid.user.cf_bpr': None, 'lookup.resolved_artist_discography': None, 'lookup.era_popularity': None}`.
- Classification: retriever depth or state gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Improve candidate generation for this state slice, then rerank over the wider union pool.

### union200_deep_miss - High Hopes by Gorilla Biscuits

- Session/turn: `0979c6fc-c382-4c14-be3e-2a4711fcc532` / `5`
- User turn: Another Dead Kennedys classic, awesome! I appreciate the continued focus on politically charged punk. But I was hoping for something with a bit more *melody* or even some *metallic* influences mixed into that 80s hardcore sound. Any bands come to mind that blended those elements, keeping the raw energy intact?
- Organizer goal: category `H`, specificity `HL`, listener_goal: find multiple songs from punk and hardcore punk artists with specific sub-genre characteristics, lyrical themes, or historical periods.
- Profile: `{'age_group': '20s', 'country_name': 'South Africa', 'preferred_musical_culture': 'Punk/Hardcore Subculture'}`
- State intent: Another Dead Kennedys classic, awesome! I appreciate the continued focus on politically charged punk. But I was hoping for something with a bit more *melody* or even some *metallic* influences mixed into that 80s hardcore sound. Any bands come to mind that ble
- State audit: intent_mode `refinement`, mentioned `[['artist', 'Dead Kennedys', 1], ['tag', '80s', 1], ['tag', 'American hardcore punk', 1], ['tag', 'hardcore punk', 1], ['tag', 'punk', 1], ['tag', 'raw energy', 1], ['tag', 'raw', 1], ['tag', 'energetic', 1], ['tag', 'melody', 1], ['tag', 'melodic', 1], ['tag', 'metallic', 1], ['tag', 'metal', 1], ['tag', 'politically charged', 1], ['tag', 'political', 1], ['tag', 'socially critical', 1]]`, resolved `[['artist', 'Dead Kennedys']]`, pos_tags `['80s', 'American hardcore punk', 'hardcore punk', 'punk', 'raw energy', 'raw', 'energetic', 'melody', 'melodic', 'metallic', 'metal', 'politically charged', 'political', 'socially critical']`, rejected tags `[]`, year_range `{'start': 1980, 'end': 1989}`, anchors `['Dead Kennedys']`.
- Ranks: final `208`, fused `277`, best branch `169` via `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b`
- Anatomy: n_pools `12`, n_anchor_tracks `4`, n_resolved_targets `1`, per_branch_rank `{'bm25': 198, 'dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b': None, 'dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b': None, 'dense.qwen_8b.metadata.metadata_qwen3_embedding_8b': 516, 'dense.qwen_8b.attributes.attributes_qwen3_embedding_8b': 169, 'dense.clap_text.sonic.audio_laion_clap': None, 'centroid.anchor_tracks.image_siglip2': 987, 'centroid.anchor_tracks.audio_laion_clap': 170, 'centroid.anchor_tracks.cf_bpr': None, 'centroid.user.cf_bpr': None, 'lookup.resolved_artist_discography': None, 'lookup.era_popularity': None}`.
- Classification: retriever depth or state gap
- Diagnosis: No exact gold track or gold artist is grounded in state.; State is a compressed rewrite; audit for lost constraints against the raw user turn.
- Smallest next test: Improve candidate generation for this state slice, then rerank over the wider union pool.

## Data Fields To Use Better

- `conversation_goal.category/specificity/listener_goal`: Available in dev/test and Blind-A HF rows; current inference batch does not pass it into retrieval/compiler state. Better use: Use listener_goal as goal text for broad latent-target retrieval; use category/specificity mostly as routing conditioners, slices, or candidate-varying goal compatibility rather than raw within-turn ranker constants.
- `raw current user turn and recent user turns`: Used to produce state, but not preserved in the compact recall-gap report until this join. Better use: Use for state QA and as a second ranker text feature beside state.turn_intent.
- `user_profile preferred_musical_culture/country/age_group`: UserProfileDB renders only user_id, age_group, gender, country_name; preferred_musical_culture is not used by retrieval/ranking. Better use: Add cautious personalization features and slice checks, especially for culture-specific genres.
- `goal_progress_assessments`: Available from organizer data in dev/test and Blind-A, but not passed into the compiler. Better use: Use previous-turn progress labels as state/ranking features when available; use current-turn labels only for diagnostics/training labels.
- `track popularity`: Used in lookup/backfill paths, not as a calibrated final ranker feature across all candidates. Better use: Model popularity/canonicality explicitly for asks like 'highly popular' or 'widely recognized'.
- `track tag_list and tag overlap`: Used by BM25 and post-fusion boosts; ranker does not learn tag precision by slice. Better use: Use overlap count, exact tag matches, tag rarity, and missed-positive-tag features.
- `artist_id/album_id continuity`: Used for demotion/discography; policy is mostly rule-based. Better use: Learn when same-artist continuation is good, neutral, or bad instead of fixed demotion.
- `audio/image/CF/text embeddings`: Used as branch retrievers; ranker mostly sees their current-fusion positions, not calibrated similarities. Better use: Expose branch ranks, raw distances where safe, modality coverage flags, and cross-branch agreement.
- `Qwen 8B LanceDB fields`: Trace/config use 8B branches; local source cache is missing: attributes_qwen3_embedding_8b, metadata_qwen3_embedding_8b. Better use: Use Modal LanceDB for reproducible schema/ranker feature extraction when training the ranker.

## Reusable Prompt

```text
Build a decision-ready Music CRS devset recall-gap report for v0plus_compiler_all_retrievers_devset.

Sources to inspect:
- exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl
- exp/inference/devset/v0plus_compiler_all_retrievers_devset.json
- evaluator/exp/ground_truth/devset.json
- reports/devset_recall_gap_interactive/recall_gap_data.json
- reports/devset_recall_gap_interactive/branch_diagnostics.json
- configs/v0plus_compiler_all_retrievers_devset.yaml
- docs/data.md, docs/architectures/session_state.md, docs/architectures/v0plus_retrieval.md
- Hugging Face TalkPlayData-Challenge-Dataset test split for raw conversation turns
- Hugging Face organizer metadata: conversation_goal.category/specificity/listener_goal, goal_progress_assessments, user_profile.preferred_musical_culture
- Hugging Face Blind-A schema check to determine whether organizer metadata is usable at inference time
- Local or Modal LanceDB catalog when schema/ranker feature fields are needed

Central questions:
1. Treat union@20 as the first decision boundary. If gold is not in union@20, classify it as a candidate-generation/state/retriever gap. If gold is in union@20 but not final top-20, classify it as fusion, ranker, post-fusion, or finalization loss.
2. Also report union@100 and union@1000 so we can separate near misses from deep retriever misses.
3. Diagnose whether misses come from state being wrong or incomplete. Compare raw user turns and recent conversation against trace.state.turn_intent, mentioned_entities, release_year_range, routing_tags, resolver anchors, and exploration_policy.
4. Check whether fields in the data are not being used enough: conversation_goal, user_profile, profile culture, track popularity, tags, duration, artist/album IDs, track/user embeddings, and LanceDB vector fields.
5. Decide whether the next step should be better state, better use of state, better retrievers, post-fusion fixes, or replacing the current fusion stage with a trained ranker.
6. Include concrete examples of gaps or bugs. Each example should show session_id, turn_number, raw user turn, recent context, ground-truth track/artist, final/fused/branch ranks, state fields, branch ranks, post-fusion symptoms, classification, and the smallest fix or experiment.
7. Separate confirmed bugs/config gaps from plausible gaps. Do not call something a bug unless the code/config/artifact proves it.

Output:
- Primary: visually clear HTML report with charts and an example explorer.
- Companion: Markdown report for future agents.
- Include the full prompt and source/caveat notes.
```
