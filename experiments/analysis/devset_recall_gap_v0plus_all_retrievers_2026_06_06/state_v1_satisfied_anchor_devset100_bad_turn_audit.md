# State V1 Devset-100 Bad-Turn Audit

Date: 2026-06-08

Scope: 100 deterministic devset sessions, 800 turns, Modal inference on the current branch. This is a smoke diagnostic, not a leaderboard claim.

## Headline

The 100-session smoke does **not** validate the current satisfied-anchor candidate change as a top-20 improvement. It slightly expands deep branch union, but top-20 candidate quality and final top-20 are worse than the old same-subset artifact.

| Metric | Old same 100 | New smoke | Delta |
| --- | ---: | ---: | ---: |
| Final Hit@20 | 0.2612 | 0.2400 | -0.0212 |
| Final Hit@100 | 0.4388 | 0.4062 | -0.0325 |
| Final Hit@1000 | 0.6975 | 0.6525 | -0.0450 |
| NDCG@20 | 0.1121 | 0.1116 | -0.0005 |
| union@20 | 0.4400 | 0.4250 | -0.0150 |
| union@50 | 0.5413 | 0.5437 | +0.0025 |
| union@100 | 0.6238 | 0.6275 | +0.0037 |
| union@200 | 0.7150 | 0.7388 | +0.0238 |
| union@1000 | 0.8962 | 0.9050 | +0.0088 |
| Fusion efficiency @20 | 0.5938 | 0.5647 | -0.0290 |

Caveat: the old comparison is an older full-devset artifact filtered to the same 100 sessions. Treat this as directional, not a perfect single-change A/B.

## Bad-Turn Anatomy

Final top-20 misses: 608/800 (76.0%).

| Final rank bucket | Turns |
| --- | ---: |
| absent_gt_not_in_top1000 | 278 |
| hit_top20 | 192 |
| rank_201_1000 | 140 |
| rank_21_50 | 77 |
| rank_101_200 | 57 |
| rank_51_100 | 56 |

For final@20 misses only:

| Failure class from branch union | Turns | Read |
| --- | ---: | --- |
| union_top20_final_selection_gap | 152 | GT is already in a branch top-20, but fusion/final rank loses it. |
| union_21_50_branch_rank_gap | 91 | Retriever has GT close; branch-local scoring or fusion could rescue. |
| union_51_100_branch_rank_gap | 67 | Retriever has signal but not sharply enough for top-20. |
| union_101_200_branch_rank_gap | 89 | Weak branch/source signal. |
| union_201_1000_deep_source_gap | 133 | Candidate source can express it only very weakly. |
| union_absent_top1000_source_gap | 74 | No current branch surfaces GT in top1000. |
| no_branch_trace_extractor_failure | 2 | Extractor failed/empty candidate row. |

Interpretation: this is not one monolithic failure. There are three big buckets: final selection misses when union already has the answer, branch-local rank gaps where GT is around 21-100, and true source gaps where no existing branch gets close.

## Turn Position

| Turn | Final Hit@20 | Union@20 | Union@100 | Final misses |
| --- | ---: | ---: | ---: | ---: |
| 1 | 0.180 | 0.340 | 0.550 | 82 |
| 2 | 0.370 | 0.530 | 0.730 | 63 |
| 3 | 0.330 | 0.440 | 0.630 | 67 |
| 4 | 0.220 | 0.420 | 0.590 | 78 |
| 5 | 0.200 | 0.410 | 0.630 | 80 |
| 6 | 0.240 | 0.480 | 0.640 | 76 |
| 7 | 0.230 | 0.410 | 0.590 | 77 |
| 8 | 0.150 | 0.370 | 0.660 | 85 |

Late turns remain bad. Turn 8 has only 15% final Hit@20; the issue is partly source coverage and partly accumulated state/fusion noise.

## Old/New Movement

| Movement | Turns |
| --- | ---: |
| both_miss20 | 544 |
| both_hit20 | 145 |
| regressed_old_hit_new_miss | 64 |
| rescued_old_miss_new_hit | 47 |

Regressions old-hit/new-miss: 64. Rescues old-miss/new-hit: 47. Net top-20 movement: -17 turns.

## State/Routing Slices On Final Misses

| Request type | Final misses |
| --- | ---: |
| attribute_search | 377 |
| new_artist | 110 |
| hidden_target | 42 |
| exact_track | 21 |
| same_artist | 20 |
| unknown | 18 |
| similar_to_prior | 14 |
| exact_album | 2 |
| exact_artist | 2 |
| same_album | 2 |

