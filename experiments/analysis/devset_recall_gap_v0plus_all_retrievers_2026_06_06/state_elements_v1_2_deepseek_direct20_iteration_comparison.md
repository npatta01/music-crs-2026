# DeepSeek v1.2 Direct20 Prompt Iteration Comparison

Same 20 focused70 examples. No retrieval run. `compiler_core_pass` ignores request_type and novelty constraint, but still requires schema, required elements, required relations, reference capture, exclusions, temporal, and ambiguity.

| Run | Errors | All Pass | Compiler Core | Request | ReqElems | ReqRel | RefElems | RefRel | Excl | ExclSubtype | Temporal | Novelty | Ambiguity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v1_original_prompt | 2 | 0.100 | 0.200 | 0.350 | 0.550 | 0.400 | 0.700 | 0.700 | 0.850 | 0.800 | 0.850 | 0.650 | 0.600 |
| v2_current_turn_atomic | 0 | 0.150 | 0.350 | 0.750 | 0.600 | 0.550 | 0.450 | 0.450 | 0.950 | 0.850 | 0.800 | 0.400 | 0.900 |
| v3_reference_preserving | 0 | 0.150 | 0.250 | 0.250 | 0.600 | 0.600 | 0.550 | 0.550 | 0.950 | 0.900 | 0.750 | 0.900 | 1.000 |

## Read
- v2 is the best balanced prompt: no JSON errors, much better request type, and modest all-pass improvement.
- v3 proves reference-preservation instructions can improve novelty/ambiguity/relations, but they hurt request typing and temporal/reference coverage.
- The remaining bottleneck is not JSON/schema; it is consistent required-facet extraction and target/reference relation quality.
