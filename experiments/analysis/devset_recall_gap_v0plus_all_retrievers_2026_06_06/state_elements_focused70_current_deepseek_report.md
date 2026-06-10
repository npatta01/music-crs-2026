# Conversation Elements Focused70 Score

Scores current DeepSeek old-schema state against the simplified `conversation_elements_v1` labels. This is a diagnostic baseline, not a final test of a new prompt.

## Overall
- request_type_captured: `0.771` (16 failures)
- required_elements_captured: `0.529` (33 failures)
- required_element_roles_correct: `0.514` (34 failures)
- reference_facts_captured: `0.757` (17 failures)
- reference_roles_correct: `0.729` (19 failures)
- exclusions_captured: `0.871` (9 failures)
- temporal_captured: `0.914` (6 failures)
- ambiguity_captured: `0.986` (1 failures)
- all_pass: `0.386` (43 failures)

## By Pack
| Pack | All | Request | Required Elements | Required Roles | Reference Facts | Reference Roles | Exclusions | Temporal | Ambiguity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_new_artist_union20_gap_failure | 0.300 | 0.700 | 0.400 | 0.400 | 0.500 | 0.500 | 1.000 | 0.900 | 0.900 |
| P0_novelty_prior_anchor_failure | 0.600 | 0.700 | 0.700 | 0.700 | 0.600 | 0.600 | 1.000 | 1.000 | 1.000 |
| P0_roleless_stale_entity_failure | 0.200 | 0.600 | 0.500 | 0.400 | 0.400 | 0.400 | 0.900 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 0.000 | 0.700 | 0.500 | 0.500 | 0.800 | 0.700 | 0.300 | 1.000 | 1.000 |
| P1_temporal_constraint_failure | 0.100 | 0.700 | 0.100 | 0.100 | 1.000 | 0.900 | 0.900 | 0.500 | 1.000 |
| POS_clean_final_hit_control | 0.600 | 1.000 | 0.600 | 0.600 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| POS_exact_entity_success_control | 0.900 | 1.000 | 0.900 | 0.900 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Main Read
- Required element coverage is a fact-recall test: did the model mention the needed entities/facets at all?
- Reference role is the key new-schema test: prior positives should be preserved as references, not active targets.
- Current old-schema output is expected to underperform on reference roles and ambiguity because those fields were not requested.
