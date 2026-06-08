# State V1 Candidate Quality Non-Prompt Matrix

Scope: focused-110 only. V1 state extractor prompt and schema are frozen. Metrics are additive against the protected current+targeted baseline.

## Read This First

- Current+targeted baseline: 77/110 union@20, 90/110 union@50, 93/110 union@100.
- Best non-prompt lever: `promoted_feature_family` 84/110 union@20, 95/110 union@50, 100/110 union@100.
- Valid-GT-only lift: 69/99 -> 76/99 union@20. That is +7 valid top-20 rescues with no state prompt/schema changes.
- Plain `all_on_original` does not move top-20. The gap is not only whether branches fire; it is branch-local candidate ordering using catalog tags, year/popularity compatibility, anchor-CF, and soft novelty/negative evidence.
- User-CF alone does not improve union@20, but it improves deeper recall and should be deferred as a ranking feature rather than promoted as a top-20 candidate-recall fix.

## Headline Metrics

| Variant | all n | all u@20 | all u@50 | all u@100 | valid n | valid u@20 | valid u@50 | valid u@100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `current_or` | 110 | 75/110 | 87/110 | 91/110 | 99 | 67/99 | 79/99 | 83/99 |
| `current_plus_targeted` | 110 | 77/110 | 90/110 | 93/110 | 99 | 69/99 | 82/99 | 85/99 |
| `all_on_original` | 110 | 77/110 | 90/110 | 93/110 | 99 | 69/99 | 82/99 | 85/99 |
| `catalog_features` | 110 | 80/110 | 92/110 | 98/110 | 99 | 72/99 | 84/99 | 89/99 |
| `anchor_cf_features` | 110 | 80/110 | 91/110 | 96/110 | 99 | 72/99 | 82/99 | 87/99 |
| `user_cf_features` | 110 | 77/110 | 91/110 | 101/110 | 99 | 69/99 | 83/99 | 92/99 |
| `branch_local_hybrid` | 110 | 82/110 | 94/110 | 97/110 | 99 | 74/99 | 86/99 | 89/99 |
| `catalog_plus_anchor_cf` | 110 | 81/110 | 93/110 | 99/110 | 99 | 73/99 | 84/99 | 90/99 |
| `promoted_feature_family` | 110 | 84/110 | 95/110 | 100/110 | 99 | 76/99 | 86/99 | 91/99 |
| `all_feature_family` | 110 | 84/110 | 95/110 | 104/110 | 99 | 76/99 | 86/99 | 94/99 |

## GT Audit

| Label | Count |
|---|---:|
| `gt_conflicts_with_explicit_user_constraint` | 10 |
| `underspecified_next_play_behavior` | 1 |
| `valid_gt_branch_local_ranking_weak` | 16 |
| `valid_gt_retriever_source_weak` | 2 |
| `valid_gt_state_signal_compiler_not_consumed` | 12 |
| `valid_gt_state_supports_it` | 69 |

Noisy/contradictory GT is excluded only for the valid-GT-only view. All-110 metrics still include every turn. The conflict labels are mostly literal cases like 'not Drake', 'not Daft Punk', or 'not System Of A Down' where the GT artist violates an explicit user constraint.

## Decisions

| Lever | Decision | all u@20 gain | valid u@20 gain | valid u@50 gain |
|---|---|---:|---:|---:|
| `all_on_original` | reject_without_branch_local_scoring | 0 | 0 | 0 |
| `catalog_features` | keep_for_full_devset_smoke | 3 | 3 | 2 |
| `anchor_cf_features` | keep_for_full_devset_smoke | 3 | 3 | 0 |
| `user_cf_features` | defer_to_branch_ranking_work | 0 | 0 | 1 |
| `branch_local_hybrid` | keep_for_full_devset_smoke | 5 | 5 | 4 |
| `catalog_plus_anchor_cf` | keep_for_full_devset_smoke | 4 | 4 | 2 |
| `promoted_feature_family` | keep_for_full_devset_smoke | 7 | 7 | 4 |
| `all_feature_family` | defer_user_cf_component | 7 | 7 | 4 |

## Lever Readout

