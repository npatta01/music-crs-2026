# Backward Oracle: What Would Pull Focused Misses Up?

Variant audited: `promoted_feature_family`. Misses audited: **26**.

This report works backward from the GT for each promoted-family `union@20` miss. Production-valid probes use only current state/projection plus catalog metadata. `oracle_gt_clean_music_tags` uses cleaned genre/scene tags from the GT track and is only a diagnostic for whether the catalog tag surface could express the target.

## Summary

### Ideal lever counts
- `branch_local_rerank_existing_branch`: 7
- `sharper_tag_hybrid_scoring`: 6
- `branch_local_rerank_or_survivor_slots`: 6
- `do_not_optimize_invalid_or_contradictory_gt`: 3
- `promote_state_tag_popularity_alias`: 2
- `underspecified_or_new_source_needed`: 1
- `tune_state_tag_popularity_alias`: 1

### Rank bucket counts
- `deep_or_source_gap_gt_rank_gt100`: 9
- `order_gap_21_50`: 8
- `order_gap_51_100`: 6
- `absent_from_promoted_top100`: 3

## Build Order From The Backward Pass

1. **Branch-local ordering / survivor slots first**: 13 misses are already in an existing branch around ranks 21-100. The ideal retriever is not new; the GT needs a per-branch scorer using branch rank, state-tag overlap, year compatibility, popularity-if-requested, anchor-CF/audio evidence, and hard resolved exclusions.
2. **Tag hybrid second**: 9 misses show state/catalog tag overlap or a useful tag-popularity probe, but the tag surface is noisy. The ideal branch is a hybrid of BM25 tag/search text plus dense attributes over cleaned/canonical tag concepts, with specificity weighting.
3. **Do not optimize noisy GTs**: 3 misses are marked invalid or contradictory by the audit. They can test guardrails, but should not drive candidate recall work.
4. **New source only for residuals**: 1 miss is still poorly expressed after production-valid and cleaned-tag probes. That is the right place to consider catalog enrichment or a specialized embedding/source.

## Reading

- If `current_best_rank` is 21-50 or 51-100, the problem is mostly branch-local ordering or survivor slots, not state extraction.
- If a production probe is <=20, we likely already have a retriever branch that can rescue the turn with better routing or promotion.
- If only the GT-tag oracle is good, the missing piece is query-to-catalog tag mapping, not a brand-new embedding by default.
- If neither production probes nor GT-tag oracle are good, this is a real source/representation gap or a noisy GT.

## Miss Worksheet

