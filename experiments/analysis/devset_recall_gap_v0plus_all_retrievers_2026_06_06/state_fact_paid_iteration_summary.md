# State Fact Paid Iteration Summary

Extractor-only paid validation on the 56 hand-labeled fact examples using `openrouter/deepseek/deepseek-v4-flash` and full TalkPlay session history. No retrieval run was performed.

## Decision

Keep the deterministic schema compatibility merge. Do not keep the literal/carry-forward prompt edits from this iteration: they improved entity recall but regressed request type, rejection, and temporal checks on the full 56 run.

## Metrics

| Run | N | All pass | Compiler core | Request type | Required entities | Exclusions | Temporal | Note |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| paid_current_full_original | 56 | 0.625 | 0.750 | 0.839 | 0.768 | 0.946 | 0.982 | Fresh paid current prompt, before re-deriving observations through schema merge. |
| paid_current_full_schema_merge | 56 | 0.661 | 0.786 | 0.839 | 0.804 | 0.946 | 0.982 | Same paid states, re-scored after fact-to-entity compatibility merge. Best validated path. |
| paid_rubric_corefail | 14 | 0.214 | 0.286 | 0.714 | 0.429 | 0.786 | 0.929 | Rubric prompt on original 14 core failures only; recovered a few but not enough. |
| paid_rejection_corefail | 14 | 0.000 | 0.000 | 0.786 | 0.071 | 0.786 | 0.929 | Rejection prompt on original 14 core failures only; worse entity coverage. |
| paid_current_literal_corefail | 12 | 0.083 | 0.083 | 0.750 | 0.250 | 0.750 | 0.917 | Literal phrase prompt on remaining 12 core failures; only fixed hit case. |
| paid_current_carry_corefail | 12 | 0.417 | 0.417 | 0.833 | 0.583 | 0.750 | 0.917 | Carry-forward prompt on remaining 12 core failures; fixed 5/12 targeted cases. |
| paid_current_carry_full_rejected | 56 | 0.643 | 0.768 | 0.804 | 0.821 | 0.929 | 0.964 | Full 56 validation of carry-forward prompt; net worse than schema merge, rejected. |

## What Improved

- Schema merge recovered fact-first items that the LLM had captured in `facts` but omitted from legacy `entities`, including `Baker Street` as contrast and the Ice Cube lyric phrase as a retrieval tag/lyrical cue.
- Best validated score moved from all-pass `0.625` / compiler-core `0.750` to all-pass `0.661` / compiler-core `0.786` without another paid extraction call.
- Required entity coverage moved from `0.768` to `0.804` under the kept change.

## What Did Not Validate

- The prompt literal/carry-forward edits fixed several targeted omissions, but the full run regressed other checks and landed at all-pass `0.643` / compiler-core `0.768`, below the schema-merge path.
- The `rejection` prompt variant should not be used; it scored `0.000` compiler-core on the original 14 hard failures because entity coverage collapsed.
- The `rubric` variant is not worth adopting wholesale; it helped a few exact/phrase cases but did not solve the remaining extraction issue generally.

## Remaining State Extraction Gaps

- Literal current-turn attributes still get paraphrased or dropped in some cases (`artistically unique`, `watching a movie`, `boost my energy`).
- Some labels expect hard style exclusions for negative style feedback; the extractor often emits soft style exclusions, which is safer for the compiler but mismatches the current label contract.
- Some request-type mismatches are request-label noise rather than compiler-critical failures; use `compiler_core_pass` as the main extractor readiness metric.

## Artifacts

- Best kept scores: `state_fact_v1_paid_current_full_stateonly_fact_scores.json`
- Best kept report: `state_fact_v1_paid_current_full_stateonly_fact_report.md`
- Final rejected prompt run: `state_fact_v1_paid_current_carry_full_fact_scores.json`
- This summary: `state_fact_paid_iteration_summary.md`
