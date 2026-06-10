# State Replay Extraction Report

- State source: `ideal`
- Model: `n/a`
- Samples: `70`
- Overall all-pass rate: `1.000`
- New state captures expected information: `70/70`
- Improved vs previous trace state: `70/70`
- Regressed vs previous trace state: `0/70`

## Pack Results

| Pack | N | All Pass | Request Type | Role | Artist Mode | Profile | Temporal | Rejection | Positive Control |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_new_artist_union20_gap_failure | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_novelty_prior_anchor_failure | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_roleless_stale_entity_failure | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P1_temporal_constraint_failure | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| POS_clean_final_hit_control | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| POS_exact_entity_success_control | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## State Change Evaluation

Each row compares the previous trace state snapshot against the new extracted state and the desired state contract for the replay example.

## Failures

No failing checks.
