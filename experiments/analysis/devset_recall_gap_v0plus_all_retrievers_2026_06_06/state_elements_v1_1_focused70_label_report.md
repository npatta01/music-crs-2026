# Conversation Elements v1.1 Focused70 Relabel

Relabels the focused70 replay set with `relation`, `reference_kind`, and first-class ambiguity records.

## Summary
- samples: `70`
- packs: `{"POS_exact_entity_success_control": 10, "P0_roleless_stale_entity_failure": 10, "P1_rejection_guardrail_failure": 10, "POS_clean_final_hit_control": 10, "P0_new_artist_union20_gap_failure": 10, "P1_temporal_constraint_failure": 10, "P0_novelty_prior_anchor_failure": 10}`
- request_types: `{"exact_entity": 20, "attribute_search": 34, "new_discovery": 13, "refinement": 3}`
- relations: `{"target": 33, "desired": 168, "reference": 51, "exclude": 30}`
- reference_kinds: `{"liked_prior": 27, "satisfied_prior": 23, "explicit_similarity": 1}`
- constraint_types: `{"exactness": 13, "artist_reuse": 50, "novelty": 50, "temporal": 18}`
- ambiguity_types: `{"reference_use": 31, "artist_reuse": 2}`
- samples_with_ambiguity: `31`
- schema_gap_types: `{"liked_prior_plus_pivot_policy_boundary": 5, "reference_kind_requires_human_review": 16, "temporal_style_vs_reference_needs_compiler_rule": 18, "exclusion_entity_type_unresolved": 5}`
- schema_gap_count: `44`

## Schema Gaps
- `liked_prior_plus_pivot_policy_boundary`: 5
- `reference_kind_requires_human_review`: 16
- `temporal_style_vs_reference_needs_compiler_rule`: 18
- `exclusion_entity_type_unresolved`: 5

## Interpretation
- The schema now resolves the previous biggest gap: not all references are the same.
- Remaining gaps are mostly compiler-boundary issues, not extractor-shape issues.
- The highest-risk ambiguity is liked prior + pivot: the extractor can label it, but compiler must decide anchor strength and same-artist behavior.
