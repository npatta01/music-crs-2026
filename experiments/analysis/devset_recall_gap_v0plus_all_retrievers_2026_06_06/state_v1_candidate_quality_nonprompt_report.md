# State V1 Candidate Quality Non-Prompt Matrix

Scope: focused-110 only. V1 state extractor prompt and schema are frozen. Metrics are additive against the protected current+targeted baseline. This is a branch-local top-k quality test: it reorders existing branch pools and measures a union ceiling, not the final served top-20 list.

## Read This First

- Current+targeted baseline: 77/110 union@20, 90/110 union@50, 93/110 union@100.
- Best non-prompt lever: `promoted_feature_family` 84/110 union@20, 95/110 union@50, 100/110 union@100.
- Valid-GT-only lift: 69/99 -> 76/99 union@20. That is +7 valid branch-union top-20 rescues with no state prompt/schema changes. It still needs final-fusion validation.
- Plain `all_on_original` does not move top-20. The gap is not only whether branches fire; it is branch-local candidate ordering using catalog tags, year/popularity compatibility, anchor-CF, and soft novelty/negative evidence.
- No new candidates are introduced by these feature variants. The result means reachable @21-100 candidates can be pulled upward inside branches; it does not prove final@20/nDCG lift until the real compiler/fusion path is smoked.
- Saved-pool fusion proxy does not validate the feature family as a direct final-list fix: `protected_plus_all_on` gets 50/110 proxy@20, while `protected_plus_promoted_feature_family` gets 39/110 proxy@20. Treat the features as reranker/candidate-pool evidence, not as a production RRF patch.
- Compiler-aware branch-family scoring also fails to create current-miss top-20 rescues. That rules out a simple RRF/branch-weight fix on the saved pools; the next useful scorer needs candidate-level metadata, cross-encoder evidence, or a targeted new source for the few absent cases.
- User-CF alone does not improve union@20, but it improves deeper recall and should be deferred as a ranking feature rather than promoted as a top-20 candidate-recall fix.

## Source Truth And State Gate

- Active prompt: `mcrs/conversation_state/prompts/current.py` (`ConversationStateV1` JSON schema).
- Active schema/bridge: `mcrs/conversation_state/schema.py` (`project_v1_to_v0plus`).
- Active extractor decode path: `mcrs/qu_modules/compiler_v0plus_qu.py` validates V1, then projects to V0Plus.
- Active compiler consumers: `mcrs/qu_modules/compiler_v0plus.py` uses `mentioned_entities`, `style_reference_entities`, `turn_intent`, `lyrical_theme`, `release_year_range`, `explicit_rejections`, and `track_feedback` through the projected V0Plus view.

| Gate | Samples | Pass/read | Notes |
|---|---:|---:|---|
| role labels | 56 | 0.929 | exact seeds 1.000, style refs 1.000, query facets 1.000, temporal 1.000 |
| projected retriever contract | 56 | 53/56 | current failures are narrow synonym/phrase cases |
| fact compiler core | 56 | 0.821 | strict fact all-pass 0.714; forbidden stale seeds 1.000 |
| old V0Plus replay all-pass | 110 | 0.291 | low by design because V1 no longer asks the LLM to own policy fields |

State-gate decision: do not spend another broad paid extraction pass yet. The cached V1 extraction is good enough for focused retrieval/projection smokes; remaining state issues are localized label/prompt cases such as `popular` vs `well-known`, `metal` vs `heavy and intense`, and preserving `boost my energy` as a fact value rather than only evidence text.

## Tiny Local Retrieval Smoke

This rerun uses saved V1 extraction and disables paid dense text embedding calls. It tests BM25, lookup, era-popularity, and local centroid/style-reference consumption on 12 representative turns.

| Variant | final@20 | union@20 | union@100 | union@200 | union@1000 |
|---|---:|---:|---:|---:|---:|
| `tags_only` | 0.167 | 0.167 | 0.167 | 0.333 | 0.500 |
| `centroid_no_style` | 0.167 | 0.167 | 0.167 | 0.333 | 0.500 |
| `centroid_style_safe` | 0.167 | 0.167 | 0.250 | 0.500 | 0.583 |
| `centroid_style_broad` | 0.167 | 0.167 | 0.250 | 0.583 | 0.667 |
| `centroid_style_broad_w3` | 0.167 | 0.167 | 0.250 | 0.583 | 0.667 |
| `centroid_style_broad_w5` | 0.167 | 0.167 | 0.250 | 0.583 | 0.667 |

