# Conversation Elements v1.2 Current DeepSeek Score

Diagnostic score: current old-schema DeepSeek output against v1.2 labels. The model was not prompted to emit v1.2, so this is baseline evidence only.

## Overall
- request_type_captured: `0.771` (16 failures)
- required_elements_captured: `0.529` (33 failures)
- required_relations_correct: `0.514` (34 failures)
- required_subtypes_compatible: `0.529` (33 failures)
- reference_elements_captured: `0.814` (13 failures)
- reference_relations_correct: `0.771` (16 failures)
- exclusions_captured: `0.857` (10 failures)
- exclusion_subtypes_compatible: `0.886` (8 failures)
- temporal_captured: `0.914` (6 failures)
- all_pass: `0.343` (46 failures)

## By Pack
| Pack | All | Req | ReqElems | ReqRel | RefElems | RefRel | Excl | ExclSubtype | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_new_artist_union20_gap_failure | 0.200 | 0.700 | 0.400 | 0.400 | 0.600 | 0.500 | 1.000 | 1.000 | 0.900 |
| P0_novelty_prior_anchor_failure | 0.500 | 0.700 | 0.700 | 0.700 | 0.800 | 0.800 | 1.000 | 1.000 | 1.000 |
| P0_roleless_stale_entity_failure | 0.100 | 0.600 | 0.500 | 0.400 | 0.500 | 0.500 | 0.900 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 0.000 | 0.700 | 0.500 | 0.500 | 0.800 | 0.700 | 0.200 | 0.300 | 1.000 |
| P1_temporal_constraint_failure | 0.100 | 0.700 | 0.100 | 0.100 | 1.000 | 0.900 | 0.900 | 0.900 | 0.500 |
| POS_clean_final_hit_control | 0.600 | 1.000 | 0.600 | 0.600 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| POS_exact_entity_success_control | 0.900 | 1.000 | 0.900 | 0.900 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