| sample | GT | bucket | current best | ideal lever | best production probe | GT-tag oracle | overlap | read |
|---|---|---|---|---|---|---:|---|---|
| 0b9d547f::t6 | Give It To Me Baby / Rick James | deep_or_source_gap_gt_rank_gt100 | analysis.era_tag_popularity.anchor_cf_features @ 109 | `sharper_tag_hybrid_scoring` | state_fact_only_scene_era @ 2518 | 1 | funk, rock, soul | The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting. |
| 41367174::t2 | Mercy / Muse | order_gap_51_100 | analysis.tag_popularity_alias.catalog_features @ 80 | `branch_local_rerank_or_survivor_slots` | state_tag_popularity_alias @ 77 | 1 | 2010s, alt rock, alternative, alternative rock, alternative-rock, emotional,... | GT is visible at rank 80; use branch-local hybrid scoring or reserve survivor slots. |
| 10a15ba2::t7 | I Can't Go to Sleep / Wu-Tang Clan | order_gap_21_50 | dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b.catalog_features @ 29 | `branch_local_rerank_existing_branch` | state_tag_popularity_alias @ 2334 | 1 | hip hop, hip hop/rap, hip-hop, hip-hop/rap, rap | GT is already close at rank 29 in dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b.catalog_features; rescore within that branch/pool. |
| 5f29a9df::t2 | Shaft / Kashmere Stage Band | absent_from_promoted_top100 | None @ None | `sharper_tag_hybrid_scoring` | state_tag_popularity_alias @ 18216 | 1 | funk | The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting. |
| 78cdaccb::t8 | In the Shadows / The Rasmus | deep_or_source_gap_gt_rank_gt100 | centroid.anchor_tracks.audio_laion_clap.branch_local_hybrid @ 197 | `sharper_tag_hybrid_scoring` | state_fact_only_scene_era @ 4531 | 1 | alt rock, alternative, alternative rock, alternative-rock, metal, rock | The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting. |
| 88af7ec3::t2 | I Believe in a Thing Called Love / The Darkness | absent_from_promoted_top100 | None @ None | `do_not_optimize_invalid_or_contradictory_gt` | None @ None | 1 |  | Do not chase this with retrieval. Keep it as a guardrail/audit case. |
| d9a65836::t2 | Move Along / The All-American Rejects | order_gap_51_100 | dense.clap_text.sonic_nl.audio_laion_clap.branch_local_hybrid @ 97 | `branch_local_rerank_or_survivor_slots` | artist_neighbor_scene_fact @ 23 | 1 | alt rock, alternative, alternative rock, alternative-rock, classic punk, emo... | GT is visible at rank 97; use branch-local hybrid scoring or reserve survivor slots. |
| c7a965c3::t3 | S&M / Rihanna | deep_or_source_gap_gt_rank_gt100 | analysis.artist_tag_neighbor_popularity.anchor_cf_features @ 120 | `promote_state_tag_popularity_alias` | state_tag_popularity_alias @ 30 | 1 | energetic, female, sex | state_tag_popularity_alias would put GT at rank 30; promote/tune this production-valid branch. |
| 88beb200::t6 | Used To / Lil Wayne, Drake | order_gap_21_50 | dense.clap_text.sonic.audio_laion_clap.anchor_cf_features @ 48 | `do_not_optimize_invalid_or_contradictory_gt` | same_album_fanout @ 14 | 1 | hip hop, hip hop/rap, hip-hop, hip-hop/rap, love, rap | Do not chase this with retrieval. Keep it as a guardrail/audit case. |
| 8dc4c630::t7 | Transcentience / Animals As Leaders | deep_or_source_gap_gt_rank_gt100 | dense.qwen_8b.intent.metadata_qwen3_embedding_8b.anchor_cf_features @ 147 | `underspecified_or_new_source_needed` | artist_neighbor_scene_fact @ 15452 | 6383 |  | No current production-valid probe sees the GT well; keep as candidate for new source audit. |
| 380a5ed5::t3 | God Hates a Coward / Tomahawk | deep_or_source_gap_gt_rank_gt100 | bm25.catalog_features @ 126 | `promote_state_tag_popularity_alias` | state_tag_popularity_alias @ 23 | 1 | alt rock, alternative, alternative rock, alternative-rock, avant-garde, exper... | state_tag_popularity_alias would put GT at rank 23; promote/tune this production-valid branch. |
| cdd374ea::t3 | Gib ihn einfach (Dies das 2) / Ghanaian Stallion | deep_or_source_gap_gt_rank_gt100 | dense.qwen_8b.attributes.attributes_qwen3_embedding_8b.catalog_features @ 212 | `sharper_tag_hybrid_scoring` | state_fact_only_scene_era @ 6502 | 72 | hip hop, hip-hop, rap | The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting. |
| 5ee0dbbc::t8 | You Reposted in the Wrong Neighborhood I Glue70 Mashup / Shokk | order_gap_21_50 | dense.qwen_8b.intent.metadata_qwen3_embedding_8b.anchor_cf_features @ 22 | `branch_local_rerank_existing_branch` | None @ None | 1129 |  | GT is already close at rank 22 in dense.qwen_8b.intent.metadata_qwen3_embedding_8b.anchor_cf_features; rescore within that branch/pool. |
| 5861afef::t4 | Carmesí / Vicente Garcia | order_gap_51_100 | dense.qwen_8b.attributes.attributes_qwen3_embedding_8b.anchor_cf_features @ 74 | `branch_local_rerank_or_survivor_slots` | state_tag_popularity_alias @ 1104 | 491 | latin | GT is visible at rank 74; use branch-local hybrid scoring or reserve survivor slots. |
| 15b1caf3::t6 | Hong Kong 2046 / Hong Kong Express | deep_or_source_gap_gt_rank_gt100 | dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b.catalog_features @ 347 | `sharper_tag_hybrid_scoring` | state_fact_only_scene_era @ 3512 | 1 | edm, electronic, electronica | The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting. |
| 907921a3::t7 | Sunrise - Slow Hands Remix / Kasper Bjørke | order_gap_21_50 | centroid.anchor_tracks.cf_bpr.branch_local_hybrid @ 36 | `branch_local_rerank_existing_branch` | artist_neighbor_scene_fact @ 2797 | 1878 | dance, edm, electronic, electronica, freestyle mix, house | GT is already close at rank 36 in centroid.anchor_tracks.cf_bpr.branch_local_hybrid; rescore within that branch/pool. |
| 324ddfb5::t3 | Acknowledge / Masta Ace | order_gap_51_100 | dense.qwen_8b.metadata.metadata_qwen3_embedding_8b.branch_local_hybrid @ 81 | `branch_local_rerank_or_survivor_slots` | artist_neighbor_scene_fact @ 128 | 1 | east coast hip hop, hip hop, hip hop/rap, hip-hop, hip-hop/rap, rap, undergro... | GT is visible at rank 81; use branch-local hybrid scoring or reserve survivor slots. |
| ba68a3cc::t5 | Buttons / The Pussycat Dolls | order_gap_21_50 | analysis.artist_tag_neighbor_popularity.anchor_cf_features @ 34 | `branch_local_rerank_existing_branch` | artist_neighbor_scene_fact @ 50 | 1 | female, love | GT is already close at rank 34 in analysis.artist_tag_neighbor_popularity.anchor_cf_features; rescore within that branch/pool. |
| 67b9ba8a::t8 | Gangsta Gangsta / N.W.A. | order_gap_51_100 | dense.qwen_8b.intent.metadata_qwen3_embedding_8b.anchor_cf_features @ 85 | `branch_local_rerank_or_survivor_slots` | state_tag_popularity_alias @ 82 | 1 | gansta rap, gansta-rap, hip-hop, rap | GT is visible at rank 85; use branch-local hybrid scoring or reserve survivor slots. |
| 9468e467::t5 | Midnight / A Tribe Called Quest | deep_or_source_gap_gt_rank_gt100 | dense.qwen_8b.metadata.metadata_qwen3_embedding_8b.anchor_cf_features @ 175 | `sharper_tag_hybrid_scoring` | state_tag_popularity_alias @ 3263 | 1 | hip hop, hip hop/rap, hip-hop, hip-hop/rap, rap | The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting. |
| e978bb5b::t8 | Dear Yvette / Jane Doe, Masta Ace | deep_or_source_gap_gt_rank_gt100 | dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b.branch_local_hybrid @ 391 | `do_not_optimize_invalid_or_contradictory_gt` | same_album_fanout @ 4 | 608 | hip hop, hip-hop, rap | Do not chase this with retrieval. Keep it as a guardrail/audit case. |
| 3676005d::t1 | Breath and Life / Audiomachine | order_gap_21_50 | dense.qwen_8b.attributes.attributes_qwen3_embedding_8b.anchor_cf_features @ 27 | `branch_local_rerank_existing_branch` | state_scene_era_tag_popularity @ 82 | 2 | classical, movie score, orchestral epic, orchestral-epic, ost, score, soundtrack | GT is already close at rank 27 in dense.qwen_8b.attributes.attributes_qwen3_embedding_8b.anchor_cf_features; rescore within that branch/pool. |
| c4c0c288::t4 | I Juswanna Chill / Large Professor | order_gap_51_100 | dense.qwen_8b.metadata.metadata_qwen3_embedding_8b.anchor_cf_features @ 71 | `branch_local_rerank_or_survivor_slots` | state_tag_popularity_alias @ 3899 | 43 | hip hop, hip-hop, rap | GT is visible at rank 71; use branch-local hybrid scoring or reserve survivor slots. |
| ad5348a7::t5 | Glitter / Tyler, The Creator | absent_from_promoted_top100 | None @ None | `tune_state_tag_popularity_alias` | state_tag_popularity_alias @ 79 | 1 | alternative hip hop, alternative-hip-hop, hip hop, hip hop/rap, hip-hop, hip-... | state_tag_popularity_alias sees GT at rank 79; needs better local scoring, not a new source. |
| 2bbc0a7e::t1 | Las Almas Del Silencio / Ricky Martin | order_gap_21_50 | dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b.catalog_features @ 30 | `branch_local_rerank_existing_branch` | state_fact_only_scene_era @ 227 | 1 | latin, latin pop, latin-pop, pop | GT is already close at rank 30 in dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b.catalog_features; rescore within that branch/pool. |
| 464477e4::t6 | Where Eagles Dare / Glenn Danzig, Misfits | order_gap_21_50 | analysis.artist_tag_neighbor_popularity.anchor_cf_features @ 43 | `branch_local_rerank_existing_branch` | state_scene_era_tag_popularity @ 42 | 1 | alternative, classic punk, classic-punk, hardcore, hardcore punk, hardcore-pu... | GT is already close at rank 43 in analysis.artist_tag_neighbor_popularity.anchor_cf_features; rescore within that branch/pool. |

## Per-Example Notes

