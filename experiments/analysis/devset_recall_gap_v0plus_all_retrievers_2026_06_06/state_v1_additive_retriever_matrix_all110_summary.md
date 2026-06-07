# State V1 Additive Retriever Branch Matrix - Focused 110

Scope: frozen V1 state/projection, focused 110 state-gap pack, candidate recall only. This report measures additive union over protected saved baseline pools plus new or improved branch pools. It does not optimize RRF, final ranking, full devset, or leaderboard score.

## Headline

- Protected saved-trace baseline: union@20=60/110 (54.5%), union@50=60/110 (54.5%), union@100=60/110 (54.5%).
- all_candidate_recall: additive union@20=66/110 (60.0%), @50=74/110 (67.3%), @100=82/110 (74.5%), top-20 rescues=6, additive regressions=0.
- all_synthetic_recall: additive union@20=64/110 (58.2%), @50=69/110 (62.7%), @100=69/110 (62.7%), top-20 rescues=4, additive regressions=0.
- all_candidate_plus_synthetic_or: additive union@20=70/110 (63.6%), @50=81/110 (73.6%), @100=86/110 (78.2%), top-20 rescues=10, additive regressions=0.
- existing_modal_plus_synthetic_or: additive union@20=71/110 (64.5%), @50=82/110 (74.5%), @100=88/110 (80.0%), top-20 rescues=11, additive regressions=0.

Read: the best practical existing-source branch family already improves additive union@20 by 6 turns. The new synthetic branches add another measured lift, but even the full diagnostic OR reaches 71/110 at union@20 and 88/110 at union@100, so candidate recall is not solved by branch gating alone.

## Variant Matrix

| Variant | Family | Branch @20 | Add @20 | Add @50 | Add @100 | Rescued @20 | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| `current_config` | existing_modal | 50.0% | 66/110 (60.0%) | 72/110 (65.5%) | 81/110 (73.6%) | 6 | diagnostic only |
| `bm25_lookup` | existing_modal | 26.4% | 61/110 (55.5%) | 61/110 (55.5%) | 62/110 (56.4%) | 1 | diagnostic only |
| `bm25_discography` | existing_modal | 21.8% | 60/110 (54.5%) | 60/110 (54.5%) | 61/110 (55.5%) | 0 | diagnostic only |
| `bm25_era_popularity` | existing_modal | 25.5% | 61/110 (55.5%) | 61/110 (55.5%) | 62/110 (56.4%) | 1 | diagnostic only |
| `centroid_style` | existing_modal | 42.7% | 64/110 (58.2%) | 66/110 (60.0%) | 67/110 (60.9%) | 4 | diagnostic only |
| `centroid_all` | existing_modal | 27.3% | 61/110 (55.5%) | 61/110 (55.5%) | 63/110 (57.3%) | 1 | diagnostic only |
| `centroid_all_similar` | existing_modal | 42.7% | 64/110 (58.2%) | 66/110 (60.0%) | 67/110 (60.9%) | 4 | diagnostic only |
| `clap_all` | existing_modal | 28.2% | 63/110 (57.3%) | 63/110 (57.3%) | 66/110 (60.0%) | 3 | diagnostic only |
| `clap_centroid` | existing_modal | 44.5% | 66/110 (60.0%) | 68/110 (61.8%) | 71/110 (64.5%) | 6 | diagnostic only |
| `qwen06_intent_attr_enriched` | existing_modal | 36.4% | 61/110 (55.5%) | 63/110 (57.3%) | 64/110 (58.2%) | 1 | diagnostic only |
| `qwen8_intent_attr_enriched` | existing_modal | 35.5% | 61/110 (55.5%) | 65/110 (59.1%) | 71/110 (64.5%) | 1 | diagnostic only |
| `all_candidate_recall` | existing_modal | 50.9% | 66/110 (60.0%) | 74/110 (67.3%) | 82/110 (74.5%) | 6 | keep as existing-source additive baseline; it rescues protected misses without replacing saved pools |
| `qwen06_clap_centroid_branch_rules` | existing_modal | 44.5% | 67/110 (60.9%) | 72/110 (65.5%) | 77/110 (70.0%) | 7 | defer for ranking goal; not a candidate-recall solution by itself |
| `all_candidate_branch_rules` | existing_modal | 46.4% | 67/110 (60.9%) | 76/110 (69.1%) | 85/110 (77.3%) | 7 | defer for ranking goal; additive can rescue unique turns, but replacement branch-only recall is weaker |
| `tag_popularity_alias` | synthetic_local | 10.0% | 61/110 (55.5%) | 61/110 (55.5%) | 61/110 (55.5%) | 1 | defer; tiny top-20 lift and broad popularity bias risk |
| `era_tag_popularity` | synthetic_local | 9.1% | 61/110 (55.5%) | 62/110 (56.4%) | 62/110 (56.4%) | 1 | defer; small lift, era filtering is too blunt as a standalone branch |
| `same_album_fanout` | synthetic_local | 0.9% | 60/110 (54.5%) | 60/110 (54.5%) | 60/110 (54.5%) | 0 | reject for this pack; no additive @20 rescue |
| `artist_tag_neighbor_popularity` | synthetic_local | 19.1% | 62/110 (56.4%) | 66/110 (60.0%) | 66/110 (60.0%) | 2 | keep/defer class-gated; best single synthetic branch, especially for style-reference/new-artist misses |
| `all_synthetic_recall` | synthetic_local | 26.4% | 64/110 (58.2%) | 69/110 (62.7%) | 69/110 (62.7%) | 4 | keep as diagnostic branch family; useful top-20 lift and better @50/@100 tail, but modest enough to gate later |
| `all_candidate_plus_synthetic_or` | diagnostic_or | 54.5% | 70/110 (63.6%) | 81/110 (73.6%) | 86/110 (78.2%) | 10 | diagnostic only |
| `existing_modal_all_variants_or` | diagnostic_or | 51.8% | 67/110 (60.9%) | 77/110 (70.0%) | 85/110 (77.3%) | 7 | diagnostic only |
| `existing_modal_plus_synthetic_or` | diagnostic_or | 55.5% | 71/110 (64.5%) | 82/110 (74.5%) | 88/110 (80.0%) | 11 | diagnostic only |

