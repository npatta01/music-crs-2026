# State V1 Bridge Retriever-State Validation

This artifact validates the paid DeepSeek V1 extraction against hand labels and checks that the deterministic bridge exposes the compiler-facing state consumed by the current retrievers. It intentionally does not claim full recall lift; that requires a separate tiny retrieval smoke or devset run after this state contract is merged.

## Summary

- Live extractor samples: `56`
- V1 extraction role-label pass rate: `1.000`
- V1->V0Plus projection pass rate after bridge patch: `1.000` (`56/56`)
- Schema-valid live extractions: `1.000`
- Forbidden/stale exact-seed label cases: `24`; old-state positive seed hits on those forbidden values: `24`; V1 positive seed hits: `0`

## What Current Retrievers Need

| Compiler/retriever consumer | Needed state | Validation result |
|---|---|---|
| BM25 multi-field query | Positive `mentioned_entities`: artist/album/track exact terms and tag query facets | Covered by projection labels: 56/56. Bridge patch maps `relation=query_facet` to tag even if coarse type is noisy. |
| Dense attributes branch | Positive tag mentions from query facets | Covered by query-facet labels: 56/56. |
| Resolver / discography | Positive artist/track exact targets only; style refs separately grounded as `style_reference` | Covered by exact seed + style-reference labels: 56/56. Stale satisfied prior entities no longer become exact seeds. Current discography uses exact targets and pivot gating, so style refs are projected but not fully exploited by this branch. |
| Lyric branch | `lyrical_theme` plus lyrical-theme query fact | Covered in lyric hidden-target positive control; projected into positive tag plus `lyrical_theme`. |
| Rejection guardrail | Negative mentions and `explicit_rejections` for hard entity/tag exclusions | Covered by rejection labels: 56/56. |
| Temporal handling | Hard release-date filter only when explicit; style era remains soft release-year signal | Covered by temporal labels: 56/56. |
| Routing/profile | Derived compatibility only; not LLM-owned | Not used as role-label gate. Current `routing_boost` is empty, so profile changes mostly affect intent/process constraints, not branch weights. |
| Style-reference consumption | Prior liked/satisfied artists/tracks as soft anchors, not exact seeds | Projected and resolved correctly. Current configured query IDs mostly consume tags/exact mentions; `similar_artist_anchors` is off and the configured dense templates do not directly use style-reference artist names. This is the main remaining retriever-side gap to test after state. |

## Pack-Level Projection Results

| Pack | Samples | Projection passes |
|---|---:|---:|
| `P0_good_state_ranker_near_miss_failure` | 5 | 5 |
| `P0_named_artist_ranker_failure` | 5 | 5 |
| `P0_new_artist_union20_gap_failure` | 5 | 5 |
| `P0_novelty_prior_anchor_failure` | 5 | 5 |
| `P0_roleless_stale_entity_failure` | 5 | 5 |
| `P0_same_album_ranker_failure` | 5 | 5 |
| `P1_positive_tag_retrieval_gap_failure` | 5 | 5 |
| `P1_rejection_guardrail_failure` | 5 | 5 |
| `P1_temporal_constraint_failure` | 5 | 5 |
| `POS_clean_final_hit_control` | 5 | 5 |
| `POS_exact_entity_success_control` | 6 | 6 |

## Representative Session Comparisons

### `0b9d547f-e748-464a-90e2-2199149f915c::t6`

- Pack: `P0_roleless_stale_entity_failure`; class: `attribute_temporal`
- Current user: Yes! "Can You Feel the Force" is awesome, such a great track. That's exactly the kind of energy I'm looking for. What are some other high-energy, classic disco or funk tracks from that late 70s to early 80s period?
- Retriever need: query facets: high-energy, disco, funk; temporal: kind=['style_era', 'reference_era'] strength=soft filter=False; forbidden exact seeds: The Real Thing
- Old positive inputs: unknown:The Real Thing, tag:high-energy, tag:classic, tag:disco, tag:funk, tag:late 70s, tag:early 80s
- V1 positive inputs: tag:high-energy, tag:classic disco, tag:funk, tag:late 70s to early 80s
- V1 style anchors: track:The Sweetest Pain, track:Georgy Porgy, track:Can You Feel the Force, artist:The Real Thing
- V1 rejections: none
- V1 temporal: {"kind": "style_era", "strength": "soft", "apply_as_filter": false, "range": [1977, 1984]}
- V1 mode/profile: `unknown` / `feature_search`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