Smoke read: style-reference centroid consumption improves depth (`union@1000` 0.500 -> 0.667), but does not move `union@20` or `final@20`; this is ranking/order territory, not another state extraction call.

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

## Deep Branch Recall Curves

These are branch-only raw pool hits from the saved top1000 pools. They answer whether a future reranker could possibly recover the GT from a branch.

Coverage note: `state_v1_all_on_branch_pools.json` does not contain a raw SigLIP visual text-to-image pool or user-CF retrieval pool. SigLIP is reflected in the current+targeted baseline, and user-CF is tested below as a candidate feature, but their top500/top1000 branch curves are unavailable in this saved-pool run.

| Branch | Family | fired | hit@20 | hit@50 | hit@100 | hit@200 | hit@500 | hit@1000 | marginal@20 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `centroid.anchor_tracks.cf_bpr` | `cf_anchor_centroid` | 85 | 36 | 37 | 41 | 44 | 53 | 56 | 0 |
| `dense.qwen_0_6b.intent.metadata_qwen3_embedding_0_6b` | `qwen_intent` | 110 | 30 | 33 | 37 | 40 | 41 | 47 | 0 |
| `centroid.anchor_tracks.image_siglip2` | `image_anchor_centroid` | 85 | 30 | 34 | 37 | 39 | 41 | 45 | 0 |
| `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | `qwen_intent` | 110 | 27 | 34 | 42 | 48 | 59 | 70 | 0 |
| `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b` | `qwen_metadata` | 110 | 26 | 32 | 39 | 44 | 53 | 61 | 0 |
| `dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b` | `qwen_metadata` | 110 | 24 | 29 | 31 | 32 | 34 | 40 | 0 |
| `bm25` | `bm25` | 110 | 23 | 25 | 29 | 33 | 46 | 59 | 0 |
| `centroid.anchor_tracks.audio_laion_clap` | `audio_anchor_centroid` | 85 | 22 | 25 | 32 | 37 | 48 | 53 | 0 |
| `analysis.artist_tag_neighbor_popularity` | `artist_neighbor` | 110 | 21 | 27 | 29 | 33 | 43 | 52 | 0 |
| `analysis.query_text_tag_popularity` | `tag_scene` | 110 | 20 | 23 | 25 | 32 | 41 | 53 | 0 |
| `lookup.resolved_artist_discography` | `exact_lookup_discography` | 26 | 19 | 19 | 19 | 19 | 19 | 19 | 0 |
| `analysis.tag_popularity_alias` | `tag_scene` | 110 | 12 | 13 | 14 | 17 | 27 | 34 | 0 |
| `analysis.era_tag_popularity` | `era_popularity` | 110 | 11 | 12 | 15 | 18 | 28 | 32 | 0 |
| `lookup.era_popularity` | `era_popularity` | 46 | 10 | 12 | 14 | 16 | 16 | 16 | 0 |
| `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` | `qwen_attributes_enriched` | 93 | 3 | 4 | 8 | 14 | 18 | 31 | 0 |
| `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | `qwen_attributes` | 93 | 2 | 3 | 7 | 12 | 16 | 30 | 0 |
| `dense.clap_text.sonic_nl_enriched.audio_laion_clap` | `clap_sonic_nl_enriched` | 110 | 2 | 2 | 6 | 10 | 22 | 40 | 0 |
| `dense.clap_text.sonic.audio_laion_clap` | `clap_sonic` | 110 | 2 | 3 | 4 | 8 | 20 | 32 | 0 |

## Branch-Family Additive Recall

Rows are additive against current+targeted. For k>100, protected baseline only has top100 saved pools, so use the branch-only counts as the clean deep-pool signal.

| Family variant | all u@20 | valid u@20 | valid branch-only@100 | valid branch-only@1000 |
|---|---:|---:|---:|---:|
| `baseline_only` | 77/110 | 69/99 | 0/99 | 0/99 |
| `all_candidate_branches` | 77/110 | 69/99 | 76/99 | 97/99 |
| `all_branch_local_cleaned` | 84/110 | 76/99 | 86/99 | 97/99 |
| `family_exact_lookup` | 77/110 | 69/99 | 20/99 | 20/99 |
| `family_semantic_text` | 77/110 | 69/99 | 56/99 | 88/99 |
| `family_tag_scene` | 77/110 | 69/99 | 45/99 | 74/99 |
| `family_anchor_similarity` | 77/110 | 69/99 | 42/99 | 64/99 |
| `family_modality` | 77/110 | 69/99 | 46/99 | 76/99 |

## Reranker Pool Size Strategy

