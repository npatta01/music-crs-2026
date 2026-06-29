# Music Recommender Leaderboard - Devset

Devset = 1000 sessions x 8 turns = 8000 turns, 47,071-track catalog. Higher is
better for all metrics. Final prediction files contain the served top 20; stage
diagnostics report deeper stage recall separately.

| Rank | Run / config | Role | NDCG@20 | Hit@20 | Hit@1000 | MRR |
|---:|---|---|---:|---:|---:|---:|
| 1 | `state_ranker_v10_lgbm_devset` | **Current best** - v10 state-ranker, fresh LambdaMART v10 | 0.4562 | 0.6138 | 0.6138† | 0.4102 |
| 2 | `v0plus_compiler_devset_rr2` | Previous best - LambdaMART v9, v0plus trace contract | 0.3450 | 0.5305 | 0.5305† | 0.2908 |
| 3 | `state_ranker_v10_rrf_devset` | Explicit RRF/candidate-fusion baseline | 0.1492 | 0.3183 | 0.3183† | 0.1015 |

† Final prediction files are top-20 lists, so final Hit@1000 equals Hit@20 for
these rows. Use stage diagnostics for candidate-pool and learned-ranker deep
recall.

## Fresh Devset Capture (2026-06-15 UTC)

Run: `state_ranker_v10_lgbm_devset`, Modal 50-shard full devset
(`20260615T020857Z-b8ec83`) on the v10 trace contract. Shard 47 was rerun
directly with the same run-scoped suffix after the sharded wrapper waited on
that final shard.

| Metric family | @1 | @5 | @10 | @20 | @50 | @100 | @200 | @1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| final Hit@k | 0.3400 | 0.4879 | 0.5466 | 0.6138 | 0.6138 | 0.6138 | 0.6138 | 0.6138 |
| branch union@k | - | - | - | 0.4299 | - | 0.6255 | 0.7209 | 0.8919 |
| `candidate_fusion` stage Hit@k | 0.0493 | - | - | 0.3182 | 0.4224 | 0.4915 | 0.5554 | 0.7206 |
| `lgbm_v10` stage Hit@k | 0.3400 | - | - | 0.6138 | 0.6825 | 0.7212 | 0.7535 | 0.8204 |

The v10 public trace uses `extracted_state`, `compiled_state`,
`retrieval.branches`, ordered `ranking.stages`, and canonical
`final_recommendation`; `predicted_track_ids` equals
`final_recommendation.track_ids[:20]`. Full trace audit found 8000/8000
extracted and compiled states, 0 extractor failures, and no mismatches for
`intent_mode`, `process_constraints`, `routing_tags`, or `hard_filters`.

## Local Devset Recapture (2026-06-29)

Run: `state_ranker_v10_lgbm_devset`, **local 2-shard** (`20260629T190936Z-54e94a`)
on the current pruned config (post #178). Full 8000 turns.

| Metric family | @1 | @5 | @10 | @20 | @50 | @100 | @200 | @1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| final Hit@k | 0.2546 | 0.4240 | 0.4904 | 0.5610 | 0.5610 | 0.5610 | 0.5610 | 0.5610 |
| branch union@k | - | - | - | 0.4323 | - | 0.6270 | 0.7223 | 0.8931 |
| `candidate_fusion` stage Hit@k | 0.0496 | - | - | 0.3197 | 0.4240 | 0.4936 | 0.5576 | 0.7212 |
| `lgbm_v10` stage Hit@k | 0.2546 | - | - | 0.5610 | 0.6372 | 0.6827 | 0.7220 | 0.8159 |

NDCG@20 **0.3844**, MRR **0.3325**, catalog_diversity@20 0.5265 (lexical 0.0, lm_type=dummy).

⚠️ **Discrepancy vs the 2026-06-15 Modal capture** (NDCG@20 0.4562 / Hit@20 0.6138):
the candidate pool matches (fusion Hit@20 0.3197 vs 0.3182; all multimodal branches
fired — CLAP 8000, SigLIP/CLAP centroids ~6950), so retrieval is equivalent. The
−0.072 NDCG@20 gap is entirely in the **lgbm rerank** (Hit@20 0.561 vs 0.614) and most
likely reflects pipeline drift since 2026-06-15 (config pruned/`_fastlocal` folded in,
reranker fix commits #173–#178) rather than a clean regression. Treat 0.4562 as a stale
Modal number; rerun on Modal for an apples-to-apples current baseline before ranking.

## Blind-A (CodaBench)

| Submission | File | nDCG@20 | catalog_diversity | lexical_diversity | llm_judge | composite |
|---|---|---:|---:|---:|---:|---:|
| `797598` | `v10_lgbm_A.zip` | **0.4380** | 0.0313 | 0.7670 | 4.2000 | **0.5389** |
| `795544` | `rr2-0622986.zip` | 0.4261 | 0.0311 | 0.7755 | 4.2500 | 0.5375 |

The v10 submission improves Blind-A nDCG@20 by +0.0119 and composite by +0.0014
over the previous `rr2` submission, despite a small LLM-judge decrease. This
historical Blind-A score predates populated `routing_tags` in the state-ranker
serving trace; rerun Blind-A before treating the next submission as comparable.

## Interpretation

- **state_ranker_v10_lgbm_devset**: Fresh v10 traces plus LambdaMART v10 improve
  devset NDCG@20 by +0.1112, Hit@20 by +0.0833, and MRR by +0.1194 versus the
  previous v9 `rr2` devset report.
- **state_ranker_v10_rrf_devset**: Explicit candidate-fusion baseline; RRF is no
  longer an implicit production default.
- **v0plus_compiler_devset_rr2**: Previous best retained only as historical
  comparison; active configs now use `state_ranker_v10_*`.
