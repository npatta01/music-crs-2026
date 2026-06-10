# State V1 Retriever Matrix

Focused candidate-generation matrix over saved V1 extraction states.
The main gate is branch union@20/50; RRF/final ranking is reported separately.

## Summary

| Variant | n | final@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_trace_baseline` | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |  |  |
| `siglip_visual` | 6 |  |  | 0.000 | 0.000 | 0.000 |  |  |  |

## Per-Class Summary

| Pack | n | baseline u@20 | baseline u@50 | best single | single u@20 | single u@50 | combined | combined u@20 | combined u@50 |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|
| P0_new_artist_union20_gap_failure | 1 | 0.000 | 0.000 | `siglip_visual` | 0.000 | 0.000 | `` |  |  |
| P0_novelty_prior_anchor_failure | 2 | 0.000 | 0.000 | `siglip_visual` | 0.000 | 0.000 | `` |  |  |
| P0_roleless_stale_entity_failure | 2 | 0.000 | 0.000 | `siglip_visual` | 0.000 | 0.000 | `` |  |  |
| P1_positive_tag_retrieval_gap_failure | 1 | 0.000 | 0.000 | `siglip_visual` | 0.000 | 0.000 | `` |  |  |

## Examples

### `siglip_visual` Rescued union@20


### `siglip_visual` Still Missed union@20

- `41367174-552b-4117-9caa-d0ba1b307d37::t2` (P0_roleless_stale_entity_failure): GT=Mercy by Muse; best_branch=`bm25` rank=737; why=deep_candidate_ranking_gap; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` (P0_roleless_stale_entity_failure): GT=The Carbon Stampede by Cattle Decapitation; best_branch=`dense.siglip2_text.visual.image_siglip2` rank=148; why=deep_candidate_ranking_gap; change=Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- `88beb200-0334-4aba-be15-8e1303725766::t6` (P0_novelty_prior_anchor_failure): GT=Used To by Lil Wayne, Drake; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` (P0_novelty_prior_anchor_failure): GT=God Hates a Coward by Tomahawk; best_branch=`bm25` rank=828; why=deep_candidate_ranking_gap; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` (P0_new_artist_union20_gap_failure): GT=Hong Kong 2046 by Hong Kong Express; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `ad5348a7-d3bc-4882-bfca-54aa655eac96::t5` (P1_positive_tag_retrieval_gap_failure): GT=Glitter by Tyler, The Creator; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Improve turn-type routing and candidate generation: use listener_goal/current state, role-aware entities, tags, popularity, culture/CF affinity, and novelty profiles before spending effort only on final reranking.


## Per-Sample Rows

| Sample | Pack | GT | Variant | final rank | best branch rank | best branch | union@20 | union@50 | union@100 |
|---|---|---|---|---:|---:|---|---:|---:|---:|
| `41367174-552b-4117-9caa-d0ba1b307d37::t2` | `P0_roleless_stale_entity_failure` | Mercy / Muse | `siglip_visual` |  | 737 | `bm25` | 0 | 0 | 0 |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | `P0_roleless_stale_entity_failure` | The Carbon Stampede / Cattle Decapitation | `siglip_visual` | 161 | 148 | `dense.siglip2_text.visual.image_siglip2` | 0 | 0 | 0 |
| `88beb200-0334-4aba-be15-8e1303725766::t6` | `P0_novelty_prior_anchor_failure` | Used To / Lil Wayne, Drake | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3` | `P0_novelty_prior_anchor_failure` | God Hates a Coward / Tomahawk | `siglip_visual` |  | 828 | `bm25` | 0 | 0 | 0 |
| `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6` | `P0_new_artist_union20_gap_failure` | Hong Kong 2046 / Hong Kong Express | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
| `ad5348a7-d3bc-4882-bfca-54aa655eac96::t5` | `P1_positive_tag_retrieval_gap_failure` | Glitter / Tyler, The Creator | `siglip_visual` |  |  | `` | 0 | 0 | 0 |