### 0b9d547f-e748-464a-90e2-2199149f915c::t6 — Give It To Me Baby / Rick James

- Pack: `P0_roleless_stale_entity_failure`; valid_gt=True; bucket=`deep_or_source_gap_gt_rank_gt100`.
- Current best: `analysis.era_tag_popularity.anchor_cf_features` rank `109`; union@50=True; union@100=True.
- Ideal pull-up: **The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting.**
- Why: The current tag surface has signal but too much noise.
- GT catalog: year=1981; popularity_rank=2426; tags=funk, guitars, Funk, sexy, faves, genius, 80s soul weekender, horns, Rock, R&B/Soul.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=high-energy, classic disco, funk, late 70s to early 80s, 1978, pop, soft rock, disco, rock, gertski pick, billboard hits to check out - the 70s, prog rock.
- Query builders: attributes=music attributes, tags :high-energy, classic disco, funk, late 70s to early 80s, 1978, pop, soft rock, disco, rock; sonic=A song with high-energy, classic disco, funk, late 70s to early 80s, 1978, pop, soft rock, disco, rock sound, similar to Toto, The Real Thing; lyric=.
- Probes: production_best=`state_fact_only_scene_era` @ `2518`; gt_tag_oracle @ `1`; overlap=funk, rock, soul.
- User: Yes! "Can You Feel the Force" is awesome, such a great track. That's exactly the kind of energy I'm looking for. What are some other high-energy, classic disco or funk tracks from that late 70s to early 80s period?

### 41367174-552b-4117-9caa-d0ba1b307d37::t2 — Mercy / Muse

- Pack: `P0_roleless_stale_entity_failure`; valid_gt=True; bucket=`order_gap_51_100`.
- Current best: `analysis.tag_popularity_alias.catalog_features` rank `80`; union@50=False; union@100=True.
- Ideal pull-up: **GT is visible at rank 80; use branch-local hybrid scoring or reserve survivor slots.**
- Why: Candidate source partially works; rank depth is the gap.
- GT catalog: year=2015; popularity_rank=6953; tags=beautiful, muse, emotional, fucking awesome, new, alternative rock, piano, vocal layering, 2015, british.
- State/read: request_type=`RequestType.new_artist`; target_artist_mode=`TargetArtistMode.new_artist`; positive_tags=alternative rock, intense, emotional, 2000s or 2010s, alternative, pop, my top 100 of 2015, bbc radio1 playlist 2016, generic, pretty much, fucking awesome.
- Query builders: attributes=music attributes, tags :alternative rock, intense, emotional, 2000s or 2010s, alternative, pop, my top 100 of 2015, bbc radio1 playlist 2016; sonic=A song with alternative rock, intense, emotional, 2000s or 2010s, alternative, pop, my top 100 of 2015, bbc radio1 playlist 2016 sound, similar to My Chemical Romance,...; lyric=.
- Probes: production_best=`state_tag_popularity_alias` @ `77`; gt_tag_oracle @ `1`; overlap=2010s, alt rock, alternative, alternative rock, alternative-rock, emotional, pop, rock.
- User: Yes! Twenty One Pilots is a great choice, "Stressed Out" totally has that powerful vibe I'm looking for. Can you recommend a few more songs or artists from the 2000s or 2010s that have a similar intense and emotional alternative rock sound, maybe with a str...

### 10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7 — I Can't Go to Sleep / Wu-Tang Clan

- Pack: `P0_roleless_stale_entity_failure`; valid_gt=True; bucket=`order_gap_21_50`.
- Current best: `dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b.catalog_features` rank `29`; union@50=True; union@100=True.
- Ideal pull-up: **GT is already close at rank 29 in dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b.catalog_features; rescore within that branch/pool.**
- Why: Candidate source works; top-20 ordering is the gap.
- GT catalog: year=2000; popularity_rank=17110; tags=legend, lyrical, gangsta, get the jelly out ya spine, Hip-Hop/Rap, sleep, wu-tang clan, boring, insomnia, hip-hop.
- State/read: request_type=`RequestType.same_artist`; target_artist_mode=`TargetArtistMode.same_artist`; positive_tags=intricate storytelling, narrative and character development, music is part of the journey, hip-hop/rap, conscious hip hop, trap rap, kendrick lamar, west coast hip-hop, goddamn,....
- Query builders: attributes=music attributes, tags :intricate storytelling, narrative and character development, music is part of the journey, hip-hop/rap, conscious hip hop, trap rap, kendrick l...; sonic=A song with intricate storytelling, narrative and character development, music is part of the journey, hip-hop/rap, conscious hip hop, trap rap, kendrick lamar, west c...; lyric=music lyrics :intricate storytelling narrative and character development.
- Probes: production_best=`state_tag_popularity_alias` @ `2334`; gt_tag_oracle @ `1`; overlap=hip hop, hip hop/rap, hip-hop, hip-hop/rap, rap.
- User: This is exactly the kind of intricate storytelling I'm digging into. The way Kendrick builds a narrative and develops characters, with the music itself being a part of that journey, is just next level. 'untitled 03' definitely has that layered depth. Keep '...

### 5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2 — Shaft / Kashmere Stage Band

- Pack: `P0_roleless_stale_entity_failure`; valid_gt=True; bucket=`absent_from_promoted_top100`.
- Current best: `None` rank `None`; union@50=False; union@100=False.
- Ideal pull-up: **The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting.**
- Why: The current tag surface has signal but too much noise.
- GT catalog: year=2011; popularity_rank=37049; tags=funk, umlaute, soundtrack, Others, instrumental, lovedtrack, instrumental funk, bespoke radio for sriman, jazz-rock, mark-test2.
- State/read: request_type=`RequestType.unknown`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=pop, funk, classics, funk tag, soul, boogie, memorable gta tracks, favourites.
- Query builders: attributes=music attributes, tags :pop, funk, classics, funk tag, soul; sonic=A song with pop, funk, classics, funk tag, soul sound, similar to Kool & The Gang; lyric=.
- Probes: production_best=`state_tag_popularity_alias` @ `18216`; gt_tag_oracle @ `1`; overlap=funk.
- User: Yes! That's a classic, I know that one well! It definitely fits the vibe of what I was looking for. It's got that undeniable groove.

### 78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8 — In the Shadows / The Rasmus