### `5f085552-b56b-440e-830b-b4e40b58f854::t6`

- Pack: `P0_novelty_prior_anchor_failure`; class: `attribute_temporal`
- Current user: Yes, Tim McGraw definitely brings that big energy! That's another great anthem from that era. Keep them coming – can you find me another upbeat, high-energy country track from the late 90s or early 2000s that really gets you moving?
- Retriever need: query facets: upbeat, high-energy country; temporal: kind=['style_era', 'reference_era'] strength=soft filter=False
- Old positive inputs: unknown:Tim McGraw, tag:upbeat, tag:high-energy, tag:energetic, tag:country, tag:anthem, tag:stadium-filling, tag:sing-along, tag:rousing, tag:big, +3 more
- V1 positive inputs: tag:country, tag:upbeat high-energy, tag:late 90s or early 2000s, tag:gets you moving
- V1 style anchors: artist:Shania Twain, artist:Tim McGraw
- V1 rejections: none
- V1 temporal: {"kind": "style_era", "strength": "soft", "apply_as_filter": false, "range": [1997, 2004]}
- V1 mode/profile: `unknown` / `feature_search`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

### `0858f444-c9af-4f08-a9fc-2a731a24182b::t5`

- Pack: `P0_roleless_stale_entity_failure`; class: `attribute_refinement`
- Current user: Yes! "Pallbearer" is absolutely brutal, exactly the kind of intricate and relentless breakcore I was hoping for. Great pick! Can you recommend something with a similar raw power and darkness, but maybe a bit more stripped-down or minimalistic in its approac...
- Retriever need: query facets: raw power, darkness, minimalistic
- Old positive inputs: unknown:Igorrr, tag:raw, tag:powerful, tag:dark, tag:stripped-down, tag:minimalistic, tag:intense, tag:electronic, tag:breakcore, tag:industrial
- V1 positive inputs: tag:raw power, tag:darkness, tag:stripped-down minimalistic
- V1 style anchors: track:Pallbearer, artist:Igorrr
- V1 rejections: none
- V1 temporal: null
- V1 mode/profile: `unknown` / `feature_search`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

### `88beb200-0334-4aba-be15-8e1303725766::t6`

- Pack: `P0_novelty_prior_anchor_failure`; class: `hard_rejection`
- Current user: Legend" is a classic, no doubt! I'm good on Drake for now though. I was hoping for some popular Hip-Hop tracks from *other artists* around late 2015 to early 2016. Any major hits from that period by someone different?
- Retriever need: query facets: popular Hip-Hop; exclusions: artist:Drake; temporal: kind=['release_date', 'style_era', 'reference_era'] strength=['hard', 'soft'] filter=[True, False]; forbidden exact seeds: Drake, Drake
- Old positive inputs: unknown:Drake, tag:popular, tag:hip hop, tag:rap, tag:late 2015, tag:early 2016, tag:major hits
- V1 positive inputs: tag:Hip-Hop, tag:hits, tag:late 2015 to early 2016
- V1 style anchors: album:If You're Reading This It's Too Late
- V1 rejections: artist:Drake
- V1 temporal: {"kind": "style_era", "strength": "soft", "apply_as_filter": false, "range": [2015, 2016]}
- V1 mode/profile: `new_artist` / `novelty`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

### `daeef24e-b041-4140-9101-882820c63408::t7`

- Pack: `P0_novelty_prior_anchor_failure`; class: `exact_entity`
- Current user: Okay, it sounds like there's a problem with 'Tom Sawyer'. That's a bummer. Can you please play 'The Spirit of Radio' by Rush instead?
- Retriever need: exact seeds: track:The Spirit of Radio, artist:Rush; exclusions: track:Tom Sawyer; forbidden exact seeds: Tom Sawyer
- Old positive inputs: unknown:Rush, tag:progressive rock
- V1 positive inputs: artist:Rush, track:The Spirit of Radio
- V1 style anchors: none
- V1 rejections: track:Tom Sawyer
- V1 temporal: null
- V1 mode/profile: `unknown` / `exact_probe`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

