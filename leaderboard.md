# Music Recommender Leaderboard - Devset

Devset = 1000 sessions x 8 turns = 8000 turns, 47,071-track catalog. Higher is
better for all metrics. Final prediction files contain the served top 20; stage
diagnostics report deeper stage recall separately.

| Rank | Run / config | Role | NDCG@20 | Hit@20 | Hit@1000 | MRR |
|---:|---|---|---:|---:|---:|---:|
| 1 | `state_ranker_v10_lgbm_devset` | **Current best** - v10 state-ranker, fresh LambdaMART v10 | 0.4520 | 0.6105 | 0.6105† | 0.4055 |
| 2 | `v0plus_compiler_devset_rr2` | Previous best - LambdaMART v9, v0plus trace contract | 0.3450 | 0.5305 | 0.5305† | 0.2908 |
| 3 | `state_ranker_v10_rrf_devset` | Explicit RRF/candidate-fusion baseline | 0.1492 | 0.3183 | 0.3183† | 0.1015 |

† Final prediction files are top-20 lists, so final Hit@1000 equals Hit@20 for
these rows. Use stage diagnostics for candidate-pool and learned-ranker deep
recall.

## Fresh Devset Capture (2026-06-14)

Run: `state_ranker_v10_lgbm_devset`, Modal 50-shard full devset
(`20260614T145049Z-7f7232`) on the v10 trace contract. Shard 49 was retried with
`--batch_size 8` after the original `64` batch run hit memory pressure.

| Metric family | @1 | @5 | @10 | @20 | @50 | @100 | @200 | @1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| final Hit@k | 0.3349 | 0.4839 | 0.5436 | 0.6105 | 0.6105 | 0.6105 | 0.6105 | 0.6105 |
| branch union@k | - | - | - | 0.4299 | - | 0.6255 | 0.7209 | 0.8919 |
| `candidate_fusion` stage Hit@k | 0.0493 | - | - | 0.3185 | 0.4224 | 0.4915 | 0.5554 | 0.7206 |
| `lgbm_v10` stage Hit@k | 0.3349 | - | - | 0.6105 | 0.6804 | 0.7201 | 0.7524 | 0.8200 |

The v10 public trace uses `extracted_state`, `compiled_state`,
`retrieval.branches`, ordered `ranking.stages`, and canonical
`final_recommendation`; `predicted_track_ids` equals
`final_recommendation.track_ids[:20]`.

## Blind-A (CodaBench)

| Submission | File | nDCG@20 | catalog_diversity | lexical_diversity | llm_judge | composite |
|---|---|---:|---:|---:|---:|---:|
| `795544` | `rr2-0622986.zip` | **0.4261** | 0.0311 | 0.7755 | 4.2500 | **0.5375** |

This is still the latest measured Blind-A CodaBench row. The v10 Blind-A
prediction package has been generated as
`submission/submission_state_ranker_v10_lgbm_blindset_A_20260614.zip`, but no
CodaBench score is available yet.

## Interpretation

- **state_ranker_v10_lgbm_devset**: Fresh v10 traces plus LambdaMART v10 improve
  devset NDCG@20 by +0.1070, Hit@20 by +0.0800, and MRR by +0.1147 versus the
  previous v9 `rr2` devset report.
- **state_ranker_v10_rrf_devset**: Explicit candidate-fusion baseline; RRF is no
  longer an implicit production default.
- **v0plus_compiler_devset_rr2**: Previous best retained only as historical
  comparison; active configs now use `state_ranker_v10_*`.