- Pack: `P0_roleless_stale_entity_failure`; valid_gt=True; bucket=`deep_or_source_gap_gt_rank_gt100`.
- Current best: `centroid.anchor_tracks.audio_laion_clap.branch_local_hybrid` rank `197`; union@50=False; union@100=False.
- Ideal pull-up: **The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting.**
- Why: The current tag surface has signal but too much noise.
- GT catalog: year=2003; popularity_rank=776; tags=winamp erk playlist all the goodies on my computer, Metal, rock, pop rock, favourite songs, imogen, alternative rock, finnish, Alternative, pozitiv.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=rock, powerful, strong guitar riff, alternative, alternative rock, metal, punk, hard rock, 00s, favourite.
- Query builders: attributes=music attributes, tags :rock, powerful, strong guitar riff, alternative, alternative rock, metal, punk; sonic=A song with rock, powerful, strong guitar riff, alternative, alternative rock, metal, punk sound, similar to Guano Apes; lyric=.
- Probes: production_best=`state_fact_only_scene_era` @ `4531`; gt_tag_oracle @ `1`; overlap=alt rock, alternative, alternative rock, alternative-rock, metal, rock.
- User: Yes! Guano Apes! I love this song, it's so powerful. The vocalist is amazing. Do you have any other powerful rock songs, maybe with a really strong guitar riff?

### 88af7ec3-c368-421b-9512-d0180da3d1f6::t2 — I Believe in a Thing Called Love / The Darkness

- Pack: `P0_roleless_stale_entity_failure`; valid_gt=False; bucket=`absent_from_promoted_top100`.
- Current best: `None` rank `None`; union@50=False; union@100=False.
- Ideal pull-up: **Do not chase this with retrieval. Keep it as a guardrail/audit case.**
- Why: GT audit marks this noisy or contradictory.
- GT catalog: year=2003; popularity_rank=1093; tags=Metal, metal, doom metal, Soundtracks, Rock.
- State/read: request_type=`RequestType.hidden_target`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=overhearing gossip, bartender, wedding drama, 2000s.
- Query builders: attributes=music attributes, tags :overhearing gossip, bartender, wedding drama, 2000s; sonic=A song with overhearing gossip, bartender, wedding drama, 2000s sound; lyric=music lyrics :overhearing gossip, bartender, wedding drama.
- Probes: production_best=`None` @ `None`; gt_tag_oracle @ `1`; overlap=none.
- User: Oh my goodness, that's a very interesting choice! "I Write Sins Not Tragedies" definitely has a strong story. I remember a song like that, with a wedding drama. Can you remind me of any specific lines about a bartender, or someone overhearing gossip?

### d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2 — Move Along / The All-American Rejects

- Pack: `P0_roleless_stale_entity_failure`; valid_gt=True; bucket=`order_gap_51_100`.
- Current best: `dense.clap_text.sonic_nl.audio_laion_clap.branch_local_hybrid` rank `97`; union@50=False; union@100=True.
- Ideal pull-up: **GT is visible at rank 97; use branch-local hybrid scoring or reserve survivor slots.**
- Why: Candidate source partially works; rank depth is the gap.
- GT catalog: year=2005; popularity_rank=1407; tags=alternative rock, hopeful, Alternative, punk-pop, favorites, hope, fav songs, favorite song, emo rock, positive.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=pop-punk, alternative rock, early 2000s, angsty, energetic, punk, pop, rock, pop punk, alternative.
- Query builders: attributes=music attributes, tags :pop-punk, alternative rock, early 2000s, angsty, energetic, punk, pop, rock, pop punk; sonic=A song with pop-punk, alternative rock, early 2000s, angsty, energetic, punk, pop, rock, pop punk sound; lyric=.
- Probes: production_best=`artist_neighbor_scene_fact` @ `23`; gt_tag_oracle @ `1`; overlap=alt rock, alternative, alternative rock, alternative-rock, classic punk, emo rock, emo-rock, hardcore punk, pop punk, pop-punk, proto-punk, punk, punk pop, punk-pop.
- User: That's a good one, it totally brings back early 2000s pop-punk! It's got the energy, but I'm looking for something that feels a bit more... not quite heavier, but with a stronger angsty feel. Still from that early 2000s pop-punk or alternative rock vibe, ma...

### c7a965c3-cd7f-46f6-b166-9dce9a800e0a::t3 — S&M / Rihanna

- Pack: `P0_novelty_prior_anchor_failure`; valid_gt=True; bucket=`deep_or_source_gap_gt_rank_gt100`.
- Current best: `analysis.artist_tag_neighbor_popularity.anchor_cf_features` rank `120`; union@50=True; union@100=True.
- Ideal pull-up: **state_tag_popularity_alias would put GT at rank 30; promote/tune this production-valid branch.**
- Why: Current projected tags plus catalog alias expansion.
- GT catalog: year=2010; popularity_rank=94; tags=energetic, party time, awful, workout, 2010, hot, unlistenable, 2010s, erotica, s&m.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=super strong driving beat, empowering pop energy, more recent, pop, 2003, sex, guilty pleasures, female, favorite, usa, energetic.
- Query builders: attributes=music attributes, tags :super strong driving beat, empowering pop energy, more recent, pop, 2003, sex, guilty pleasures, female; sonic=A song with super strong driving beat, empowering pop energy, more recent, pop, 2003, sex, guilty pleasures, female sound, similar to Britney Spears; lyric=.
- Probes: production_best=`state_tag_popularity_alias` @ `30`; gt_tag_oracle @ `1`; overlap=energetic, female, sex.
- User: Yes! That's exactly the track! 'Toxic' by Britney Spears always makes me feel that way. It's so iconic and brings back all those confident, dancing vibes. You nailed it! Thanks! Can you recommend something else with a similar super strong, driving beat? May...

### 88beb200-0334-4aba-be15-8e1303725766::t6 — Used To / Lil Wayne, Drake

- Pack: `P0_novelty_prior_anchor_failure`; valid_gt=False; bucket=`order_gap_21_50`.
- Current best: `dense.clap_text.sonic.audio_laion_clap.anchor_cf_features` rank `48`; union@50=True; union@100=True.
- Ideal pull-up: **Do not chase this with retrieval. Keep it as a guardrail/audit case.**
- Why: GT audit marks this noisy or contradictory.
- GT catalog: year=2015; popularity_rank=6081; tags=lil wayne, love, ovo, bass, Hip-Hop/Rap, hip hop, hip-hop, canada, rap.
- State/read: request_type=`RequestType.new_artist`; target_artist_mode=`TargetArtistMode.new_artist`; positive_tags=hip-hop, popular, major hits, love, hip-hop/rap, hip hop, rap, chill, partynextdoor, chillout.
- Query builders: attributes=music attributes, tags :hip-hop, popular, major hits, love, hip-hop/rap, hip hop, rap; sonic=A song with hip-hop, popular, major hits, love, hip-hop/rap, hip hop, rap sound; lyric=.
- Probes: production_best=`same_album_fanout` @ `14`; gt_tag_oracle @ `1`; overlap=hip hop, hip hop/rap, hip-hop, hip-hop/rap, love, rap.
- User: Legend" is a classic, no doubt! I'm good on Drake for now though. I was hoping for some popular Hip-Hop tracks from *other artists* around late 2015 to early 2016. Any major hits from that period by someone different?