## Best Additive Result By Failure Class

| Pack | n | Protected @20 | Best Variant | Best Add @20 | Best Add @50 | Rescue @20 | Read |
|---|---:|---:|---|---:|---:|---:|---|
| `P0_good_state_ranker_near_miss_failure` | 10 | 100.0% | `all_candidate_branch_rules` | 100.0% | 100.0% | 0 | no top-20 candidate-recall lift |
| `P0_named_artist_ranker_failure` | 10 | 100.0% | `all_candidate_branch_rules` | 100.0% | 100.0% | 0 | no top-20 candidate-recall lift |
| `P0_new_artist_union20_gap_failure` | 10 | 0.0% | `all_candidate_plus_synthetic_or` | 10.0% | 30.0% | 1 | candidate source/gating helped; tail candidate needs ranking/query sharpening |
| `P0_novelty_prior_anchor_failure` | 10 | 0.0% | `existing_modal_plus_synthetic_or` | 30.0% | 50.0% | 3 | candidate source/gating helped; tail candidate needs ranking/query sharpening |
| `P0_roleless_stale_entity_failure` | 10 | 0.0% | `all_candidate_branch_rules` | 10.0% | 40.0% | 1 | candidate source/gating helped; tail candidate needs ranking/query sharpening |
| `P0_same_album_ranker_failure` | 10 | 100.0% | `all_candidate_branch_rules` | 100.0% | 100.0% | 0 | no top-20 candidate-recall lift |
| `P1_positive_tag_retrieval_gap_failure` | 10 | 0.0% | `all_candidate_branch_rules` | 20.0% | 50.0% | 2 | candidate source/gating helped; tail candidate needs ranking/query sharpening |
| `P1_rejection_guardrail_failure` | 10 | 100.0% | `all_candidate_branch_rules` | 100.0% | 100.0% | 0 | no top-20 candidate-recall lift |
| `P1_temporal_constraint_failure` | 10 | 0.0% | `all_candidate_plus_synthetic_or` | 40.0% | 50.0% | 4 | candidate source/gating helped; tail candidate needs ranking/query sharpening |
| `POS_clean_final_hit_control` | 10 | 100.0% | `all_candidate_branch_rules` | 100.0% | 100.0% | 0 | no top-20 candidate-recall lift |
| `POS_exact_entity_success_control` | 10 | 100.0% | `all_candidate_branch_rules` | 100.0% | 100.0% | 0 | no top-20 candidate-recall lift |