### `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6`

- Pack: `P0_new_artist_union20_gap_failure`; class: `popular_new_artist`
- Current user: Another fantastic Michael Jackson track! 'Will You Be There' is definitely a powerful and energetic song that everybody knows. These are exactly the kind of widely loved, feel-good hits I enjoy. What other well-known songs do you have that are popular and h...
- Retriever need: query facets: well-known, popular; forbidden exact seeds: Michael Jackson, Michael Jackson
- Old positive inputs: tag:well-known, tag:popular, tag:feel-good, tag:positive energy, tag:upbeat, tag:energetic, tag:not too niche, tag:mainstream
- V1 positive inputs: tag:well-known, tag:popular, tag:feel-good, tag:high-energy, tag:strong beat, tag:pop, tag:R&B
- V1 style anchors: artist:India.Arie, artist:Michael Jackson
- V1 rejections: none
- V1 temporal: null
- V1 mode/profile: `unknown` / `feature_search`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

### `b466a64b-b3cc-4c62-8a70-8261434f915f::t2`

- Pack: `P0_new_artist_union20_gap_failure`; class: `same_style_after_exact`
- Current user: Yes! 'Finally' by CeCe Peniston! That's exactly the track I was trying to remember. Spot on! 'Finally' is it. Can you suggest other iconic 90s dance hits similar to this one?
- Retriever need: query facets: 90s dance hits; forbidden exact seeds: Finally, CeCe Peniston
- Old positive inputs: unknown:CeCe Peniston, tag:energetic, tag:dance, tag:dance-pop, tag:iconic, tag:90s, tag:house
- V1 positive inputs: tag:dance, tag:iconic, tag:1990s
- V1 style anchors: track:Finally, artist:CeCe Peniston
- V1 rejections: none
- V1 temporal: {"kind": "style_era", "strength": "soft", "apply_as_filter": false, "range": [1990, 1999]}
- V1 mode/profile: `unknown` / `continuation`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

### `d5fcb591-3744-4ebb-9d1a-5c57c314b7d0::t5`

- Pack: `P1_temporal_constraint_failure`; class: `temporal_style_era`
- Current user: Yes! "He's the Greatest Dancer" is such a jam! That's exactly the kind of funky, soulful sound from the late 70s I'm looking for. What else do you have from that golden era of R&B?
- Retriever need: query facets: funky, soulful, R&B; temporal: kind=['style_era', 'reference_era'] strength=soft filter=False
- Old positive inputs: unknown:Sister Sledge, tag:R&B, tag:Soul, tag:funky, tag:funk, tag:smooth, tag:soulful, tag:late 70s, tag:early 80s, tag:golden era, +1 more
- V1 positive inputs: tag:R&B, tag:funky, tag:soulful, tag:late 70s
- V1 style anchors: track:He's the Greatest Dancer, artist:Sister Sledge
- V1 rejections: none
- V1 temporal: {"kind": "style_era", "strength": "soft", "apply_as_filter": false, "range": [1977, 1979]}
- V1 mode/profile: `unknown` / `feature_search`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

### `f2d85aa5-2086-4b1e-9974-d188c43621db::t8`

- Pack: `P1_temporal_constraint_failure`; class: `negative_feedback_temporal`
- Current user: Unfortunately, 'Sleep Paralysis' is not what I'm looking for at all. The mood is too dark and harsh, not dreamy or serene like the late 2000s ambient electronic I'm trying to find. Also, the era is still off. I'm specifically looking for something with a wa...
- Retriever need: query facets: dreamy, serene, ambient electronic; exclusions: style:dark and harsh; temporal: kind=['style_era', 'reference_era'] strength=soft filter=False
- Old positive inputs: tag:ambient electronic, tag:dreamy, tag:atmospheric, tag:ethereal, tag:shimmering, tag:serene, tag:melancholic, tag:floating, tag:introspective, tag:warm, +2 more
- V1 positive inputs: tag:dreamy, tag:serene, tag:warm evolving pads, tag:subtle rhythms, tag:ethereal evolving atmosphere, tag:instrumental, tag:ambient electronic, tag:late 2000s
- V1 style anchors: none
- V1 rejections: track:Sleep Paralysis, artist:Sidewalks and Skeletons, tag:dark and harsh
- V1 temporal: {"kind": "style_era", "strength": "soft", "apply_as_filter": false, "range": [2007, 2009]}
- V1 mode/profile: `unknown` / `hidden_target_search`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