### 8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7 — Transcentience / Animals As Leaders

- Pack: `P0_novelty_prior_anchor_failure`; valid_gt=True; bucket=`deep_or_source_gap_gt_rank_gt100`.
- Current best: `dense.qwen_8b.intent.metadata_qwen3_embedding_8b.anchor_cf_features` rank `147`; union@50=False; union@100=False.
- Ideal pull-up: **No current production-valid probe sees the GT well; keep as candidate for new source audit.**
- Why: The request/GT connection is weak in available metadata.
- GT catalog: year=2016; popularity_rank=41464; tags=Hard Rock.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=technical, orchestral, symphonic, melodic, atmospheric, metal, rock, death metal, math metal, technical metal, fucking awesome, unmatched melodies, progressive metal.
- Query builders: attributes=music attributes, tags :technical, orchestral, symphonic, melodic, atmospheric, metal, rock, death metal, math metal, technical metal; sonic=A song with technical, orchestral, symphonic, melodic, atmospheric, metal, rock, death metal, math metal, technical metal sound, similar to Gorguts, Allegaeon; lyric=.
- Probes: production_best=`artist_neighbor_scene_fact` @ `15452`; gt_tag_oracle @ `6383`; overlap=none.
- User: This is excellent! The melodic technicality of Allegaeon is exactly the kind of balance I was looking for. Can you suggest something else that leans into orchestral or symphonic elements alongside the technicality?

### 380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3 — God Hates a Coward / Tomahawk

- Pack: `P0_novelty_prior_anchor_failure`; valid_gt=True; bucket=`deep_or_source_gap_gt_rank_gt100`.
- Current best: `bm25.catalog_features` rank `126`; union@50=False; union@100=False.
- Ideal pull-up: **state_tag_popularity_alias would put GT at rank 23; promote/tune this production-valid branch.**
- Why: Current projected tags plus catalog alias expansion.
- GT catalog: year=2001; popularity_rank=21312; tags=experimental, supergroup, folk, alternative rock, progressive metal, neuroshima, aberrant mental states, leapsandloved2009, epic, favorites.
- State/read: request_type=`RequestType.new_artist`; target_artist_mode=`TargetArtistMode.new_artist`; positive_tags=experimental genre-bending, avant-garde theatrical, high energy, alternative, rock, experimental, genius, mike patton, psychedelic, progressive, hard rock.
- Query builders: attributes=music attributes, tags :experimental genre-bending, avant-garde theatrical, high energy, alternative, rock, experimental, genius, mike patton; sonic=A song with experimental genre-bending, avant-garde theatrical, high energy, alternative, rock, experimental, genius, mike patton sound, similar to Mr. Bungle; lyric=.
- Probes: production_best=`state_tag_popularity_alias` @ `23`; gt_tag_oracle @ `1`; overlap=alt rock, alternative, alternative rock, alternative-rock, avant-garde, experimental, mike patton, mike-patton, progressive metal, progressive-metal, strange.
- User: Yes! Mr. Bungle! That's exactly the band I was trying to remember. "Violenza Domestica" is definitely a great example of their sound. Thanks! Now that we found them, what else could you recommend that has a similar experimental, genre-bending vibe, maybe wi...

### cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3 — Gib ihn einfach (Dies das 2) / Ghanaian Stallion

- Pack: `P0_novelty_prior_anchor_failure`; valid_gt=True; bucket=`deep_or_source_gap_gt_rank_gt100`.
- Current best: `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b.catalog_features` rank `212`; union@50=False; union@100=False.
- Ideal pull-up: **The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting.**
- Why: The current tag surface has signal but too much noise.
- GT catalog: year=2015; popularity_rank=42431; tags=hip-hop, Hip-Hop/Rap, rap, boom-bap.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=old-school hip-hop, timeless era-defining, dancehall, reggae, reggae-pop, dubhop, loved, raggae, political, 00s.
- Query builders: attributes=music attributes, tags :old-school hip-hop, timeless era-defining, dancehall, reggae, reggae-pop, dubhop, loved; sonic=A song with old-school hip-hop, timeless era-defining, dancehall, reggae, reggae-pop, dubhop, loved sound, similar to Damian Marley; lyric=.
- Probes: production_best=`state_fact_only_scene_era` @ `6502`; gt_tag_oracle @ `72`; overlap=hip hop, hip-hop, rap.
- User: Yes, this is exactly the kind of sound I was looking for! "Welcome To Jamrock" is a classic. That definitely fits the "defined an era" vibe. Can you give me another track that has that timeless, era-defining feeling, maybe an old-school hip-hop gem this time?

### 5ee0dbbc-c1d1-4bed-ba09-7dafeec198bc::t8 — You Reposted in the Wrong Neighborhood I Glue70 Mashup / Shokk

- Pack: `P0_new_artist_union20_gap_failure`; valid_gt=True; bucket=`order_gap_21_50`.
- Current best: `dense.qwen_8b.intent.metadata_qwen3_embedding_8b.anchor_cf_features` rank `22`; union@50=True; union@100=True.
- Ideal pull-up: **GT is already close at rank 22 in dense.qwen_8b.intent.metadata_qwen3_embedding_8b.anchor_cf_features; rescore within that branch/pool.**
- Why: Candidate source works; top-20 ordering is the gap.
- GT catalog: year=2014; popularity_rank=7565; tags=Electronic.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=meme song/goofy, absurd story with characters, famous viral, catchy vocal hook.
- Query builders: attributes=music attributes, tags :meme song/goofy, absurd story with characters, famous viral, catchy vocal hook; sonic=A song with meme song/goofy, absurd story with characters, famous viral, catchy vocal hook sound; lyric=music lyrics :absurd story with characters.
- Probes: production_best=`None` @ `None`; gt_tag_oracle @ `1129`; overlap=none.
- User: Dude, 'The Ultimate Showdown of Ultimate Destiny' is awesome! That song is a classic, the story is just so over-the-top and hilarious. You really crushed it with these meme and goofy song recommendations! Thanks! What else you got for me? Maybe something mo...

### 5861afef-85c0-4163-b8b9-5a11e308f352::t4 — Carmesí / Vicente Garcia