- Projection-only state consumption: represented by `catalog_features` and `branch_local_hybrid`, which derive query terms from the existing frozen request summary/facts/lyrical theme and consume them as score features. This moved valid union@20, so this should become compiler-owned structured branch-local scoring before any prompt work.
- Derived catalog features: normalized tag aliases, broad track text, release year compatibility, and popularity-if-requested are positive. Keep for full-devset smoke.
- Anchor-CF: positive top-20 lift. Keep as a branch-local feature when the state has liked/reference/accepted anchors.
- User-CF: 89/110 focused users have vectors and user-CF improves union@100, but not union@20. Defer to ranking work; do not call it a candidate-recall fix yet.
- Last-resort prompt ablation: not run. The frozen state contains enough usable signal to get +7 valid union@20 from non-prompt levers, so prompt iteration should be a separate later goal only for the remaining state/lyric failures.

## Remaining Gap

- Still-near @21-50: mostly branch-local scoring/query specificity. Examples include `5ee0dbbc...::t8` at rank 22, `3676005d...::t1` at rank 27, `10a15ba2...::t7` at rank 29, and `2bbc0a7e...::t1` at rank 30.
- Deeper/missing: stale or roleless anchors still blur novelty requests, and some lyric/theme requests need a stronger lyric-aware source or better query text.
- Rejection controls stayed stable in this additive analysis: the P1 rejection guardrail valid slice remains 5/5 union@20.

## Per-Class Valid-Only union@20

