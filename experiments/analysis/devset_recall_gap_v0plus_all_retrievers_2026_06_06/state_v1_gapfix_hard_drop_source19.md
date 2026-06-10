# State V1 Retriever Matrix

Focused candidate-generation matrix over saved V1 extraction states.
The main gate is branch union@20/50; RRF/final ranking is reported separately.

## Summary

| Variant | n | final@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_trace_baseline` | 19 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |  |  |
| `all_candidate_plus_targeted_v4_hard_drop` | 19 |  |  | 0.211 | 0.316 | 0.526 |  |  |  |

## Per-Class Summary

| Pack | n | baseline u@20 | baseline u@50 | best single | single u@20 | single u@50 | combined | combined u@20 | combined u@50 |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|
| P0_new_artist_union20_gap_failure | 4 | 0.000 | 0.000 | `all_candidate_plus_targeted_v4_hard_drop` | 0.250 | 0.250 | `` |  |  |
| P0_novelty_prior_anchor_failure | 4 | 0.000 | 0.000 | `all_candidate_plus_targeted_v4_hard_drop` | 0.500 | 0.500 | `` |  |  |
| P0_roleless_stale_entity_failure | 6 | 0.000 | 0.000 | `all_candidate_plus_targeted_v4_hard_drop` | 0.000 | 0.333 | `` |  |  |
| P1_positive_tag_retrieval_gap_failure | 1 | 0.000 | 0.000 | `all_candidate_plus_targeted_v4_hard_drop` | 0.000 | 0.000 | `` |  |  |
| P1_temporal_constraint_failure | 4 | 0.000 | 0.000 | `all_candidate_plus_targeted_v4_hard_drop` | 0.250 | 0.250 | `` |  |  |

## Examples

### `all_candidate_plus_targeted_v4_hard_drop` Rescued union@20

- `88beb200-0334-4aba-be15-8e1303725766::t6` (P0_novelty_prior_anchor_failure): GT=Used To by Lil Wayne, Drake; best_branch=`analysis.same_album_fanout` rank=14; why=rescued_at_union20
- `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` (P0_novelty_prior_anchor_failure): GT=God Hates a Coward by Tomahawk; best_branch=`dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` rank=1; why=rescued_at_union20
- `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` (P0_new_artist_union20_gap_failure): GT=Two To Make It Right by Seduction; best_branch=`analysis.scene_era_tag_popularity_v2` rank=6; why=rescued_at_union20
- `67b9ba8a-382f-4b70-af76-576848d8cf67::t8` (P1_temporal_constraint_failure): GT=Gangsta Gangsta by N.W.A.; best_branch=`analysis.artist_neighbor_scene_v2` rank=20; why=rescued_at_union20

### `all_candidate_plus_targeted_v4_hard_drop` Still Missed union@20

- `41367174-552b-4117-9caa-d0ba1b307d37::t2` (P0_roleless_stale_entity_failure): GT=Mercy by Muse; best_branch=`analysis.era_tag_popularity` rank=60; why=branch_local_ranking_gap_51_100; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` (P0_roleless_stale_entity_failure): GT=The Carbon Stampede by Cattle Decapitation; best_branch=`centroid.anchor_tracks.cf_bpr` rank=67; why=branch_local_ranking_gap_51_100; change=Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` (P0_roleless_stale_entity_failure): GT=Shaft by Kashmere Stage Band; best_branch=`dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` rank=50; why=branch_local_ranking_gap_21_50; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` (P0_roleless_stale_entity_failure): GT=In the Shadows by The Rasmus; best_branch=`analysis.artist_tag_neighbor_popularity` rank=265; why=deep_candidate_ranking_gap; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` (P0_roleless_stale_entity_failure): GT=I Believe in a Thing Called Love by The Darkness; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` (P0_roleless_stale_entity_failure): GT=Move Along by The All-American Rejects; best_branch=`analysis.artist_neighbor_scene_v2` rank=39; why=branch_local_ranking_gap_21_50; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- `8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7` (P0_novelty_prior_anchor_failure): GT=Transcentience by Animals As Leaders; best_branch=`dense.qwen_8b.intent.metadata_qwen3_embedding_8b` rank=100; why=branch_local_ranking_gap_51_100; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3` (P0_novelty_prior_anchor_failure): GT=Gib ihn einfach (Dies das 2) by Ghanaian Stallion; best_branch=`dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` rank=101; why=deep_candidate_ranking_gap; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` (P0_new_artist_union20_gap_failure): GT=Hong Kong 2046 by Hong Kong Express; best_branch=`dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b` rank=381; why=deep_candidate_ranking_gap; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `907921a3-d08f-4ba1-8cce-0e760a9e7044::t7` (P0_new_artist_union20_gap_failure): GT=Sunrise - Slow Hands Remix by Kasper Bjørke; best_branch=`centroid.anchor_tracks.cf_bpr` rank=280; why=deep_candidate_ranking_gap; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `324ddfb5-8a18-4729-9acb-c851907a297c::t3` (P0_new_artist_union20_gap_failure): GT=Acknowledge by Masta Ace; best_branch=`analysis.artist_neighbor_scene_v2` rank=148; why=deep_candidate_ranking_gap; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- `9468e467-d396-461b-be29-b30b6cf87c35::t5` (P1_temporal_constraint_failure): GT=Midnight by A Tribe Called Quest; best_branch=`dense.qwen_8b.metadata.metadata_qwen3_embedding_8b` rank=177; why=deep_candidate_ranking_gap; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.


