# DeepSeek Direct v1.2 Elements Probe

Extractor-only test. DeepSeek was prompted directly for `conversation_elements_v1_2` on 20 balanced focused70 examples. No retrieval run.

## Overall
- schema_valid: `1.000` (0 failures)
- request_type_captured: `0.389` (11 failures)
- required_elements_captured: `0.611` (7 failures)
- required_relations_correct: `0.444` (10 failures)
- required_subtypes_compatible: `0.556` (8 failures)
- reference_elements_captured: `0.778` (4 failures)
- reference_relations_correct: `0.778` (4 failures)
- reference_kind_present: `0.778` (4 failures)
- exclusions_captured: `0.944` (1 failures)
- exclusion_subtypes_compatible: `0.889` (2 failures)
- temporal_captured: `0.944` (1 failures)
- exactness_constraint_captured: `1.000` (0 failures)
- novelty_constraint_captured: `0.722` (5 failures)
- ambiguity_captured: `0.667` (6 failures)
- all_pass: `0.111` (16 failures)

## By Pack
| Pack | N | All | Request | ReqElems | ReqRel | RefElems | RefKind | Excl | ExclSubtype | Temporal | Exactness | Novelty | Ambiguity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_new_artist_union20_gap_failure | 3 | 0.000 | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.667 |
| P0_novelty_prior_anchor_failure | 2 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.500 | 1.000 |
| P0_roleless_stale_entity_failure | 3 | 0.000 | 0.000 | 0.333 | 0.333 | 0.667 | 0.667 | 1.000 | 1.000 | 1.000 | 1.000 | 0.333 | 0.000 |
| P1_rejection_guardrail_failure | 2 | 0.000 | 0.500 | 1.000 | 1.000 | 0.500 | 0.500 | 0.500 | 0.000 | 1.000 | 1.000 | 1.000 | 0.500 |
| P1_temporal_constraint_failure | 2 | 0.000 | 0.000 | 0.500 | 0.500 | 1.000 | 1.000 | 1.000 | 1.000 | 0.500 | 1.000 | 0.500 | 0.500 |
| POS_clean_final_hit_control | 3 | 0.000 | 0.667 | 1.000 | 0.333 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.667 | 1.000 |
| POS_exact_entity_success_control | 3 | 0.667 | 1.000 | 1.000 | 0.667 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Notes
- All-pass is intentionally strict and includes constraints/ambiguity, not just element extraction.
- This test is label-driven from v1.2 focused70 and does not use GT target facts in the prompt.
- The one preliminary smoke call is not included in these 20 scored rows.
