# State V1 Retriever Matrix

Focused candidate-generation matrix over saved V1 extraction states.
The main gate is branch union@20/50; RRF/final ranking is reported separately.

## Summary

| Variant | n | final@20 | NDCG@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_trace_baseline` | 3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |  |  |
| `current_config_state_selector` | 3 | 0.000 | 0.000 | 0.000 | 0.333 | 0.333 | 0.667 | 1.000 | 1.000 | 0.333 |

## Guardrails

| Variant | n | GT release-date masked | GT hard-dropped |
|---|---:|---:|---:|
| `current_config_state_selector` | 3 | 0 | 0 |

## Per-Class Summary

| Pack | n | baseline u@20 | baseline u@50 | best single | single u@20 | single u@50 | combined | combined u@20 | combined u@50 |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|
| P0_roleless_stale_entity_failure | 3 | 0.000 | 0.000 | `` |  |  | `current_config_state_selector` | 0.333 | 0.333 |

## Examples

### `current_config_state_selector` Rescued union@20

- `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` (P0_roleless_stale_entity_failure): GT=Armature by Emptyset; best_branch=`dense.clap_text.sonic.audio_laion_clap` rank=12; why=rescued_at_union20

### `current_config_state_selector` Still Missed union@20

- `0b9d547f-e748-464a-90e2-2199149f915c::t6` (P0_roleless_stale_entity_failure): GT=Give It To Me Baby by Rick James; best_branch=`dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` rank=67; why=branch_local_ranking_gap_51_100; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- `e66c6a88-88ba-4117-9114-363bfa96294a::t7` (P0_roleless_stale_entity_failure): GT=Test Drive by John Powell; best_branch=`dense.clap_text.sonic_nl.audio_laion_clap` rank=180; why=deep_candidate_ranking_gap; change=Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.


## Per-Sample Rows

| Sample | Pack | GT | Variant | final rank | NDCG@20 | best branch rank | best branch | union@20 | union@50 | union@100 | GT release masked | GT hard-dropped |
|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| `0b9d547f-e748-464a-90e2-2199149f915c::t6` | `P0_roleless_stale_entity_failure` | Give It To Me Baby / Rick James | `current_config_state_selector` | 201 | 0.000 | 67 | `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 0 | 0 | 1 | 0 | 0 |
| `e66c6a88-88ba-4117-9114-363bfa96294a::t7` | `P0_roleless_stale_entity_failure` | Test Drive / John Powell | `current_config_state_selector` | 554 | 0.000 | 180 | `dense.clap_text.sonic_nl.audio_laion_clap` | 0 | 0 | 0 | 0 | 0 |
| `0858f444-c9af-4f08-a9fc-2a731a24182b::t5` | `P0_roleless_stale_entity_failure` | Armature / Emptyset | `current_config_state_selector` | 63 | 0.000 | 12 | `dense.clap_text.sonic.audio_laion_clap` | 1 | 1 | 1 | 0 | 0 |