| Recipe | depth/branch | avg unique | p90 unique | all GT in pool | valid GT in pool | dominant raw-slot families |
|---|---:|---:|---:|---:|---:|---|
| `small_top50_per_branch` | 50 | 542.218 | 670 | 76/110 | 71/99 | qwen_metadata:11000, qwen_intent:11000, qwen_attributes:9300, qwen_attributes_enriched:9300 |
| `medium_top100_per_branch` | 100 | 1053.600 | 1302 | 81/110 | 76/99 | qwen_metadata:22000, qwen_intent:22000, qwen_attributes:18600, qwen_attributes_enriched:18600 |
| `large_top200_per_branch` | 200 | 2024.800 | 2515 | 96/110 | 88/99 | qwen_metadata:44000, qwen_intent:44000, qwen_attributes:37200, qwen_attributes_enriched:37200 |
| `very_large_top500_per_branch` | 500 | 4554.845 | 5622 | 104/110 | 95/99 | qwen_metadata:110000, qwen_intent:110000, qwen_attributes:93000, qwen_attributes_enriched:93000 |
| `raw_deep_top1000_per_branch` | 1000 | 8195.045 | 10143 | 106/110 | 97/99 | qwen_metadata:220000, qwen_intent:220000, qwen_attributes:186000, qwen_attributes_enriched:186000 |

Pool recommendation: use a large but capped reranker pool around top200 per active branch family as the first serious reranker recipe. It reaches 88/99 valid GT with about 2,025 unique candidates/turn on this pack. Top500/top1000 recover more GT (95/99 and 97/99 valid), but the pool sizes explode to roughly 4,555 and 8,195 unique candidates/turn. Keep exact/lookup generous, keep BM25/Qwen/tag/scene/anchor branches around top100-200, trigger lyric/visual/sonic branches only when state evidence asks for them, and use popularity/user-CF as score features unless a separate branch proves top20 lift.

## Saved-Pool Fusion Proxy

This is not production final ranking. It runs unweighted RRF over saved analysis pools so we can tell whether branch-local top-20 movement survives a simple fusion step. Treat it as a cheap gate before touching global RRF or running full devset.

| Proxy variant | all p@20 | all p@50 | all p@100 | valid p@20 | valid p@50 | valid p@100 | valid median rank |
|---|---:|---:|---:|---:|---:|---:|---:|
| `protected_trace_top100` | 43/110 | 54/110 | 58/110 | 36/99 | 47/99 | 50/99 | 10 |
| `protected_plus_all_on` | 50/110 | 54/110 | 61/110 | 43/99 | 46/99 | 53/99 | 5 |
| `protected_plus_catalog_features` | 42/110 | 53/110 | 62/110 | 36/99 | 45/99 | 54/99 | 7 |
| `protected_plus_anchor_cf` | 48/110 | 56/110 | 62/110 | 42/99 | 48/99 | 54/99 | 6 |
| `protected_plus_branch_local_hybrid` | 40/110 | 53/110 | 64/110 | 36/99 | 47/99 | 57/99 | 9 |
| `protected_plus_promoted_feature_family` | 39/110 | 53/110 | 65/110 | 37/99 | 47/99 | 58/99 | 8 |

Fusion-proxy read: if `protected_plus_promoted_feature_family` does not beat `protected_plus_all_on` at proxy@20, the +7 union@20 branch-local movement should be treated as candidate-quality evidence, not a production final-list fix. If it does beat it, the next step is a tiny real compiler final-list smoke with the same fixed features.

## Compiler-Aware Saved-Pool Scorer Proxy

This stronger proxy replaces plain RRF with state-conditioned branch-family weights, exact/album bonuses, hard drops for explicit rejected tracks, and cross-family agreement. It still uses only saved branch pools; no new retriever, prompt, or catalog metadata feature is introduced here.

| Proxy variant | depth | all p@20 | valid p@20 | current+proxy u@20 | valid current+proxy u@20 | current-miss rescues@20 | valid rescues@20 | valid p@100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `protected_plus_all_on_weighted` | 50 | 48/110 | 43/99 | 77/110 | 69/99 | 0 | 0 | 48/99 |
| `protected_plus_all_on_weighted` | 100 | 49/110 | 43/99 | 77/110 | 69/99 | 0 | 0 | 50/99 |
| `protected_plus_all_on_weighted` | 200 | 49/110 | 43/99 | 77/110 | 69/99 | 0 | 0 | 52/99 |
| `protected_plus_all_on_weighted` | 500 | 49/110 | 43/99 | 77/110 | 69/99 | 0 | 0 | 53/99 |

