# State V1 Retriever Matrix: 110 Focused Turns

Frozen inputs: `state_experiment_pack.json` (110 turns) and `state_v1_goal_current_all110_reprojected_audit.jsonl`. State extraction/projection was not changed during this goal; all runs use existing retriever/compiler mechanisms plus analysis-only branch-local variants.

## Bottom Line

- Primary metric did not improve: saved trace `union@20` is 60/110 (0.545). The best reproduced/current broad stacks are `all_candidate_recall` at 56/110 (0.509) and `current_config` at 55/110 (0.500).
- Secondary depth did improve: `all_candidate_recall` reaches `union@50` 65/110 (0.591) and `union@100` 74/110 (0.673), versus saved trace 60/110 at both cutoffs in this pack.
- Branch-local post-rank rules are negative: `all_candidate_branch_rules` falls to `union@20` 51/110 (0.464). Do not promote those hard/soft branch reordering rules as-is.
- The gap is not only missing state. Existing mechanisms can express some missed targets at depth, but top-20 placement and route gating are weak. Some classes still need a better candidate source.

## Overall Results

| variant | union@20 | union@50 | union@100 | final@20 | decision |
|---|---:|---:|---:|---:|---|
| `official_trace_baseline` | 0.545 | 0.545 | 0.545 | 0.182 | reference baseline from saved trace pack |
| `all_candidate_recall` | 0.509 | 0.591 | 0.673 | 0.309 | defer/gate: depth lift, top-20 regression overall |
| `current_config` | 0.500 | 0.573 | 0.664 | 0.282 | defer/gate: depth lift, top-20 regression overall |
| `all_candidate_branch_rules` | 0.464 | 0.555 | 0.655 | 0.309 | do not promote: branch-local rules hurt top-20 |
| `clap_centroid` | 0.445 | 0.491 | 0.545 | 0.291 | candidate for novelty/anchor-gated branch, not global |
| `qwen06_clap_centroid_branch_rules` | 0.445 | 0.509 | 0.573 | 0.291 | do not promote: branch-local rules hurt top-20 |
| `centroid_all_similar` | 0.427 | 0.473 | 0.509 | 0.355 | candidate for novelty/anchor-gated branch, not global |
| `centroid_style` | 0.427 | 0.473 | 0.509 | 0.355 | candidate for novelty/anchor-gated branch, not global |
| `qwen06_intent_attr_enriched` | 0.364 | 0.409 | 0.445 | 0.264 | keep diagnostic; useful depth/controls but weak standalone |
| `qwen06_metadata_intent` | 0.355 | 0.400 | 0.436 | 0.255 | keep diagnostic; useful depth/controls but weak standalone |
| `qwen8_intent_attr_enriched` | 0.355 | 0.427 | 0.509 | 0.255 | keep diagnostic; useful depth/controls but weak standalone |
| `qwen8_metadata_intent` | 0.345 | 0.418 | 0.473 | 0.236 | keep diagnostic; useful depth/controls but weak standalone |
| `qwen8_metadata` | 0.336 | 0.373 | 0.445 | 0.236 | keep diagnostic; useful depth/controls but weak standalone |
| `qwen06_metadata` | 0.309 | 0.355 | 0.400 | 0.236 | keep diagnostic; useful depth/controls but weak standalone |
| `clap_all` | 0.282 | 0.309 | 0.373 | 0.200 | keep diagnostic; useful with centroids only |
| `qwen8_attributes_enriched` | 0.282 | 0.318 | 0.391 | 0.245 | keep diagnostic; useful depth/controls but weak standalone |
| `centroid_all` | 0.273 | 0.300 | 0.345 | 0.236 | keep diagnostic; similar-artist anchors matter |
| `centroid_audio` | 0.273 | 0.300 | 0.336 | 0.236 | keep diagnostic; similar-artist anchors matter |
| `centroid_cf` | 0.273 | 0.300 | 0.336 | 0.236 | keep diagnostic; similar-artist anchors matter |
| `centroid_image` | 0.273 | 0.300 | 0.345 | 0.236 | keep diagnostic; similar-artist anchors matter |
| `clap_sonic` | 0.273 | 0.300 | 0.345 | 0.227 | keep diagnostic; useful with centroids only |
| `clap_sonic_nl_enriched` | 0.273 | 0.300 | 0.364 | 0.227 | keep diagnostic; useful with centroids only |
| `qwen06_attributes` | 0.273 | 0.309 | 0.355 | 0.236 | keep diagnostic; useful depth/controls but weak standalone |
| `qwen06_attributes_enriched` | 0.273 | 0.309 | 0.355 | 0.236 | keep diagnostic; useful depth/controls but weak standalone |
| `qwen06_lyrics` | 0.273 | 0.300 | 0.345 | 0.236 | keep diagnostic; useful depth/controls but weak standalone |
| `qwen8_attributes` | 0.273 | 0.309 | 0.400 | 0.236 | keep diagnostic; useful depth/controls but weak standalone |
| `bm25_lookup` | 0.264 | 0.291 | 0.336 | 0.227 | keep as support path; weak standalone |
| `clap_sonic_nl` | 0.264 | 0.291 | 0.364 | 0.227 | keep diagnostic; useful with centroids only |
| `bm25_era_popularity` | 0.255 | 0.282 | 0.327 | 0.227 | keep as support path; weak standalone |
| `bm25_discography` | 0.218 | 0.236 | 0.273 | 0.191 | keep as support path; weak standalone |
| `bm25_only` | 0.209 | 0.227 | 0.264 | 0.191 | keep as support path; weak standalone |

