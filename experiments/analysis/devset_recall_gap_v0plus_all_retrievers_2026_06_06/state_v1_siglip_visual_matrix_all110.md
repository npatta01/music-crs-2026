# State V1 Retriever Matrix

Focused candidate-generation matrix over saved V1 extraction states.
The main gate is branch union@20/50; RRF/final ranking is reported separately.

## Summary

| Variant | n | final@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_trace_baseline` | 110 | 0.182 | 0.373 | 0.545 | 0.545 | 0.545 | 1.000 |  |  |
| `siglip_visual` | 110 |  |  | 0.564 | 0.573 | 0.600 |  |  |  |

## Per-Class Summary

| Pack | n | baseline u@20 | baseline u@50 | best single | single u@20 | single u@50 | combined | combined u@20 | combined u@50 |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|
| P0_good_state_ranker_near_miss_failure | 10 | 1.000 | 1.000 | `siglip_visual` | 0.500 | 0.600 | `` |  |  |
| P0_named_artist_ranker_failure | 10 | 1.000 | 1.000 | `siglip_visual` | 0.500 | 0.500 | `` |  |  |
| P0_new_artist_union20_gap_failure | 10 | 0.000 | 0.000 | `siglip_visual` | 0.000 | 0.100 | `` |  |  |
| P0_novelty_prior_anchor_failure | 10 | 0.000 | 0.000 | `siglip_visual` | 0.100 | 0.100 | `` |  |  |
| P0_roleless_stale_entity_failure | 10 | 0.000 | 0.000 | `siglip_visual` | 0.000 | 0.000 | `` |  |  |
| P0_same_album_ranker_failure | 10 | 1.000 | 1.000 | `siglip_visual` | 0.100 | 0.200 | `` |  |  |
| P1_positive_tag_retrieval_gap_failure | 10 | 0.000 | 0.000 | `siglip_visual` | 0.100 | 0.100 | `` |  |  |
| P1_rejection_guardrail_failure | 10 | 1.000 | 1.000 | `siglip_visual` | 0.100 | 0.100 | `` |  |  |
| P1_temporal_constraint_failure | 10 | 0.000 | 0.000 | `siglip_visual` | 0.000 | 0.000 | `` |  |  |
| POS_clean_final_hit_control | 10 | 1.000 | 1.000 | `siglip_visual` | 0.800 | 0.800 | `` |  |  |
| POS_exact_entity_success_control | 10 | 1.000 | 1.000 | `siglip_visual` | 1.000 | 1.000 | `` |  |  |

## Examples

### `siglip_visual` Rescued union@20

- `d6e50fb5-a135-4008-80b6-d0be434369ac::t3` (P0_novelty_prior_anchor_failure): GT=Volare (Nel Blu Di Pinto Di Blu) - 1998 - Remastered by Dean Martin; best_branch=`lookup.era_popularity` rank=9; why=rescued_at_union20
- `dd686049-59ba-439b-8c51-949a0876e1b3::t1` (P1_positive_tag_retrieval_gap_failure): GT=Vengeance (The Return of the Night Driving Avenger) [Bonus Track] by Perturbator; best_branch=`dense.siglip2_text.visual.image_siglip2` rank=1; why=rescued_at_union20

### `siglip_visual` Still Missed union@20

- `0b9d547f-e748-464a-90e2-2199149f915c::t6` (P0_roleless_stale_entity_failure): GT=Give It To Me Baby by Rick James; best_branch=`lookup.era_popularity` rank=169; why=deep_candidate_ranking_gap; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `e66c6a88-88ba-4117-9114-363bfa96294a::t7` (P0_roleless_stale_entity_failure): GT=Test Drive by John Powell; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` (P0_roleless_stale_entity_failure): GT=Armature by Emptyset; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `41367174-552b-4117-9caa-d0ba1b307d37::t2` (P0_roleless_stale_entity_failure): GT=Mercy by Muse; best_branch=`bm25` rank=737; why=deep_candidate_ranking_gap; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7` (P0_roleless_stale_entity_failure): GT=I Can't Go to Sleep by Wu-Tang Clan; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` (P0_roleless_stale_entity_failure): GT=The Carbon Stampede by Cattle Decapitation; best_branch=`dense.siglip2_text.visual.image_siglip2` rank=148; why=deep_candidate_ranking_gap; change=Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` (P0_roleless_stale_entity_failure): GT=Shaft by Kashmere Stage Band; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` (P0_roleless_stale_entity_failure): GT=In the Shadows by The Rasmus; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` (P0_roleless_stale_entity_failure): GT=I Believe in a Thing Called Love by The Darkness; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` (P0_roleless_stale_entity_failure): GT=Move Along by The All-American Rejects; best_branch=`bm25` rank=523; why=deep_candidate_ranking_gap; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- `c7a965c3-cd7f-46f6-b166-9dce9a800e0a::t3` (P0_novelty_prior_anchor_failure): GT=S&M by Rihanna; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `88beb200-0334-4aba-be15-8e1303725766::t6` (P0_novelty_prior_anchor_failure): GT=Used To by Lil Wayne, Drake; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.


