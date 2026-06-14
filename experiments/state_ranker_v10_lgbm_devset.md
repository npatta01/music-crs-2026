# Experiment: state_ranker_v10_lgbm_devset

**Date:** 2026-06-14
**Config:** `configs/state_ranker_v10_lgbm_devset.yaml`

## Summary

Current devset score anchor. The run uses the v10 trace contract and serves the
`lgbm_v10` stage through canonical `final_recommendation`.

## Comparison

| Run | NDCG@20 | Hit@20 | MRR |
|---|---:|---:|---:|
| Previous `v0plus_compiler_devset_rr2` | 0.3450 | 0.5305 | 0.2908 |
| `state_ranker_v10_lgbm_devset` | 0.4520 | 0.6105 | 0.4055 |
| Delta | +0.1070 | +0.0800 | +0.1147 |

## Ranking Quality

| Metric | Value |
|---|---:|
| NDCG@1 | 0.3349 |
| NDCG@5 | 0.4158 |
| NDCG@10 | 0.4350 |
| NDCG@20 | 0.4520 |
| MRR | 0.4055 |

## Retrieval Coverage

| Metric | Value |
|---|---:|
| Hit@1 | 0.3349 |
| Hit@5 | 0.4839 |
| Hit@10 | 0.5436 |
| Hit@20 | 0.6105 |
| Branch union@20 | 0.4299 |
| Branch union@100 | 0.6255 |
| Branch union@200 | 0.7209 |
| Branch union@1000 | 0.8919 |

## Stage Diagnostics

| Stage | Fired | Hit@1 | Hit@20 | Hit@100 | Hit@1000 |
|---|---:|---:|---:|---:|---:|
| `candidate_fusion` | 8000 | 0.0493 | 0.3185 | 0.4915 | 0.7206 |
| `lgbm_v10` | 8000 | 0.3349 | 0.6105 | 0.7201 | 0.8200 |

## Trace Contract

- `ranking.final_stage`: `lgbm_v10`
- `final_recommendation.source_stage`: `lgbm_v10`
- `final_recommendation.ranking_mode`: `lgbm`
- `predicted_track_ids == final_recommendation.track_ids[:20]`

## Files

- Inference predictions: `exp/inference/devset/state_ranker_v10_lgbm_devset.json`
- Trace: `exp/inference/devset/state_ranker_v10_lgbm_devset_trace.jsonl`
- Aggregate scores: `exp/scores/devset/state_ranker_v10_lgbm_devset.json`
- Branch diagnostics: `exp/scores/devset/state_ranker_v10_lgbm_devset_branch_diagnostics.json`
- Per-sample metrics: `exp/scores/devset/state_ranker_v10_lgbm_devset_samples.csv`