| Pack | Variant | valid n | valid u@20 | valid u@50 | valid u@100 |
|---|---|---:|---:|---:|---:|
| P0_good_state_ranker_near_miss_failure | `current_plus_targeted` | 10 | 10/10 | 10/10 | 10/10 |
| P0_good_state_ranker_near_miss_failure | `all_on_original` | 10 | 10/10 | 10/10 | 10/10 |
| P0_good_state_ranker_near_miss_failure | `catalog_features` | 10 | 10/10 | 10/10 | 10/10 |
| P0_good_state_ranker_near_miss_failure | `anchor_cf_features` | 10 | 10/10 | 10/10 | 10/10 |
| P0_good_state_ranker_near_miss_failure | `user_cf_features` | 10 | 10/10 | 10/10 | 10/10 |
| P0_good_state_ranker_near_miss_failure | `branch_local_hybrid` | 10 | 10/10 | 10/10 | 10/10 |
| P0_good_state_ranker_near_miss_failure | `catalog_plus_anchor_cf` | 10 | 10/10 | 10/10 | 10/10 |
| P0_good_state_ranker_near_miss_failure | `promoted_feature_family` | 10 | 10/10 | 10/10 | 10/10 |
| P0_good_state_ranker_near_miss_failure | `all_feature_family` | 10 | 10/10 | 10/10 | 10/10 |
| P0_named_artist_ranker_failure | `current_plus_targeted` | 7 | 7/7 | 7/7 | 7/7 |
| P0_named_artist_ranker_failure | `all_on_original` | 7 | 7/7 | 7/7 | 7/7 |
| P0_named_artist_ranker_failure | `catalog_features` | 7 | 7/7 | 7/7 | 7/7 |
| P0_named_artist_ranker_failure | `anchor_cf_features` | 7 | 7/7 | 7/7 | 7/7 |
| P0_named_artist_ranker_failure | `user_cf_features` | 7 | 7/7 | 7/7 | 7/7 |
| P0_named_artist_ranker_failure | `branch_local_hybrid` | 7 | 7/7 | 7/7 | 7/7 |
| P0_named_artist_ranker_failure | `catalog_plus_anchor_cf` | 7 | 7/7 | 7/7 | 7/7 |
| P0_named_artist_ranker_failure | `promoted_feature_family` | 7 | 7/7 | 7/7 | 7/7 |
| P0_named_artist_ranker_failure | `all_feature_family` | 7 | 7/7 | 7/7 | 7/7 |
| P0_new_artist_union20_gap_failure | `current_plus_targeted` | 10 | 4/10 | 6/10 | 7/10 |
| P0_new_artist_union20_gap_failure | `all_on_original` | 10 | 4/10 | 6/10 | 7/10 |
| P0_new_artist_union20_gap_failure | `catalog_features` | 10 | 4/10 | 6/10 | 9/10 |
| P0_new_artist_union20_gap_failure | `anchor_cf_features` | 10 | 4/10 | 6/10 | 7/10 |
| P0_new_artist_union20_gap_failure | `user_cf_features` | 10 | 4/10 | 6/10 | 9/10 |
| P0_new_artist_union20_gap_failure | `branch_local_hybrid` | 10 | 4/10 | 7/10 | 9/10 |
| P0_new_artist_union20_gap_failure | `catalog_plus_anchor_cf` | 10 | 4/10 | 6/10 | 9/10 |
| P0_new_artist_union20_gap_failure | `promoted_feature_family` | 10 | 4/10 | 7/10 | 9/10 |
| P0_new_artist_union20_gap_failure | `all_feature_family` | 10 | 4/10 | 7/10 | 9/10 |
| P0_novelty_prior_anchor_failure | `current_plus_targeted` | 9 | 4/9 | 6/9 | 6/9 |
| P0_novelty_prior_anchor_failure | `all_on_original` | 9 | 4/9 | 6/9 | 6/9 |
| P0_novelty_prior_anchor_failure | `catalog_features` | 9 | 5/9 | 6/9 | 6/9 |
| P0_novelty_prior_anchor_failure | `anchor_cf_features` | 9 | 5/9 | 6/9 | 6/9 |
| P0_novelty_prior_anchor_failure | `user_cf_features` | 9 | 4/9 | 6/9 | 7/9 |
| P0_novelty_prior_anchor_failure | `branch_local_hybrid` | 9 | 5/9 | 6/9 | 6/9 |
| P0_novelty_prior_anchor_failure | `catalog_plus_anchor_cf` | 9 | 5/9 | 6/9 | 6/9 |
| P0_novelty_prior_anchor_failure | `promoted_feature_family` | 9 | 5/9 | 6/9 | 6/9 |
| P0_novelty_prior_anchor_failure | `all_feature_family` | 9 | 5/9 | 6/9 | 7/9 |
| P0_roleless_stale_entity_failure | `current_plus_targeted` | 9 | 1/9 | 4/9 | 4/9 |
| P0_roleless_stale_entity_failure | `all_on_original` | 9 | 1/9 | 4/9 | 4/9 |
| P0_roleless_stale_entity_failure | `catalog_features` | 9 | 2/9 | 4/9 | 6/9 |
| P0_roleless_stale_entity_failure | `anchor_cf_features` | 9 | 1/9 | 4/9 | 5/9 |
| P0_roleless_stale_entity_failure | `user_cf_features` | 9 | 1/9 | 4/9 | 7/9 |
| P0_roleless_stale_entity_failure | `branch_local_hybrid` | 9 | 2/9 | 5/9 | 6/9 |
| P0_roleless_stale_entity_failure | `catalog_plus_anchor_cf` | 9 | 2/9 | 4/9 | 6/9 |
| P0_roleless_stale_entity_failure | `promoted_feature_family` | 9 | 3/9 | 5/9 | 7/9 |
| P0_roleless_stale_entity_failure | `all_feature_family` | 9 | 3/9 | 5/9 | 8/9 |
| P0_same_album_ranker_failure | `current_plus_targeted` | 10 | 10/10 | 10/10 | 10/10 |
| P0_same_album_ranker_failure | `all_on_original` | 10 | 10/10 | 10/10 | 10/10 |
| P0_same_album_ranker_failure | `catalog_features` | 10 | 10/10 | 10/10 | 10/10 |
| P0_same_album_ranker_failure | `anchor_cf_features` | 10 | 10/10 | 10/10 | 10/10 |
| P0_same_album_ranker_failure | `user_cf_features` | 10 | 10/10 | 10/10 | 10/10 |
| P0_same_album_ranker_failure | `branch_local_hybrid` | 10 | 10/10 | 10/10 | 10/10 |
| P0_same_album_ranker_failure | `catalog_plus_anchor_cf` | 10 | 10/10 | 10/10 | 10/10 |
| P0_same_album_ranker_failure | `promoted_feature_family` | 10 | 10/10 | 10/10 | 10/10 |
| P0_same_album_ranker_failure | `all_feature_family` | 10 | 10/10 | 10/10 | 10/10 |
| P1_positive_tag_retrieval_gap_failure | `current_plus_targeted` | 10 | 4/10 | 7/10 | 9/10 |
| P1_positive_tag_retrieval_gap_failure | `all_on_original` | 10 | 4/10 | 7/10 | 9/10 |
| P1_positive_tag_retrieval_gap_failure | `catalog_features` | 10 | 4/10 | 9/10 | 9/10 |
| P1_positive_tag_retrieval_gap_failure | `anchor_cf_features` | 10 | 5/10 | 7/10 | 9/10 |
| P1_positive_tag_retrieval_gap_failure | `user_cf_features` | 10 | 4/10 | 8/10 | 9/10 |
| P1_positive_tag_retrieval_gap_failure | `branch_local_hybrid` | 10 | 6/10 | 9/10 | 9/10 |
| P1_positive_tag_retrieval_gap_failure | `catalog_plus_anchor_cf` | 10 | 5/10 | 9/10 | 9/10 |
| P1_positive_tag_retrieval_gap_failure | `promoted_feature_family` | 10 | 7/10 | 9/10 | 9/10 |
| P1_positive_tag_retrieval_gap_failure | `all_feature_family` | 10 | 7/10 | 9/10 | 9/10 |
| P1_rejection_guardrail_failure | `current_plus_targeted` | 5 | 5/5 | 5/5 | 5/5 |
| P1_rejection_guardrail_failure | `all_on_original` | 5 | 5/5 | 5/5 | 5/5 |
| P1_rejection_guardrail_failure | `catalog_features` | 5 | 5/5 | 5/5 | 5/5 |
| P1_rejection_guardrail_failure | `anchor_cf_features` | 5 | 5/5 | 5/5 | 5/5 |
| P1_rejection_guardrail_failure | `user_cf_features` | 5 | 5/5 | 5/5 | 5/5 |
| P1_rejection_guardrail_failure | `branch_local_hybrid` | 5 | 5/5 | 5/5 | 5/5 |
| P1_rejection_guardrail_failure | `catalog_plus_anchor_cf` | 5 | 5/5 | 5/5 | 5/5 |
| P1_rejection_guardrail_failure | `promoted_feature_family` | 5 | 5/5 | 5/5 | 5/5 |
| P1_rejection_guardrail_failure | `all_feature_family` | 5 | 5/5 | 5/5 | 5/5 |
| P1_temporal_constraint_failure | `current_plus_targeted` | 9 | 4/9 | 7/9 | 7/9 |
| P1_temporal_constraint_failure | `all_on_original` | 9 | 4/9 | 7/9 | 7/9 |
| P1_temporal_constraint_failure | `catalog_features` | 9 | 5/9 | 7/9 | 7/9 |
| P1_temporal_constraint_failure | `anchor_cf_features` | 9 | 5/9 | 7/9 | 8/9 |
| P1_temporal_constraint_failure | `user_cf_features` | 9 | 4/9 | 7/9 | 8/9 |
| P1_temporal_constraint_failure | `branch_local_hybrid` | 9 | 5/9 | 7/9 | 7/9 |
| P1_temporal_constraint_failure | `catalog_plus_anchor_cf` | 9 | 5/9 | 7/9 | 8/9 |
| P1_temporal_constraint_failure | `promoted_feature_family` | 9 | 5/9 | 7/9 | 8/9 |
| P1_temporal_constraint_failure | `all_feature_family` | 9 | 5/9 | 7/9 | 9/9 |
| POS_clean_final_hit_control | `current_plus_targeted` | 10 | 10/10 | 10/10 | 10/10 |
| POS_clean_final_hit_control | `all_on_original` | 10 | 10/10 | 10/10 | 10/10 |
| POS_clean_final_hit_control | `catalog_features` | 10 | 10/10 | 10/10 | 10/10 |
| POS_clean_final_hit_control | `anchor_cf_features` | 10 | 10/10 | 10/10 | 10/10 |
| POS_clean_final_hit_control | `user_cf_features` | 10 | 10/10 | 10/10 | 10/10 |
| POS_clean_final_hit_control | `branch_local_hybrid` | 10 | 10/10 | 10/10 | 10/10 |
| POS_clean_final_hit_control | `catalog_plus_anchor_cf` | 10 | 10/10 | 10/10 | 10/10 |
| POS_clean_final_hit_control | `promoted_feature_family` | 10 | 10/10 | 10/10 | 10/10 |
| POS_clean_final_hit_control | `all_feature_family` | 10 | 10/10 | 10/10 | 10/10 |
| POS_exact_entity_success_control | `current_plus_targeted` | 10 | 10/10 | 10/10 | 10/10 |
| POS_exact_entity_success_control | `all_on_original` | 10 | 10/10 | 10/10 | 10/10 |
| POS_exact_entity_success_control | `catalog_features` | 10 | 10/10 | 10/10 | 10/10 |
| POS_exact_entity_success_control | `anchor_cf_features` | 10 | 10/10 | 10/10 | 10/10 |
| POS_exact_entity_success_control | `user_cf_features` | 10 | 10/10 | 10/10 | 10/10 |
| POS_exact_entity_success_control | `branch_local_hybrid` | 10 | 10/10 | 10/10 | 10/10 |
| POS_exact_entity_success_control | `catalog_plus_anchor_cf` | 10 | 10/10 | 10/10 | 10/10 |
| POS_exact_entity_success_control | `promoted_feature_family` | 10 | 10/10 | 10/10 | 10/10 |
| POS_exact_entity_success_control | `all_feature_family` | 10 | 10/10 | 10/10 | 10/10 |

