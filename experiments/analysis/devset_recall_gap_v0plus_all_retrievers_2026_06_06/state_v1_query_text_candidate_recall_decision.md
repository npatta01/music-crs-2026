# State V1 Additive Candidate Recall Decision

Scope: focused 110 state-gap turns; frozen V1 state/projection; additive candidate recall only. No RRF/final-ranking/full-devset claim.

## Result

| Measure | Before full OR | After + query-text branch | Lift |
|---|---:|---:|---:|
| union@20 | 71/110 | 75/110 | +4 |
| union@50 | 82/110 | 87/110 | +5 |
| union@100 | 88/110 | 91/110 | +3 |

Protected baseline alone remains 60/110 at @20 and 60/110 at @50. The new branch is evaluated additively against the prior strongest diagnostic OR, so it cannot regress protected hits.

## What Changed

- Added `query_text_tag_popularity`: builds catalog tag/popularity candidates from frozen projected state text (`turn_intent`, current request summary/evidence, lyrical theme, and positive attribute facts).
- Added scene-term aliases for broad request language such as Christian, Latin pop, soundtrack/orchestral, country, pop-punk/emo, underground hip-hop, disco/funk, and technical/death metal.
- Added soft era scoring inside the branch. Era boosts/demotes branch order but does not filter.
- Added slash-tag expansion so catalog tags like `R&B/Soul` expose `r&b` and `soul`.

## Rescued At union@20

| Sample | Pack | GT | Branch rank | Why it worked |
|---|---|---|---:|---|
| `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6` | P0_new_artist_union20_gap_failure | Without You / Christina Aguilera | 7 | query text/scene terms surfaced the GT |
| `5f085552-b56b-440e-830b-b4e40b58f854::t6` | P0_novelty_prior_anchor_failure | Redneck Yacht Club / Craig Morgan | 6 | query text/scene terms surfaced the GT |
| `a8df96e2-c196-462c-9484-72aa093aedf4::t1` | P1_positive_tag_retrieval_gap_failure | Do Everything / Steven Curtis Chapman | 6 | query text/scene terms surfaced the GT |
| `4e2482dc-a76c-4f4b-9d3f-7becec2f8a3a::t4` | P0_new_artist_union20_gap_failure | Goodbye Pork Pie Hat / Charles Mingus | 15 | query text/scene terms surfaced the GT |

## Additional union@50 Rescue

| Sample | Pack | GT | Branch rank | Read |
|---|---|---|---:|---|
| `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6` | P1_temporal_constraint_failure | Thriller / Fall Out Boy | 42 | candidate source works, but branch-local top-20 ordering is still weak |

## Remaining @50 Misses

| Reason | Count | Read |
|---|---:|---|
| visual_cover_art_source_gap | 7 | Needs a real visual/cover-art retrieval source or image/text bridge. |
| lyric_or_theme_source_gap | 5 | Needs lyric/theme index or a stronger lyric-aware query source. |
| popularity_by_scene_query_gap | 4 | Existing tags/popularity are too sparse or generic for the target scene. |
| target_in_51_100_tail_query_or_ordering | 4 | A branch can weakly express it, but top-20/50 ordering is not sharp enough. |
| scene_subculture_or_genre_query_gap | 2 | Needs better scene/subculture lexicon or artist-neighbor graph. |
| retriever_source_or_query_gap | 1 | No current source cleanly expresses the requested relation. |

## Recommendation

- Keep `query_text_tag_popularity` as a measured diagnostic branch and candidate for indexed implementation.
- Keep slash-tag normalization.
- Do not claim full-devset or leaderboard improvement yet.
- Do not spend the next iteration on RRF/final ranking for these classes; candidate source gaps remain visible at @50.
- Next best retrieval work: indexed scene/tag-text branch, lyric/theme source, cover-art text/image source, and artist-neighbor graph for scene popularity.

## Artifacts

- Matrix JSON: `state_v1_additive_query_text_branches_all110.json`
- Matrix Markdown: `state_v1_additive_query_text_branches_all110.md`
- Bad-turn worksheet: `state_v1_candidate_recall_bad_turn_worksheet.md` / `.json` / `.csv`
- Decision JSON: `state_v1_query_text_candidate_recall_decision.json`

