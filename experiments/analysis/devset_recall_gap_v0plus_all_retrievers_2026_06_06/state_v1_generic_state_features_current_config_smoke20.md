# State V1 Retriever Matrix

Focused candidate-generation matrix over saved V1 extraction states.
The main gate is branch union@20/50; RRF/final ranking is reported separately.

## Summary

| Variant | n | final@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_trace_baseline` | 20 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |  |  |
| `current_config` | 20 | 0.050 | 0.200 | 0.250 | 0.400 | 0.600 | 0.800 | 0.950 | 0.400 |
| `current_config_state_features` | 20 | 0.000 | 0.050 | 0.300 | 0.550 | 0.750 | 0.850 | 0.950 | 0.550 |

## Per-Class Summary

| Pack | n | baseline u@20 | baseline u@50 | best single | single u@20 | single u@50 | combined | combined u@20 | combined u@50 |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|
| P0_novelty_prior_anchor_failure | 10 | 0.000 | 0.000 | `` |  |  | `current_config_state_features` | 0.500 | 0.700 |
| P0_roleless_stale_entity_failure | 10 | 0.000 | 0.000 | `` |  |  | `current_config_state_features` | 0.100 | 0.400 |

## Examples

### `current_config` Rescued union@20

- `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` (P0_roleless_stale_entity_failure): GT=Armature by Emptyset; best_branch=`dense.clap_text.sonic.audio_laion_clap` rank=12; why=rescued_at_union20
- `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` (P0_novelty_prior_anchor_failure): GT=God Hates a Coward by Tomahawk; best_branch=`dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` rank=3; why=rescued_at_union20
- `d6e50fb5-a135-4008-80b6-d0be434369ac::t3` (P0_novelty_prior_anchor_failure): GT=Volare (Nel Blu Di Pinto Di Blu) - 1998 - Remastered by Dean Martin; best_branch=`lookup.era_popularity` rank=9; why=rescued_at_union20
- `38d8ba41-a4ea-48ea-b460-bd93d164302a::t4` (P0_novelty_prior_anchor_failure): GT=Woo Hah!! Got You All In Check by Busta Rhymes; best_branch=`centroid.anchor_tracks.audio_laion_clap` rank=18; why=rescued_at_union20
- `8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6` (P0_novelty_prior_anchor_failure): GT=Exit Theme (feat. Astronautalis & Lotte Kestner) by Astronautalis, Sadistik, Lotte Kestner; best_branch=`centroid.anchor_tracks.audio_laion_clap` rank=1; why=rescued_at_union20

### `current_config` Still Missed union@20

- `0b9d547f-e748-464a-90e2-2199149f915c::t6` (P0_roleless_stale_entity_failure): GT=Give It To Me Baby by Rick James; best_branch=`dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` rank=68; why=branch_local_ranking_gap_51_100; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `e66c6a88-88ba-4117-9114-363bfa96294a::t7` (P0_roleless_stale_entity_failure): GT=Test Drive by John Powell; best_branch=`dense.clap_text.sonic_nl.audio_laion_clap` rank=180; why=deep_candidate_ranking_gap; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `41367174-552b-4117-9caa-d0ba1b307d37::t2` (P0_roleless_stale_entity_failure): GT=Mercy by Muse; best_branch=`centroid.anchor_tracks.audio_laion_clap` rank=334; why=deep_candidate_ranking_gap; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7` (P0_roleless_stale_entity_failure): GT=I Can't Go to Sleep by Wu-Tang Clan; best_branch=`dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b` rank=34; why=branch_local_ranking_gap_21_50; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` (P0_roleless_stale_entity_failure): GT=The Carbon Stampede by Cattle Decapitation; best_branch=`centroid.anchor_tracks.cf_bpr` rank=76; why=branch_local_ranking_gap_51_100; change=Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` (P0_roleless_stale_entity_failure): GT=Shaft by Kashmere Stage Band; best_branch=`dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` rank=50; why=branch_local_ranking_gap_21_50; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` (P0_roleless_stale_entity_failure): GT=In the Shadows by The Rasmus; best_branch=`centroid.anchor_tracks.audio_laion_clap` rank=835; why=deep_candidate_ranking_gap; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` (P0_roleless_stale_entity_failure): GT=I Believe in a Thing Called Love by The Darkness; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` (P0_roleless_stale_entity_failure): GT=Move Along by The All-American Rejects; best_branch=`centroid.anchor_tracks.audio_laion_clap` rank=103; why=deep_candidate_ranking_gap; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- `c7a965c3-cd7f-46f6-b166-9dce9a800e0a::t3` (P0_novelty_prior_anchor_failure): GT=S&M by Rihanna; best_branch=`dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` rank=40; why=branch_local_ranking_gap_21_50; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `88beb200-0334-4aba-be15-8e1303725766::t6` (P0_novelty_prior_anchor_failure): GT=Used To by Lil Wayne, Drake; best_branch=`dense.clap_text.sonic.audio_laion_clap` rank=258; why=deep_candidate_ranking_gap; change=Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- `daeef24e-b041-4140-9101-882820c63408::t7` (P0_novelty_prior_anchor_failure): GT=The Analog Kid by Rush; best_branch=`dense.qwen_8b.intent.metadata_qwen3_embedding_8b` rank=72; why=branch_local_ranking_gap_51_100; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.


