# State V1 Targeted Branch Recall Report

110 focused state-gap turns; V1 extraction/projection frozen; no global ranking/RRF change

## Headline

| Pool | union@20 | union@50 | union@100 |
|---|---:|---:|---:|
| protected trace pools | 60 | 60 | 60 |
| current OR baseline | 75 | 87 | 91 |
| targeted branches only | 43 | 53 | 60 |
| current + targeted | 77 | 90 | 93 |
| new rescues over current | 2 | 3 | 2 |

## Interpretation

- The gap is partly solvable with targeted retrieval: current focused recall moves from 75/87/91 to 77/90/93 at union@20/50/100.
- The strongest top-20 fixes are not global RRF changes: one is scene/era/tag scoring for 90s dance/freestyle, and one is the previously-missing SigLIP text-to-cover-image branch.
- Artist-neighbor scene retrieval does not improve union@20 over current, but it creates useful union@50 evidence for style-neighborhood cases.
- The remaining top-100 misses are not solved by these branches; several are lyric/hidden-target or weak-source cases, and some have contradictory GT relative to the user request.

## Unique Rescues Over Current

| k | sample | pack | GT | branch | rank | current user |
|---:|---|---|---|---|---:|---|
| 20 | `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` | `P0_new_artist_union20_gap_failure` | Two To Make It Right / Seduction | `analysis.scene_era_tag_popularity_v2` | 6 | Yes! 'Finally' by CeCe Peniston! That's exactly the track I was trying to remember. Spot on! 'Finally' is it. Can you... |
| 20 | `dd686049-59ba-439b-8c51-949a0876e1b3::t1` | `P1_positive_tag_retrieval_gap_failure` | Vengeance (The Return of the Night Driving Avenger) [Bonus Track] / Perturbator | `dense.siglip2_text.visual.image_siglip2` | 1 | I'm looking for a really intense electronic song, something that makes you feel like you're speeding through a cyberp... |
| 50 | `54cda581-3b2e-4245-a479-1a27589760d2::t3` | `P1_positive_tag_retrieval_gap_failure` | Deliberation - Studio / Katatonia | `analysis.artist_neighbor_scene_v2` | 46 | This is getting really close! The album art for "Character" by Dark Tranquillity is definitely in the right ballpark ... |
| 50 | `67b9ba8a-382f-4b70-af76-576848d8cf67::t8` | `P1_temporal_constraint_failure` | Gangsta Gangsta / N.W.A. | `analysis.artist_neighbor_scene_v2` | 21 | DMX is a beast! "Where The Hood At" is definitely a raw, aggressive banger and fits that dark, intense vibe perfectly... |
| 50 | `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` | `P0_new_artist_union20_gap_failure` | Two To Make It Right / Seduction | `analysis.scene_era_tag_popularity_v2` | 6 | Yes! 'Finally' by CeCe Peniston! That's exactly the track I was trying to remember. Spot on! 'Finally' is it. Can you... |
| 100 | `67b9ba8a-382f-4b70-af76-576848d8cf67::t8` | `P1_temporal_constraint_failure` | Gangsta Gangsta / N.W.A. | `analysis.artist_neighbor_scene_v2` | 21 | DMX is a beast! "Where The Hood At" is definitely a raw, aggressive banger and fits that dark, intense vibe perfectly... |
| 100 | `b466a64b-b3cc-4c62-8a70-8261434f915f::t2` | `P0_new_artist_union20_gap_failure` | Two To Make It Right / Seduction | `analysis.scene_era_tag_popularity_v2` | 6 | Yes! 'Finally' by CeCe Peniston! That's exactly the track I was trying to remember. Spot on! 'Finally' is it. Can you... |

## Per-Class Current vs Targeted