## Examples

### `promoted_feature_family` rescued union@20

- `daeef24e-b041-4140-9101-882820c63408::t7` (P0_novelty_prior_anchor_failure, valid_gt_branch_local_ranking_weak): GT=The Analog Kid by Rush; rank 24 -> 3 via `dense.qwen_8b.intent.metadata_qwen3_embedding_8b.anchor_cf_features`. User: Okay, it sounds like there's a problem with 'Tom Sawyer'. That's a bummer. Can you please play 'The Spirit of Radio' by Rush instead?
- `54cda581-3b2e-4245-a479-1a27589760d2::t3` (P1_positive_tag_retrieval_gap_failure, valid_gt_branch_local_ranking_weak): GT=Deliberation - Studio by Katatonia; rank 46 -> 8 via `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b.branch_local_hybrid`. User: This is getting really close! The album art for "Character" by Dark Tranquillity is definitely in the right ballpark with the ruined city and bleak atmosphere. However, the one I'm thinking of had a somewhat more abstrac
- `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` (P0_roleless_stale_entity_failure, valid_gt_state_signal_compiler_not_consumed): GT=The Carbon Stampede by Cattle Decapitation; rank 108 -> 9 via `dense.clap_text.sonic_nl.audio_laion_clap.branch_local_hybrid`. User: Suffocation is always a solid listen, but I'm really looking to discover some *new* bands. Can you suggest some more recent acts that are making waves in the technical or progressive death metal scene? I'm open to anythi
- `e66c6a88-88ba-4117-9114-363bfa96294a::t7` (P0_roleless_stale_entity_failure, valid_gt_branch_local_ranking_weak): GT=Test Drive by John Powell; rank 36 -> 16 via `centroid.anchor_tracks.audio_laion_clap.catalog_features`. User: This is absolutely perfect! "Anthem of the World" is exactly the powerful and uplifting epic music I was looking for. Can you give me more recommendations that are similar to this or Two Steps from Hell?
- `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6` (P1_temporal_constraint_failure, valid_gt_branch_local_ranking_weak): GT=Thriller by Fall Out Boy; rank 23 -> 16 via `bm25.branch_local_hybrid`. User: You're doing so well with Panic! At The Disco and the emotional vibe! "Always" is a great song, but it's still not the one that screams "mid-2000s emo phase" to me. The track I'm thinking of is definitely from their firs
- `1c567917-f931-4609-9695-a9c0f8e39f3d::t2` (P1_positive_tag_retrieval_gap_failure, valid_gt_branch_local_ranking_weak): GT=Arregaçada / U Can't Touch This by Banda Uó; rank 35 -> 16 via `dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b.anchor_cf_features`. User: That's a good start! Anitta is definitely on point for contemporary pop. What about something more recent and upbeat, specifically from the 'tecno brega' or 'funk carioca' scenes?
- `5a0dfe9d-ec8a-4449-97df-35535cbf162f::t1` (P1_positive_tag_retrieval_gap_failure, valid_gt_branch_local_ranking_weak): GT=A New World by Harry Gregson-Williams; rank 60 -> 18 via `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b.branch_local_hybrid`. User: Play something epic and orchestral, like a movie soundtrack, for background music.

