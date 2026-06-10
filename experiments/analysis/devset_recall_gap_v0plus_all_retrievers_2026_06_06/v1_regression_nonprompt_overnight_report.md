# V1 Retrieval Regression Non-Prompt Probe

Date: 2026-06-09

Scope: freeze the V1 state extractor prompt/schema and test non-prompt retrieval levers only. The goal was not to optimize leaderboard or full devset. The goal was to explain the current V1 served regression and identify meaningful overnight ideas.

## Bottom Line

The current gap is not primarily "LLM state cannot extract the request." For this goal, the primary metric is candidate recall: union@20 first, then union@50/100. `final@20` is only a diagnostic because this pass intentionally did not work on ranking or global fusion.

By the candidate-recall metric, none of the tested variants solved the gap:

1. Current V1 all-retrievers is slightly below the old path on union@20: 0.4250 vs 0.4400 on the same-100 smoke.
2. Pruning improves the existing fused output, but it reduces candidate recall: union@20 drops to 0.3875.
3. Hard-cleaning V1 attribute terms into exact catalog tags is too lossy. The raw attribute phrases are noisy, but they carry useful BM25 signal. Exact catalog whitelisting and dense-only attribute routing both reduce candidate recall.

The useful finding from branch pruning is diagnostic only: the served path has branch/fusion noise. It is not a recall improvement and should not be promoted as the candidate-recall fix.

So the next overnight bet should not be another state prompt iteration, and it should not use `final@20` as the pass/fail gate. It should be an additive candidate-recall experiment: protect baseline pools, add softer tag/scene normalization, use Qwen8B for attribute semantics, keep Qwen0.6B for lyrics only, and test branch-local hybrid retrieval rather than exact tag filtering.

## Same-100 Devset Smoke

All rows use the same 100-session devset subset.

| Variant | final@20 | union@20 | union@50 | union@100 | union@1000 | union size@20 | Read |
|---|---:|---:|---:|---:|---:|---:|---|
| Old all-retrievers subset | 0.2613 | 0.4400 | 0.5413 | 0.6238 | 0.8963 | 161.1 | Old path had smaller pool and better final than current V1. |
| Current V1 all-retrievers | 0.2400 | 0.4250 | 0.5438 | 0.6275 | 0.9050 | 224.6 | More candidates, worse final. This is a noise/fusion pressure sign. |
| Pruned branches | 0.2788 | 0.3875 | 0.5075 | 0.5900 | 0.8800 | 139.3 | Candidate recall regresses. Treat final@20 movement as diagnostic only. |
| Pruned + dense-only V1 attrs | 0.2613 | 0.3763 | 0.4988 | 0.5713 | 0.8700 | 138.9 | Reject for served path. BM25 signal collapsed. |
| Pruned + catalog-exact safe tags | 0.2688 | 0.3813 | 0.5013 | 0.5775 | 0.8750 | 139.7 | Safer than dense-only but still worse than prune-only. Too conservative. |

## Focused-110 State-Gap Pack

Focused-110 is intentionally biased toward difficult state/retrieval failures, so use it to compare variants, not to estimate full-devset score.

| Variant | final@20 | union@20 | union@50 | union@100 | union@1000 | Read |
|---|---:|---:|---:|---:|---:|---|
| Official trace baseline in focused pack | 0.1818 | 0.5455 | 0.5455 | 0.5455 | n/a | Baseline traces already had many GTs around the focused boundary. |
| Pruned branches | 0.3364 | 0.4818 | 0.5273 | 0.6455 | 0.9364 | Better fused top-20 on this pack, but not a union@20 win over the focused trace baseline. |
| Pruned + dense-only V1 attrs | 0.3545 | 0.4727 | 0.5182 | 0.6273 | 0.9000 | Slight focused final lift, but served same-100 degrades. Do not promote. |
| Pruned + catalog-exact safe tags | 0.3364 | 0.4727 | 0.5182 | 0.6273 | 0.9000 | No advantage over prune-only. |
| Native LanceDB safe-tag hybrid branch only | 0.0091 | 0.0091 | 0.0091 | 0.0273 | 0.2636 | API works, this query design does not. |

## Branch Quality Clues

Same-100 branch diagnostics. These are branch recall@100 / recall@1000 on fired turns unless noted.