| Active routing tag | Final misses where active |
| --- | ---: |
| feature_articulation | 393 |
| lyric_search | 133 |
| hidden_target_search | 42 |
| exact_entity_probe | 25 |
| image_or_visual_search | 15 |

The extractor is producing useful request/state signals on many misses; the problem is that the branch/fusion layer does not always turn those signals into top-20 candidates. Lyrical/theme and visual/attribute requests still look weak unless a branch has a high-quality matching source.

## Best Branch When Final Misses Still Have GT Somewhere

| Best branch | Final misses where this is closest branch |
| --- | ---: |
| bm25 | 69 |
| centroid.anchor_tracks.image_siglip2 | 66 |
| centroid.user.cf_bpr | 49 |
| centroid.anchor_tracks.cf_bpr | 46 |
| centroid.anchor_tracks.audio_laion_clap | 44 |
| dense.qwen_8b.intent.metadata_qwen3_embedding_8b | 43 |
| dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b | 32 |
| dense.qwen_8b.attributes.attributes_qwen3_embedding_8b | 26 |
| dense.clap_text.sonic_nl.audio_laion_clap | 24 |
| dense.qwen_8b.metadata.metadata_qwen3_embedding_8b | 24 |
| dense.qwen_0_6b.intent.metadata_qwen3_embedding_0_6b | 21 |
| dense.clap_text.sonic.audio_laion_clap | 18 |
| dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b | 17 |
| dense.clap_text.sonic_nl_enriched.audio_laion_clap | 14 |
| dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b | 13 |

Qwen-8B intent/metadata and anchor image/CF are doing most of the heavy lifting. BM25 is still useful, but the new run reduced BM25 and qwen metadata per-branch recall versus the old artifact while adding deeper branch coverage.

## Concrete Examples

### fusion_gap_union_top20_but_final_miss

- `0979c6fc-c382-4c14-be3e-2a4711fcc532::t1` GT=Hard Times by Cro-Mags; final=41; old=134; union=2 via `dense.qwen_8b.intent.metadata_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: I'm looking for 80s American hardcore punk bands known for their raw energy and short, intense songs.
  Read: union_top20_final_selection_gap
- `0979c6fc-c382-4c14-be3e-2a4711fcc532::t2` GT=Fuck Authority by Wasted Youth; final=80; old=137; union=19 via `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b`; request=similar_to_prior; profile=continuation; routing=none
  User: Yes, Cro-Mags is a great pick for that raw, intense 80s hardcore sound. Can you recommend a few more bands with that same kind of aggressive, no-frills energy and short song structures?
  Read: union_top20_final_selection_gap
- `0979c6fc-c382-4c14-be3e-2a4711fcc532::t4` GT=Too Drunk to Fuck by Dead Kennedys; final=76; old=74; union=4 via `centroid.anchor_tracks.image_siglip2`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Dead Kennedys, yes! "California Uber Alles" is perfect for that politically charged, critical punk sound. They're legends. Now that we've explored that, how about some more 80s American hardcore punk bands that incorporated a bit more melody or even some meta…
  Read: union_top20_final_selection_gap
- `24fd6c9f-b4e8-4077-8fcf-9c49528802f1::t3` GT=A Different World (feat. Corey Taylor) by Corey Taylor; final=26; old=1; union=20 via `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: YES! That was much closer to what I'm looking for. The raw energy and intensity of "Rotting In Vain" definitely resonated with me. I'm especially drawn to the vocal performance in that one. Is it the raw emotion in the vocals or perhaps the distorted, heavy i…
  Read: union_top20_final_selection_gap
- `24fd6c9f-b4e8-4077-8fcf-9c49528802f1::t4` GT=Everything Falls Apart by Korn; final=None; old=171; union=19 via `centroid.anchor_tracks.image_siglip2`; request=new_artist; profile=novelty; routing=none
  User: Yes, that was great! "A Different World" absolutely showcased that powerful vocal performance, and the way it interacts with the heavy, driving guitar riffs is exactly what I'm drawn to. It feels very cathartic. So, I'm thinking I really connect with songs th…
  Read: union_top20_final_selection_gap
- `19c7e5bf-0797-40c5-b798-4d024af9558d::t2` GT=Burn by Phillipa Soo; final=164; old=47; union=4 via `centroid.anchor_tracks.cf_bpr`; request=attribute_search; profile=feature_search; routing=feature_articulation,lyric_search
  User: Yes, "It's Quiet Uptown" is exactly what I meant! It's incredibly powerful and captures that feeling perfectly. Can you give me more songs about processing grief and finding a path forward, rather than just despair? I'm looking for that resilient determinatio…
  Read: union_top20_final_selection_gap
