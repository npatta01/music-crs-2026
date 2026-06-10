# DeepSeek Direct v1.2 Elements Probe - v2 Prompt

Second extractor-only prompt iteration on the same 20 examples. Malformed JSON counts as failed. No retrieval run.

## Overall
- schema_valid: `1.000` (0 failures)
- request_type_captured: `0.750` (5 failures)
- required_elements_captured: `0.600` (8 failures)
- required_relations_correct: `0.550` (9 failures)
- required_subtypes_compatible: `0.600` (8 failures)
- reference_elements_captured: `0.450` (11 failures)
- reference_relations_correct: `0.450` (11 failures)
- reference_kind_present: `0.450` (11 failures)
- exclusions_captured: `0.950` (1 failures)
- exclusion_subtypes_compatible: `0.850` (3 failures)
- temporal_captured: `0.800` (4 failures)
- exactness_constraint_captured: `0.950` (1 failures)
- novelty_constraint_captured: `0.400` (12 failures)
- ambiguity_captured: `0.900` (2 failures)
- all_pass: `0.150` (17 failures)

- attempted calls: `20`
- errors: `0`

## By Pack
| Pack | N | All | Schema | Request | ReqElems | ReqRel | RefElems | RefKind | Excl | ExclSubtype | Temporal | Exactness | Novelty | Ambiguity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_new_artist_union20_gap_failure | 3 | 0.000 | 1.000 | 0.667 | 0.333 | 0.333 | 0.000 | 0.000 | 1.000 | 1.000 | 0.667 | 1.000 | 0.333 | 0.667 |
| P0_novelty_prior_anchor_failure | 2 | 0.000 | 1.000 | 0.500 | 0.500 | 0.500 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.500 | 1.000 |
| P0_roleless_stale_entity_failure | 3 | 0.000 | 1.000 | 1.000 | 0.667 | 0.667 | 0.333 | 0.333 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 |
| P1_rejection_guardrail_failure | 3 | 0.000 | 1.000 | 0.667 | 0.333 | 0.333 | 0.000 | 0.000 | 0.667 | 0.000 | 1.000 | 1.000 | 0.000 | 0.667 |
| P1_temporal_constraint_failure | 3 | 0.000 | 1.000 | 0.667 | 0.333 | 0.333 | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 | 0.333 | 1.000 |
| POS_clean_final_hit_control | 3 | 0.333 | 1.000 | 0.667 | 1.000 | 0.667 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.667 | 1.000 |
| POS_exact_entity_success_control | 3 | 0.667 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.667 | 1.000 | 1.000 |