### `promoted_feature_family` still missed valid GT

- `5ee0dbbc-c1d1-4bed-ba09-7dafeec198bc::t8` (P0_new_artist_union20_gap_failure): GT=You Reposted in the Wrong Neighborhood I Glue70 Mashup by Shokk; best rank=22; reason=The target is not in a strong candidate pool (best branch 102 in dense.qwen_8b.metadata.metadata_qwen3_embedding_8b; final -). This is mostly a retriever/state-to-retriever coverag; change=Improve turn-type routing and candidate generation: use listener_goal/current state, role-aware entities, tags, popularity, culture/CF affinity, and novelty profiles before spendin
- `3676005d-5b7c-4c48-9b73-3e10dd509c07::t1` (P1_temporal_constraint_failure): GT=Breath and Life by Audiomachine; best rank=27; reason=The extracted release range (2000, 2004) excludes the target release year 2012. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away be; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily pe
- `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7` (P0_roleless_stale_entity_failure): GT=I Can't Go to Sleep by Wu-Tang Clan; best rank=29; reason=The user asks for novelty or a different direction, but the state still keeps Deltron 3030, Kendrick Lamar as positive anchors. That sends retrievers toward already-satisfied artis; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metada
- `2bbc0a7e-3ab0-4376-8135-182cd4ae075f::t1` (P1_positive_tag_retrieval_gap_failure): GT=Las Almas Del Silencio by Ricky Martin; best rank=30; reason=The target is not in a strong candidate pool (best branch 101 in dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b; final 119). This is mostly a retriever/state-to-retriev; change=Improve turn-type routing and candidate generation: use listener_goal/current state, role-aware entities, tags, popularity, culture/CF affinity, and novelty profiles before spendin
- `ba68a3cc-5278-4680-917a-4ca66d33ef31::t5` (P0_new_artist_union20_gap_failure): GT=Buttons by The Pussycat Dolls; best rank=34; reason=The user asks for novelty or a different direction, but the state still keeps Spice Girls as positive anchors. That sends retrievers toward already-satisfied artists instead of the; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metada
- `907921a3-d08f-4ba1-8cce-0e760a9e7044::t7` (P0_new_artist_union20_gap_failure): GT=Sunrise - Slow Hands Remix by Kasper Bjørke; best rank=36; reason=The state still treats Men I Trust, The Goo Goo Dolls as positive artist/track evidence even though it is not present in the current user turn. This can over-anchor retrieval on co; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retri
- `464477e4-f186-47fb-8cb0-55691c8b8f57::t6` (P1_positive_tag_retrieval_gap_failure): GT=Where Eagles Dare by Glenn Danzig, Misfits; best rank=43; reason=The target is not in a strong candidate pool (best branch 102 in centroid.anchor_tracks.image_siglip2; final 475). This is mostly a retriever/state-to-retriever coverage gap, not j; change=Improve turn-type routing and candidate generation: use listener_goal/current state, role-aware entities, tags, popularity, culture/CF affinity, and novelty profiles before spendin
- `c4c0c288-dbcd-4970-ad52-901aafe91b88::t4` (P1_temporal_constraint_failure): GT=I Juswanna Chill by Large Professor; best rank=71; reason=The extracted release range (1990, 1999) excludes the target release year 2009. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away be; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily pe
- `5861afef-85c0-4163-b8b9-5a11e308f352::t4` (P0_new_artist_union20_gap_failure): GT=Carmesí by Vicente Garcia; best rank=74; reason=The user asks for novelty or a different direction, but the state still keeps DENNIS, Lucas Lucco, MC Lan as positive anchors. That sends retrievers toward already-satisfied artist; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metada
- `41367174-552b-4117-9caa-d0ba1b307d37::t2` (P0_roleless_stale_entity_failure): GT=Mercy by Muse; best rank=80; reason=The state still treats My Chemical Romance, Foo Fighters as positive artist/track evidence even though it is not present in the current user turn. This can over-anchor retrieval on; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retri
- `324ddfb5-8a18-4729-9acb-c851907a297c::t3` (P0_new_artist_union20_gap_failure): GT=Acknowledge by Masta Ace; best rank=81; reason=The extracted release range (1995, 2004) excludes the target release year 2005. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away be; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily pe
- `67b9ba8a-382f-4b70-af76-576848d8cf67::t8` (P1_temporal_constraint_failure): GT=Gangsta Gangsta by N.W.A.; best rank=85; reason=The extracted release range (1995, 2004) excludes the target release year 1988. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away be; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily pe
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` (P0_roleless_stale_entity_failure): GT=Move Along by The All-American Rejects; best rank=97; reason=The extracted release range (2000, 2004) excludes the target release year 2005. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away be; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily pe
- `0b9d547f-e748-464a-90e2-2199149f915c::t6` (P0_roleless_stale_entity_failure): GT=Give It To Me Baby by Rick James; best rank=109; reason=The user asks for novelty or a different direction, but the state still keeps The Real Thing as positive anchors. That sends retrievers toward already-satisfied artists instead of ; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metada

## User-CF Coverage

- Focused users with `cf_bpr` vector: 89/110.
- User ids found in trace: 110/110.

## Recommendation

Keep only levers with positive valid-GT union@20 lift for the next full-devset smoke. If a lever only improves union@50, treat it as evidence for branch-local ranking or a lightweight ranker, not as candidate recall solved.