- `19c7e5bf-0797-40c5-b798-4d024af9558d::t4` GT=Satisfied by Original Broadway Cast of Hamilton; final=26; old=281; union=1 via `centroid.anchor_tracks.image_siglip2`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Oh, "Once Upon a December" is a classic! It absolutely has that beautiful, dramatic longing I enjoy in musicals. I'm definitely looking for more songs with that kind of deep, expressive emotion. Do you have any other suggestions, perhaps something with a gran…
  Read: union_top20_final_selection_gap
- `99f954b6-6784-4db4-8b3a-0b967e447770::t2` GT=Pyramids by Frank Ocean; final=None; old=1; union=5 via `bm25`; request=hidden_target; profile=hidden_target_search; routing=hidden_target_search
  User: Super Rich Kids" is a classic, no doubt, and it's definitely from that era. But it's not quite the one. I'm thinking of something with a more soulful, introspective sound. Maybe something with a bit of a dreamy or hazy feel, not too upbeat.
  Read: union_top20_final_selection_gap

### branch_rank_gap_union_21_100

- `24fd6c9f-b4e8-4077-8fcf-9c49528802f1::t2` GT=Rotting In Vain by Korn; final=988; old=355; union=42 via `centroid.user.cf_bpr`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: That was interesting! I can definitely appreciate the rock sound, but it didn't quite hit me on that deeper level I'm looking for. It felt a bit... straightforward. Can you play something that has a more intense or complex emotional soundscape, maybe with som…
  Read: union_21_50_branch_rank_gap
- `19c7e5bf-0797-40c5-b798-4d024af9558d::t3` GT=Once Upon a December by Christy Altomare; final=212; old=98; union=56 via `dense.clap_text.sonic.audio_laion_clap`; request=new_artist; profile=novelty; routing=lyric_search
  User: Yes, "Burn" is absolutely perfect! Both "It's Quiet Uptown" and "Burn" truly resonate with the dramatic and poignant themes I wanted to explore, capturing that nuanced emotional intensity beautifully. You've hit the nail on the head. Can you give me more song…
  Read: union_51_100_branch_rank_gap
- `19c7e5bf-0797-40c5-b798-4d024af9558d::t5` GT=A Girl Worth Fighting For by Harvey Fierstein; final=129; old=171; union=41 via `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Oh, "Satisfied" is brilliant! That's exactly the kind of sweeping emotional arc and powerful dramatic build-up I was hoping for. It's so complex and moving. I'm loving these recommendations. Can you suggest more songs, perhaps from other Broadway shows, that …
  Read: union_21_50_branch_rank_gap
- `19c7e5bf-0797-40c5-b798-4d024af9558d::t6` GT=The Reynolds Pamphlet by Original Broadway Cast of Hamilton; final=49; old=16; union=28 via `dense.qwen_8b.intent.metadata_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation,lyric_search
  User: A Girl Worth Fighting For" is a great song from Mulan, and I appreciate the determination in it. However, I was hoping for something with a bit more of that intense, complex emotional depth, particularly with a strong female vocal performance like "Satisfied.…
  Read: union_21_50_branch_rank_gap
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t7` GT=Face Down by The Red Jumpsuit Apparatus; final=246; old=67; union=75 via `centroid.user.cf_bpr`; request=hidden_target; profile=hidden_target_search; routing=hidden_target_search
  User: Oh, '21 Guns' is a classic Green Day song and it's definitely anthemic, but that's a bit later than the early 2000s sound I'm thinking of, like before 2006. I'm really trying to find a song that screams *early* 2000s, like 2000-2005. Something with that iconi…
  Read: union_51_100_branch_rank_gap
- `e0631f94-a91d-4357-a7b2-cd82ea639a7a::t1` GT=Sinner by Lincoln Durham; final=36; old=409; union=51 via `dense.clap_text.sonic_nl.audio_laion_clap`; request=attribute_search; profile=feature_search; routing=feature_articulation,lyric_search
  User: Do you have any tracks that tell stories about the devil, sin, or damnation, preferably with a Southern Gothic or Americana sound?
  Read: union_51_100_branch_rank_gap
- `e0631f94-a91d-4357-a7b2-cd82ea639a7a::t2` GT=Too Old to Die Young by Brother Dege; final=485; old=439; union=99 via `bm25`; request=attribute_search; profile=feature_search; routing=feature_articulation,lyric_search
  User: Yes! "Sinner" is exactly the kind of gritty, dark track I was hoping for. That Southern Gothic vibe is perfect. Can you give me more songs that explore not just sin, but also the consequences and maybe even redemption, keeping that blues rock or Americana fee…
  Read: union_51_100_branch_rank_gap
- `e0631f94-a91d-4357-a7b2-cd82ea639a7a::t6` GT=Some Of Adam's Blues by Quaker City Night Hawks; final=62; old=11; union=43 via `dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Yes, "Kiss It" is awesome! Dorothy just keeps delivering. I love that raw energy. Do you have any more recommendations for bands or artists, male or female vocalists, who have a similar gritty, heavy blues rock sound, maybe with a really distinctive guitar ri…
  Read: union_21_50_branch_rank_gap

