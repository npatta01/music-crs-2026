# Experiment: state_ranker_v10_lgbm_devset

**Date:** 2026-06-29
**Config:** `configs/state_ranker_v10_lgbm_devset.yaml`
**Backend:** local (2 shards / 2 workers), run_id `20260629T190936Z-54e94a`

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | candidate_fusion → lgbm_v10 rerank |
| retrieval_topk | 20 |
| ranking.mode | lgbm (model_version lgbm_v10, bundle models/reranker_v10) |
| state extraction | prompt_version v1, file_per_turn cache |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.2546 |
| NDCG@5 | 0.3450 |
| NDCG@10 | 0.3664 |
| NDCG@20 | 0.3844 |
| NDCG@50 | 0.3844 |
| NDCG@100 | 0.3844 |
| NDCG@200 | 0.3844 |
| NDCG@500 | 0.3844 |
| NDCG@1000 | 0.3844 |
| MRR | 0.3325 |
| MRR@100 | 0.3325 |
| MRR@200 | 0.3325 |
| MRR@500 | 0.3325 |
| MRR@1000 | 0.3325 |

_Predictions are top-20, so all cutoffs ≥20 equal the @20 value._

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.2546 |
| Hit@5 | 0.4240 |
| Hit@10 | 0.4904 |
| Hit@20 | 0.5610 |
| Hit@50 | 0.5610 |
| Hit@100 | 0.5610 |
| Hit@200 | 0.5610 |
| Hit@500 | 0.5610 |
| Hit@1000 | 0.5610 |
| % GT not in top-20 | 43.9% |
| % GT not in top-100 | 43.9% |
| % GT not in top-200 | 43.9% |
| % GT not in top-500 | 43.9% |
| % GT not in top-1000 | 43.9% |
| Mean rank (when found) | 4.1 |
| Median rank (when found) | 2.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.5265 |
| Catalog diversity @100 | 0.5265 |
| Lexical diversity | 0.0000 |

_Lexical diversity is 0.0 because lm_type=dummy emits no natural-language response._

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.3781 | 0.554 | 0.554 | 1000 |
| 2 | 0.4627 | 0.638 | 0.638 | 1000 |
| 3 | 0.4035 | 0.591 | 0.591 | 1000 |
| 4 | 0.3812 | 0.572 | 0.572 | 1000 |
| 5 | 0.3666 | 0.553 | 0.553 | 1000 |
| 6 | 0.3476 | 0.516 | 0.516 | 1000 |
| 7 | 0.3531 | 0.517 | 0.517 | 1000 |
| 8 | 0.3823 | 0.547 | 0.547 | 1000 |

## Stage Recall (denominator = turns stage fired, n=8000)

| Stage | h@1 | h@20 | h@100 | h@1000 |
|---|---|---|---|---|
| candidate_fusion | 0.0496 | 0.3197 | 0.4936 | 0.7212 |
| lgbm_v10 | 0.2546 | 0.5610 | 0.6827 | 0.8159 |

_The LambdaMART rerank lifts hit@20 from 0.32 (fusion pool) to 0.56._

## Files

- Inference predictions: `exp/inference/devset/state_ranker_v10_lgbm_devset.json`
- Aggregate scores: `exp/scores/devset/state_ranker_v10_lgbm_devset.json`
- Per-sample metrics: `exp/scores/devset/state_ranker_v10_lgbm_devset_samples.csv`
- Branch diagnostics: `exp/scores/devset/state_ranker_v10_lgbm_devset_branch_diagnostics.json`

## Notes

- Resilience fix applied to the config during this run: added `num_retries: 4` + `timeout: 60`
  to the DeepInfra `qwen_0_6b` embedder, after a transient `litellm.Timeout` killed a shard at
  156/250. Resilience-only; does not affect metrics.
- Local speed finding: on the single unified-memory GPU, 2 shards (~0.137 sessions/s) beats
  single-process (~0.108) and 4 shards (~0.069 — GPU over-contention). ~50 min wall for devset.