- Pack: `P0_new_artist_union20_gap_failure`; valid_gt=True; bucket=`order_gap_51_100`.
- Current best: `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b.anchor_cf_features` rank `74`; union@50=False; union@100=True.
- Ideal pull-up: **GT is visible at rank 74; use branch-local hybrid scoring or reserve survivor slots.**
- Why: Candidate source partially works; rank depth is the gap.
- GT catalog: year=2016; popularity_rank=3829; tags=Latin.
- State/read: request_type=`RequestType.new_artist`; target_artist_mode=`TargetArtistMode.new_artist`; positive_tags=danceable, Latin, funk carioca, others.
- Query builders: attributes=music attributes, tags :danceable, Latin, funk carioca, others; sonic=A song with danceable, Latin, funk carioca, others sound, similar to DENNIS, Nego Bam, MC Nandinho, Lucas Lucco, MC Lan; lyric=.
- Probes: production_best=`state_tag_popularity_alias` @ `1104`; gt_tag_oracle @ `491`; overlap=latin.
- User: Yes, "Tic Tac" is super catchy and energetic! It's great to hear MC Lan with Lucas Lucco too. I'm finding some really good artists. Can you give me a few more diverse artists to check out, maybe with a slightly different take on that danceable or Latin sound?

### 15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6 — Hong Kong 2046 / Hong Kong Express

- Pack: `P0_new_artist_union20_gap_failure`; valid_gt=True; bucket=`deep_or_source_gap_gt_rank_gt100`.
- Current best: `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b.catalog_features` rank `347`; union@50=False; union@100=False.
- Ideal pull-up: **The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting.**
- Why: The current tag surface has signal but too much noise.
- GT catalog: year=2014; popularity_rank=16654; tags=numbers, late night lo-fi, Electronic, cityvapor, towns and cities, vaporwave.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=unique and out-there, electronic, soulful, interesting mix of sounds, r&b/soul, experimental, macedead, best 2014, gospel, ethereal, soul.
- Query builders: attributes=music attributes, tags :unique and out-there, electronic, soulful, interesting mix of sounds, r&b/soul, experimental, macedead, best 2014; sonic=A song with unique and out-there, electronic, soulful, interesting mix of sounds, r&b/soul, experimental, macedead, best 2014 sound; lyric=.
- Probes: production_best=`state_fact_only_scene_era` @ `3512`; gt_tag_oracle @ `1`; overlap=edm, electronic, electronica.
- User: Oh, Flying Lotus! This is cool, it's got a really interesting mix of sounds. It's like electronic but also soulful, very unique. What else have you got that's really out there?

### 907921a3-d08f-4ba1-8cce-0e760a9e7044::t7 — Sunrise - Slow Hands Remix / Kasper Bjørke

- Pack: `P0_new_artist_union20_gap_failure`; valid_gt=True; bucket=`order_gap_21_50`.
- Current best: `centroid.anchor_tracks.cf_bpr.branch_local_hybrid` rank `36`; union@50=True; union@100=True.
- Ideal pull-up: **GT is already close at rank 36 in centroid.anchor_tracks.cf_bpr.branch_local_hybrid; rescore within that branch/pool.**
- Why: Candidate source works; top-20 ordering is the gap.
- GT catalog: year=2013; popularity_rank=44774; tags=Pop, Dance, Electronic.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=electronic, direct intense plea, begging, ambient, note to self, mymau5, minimal, dance, chillout, pe jos.
- Query builders: attributes=music attributes, tags :electronic, direct intense plea, begging, ambient, note to self, mymau5, minimal; sonic=A song with electronic, direct intense plea, begging, ambient, note to self, mymau5, minimal sound, similar to Men I Trust; lyric=music lyrics :direct intense plea.
- Probes: production_best=`artist_neighbor_scene_fact` @ `2797`; gt_tag_oracle @ `1878`; overlap=dance, edm, electronic, electronica, freestyle mix, house.
- User: This one has a cool electronic sound and it's definitely emotional. But I'm still looking for that really strong, direct "plea" or "begging" in the lyrics, like in "Iris," but for electronic songs. Do you have any tracks that really hit that direct lyrical...

### 324ddfb5-8a18-4729-9acb-c851907a297c::t3 — Acknowledge / Masta Ace

- Pack: `P0_new_artist_union20_gap_failure`; valid_gt=True; bucket=`order_gap_51_100`.
- Current best: `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b.branch_local_hybrid` rank `81`; union@50=False; union@100=True.
- Ideal pull-up: **GT is visible at rank 81; use branch-local hybrid scoring or reserve survivor slots.**
- Why: Candidate source partially works; rank depth is the gap.
- GT catalog: year=2005; popularity_rank=15834; tags=strictly for the undergound, great rap, underground hip-hop, masta ace rap hiphop, great diss, hippity hoppity, east coast rap, new york rap, wizardry, the real.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=raw hip-hop, underground hip-hop, classic, authentic vibe, late 90s or early 2000s, hip-hop/rap, hip hop, hip-hop, hell, totalny wypierdalacz klasyka, pop, najwyzszy poziom, naj....
- Query builders: attributes=music attributes, tags :raw hip-hop, underground hip-hop, classic, authentic vibe, late 90s or early 2000s, hip-hop/rap, hip hop, hip-hop, hell, totalny wypierdalacz k...; sonic=A song with raw hip-hop, underground hip-hop, classic, authentic vibe, late 90s or early 2000s, hip-hop/rap, hip hop, hip-hop, hell, totalny wypierdalacz klasyka sound...; lyric=.
- Probes: production_best=`artist_neighbor_scene_fact` @ `128`; gt_tag_oracle @ `1`; overlap=east coast hip hop, hip hop, hip hop/rap, hip-hop, hip-hop/rap, rap, underground hip hop, underground hip-hop, underground-hip-hop.
- User: Yeah, that Dead Prez track is fire! Super authentic and exactly the kind of vibe I'm into from that era. What else hits like that? Maybe some more underground stuff from the late 90s or early 2000s?

### ba68a3cc-5278-4680-917a-4ca66d33ef31::t5 — Buttons / The Pussycat Dolls

- Pack: `P0_new_artist_union20_gap_failure`; valid_gt=True; bucket=`order_gap_21_50`.
- Current best: `analysis.artist_tag_neighbor_popularity.anchor_cf_features` rank `34`; union@50=True; union@100=True.
- Ideal pull-up: **GT is already close at rank 34 in analysis.artist_tag_neighbor_popularity.anchor_cf_features; rescore within that branch/pool.**
- Why: Candidate source works; top-20 ordering is the gap.
- GT catalog: year=2005; popularity_rank=1776; tags=a vocal-centric aesthetic, lust, groove based composition, workout, hot, english, lights off, top, favorites, start dancing.
- State/read: request_type=`RequestType.similar_to_prior`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=pop, high-energy, iconic, empowering, confident, early 2000s, dance, nostalgia, favorites, love, feel good, female, hit.
- Query builders: attributes=music attributes, tags :pop, high-energy, iconic, empowering, confident, early 2000s, dance, nostalgia, favorites, love; sonic=A song with pop, high-energy, iconic, empowering, confident, early 2000s, dance, nostalgia, favorites, love sound, similar to Spice Girls; lyric=.
- Probes: production_best=`artist_neighbor_scene_fact` @ `50`; gt_tag_oracle @ `1`; overlap=female, love.
- User: Yes, this selection is great! "Wannabe" is iconic, it really gets me in a powerful mood. I think these are all perfect for what I asked for. What else do you have that's like these? Maybe some other pop artists from that same time?