### deep_source_gap_union_101_1000

- `0979c6fc-c382-4c14-be3e-2a4711fcc532::t3` GT=California Uber Alles by Dead Kennedys; final=119; old=62; union=128 via `bm25`; request=attribute_search; profile=feature_search; routing=feature_articulation,lyric_search
  User: Yes, Wasted Youth's "Fuck Authority" is absolutely spot on! That's exactly the kind of aggressive, no-frills 80s hardcore I'm into. These bands truly represent the core of classic punk. What about some other bands from that same era that had a particularly st…
  Read: union_101_200_branch_rank_gap
- `0979c6fc-c382-4c14-be3e-2a4711fcc532::t5` GT=High Hopes by Gorilla Biscuits; final=427; old=208; union=178 via `bm25`; request=attribute_search; profile=feature_search; routing=feature_articulation,lyric_search
  User: Another Dead Kennedys classic, awesome! I appreciate the continued focus on politically charged punk. But I was hoping for something with a bit more *melody* or even some *metallic* influences mixed into that 80s hardcore sound. Any bands come to mind that bl…
  Read: union_101_200_branch_rank_gap
- `0979c6fc-c382-4c14-be3e-2a4711fcc532::t6` GT=Waiting Room by Fugazi; final=291; old=491; union=120 via `centroid.anchor_tracks.cf_bpr`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Yes! Gorilla Biscuits "High Hopes" is spot on for that melodic hardcore sound with raw energy. Love it. Can you now give me some classic 80s American hardcore bands that had a really distinctive, almost chaotic or noisy, sound? I'm thinking less melodic, more…
  Read: union_101_200_branch_rank_gap
