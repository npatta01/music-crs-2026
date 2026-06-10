# Conversation Elements v1.2 Focused70 Relabel

Adds `resolution_status` and `candidate_subtypes` to stress-test whether unresolved exclusions need a schema change.

## Summary
- samples: `70`
- relations: `{"target": 33, "desired": 168, "reference": 51, "exclude": 30}`
- element_kinds: `{"entity": 104, "facet": 178}`
- reference_kinds: `{"liked_prior": 27, "satisfied_prior": 23, "explicit_similarity": 1}`
- resolution_status: `{"resolved": 274, "ambiguous": 8}`
- exclude_resolution_status: `{"resolved": 22, "ambiguous": 8}`
- exclude_candidate_subtypes: `{"artist": 20, "energy": 4, "mood": 7, "style": 2, "genre": 1, "soundscape": 1, "theme": 2, "texture": 1, "vocal_style": 1, "lyrics": 1}`
- constraint_types: `{"exactness": 13, "artist_reuse": 50, "novelty": 50, "temporal": 18}`
- ambiguity_types: `{"reference_use": 31, "artist_reuse": 2}`
- samples_with_ambiguity: `31`
- schema_gap_types: `{"liked_prior_plus_pivot_policy_boundary": 14, "reference_kind_requires_human_review": 17, "temporal_style_vs_reference_needs_compiler_rule": 18, "exclusion_candidate_subtype_ambiguous": 5}`
- schema_gap_count: `54`

## Read
- The previous `exclusion_entity_type_unresolved` gap is removed: unknown exclusions are now represented as facet exclusions with candidate subtype mappings.
- The remaining exclusion issue is not schema shape; it is compiler mapping for ambiguous facets like heavy, intense, rain, combat, harsh, and spoken word.
- Reference and temporal gaps remain because they require either human label review or compiler policy, not more extractor fields.
