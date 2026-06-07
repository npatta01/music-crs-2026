# State V1 Goal Iteration Summary

Date: 2026-06-07

## Questions Answered

### Am I happy with the extraction state?

Mostly yes for the schema and compiler bridge, but not as a fully solved extractor.

The old all-110 replay all-pass metric is not a valid V1 acceptance gate because it still penalizes `target_artist_mode` and `retrieval_profile`, which V1 intentionally treats as derived compiler compatibility fields rather than LLM-owned facts.

Using V1-relevant checks on the fresh all-110 paid run:

- V1 state-core pass: `90/110 = 81.8%`
- Request type: `110/110 = 100.0%`
- Role correctness: `101/110 = 91.8%`
- Temporal semantics: `108/110 = 98.2%`
- Rejection normalization: `109/110 = 99.1%`
- No schema/API extraction errors in the final audit.

On the 56 hand-labeled V1 role/projection subset after reprojecting through the current bridge:

- Role-label pass: `52/56 = 92.9%`
- Projection-label pass: `53/56 = 94.6%`
- Fact-label compiler-core pass: `46/56 = 82.1%`

### Did extraction improve for the 100+ replay sessions?

Not under the old all-pass metric. The fresh current-V1 all-110 run scores `29.1%` old all-pass because `76/110` failures are `target_artist_mode` / `retrieval_profile` disagreements.

Under the V1 state-core metric, the extractor is materially better: `90/110 = 81.8%`. The remaining true extraction/projection misses are mostly:

- Named-artist role errors in a small set of ranker-near-miss examples.
- Fine-grained label/string mismatches like `popular` vs `well-known/widely loved`.
- A few positive-control checks that are old-contract artifacts rather than V1 compiler failures.

### Is the retriever using the new information?

Partially.

The bridge exposes exact seeds, query facets, hard rejections, temporal hints, and style references. Current retrieval consumes exact seeds/tags/rejections. Before this iteration, the reference configs did not enable the existing `enable_similar_artist_anchors` path, so `style_reference_entities` were available but mostly unused by centroid branches.

This iteration enables safe style-reference centroid consumption in both current configs:

- `configs/v0plus_compiler_all_retrievers_devset.yaml`
- `configs/v0plus_compiler_blindset_A.yaml`

Focused local retrieval smoke shows this helps candidate generation but does not solve top-20 ranking:

| Variant | final@20 | final@100 | union@100 | union@200 | union@1000 |
|---|---:|---:|---:|---:|---:|
| `centroid_no_style` | 0.167 | 0.167 | 0.167 | 0.333 | 0.500 |
| `centroid_style_safe` | 0.167 | 0.167 | 0.250 | 0.500 | 0.583 |
| `centroid_style_broad` | 0.167 | 0.167 | 0.250 | 0.583 | 0.667 |
| `centroid_style_broad_w3` | 0.167 | 0.250 | 0.250 | 0.583 | 0.667 |

Interpretation: V1 style-reference information is useful for candidate depth. The remaining gap is ranking/fusion and stronger text/centroid branch use, not just state extraction.

## Code Change From This Iteration

Fixed one real bridge bug found in the fresh all-110 run:

- Soft entity exclusions no longer become compiler hard rejections.
- Example: current exact target `The Spirit of Radio` by `Rush` should not be suppressed because a stale soft prior exclusion also mentions `Rush`.
- Soft attribute/style exclusions still project as tag demotions.

## Evidence Files

- Fresh paid all-110 current V1 audit: `state_v1_goal_current_all110_audit.jsonl`
- Fresh paid all-110 report: `state_v1_goal_current_all110_report.md`
- Reprojected all-110 audit after bridge patch: `state_v1_goal_current_all110_reprojected_audit.jsonl`
- Reprojected role labels: `state_v1_goal_current_all110_reprojected_role_report.md`
- Reprojected projection labels: `state_v1_goal_current_all110_reprojected_projection_report.md`
- Reprojected fact labels: `state_v1_goal_current_all110_reprojected_fact_report.md`
- Retrieval smoke: `state_v1_retrieval_smoke.md`

## Next Work

Do not spend more effort making the LLM predict old policy fields. The next useful iteration is:

1. Add a V1-native all-110 evaluator that reports state-core and projection-core metrics directly.
2. Improve or relax the remaining three projection-label mismatches after hand review.
3. Test fuller retriever consumption: style-reference-aware dense query templates and branch/ranker features, using union@20/100/200 and final@20 as separate gates.
