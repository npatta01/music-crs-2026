# Experiment: v0plus_compiler_all_retrievers_reranked_devset

**Date:** 2026-06-08
**Config:** `configs/v0plus_compiler_all_retrievers_reranked_devset.yaml`
**Branch:** semih_reranker_v4 · **Backend:** Modal · run_id 20260608T105413Z-14990a

> NOTE: deployed reranker model was trained on the devset features it reranks (train-on-test),
> so these numbers are OPTIMISTIC. Leakage-free signal: offline CV-OOF NDCG@20 0.2535
> (+0.008 over the A-F baseline). This run validates the v4 serving path end-to-end on Modal.

## Configuration
| Field | Value |
|---|---|
| lm_type | dummy |
| retrieval_type | bm25 |
| ranker | lambdamart |
| reranker_model_path | /root/models/rerank/model.txt |
| retrieval_topk | 1000 |
| model features | 142 (A-F + block P + block U; no block H) |

## Ranking Quality
| Metric | Value |
|---|---|
| NDCG@1 | 0.1539 |
| NDCG@5 | 0.2267 |
| NDCG@10 | 0.2490 |
| NDCG@20 | 0.2670 |
| NDCG@50 | 0.2836 |
| NDCG@100 | 0.2938 |
| NDCG@200 | 0.3018 |
| MRR | 0.2229 |
| MRR@100 | 0.2222 |

## Retrieval Coverage
| Metric | Value |
|---|---|
| Hit@1 | 0.1539 |
| Hit@5 | 0.2944 |
| Hit@10 | 0.3635 |
| Hit@20 | 0.4344 |
| Hit@50 | 0.5174 |
| Hit@100 | 0.5799 |
| Hit@1000 | 0.7612 |
| % GT not in top-20 | 56.6% |
| % GT not in top-100 | 42.0% |
| Mean rank (when found) | 100.1849 |
| Median rank (when found) | 12.0000 |

## Diversity
| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.5524 |
| Catalog diversity @100 | 0.8966 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown
| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.2411 | 0.3970 | 0.5260 | 1000 |
| 2 | 0.3074 | 0.4970 | 0.6610 | 1000 |
| 3 | 0.2821 | 0.4750 | 0.6300 | 1000 |
| 4 | 0.2739 | 0.4530 | 0.5950 | 1000 |
| 5 | 0.2702 | 0.4320 | 0.5830 | 1000 |
| 6 | 0.2550 | 0.4140 | 0.5610 | 1000 |
| 7 | 0.2489 | 0.3920 | 0.5340 | 1000 |
| 8 | 0.2572 | 0.4150 | 0.5490 | 1000 |

## Files
- Inference predictions: `exp/inference/devset/v0plus_compiler_all_retrievers_reranked_devset.json`
- Aggregate scores: `exp/scores/devset/v0plus_compiler_all_retrievers_reranked_devset.json`


## Retrieval Ceiling (union) vs Fusion Efficiency
| k | union@k (recall ceiling) | hit@k | fusion_efficiency@k |
|---|---|---|---|
| 20 | 0.4766 | 0.4344 | 0.9114 |
| 100 | 0.6624 | 0.5799 | 0.8754 |

union@k = fraction of turns whose golden track is within the merged branch-pool union's top-k
(the ceiling the reranker can't exceed). fusion_efficiency@k = hit@k / union@k. Reranker is
~91% efficient @20; the limiter is retrieval coverage (~52% of turns lack the golden in the
union top-20).