| Branch | Old | Current V1 | Pruned | Dense-only attrs | Catalog-exact safe tags | Read |
|---|---:|---:|---:|---:|---:|---|
| BM25 | 0.369 / 0.586 | 0.292 / 0.503 | 0.294 / 0.504 | 0.224 / 0.368 | 0.238 / 0.453 | The old BM25 path was stronger. Removing or exact-filtering V1 phrases hurts badly. |
| Qwen8 metadata | 0.341 / 0.553 | 0.257 / 0.465 | 0.258 / 0.465 | 0.258 / 0.465 | 0.258 / 0.465 | Metadata dense is useful but not enough. |
| Qwen8 attributes | 0.137 / 0.408 | 0.099 / 0.340 | 0.099 / 0.340 | 0.097 / 0.330 | 0.099 / 0.340 | Current attribute query is weak; dense-only V1 facts did not fix it. |
| Qwen0.6 lyric | 0.000 / 0.125 on 8 fired | 0.046 / 0.131 on 175 fired | 0.045 / 0.131 | 0.045 / 0.131 | 0.045 / 0.131 | Use 0.6B only for lyrics. It should not carry metadata/attribute branches. |
| CLAP sonic_nl | not in old as this exact branch | 0.074 / 0.303 | 0.074 / 0.303 | 0.074 / 0.303 | 0.074 / 0.303 | Weak alone; keep one CLAP branch for sonic requests, not all variants. |
| Anchor image centroid | 0.381 / 0.485 | 0.379 / 0.480 | 0.380 / 0.481 | 0.380 / 0.481 | 0.380 / 0.481 | Strong branch. Do not prune away anchor centroids blindly. |
| Anchor CF centroid | 0.260 / 0.426 | 0.294 / 0.471 | 0.295 / 0.472 | 0.295 / 0.472 | 0.295 / 0.472 | User/anchor CF is a real signal for sequential next-play behavior. |
| Resolved artist discography | 0.412 / 0.417 on 575 fired | 0.667 / 0.667 on 156 fired | 0.669 / 0.669 | 0.669 / 0.669 | 0.669 / 0.669 | Great when correctly gated. Firing less but cleaner after V1 role typing. |

## Rescue/Regression Summary

Compared with current V1 all-retrievers on the same 800 turns:

| Variant | final@20 rescues | final@20 regressions | Read |
|---|---:|---:|---|
| Pruned branches | 44 | 13 | Diagnostic only: some current branches hurt fused ordering, but this does not prove recall improved. |
| Dense-only V1 attrs | 36 | 19 | Diagnostic only, and candidate recall regresses. |
| Catalog-exact safe tags | 37 | 14 | Diagnostic only, and candidate recall regresses. |

Example pruned rescues:

| Session | Turn | Current rank | Pruned rank |
|---|---:|---:|---:|
| 19c7e5bf-0797-40c5-b798-4d024af9558d | 4 | 26 | 10 |
| b60dab84-45ca-4b1f-b3ff-497604217af5 | 8 | 26 | 6 |
| 1dbc5930-21a7-41ab-82d3-0f1d278eac2e | 2 | 46 | 17 |
| 1dbc5930-21a7-41ab-82d3-0f1d278eac2e | 5 | 25 | 12 |
| c1c115ca-eae2-43b9-a8cf-9bdb349d95d8 | 3 | not found | 4 |
| 7f2b18a6-f30c-4d96-8cb4-e08b8c1c6f3b | 1 | 107 | 16 |

Example pruned regressions:

| Session | Turn | Current rank | Pruned rank |
|---|---:|---:|---:|
| d9a65836-7165-45bf-aa3e-3ef7ba5d073a | 5 | 17 | 45 |
| b38bed11-2d23-4518-9751-66f0a433d145 | 2 | 17 | 35 |
| c1c115ca-eae2-43b9-a8cf-9bdb349d95d8 | 5 | 6 | 49 |
| 77ea612c-6bdd-43a2-b15f-52ca9afb98c2 | 7 | 4 | 23 |
| b2a18a51-2a76-4cf5-9f2f-39c80601deee | 2 | 16 | 45 |

## LanceDB Hybrid Check

Installed LanceDB: 0.30.2.

Confirmed:

- Native hybrid search works on the real catalog when using the Qwen8B attribute vector column plus FTS over `tag_list_text`.
- `MatchQuery(query, column, boost=...)` is the field/term boost path for FTS clauses.
- `BoostQuery` is not field boosting in this version; it is a positive/negative-query wrapper.
- Hybrid reranking with `RRFReranker` returns `_relevance_score`; selecting `_score` directly in the result projection can fail.

Measured result:

| Probe | Fired | hit@20 | hit@50 | hit@100 | hit@1000 | Decision |
|---|---:|---:|---:|---:|---:|---|
| Qwen8 attrs + exact-safe tag hybrid, branch only | 81/110 | 0.0091 | 0.0091 | 0.0273 | 0.2636 | Reject this exact query design. |

Interpretation: hybrid is worth using, but not with exact-safe tags only. The next test should use a softer lexical field like cleaned request/fact text plus weighted catalog tag aliases, not only exact catalog tag names.

## Per-Idea Decisions