Weighted-scorer read: this does not rescue current union@20 misses. So the remaining focused gap is not solved by branch-family weights, intent routing, or a conservative RRF rewrite alone. The measurable branch-local +7 comes from candidate-level catalog/anchor features; those need a real capped candidate scorer or learned ranker over a top100-200 pool, while the two valid deep-pool absences are the only clear new-source candidates in this focused pack.

## GT Audit

| Label | Count |
|---|---:|
| `gt_conflicts_with_explicit_user_constraint` | 10 |
| `underspecified_next_play_behavior` | 1 |
| `valid_gt_branch_local_ranking_weak` | 16 |
| `valid_gt_retriever_source_weak` | 2 |
| `valid_gt_state_signal_compiler_not_consumed` | 12 |
| `valid_gt_state_supports_it` | 69 |

Noisy/contradictory GT is excluded only for the valid-GT-only view. All-110 metrics still include every turn. The conflict labels are mostly literal cases like 'not Drake', 'not Daft Punk', or 'not System Of A Down' where the GT artist violates an explicit user constraint. Because the conflict detector uses name matching, keep this as an audit label rather than a leaderboard exclusion until the 10 conflict rows are hand-verified.

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

- Projection-only state consumption: represented by `catalog_features` and `branch_local_hybrid`, which derive query terms from the existing frozen request summary/facts/lyrical theme and consume them as score features. This moved valid union@20 inside branch pools, but the saved-pool fusion proxy did not preserve the lift. Keep the features for a capped candidate ranker or learned scorer, not as a direct RRF branch duplication.
- Derived catalog features: normalized tag aliases, broad track text, release year compatibility, and popularity-if-requested are positive. Keep for full-devset smoke.
- Anchor-CF: positive top-20 lift. Keep as a branch-local feature when the state has liked/reference/accepted anchors.
- User-CF: 89/110 focused users have vectors and user-CF improves union@100, but not union@20. Defer to ranking work; do not call it a candidate-recall fix yet.
- Feature magnitudes are hand-set on the focused gap pack. The direction is credible because controls stay stable, but the exact +7 size is overfit-risk until the same frozen weights pass a held-out/full-devset smoke.
- Last-resort prompt ablation: not run. The frozen state contains enough usable signal to get +7 valid union@20 from non-prompt levers, so prompt iteration should be a separate later goal only for the remaining state/lyric failures.

## Remaining Gap

- Still-near @21-50: mostly branch-local scoring/query specificity. Examples include `5ee0dbbc...::t8` at rank 22, `3676005d...::t1` at rank 27, `10a15ba2...::t7` at rank 29, and `2bbc0a7e...::t1` at rank 30.
- Deeper/missing: stale or roleless anchors still blur novelty requests, and some lyric/theme requests need a stronger lyric-aware source or better query text.
- Some temporal residuals are state errors, not only scoring errors: if the frozen state emits a tight wrong release range, a non-prompt scorer can only soften the damage. It cannot recover the intended era semantics perfectly.
- Rejection controls stayed stable in this additive analysis: the P1 rejection guardrail valid slice remains 5/5 union@20.

## Gap Reason By Slice

| Slice | n | valid n | current u@20 | promoted u@20 | dominant reasons |
|---|---:|---:|---:|---:|---|
| `P0_new_artist_union20_gap_failure` | 10 | 10 | 4 | 4 | already_in_current_union20:4, deep_101_500_branch_query_or_noise:3, near_miss_21_50_branch_local_scoring:2, near_miss_51_100_branch_local_scoring:1 |
| `P0_novelty_prior_anchor_failure` | 10 | 9 | 4 | 5 | already_in_current_union20:4, deep_101_500_branch_query_or_noise:2, near_miss_21_50_branch_local_scoring:1, gt_conflicts_with_explicit_user_constraint:1 |
| `P0_roleless_stale_entity_failure` | 10 | 9 | 1 | 3 | deep_101_500_branch_query_or_noise:3, rescued_by_branch_local_scoring:2, near_miss_51_100_branch_local_scoring:1, already_in_current_union20:1 |
| `P1_positive_tag_retrieval_gap_failure` | 10 | 10 | 4 | 7 | already_in_current_union20:4, rescued_by_branch_local_scoring:3, gt_absent_from_all_saved_deep_pools:1, deep_101_500_branch_query_or_noise:1 |
| `P1_rejection_guardrail_failure` | 10 | 5 | 10 | 10 | already_in_current_union20:5, gt_conflicts_with_explicit_user_constraint:5 |
| `P1_temporal_constraint_failure` | 10 | 9 | 4 | 5 | already_in_current_union20:4, deep_101_500_branch_query_or_noise:3, gt_conflicts_with_explicit_user_constraint:1, rescued_by_branch_local_scoring:1 |
| `POS_clean_final_hit_control` | 10 | 10 | 10 | 10 | already_in_current_union20:10 |
| `POS_exact_entity_success_control` | 10 | 10 | 10 | 10 | already_in_current_union20:10 |
| `lyric_or_theme_gap` | 18 | 16 | 10 | 11 | already_in_current_union20:10, deep_101_500_branch_query_or_noise:3, near_miss_21_50_branch_local_scoring:2, underspecified_next_play_behavior:1 |
| `visual_or_cover_art_gap` | 11 | 6 | 7 | 9 | gt_conflicts_with_explicit_user_constraint:5, rescued_by_branch_local_scoring:2, already_in_current_union20:2, deep_101_500_branch_query_or_noise:1 |

