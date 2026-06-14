# Music Recommender Leaderboard - Devset

Devset = 1000 sessions × 8 turns = 8000 turns, 47,071-track catalog. Higher is
better for all metrics. Hit@1000 for reranker rows equals Hit@20 (pool depth = 20).

| Rank | Run / config | Role | NDCG@20 | Hit@20 | Hit@1000 | MRR |
|---:|---|---|---:|---:|---:|---:|
| 1 | `v0plus_compiler_devset_rr2` | **Current best** — LambdaMART v9, pruned RRF pool, V1 state | 0.3450 | 0.5305 | 0.5305† | 0.2908 |
| 2 | `v0plus_compiler_pruned_resolved_tags_devset` | **RRF baseline** — pruned branches + resolved tags, V1 state | 0.1374 | 0.293 | 0.698 | 0.099 |
| 3 | `v0plus_compiler_all_retrievers_devset` | All-branches coverage reference (RRF, V1 state) | 0.1255 | 0.274 | 0.729 | 0.090 |

† Reranker outputs top-20 only; Hit@1000 = Hit@20.

## Fresh Devset Capture (2026-06-13)

Run: `v0plus_compiler_devset_rr2`, Modal 50-shard full devset
(`20260613T164013Z-bf39ef`) on `0622986`.

| Metric family | @1 | @5 | @10 | @20 | @50 | @100 | @200 | @500 | @1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| final Hit@k | 0.2127 | 0.3828 | 0.4551 | 0.5305 | 0.5305 | 0.5305 | 0.5305 | 0.5305 | 0.5305 |
| branch union@k | - | - | - | 0.4304 | 0.5397 | 0.6259 | 0.7218 | - | 0.8924 |
| final / union | - | - | - | 1.233 | 0.983 | 0.848 | 0.735 | - | 0.594 |

For reranker rows, `union@20` is not a hard ceiling for final Hit@20: the
LambdaMART stage reranks over a deeper branch pool and can promote candidates
that were outside every branch's own top 20.

## Blind-A (CodaBench, 2026-06-13)

| Submission | File | nDCG@20 | catalog_diversity | lexical_diversity | llm_judge | composite |
|---|---|---:|---:|---:|---:|---:|
| `795544` | `rr2-0622986.zip` | **0.4261** | 0.0311 | 0.7755 | 4.2500 | **0.5375** |

Fresh resubmission artifact from `0622986`: `submission/rr2-0622986.zip`
(same contents as `submission_v0plus_compiler_blindset_A_rr2_20260613.zip`).

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