| Pack | n | current@20 | current+targeted@20 | new@20 | current@50 | current+targeted@50 | new@50 | current@100 | current+targeted@100 | new@100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `P0_good_state_ranker_near_miss_failure` | 10 | 10 | 10 | 0 | 10 | 10 | 0 | 10 | 10 | 0 |
| `P0_named_artist_ranker_failure` | 10 | 10 | 10 | 0 | 10 | 10 | 0 | 10 | 10 | 0 |
| `P0_new_artist_union20_gap_failure` | 10 | 3 | 4 | 1 | 5 | 6 | 1 | 6 | 7 | 1 |
| `P0_novelty_prior_anchor_failure` | 10 | 4 | 4 | 0 | 6 | 6 | 0 | 6 | 6 | 0 |
| `P0_roleless_stale_entity_failure` | 10 | 1 | 1 | 0 | 4 | 4 | 0 | 4 | 4 | 0 |
| `P0_same_album_ranker_failure` | 10 | 10 | 10 | 0 | 10 | 10 | 0 | 10 | 10 | 0 |
| `P1_positive_tag_retrieval_gap_failure` | 10 | 3 | 4 | 1 | 6 | 7 | 1 | 9 | 9 | 0 |
| `P1_rejection_guardrail_failure` | 10 | 10 | 10 | 0 | 10 | 10 | 0 | 10 | 10 | 0 |
| `P1_temporal_constraint_failure` | 10 | 4 | 4 | 0 | 6 | 7 | 1 | 6 | 7 | 1 |
| `POS_clean_final_hit_control` | 10 | 10 | 10 | 0 | 10 | 10 | 0 | 10 | 10 | 0 |
| `POS_exact_entity_success_control` | 10 | 10 | 10 | 0 | 10 | 10 | 0 | 10 | 10 | 0 |

## Rejected / Deferred Probe

| Branch | Decision | Evidence |
|---|---|---|
| `artist_neighbor_scene_weighted_v3` | reject for now | No unique rescues over current at union@20/50/100. It moved Acknowledge from rank 149 to 128, but still outside @100, and worsened the Gangsta Gangsta near miss from rank 21 to 230. |

## Remaining Gap Diagnosis

- Retriever-fixable now: scene/era/tag/popularity and visual text-to-image are demonstrably useful with current catalog/vector sources.
- State or resolver blocked: at least one artist-neighbor miss is blocked before retrieval; `Mr. Bungle` resolves to the wrong catalog artist, so the neighbor branch has no useful seed.
- Likely new source needed: lyric/hidden-target and sparse-tag cases remain weak; current lyrics dense and catalog tags do not reliably express them.
- Needs hand audit before narrow fixes: some remaining GTs conflict with explicit user constraints, so building a retriever around them may optimize noise.

## Still Missed After Current + Targeted @100

17 / 110 focused turns remain outside union@100 after adding the targeted branches.

| sample | pack | GT | best targeted rank | likely next gap |
|---|---|---|---:|---|
| `41367174-552b-4117-9caa-d0ba1b307d37::t2` | `P0_roleless_stale_entity_failure` | Mercy / Muse | 737 | Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions the... |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | 148 | Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-a... |
| `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2` | `P0_roleless_stale_entity_failure` | Shaft / Kashmere Stage Band |  | Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; onl... |
| `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8` | `P0_roleless_stale_entity_failure` | In the Shadows / The Rasmus |  | Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisf... |
| `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` | `P0_roleless_stale_entity_failure` | I Believe in a Thing Called Love / The Darkness |  | Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions the... |
| `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` | `P0_roleless_stale_entity_failure` | Move Along / The All-American Rejects | 432 | Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; onl... |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | 884 | Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-a... |
| `8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7` | `P0_novelty_prior_anchor_failure` | Transcentience / Animals As Leaders |  | Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisf... |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | 122 | Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisf... |
| `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3` | `P0_novelty_prior_anchor_failure` | Gib ihn einfach (Dies das 2) / Ghanaian Stallion |  | Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisf... |
| `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` | `P0_new_artist_union20_gap_failure` | Hong Kong 2046 / Hong Kong Express |  | Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisf... |
| `907921a3-d08f-4ba1-8cce-0e760a9e7044::t7` | `P0_new_artist_union20_gap_failure` | Sunrise - Slow Hands Remix / Kasper Bjørke |  | Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions the... |
| `324ddfb5-8a18-4729-9acb-c851907a297c::t3` | `P0_new_artist_union20_gap_failure` | Acknowledge / Masta Ace | 149 | Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; onl... |
| `9468e467-d396-461b-be29-b30b6cf87c35::t5` | `P1_temporal_constraint_failure` | Midnight / A Tribe Called Quest | 742 | Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; onl... |
| `e978bb5b-26af-4c7d-b720-b9210bdddf25::t8` | `P1_temporal_constraint_failure` | Dear Yvette / Jane Doe, Masta Ace |  | Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; onl... |
| `c4c0c288-dbcd-4970-ad52-901aafe91b88::t4` | `P1_temporal_constraint_failure` | I Juswanna Chill / Large Professor |  | Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; onl... |
| `ad5348a7-d3bc-4882-bfca-54aa655eac96::t5` | `P1_positive_tag_retrieval_gap_failure` | Glitter / Tyler, The Creator |  | Improve turn-type routing and candidate generation: use listener_goal/current state, role-aware entities, tags, popul... |
