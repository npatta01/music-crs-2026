# DeepSeek Direct v1.2 Elements Probe - Strict Score

Malformed JSON responses are counted as failed rows. No retrieval run.

## Overall
- schema_valid: `0.900` (2 failures)
- request_type_captured: `0.350` (13 failures)
- required_elements_captured: `0.550` (9 failures)
- required_relations_correct: `0.400` (12 failures)
- required_subtypes_compatible: `0.500` (10 failures)
- reference_elements_captured: `0.700` (6 failures)
- reference_relations_correct: `0.700` (6 failures)
- reference_kind_present: `0.700` (6 failures)
- exclusions_captured: `0.850` (3 failures)
- exclusion_subtypes_compatible: `0.800` (4 failures)
- temporal_captured: `0.850` (3 failures)
- exactness_constraint_captured: `0.900` (2 failures)
- novelty_constraint_captured: `0.650` (7 failures)
- ambiguity_captured: `0.600` (8 failures)
- all_pass: `0.100` (18 failures)

- attempted calls: `20`
- errors: `2`

## By Pack
| Pack | N | All | Schema | Request | ReqElems | ReqRel | RefElems | RefKind | Excl | ExclSubtype | Temporal | Exactness | Novelty | Ambiguity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_new_artist_union20_gap_failure | 3 | 0.000 | 1.000 | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.667 |
| P0_novelty_prior_anchor_failure | 2 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.500 | 1.000 |
| P0_roleless_stale_entity_failure | 3 | 0.000 | 1.000 | 0.000 | 0.333 | 0.333 | 0.667 | 0.667 | 1.000 | 1.000 | 1.000 | 1.000 | 0.333 | 0.000 |
| P1_rejection_guardrail_failure | 3 | 0.000 | 0.667 | 0.333 | 0.667 | 0.667 | 0.333 | 0.333 | 0.333 | 0.000 | 0.667 | 0.667 | 0.667 | 0.333 |
| P1_temporal_constraint_failure | 3 | 0.000 | 0.667 | 0.000 | 0.333 | 0.333 | 0.667 | 0.667 | 0.667 | 0.667 | 0.333 | 0.667 | 0.333 | 0.333 |
| POS_clean_final_hit_control | 3 | 0.000 | 1.000 | 0.667 | 1.000 | 0.333 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.667 | 1.000 |
| POS_exact_entity_success_control | 3 | 0.667 | 1.000 | 1.000 | 1.000 | 0.667 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Error Rows
- `1e14a07f-7369-4d24-9285-9343b6b18353::t8` (P1_rejection_guardrail_failure): JSONDecodeError: Expecting value: line 301 column 27 (char 12367)
- `9468e467-d396-461b-be29-b30b6cf87c35::t5` (P1_temporal_constraint_failure): JSONDecodeError: Unterminated string starting at: line 359 column 24 (char 11920)