## Per-Sample Rows

| Sample | Pack | GT | Variant | final rank | best branch rank | best branch | union@20 | union@50 | union@100 |
|---|---|---|---|---:|---:|---|---:|---:|---:|
| `0b9d547f-e748-464a-90e2-2199149f915c::t6` | `P0_roleless_stale_entity_failure` | Give It To Me Baby / Rick James | `current_config` | 172 | 68 | `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 0 | 0 | 1 |
| `e66c6a88-88ba-4117-9114-363bfa96294a::t7` | `P0_roleless_stale_entity_failure` | Test Drive / John Powell | `current_config` | 563 | 180 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 0 |
| `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` | `P0_roleless_stale_entity_failure` | Armature / Emptyset | `current_config` | 50 | 12 | `dense.clap_text.sonic.audio_laion_clap` | 1 | 1 | 1 |
| `41367174-552b-4117-9caa-d0ba1b307d37::t2` | `P0_roleless_stale_entity_failure` | Mercy / Muse | `current_config` |  | 334 | `centroid.anchor_tracks.audio_laion_clap` | 0 | 0 | 0 |
| `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7` | `P0_roleless_stale_entity_failure` | I Can't Go to Sleep / Wu-Tang Clan | `current_config` | 876 | 34 | `dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b` | 0 | 1 | 1 |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | `current_config` | 302 | 76 | `centroid.anchor_tracks.cf_bpr` | 0 | 0 | 1 |
| `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` | `P0_roleless_stale_entity_failure` | Shaft / Kashmere Stage Band | `current_config` | 959 | 50 | `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` | 0 | 1 | 1 |
| `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` | `P0_roleless_stale_entity_failure` | In the Shadows / The Rasmus | `current_config` |  | 835 | `centroid.anchor_tracks.audio_laion_clap` | 0 | 0 | 0 |
| `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` | `P0_roleless_stale_entity_failure` | I Believe in a Thing Called Love / The Darkness | `current_config` |  |  | `` | 0 | 0 | 0 |
| `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` | `P0_roleless_stale_entity_failure` | Move Along / The All-American Rejects | `current_config` | 339 | 103 | `centroid.anchor_tracks.audio_laion_clap` | 0 | 0 | 0 |
| `c7a965c3-cd7f-46f6-b166-9dce9a800e0a::t3` | `P0_novelty_prior_anchor_failure` | S&M / Rihanna | `current_config` | 134 | 40 | `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` | 0 | 1 | 1 |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | `current_config` |  | 258 | `dense.clap_text.sonic.audio_laion_clap` | 0 | 0 | 0 |
| `daeef24e-b041-4140-9101-882820c63408::t7` | `P0_novelty_prior_anchor_failure` | The Analog Kid / Rush | `current_config` | 333 | 72 | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 0 | 0 | 1 |
| `8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7` | `P0_novelty_prior_anchor_failure` | Transcentience / Animals As Leaders | `current_config` |  | 103 | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 0 | 0 | 0 |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | `current_config` | 243 | 3 | `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` | 1 | 1 | 1 |
| `5f085552-b56b-440e-830b-b4e40b58f854::t6` | `P0_novelty_prior_anchor_failure` | Redneck Yacht Club / Craig Morgan | `current_config` | 41 | 55 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 1 |
| `d6e50fb5-a135-4008-80b6-d0be434369ac::t3` | `P0_novelty_prior_anchor_failure` | Volare (Nel Blu Di Pinto Di Blu) - 1998 - Remastered / Dean Martin | `current_config` | 31 | 9 | `lookup.era_popularity` | 1 | 1 | 1 |
| `38d8ba41-a4ea-48ea-b460-bd93d164302a::t4` | `P0_novelty_prior_anchor_failure` | Woo Hah!! Got You All In Check / Busta Rhymes | `current_config` | 175 | 18 | `centroid.anchor_tracks.audio_laion_clap` | 1 | 1 | 1 |
| `8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6` | `P0_novelty_prior_anchor_failure` | Exit Theme (feat. Astronautalis & Lotte Kestner) / Astronautalis, Sadistik, Lotte Kestner | `current_config` | 10 | 1 | `centroid.anchor_tracks.audio_laion_clap` | 1 | 1 | 1 |
| `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3` | `P0_novelty_prior_anchor_failure` | Gib ihn einfach (Dies das 2) / Ghanaian Stallion | `current_config` |  | 101 | `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 0 | 0 | 0 |
| `0b9d547f-e748-464a-90e2-2199149f915c::t6` | `P0_roleless_stale_entity_failure` | Give It To Me Baby / Rick James | `current_config_state_features` | 239 | 68 | `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 0 | 0 | 1 |
| `e66c6a88-88ba-4117-9114-363bfa96294a::t7` | `P0_roleless_stale_entity_failure` | Test Drive / John Powell | `current_config_state_features` | 340 | 71 | `dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b.state_features` | 0 | 0 | 1 |
| `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` | `P0_roleless_stale_entity_failure` | Armature / Emptyset | `current_config_state_features` | 97 | 12 | `dense.clap_text.sonic.audio_laion_clap` | 1 | 1 | 1 |
| `41367174-552b-4117-9caa-d0ba1b307d37::t2` | `P0_roleless_stale_entity_failure` | Mercy / Muse | `current_config_state_features` |  | 79 | `centroid.anchor_tracks.audio_laion_clap.state_features` | 0 | 0 | 1 |
| `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7` | `P0_roleless_stale_entity_failure` | I Can't Go to Sleep / Wu-Tang Clan | `current_config_state_features` |  | 34 | `dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b` | 0 | 1 | 1 |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | `current_config_state_features` | 155 | 39 | `dense.clap_text.sonic_nl.audio_laion_clap.state_features` | 0 | 1 | 1 |
| `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` | `P0_roleless_stale_entity_failure` | Shaft / Kashmere Stage Band | `current_config_state_features` |  | 50 | `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` | 0 | 1 | 1 |
| `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` | `P0_roleless_stale_entity_failure` | In the Shadows / The Rasmus | `current_config_state_features` |  | 600 | `centroid.anchor_tracks.audio_laion_clap.state_features` | 0 | 0 | 0 |
| `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` | `P0_roleless_stale_entity_failure` | I Believe in a Thing Called Love / The Darkness | `current_config_state_features` |  |  | `` | 0 | 0 | 0 |
| `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` | `P0_roleless_stale_entity_failure` | Move Along / The All-American Rejects | `current_config_state_features` | 121 | 52 | `dense.qwen_0_6b.intent.metadata_qwen3_embedding_0_6b.state_features` | 0 | 0 | 1 |
| `c7a965c3-cd7f-46f6-b166-9dce9a800e0a::t3` | `P0_novelty_prior_anchor_failure` | S&M / Rihanna | `current_config_state_features` | 145 | 40 | `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` | 0 | 1 | 1 |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | `current_config_state_features` |  | 258 | `dense.clap_text.sonic.audio_laion_clap` | 0 | 0 | 0 |
| `daeef24e-b041-4140-9101-882820c63408::t7` | `P0_novelty_prior_anchor_failure` | The Analog Kid / Rush | `current_config_state_features` | 118 | 16 | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b.state_features` | 1 | 1 | 1 |
| `8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7` | `P0_novelty_prior_anchor_failure` | Transcentience / Animals As Leaders | `current_config_state_features` |  | 103 | `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` | 0 | 0 | 0 |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | `current_config_state_features` | 121 | 3 | `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` | 1 | 1 | 1 |
| `5f085552-b56b-440e-830b-b4e40b58f854::t6` | `P0_novelty_prior_anchor_failure` | Redneck Yacht Club / Craig Morgan | `current_config_state_features` | 54 | 39 | `dense.clap_text.sonic_nl.audio_laion_clap.state_features` | 0 | 1 | 1 |
| `d6e50fb5-a135-4008-80b6-d0be434369ac::t3` | `P0_novelty_prior_anchor_failure` | Volare (Nel Blu Di Pinto Di Blu) - 1998 - Remastered / Dean Martin | `current_config_state_features` | 26 | 9 | `lookup.era_popularity` | 1 | 1 | 1 |
| `38d8ba41-a4ea-48ea-b460-bd93d164302a::t4` | `P0_novelty_prior_anchor_failure` | Woo Hah!! Got You All In Check / Busta Rhymes | `current_config_state_features` | 334 | 18 | `centroid.anchor_tracks.audio_laion_clap` | 1 | 1 | 1 |
| `8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6` | `P0_novelty_prior_anchor_failure` | Exit Theme (feat. Astronautalis & Lotte Kestner) / Astronautalis, Sadistik, Lotte Kestner | `current_config_state_features` | 86 | 1 | `centroid.anchor_tracks.audio_laion_clap` | 1 | 1 | 1 |
| `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3` | `P0_novelty_prior_anchor_failure` | Gib ihn einfach (Dies das 2) / Ghanaian Stallion | `current_config_state_features` | 994 | 101 | `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 0 | 0 | 0 |