## Rescued Examples

Examples below are protected-baseline misses at @20 that become additive hits at @20 under `existing_modal_plus_synthetic_or`.

- `ab5eac17-909e-4271-8cf9-40c06b27ee56::t2` (`P0_new_artist_union20_gap_failure`): GT=Sparks / Hilary Duff; best=all_synthetic_recall `analysis.era_tag_popularity` rank=7; user='Oh, "IDGAF"! That's a good one, it was definitely super popular back then. Let me listen again... Hmm, it's not quite the one I'm thinking of, but it's really close in vibe! The one I'm remembering felt a bit more upb...'
- `8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6` (`P0_novelty_prior_anchor_failure`): GT=Exit Theme (feat. Astronautalis & Lotte Kestner) / Astronautalis, Sadistik, Lotte Kestner; best=centroid_all_similar `centroid.anchor_tracks.audio_laion_clap` rank=1; user='Yes, 'Virginia Woolf' is another excellent choice from Sadistik, really hits those deep, introspective notes. I'm clearly a big fan of his work. But I was hoping to branch out a little. Can you recommend any *differen...'
- `d6e50fb5-a135-4008-80b6-d0be434369ac::t3` (`P0_novelty_prior_anchor_failure`): GT=Volare (Nel Blu Di Pinto Di Blu) - 1998 - Remastered / Dean Martin; best=bm25_lookup `lookup.era_popularity` rank=9; user='Yes, this is absolutely perfect! Frank Sinatra's 'In The Wee Small Hours Of The Morning' really captures that nostalgic, contemplative mood I was looking for, with the classic vocals and instrumentation. This is exact...'
- `38d8ba41-a4ea-48ea-b460-bd93d164302a::t4` (`P0_novelty_prior_anchor_failure`): GT=Woo Hah!! Got You All In Check / Busta Rhymes; best=qwen06_clap_centroid_branch_rules `centroid.anchor_tracks.audio_laion_clap` rank=14; user='Yeah, M.O.P. is pure raw energy! "Cold as Ice" is a banger, definitely keeps that gritty East Coast sound going strong. Give me another one that brings that same kind of raw, uncompromising street vibe from the 90s.'
- `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` (`P0_roleless_stale_entity_failure`): GT=Armature / Emptyset; best=clap_sonic `dense.clap_text.sonic.audio_laion_clap` rank=12; user='Yes! "Pallbearer" is absolutely brutal, exactly the kind of intricate and relentless breakcore I was hoping for. Great pick! Can you recommend something with a similar raw power and darkness, but maybe a bit more stri...'
- `a2cface7-c4fc-4eb5-80b2-e0c516093732::t3` (`P1_positive_tag_retrieval_gap_failure`): GT=The City Is At War / Cobra Starship; best=qwen06_clap_centroid_branch_rules `centroid.anchor_tracks.cf_bpr` rank=1; user='Okay, that album art is super intense and cool, definitely more like what I meant visually! The song is powerful too. But can we get something with that same kind of visually striking, bold artwork, but the music itse...'
- `13066d2c-2d5e-4162-b3dc-354ecef3aff5::t5` (`P1_positive_tag_retrieval_gap_failure`): GT=You Know What I Mean / Cults; best=qwen06_clap_centroid_branch_rules `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b` rank=11; user='Yeah, that's a good one! "Jerk It Out" is exactly the kind of raw, driving sound I was thinking of. For the next step, how about something from the late 2000s or early 2010s that has a strong indie rock or post-punk r...'
- `f2d85aa5-2086-4b1e-9974-d188c43621db::t8` (`P1_temporal_constraint_failure`): GT=Leraine / Kettel; best=qwen06_clap_centroid_branch_rules `dense.clap_text.sonic_nl_enriched.audio_laion_clap` rank=3; user='Unfortunately, 'Sleep Paralysis' is not what I'm looking for at all. The mood is too dark and harsh, not dreamy or serene like the late 2000s ambient electronic I'm trying to find. Also, the era is still off. I'm spec...'
- `d5fcb591-3744-4ebb-9d1a-5c57c314b7d0::t5` (`P1_temporal_constraint_failure`): GT=Love Train / The O'Jays; best=all_synthetic_recall `analysis.artist_tag_neighbor_popularity` rank=4; user='Yes! "He's the Greatest Dancer" is such a jam! That's exactly the kind of funky, soulful sound from the late 70s I'm looking for. What else do you have from that golden era of R&B?'
- `3676005d-5b7c-4c48-9b73-3e10dd509c07::t3` (`P1_temporal_constraint_failure`): GT=Conquest of Paradise / Vangelis; best=all_synthetic_recall `analysis.tag_popularity_alias` rank=5; user='YES! That's 'Divano' by ERA! That's exactly the quintessential early 2000s sound I was searching for. You nailed it! Thank you so much! Can you suggest other instrumental tracks that have a similar epic or new-age feel?'
- `71bb177a-dab1-4bbc-8508-22d809b05c31::t6` (`P1_temporal_constraint_failure`): GT=Constant Craving - Remastered / k.d. lang; best=all_synthetic_recall `analysis.artist_tag_neighbor_popularity` rank=5; user='Yes, Natalie Merchant is a great pick! 'Wonder' definitely fits that introspective and emotionally resonant style. Can you suggest another iconic female artist from the 90s who has a similar thoughtful, storytelling a...'

