# Experiment: state_ranker_v10_rrf_devset

**Date:** 2026-06-14
**Config:** `configs/state_ranker_v10_rrf_devset.yaml`

## Summary

Explicit v10 candidate-fusion baseline. This run is the retrieval/feature-build
source for v10 reranker training and does not implicitly stand in for production
ranking when `ranking.mode: lgbm` is configured.

## Ranking Quality

| Metric | Value |
|---|---:|
| NDCG@1 | 0.0493 |
| NDCG@5 | 0.1025 |
| NDCG@10 | 0.1280 |
| NDCG@20 | 0.1492 |
| MRR | 0.1015 |

## Retrieval Coverage

| Metric | Value |
|---|---:|
| Hit@1 | 0.0493 |
| Hit@5 | 0.1553 |
| Hit@10 | 0.2348 |
| Hit@20 | 0.3183 |
| Branch union@20 | 0.4299 |
| Branch union@100 | 0.6255 |
| Branch union@200 | 0.7209 |
| Branch union@1000 | 0.8919 |

## Stage Diagnostics

| Stage | Fired | Hit@1 | Hit@20 | Hit@100 | Hit@1000 |
|---|---:|---:|---:|---:|---:|
| `candidate_fusion` | 8000 | 0.0493 | 0.3183 | 0.4915 | 0.7206 |

## Files

- Inference predictions: `exp/inference/devset/state_ranker_v10_rrf_devset.json`
- Trace: `exp/inference/devset/state_ranker_v10_rrf_devset_trace.jsonl`
- Aggregate scores: `exp/scores/devset/state_ranker_v10_rrf_devset.json`
- Branch diagnostics: `exp/scores/devset/state_ranker_v10_rrf_devset_branch_diagnostics.json`
- Per-sample metrics: `exp/scores/devset/state_ranker_v10_rrf_devset_samples.csv`
