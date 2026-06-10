# State V1 Retriever Matrix

Focused candidate-generation matrix over saved V1 extraction states.
The main gate is branch union@20/50; RRF/final ranking is reported separately.

## Summary

| Variant | n | final@20 | NDCG@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_trace_baseline` | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |  |  |
| `current_config_state_selector_family` | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 |

## Guardrails

| Variant | n | GT release-date masked | GT hard-dropped |
|---|---:|---:|---:|
| `current_config_state_selector_family` | 1 | 0 | 0 |

## Per-Class Summary

| Pack | n | baseline u@20 | baseline u@50 | best single | single u@20 | single u@50 | combined | combined u@20 | combined u@50 |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|
| P0_roleless_stale_entity_failure | 1 | 0.000 | 0.000 | `` |  |  | `current_config_state_selector_family` | 0.000 | 0.000 |

## Examples

### `current_config_state_selector_family` Rescued union@20


### `current_config_state_selector_family` Still Missed union@20

- `0b9d547f-e748-464a-90e2-2199149f915c::t6` (P0_roleless_stale_entity_failure): GT=Give It To Me Baby by Rick James; best_branch=`dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` rank=68; why=branch_local_ranking_gap_51_100; change=Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.


## Per-Sample Rows

| Sample | Pack | GT | Variant | final rank | NDCG@20 | best branch rank | best branch | union@20 | union@50 | union@100 | GT release masked | GT hard-dropped |
|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| `0b9d547f-e748-464a-90e2-2199149f915c::t6` | `P0_roleless_stale_entity_failure` | Give It To Me Baby / Rick James | `current_config_state_selector_family` | 221 | 0.000 | 68 | `dense.qwen_8b.attributes.attributes_qwen3_embedding_8b` | 0 | 0 | 1 | 0 | 0 |