## Per-Class Read

| class | baseline u20 | best single | best single u20/u50/u100 | best combined | combined u20/u50/u100 | all-candidate u20/u50/u100 | read |
|---|---:|---|---:|---|---:|---:|---|
| `P0_good_state_ranker_near_miss_failure` | 1.000 | `clap_centroid` | 1.000/1.000/1.000 | `clap_centroid` | 1.000/1.000/1.000 | 1.000/1.000/1.000 | Candidate is already present. This is ranking, not recall. |
| `P0_named_artist_ranker_failure` | 1.000 | `clap_centroid` | 0.800/0.800/0.800 | `clap_centroid` | 0.800/0.800/0.800 | 0.800/0.800/0.800 | Saved trace protects this class; reproduced broad stacks regress. Do not replace exact/named-artist path globally. |
| `P0_new_artist_union20_gap_failure` | 0.000 | `qwen8_attributes` | 0.000/0.000/0.200 | `clap_centroid` | 0.000/0.000/0.100 | 0.000/0.100/0.300 | Existing mechanisms mostly cannot top-20 this class; even all-candidate only reaches 0.3 by @100. Consider new candidate source or stronger novelty/artist-similarity retrieval. |
| `P0_novelty_prior_anchor_failure` | 0.000 | `clap_centroid` | 0.300/0.300/0.500 | `clap_centroid` | 0.300/0.300/0.500 | 0.300/0.300/0.600 | Existing centroids/CLAP can recover 3/10 at @20 and 6/10 by @100. This is a route-gating/anchor-use opportunity. |
| `P0_roleless_stale_entity_failure` | 0.000 | `clap_centroid` | 0.100/0.200/0.200 | `clap_centroid` | 0.100/0.200/0.200 | 0.100/0.300/0.400 | Some depth headroom, weak top-20. State roles help, but retriever/ranker needs to stop treating stale positives as current exact anchors. |
| `P0_same_album_ranker_failure` | 1.000 | `qwen06_intent_attr_enriched` | 0.500/0.600/0.700 | `qwen06_clap_centroid_branch_rules` | 0.700/0.800/0.800 | 0.700/0.800/0.900 | Saved trace protects this class; all-candidate regresses top-20 but has depth. Needs ranker features, not candidate replacement. |
| `P1_positive_tag_retrieval_gap_failure` | 0.000 | `clap_centroid` | 0.100/0.200/0.200 | `qwen06_clap_centroid_branch_rules` | 0.200/0.400/0.600 | 0.100/0.500/0.700 | Clear depth headroom: all-candidate 0.5 @50 and 0.7 @100. Candidate exists but ranking/branch weights are weak. |
| `P1_rejection_guardrail_failure` | 1.000 | `qwen8_metadata` | 0.400/0.500/0.600 | `all_candidate_recall` | 0.700/0.700/0.700 | 0.700/0.700/0.700 | Saved trace has union coverage; branch-local rules lose many hits. Rejection should remain a final/assertion guardrail, not broad branch reranking. |
| `P1_temporal_constraint_failure` | 0.000 | `clap_centroid` | 0.100/0.100/0.100 | `clap_centroid` | 0.100/0.100/0.100 | 0.100/0.200/0.200 | Existing era/popularity path is not enough. This likely needs better era/popularity retrieval or metadata-derived candidate source. |
| `POS_clean_final_hit_control` | 1.000 | `qwen8_attributes` | 0.800/0.800/0.800 | `clap_centroid` | 0.800/0.800/0.800 | 0.800/0.800/0.800 | Regression control: broad stacks lose 2/10. Gating is required. |
| `POS_exact_entity_success_control` | 1.000 | `qwen8_attributes` | 1.000/1.000/1.000 | `clap_centroid` | 1.000/1.000/1.000 | 1.000/1.000/1.000 | Exact entity remains safe in most variants; preserve this path. |

