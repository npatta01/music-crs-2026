# State V1 Retriever Matrix

Focused candidate-generation matrix over saved V1 extraction states.
The main gate is branch union@20/50; RRF/final ranking is reported separately.

## Summary

| Variant | n | final@20 | NDCG@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_trace_baseline` | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |  |  |
| `current_config_state_survivor` | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 |

## Guardrails

| Variant | n | GT release-date masked | GT hard-dropped |
|---|---:|---:|---:|
| `current_config_state_survivor` | 1 | 0 | 0 |

## Per-Class Summary

| Pack | n | baseline u@20 | baseline u@50 | best single | single u@20 | single u@50 | combined | combined u@20 | combined u@50 |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|
| P1_temporal_constraint_failure | 1 | 0.000 | 0.000 | `` |  |  | `current_config_state_survivor` | 0.000 | 0.000 |

## Examples

### `current_config_state_survivor` Rescued union@20


### `current_config_state_survivor` Still Missed union@20

- `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6` (P1_temporal_constraint_failure): GT=Thriller by Fall Out Boy; best_branch=`bm25` rank=479; why=deep_candidate_ranking_gap; change=Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.


## Per-Sample Rows

| Sample | Pack | GT | Variant | final rank | NDCG@20 | best branch rank | best branch | union@20 | union@50 | union@100 | GT release masked | GT hard-dropped |
|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6` | `P1_temporal_constraint_failure` | Thriller / Fall Out Boy | `current_config_state_survivor` |  | 0.000 | 479 | `bm25` | 0 | 0 | 0 | 0 | 0 |
