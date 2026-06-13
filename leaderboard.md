# Music Recommender Leaderboard - Devset

Devset = 1000 sessions × 8 turns = 8000 turns, 47,071-track catalog. Higher is
better for all metrics. Hit@1000 for reranker rows equals Hit@20 (pool depth = 20).

| Rank | Run / config | Role | NDCG@20 | Hit@20 | Hit@1000 | MRR |
|---:|---|---|---:|---:|---:|---:|
| 1 | `v0plus_compiler_devset_rr2` | **Current best** — LambdaMART v9, pruned RRF pool, V1 state | 0.3449 | 0.531 | 0.531† | 0.291 |
| 2 | `v0plus_compiler_pruned_resolved_tags_devset` | **RRF baseline** — pruned branches + resolved tags, V1 state | 0.1374 | 0.293 | 0.698 | 0.099 |
| 3 | `v0plus_compiler_all_retrievers_devset` | All-branches coverage reference (RRF, V1 state) | 0.1255 | 0.274 | 0.729 | 0.090 |

† Reranker outputs top-20 only; Hit@1000 = Hit@20.

## Blind-A (CodaBench, 2026-06-13)

| Config | nDCG@20 | catalog_diversity | lexical_diversity | llm_judge | composite |
|---|---:|---:|---:|---:|---:|
| `v0plus_compiler_blindset_A_rr2` | **0.4261** | 0.031 | 0.774 | 4.20 | **0.5336** |

Blind nDCG@20 (0.426) > devset nDCG@20 (0.345) — good generalization.
Low catalog_diversity (0.031) is the #1 lever for v10: `artist_best_rank_in_union`
accounts for 41.6% of model gain → artist concentration in top-20.

## Interpretation

- **rr2**: LambdaMART v9 (148 features, 136 trees) reranks the pruned RRF pool.
  +151% NDCG@20 over RRF baseline on devset; +131% over the RRF blind-A baseline.
  Reproduce via [docs/reproduce_reranker.md](docs/reproduce_reranker.md).
- **pruned_resolved_tags**: pruned 4-branch retrieval + tiered tag resolver. Higher
  Hit@1000 than rr2 because it returns a full 1000-track pool.
- **all_retrievers**: maximum branch coverage (12 dense + BM25 + centroid). Best
  Hit@1000 (0.729) but lowest NDCG@20 — kept as a coverage-ceiling reference.
- Historical rows (BM25-only, image-only, Milvus, offline reranker) in Git history.