### 67b9ba8a-382f-4b70-af76-576848d8cf67::t8 — Gangsta Gangsta / N.W.A.

- Pack: `P1_temporal_constraint_failure`; valid_gt=True; bucket=`order_gap_51_100`.
- Current best: `dense.qwen_8b.intent.metadata_qwen3_embedding_8b.anchor_cf_features` rank `85`; union@50=True; union@100=True.
- Ideal pull-up: **GT is visible at rank 85; use branch-local hybrid scoring or reserve survivor slots.**
- Why: Candidate source partially works; rank depth is the gap.
- GT catalog: year=1988; popularity_rank=3065; tags=808, gangsta rap attitude, electric guitars, rap hip-hop, an electric bass riff, richard pryor, explicit lyrics, sample, old school hip hop, nwa.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=raw aggression, dark and intense, gritty beats, horrorcore-influenced lyrics, East Coast underground, 2003, gansta rap, russian alternative, lulz: a corruption of lol, b3zmonde,....
- Query builders: attributes=music attributes, tags :raw aggression, dark and intense, gritty beats, horrorcore-influenced lyrics, East Coast underground, 2003, gansta rap, russian alternative, lu...; sonic=A song with raw aggression, dark and intense, gritty beats, horrorcore-influenced lyrics, East Coast underground, 2003, gansta rap, russian alternative, lulz: a corrup...; lyric=music lyrics :horrorcore-influenced.
- Probes: production_best=`state_tag_popularity_alias` @ `82`; gt_tag_oracle @ `1`; overlap=gansta rap, gansta-rap, hip-hop, rap.
- User: DMX is a beast! "Where The Hood At" is definitely a raw, aggressive banger and fits that dark, intense vibe perfectly. You nailed it with these last few tracks. Thanks for the awesome recommendations! Can you suggest another track that's just pure, unfilter...

### 9468e467-d396-461b-be29-b30b6cf87c35::t5 — Midnight / A Tribe Called Quest

- Pack: `P1_temporal_constraint_failure`; valid_gt=True; bucket=`deep_or_source_gap_gt_rank_gt100`.
- Current best: `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b.anchor_cf_features` rank `175`; union@50=False; union@100=False.
- Ideal pull-up: **The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting.**
- Why: The current tag surface has signal but too much noise.
- GT catalog: year=1993; popularity_rank=13021; tags=strictly for the undergound, east coast rap, loved, hip hop is read playlist, hard, sopperfield, rap hip-hop, hip hop hooray, true hop, hip hoprap.
- State/read: request_type=`RequestType.similar_to_prior`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=atmospheric, night-time city walk, spoken-word storytelling, early 2000s UK sound, hip hop, electronica, pop, rock, lyrically-induced-grinning, songs to save your life, hip-hop/....
- Query builders: attributes=music attributes, tags :atmospheric, night-time city walk, spoken-word storytelling, early 2000s UK sound, hip hop, electronica, pop, rock, lyrically-induced-grinning; sonic=A song with atmospheric, night-time city walk, spoken-word storytelling, early 2000s UK sound, hip hop, electronica, pop, rock, lyrically-induced-grinning sound, simil...; lyric=.
- Probes: production_best=`state_tag_popularity_alias` @ `3263`; gt_tag_oracle @ `1`; overlap=hip hop, hip hop/rap, hip-hop, hip-hop/rap, rap.
- User: Yes! "Blinded By The Lights" is exactly the track I was trying to recall! That's the one! You totally nailed it with that recommendation. Thanks so much! Now that you've found that one for me, can you recommend some other tracks that have a similar kind of...

### e978bb5b-26af-4c7d-b720-b9210bdddf25::t8 — Dear Yvette / Jane Doe, Masta Ace

- Pack: `P1_temporal_constraint_failure`; valid_gt=False; bucket=`deep_or_source_gap_gt_rank_gt100`.
- Current best: `dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b.branch_local_hybrid` rank `391`; union@50=False; union@100=False.
- Ideal pull-up: **Do not chase this with retrieval. Keep it as a guardrail/audit case.**
- Why: GT audit marks this noisy or contradictory.
- GT catalog: year=2005; popularity_rank=38148; tags=hiphop, Hip-Hop/Rap, hip-hop.
- State/read: request_type=`RequestType.new_artist`; target_artist_mode=`TargetArtistMode.new_artist`; positive_tags=narrative-driven, East Coast hip-hop, 1990s, classic, underground hip-hop, east coast, socially conscious, the best song ever, game, classic hip-hop, lyrics to learn from, damn....
- Query builders: attributes=music attributes, tags :narrative-driven, East Coast hip-hop, 1990s, classic, underground hip-hop, east coast, socially conscious, the best song ever, game; sonic=A song with narrative-driven, East Coast hip-hop, 1990s, classic, underground hip-hop, east coast, socially conscious, the best song ever, game sound; lyric=music lyrics :narrative-driven.
- Probes: production_best=`same_album_fanout` @ `4`; gt_tag_oracle @ `608`; overlap=hip hop, hip-hop, rap.
- User: Make My" is a strong track and Black Thought's lyrics are always on point, but I'm really trying to branch out from The Roots and Masta Ace for a bit. Can you definitely give me a narrative-driven track from a *different* classic 90s East Coast artist, like...

### 3676005d-5b7c-4c48-9b73-3e10dd509c07::t1 — Breath and Life / Audiomachine

- Pack: `P1_temporal_constraint_failure`; valid_gt=True; bucket=`order_gap_21_50`.
- Current best: `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b.anchor_cf_features` rank `27`; union@50=True; union@100=True.
- Ideal pull-up: **GT is already close at rank 27 in dense.qwen_8b.attributes.attributes_qwen3_embedding_8b.anchor_cf_features; rescore within that branch/pool.**
- Why: Candidate source works; top-20 ordering is the gap.
- GT catalog: year=2012; popularity_rank=40387; tags=trailer music, epic, soundtrack, instrumental, fucking awesome, orchestral epic, Classical.
- State/read: request_type=`RequestType.hidden_target`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=powerful orchestral, like something from a movie score, early 2000s.
- Query builders: attributes=music attributes, tags :powerful orchestral, like something from a movie score, early 2000s; sonic=A song with powerful orchestral, like something from a movie score, early 2000s sound; lyric=.
- Probes: production_best=`state_scene_era_tag_popularity` @ `82`; gt_tag_oracle @ `2`; overlap=classical, movie score, orchestral epic, orchestral-epic, ost, score, soundtrack.
- User: I'm trying to remember a really powerful, orchestral song from the early 2000s, like something from a movie score.