- `0979c6fc-c382-4c14-be3e-2a4711fcc532::t7` GT=Bad Mouth by Fugazi; final=199; old=47; union=109 via `dense.qwen_8b.intent.metadata_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Fugazi is legendary, and "Waiting Room" is a classic, but I was looking for something a bit more sonically chaotic and abrasive for that distinct 80s American hardcore sound. Can you recommend bands that pushed the boundaries with noise, feedback, or a more u…
  Read: union_101_200_branch_rank_gap
- `0979c6fc-c382-4c14-be3e-2a4711fcc532::t8` GT=Tough Guy by Beastie Boys; final=None; old=None; union=201 via `dense.qwen_8b.intent.metadata_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Still solid, but I'm really trying to dig into the more *extreme* and *sonically challenging* side of 80s American hardcore. Think bands that were deliberately noisy, heavily distorted, or had a more unhinged, almost brutal approach. Any recommendations for b…
  Read: union_201_1000_deep_source_gap
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t1` GT=Girl All the Bad Guys Want by Bowling For Soup; final=95; old=323; union=105 via `dense.clap_text.sonic.audio_laion_clap`; request=hidden_target; profile=hidden_target_search; routing=hidden_target_search
  User: I'm trying to think of a song that really captures the energetic, slightly angsty pop-punk vibe from the early 2000s.
  Read: union_101_200_branch_rank_gap
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2` GT=Move Along by The All-American Rejects; final=391; old=113; union=142 via `centroid.user.cf_bpr`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: That's a good one, it totally brings back early 2000s pop-punk! It's got the energy, but I'm looking for something that feels a bit more... not quite heavier, but with a stronger angsty feel. Still from that early 2000s pop-punk or alternative rock vibe, mayb…
  Read: union_101_200_branch_rank_gap
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t4` GT=Tonight Tonight by Hot Chelle Rae; final=None; old=None; union=244 via `centroid.user.cf_bpr`; request=hidden_target; profile=hidden_target_search; routing=hidden_target_search
  User: Okay, 'The Diary of Jane' is a solid track and definitely from that era with a powerful riff, I can see why you'd recommend it! It's got the angsty alternative feel. But I'm still feeling like the song I'm thinking of was a bit more on the *pop-rock* side, yo…
  Read: union_201_1000_deep_source_gap

### source_absent_gap

- `24fd6c9f-b4e8-4077-8fcf-9c49528802f1::t1` GT=Fracasso by Pitty; final=None; old=None; union=None via `None`; request=unknown; profile=feature_search; routing=feature_articulation
  User: I'm trying to figure out what kind of music I really connect with on a deeper level. Can you play something that might help me explore my tastes?
  Read: union_absent_top1000_source_gap
- `24fd6c9f-b4e8-4077-8fcf-9c49528802f1::t5` GT=Stargazer by Rx Bandits; final=None; old=None; union=None via `None`; request=new_artist; profile=novelty; routing=none
  User: YES! "Everything Falls Apart" truly solidifies what I've been realizing. I've found it! I'm truly into songs with powerful, cathartic vocal performances and driving, distorted guitar riffs. It doesn't even have to be super heavy all the time, as long as it ha…
  Read: union_absent_top1000_source_gap
- `19c7e5bf-0797-40c5-b798-4d024af9558d::t1` GT=It's Quiet Uptown by Lin-Manuel Miranda; final=None; old=None; union=None via `None`; request=attribute_search; profile=feature_search; routing=feature_articulation,lyric_search
  User: I'm looking for music that expresses a powerful sense of loss or deep sadness, but with an undercurrent of strength.
  Read: union_absent_top1000_source_gap
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t3` GT=The Diary of Jane by Breaking Benjamin; final=None; old=None; union=None via `None`; request=hidden_target; profile=hidden_target_search; routing=hidden_target_search
  User: Yes! 'Move Along' is *much* closer, it totally has that anthemic, angsty vibe from the early 2000s and I remember it being everywhere. It's a great example of the era's sound. But I'm still trying to think of *the* song, you know? Something that has a really …
  Read: union_absent_top1000_source_gap
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t8` GT=Revolution Radio by Green Day; final=None; old=None; union=None via `None`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Yes! That's exactly the sound of that era I was trying to pinpoint, perfect! 'Face Down' totally captures that angsty, powerful, radio-friendly alternative rock vibe from the early 2000s. It's spot on! Now that you've nailed that, can you recommend some other…
  Read: union_absent_top1000_source_gap
- `99f954b6-6784-4db4-8b3a-0b967e447770::t6` GT=Wildfire by John Mayer; final=None; old=None; union=None via `None`; request=new_artist; profile=novelty; routing=none
  User: Pilot Jones" is fantastic and absolutely hits that intimate, hazy R&B vibe I love from Frank Ocean. It's a perfect example of his sound from that era! But I'm actually trying to discover artists *other than* Frank Ocean who also captured that unique early 201…
  Read: union_absent_top1000_source_gap
- `b4ffa800-8173-4f16-800a-4b5e765d7f80::t1` GT=I Want You (She's So Heavy) - Remastered 2009 by The Beatles; final=None; old=None; union=None via `None`; request=hidden_target; profile=hidden_target_search; routing=hidden_target_search,image_or_visual_search
  User: I'm trying to think of a classic rock album with a really famous cover, kind of a simple, outdoor scene.
  Read: union_absent_top1000_source_gap
- `b4ffa800-8173-4f16-800a-4b5e765d7f80::t6` GT=Tempo Perdido by Legião Urbana; final=None; old=None; union=None via `None`; request=exact_track; profile=exact_probe; routing=exact_entity_probe
  User: Wait, I don't think you've played "I Want You (She's So Heavy)" from Abbey Road yet! You played other Beatles songs. Can you please play "I Want You (She's So Heavy)" from Abbey Road now?
  Read: union_absent_top1000_source_gap

### extractor_failures

- `c1c115ca-eae2-43b9-a8cf-9bdb349d95d8::t3` GT=Winter’s Wolves by The Sword; final=None; old=1; union=None via `None`; request=unknown; profile=None; routing=none
  User: Yes! The Sword is definitely the band I was thinking of! You're on the right track now. That epic fantasy sound is spot on. I'm trying to remember a particular song of theirs though, I think the lyrics might have mentioned something about winter or wolves, an…
  Read: no_branch_trace_extractor_failure
- `c1c115ca-eae2-43b9-a8cf-9bdb349d95d8::t7` GT=Wolf's Blood by Pentagram; final=None; old=None; union=None via `None`; request=unknown; profile=None; routing=none
  User: Yes! "Barael's Blade" is a fantastic example of what I'm looking for – that epic, intricate, heavy sound from The Sword. You totally get it. Now, can you suggest another band that has that similar epic, fantasy-driven, heavy stoner or traditional doom sound, …
  Read: no_branch_trace_extractor_failure

### regressed_old_hit_new_miss

- `24fd6c9f-b4e8-4077-8fcf-9c49528802f1::t3` GT=A Different World (feat. Corey Taylor) by Corey Taylor; final=26; old=1; union=20 via `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: YES! That was much closer to what I'm looking for. The raw energy and intensity of "Rotting In Vain" definitely resonated with me. I'm especially drawn to the vocal performance in that one. Is it the raw emotion in the vocals or perhaps the distorted, heavy i…
  Read: union_top20_final_selection_gap
