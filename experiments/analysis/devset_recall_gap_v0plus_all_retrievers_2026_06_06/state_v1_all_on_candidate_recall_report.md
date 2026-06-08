# State V1 All-On Candidate Recall Report

Focused 110-pack diagnostic. V1 extraction and V1-to-V0 projection were frozen. This is candidate recall only; no final ranker, RRF, response generation, full devset, or leaderboard claim.

## Bottom Line

- The expanded v3 all-on branch matrix did not improve the current focused baseline. Current remains 75/110 union@20, 87/110 union@50, and 91/110 union@100 after adding v3 branches.
- Relative to the protected saved-trace baseline alone, v3 reaches 74/110 union@20, 85/110 union@50, and 89/110 union@100, but that is still below the current 75/87/91 OR baseline.
- The added raw-attribute and lyric dense branches were valid, but not useful on this pack. The lyric branch hit only 2/110 and had zero marginal or unique rescues.
- The remaining problem is split: 16 current misses are already somewhere in the current top100 candidate tail, while 19 are absent from current union@100 and need better source/query design rather than more branch gating.

## Headline Counts

| System | union@20 | union@50 | union@100 | Read |
|---|---:|---:|---:|---|
| Protected saved-trace baseline | 60/110 | 60/110 | 60/110 | frozen trace pools only |
| Existing modal+synthetic OR | 71/110 | 82/110 | 88/110 | prior diagnostic OR before query-text branch |
| Current focused baseline | 75/110 | 87/110 | 91/110 | existing OR plus query-text tag popularity |
| v3 all-on branch-only | 64/110 | 76/110 | 81/110 | forced new/existing branch pools without protected pools |
| v3 all-on + protected baseline | 74/110 | 85/110 | 89/110 | protected pools plus v3 all-on |
| Current + v3 all-on | 75/110 | 87/110 | 91/110 | no new current-baseline rescues |

## Branch Coverage

The v3 forced pass saved 21 pools per turn at top1000: BM25, Qwen 0.6B metadata/intent/raw attributes/enriched attributes/lyrics, Qwen 8B metadata/intent/raw attributes/enriched attributes, CLAP sonic/sonic_nl/sonic_nl_enriched, centroid audio/image/CF, era popularity, tag-popularity aliases, era tag-popularity, same-album fanout, artist-neighbor popularity, and query-text tag popularity.

| Branch | hit@20 | unique rescue@20 vs protected | unique rescue@100 vs protected | Decision |
|---|---:|---:|---:|---|
| `analysis.query_text_tag_popularity` | 20 | 4 | 3 | keep_current: already part of the current 75/87/91 baseline; strongest unique protected-baseline rescuer |
| `analysis.artist_tag_neighbor_popularity` | 21 | 2 | 2 | diagnostic_only: unique against protected baseline, but duplicated by existing current OR baseline |
| `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 27 | 0 | 1 | diagnostic_only: unique against protected baseline, but duplicated by existing current OR baseline |
| `centroid.anchor_tracks.cf_bpr` | 36 | 1 | 1 | diagnostic_only: unique against protected baseline, but duplicated by existing current OR baseline |
| `analysis.tag_popularity_alias` | 12 | 1 | 1 | diagnostic_only: unique against protected baseline, but duplicated by existing current OR baseline |
| `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b` | 26 | 0 | 0 | defer: no marginal lift over the 75/87/91 current baseline |
| `centroid.anchor_tracks.audio_laion_clap` | 22 | 1 | 0 | diagnostic_only: unique against protected baseline, but duplicated by existing current OR baseline |
| `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` | 3 | 0 | 0 | defer: no marginal lift over the 75/87/91 current baseline |
| `dense.clap_text.sonic_nl_enriched.audio_laion_clap` | 2 | 1 | 0 | diagnostic_only: unique against protected baseline, but duplicated by existing current OR baseline |
| `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 2 | 0 | 0 | defer: no marginal lift over the 75/87/91 current baseline |
| `dense.clap_text.sonic_nl.audio_laion_clap` | 1 | 0 | 0 | defer: no marginal lift over the 75/87/91 current baseline |
| `centroid.anchor_tracks.image_siglip2` | 30 | 0 | 0 | defer: no marginal lift over the 75/87/91 current baseline |
| `analysis.era_tag_popularity` | 11 | 0 | 0 | defer: no marginal lift over the 75/87/91 current baseline |
| `dense.clap_text.sonic.audio_laion_clap` | 2 | 1 | 0 | diagnostic_only: unique against protected baseline, but duplicated by existing current OR baseline |