### c4c0c288-dbcd-4970-ad52-901aafe91b88::t4 — I Juswanna Chill / Large Professor

- Pack: `P1_temporal_constraint_failure`; valid_gt=True; bucket=`order_gap_51_100`.
- Current best: `dense.qwen_8b.metadata.metadata_qwen3_embedding_8b.anchor_cf_features` rank `71`; union@50=False; union@100=True.
- Ideal pull-up: **GT is visible at rank 71; use branch-local hybrid scoring or reserve survivor slots.**
- Why: Candidate source partially works; rank depth is the gap.
- GT catalog: year=2009; popularity_rank=10260; tags=banned, Hip-Hop/Rap, hip-hop.
- State/read: request_type=`RequestType.new_artist`; target_artist_mode=`TargetArtistMode.new_artist`; positive_tags=jazzy hip-hop, golden age hip-hop, underground 90s hip-hop, east coast rap, old school hip hop, favorites, hip hoprap, jazz hop, hiphopgdchill, alternative hip hop, leapsandboun....
- Query builders: attributes=music attributes, tags :jazzy hip-hop, golden age hip-hop, underground 90s hip-hop, east coast rap, old school hip hop, favorites, hip hoprap, jazz hop; sonic=A song with jazzy hip-hop, golden age hip-hop, underground 90s hip-hop, east coast rap, old school hip hop, favorites, hip hoprap, jazz hop sound, similar to A Tribe C...; lyric=.
- Probes: production_best=`state_tag_popularity_alias` @ `3899`; gt_tag_oracle @ `43`; overlap=hip hop, hip-hop, rap.
- User: These selections are spot on for that underground 90s hip-hop sound. Exactly what I wanted! What else is out there that I might like with a similar vibe, maybe from other artists but still with that golden age jazzy feel?

### ad5348a7-d3bc-4882-bfca-54aa655eac96::t5 — Glitter / Tyler, The Creator

- Pack: `P1_positive_tag_retrieval_gap_failure`; valid_gt=True; bucket=`absent_from_promoted_top100`.
- Current best: `None` rank `None`; union@50=False; union@100=False.
- Ideal pull-up: **state_tag_popularity_alias sees GT at rank 79; needs better local scoring, not a new source.**
- Why: Current projected tags plus catalog alias expansion.
- GT catalog: year=2017; popularity_rank=1953; tags=bittersweet, Hip-Hop/Rap, hip hop, post-nerdcore, alternative hip-hop, alternative hip hop, hip-hop, played, tyler the creator, rap.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=hip-hop/rap, best of 2017, hip hop, 2-5-19, hype, alternative hip hop, banger, 10s.
- Query builders: attributes=music attributes, tags :hip-hop/rap, best of 2017, hip hop, 2-5-19, hype; sonic=A song with hip-hop/rap, best of 2017, hip hop, 2-5-19, hype sound; lyric=.
- Probes: production_best=`state_tag_popularity_alias` @ `79`; gt_tag_oracle @ `1`; overlap=alternative hip hop, alternative-hip-hop, hip hop, hip hop/rap, hip-hop, hip-hop/rap, rap.
- User: Dope! "REDMERCEDES" is definitely on point with that vibrant energy, both in the song and the cover. These are exactly the kind of tracks I was looking for, where the artwork really brings out the music's vibe. What else have you got that fits this awesome...

### 2bbc0a7e-3ab0-4376-8135-182cd4ae075f::t1 — Las Almas Del Silencio / Ricky Martin

- Pack: `P1_positive_tag_retrieval_gap_failure`; valid_gt=True; bucket=`order_gap_21_50`.
- Current best: `dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b.catalog_features` rank `30`; union@50=True; union@100=True.
- Ideal pull-up: **GT is already close at rank 30 in dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b.catalog_features; rescore within that branch/pool.**
- Why: Candidate source works; top-20 ordering is the gap.
- GT catalog: year=2003; popularity_rank=36495; tags=pop, Latin Pop, beautiful, latin pop, easy listening, male vocalists, favourite, puerto rico, puerto rican, latin.
- State/read: request_type=`RequestType.hidden_target`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=Latin Pop, hit back then, early 2000s.
- Query builders: attributes=music attributes, tags :Latin Pop, hit back then, early 2000s; sonic=A song with Latin Pop, hit back then, early 2000s sound; lyric=.
- Probes: production_best=`state_fact_only_scene_era` @ `227`; gt_tag_oracle @ `1`; overlap=latin, latin pop, latin-pop, pop.
- User: I'm trying to remember a Latin Pop song from around the early 2000s, it was quite a hit back then.

### 464477e4-f186-47fb-8cb0-55691c8b8f57::t6 — Where Eagles Dare / Glenn Danzig, Misfits

- Pack: `P1_positive_tag_retrieval_gap_failure`; valid_gt=True; bucket=`order_gap_21_50`.
- Current best: `analysis.artist_tag_neighbor_popularity.anchor_cf_features` rank `43`; union@50=True; union@100=True.
- Ideal pull-up: **GT is already close at rank 43 in analysis.artist_tag_neighbor_popularity.anchor_cf_features; rescore within that branch/pool.**
- Why: Candidate source works; top-20 ordering is the gap.
- GT catalog: year=1986; popularity_rank=5143; tags=under two minutes, hardcore punk, i aint no goddamn son of a bitch, alternative rock, 1979, classic hard rock, gothic, favorites, classic punk, favorite song.
- State/read: request_type=`RequestType.attribute_search`; target_artist_mode=`TargetArtistMode.unknown`; positive_tags=proto-punk, early New York City punk, influential, punk, rock, alternative, hard rock, hardcore, political, theo73 loves this music, 80s.
- Query builders: attributes=music attributes, tags :proto-punk, early New York City punk, influential, punk, rock, alternative, hard rock, hardcore; sonic=A song with proto-punk, early New York City punk, influential, punk, rock, alternative, hard rock, hardcore sound, similar to Bad Religion, Dead Kennedys, The Clash; lyric=.
- Probes: production_best=`state_scene_era_tag_popularity` @ `42`; gt_tag_oracle @ `1`; overlap=alternative, classic punk, classic-punk, hardcore, hardcore punk, hardcore-punk, proto-punk, punk.
- User: Yes, The Clash! "White Riot" is a perfect example of that raw UK punk energy. These are all legendary tracks. What about something equally influential, but from the earlier wave of punk, like proto-punk, or something from New York City's early scene?