### `1c567917-f931-4609-9695-a9c0f8e39f3d::t2`

- Pack: `P1_positive_tag_retrieval_gap_failure`; class: `genre_search`
- Current user: That's a good start! Anitta is definitely on point for contemporary pop. What about something more recent and upbeat, specifically from the 'tecno brega' or 'funk carioca' scenes?
- Retriever need: query facets: tecno brega, funk carioca; forbidden exact seeds: Anitta, Anitta
- Old positive inputs: unknown:Anitta, tag:Brazilian, tag:contemporary, tag:dance, tag:pop, tag:recent, tag:upbeat, tag:tecno brega, tag:funk carioca, tag:funk
- V1 positive inputs: tag:tecno brega, tag:funk carioca, tag:upbeat, tag:recent
- V1 style anchors: artist:Anitta
- V1 rejections: none
- V1 temporal: null
- V1 mode/profile: `unknown` / `feature_search`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

### `a9b423bf-d05c-418d-98af-2a3b1e1d7917::t1`

- Pack: `POS_clean_final_hit_control`; class: `lyric_hidden_target`
- Current user: Play the classic Ice Cube song from the 90s that starts with "Just wakin' up in the morning, gotta thank God".
- Retriever need: exact seeds: artist:Ice Cube; query facets: Just wakin' up in the morning; temporal: kind=['style_era', 'reference_era'] strength=soft filter=False
- Old positive inputs: unknown:Ice Cube, tag:classic, tag:90s, tag:hip hop
- V1 positive inputs: artist:Ice Cube, tag:Just wakin' up in the morning, gotta thank God, tag:classic, tag:1990s
- V1 style anchors: none
- V1 rejections: none
- V1 temporal: {"kind": "style_era", "strength": "soft", "apply_as_filter": false, "range": [1990, 1999]}
- V1 mode/profile: `unknown` / `hidden_target_search`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

### `737a65cf-9c45-4b1d-910d-2f1f1ef5eab7::t8`

- Pack: `POS_clean_final_hit_control`; class: `same_artist_album`
- Current user: Yeah, "On Melancholy Hill" is a definite vibe! You got that right. What about a Gorillaz track with a more upbeat or quirky electronic feel, maybe something that's more instrumental-focused or from one of their newer albums like 'Cracker Island'?
- Retriever need: exact seeds: artist:Gorillaz, album:Cracker Island; query facets: upbeat, quirky electronic
- Old positive inputs: unknown:Gorillaz, tag:upbeat, tag:quirky, tag:electronic, tag:instrumental, tag:instrumental-focused
- V1 positive inputs: artist:Gorillaz, album:Cracker Island, tag:upbeat, tag:quirky electronic, tag:instrumental-focused
- V1 style anchors: none
- V1 rejections: none
- V1 temporal: null
- V1 mode/profile: `same_artist` / `continuation`
- Verdict: projection label `pass`; retriever-facing fields contain the labeled exact/tag/style/rejection/temporal inputs.

## Residual Risk

- This validates extraction and bridge projection, not full candidate recall. The next validation should run a tiny retrieval smoke on 10-20 sessions per failure class and compare union@20/union@100 or at least branch-pool hit movement.
- The old generic replay scorer still marks some `target_artist_mode` / `retrieval_profile` cases as failures because those labels encode the previous LLM-owned policy contract. For V1, use role/projection labels as the state acceptance gate.
- `routing_boost` remains empty in the reference config, so V1 state can expose clearer routing evidence without current branch weighting changing. If candidate recall stays low after state fixes, branch weighting or candidate generation should be tested separately.
- Style-reference anchors are the strongest remaining consumption gap: V1 separates them correctly, but the current reference config mainly uses exact mentions and tag facets in active query builders. A follow-up retrieval smoke should test enabling style-reference-aware dense queries or `enable_similar_artist_anchors` on the focused failure packs.