Notable weak branches:

| Branch | hit@20 | hit@100 | Decision |
|---|---:|---:|---|
| `dense.qwen_0_6b.lyric.lyrics_qwen3_embedding_0_6b` | 2 | 2 | reject for this pack: zero protected/current marginal rescues |
| `analysis.same_album_fanout` | 1 | 1 | reject for this pack: same-album controls are already covered by protected pools |
| `dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b` | 1 | 4 | diagnostic only: raw attributes add no current-baseline rescues |

## Minimal Subset

Greedy minimal subset against the protected baseline selects 10 branches and reaches 71/110 union@20, 83/110 union@50, and 89/110 union@100. It matches all-on at union@100 but is still below the current focused baseline at union@20/50.

1. `analysis.query_text_tag_popularity` -> 65/110 @20, 66/110 @50, 67/110 @100
2. `analysis.artist_tag_neighbor_popularity` -> 67/110 @20, 72/110 @50, 72/110 @100
3. `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b` -> 67/110 @20, 73/110 @50, 76/110 @100
4. `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` -> 67/110 @20, 74/110 @50, 80/110 @100
5. `centroid.anchor_tracks.cf_bpr` -> 69/110 @20, 76/110 @50, 83/110 @100
6. `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b` -> 69/110 @20, 78/110 @50, 85/110 @100
7. `dense.clap_text.sonic_nl_enriched.audio_laion_clap` -> 70/110 @20, 79/110 @50, 86/110 @100
8. `analysis.tag_popularity_alias` -> 71/110 @20, 80/110 @50, 87/110 @100
9. `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` -> 71/110 @20, 82/110 @50, 88/110 @100
10. `dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b` -> 71/110 @20, 83/110 @50, 89/110 @100

## Top-20 Ordering Headroom

Current misses at union@20: 35/110. Of those, current sources already have 12 in 21-50 and 4 in 51-100; 19 are absent from current union@100.

The v3 all-on branch ranks for current @20 misses are: {'rank_51_100': 4, 'rank_21_50': 10, 'rank_101_1000': 18, 'absent_top1000': 3}. This supports a later top-20 ordering/survivor-slot goal for the 21-100 tail, but it does not justify adding v3 branches as a source-recall fix.