## Top-20 Noise Examples

These are valid/current misses where raw branch top slots are occupied by plausible but wrong candidates. Use them for branch-local scoring and query specificity debugging, not prompt tuning.

- `0b9d547f-e748-464a-90e2-2199149f915c::t6` (P0_roleless_stale_entity_failure) GT=Give It To Me Baby by Rick James; top noise: bm25#1=Evelyn Thomas - High Energy; bm25#2=Nightmares On Wax - 70s 80s; bm25#3=Michael Jackson - Burn This Disco Out
- `e66c6a88-88ba-4117-9114-363bfa96294a::t7` (P0_roleless_stale_entity_failure) GT=Test Drive by John Powell; top noise: bm25#1=blink-182 - Anthem Part Two; bm25#2=Two Steps from Hell - Heart of Courage; bm25#3=Steve Jablonsky - Downtown Battle
- `41367174-552b-4117-9caa-d0ba1b307d37::t2` (P0_roleless_stale_entity_failure) GT=Mercy by Muse; top noise: bm25#1=Madonna - This Used To Be My Playground; bm25#2=Foo Fighters - Something from Nothing; bm25#3=Destiny's Child - Emotion
- `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7` (P0_roleless_stale_entity_failure) GT=I Can't Go to Sleep by Wu-Tang Clan; top noise: bm25#1=Kendrick Lamar - Illuminate (feat. Kendrick Lamar); bm25#2=Jay Rock - Pay for It (feat. Kendrick Lamar & Chantal); bm25#3=Jay Rock - Hood Gone Love It (feat. Kendrick Lamar)
- `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` (P0_roleless_stale_entity_failure) GT=The Carbon Stampede by Cattle Decapitation; top noise: bm25#1=Cephalic Carnage - Dying Will Be the Death of Me; bm25#2=Static-X - Push It; bm25#3=The Faceless - Akeldama

## Next Tests

1. Do not promote the feature family directly into production fusion. First build a tiny final-list smoke that scores a capped top200 candidate pool once per turn, instead of duplicating every branch into RRF. Report `final@20`, nDCG@20 if available, and union diagnostics before any full-devset run.
2. Run a held-out focused/devset slice with the same fixed weights. Do not tune weights on the focused-110 again; if fixed weights are unstable, learn or parameterize them before promoting.
3. Hand-audit the 10 `gt_conflicts_with_explicit_user_constraint` rows and keep all-110 metrics side by side with valid-only metrics.
4. Separately replay the role-typed state branch against the remaining stale-anchor and temporal residuals. Branch-local scoring is complementary; it is not a substitute for extracting seed/satisfied/history/contrast/rejected roles or soft-era versus hard-date intent correctly.
5. For lyric/theme cases, validate whether the existing lyric branch can move known @21-100 examples before adding a new retriever. If it cannot express the target even with good query text, then scope a lyric/theme source goal.

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

Keep only levers with positive valid-GT union@20 lift for the next full-devset smoke. If a lever only improves union@50, treat it as evidence for branch-local ranking or a lightweight ranker, not as candidate recall solved. The saved-pool fusion proxies now say these features should feed a capped candidate-level scorer/ranker rather than direct RRF branch duplication or broad branch-family weighting. Only the small absent-from-deep-pools slice should trigger a new-source goal.

Need-new-source note: only 2 valid GTs are absent from all saved deep pools in this run. Most remaining valid failures are not fundamentally absent; they are near/deep ranking, query specificity, or state-role consumption problems.