## Rescued Examples

Saved trace missed these at union@20; `all_candidate_recall` put the GT into a branch top-20.

- `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` (`P0_roleless_stale_entity_failure`): Armature by Emptyset; best branch `dense.clap_text.sonic.audio_laion_clap` rank 12; final rank 43. User: Yes! "Pallbearer" is absolutely brutal, exactly the kind of intricate and relentless breakcore I was hoping for. Great pick! Can you recommend something with a similar raw power and darkness, but maybe a bit m... Change suggested: Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retr...
- `d6e50fb5-a135-4008-80b6-d0be434369ac::t3` (`P0_novelty_prior_anchor_failure`): Volare (Nel Blu Di Pinto Di Blu) - 1998 - Remastered by Dean Martin; best branch `lookup.era_popularity` rank 9; final rank 30. User: Yes, this is absolutely perfect! Frank Sinatra's 'In The Wee Small Hours Of The Morning' really captures that nostalgic, contemplative mood I was looking for, with the classic vocals and instrumentation. This ... Change suggested: Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metad...
- `38d8ba41-a4ea-48ea-b460-bd93d164302a::t4` (`P0_novelty_prior_anchor_failure`): Woo Hah!! Got You All In Check by Busta Rhymes; best branch `centroid.anchor_tracks.audio_laion_clap` rank 18; final rank 121. User: Yeah, M.O.P. is pure raw energy! "Cold as Ice" is a banger, definitely keeps that gritty East Coast sound going strong. Give me another one that brings that same kind of raw, uncompromising street vibe from th... Change suggested: Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metad...
- `8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6` (`P0_novelty_prior_anchor_failure`): Exit Theme (feat. Astronautalis & Lotte Kestner) by Astronautalis, Sadistik, Lotte Kestner; best branch `centroid.anchor_tracks.audio_laion_clap` rank 1; final rank 3. User: Yes, 'Virginia Woolf' is another excellent choice from Sadistik, really hits those deep, introspective notes. I'm clearly a big fan of his work. But I was hoping to branch out a little. Can you recommend any *... Change suggested: Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metad...
- `f2d85aa5-2086-4b1e-9974-d188c43621db::t8` (`P1_temporal_constraint_failure`): Leraine by Kettel; best branch `dense.clap_text.sonic_nl_enriched.audio_laion_clap` rank 7; final rank 22. User: Unfortunately, 'Sleep Paralysis' is not what I'm looking for at all. The mood is too dark and harsh, not dreamy or serene like the late 2000s ambient electronic I'm trying to find. Also, the era is still off. ... Change suggested: Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily p...
- `a2cface7-c4fc-4eb5-80b2-e0c516093732::t3` (`P1_positive_tag_retrieval_gap_failure`): The City Is At War by Cobra Starship; best branch `centroid.anchor_tracks.cf_bpr` rank 9; final rank 140. User: Okay, that album art is super intense and cool, definitely more like what I meant visually! The song is powerful too. But can we get something with that same kind of visually striking, bold artwork, but the mu... Change suggested: Improve turn-type routing and candidate generation: use listener_goal/current state, role-aware entities, tags, popularity, culture/CF affinity, and novelty profiles before spendi...