| Sample | Pack | GT | v3 best branch | Rank | Current tail |
|---|---|---|---|---:|---|
| `5ee0dbbc-c1d1-4bed-ba09-7dafeec198bc::t8` | `P0_new_artist_union20_gap_failure` | You Reposted in the Wrong Neighborhood I Glue70 Mashup / Shokk | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 22 | current_rank_21_50 |
| `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7` | `P0_roleless_stale_entity_failure` | I Can't Go to Sleep / Wu-Tang Clan | `dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b` | 27 | current_rank_21_50 |
| `3676005d-5b7c-4c48-9b73-3e10dd509c07::t1` | `P1_temporal_constraint_failure` | Breath and Life / Audiomachine | `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 27 | current_rank_21_50 |
| `1c567917-f931-4609-9695-a9c0f8e39f3d::t2` | `P1_positive_tag_retrieval_gap_failure` | Arregaçada / U Can't Touch This / Banda Uó | `dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b` | 35 | current_rank_21_50 |
| `464477e4-f186-47fb-8cb0-55691c8b8f57::t6` | `P1_positive_tag_retrieval_gap_failure` | Where Eagles Dare / Glenn Danzig, Misfits | `centroid.anchor_tracks.image_siglip2` | 35 | current_rank_21_50 |
| `e66c6a88-88ba-4117-9114-363bfa96294a::t7` | `P0_roleless_stale_entity_failure` | Test Drive / John Powell | `centroid.anchor_tracks.audio_laion_clap` | 36 | current_rank_21_50 |
| `dd686049-59ba-439b-8c51-949a0876e1b3::t1` | `P1_positive_tag_retrieval_gap_failure` | Vengeance (The Return of the Night Driving Avenger) [Bonus Track] / Perturbator | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 42 | current_rank_21_50 |
| `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6` | `P1_temporal_constraint_failure` | Thriller / Fall Out Boy | `analysis.query_text_tag_popularity` | 42 | current_rank_21_50 |
| `ba68a3cc-5278-4680-917a-4ca66d33ef31::t5` | `P0_new_artist_union20_gap_failure` | Buttons / The Pussycat Dolls | `analysis.artist_tag_neighbor_popularity` | 44 | current_rank_21_50 |
| `c7a965c3-cd7f-46f6-b166-9dce9a800e0a::t3` | `P0_novelty_prior_anchor_failure` | S&M / Rihanna | `analysis.artist_tag_neighbor_popularity` | 49 | current_rank_21_50 |
| `0b9d547f-e748-464a-90e2-2199149f915c::t6` | `P0_roleless_stale_entity_failure` | Give It To Me Baby / Rick James | `analysis.era_tag_popularity` | 51 | current_rank_21_50 |
| `5a0dfe9d-ec8a-4449-97df-35535cbf162f::t1` | `P1_positive_tag_retrieval_gap_failure` | A New World / Harry Gregson-Williams | `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b` | 60 | current_rank_51_100 |
| `5861afef-85c0-4163-b8b9-5a11e308f352::t4` | `P0_new_artist_union20_gap_failure` | Carmesí / Vicente Garcia | `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 65 | current_rank_51_100 |
| `daeef24e-b041-4140-9101-882820c63408::t7` | `P0_novelty_prior_anchor_failure` | The Analog Kid / Rush | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 72 | current_rank_21_50 |

## Source Gaps

Current misses at union@100: 19/110. These are not solved by forcing the existing branch families on; v3 adds zero new union@100 rescues over current.