## Per-Sample Rows

| Sample | Pack | GT | Variant | final rank | best branch rank | best branch | union@20 | union@50 | union@100 |
|---|---|---|---|---:|---:|---|---:|---:|---:|
| `41367174-552b-4117-9caa-d0ba1b307d37::t2` | `P0_roleless_stale_entity_failure` | Mercy / Muse | `all_candidate_plus_targeted_v4_hard_drop` |  | 60 | `analysis.era_tag_popularity` | 0 | 0 | 1 |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | `all_candidate_plus_targeted_v4_hard_drop` | 242 | 67 | `centroid.anchor_tracks.cf_bpr` | 0 | 0 | 1 |
| `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` | `P0_roleless_stale_entity_failure` | Shaft / Kashmere Stage Band | `all_candidate_plus_targeted_v4_hard_drop` |  | 50 | `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` | 0 | 1 | 1 |
| `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` | `P0_roleless_stale_entity_failure` | In the Shadows / The Rasmus | `all_candidate_plus_targeted_v4_hard_drop` |  | 265 | `analysis.artist_tag_neighbor_popularity` | 0 | 0 | 0 |
| `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` | `P0_roleless_stale_entity_failure` | I Believe in a Thing Called Love / The Darkness | `all_candidate_plus_targeted_v4_hard_drop` |  |  | `` | 0 | 0 | 0 |
| `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` | `P0_roleless_stale_entity_failure` | Move Along / The All-American Rejects | `all_candidate_plus_targeted_v4_hard_drop` | 353 | 39 | `analysis.artist_neighbor_scene_v2` | 0 | 1 | 1 |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | `all_candidate_plus_targeted_v4_hard_drop` |  | 14 | `analysis.same_album_fanout` | 1 | 1 | 1 |
| `8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7` | `P0_novelty_prior_anchor_failure` | Transcentience / Animals As Leaders | `all_candidate_plus_targeted_v4_hard_drop` |  | 100 | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 0 | 0 | 1 |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | `all_candidate_plus_targeted_v4_hard_drop` | 252 | 1 | `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` | 1 | 1 | 1 |
| `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3` | `P0_novelty_prior_anchor_failure` | Gib ihn einfach (Dies das 2) / Ghanaian Stallion | `all_candidate_plus_targeted_v4_hard_drop` |  | 101 | `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 0 | 0 | 0 |
| `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` | `P0_new_artist_union20_gap_failure` | Hong Kong 2046 / Hong Kong Express | `all_candidate_plus_targeted_v4_hard_drop` |  | 381 | `dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b` | 0 | 0 | 0 |
| `907921a3-d08f-4ba1-8cce-0e760a9e7044::t7` | `P0_new_artist_union20_gap_failure` | Sunrise - Slow Hands Remix / Kasper Bjørke | `all_candidate_plus_targeted_v4_hard_drop` |  | 280 | `centroid.anchor_tracks.cf_bpr` | 0 | 0 | 0 |
| `324ddfb5-8a18-4729-9acb-c851907a297c::t3` | `P0_new_artist_union20_gap_failure` | Acknowledge / Masta Ace | `all_candidate_plus_targeted_v4_hard_drop` | 376 | 148 | `analysis.artist_neighbor_scene_v2` | 0 | 0 | 0 |
| `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` | `P0_new_artist_union20_gap_failure` | Two To Make It Right / Seduction | `all_candidate_plus_targeted_v4_hard_drop` | 412 | 6 | `analysis.scene_era_tag_popularity_v2` | 1 | 1 | 1 |
| `67b9ba8a-382f-4b70-af76-576848d8cf67::t8` | `P1_temporal_constraint_failure` | Gangsta Gangsta / N.W.A. | `all_candidate_plus_targeted_v4_hard_drop` |  | 20 | `analysis.artist_neighbor_scene_v2` | 1 | 1 | 1 |
| `9468e467-d396-461b-be29-b30b6cf87c35::t5` | `P1_temporal_constraint_failure` | Midnight / A Tribe Called Quest | `all_candidate_plus_targeted_v4_hard_drop` |  | 177 | `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b` | 0 | 0 | 0 |
| `e978bb5b-26af-4c7d-b720-b9210bdddf25::t8` | `P1_temporal_constraint_failure` | Dear Yvette / Jane Doe, Masta Ace | `all_candidate_plus_targeted_v4_hard_drop` |  |  | `` | 0 | 0 | 0 |
| `c4c0c288-dbcd-4970-ad52-901aafe91b88::t4` | `P1_temporal_constraint_failure` | I Juswanna Chill / Large Professor | `all_candidate_plus_targeted_v4_hard_drop` | 805 | 227 | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 0 | 0 | 0 |
| `ad5348a7-d3bc-4882-bfca-54aa655eac96::t5` | `P1_positive_tag_retrieval_gap_failure` | Glitter / Tyler, The Creator | `all_candidate_plus_targeted_v4_hard_drop` |  | 78 | `analysis.tag_popularity_alias` | 0 | 0 | 1 |