| Idea | Decision | Evidence | Next action |
|---|---|---|---|
| Prune noisy branches: Qwen0.6B metadata/attrs, redundant CLAP variants, redundant enriched variants | Do not promote as recall fix | Same-100 union@20 drops 0.4250 -> 0.3875. final@20 movement is diagnostic only. | Use only as a diagnostic clean-room config when studying branch noise. |
| Route V1 attribute facts to dense-only and remove BM25 tag fanout | Reject for served path | BM25 recall@1000 drops 0.504 -> 0.368 and same-100 metrics regress vs prune-only | Keep raw lexical BM25 signal available. |
| Exact catalog-safe V1 attribute tags in BM25 | Reject/defer | Same-100 union and final are worse than prune-only; focused-110 no gain | Replace hard exact whitelist with soft tag normalization and boosted lexical query text. |
| Native LanceDB hybrid with safe tags | Reject current query design; keep API path | API works, but focused branch-only hit@20 is 1/110 | Retest with softer query text and alias-expanded tags. |
| Qwen0.6B as all-purpose dense retriever | Reject | Current diagnostics show weak metadata/attribute branches and user concern is valid | Keep Qwen0.6B for lyrics only; Qwen8B for metadata/attributes. |
| More state prompt work right now | Defer | Frozen-state tests show the problem is not fixed by consuming V1 facts differently; branch noise and BM25/tag/query design dominate this pass | Do state prompt work only if turn-level audits show missing facts, not because retrieval fails. |

## What The Gap Is

The gap looks like a retrieval/query construction gap, with some final-fusion pressure, not a pure state-extraction gap.

Observed failure modes:

- The old BM25 path did better than current V1 BM25. V1 facts are cleaner structurally, but the way we convert them into BM25/tag clauses is losing useful lexical signal or adding the wrong lexical signal.
- Candidate recall is still not healthy. Pruning improves final ranking but lowers union@20 and union@100, so cleaner branch selection alone cannot solve it.
- Exact tag mapping is too brittle. If the user says "raw emotion" or "late night guitar haze," exact catalog tags will miss useful synonyms. But using the whole phrase as a tag-like clause can still help BM25. We need soft lexical/tag normalization, not exact-only mapping.
- Dense attributes are underperforming. Qwen8B attribute recall@1000 is only around 0.34 on the same-100 smoke. Better query text may help, but dense-only V1 attribute facts did not.
- Lyrical search remains thin. The lyric branch fires more under current V1, but recall is low. This likely needs a lyric/theme-specific query and maybe lyric metadata if available, not all-purpose dense search.
- Sequential behavior matters. Anchor image/audio/CF and resolved artist discography remain among the strongest branches. The system should preserve satisfied-prior/style-reference/history distinctions and use those as anchors, but avoid letting old anchors dominate novelty requests.

## Recommended Overnight Goal

Run one additive candidate-quality experiment, not another broad prompt/schema iteration:

1. Freeze V1 extractor/schema and use the current projected state.
2. Keep the current baseline pools protected. Optionally report pruned as a diagnostic sidecar, but do not use it as the recall baseline.
3. Add one new branch family at a time, additively against protected baseline pools:
   - soft tag/scene lexical branch: cleaned request text + V1 attribute facts + alias-expanded catalog tags;
   - Qwen8B hybrid branch: Qwen8B attribute vector + BM25 over cleaned track search text and tag text;
   - lyric/theme branch: lyric/theme facts only, using Qwen0.6B lyric vectors and BM25 over lyric/theme text if available;
   - anchor-CF/tag branch: liked/satisfied prior tracks fan out through CF plus shared high-specificity tags;
   - artist-neighbor branch: explicit style-reference artist or liked-prior artist to similar artists, with novelty demotion only when explicit.
4. Measure additive union@20 first. If union@20 does not improve, report union@50/100 and branch rank of GT.
5. Do not replace baseline pools while testing. Pure additive union should not regress.
6. Only after candidate recall improves, test final fusion/ranker changes.

## Artifacts

- Same-100 current V1 smoke: `exp/smoke_satisfied_anchor_100sessions_20260608/`
- Pruned same-100 smoke: `exp/v1_regression_pruned_100sessions_20260608/`
- Dense-only V1 attrs same-100 smoke: `exp/v1_regression_pruned_dense_attrs_100sessions_20260608/`
- Safe-tag same-100 smoke: `exp/v1_regression_pruned_safe_tags_100sessions_20260608/`
- Focused-110 matrices:
  - `v1_regression_pruned_focused110_matrix.json`
  - `v1_regression_pruned_dense_attrs_focused110_matrix.json`
  - `v1_regression_pruned_safe_tags_focused110_matrix.json`
  - `v1_regression_safe_tag_hybrid_focused110.json`

## Conclusion

If we only have one overnight slot, spend it on additive candidate recall with soft tag/scene hybrid branches and protected baseline pools.

Do not spend it on more LLM extraction. Do not spend it on global RRF/ranker work yet. The extractor/state boundary is good enough for this next test; the weak point is how retrieval consumes that state into lexical/tag/dense branches.