## Still Missed

Top-20 misses under the strongest diagnostic OR. These are the turns that should drive the next candidate-source or query-design work.

- `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6` (`P0_new_artist_union20_gap_failure`): GT=Without You / Christina Aguilera; best=None `None` rank=none<=100; why=no protected/existing/synthetic branch placed GT in top100; current sources or compiled signal are insufficient; user='Another fantastic Michael Jackson track! 'Will You Be There' is definitely a powerful and energetic song that everybody knows. These are exactly the kind of widely loved, feel-good hits I enjoy. What other well-known ...'
- `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` (`P0_roleless_stale_entity_failure`): GT=Shaft / Kashmere Stage Band; best=None `None` rank=none<=100; why=no protected/existing/synthetic branch placed GT in top100; current sources or compiled signal are insufficient; user='Yes! That's a classic, I know that one well! It definitely fits the vibe of what I was looking for. It's got that undeniable groove.'
- `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` (`P0_roleless_stale_entity_failure`): GT=I Believe in a Thing Called Love / The Darkness; best=None `None` rank=none<=100; why=no protected/existing/synthetic branch placed GT in top100; current sources or compiled signal are insufficient; user='Oh my goodness, that's a very interesting choice! "I Write Sins Not Tragedies" definitely has a strong story. I remember a song like that, with a wedding drama. Can you remind me of any specific lines about a bartende...'
- `ad5348a7-d3bc-4882-bfca-54aa655eac96::t5` (`P1_positive_tag_retrieval_gap_failure`): GT=Glitter / Tyler, The Creator; best=None `None` rank=none<=100; why=no protected/existing/synthetic branch placed GT in top100; current sources or compiled signal are insufficient; user='Dope! "REDMERCEDES" is definitely on point with that vibrant energy, both in the song and the cover. These are exactly the kind of tracks I was looking for, where the artwork really brings out the music's vibe. What e...'
- `5ee0dbbc-c1d1-4bed-ba09-7dafeec198bc::t8` (`P0_new_artist_union20_gap_failure`): GT=You Reposted in the Wrong Neighborhood I Glue70 Mashup / Shokk; best=qwen8_intent_attr_enriched `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` rank=22; why=GT appears in candidate tail 21-50; branch ranking/query quality is the bottleneck; user='Dude, 'The Ultimate Showdown of Ultimate Destiny' is awesome! That song is a classic, the story is just so over-the-top and hilarious. You really crushed it with these meme and goofy song recommendations! Thanks! What...'
- `daeef24e-b041-4140-9101-882820c63408::t7` (`P0_novelty_prior_anchor_failure`): GT=The Analog Kid / Rush; best=qwen8_metadata_intent `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` rank=24; why=GT appears in candidate tail 21-50; branch ranking/query quality is the bottleneck; user='Okay, it sounds like there's a problem with 'Tom Sawyer'. That's a bummer. Can you please play 'The Spirit of Radio' by Rush instead?'
- `3676005d-5b7c-4c48-9b73-3e10dd509c07::t1` (`P1_temporal_constraint_failure`): GT=Breath and Life / Audiomachine; best=qwen8_attributes `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` rank=26; why=GT appears in candidate tail 21-50; branch ranking/query quality is the bottleneck; user='I'm trying to remember a really powerful, orchestral song from the early 2000s, like something from a movie score.'
- `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7` (`P0_roleless_stale_entity_failure`): GT=I Can't Go to Sleep / Wu-Tang Clan; best=all_candidate_recall `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b` rank=27; why=GT appears in candidate tail 21-50; branch ranking/query quality is the bottleneck; user='This is exactly the kind of intricate storytelling I'm digging into. The way Kendrick builds a narrative and develops characters, with the music itself being a part of that journey, is just next level. 'untitled 03' d...'
- `0b9d547f-e748-464a-90e2-2199149f915c::t6` (`P0_roleless_stale_entity_failure`): GT=Give It To Me Baby / Rick James; best=all_candidate_branch_rules `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` rank=30; why=GT appears in candidate tail 21-50; branch ranking/query quality is the bottleneck; user='Yes! "Can You Feel the Force" is awesome, such a great track. That's exactly the kind of energy I'm looking for. What are some other high-energy, classic disco or funk tracks from that late 70s to early 80s period?'
- `464477e4-f186-47fb-8cb0-55691c8b8f57::t6` (`P1_positive_tag_retrieval_gap_failure`): GT=Where Eagles Dare / Glenn Danzig, Misfits; best=all_synthetic_recall `analysis.artist_tag_neighbor_popularity` rank=34; why=GT appears in candidate tail 21-50; branch ranking/query quality is the bottleneck; user='Yes, The Clash! "White Riot" is a perfect example of that raw UK punk energy. These are all legendary tracks. What about something equally influential, but from the earlier wave of punk, like proto-punk, or something ...'
- `1c567917-f931-4609-9695-a9c0f8e39f3d::t2` (`P1_positive_tag_retrieval_gap_failure`): GT=Arregaçada / U Can't Touch This / Banda Uó; best=qwen06_metadata `dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b` rank=35; why=GT appears in candidate tail 21-50; branch ranking/query quality is the bottleneck; user='That's a good start! Anitta is definitely on point for contemporary pop. What about something more recent and upbeat, specifically from the 'tecno brega' or 'funk carioca' scenes?'
- `e66c6a88-88ba-4117-9114-363bfa96294a::t7` (`P0_roleless_stale_entity_failure`): GT=Test Drive / John Powell; best=centroid_all_similar `centroid.anchor_tracks.audio_laion_clap` rank=36; why=GT appears in candidate tail 21-50; branch ranking/query quality is the bottleneck; user='This is absolutely perfect! "Anthem of the World" is exactly the powerful and uplifting epic music I was looking for. Can you give me more recommendations that are similar to this or Two Steps from Hell?'
- `dd686049-59ba-439b-8c51-949a0876e1b3::t1` (`P1_positive_tag_retrieval_gap_failure`): GT=Vengeance (The Return of the Night Driving Avenger) [Bonus Track] / Perturbator; best=all_candidate_branch_rules `dense.qwen_8b.intent.metadata_qwen3_embedding_8b` rank=38; why=GT appears in candidate tail 21-50; branch ranking/query quality is the bottleneck; user='I'm looking for a really intense electronic song, something that makes you feel like you're speeding through a cyberpunk city at night.'
- `ba68a3cc-5278-4680-917a-4ca66d33ef31::t5` (`P0_new_artist_union20_gap_failure`): GT=Buttons / The Pussycat Dolls; best=all_synthetic_recall `analysis.artist_tag_neighbor_popularity` rank=45; why=GT appears in candidate tail 21-50; branch ranking/query quality is the bottleneck; user='Yes, this selection is great! "Wannabe" is iconic, it really gets me in a powerful mood. I think these are all perfect for what I asked for. What else do you have that's like these? Maybe some other pop artists from t...'
- `c7a965c3-cd7f-46f6-b166-9dce9a800e0a::t3` (`P0_novelty_prior_anchor_failure`): GT=S&M / Rihanna; best=all_synthetic_recall `analysis.artist_tag_neighbor_popularity` rank=49; why=GT appears in candidate tail 21-50; branch ranking/query quality is the bottleneck; user='Yes! That's exactly the track! 'Toxic' by Britney Spears always makes me feel that way. It's so iconic and brings back all those confident, dancing vibes. You nailed it! Thanks! Can you recommend something else with a...'
- `5f085552-b56b-440e-830b-b4e40b58f854::t6` (`P0_novelty_prior_anchor_failure`): GT=Redneck Yacht Club / Craig Morgan; best=qwen06_clap_centroid_branch_rules `dense.clap_text.sonic_nl.audio_laion_clap` rank=51; why=GT appears in candidate tail 51-100; source can express it but top20 ordering is weak; user='Yes, Tim McGraw definitely brings that big energy! That's another great anthem from that era. Keep them coming – can you find me another upbeat, high-energy country track from the late 90s or early 2000s that really g...'
- `54cda581-3b2e-4245-a479-1a27589760d2::t3` (`P1_positive_tag_retrieval_gap_failure`): GT=Deliberation - Studio / Katatonia; best=all_candidate_branch_rules `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b` rank=52; why=GT appears in candidate tail 51-100; source can express it but top20 ordering is weak; user='This is getting really close! The album art for "Character" by Dark Tranquillity is definitely in the right ballpark with the ruined city and bleak atmosphere. However, the one I'm thinking of had a somewhat more abst...'
- `5a0dfe9d-ec8a-4449-97df-35535cbf162f::t1` (`P1_positive_tag_retrieval_gap_failure`): GT=A New World / Harry Gregson-Williams; best=qwen8_metadata `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b` rank=60; why=GT appears in candidate tail 51-100; source can express it but top20 ordering is weak; user='Play something epic and orchestral, like a movie soundtrack, for background music.'