- `19c7e5bf-0797-40c5-b798-4d024af9558d::t6` GT=The Reynolds Pamphlet by Original Broadway Cast of Hamilton; final=49; old=16; union=28 via `dense.qwen_8b.intent.metadata_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation,lyric_search
  User: A Girl Worth Fighting For" is a great song from Mulan, and I appreciate the determination in it. However, I was hoping for something with a bit more of that intense, complex emotional depth, particularly with a strong female vocal performance like "Satisfied.…
  Read: union_21_50_branch_rank_gap
- `99f954b6-6784-4db4-8b3a-0b967e447770::t2` GT=Pyramids by Frank Ocean; final=None; old=1; union=5 via `bm25`; request=hidden_target; profile=hidden_target_search; routing=hidden_target_search
  User: Super Rich Kids" is a classic, no doubt, and it's definitely from that era. But it's not quite the one. I'm thinking of something with a more soulful, introspective sound. Maybe something with a bit of a dreamy or hazy feel, not too upbeat.
  Read: union_top20_final_selection_gap
- `99f954b6-6784-4db4-8b3a-0b967e447770::t5` GT=Pilot Jones by Frank Ocean; final=25; old=12; union=10 via `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b`; request=new_artist; profile=novelty; routing=none
  User: Yes, "Superpower" is a fantastic choice! It perfectly continues that mood and sound from the early 2010s. I appreciate that one. Do you have any other recommendations that really capture that same intimate, atmospheric neo-soul/alt-R&B feel, maybe by artists …
  Read: union_top20_final_selection_gap
- `b60dab84-45ca-4b1f-b3ff-497604217af5::t8` GT=March Into the Sea by Modest Mouse; final=26; old=9; union=1 via `centroid.anchor_tracks.image_siglip2`; request=unknown; profile=feature_search; routing=feature_articulation
  User: Parting of the Sensory" is such a powerful song! What a great way to wrap things up. Thanks so much for all the awesome Modest Mouse recommendations today!
  Read: union_top20_final_selection_gap
- `e0631f94-a91d-4357-a7b2-cd82ea639a7a::t6` GT=Some Of Adam's Blues by Quaker City Night Hawks; final=62; old=11; union=43 via `dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Yes, "Kiss It" is awesome! Dorothy just keeps delivering. I love that raw energy. Do you have any more recommendations for bands or artists, male or female vocalists, who have a similar gritty, heavy blues rock sound, maybe with a really distinctive guitar ri…
  Read: union_21_50_branch_rank_gap
- `2017c0cd-92c6-4877-845d-abd377f44028::t8` GT=Too Old to Die Young by Brother Dege; final=206; old=18; union=82 via `dense.qwen_8b.intent.metadata_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation,lyric_search
  User: Yes, "The Preacher" is amazing! That raw, deep male vocal and the powerful storytelling are exactly what I wanted. This whole vibe is just perfect. What other artists or tracks do you have that dive deep into intense, bluesy narratives with strong, gritty voc…
  Read: union_51_100_branch_rank_gap
- `1dbc5930-21a7-41ab-82d3-0f1d278eac2e::t5` GT=Bomb (feat. Raekwon) by Raekwon; final=25; old=11; union=14 via `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Yes! "Ronnie Drake" is a classic too. This collection really captures the essence of 2014 hip-hop. Thanks! I've found some excellent tracks from that year, exactly what I was looking for in terms of discovery. What else you got for me?
  Read: union_top20_final_selection_gap

### rescued_old_miss_new_hit

- `b60dab84-45ca-4b1f-b3ff-497604217af5::t4` GT=Strangers to Ourselves by Modest Mouse; final=11; old=21; union=1 via `dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b`; request=same_artist; profile=continuation; routing=none
  User: Oh yeah, "Spitting Venom" is super good! I love how it builds up. Do you have any other Modest Mouse songs that are a bit more, like, chill or atmospheric?
  Read: union_top20_final_selection_gap
