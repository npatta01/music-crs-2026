# State V1 Retriever Matrix

Focused candidate-generation matrix over saved V1 extraction states.
The main gate is branch union@20/50; RRF/final ranking is reported separately.

## Summary

| Variant | n | final@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_trace_baseline` | 19 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |  |  |
| `all_candidate_plus_targeted_v4` | 19 |  |  | 0.053 | 0.105 | 0.105 |  |  |  |

## Per-Class Summary

| Pack | n | baseline u@20 | baseline u@50 | best single | single u@20 | single u@50 | combined | combined u@20 | combined u@50 |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|
| P0_new_artist_union20_gap_failure | 4 | 0.000 | 0.000 | `` |  |  | `all_candidate_plus_targeted_v4` | 0.250 | 0.250 |
| P0_novelty_prior_anchor_failure | 4 | 0.000 | 0.000 | `` |  |  | `all_candidate_plus_targeted_v4` | 0.000 | 0.000 |
| P0_roleless_stale_entity_failure | 6 | 0.000 | 0.000 | `` |  |  | `all_candidate_plus_targeted_v4` | 0.000 | 0.000 |
| P1_positive_tag_retrieval_gap_failure | 1 | 0.000 | 0.000 | `` |  |  | `all_candidate_plus_targeted_v4` | 0.000 | 0.000 |
| P1_temporal_constraint_failure | 4 | 0.000 | 0.000 | `` |  |  | `all_candidate_plus_targeted_v4` | 0.000 | 0.250 |

## Examples

### `all_candidate_plus_targeted_v4` Rescued union@20

- `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` (P0_new_artist_union20_gap_failure): GT=Two To Make It Right by Seduction; best_branch=`analysis.scene_era_tag_popularity_v2` rank=6; why=rescued_at_union20

### `all_candidate_plus_targeted_v4` Still Missed union@20

- `41367174-552b-4117-9caa-d0ba1b307d37::t2` (P0_roleless_stale_entity_failure): GT=Mercy by Muse; best_branch=`analysis.era_tag_popularity` rank=239; why=deep_candidate_ranking_gap; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` (P0_roleless_stale_entity_failure): GT=The Carbon Stampede by Cattle Decapitation; best_branch=`centroid.anchor_tracks.cf_bpr` rank=137; why=deep_candidate_ranking_gap; change=Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` (P0_roleless_stale_entity_failure): GT=Shaft by Kashmere Stage Band; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` (P0_roleless_stale_entity_failure): GT=In the Shadows by The Rasmus; best_branch=`centroid.anchor_tracks.audio_laion_clap` rank=253; why=deep_candidate_ranking_gap; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` (P0_roleless_stale_entity_failure): GT=I Believe in a Thing Called Love by The Darkness; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` (P0_roleless_stale_entity_failure): GT=Move Along by The All-American Rejects; best_branch=`analysis.tag_popularity_alias` rank=170; why=deep_candidate_ranking_gap; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- `88beb200-0334-4aba-be15-8e1303725766::t6` (P0_novelty_prior_anchor_failure): GT=Used To by Lil Wayne, Drake; best_branch=`analysis.query_text_tag_popularity` rank=189; why=deep_candidate_ranking_gap; change=Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- `8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7` (P0_novelty_prior_anchor_failure): GT=Transcentience by Animals As Leaders; best_branch=`dense.qwen_8b.intent.metadata_qwen3_embedding_8b` rank=102; why=deep_candidate_ranking_gap; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` (P0_novelty_prior_anchor_failure): GT=God Hates a Coward by Tomahawk; best_branch=`analysis.query_text_tag_popularity` rank=116; why=deep_candidate_ranking_gap; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3` (P0_novelty_prior_anchor_failure): GT=Gib ihn einfach (Dies das 2) by Ghanaian Stallion; best_branch=`dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` rank=101; why=deep_candidate_ranking_gap; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` (P0_new_artist_union20_gap_failure): GT=Hong Kong 2046 by Hong Kong Express; best_branch=`dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b` rank=341; why=deep_candidate_ranking_gap; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `907921a3-d08f-4ba1-8cce-0e760a9e7044::t7` (P0_new_artist_union20_gap_failure): GT=Sunrise - Slow Hands Remix by Kasper Bjørke; best_branch=`centroid.anchor_tracks.cf_bpr` rank=296; why=deep_candidate_ranking_gap; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.


## Per-Sample Rows

| Sample | Pack | GT | Variant | final rank | best branch rank | best branch | union@20 | union@50 | union@100 |
|---|---|---|---|---:|---:|---|---:|---:|---:|
| `41367174-552b-4117-9caa-d0ba1b307d37::t2` | `P0_roleless_stale_entity_failure` | Mercy / Muse | `all_candidate_plus_targeted_v4` |  | 239 | `analysis.era_tag_popularity` | 0 | 0 | 0 |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | `all_candidate_plus_targeted_v4` | 296 | 137 | `centroid.anchor_tracks.cf_bpr` | 0 | 0 | 0 |
| `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` | `P0_roleless_stale_entity_failure` | Shaft / Kashmere Stage Band | `all_candidate_plus_targeted_v4` |  |  | `` | 0 | 0 | 0 |
| `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` | `P0_roleless_stale_entity_failure` | In the Shadows / The Rasmus | `all_candidate_plus_targeted_v4` |  | 253 | `centroid.anchor_tracks.audio_laion_clap` | 0 | 0 | 0 |
| `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` | `P0_roleless_stale_entity_failure` | I Believe in a Thing Called Love / The Darkness | `all_candidate_plus_targeted_v4` |  |  | `` | 0 | 0 | 0 |
| `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` | `P0_roleless_stale_entity_failure` | Move Along / The All-American Rejects | `all_candidate_plus_targeted_v4` |  | 170 | `analysis.tag_popularity_alias` | 0 | 0 | 0 |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | `all_candidate_plus_targeted_v4` |  | 189 | `analysis.query_text_tag_popularity` | 0 | 0 | 0 |
| `8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7` | `P0_novelty_prior_anchor_failure` | Transcentience / Animals As Leaders | `all_candidate_plus_targeted_v4` |  | 102 | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 0 | 0 | 0 |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | `all_candidate_plus_targeted_v4` |  | 116 | `analysis.query_text_tag_popularity` | 0 | 0 | 0 |
| `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3` | `P0_novelty_prior_anchor_failure` | Gib ihn einfach (Dies das 2) / Ghanaian Stallion | `all_candidate_plus_targeted_v4` | 902 | 101 | `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 0 | 0 | 0 |
| `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` | `P0_new_artist_union20_gap_failure` | Hong Kong 2046 / Hong Kong Express | `all_candidate_plus_targeted_v4` |  | 341 | `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b` | 0 | 0 | 0 |
| `907921a3-d08f-4ba1-8cce-0e760a9e7044::t7` | `P0_new_artist_union20_gap_failure` | Sunrise - Slow Hands Remix / Kasper Bjørke | `all_candidate_plus_targeted_v4` |  | 296 | `centroid.anchor_tracks.cf_bpr` | 0 | 0 | 0 |
| `324ddfb5-8a18-4729-9acb-c851907a297c::t3` | `P0_new_artist_union20_gap_failure` | Acknowledge / Masta Ace | `all_candidate_plus_targeted_v4` | 403 | 149 | `analysis.artist_neighbor_scene_v2` | 0 | 0 | 0 |
| `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` | `P0_new_artist_union20_gap_failure` | Two To Make It Right / Seduction | `all_candidate_plus_targeted_v4` | 410 | 6 | `analysis.scene_era_tag_popularity_v2` | 1 | 1 | 1 |
| `67b9ba8a-382f-4b70-af76-576848d8cf67::t8` | `P1_temporal_constraint_failure` | Gangsta Gangsta / N.W.A. | `all_candidate_plus_targeted_v4` |  | 21 | `analysis.artist_neighbor_scene_v2` | 0 | 1 | 1 |
| `9468e467-d396-461b-be29-b30b6cf87c35::t5` | `P1_temporal_constraint_failure` | Midnight / A Tribe Called Quest | `all_candidate_plus_targeted_v4` |  | 179 | `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b` | 0 | 0 | 0 |
| `e978bb5b-26af-4c7d-b720-b9210bdddf25::t8` | `P1_temporal_constraint_failure` | Dear Yvette / Jane Doe, Masta Ace | `all_candidate_plus_targeted_v4` |  | 447 | `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b` | 0 | 0 | 0 |
| `c4c0c288-dbcd-4970-ad52-901aafe91b88::t4` | `P1_temporal_constraint_failure` | I Juswanna Chill / Large Professor | `all_candidate_plus_targeted_v4` | 826 | 228 | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 0 | 0 | 0 |
| `ad5348a7-d3bc-4882-bfca-54aa655eac96::t5` | `P1_positive_tag_retrieval_gap_failure` | Glitter / Tyler, The Creator | `all_candidate_plus_targeted_v4` |  |  | `` | 0 | 0 | 0 |