## Recommendations

- keep: protected-baseline additive harness - it reproduces the saved trace baseline exactly and enforces no-regression additive accounting.
- keep: all_candidate_recall as the existing-source additive baseline - baseline+all_candidate improves union@20 from 60/110 to 66/110 without replacing protected pools.
- keep/defer production gating: all_synthetic_recall and artist_tag_neighbor_popularity - synthetic branches add 4 top-20 rescues and 9 @50/@100 rescues; useful but not enough alone.
- defer: branch-local post-rank rules - they can add unique candidates additively, but replacement branch-only recall is weaker; handle in ranking/fusion goal.
- reject for now: same_album_fanout standalone - 0 additive top-20 rescues on this focused pack.
- needs new source/query design: remaining additive @100 misses - existing protected+modal+synthetic OR still misses a large tail; several classes need stronger source representation, not just gating.

## Reproduction

- Protected baseline cache: `state_v1_protected_baseline_branch_pools_top100.json`. It reproduces saved trace union@20 and union@100 exactly for the 110 pack.
- New synthetic run output: `state_v1_additive_synthetic_branches_all110.json` / `.md` / `.csv`.
- Saved existing branch inputs: `state_v1_matrix_modal_all110_*.json`. These are reused as branch-only hit evidence; no embedding rerun is needed for the additive OR report.
- Invariant: `additive_regressed@20` must be 0. If it is non-zero, the harness is replacing protected baseline pools instead of OR-ing with them.