- `2017c0cd-92c6-4877-845d-abd377f44028::t5` GT=Ballad of a Prodigal Son by Lincoln Durham; final=2; old=65; union=6 via `dense.qwen_0_6b.intent.metadata_qwen3_embedding_0_6b`; request=attribute_search; profile=feature_search; routing=feature_articulation,lyric_search
  User: Oh wow, 'Sinner' is incredible! The raw, bluesy feel and those themes are exactly what I'm looking for. This is really hitting the mark. Do you have any more tracks like this, with that deep, powerful, Southern gothic storytelling?
  Read: union_top20_final_selection_gap
- `1dbc5930-21a7-41ab-82d3-0f1d278eac2e::t4` GT=Ronnie Drake (feat. SZA) by Isaiah Rashad; final=10; old=41; union=28 via `bm25`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Yo, "West Savannah" is dope! I definitely know Isaiah Rashad. "Cilvia Demo" was a big one. You're really helping me discover some key stuff from 2014. What's another standout track or album from that year?
  Read: union_21_50_branch_rank_gap
- `b38bed11-2d23-4518-9751-66f0a433d145::t2` GT=The Journey To The Grey Havens - feat. Sir James Galway by Howard Shore; final=17; old=55; union=14 via `dense.qwen_0_6b.attributes_enriched.attributes_qwen3_embedding_0_6b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Yes, this is exactly the kind of sound I'm looking for! It definitely feels like a movie soundtrack. Can you recommend something similar, perhaps with sweeping orchestral sounds that would fit a fantasy adventure?
  Read: union_top20_final_selection_gap
- `326e2ba3-7394-435b-a104-0212ce618bfe::t7` GT=Blue Spark VIP by Flite; final=3; old=21; union=11 via `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Yes, "Reach VIP" is massive! That driving bassline is exactly what I'm looking for. Can you recommend some more high-energy, instrumental liquid D&B, but perhaps with a slightly darker or more atmospheric edge while still maintaining that powerful, driving rh…
  Read: union_top20_final_selection_gap
- `b2e2ef18-7ad7-4c93-a16b-8e09b90d7224::t7` GT=Distress Signal by Lazerhawk; final=7; old=33; union=10 via `bm25`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Yeah! 'King of the Streets' is awesome too, classic Lazerhawk! Definitely keeps that high-energy, dark synthwave vibe going. I'm loving these tracks! What else do you have that's like this, maybe some more high-energy synthwave for a late-night drive?
  Read: union_top20_final_selection_gap
- `b2e2ef18-7ad7-4c93-a16b-8e09b90d7224::t8` GT=Pedal to the Metal by Lazerhawk; final=20; old=47; union=6 via `bm25`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Another banger! 'Distress Signal' is awesome, it's got that classic driving energy I love. You're really nailing these recommendations! Keep them coming, what other killer synthwave tracks do you have for me?
  Read: union_top20_final_selection_gap
- `37bca2c1-00ba-42e8-83c0-1a7ea415b198::t6` GT=Audrey's Dance - Instrumental by Angelo Badalamenti; final=2; old=56; union=5 via `centroid.anchor_tracks.image_siglip2`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Hmm, this is a bit too energetic and not quite what I had in mind for the 'dark, cinematic' feel. Can we go back to something more atmospheric and instrumental? Maybe something that feels more like a mysterious dream or a slow, brooding electronic score?
  Read: union_top20_final_selection_gap

### late_turn_8_misses

- `0979c6fc-c382-4c14-be3e-2a4711fcc532::t8` GT=Tough Guy by Beastie Boys; final=None; old=None; union=201 via `dense.qwen_8b.intent.metadata_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Still solid, but I'm really trying to dig into the more *extreme* and *sonically challenging* side of 80s American hardcore. Think bands that were deliberately noisy, heavily distorted, or had a more unhinged, almost brutal approach. Any recommendations for b…
  Read: union_201_1000_deep_source_gap
- `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t8` GT=Revolution Radio by Green Day; final=None; old=None; union=None via `None`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Yes! That's exactly the sound of that era I was trying to pinpoint, perfect! 'Face Down' totally captures that angsty, powerful, radio-friendly alternative rock vibe from the early 2000s. It's spot on! Now that you've nailed that, can you recommend some other…
  Read: union_absent_top1000_source_gap
- `99f954b6-6784-4db4-8b3a-0b967e447770::t8` GT=Novacane by Frank Ocean; final=None; old=22; union=1 via `dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: 911 / Mr. Lonely" is a solid track and definitely has a cool, soulful vibe, but it's from 2017, which feels a little outside that *early* 2010s period I'm trying to stick to. I'm really looking for that raw, atmospheric R&B from more around 2011-2014. Any oth…
  Read: union_top20_final_selection_gap