## Top-50 Headroom

These are still not union@20, but the GT is in top-50 under all-candidate. This is the cleanest evidence for route/ranking work before a new retriever.

- `e66c6a88-88ba-4117-9114-363bfa96294a::t7` (`P0_roleless_stale_entity_failure`): Test Drive by John Powell; branch `centroid.anchor_tracks.audio_laion_clap` rank 36; final rank 156. Change: Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retr...
- `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7` (`P0_roleless_stale_entity_failure`): I Can't Go to Sleep by Wu-Tang Clan; branch `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b` rank 27; final rank 664. Change: Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metad...
- `5ee0dbbc-c1d1-4bed-ba09-7dafeec198bc::t8` (`P0_new_artist_union20_gap_failure`): You Reposted in the Wrong Neighborhood I Glue70 Mashup by Shokk; branch `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` rank 22; final rank 180. Change: Improve turn-type routing and candidate generation: use listener_goal/current state, role-aware entities, tags, popularity, culture/CF affinity, and novelty profiles before spendi...
- `3676005d-5b7c-4c48-9b73-3e10dd509c07::t1` (`P1_temporal_constraint_failure`): Breath and Life by Audiomachine; branch `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` rank 27; final rank 615. Change: Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily p...
- `464477e4-f186-47fb-8cb0-55691c8b8f57::t6` (`P1_positive_tag_retrieval_gap_failure`): Where Eagles Dare by Glenn Danzig, Misfits; branch `centroid.anchor_tracks.image_siglip2` rank 35; final rank 445. Change: Improve turn-type routing and candidate generation: use listener_goal/current state, role-aware entities, tags, popularity, culture/CF affinity, and novelty profiles before spendi...
- `13066d2c-2d5e-4162-b3dc-354ecef3aff5::t5` (`P1_positive_tag_retrieval_gap_failure`): You Know What I Mean by Cults; branch `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b` rank 25; final rank 327. Change: Improve turn-type routing and candidate generation: use listener_goal/current state, role-aware entities, tags, popularity, culture/CF affinity, and novelty profiles before spendi...

## Still Missed

Saved trace missed these and all-candidate still does not surface them by union@100. Treat these as candidates for a new retrieval source or label/GT ambiguity review.

