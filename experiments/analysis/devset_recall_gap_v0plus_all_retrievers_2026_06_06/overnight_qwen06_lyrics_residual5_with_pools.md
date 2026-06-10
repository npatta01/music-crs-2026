# State V1 Retriever Matrix

Focused candidate-generation matrix over saved V1 extraction states.
The main gate is branch union@20/50; RRF/final ranking is reported separately.

## Summary

| Variant | n | final@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_trace_baseline` | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |  |  |
| `qwen06_lyrics` | 5 |  |  | 0.000 | 0.000 | 0.000 |  |  |  |

## Per-Class Summary

| Pack | n | baseline u@20 | baseline u@50 | best single | single u@20 | single u@50 | combined | combined u@20 | combined u@50 |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|
| P0_new_artist_union20_gap_failure | 1 | 0.000 | 0.000 | `qwen06_lyrics` | 0.000 | 0.000 | `` |  |  |
| P0_roleless_stale_entity_failure | 1 | 0.000 | 0.000 | `qwen06_lyrics` | 0.000 | 0.000 | `` |  |  |
| P1_temporal_constraint_failure | 3 | 0.000 | 0.000 | `qwen06_lyrics` | 0.000 | 0.000 | `` |  |  |

## Examples

### `qwen06_lyrics` Rescued union@20


### `qwen06_lyrics` Still Missed union@20

- `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` (P0_roleless_stale_entity_failure): GT=I Believe in a Thing Called Love by The Darkness; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `907921a3-d08f-4ba1-8cce-0e760a9e7044::t7` (P0_new_artist_union20_gap_failure): GT=Sunrise - Slow Hands Remix by Kasper Bjørke; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- `67b9ba8a-382f-4b70-af76-576848d8cf67::t8` (P1_temporal_constraint_failure): GT=Gangsta Gangsta by N.W.A.; best_branch=`bm25` rank=306; why=deep_candidate_ranking_gap; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- `9468e467-d396-461b-be29-b30b6cf87c35::t5` (P1_temporal_constraint_failure): GT=Midnight by A Tribe Called Quest; best_branch=`bm25` rank=742; why=deep_candidate_ranking_gap; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- `e978bb5b-26af-4c7d-b720-b9210bdddf25::t8` (P1_temporal_constraint_failure): GT=Dear Yvette by Jane Doe, Masta Ace; best_branch=`` rank=; why=existing_retrievers_do_not_surface_gt; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.


## Per-Sample Rows

| Sample | Pack | GT | Variant | final rank | best branch rank | best branch | union@20 | union@50 | union@100 |
|---|---|---|---|---:|---:|---|---:|---:|---:|
| `88af7ec3-c368-421b-9512-d0180da3d1f6::t2` | `P0_roleless_stale_entity_failure` | I Believe in a Thing Called Love / The Darkness | `qwen06_lyrics` |  |  | `` | 0 | 0 | 0 |
| `907921a3-d08f-4ba1-8cce-0e760a9e7044::t7` | `P0_new_artist_union20_gap_failure` | Sunrise - Slow Hands Remix / Kasper Bjørke | `qwen06_lyrics` |  |  | `` | 0 | 0 | 0 |
| `67b9ba8a-382f-4b70-af76-576848d8cf67::t8` | `P1_temporal_constraint_failure` | Gangsta Gangsta / N.W.A. | `qwen06_lyrics` |  | 306 | `bm25` | 0 | 0 | 0 |
| `9468e467-d396-461b-be29-b30b6cf87c35::t5` | `P1_temporal_constraint_failure` | Midnight / A Tribe Called Quest | `qwen06_lyrics` |  | 742 | `bm25` | 0 | 0 | 0 |
| `e978bb5b-26af-4c7d-b720-b9210bdddf25::t8` | `P1_temporal_constraint_failure` | Dear Yvette / Jane Doe, Masta Ace | `qwen06_lyrics` |  |  | `` | 0 | 0 | 0 |