## Per-Sample Rows

| Sample | Pack | GT | Variant | final rank | best branch rank | best branch | union@20 | union@50 | union@100 |
|---|---|---|---|---:|---:|---|---:|---:|---:|
| `0b9d547f-e748-464a-90e2-2199149f915c::t6` | `P0_roleless_stale_entity_failure` | Give It To Me Baby / Rick James | `siglip_visual` | 345 | 169 | `lookup.era_popularity` | 0 | 0 | 0 |
| `e66c6a88-88ba-4117-9114-363bfa96294a::t7` | `P0_roleless_stale_entity_failure` | Test Drive / John Powell | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` | `P0_roleless_stale_entity_failure` | Armature / Emptyset | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `41367174-552b-4117-9caa-d0ba1b307d37::t2` | `P0_roleless_stale_entity_failure` | Mercy / Muse | `siglip_visual` |  | 737 | `bm25` | 0 | 0 | 0 |
| `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7` | `P0_roleless_stale_entity_failure` | I Can't Go to Sleep / Wu-Tang Clan | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | `siglip_visual` | 161 | 148 | `dense.siglip2_text.visual.image_siglip2` | 0 | 0 | 0 |
| `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` | `P0_roleless_stale_entity_failure` | Shaft / Kashmere Stage Band | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` | `P0_roleless_stale_entity_failure` | In the Shadows / The Rasmus | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` | `P0_roleless_stale_entity_failure` | I Believe in a Thing Called Love / The Darkness | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` | `P0_roleless_stale_entity_failure` | Move Along / The All-American Rejects | `siglip_visual` | 972 | 523 | `bm25` | 0 | 0 | 0 |
| `c7a965c3-cd7f-46f6-b166-9dce9a800e0a::t3` | `P0_novelty_prior_anchor_failure` | S&M / Rihanna | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `daeef24e-b041-4140-9101-882820c63408::t7` | `P0_novelty_prior_anchor_failure` | The Analog Kid / Rush | `siglip_visual` | 210 | 104 | `bm25` | 0 | 0 | 0 |
| `8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7` | `P0_novelty_prior_anchor_failure` | Transcentience / Animals As Leaders | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | `siglip_visual` |  | 828 | `bm25` | 0 | 0 | 0 |
| `5f085552-b56b-440e-830b-b4e40b58f854::t6` | `P0_novelty_prior_anchor_failure` | Redneck Yacht Club / Craig Morgan | `siglip_visual` | 972 | 491 | `bm25` | 0 | 0 | 0 |
| `d6e50fb5-a135-4008-80b6-d0be434369ac::t3` | `P0_novelty_prior_anchor_failure` | Volare (Nel Blu Di Pinto Di Blu) - 1998 - Remastered / Dean Martin | `siglip_visual` | 22 | 9 | `lookup.era_popularity` | 1 | 1 | 1 |
| `38d8ba41-a4ea-48ea-b460-bd93d164302a::t4` | `P0_novelty_prior_anchor_failure` | Woo Hah!! Got You All In Check / Busta Rhymes | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6` | `P0_novelty_prior_anchor_failure` | Exit Theme (feat. Astronautalis & Lotte Kestner) / Astronautalis, Sadistik, Lotte Kestner | `siglip_visual` | 542 | 260 | `dense.siglip2_text.visual.image_siglip2` | 0 | 0 | 0 |
| `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3` | `P0_novelty_prior_anchor_failure` | Gib ihn einfach (Dies das 2) / Ghanaian Stallion | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6` | `P0_new_artist_union20_gap_failure` | Without You / Christina Aguilera | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `5ee0dbbc-c1d1-4bed-ba09-7dafeec198bc::t8` | `P0_new_artist_union20_gap_failure` | You Reposted in the Wrong Neighborhood I Glue70 Mashup / Shokk | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `4e2482dc-a76c-4f4b-9d3f-7becec2f8a3a::t4` | `P0_new_artist_union20_gap_failure` | Goodbye Pork Pie Hat / Charles Mingus | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `5861afef-85c0-4163-b8b9-5a11e308f352::t4` | `P0_new_artist_union20_gap_failure` | Carmesí / Vicente Garcia | `siglip_visual` | 667 | 351 | `dense.siglip2_text.visual.image_siglip2` | 0 | 0 | 0 |
| `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` | `P0_new_artist_union20_gap_failure` | Hong Kong 2046 / Hong Kong Express | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `907921a3-d08f-4ba1-8cce-0e760a9e7044::t7` | `P0_new_artist_union20_gap_failure` | Sunrise - Slow Hands Remix / Kasper Bjørke | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `ab5eac17-909e-4271-8cf9-40c06b27ee56::t2` | `P0_new_artist_union20_gap_failure` | Sparks / Hilary Duff | `siglip_visual` | 130 | 83 | `bm25` | 0 | 0 | 1 |
| `324ddfb5-8a18-4729-9acb-c851907a297c::t3` | `P0_new_artist_union20_gap_failure` | Acknowledge / Masta Ace | `siglip_visual` | 705 | 626 | `dense.siglip2_text.visual.image_siglip2` | 0 | 0 | 0 |
| `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` | `P0_new_artist_union20_gap_failure` | Two To Make It Right / Seduction | `siglip_visual` |  | 805 | `bm25` | 0 | 0 | 0 |
| `ba68a3cc-5278-4680-917a-4ca66d33ef31::t5` | `P0_new_artist_union20_gap_failure` | Buttons / The Pussycat Dolls | `siglip_visual` | 112 | 33 | `dense.siglip2_text.visual.image_siglip2` | 0 | 1 | 1 |
| `d5fcb591-3744-4ebb-9d1a-5c57c314b7d0::t5` | `P1_temporal_constraint_failure` | Love Train / The O'Jays | `siglip_visual` | 388 | 147 | `bm25` | 0 | 0 | 0 |
| `f2d85aa5-2086-4b1e-9974-d188c43621db::t8` | `P1_temporal_constraint_failure` | Leraine / Kettel | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `67b9ba8a-382f-4b70-af76-576848d8cf67::t8` | `P1_temporal_constraint_failure` | Gangsta Gangsta / N.W.A. | `siglip_visual` |  | 632 | `bm25` | 0 | 0 | 0 |
| `9468e467-d396-461b-be29-b30b6cf87c35::t5` | `P1_temporal_constraint_failure` | Midnight / A Tribe Called Quest | `siglip_visual` |  | 742 | `bm25` | 0 | 0 | 0 |
| `e978bb5b-26af-4c7d-b720-b9210bdddf25::t8` | `P1_temporal_constraint_failure` | Dear Yvette / Jane Doe, Masta Ace | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `3676005d-5b7c-4c48-9b73-3e10dd509c07::t3` | `P1_temporal_constraint_failure` | Conquest of Paradise / Vangelis | `siglip_visual` |  | 591 | `bm25` | 0 | 0 | 0 |
| `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6` | `P1_temporal_constraint_failure` | Thriller / Fall Out Boy | `siglip_visual` | 852 | 479 | `bm25` | 0 | 0 | 0 |
| `3676005d-5b7c-4c48-9b73-3e10dd509c07::t1` | `P1_temporal_constraint_failure` | Breath and Life / Audiomachine | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `c4c0c288-dbcd-4970-ad52-901aafe91b88::t4` | `P1_temporal_constraint_failure` | I Juswanna Chill / Large Professor | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `71bb177a-dab1-4bbc-8508-22d809b05c31::t6` | `P1_temporal_constraint_failure` | Constant Craving - Remastered / k.d. lang | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `4d0afb6b-3705-493f-ab16-ca75ea311e1a::t7` | `P1_rejection_guardrail_failure` | Pilot / Benjamin Wallfisch, Hans Zimmer | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `1e14a07f-7369-4d24-9285-9343b6b18353::t8` | `P1_rejection_guardrail_failure` | Nordlys / Myrkur | `siglip_visual` | 6 | 2 | `dense.siglip2_text.visual.image_siglip2` | 1 | 1 | 1 |
| `d265b5a9-af57-4070-90f5-692a960c5aaa::t6` | `P1_rejection_guardrail_failure` | Get Lucky (feat. Pharrell Williams &amp; Nile Rodgers) - Radio Edit / Nile Rodgers, Pharrell Williams, Daft Punk | `siglip_visual` |  | 129 | `lookup.era_popularity` | 0 | 0 | 0 |
| `b2582e52-6d13-40b4-8552-2d8b63fa6c75::t8` | `P1_rejection_guardrail_failure` | Soil / System Of A Down | `siglip_visual` |  | 52 | `bm25` | 0 | 0 | 1 |
| `d265b5a9-af57-4070-90f5-692a960c5aaa::t8` | `P1_rejection_guardrail_failure` | Motherboard / Daft Punk | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `3a4224d3-1e5b-4bb9-a424-886d5c45d5d3::t8` | `P1_rejection_guardrail_failure` | Brain Relaxation Sky / Sample Rain Library | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `963b3ee7-17d1-4bb3-8a3f-0bc528a1f096::t5` | `P1_rejection_guardrail_failure` | Go Go Gadget Flow / Lupe Fiasco | `siglip_visual` |  | 66 | `bm25` | 0 | 0 | 1 |
| `08bea603-846a-428b-aa27-de4dfede7ba9::t8` | `P1_rejection_guardrail_failure` | Silhouette / Julia Holter | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `0fc60312-9a9d-4658-a950-06fc2441a2ac::t8` | `P1_rejection_guardrail_failure` | Music Will Untune the Sky / Have A Nice Life | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `3ebc2b49-0f5c-4161-bbcf-e1615821103f::t2` | `P1_rejection_guardrail_failure` | The Animus 2.0 / Jesper Kyd | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `37097db6-54b8-491b-8512-1df70648548b::t2` | `P0_named_artist_ranker_failure` | White Ferrari / Frank Ocean | `siglip_visual` | 2 | 2 | `lookup.resolved_artist_discography` | 1 | 1 | 1 |
| `f4115525-7e44-40df-8957-e38df99f214d::t4` | `P0_named_artist_ranker_failure` | Young And Beautiful / Lana Del Rey | `siglip_visual` | 5 | 1 | `lookup.resolved_artist_discography` | 1 | 1 | 1 |
| `eee89ca2-fc86-4a9a-b4c5-2d77cb3346c8::t7` | `P0_named_artist_ranker_failure` | Change (In the House of Flies) - In The House Of Flies LP Version / Deftones | `siglip_visual` | 568 | 281 | `bm25` | 0 | 0 | 0 |
| `44c3948c-bc44-4e40-ae77-82c2fec9c944::t7` | `P0_named_artist_ranker_failure` | Me Dediqué a Perderte / Alejandro Fernandez, Alejandro Fernández | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `899f906b-9b0b-42a6-9689-643eb9f1ed31::t8` | `P0_named_artist_ranker_failure` | Crawling / Linkin Park | `siglip_visual` |  | 19 | `bm25` | 1 | 1 | 1 |
| `93199894-d3db-4335-8278-e1be175944e4::t6` | `P0_named_artist_ranker_failure` | Smells Like Teen Spirit / Nirvana | `siglip_visual` | 445 | 217 | `bm25` | 0 | 0 | 0 |
| `7d2bb60e-1046-4956-91d0-cf1dd73037cc::t3` | `P0_named_artist_ranker_failure` | Hung Up / Madonna | `siglip_visual` | 1 | 1 | `lookup.resolved_artist_discography` | 1 | 1 | 1 |
| `1b406c88-9dfd-42cd-a1f5-9683f35f849b::t1` | `P0_named_artist_ranker_failure` | 93 'Til Infinity / Souls Of Mischief | `siglip_visual` | 993 | 505 | `bm25` | 0 | 0 | 0 |
| `7be411cd-f002-459e-8326-3ebe8be10b42::t6` | `P0_named_artist_ranker_failure` | Army Dreamers / Kate Bush | `siglip_visual` |  | 420 | `bm25` | 0 | 0 | 0 |
| `fc78453a-8798-4402-a01a-e9c557f08a03::t2` | `P0_named_artist_ranker_failure` | En el 2000 / Natalia Lafourcade | `siglip_visual` | 1 | 3 | `bm25` | 1 | 1 | 1 |
| `84803908-48e7-41b7-9269-a465a44f4c10::t2` | `P0_same_album_ranker_failure` | Runaway / Pusha T, Kanye West | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `6d825b33-dc20-4b3c-a277-0c8214163007::t6` | `P0_same_album_ranker_failure` | Super Rich Kids / Frank Ocean, Earl Sweatshirt | `siglip_visual` |  | 226 | `bm25` | 0 | 0 | 0 |
| `942c0b23-c5ad-4270-b23f-3ba456ea0ccf::t5` | `P0_same_album_ranker_failure` | Alive / Pearl Jam | `siglip_visual` | 16 | 11 | `dense.siglip2_text.visual.image_siglip2` | 1 | 1 | 1 |
| `19c7e5bf-0797-40c5-b798-4d024af9558d::t4` | `P0_same_album_ranker_failure` | Satisfied / Original Broadway Cast of Hamilton, Renée Elise Goldsberry | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `71b80ec3-6cca-48b4-b471-08efa00afa2d::t4` | `P0_same_album_ranker_failure` | That Would Be Enough / Lin-Manuel Miranda, Phillipa Soo | `siglip_visual` |  | 680 | `bm25` | 0 | 0 | 0 |
| `692611f0-d9ef-406c-8327-902575197aee::t8` | `P0_same_album_ranker_failure` | YAH. / Kendrick Lamar | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `8071d14d-7e0f-4f72-90a6-0941db80a371::t5` | `P0_same_album_ranker_failure` | Stay Down / Brent Faiyaz | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `c863175a-bbaf-4f6c-aef7-cb16f2792cb5::t6` | `P0_same_album_ranker_failure` | Cinderella (feat. Ty Dolla $ign) / Mac Miller | `siglip_visual` | 54 | 36 | `bm25` | 0 | 1 | 1 |
| `c96d7bb9-65d4-44be-9bc2-891e8e485f4e::t7` | `P0_same_album_ranker_failure` | Sentimento Louco - Ao Vivo / Marília Mendonça | `siglip_visual` |  | 396 | `dense.siglip2_text.visual.image_siglip2` | 0 | 0 | 0 |
| `e6ba98e1-9bee-4cc9-a6b7-0a8dcd767a1f::t7` | `P0_same_album_ranker_failure` | Boom / P.O.D. | `siglip_visual` | 638 | 290 | `bm25` | 0 | 0 | 0 |
| `ad5348a7-d3bc-4882-bfca-54aa655eac96::t5` | `P1_positive_tag_retrieval_gap_failure` | Glitter / Tyler, The Creator | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `2bbc0a7e-3ab0-4376-8135-182cd4ae075f::t1` | `P1_positive_tag_retrieval_gap_failure` | Las Almas Del Silencio / Ricky Martin | `siglip_visual` | 837 | 500 | `bm25` | 0 | 0 | 0 |
| `464477e4-f186-47fb-8cb0-55691c8b8f57::t6` | `P1_positive_tag_retrieval_gap_failure` | Where Eagles Dare / Glenn Danzig, Misfits | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `13066d2c-2d5e-4162-b3dc-354ecef3aff5::t5` | `P1_positive_tag_retrieval_gap_failure` | You Know What I Mean / Cults | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `a2cface7-c4fc-4eb5-80b2-e0c516093732::t3` | `P1_positive_tag_retrieval_gap_failure` | The City Is At War / Cobra Starship | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `dd686049-59ba-439b-8c51-949a0876e1b3::t1` | `P1_positive_tag_retrieval_gap_failure` | Vengeance (The Return of the Night Driving Avenger) [Bonus Track] / Perturbator | `siglip_visual` | 2 | 1 | `dense.siglip2_text.visual.image_siglip2` | 1 | 1 | 1 |
| `a8df96e2-c196-462c-9484-72aa093aedf4::t1` | `P1_positive_tag_retrieval_gap_failure` | Do Everything / Steven Curtis Chapman | `siglip_visual` | 899 | 492 | `bm25` | 0 | 0 | 0 |
| `5a0dfe9d-ec8a-4449-97df-35535cbf162f::t1` | `P1_positive_tag_retrieval_gap_failure` | A New World / Harry Gregson-Williams | `siglip_visual` | 138 | 78 | `dense.siglip2_text.visual.image_siglip2` | 0 | 0 | 1 |
| `1c567917-f931-4609-9695-a9c0f8e39f3d::t2` | `P1_positive_tag_retrieval_gap_failure` | Arregaçada / U Can't Touch This / Banda Uó | `siglip_visual` | 102 | 51 | `dense.siglip2_text.visual.image_siglip2` | 0 | 0 | 1 |
| `54cda581-3b2e-4245-a479-1a27589760d2::t3` | `P1_positive_tag_retrieval_gap_failure` | Deliberation - Studio / Katatonia | `siglip_visual` | 560 | 281 | `bm25` | 0 | 0 | 0 |
| `13066d2c-2d5e-4162-b3dc-354ecef3aff5::t3` | `P0_good_state_ranker_near_miss_failure` | Yellow / Coldplay | `siglip_visual` | 2 | 1 | `lookup.era_popularity` | 1 | 1 | 1 |
| `a62ed6fc-e634-4d57-afab-36d9ffc0fcc1::t1` | `P0_good_state_ranker_near_miss_failure` | Iris / The Goo Goo Dolls | `siglip_visual` | 4 | 2 | `lookup.era_popularity` | 1 | 1 | 1 |
| `be88097f-b6b0-4fb4-bed9-857a92a733c0::t3` | `P0_good_state_ranker_near_miss_failure` | Dreams - 2004 Remaster / Fleetwood Mac | `siglip_visual` | 5 | 1 | `lookup.era_popularity` | 1 | 1 | 1 |
| `2eb984dc-9c71-449a-a335-caaa113d2c2b::t3` | `P0_good_state_ranker_near_miss_failure` | Tennessee Whiskey / Chris Stapleton | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `43a0926b-882e-403d-8cf7-2b0a598e0cc5::t2` | `P0_good_state_ranker_near_miss_failure` | Devil In A New Dress / Rick Ross, Kanye West | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `401c369d-1eba-41b2-8eca-d93a6faeeddc::t3` | `P0_good_state_ranker_near_miss_failure` | Walk / Pantera | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `2db3ddc8-78a1-412c-a71e-e0d748aab0e7::t2` | `P0_good_state_ranker_near_miss_failure` | Old Time Rock & Roll / Bob Seger | `siglip_visual` | 63 | 50 | `lookup.era_popularity` | 0 | 1 | 1 |
| `b4ffa800-8173-4f16-800a-4b5e765d7f80::t4` | `P0_good_state_ranker_near_miss_failure` | And I Love Her - Remastered / The Beatles | `siglip_visual` |  | 1 | `lookup.resolved_artist_discography` | 1 | 1 | 1 |
| `66ff896f-fcbc-4c42-9d69-b0b5b5ae5a56::t3` | `P0_good_state_ranker_near_miss_failure` | Hungry Heart / Bruce Springsteen | `siglip_visual` | 185 | 76 | `lookup.era_popularity` | 0 | 0 | 1 |
| `c4c0c288-dbcd-4970-ad52-901aafe91b88::t1` | `P0_good_state_ranker_near_miss_failure` | Electric Relaxation / A Tribe Called Quest | `siglip_visual` | 119 | 11 | `bm25` | 1 | 1 | 1 |
| `0681d55b-98a0-4773-a9df-075a8050d805::t1` | `POS_exact_entity_success_control` | Numb / Linkin Park | `siglip_visual` | 1 | 1 | `bm25` | 1 | 1 | 1 |
| `8bee6f03-8cae-44ae-9325-455dc1138549::t1` | `POS_exact_entity_success_control` | Africa / TOTO, Toto | `siglip_visual` | 1 | 1 | `bm25` | 1 | 1 | 1 |
| `d62387d0-3743-4ddc-bc92-8204c951ccee::t1` | `POS_exact_entity_success_control` | In the End / Linkin Park | `siglip_visual` | 1 | 1 | `bm25` | 1 | 1 | 1 |
| `bd2aa024-68e7-43c2-aa87-afce9b4d7cf1::t2` | `POS_exact_entity_success_control` | Shut Up and Dance / WALK THE MOON | `siglip_visual` | 3 | 1 | `bm25` | 1 | 1 | 1 |
| `028027d3-ad67-4cfb-baca-516772ae7399::t1` | `POS_exact_entity_success_control` | Toxic / Britney Spears | `siglip_visual` | 1 | 1 | `bm25` | 1 | 1 | 1 |
| `fada63d6-1275-47a1-b3ab-30eae222fd72::t1` | `POS_exact_entity_success_control` | Toxic / Britney Spears | `siglip_visual` | 1 | 1 | `bm25` | 1 | 1 | 1 |
| `7c3154c5-d1c2-4f07-9b8d-96d187334f1b::t1` | `POS_exact_entity_success_control` | Way Down We Go / Kaleo, KALEO | `siglip_visual` | 1 | 1 | `bm25` | 1 | 1 | 1 |
| `ba3da7b0-1e81-4d2a-90fa-65ee1f4d7348::t1` | `POS_exact_entity_success_control` | Heart-Shaped Box / Nirvana | `siglip_visual` | 1 | 1 | `bm25` | 1 | 1 | 1 |
| `3664db63-1623-4ae7-9910-dd8bc3c2bd83::t1` | `POS_exact_entity_success_control` | No Scrubs / TLC | `siglip_visual` | 1 | 1 | `bm25` | 1 | 1 | 1 |
| `7b550636-72fe-490e-ad38-a1912d08449f::t1` | `POS_exact_entity_success_control` | Believe / Cher | `siglip_visual` | 1 | 1 | `bm25` | 1 | 1 | 1 |
| `737a65cf-9c45-4b1d-910d-2f1f1ef5eab7::t8` | `POS_clean_final_hit_control` | Feel Good Inc / Gorillaz | `siglip_visual` | 1 | 1 | `lookup.resolved_artist_discography` | 1 | 1 | 1 |
| `4a02d862-623b-4fab-a42c-2905f31a96db::t1` | `POS_clean_final_hit_control` | Dreams - 2004 Remaster / Fleetwood Mac | `siglip_visual` | 1 | 1 | `lookup.era_popularity` | 1 | 1 | 1 |
| `5b44bff3-76ed-495e-9dc1-0f075e3d178b::t1` | `POS_clean_final_hit_control` | Dreams - 2004 Remaster / Fleetwood Mac | `siglip_visual` | 8 | 1 | `lookup.era_popularity` | 1 | 1 | 1 |
| `a61b366c-8cf5-48ad-a13f-181c033b9d89::t2` | `POS_clean_final_hit_control` | Pumped Up Kicks / Foster The People | `siglip_visual` | 330 | 177 | `bm25` | 0 | 0 | 0 |
| `55388720-92b7-4972-9bb2-beb37c33c86b::t1` | `POS_clean_final_hit_control` | Ivy / Frank Ocean | `siglip_visual` | 2 | 1 | `bm25` | 1 | 1 | 1 |
| `13552d56-f3d8-443a-9272-11ec16c80fa1::t1` | `POS_clean_final_hit_control` | Congratulations / Quavo, Post Malone | `siglip_visual` | 372 | 185 | `bm25` | 0 | 0 | 0 |
| `737a65cf-9c45-4b1d-910d-2f1f1ef5eab7::t3` | `POS_clean_final_hit_control` | DARE / Gorillaz | `siglip_visual` | 1 | 3 | `lookup.resolved_artist_discography` | 1 | 1 | 1 |
| `93199894-d3db-4335-8278-e1be175944e4::t1` | `POS_clean_final_hit_control` | Even Flow / Pearl Jam | `siglip_visual` | 1 | 1 | `bm25` | 1 | 1 | 1 |
| `a9b423bf-d05c-418d-98af-2a3b1e1d7917::t1` | `POS_clean_final_hit_control` | It Was A Good Day / Ice Cube | `siglip_visual` | 2 | 1 | `lookup.resolved_artist_discography` | 1 | 1 | 1 |
| `5080d5a0-336e-4bd1-b5bc-4cc611983429::t1` | `POS_clean_final_hit_control` | Rock with You - Single Version / Michael Jackson | `siglip_visual` | 1 | 1 | `bm25` | 1 | 1 | 1 |
