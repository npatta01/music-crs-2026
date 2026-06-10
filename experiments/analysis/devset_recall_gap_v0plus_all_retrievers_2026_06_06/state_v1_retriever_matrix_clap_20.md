# State V1 Retriever Matrix

Focused candidate-generation matrix over saved V1 extraction states.
The main gate is branch union@20/50; RRF/final ranking is reported separately.

## Summary

| Variant | n | final@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_trace_baseline` | 20 | 0.000 |  | 0.000 |  | 0.000 | 1.000 |  |  |
| `clap_sonic` | 20 | 0.000 | 0.050 | 0.050 | 0.050 | 0.100 | 0.250 | 0.800 | 0.050 |
| `clap_sonic_nl` | 20 | 0.000 | 0.050 | 0.000 | 0.000 | 0.150 | 0.350 | 0.700 | 0.000 |
| `clap_sonic_nl_enriched` | 20 | 0.000 | 0.100 | 0.050 | 0.050 | 0.150 | 0.350 | 0.700 | 0.050 |
| `clap_all` | 20 | 0.050 | 0.100 | 0.100 | 0.100 | 0.200 | 0.400 | 0.800 | 0.100 |

## Per-Sample Rows

| Sample | Pack | GT | Variant | final rank | best branch rank | best branch | union@20 | union@50 | union@100 |
|---|---|---|---|---:|---:|---|---:|---:|---:|
| `0b9d547f-e748-464a-90e2-2199149f915c::t6` | `P0_roleless_stale_entity_failure` | Give It To Me Baby / Rick James | `clap_sonic` | 267 | 169 | `lookup.era_popularity` | 0 | 0 | 0 |
| `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` | `P0_roleless_stale_entity_failure` | Armature / Emptyset | `clap_sonic` | 24 | 12 | `dense.clap_text.sonic.audio_laion_clap` | 1 | 1 | 1 |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | `clap_sonic` | 536 | 289 | `bm25` | 0 | 0 | 0 |
| `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` | `P0_roleless_stale_entity_failure` | In the Shadows / The Rasmus | `clap_sonic` |  |  | `` | 0 | 0 | 0 |
| `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` | `P0_roleless_stale_entity_failure` | Move Along / The All-American Rejects | `clap_sonic` | 916 | 539 | `bm25` | 0 | 0 | 0 |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | `clap_sonic` | 588 | 258 | `dense.clap_text.sonic.audio_laion_clap` | 0 | 0 | 0 |
| `daeef24e-b041-4140-9101-882820c63408::t7` | `P0_novelty_prior_anchor_failure` | The Analog Kid / Rush | `clap_sonic` | 212 | 104 | `bm25` | 0 | 0 | 0 |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | `clap_sonic` |  | 828 | `bm25` | 0 | 0 | 0 |
| `5f085552-b56b-440e-830b-b4e40b58f854::t6` | `P0_novelty_prior_anchor_failure` | Redneck Yacht Club / Craig Morgan | `clap_sonic` | 915 | 497 | `bm25` | 0 | 0 | 0 |
| `8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6` | `P0_novelty_prior_anchor_failure` | Exit Theme (feat. Astronautalis & Lotte Kestner) / Astronautalis, Sadistik, Lotte Kestner | `clap_sonic` | 974 | 469 | `dense.clap_text.sonic.audio_laion_clap` | 0 | 0 | 0 |
| `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6` | `P0_new_artist_union20_gap_failure` | Without You / Christina Aguilera | `clap_sonic` |  |  | `` | 0 | 0 | 0 |
| `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` | `P0_new_artist_union20_gap_failure` | Hong Kong 2046 / Hong Kong Express | `clap_sonic` |  |  | `` | 0 | 0 | 0 |
| `ab5eac17-909e-4271-8cf9-40c06b27ee56::t2` | `P0_new_artist_union20_gap_failure` | Sparks / Hilary Duff | `clap_sonic` | 77 | 89 | `bm25` | 0 | 0 | 1 |
| `324ddfb5-8a18-4729-9acb-c851907a297c::t3` | `P0_new_artist_union20_gap_failure` | Acknowledge / Masta Ace | `clap_sonic` |  | 705 | `bm25` | 0 | 0 | 0 |
| `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` | `P0_new_artist_union20_gap_failure` | Two To Make It Right / Seduction | `clap_sonic` | 523 | 335 | `dense.clap_text.sonic.audio_laion_clap` | 0 | 0 | 0 |
| `d5fcb591-3744-4ebb-9d1a-5c57c314b7d0::t5` | `P1_temporal_constraint_failure` | Love Train / The O'Jays | `clap_sonic` | 484 | 193 | `bm25` | 0 | 0 | 0 |
| `f2d85aa5-2086-4b1e-9974-d188c43621db::t8` | `P1_temporal_constraint_failure` | Leraine / Kettel | `clap_sonic` |  | 648 | `dense.clap_text.sonic.audio_laion_clap` | 0 | 0 | 0 |
| `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6` | `P1_temporal_constraint_failure` | Thriller / Fall Out Boy | `clap_sonic` | 956 | 530 | `bm25` | 0 | 0 | 0 |
| `3676005d-5b7c-4c48-9b73-3e10dd509c07::t1` | `P1_temporal_constraint_failure` | Breath and Life / Audiomachine | `clap_sonic` |  | 931 | `dense.clap_text.sonic.audio_laion_clap` | 0 | 0 | 0 |
| `71bb177a-dab1-4bbc-8508-22d809b05c31::t6` | `P1_temporal_constraint_failure` | Constant Craving - Remastered / k.d. lang | `clap_sonic` |  |  | `` | 0 | 0 | 0 |
| `0b9d547f-e748-464a-90e2-2199149f915c::t6` | `P0_roleless_stale_entity_failure` | Give It To Me Baby / Rick James | `clap_sonic_nl` | 258 | 169 | `lookup.era_popularity` | 0 | 0 | 0 |
| `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` | `P0_roleless_stale_entity_failure` | Armature / Emptyset | `clap_sonic_nl` |  |  | `` | 0 | 0 | 0 |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | `clap_sonic_nl` | 347 | 289 | `bm25` | 0 | 0 | 0 |
| `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` | `P0_roleless_stale_entity_failure` | In the Shadows / The Rasmus | `clap_sonic_nl` |  |  | `` | 0 | 0 | 0 |
| `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` | `P0_roleless_stale_entity_failure` | Move Along / The All-American Rejects | `clap_sonic_nl` | 509 | 539 | `bm25` | 0 | 0 | 0 |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | `clap_sonic_nl` |  |  | `` | 0 | 0 | 0 |
| `daeef24e-b041-4140-9101-882820c63408::t7` | `P0_novelty_prior_anchor_failure` | The Analog Kid / Rush | `clap_sonic_nl` | 214 | 104 | `bm25` | 0 | 0 | 0 |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | `clap_sonic_nl` |  | 828 | `bm25` | 0 | 0 | 0 |
| `5f085552-b56b-440e-830b-b4e40b58f854::t6` | `P0_novelty_prior_anchor_failure` | Redneck Yacht Club / Craig Morgan | `clap_sonic_nl` | 76 | 55 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 1 |
| `8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6` | `P0_novelty_prior_anchor_failure` | Exit Theme (feat. Astronautalis & Lotte Kestner) / Astronautalis, Sadistik, Lotte Kestner | `clap_sonic_nl` | 405 | 189 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 0 |
| `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6` | `P0_new_artist_union20_gap_failure` | Without You / Christina Aguilera | `clap_sonic_nl` |  |  | `` | 0 | 0 | 0 |
| `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` | `P0_new_artist_union20_gap_failure` | Hong Kong 2046 / Hong Kong Express | `clap_sonic_nl` |  |  | `` | 0 | 0 | 0 |
| `ab5eac17-909e-4271-8cf9-40c06b27ee56::t2` | `P0_new_artist_union20_gap_failure` | Sparks / Hilary Duff | `clap_sonic_nl` | 38 | 89 | `bm25` | 0 | 0 | 1 |
| `324ddfb5-8a18-4729-9acb-c851907a297c::t3` | `P0_new_artist_union20_gap_failure` | Acknowledge / Masta Ace | `clap_sonic_nl` | 587 | 333 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 0 |
| `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` | `P0_new_artist_union20_gap_failure` | Two To Make It Right / Seduction | `clap_sonic_nl` | 546 | 388 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 0 |
| `d5fcb591-3744-4ebb-9d1a-5c57c314b7d0::t5` | `P1_temporal_constraint_failure` | Love Train / The O'Jays | `clap_sonic_nl` | 407 | 193 | `bm25` | 0 | 0 | 0 |
| `f2d85aa5-2086-4b1e-9974-d188c43621db::t8` | `P1_temporal_constraint_failure` | Leraine / Kettel | `clap_sonic_nl` | 202 | 71 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 1 |
| `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6` | `P1_temporal_constraint_failure` | Thriller / Fall Out Boy | `clap_sonic_nl` | 936 | 530 | `bm25` | 0 | 0 | 0 |
| `3676005d-5b7c-4c48-9b73-3e10dd509c07::t1` | `P1_temporal_constraint_failure` | Breath and Life / Audiomachine | `clap_sonic_nl` |  | 783 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 0 |
| `71bb177a-dab1-4bbc-8508-22d809b05c31::t6` | `P1_temporal_constraint_failure` | Constant Craving - Remastered / k.d. lang | `clap_sonic_nl` |  |  | `` | 0 | 0 | 0 |
| `0b9d547f-e748-464a-90e2-2199149f915c::t6` | `P0_roleless_stale_entity_failure` | Give It To Me Baby / Rick James | `clap_sonic_nl_enriched` | 258 | 169 | `lookup.era_popularity` | 0 | 0 | 0 |
| `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` | `P0_roleless_stale_entity_failure` | Armature / Emptyset | `clap_sonic_nl_enriched` |  |  | `` | 0 | 0 | 0 |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | `clap_sonic_nl_enriched` | 347 | 289 | `bm25` | 0 | 0 | 0 |
| `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` | `P0_roleless_stale_entity_failure` | In the Shadows / The Rasmus | `clap_sonic_nl_enriched` |  |  | `` | 0 | 0 | 0 |
| `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` | `P0_roleless_stale_entity_failure` | Move Along / The All-American Rejects | `clap_sonic_nl_enriched` | 509 | 539 | `bm25` | 0 | 0 | 0 |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | `clap_sonic_nl_enriched` |  |  | `` | 0 | 0 | 0 |
| `daeef24e-b041-4140-9101-882820c63408::t7` | `P0_novelty_prior_anchor_failure` | The Analog Kid / Rush | `clap_sonic_nl_enriched` | 214 | 104 | `bm25` | 0 | 0 | 0 |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | `clap_sonic_nl_enriched` |  | 828 | `bm25` | 0 | 0 | 0 |
| `5f085552-b56b-440e-830b-b4e40b58f854::t6` | `P0_novelty_prior_anchor_failure` | Redneck Yacht Club / Craig Morgan | `clap_sonic_nl_enriched` | 76 | 55 | `dense.clap_text.sonic_nl_enriched.audio_laion_clap` | 0 | 0 | 1 |
| `8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6` | `P0_novelty_prior_anchor_failure` | Exit Theme (feat. Astronautalis & Lotte Kestner) / Astronautalis, Sadistik, Lotte Kestner | `clap_sonic_nl_enriched` | 405 | 189 | `dense.clap_text.sonic_nl_enriched.audio_laion_clap` | 0 | 0 | 0 |
| `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6` | `P0_new_artist_union20_gap_failure` | Without You / Christina Aguilera | `clap_sonic_nl_enriched` |  |  | `` | 0 | 0 | 0 |
| `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` | `P0_new_artist_union20_gap_failure` | Hong Kong 2046 / Hong Kong Express | `clap_sonic_nl_enriched` |  |  | `` | 0 | 0 | 0 |
| `ab5eac17-909e-4271-8cf9-40c06b27ee56::t2` | `P0_new_artist_union20_gap_failure` | Sparks / Hilary Duff | `clap_sonic_nl_enriched` | 38 | 89 | `bm25` | 0 | 0 | 1 |
| `324ddfb5-8a18-4729-9acb-c851907a297c::t3` | `P0_new_artist_union20_gap_failure` | Acknowledge / Masta Ace | `clap_sonic_nl_enriched` | 587 | 333 | `dense.clap_text.sonic_nl_enriched.audio_laion_clap` | 0 | 0 | 0 |
| `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` | `P0_new_artist_union20_gap_failure` | Two To Make It Right / Seduction | `clap_sonic_nl_enriched` | 637 | 591 | `dense.clap_text.sonic_nl_enriched.audio_laion_clap` | 0 | 0 | 0 |
| `d5fcb591-3744-4ebb-9d1a-5c57c314b7d0::t5` | `P1_temporal_constraint_failure` | Love Train / The O'Jays | `clap_sonic_nl_enriched` | 407 | 193 | `bm25` | 0 | 0 | 0 |
| `f2d85aa5-2086-4b1e-9974-d188c43621db::t8` | `P1_temporal_constraint_failure` | Leraine / Kettel | `clap_sonic_nl_enriched` | 21 | 7 | `dense.clap_text.sonic_nl_enriched.audio_laion_clap` | 1 | 1 | 1 |
| `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6` | `P1_temporal_constraint_failure` | Thriller / Fall Out Boy | `clap_sonic_nl_enriched` | 936 | 530 | `bm25` | 0 | 0 | 0 |
| `3676005d-5b7c-4c48-9b73-3e10dd509c07::t1` | `P1_temporal_constraint_failure` | Breath and Life / Audiomachine | `clap_sonic_nl_enriched` |  | 783 | `dense.clap_text.sonic_nl_enriched.audio_laion_clap` | 0 | 0 | 0 |
| `71bb177a-dab1-4bbc-8508-22d809b05c31::t6` | `P1_temporal_constraint_failure` | Constant Craving - Remastered / k.d. lang | `clap_sonic_nl_enriched` |  |  | `` | 0 | 0 | 0 |
| `0b9d547f-e748-464a-90e2-2199149f915c::t6` | `P0_roleless_stale_entity_failure` | Give It To Me Baby / Rick James | `clap_all` | 294 | 169 | `lookup.era_popularity` | 0 | 0 | 0 |
| `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` | `P0_roleless_stale_entity_failure` | Armature / Emptyset | `clap_all` | 128 | 12 | `dense.clap_text.sonic.audio_laion_clap` | 1 | 1 | 1 |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | `clap_all` | 545 | 290 | `bm25` | 0 | 0 | 0 |
| `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` | `P0_roleless_stale_entity_failure` | In the Shadows / The Rasmus | `clap_all` |  |  | `` | 0 | 0 | 0 |
| `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` | `P0_roleless_stale_entity_failure` | Move Along / The All-American Rejects | `clap_all` | 586 | 539 | `bm25` | 0 | 0 | 0 |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | `clap_all` | 636 | 258 | `dense.clap_text.sonic.audio_laion_clap` | 0 | 0 | 0 |
| `daeef24e-b041-4140-9101-882820c63408::t7` | `P0_novelty_prior_anchor_failure` | The Analog Kid / Rush | `clap_all` | 483 | 104 | `bm25` | 0 | 0 | 0 |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | `clap_all` |  | 828 | `bm25` | 0 | 0 | 0 |
| `5f085552-b56b-440e-830b-b4e40b58f854::t6` | `P0_novelty_prior_anchor_failure` | Redneck Yacht Club / Craig Morgan | `clap_all` | 27 | 55 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 1 |
| `8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6` | `P0_novelty_prior_anchor_failure` | Exit Theme (feat. Astronautalis & Lotte Kestner) / Astronautalis, Sadistik, Lotte Kestner | `clap_all` | 288 | 189 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 0 |
| `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6` | `P0_new_artist_union20_gap_failure` | Without You / Christina Aguilera | `clap_all` |  |  | `` | 0 | 0 | 0 |
| `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` | `P0_new_artist_union20_gap_failure` | Hong Kong 2046 / Hong Kong Express | `clap_all` |  |  | `` | 0 | 0 | 0 |
| `ab5eac17-909e-4271-8cf9-40c06b27ee56::t2` | `P0_new_artist_union20_gap_failure` | Sparks / Hilary Duff | `clap_all` | 51 | 89 | `bm25` | 0 | 0 | 1 |
| `324ddfb5-8a18-4729-9acb-c851907a297c::t3` | `P0_new_artist_union20_gap_failure` | Acknowledge / Masta Ace | `clap_all` | 568 | 333 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 0 |
| `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` | `P0_new_artist_union20_gap_failure` | Two To Make It Right / Seduction | `clap_all` | 381 | 335 | `dense.clap_text.sonic.audio_laion_clap` | 0 | 0 | 0 |
| `d5fcb591-3744-4ebb-9d1a-5c57c314b7d0::t5` | `P1_temporal_constraint_failure` | Love Train / The O'Jays | `clap_all` | 558 | 193 | `bm25` | 0 | 0 | 0 |
| `f2d85aa5-2086-4b1e-9974-d188c43621db::t8` | `P1_temporal_constraint_failure` | Leraine / Kettel | `clap_all` | 11 | 7 | `dense.clap_text.sonic_nl_enriched.audio_laion_clap` | 1 | 1 | 1 |
| `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6` | `P1_temporal_constraint_failure` | Thriller / Fall Out Boy | `clap_all` |  | 530 | `bm25` | 0 | 0 | 0 |
| `3676005d-5b7c-4c48-9b73-3e10dd509c07::t1` | `P1_temporal_constraint_failure` | Breath and Life / Audiomachine | `clap_all` |  | 783 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 0 |
| `71bb177a-dab1-4bbc-8508-22d809b05c31::t6` | `P1_temporal_constraint_failure` | Constant Craving - Remastered / k.d. lang | `clap_all` |  |  | `` | 0 | 0 | 0 |