- `b60dab84-45ca-4b1f-b3ff-497604217af5::t8` GT=March Into the Sea by Modest Mouse; final=26; old=9; union=1 via `centroid.anchor_tracks.image_siglip2`; request=unknown; profile=feature_search; routing=feature_articulation
  User: Parting of the Sensory" is such a powerful song! What a great way to wrap things up. Thanks so much for all the awesome Modest Mouse recommendations today!
  Read: union_top20_final_selection_gap
- `e0631f94-a91d-4357-a7b2-cd82ea639a7a::t8` GT=Bartholomew by The Silent Comedy; final=512; old=888; union=132 via `dense.qwen_8b.attributes_enriched.attributes_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Snake Song" is really cool, I like the raw and authentic feel of it and the dark lyrics. It's got a really unique sound. Do you have any other artists that blend this kind of dark folk or Americana with a slightly heavier, perhaps more psychedelic rock elemen…
  Read: union_101_200_branch_rank_gap
- `2017c0cd-92c6-4877-845d-abd377f44028::t8` GT=Too Old to Die Young by Brother Dege; final=206; old=18; union=82 via `dense.qwen_8b.intent.metadata_qwen3_embedding_8b`; request=attribute_search; profile=feature_search; routing=feature_articulation,lyric_search
  User: Yes, "The Preacher" is amazing! That raw, deep male vocal and the powerful storytelling are exactly what I wanted. This whole vibe is just perfect. What other artists or tracks do you have that dive deep into intense, bluesy narratives with strong, gritty voc…
  Read: union_51_100_branch_rank_gap
- `b4ffa800-8173-4f16-800a-4b5e765d7f80::t8` GT=Cheated Hearts by Yeah Yeah Yeahs; final=None; old=None; union=None via `None`; request=exact_album; profile=exact_probe; routing=exact_entity_probe
  User: Okay, so the album IS Abbey Road, that's what I was looking for! But I still haven't heard a song from it. Can you please play just *any* song from The Beatles' Abbey Road album?
  Read: union_absent_top1000_source_gap
- `711a7a42-927e-4e45-821c-908b29ffe3a9::t8` GT=All These Things That I've Done by The Killers; final=None; old=None; union=None via `None`; request=attribute_search; profile=feature_search; routing=feature_articulation
  User: Okay, this is "Me Leva" by Latino! Finally, some Brazilian pop, that's great! But it's not the 'Toma' song you mentioned, and Latino is more classic Brazilian pop, not current. Can you really try to play 'Toma' by Simone Mendes, Guilherme & Benuto this time? …
  Read: union_absent_top1000_source_gap

## Recommendation

Do not keep broad satisfied-anchor expansion as a standalone production win. On 100 sessions it weakens union@20 and final@20, even though it slightly improves deeper union.

Next measured variant should be gated, not broader:

1. Keep exact resolved exclusions as hard drops only.
2. Gate satisfied-prior/album/anchor expansion to explicit continuation or positive-confirmation turns; do not let every satisfied prior become a broad top candidate source.
3. Add branch-local ranking for cases where GT is union@21-100: promote exact request facets, same-album/artist only when continuation, lyric/theme only when lyric evidence, and popularity only when explicit.
4. For source-absent cases, inspect whether the GT is actually inferable from the user turn. If inferable and no branch gets it in top1000, a new/source-improved retriever is needed for that class rather than more fusion.
5. Fix extractor JSON empty-result robustness: there were 2 no-branch rows in this smoke, both counted as misses.

## Files

- Audit JSON: `exp/smoke_satisfied_anchor_100sessions_20260608/scores/devset/v0plus_compiler_all_retrievers_devset_bad_turn_audit.json`
- Final-miss CSV: `exp/smoke_satisfied_anchor_100sessions_20260608/scores/devset/v0plus_compiler_all_retrievers_devset_bad_turns.csv`
- New scores: `exp/smoke_satisfied_anchor_100sessions_20260608/scores/devset/v0plus_compiler_all_retrievers_devset.json`
- New trace: `exp/smoke_satisfied_anchor_100sessions_20260608/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl`