- `41367174-552b-4117-9caa-d0ba1b307d37::t2` (`P0_roleless_stale_entity_failure`): Mercy by Muse; best branch `centroid.anchor_tracks.audio_laion_clap` rank 334; final rank None. User: Yes! Twenty One Pilots is a great choice, "Stressed Out" totally has that powerful vibe I'm looking for. Can you recommend a few more songs or artists from the 2000s or 2010s that have a similar intense and em...
- `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` (`P0_roleless_stale_entity_failure`): The Carbon Stampede by Cattle Decapitation; best branch `centroid.anchor_tracks.cf_bpr` rank 137; final rank 346. User: Suffocation is always a solid listen, but I'm really looking to discover some *new* bands. Can you suggest some more recent acts that are making waves in the technical or progressive death metal scene? I'm ope...
- `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` (`P0_roleless_stale_entity_failure`): Shaft by Kashmere Stage Band; best branch `None` rank None; final rank None. User: Yes! That's a classic, I know that one well! It definitely fits the vibe of what I was looking for. It's got that undeniable groove.
- `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` (`P0_roleless_stale_entity_failure`): In the Shadows by The Rasmus; best branch `centroid.anchor_tracks.audio_laion_clap` rank 253; final rank None. User: Yes! Guano Apes! I love this song, it's so powerful. The vocalist is amazing. Do you have any other powerful rock songs, maybe with a really strong guitar riff?
- `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` (`P0_roleless_stale_entity_failure`): I Believe in a Thing Called Love by The Darkness; best branch `None` rank None; final rank None. User: Oh my goodness, that's a very interesting choice! "I Write Sins Not Tragedies" definitely has a strong story. I remember a song like that, with a wedding drama. Can you remind me of any specific lines about a ...
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` (`P0_roleless_stale_entity_failure`): Move Along by The All-American Rejects; best branch `bm25` rank 523; final rank 916. User: That's a good one, it totally brings back early 2000s pop-punk! It's got the energy, but I'm looking for something that feels a bit more... not quite heavier, but with a stronger angsty feel. Still from that e...

## Regressed Controls

These had saved-trace union@20 coverage but were lost by all-candidate. This is why broad replacement is not safe.

- `d265b5a9-af57-4070-90f5-692a960c5aaa::t8` (`P1_rejection_guardrail_failure`): Motherboard by Daft Punk; baseline branch rank 2; all-candidate branch `dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b` rank 506. Change to avoid: global replacement without exact/album/rejection gating.
- `08bea603-846a-428b-aa27-de4dfede7ba9::t8` (`P1_rejection_guardrail_failure`): Silhouette by Julia Holter; baseline branch rank 2; all-candidate branch `None` rank None. Change to avoid: global replacement without exact/album/rejection gating.
- `0fc60312-9a9d-4658-a950-06fc2441a2ac::t8` (`P1_rejection_guardrail_failure`): Music Will Untune the Sky by Have A Nice Life; baseline branch rank 2; all-candidate branch `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` rank 807. Change to avoid: global replacement without exact/album/rejection gating.
- `93199894-d3db-4335-8278-e1be175944e4::t6` (`P0_named_artist_ranker_failure`): Smells Like Teen Spirit by Nirvana; baseline branch rank 1; all-candidate branch `bm25` rank 215. Change to avoid: global replacement without exact/album/rejection gating.
- `7be411cd-f002-459e-8326-3ebe8be10b42::t6` (`P0_named_artist_ranker_failure`): Army Dreamers by Kate Bush; baseline branch rank 1; all-candidate branch `bm25` rank 420. Change to avoid: global replacement without exact/album/rejection gating.
- `19c7e5bf-0797-40c5-b798-4d024af9558d::t4` (`P0_same_album_ranker_failure`): Satisfied by Original Broadway Cast of Hamilton, Renée Elise Goldsberry; baseline branch rank 1; all-candidate branch `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` rank 79. Change to avoid: global replacement without exact/album/rejection gating.

## Keep / Revert / Defer

- Keep the matrix harness and Modal wrapper. It gives the 110-turn evidence pack, per-class summaries, and negative-control checks without running full devset.
- Do not promote `all_candidate_branch_rules` or `qwen06_clap_centroid_branch_rules`; they reduce union@20 and lose protected controls.
- Defer broad all-candidate replacement. It improves depth but loses too many baseline top-20 candidates.
- Candidate next experiment: class-gated routing. Preserve exact/named-artist/same-album/rejection/control paths; only add all-candidate/centroid/CLAP expansion for novelty, roleless-stale, and positive-tag classes.
- New retriever-needed notes: temporal and new-artist classes remain weak even by @100; positive-tag has depth and should be tackled first with route/ranking before a new retriever.

## Source Artifacts

- `state_v1_matrix_modal_all110_all_candidate.json`
- `state_v1_matrix_modal_all110_all_candidate_branch_rules.json`
- `state_v1_matrix_modal_all110_centroid.json`
- `state_v1_matrix_modal_all110_clap.json`
- `state_v1_matrix_modal_all110_current_config.json`
- `state_v1_matrix_modal_all110_lookup.json`
- `state_v1_matrix_modal_all110_qwen06.json`
- `state_v1_matrix_modal_all110_qwen06_clap_branch_rules.json`
- `state_v1_matrix_modal_all110_qwen8.json`
- `state_v1_retriever_matrix_all110_summary.json`