| Sample | Pack | GT | v3 best branch | Rank | Gap type |
|---|---|---|---|---:|---|
| `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3` | `P0_novelty_prior_anchor_failure` | Gib ihn einfach (Dies das 2) / Ghanaian Stallion | `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 101 | deep_candidate_ranking_gap |
| `8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7` | `P0_novelty_prior_anchor_failure` | Transcentience / Animals As Leaders | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 102 | deep_candidate_ranking_gap |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | `centroid.anchor_tracks.cf_bpr` | 137 | deep_candidate_ranking_gap |
| `67b9ba8a-382f-4b70-af76-576848d8cf67::t8` | `P1_temporal_constraint_failure` | Gangsta Gangsta / N.W.A. | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 142 | deep_candidate_ranking_gap |
| `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` | `P0_roleless_stale_entity_failure` | Move Along / The All-American Rejects | `analysis.tag_popularity_alias` | 170 | deep_candidate_ranking_gap |
| `9468e467-d396-461b-be29-b30b6cf87c35::t5` | `P1_temporal_constraint_failure` | Midnight / A Tribe Called Quest | `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b` | 179 | deep_candidate_ranking_gap |
| `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` | `P0_new_artist_union20_gap_failure` | Two To Make It Right / Seduction | `centroid.anchor_tracks.audio_laion_clap` | 183 | deep_candidate_ranking_gap |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | `analysis.query_text_tag_popularity` | 189 | deep_candidate_ranking_gap |
| `c4c0c288-dbcd-4970-ad52-901aafe91b88::t4` | `P1_temporal_constraint_failure` | I Juswanna Chill / Large Professor | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 228 | deep_candidate_ranking_gap |
| `41367174-552b-4117-9caa-d0ba1b307d37::t2` | `P0_roleless_stale_entity_failure` | Mercy / Muse | `analysis.era_tag_popularity` | 239 | deep_candidate_ranking_gap |
| `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` | `P0_roleless_stale_entity_failure` | In the Shadows / The Rasmus | `centroid.anchor_tracks.audio_laion_clap` | 253 | deep_candidate_ranking_gap |
| `907921a3-d08f-4ba1-8cce-0e760a9e7044::t7` | `P0_new_artist_union20_gap_failure` | Sunrise - Slow Hands Remix / Kasper Bjørke | `centroid.anchor_tracks.cf_bpr` | 296 | deep_candidate_ranking_gap |
| `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` | `P0_new_artist_union20_gap_failure` | Hong Kong 2046 / Hong Kong Express | `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b` | 332 | deep_candidate_ranking_gap |
| `324ddfb5-8a18-4729-9acb-c851907a297c::t3` | `P0_new_artist_union20_gap_failure` | Acknowledge / Masta Ace | `dense.clap_text.sonic_nl.audio_laion_clap` | 333 | deep_candidate_ranking_gap |
| `e978bb5b-26af-4c7d-b720-b9210bdddf25::t8` | `P1_temporal_constraint_failure` | Dear Yvette / Jane Doe, Masta Ace | `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b` | 447 | deep_candidate_ranking_gap |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | `analysis.query_text_tag_popularity` | 547 | deep_candidate_ranking_gap |
| `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` | `P0_roleless_stale_entity_failure` | Shaft / Kashmere Stage Band | `` |  | source_absent_top1000 |
| `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` | `P0_roleless_stale_entity_failure` | I Believe in a Thing Called Love / The Darkness | `` |  | source_absent_top1000 |
| `ad5348a7-d3bc-4882-bfca-54aa655eac96::t5` | `P1_positive_tag_retrieval_gap_failure` | Glitter / Tyler, The Creator | `` |  | source_absent_top1000 |

## Per-Class Read

| Pack | n | current @20/@50/@100 | v3+protected @20/@50/@100 | current+v3 @20/@50/@100 | Read |
|---|---:|---:|---:|---:|---|
| `P0_good_state_ranker_near_miss_failure` | 10 | 10/10/10 | 10/10/10 | 10/10/10 | no current lift |
| `P0_named_artist_ranker_failure` | 10 | 10/10/10 | 10/10/10 | 10/10/10 | no current lift |
| `P0_new_artist_union20_gap_failure` | 10 | 3/5/6 | 3/5/6 | 3/5/6 | no current lift |
| `P0_novelty_prior_anchor_failure` | 10 | 4/6/6 | 4/5/6 | 4/6/6 | no current lift |
| `P0_roleless_stale_entity_failure` | 10 | 1/4/4 | 1/3/4 | 1/4/4 | no current lift |
| `P0_same_album_ranker_failure` | 10 | 10/10/10 | 10/10/10 | 10/10/10 | no current lift |
| `P1_positive_tag_retrieval_gap_failure` | 10 | 3/6/9 | 2/6/7 | 3/6/9 | no current lift |
| `P1_rejection_guardrail_failure` | 10 | 10/10/10 | 10/10/10 | 10/10/10 | no current lift |
| `P1_temporal_constraint_failure` | 10 | 4/6/6 | 4/6/6 | 4/6/6 | no current lift |
| `POS_clean_final_hit_control` | 10 | 10/10/10 | 10/10/10 | 10/10/10 | no current lift |
| `POS_exact_entity_success_control` | 10 | 10/10/10 | 10/10/10 | 10/10/10 | no current lift |

## Recommendation

- Keep the query-text tag-popularity branch as the current focused-pack candidate-recall lift; it is already reflected in 75/87/91.
- Do not promote the added lyric/raw-attribute v3 branches for this pack. They are valid diagnostics, but they add no current-baseline rescues.
- Defer production gating decisions for artist-neighbor, centroid CF/audio/image, Qwen 8B metadata/intent, and tag alias branches. They rescue against the protected baseline, but current OR already covers their rescues.
- Next candidate-recall work should be source/query design for the 19 current union@100 misses, especially stale-roleless, novelty/new-artist, temporal hip-hop/era, and positive-tag scene cases.
- Next top-20 work should be a separate ordering/survivor-slot goal for the 16 current top100 tail cases. That is not an RRF/global-ranker change yet; it can be branch-local and measured on the same pack.

## Artifacts

- `state_v1_all_on_branch_pools.json`: saved v3 branch pools at top1000.
- `state_v1_all_on_branch_ledger.json`: protected-baseline branch attribution.
- `state_v1_minimal_subset_summary.json`: greedy protected-baseline subset.
- `state_v1_top20_ordering_summary.json`: current-baseline tail/source-gap split.
- `state_v1_all_on_over_current_baseline_summary.json`: exact current-baseline comparison.
