# Experiment: state_ranker_v10_lgbm_devset

**Date:** 2026-06-15 UTC
**Config:** `configs/state_ranker_v10_lgbm_devset.yaml`

## Summary

Current devset score anchor. The run uses the v10 trace contract and serves the
`lgbm_v10` stage through canonical `final_recommendation`.

## Comparison

| Run | NDCG@20 | Hit@20 | MRR |
|---|---:|---:|---:|
| Previous `v0plus_compiler_devset_rr2` | 0.3450 | 0.5305 | 0.2908 |
| `state_ranker_v10_lgbm_devset` | 0.4562 | 0.6138 | 0.4102 |
| Delta | +0.1112 | +0.0833 | +0.1194 |

## Ranking Quality

| Metric | Value |
|---|---:|
| NDCG@1 | 0.3400 |
| NDCG@5 | 0.4204 |
| NDCG@10 | 0.4393 |
| NDCG@20 | 0.4562 |
| MRR | 0.4102 |

## Retrieval Coverage

| Metric | Value |
|---|---:|
| Hit@1 | 0.3400 |
| Hit@5 | 0.4879 |
| Hit@10 | 0.5466 |
| Hit@20 | 0.6138 |
| Branch union@20 | 0.4299 |
| Branch union@100 | 0.6255 |
| Branch union@200 | 0.7209 |
| Branch union@1000 | 0.8919 |

## Stage Diagnostics

| Stage | Fired | Hit@1 | Hit@20 | Hit@100 | Hit@1000 |
|---|---:|---:|---:|---:|---:|
| `candidate_fusion` | 8000 | 0.0493 | 0.3182 | 0.4915 | 0.7206 |
| `lgbm_v10` | 8000 | 0.3400 | 0.6138 | 0.7212 | 0.8204 |

## Trace Contract

- `ranking.final_stage`: `lgbm_v10`
- `final_recommendation.source_stage`: `lgbm_v10`
- `final_recommendation.ranking_mode`: `lgbm`
- `predicted_track_ids == final_recommendation.track_ids[:20]`
- Full trace state audit: 8000/8000 rows have `extracted_state` and
  `compiled_state`; 0 extractor failures; 0 missing or mismatched
  `intent_mode`, `process_constraints`, `routing_tags`, or `hard_filters`;
  0 resolver/compiled anchor surface-without-id gaps.

## Run Notes

- Modal 50-shard run id: `20260615T020857Z-b8ec83`.
- The original sharded wrapper completed shards 0-46 and 48-49, then was
  stopped after waiting on shard 47; shard 47 was rerun directly with the same
  run-scoped suffix and merged with the other shards.

## Files

- Inference predictions: `exp/inference/devset/state_ranker_v10_lgbm_devset.json`
- Trace: `exp/inference/devset/state_ranker_v10_lgbm_devset_trace.jsonl`
- Aggregate scores: `exp/scores/devset/state_ranker_v10_lgbm_devset.json`
- Branch diagnostics: `exp/scores/devset/state_ranker_v10_lgbm_devset_branch_diagnostics.json`
- Per-sample metrics: `exp/scores/devset/state_ranker_v10_lgbm_devset_samples.csv`
