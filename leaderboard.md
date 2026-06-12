# Music Recommender Leaderboard - Devset

This table is intentionally compact. Older rows were pruned from the working
tree because they were stale agent-facing evidence; use Git history for the
full historical leaderboard.

Devset = 1000 sessions x 8 turns = 8000 turns, 47,071-track catalog. Higher is
better for all metrics.

| Rank | Run / config | Role | NDCG@20 | Hit@20 | Hit@1000 | MRR | Report |
|---:|---|---|---:|---:|---:|---:|---|
| — | **+ trained reranker over union** (v7b, 5-fold user-grouped CV) | Reranker replaces RRF (2026-06-12) | **0.1860** | **0.382** | (pool-bound) | — | [report](experiments/rerank_v7b_monotone_2026_06_12.md) |
| 1 | `v0plus_compiler_bugfix_devset` | **Current retrieval baseline** (audit bugfixes, 2026-06-12) | **0.1491** | 0.319 | 0.721 | 0.098 | [PR #115](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/115) |
| 2 | `v0plus_compiler_pruned_resolved_tags_devset` | Prior baseline (pruned branches + tiered tag resolver, 2026-06-11) | 0.1374 | 0.293 | 0.698 | 0.099 | [report](experiments/v0plus_compiler_pruned_resolved_tags_devset.md) |
| 3 | `v0plus_compiler_all_retrievers_devset` | Candidate-pool generator for the union reranker (2026-06-03) | 0.1255 | 0.274 | **0.7289** | 0.090 | [report](experiments/v0plus_compiler_all_retrievers_devset.md) |
| 4 | `v0plus_compiler_image_devset` | Retired anchor (image-only) | 0.1452 | 0.299 | 0.626 | 0.106 | [report](experiments/v0plus_compiler_image_devset.md) |

## Interpretation

- **Trained reranker (v7b) is the headline**: 5-fold user-grouped CV over the
  full 8000 devset turns (every turn scored by a fold that never saw its user)
  = NDCG@20 0.1860, +35% over production RRF 0.1374. Runs over the PRE-bugfix
  pools; rerunning over bugfix pools should compound higher.
- `bugfix_devset` is the current retrieval baseline: 5 audit bugfixes
  (rejection-expansion, release-date filter, negation, pivot soft-adjust,
  catalog zip) = +0.0117 ndcg@20 (full devset, matches the paired smoke
  +0.0115 t=4.15). PR #115 to main.
- `pruned_resolved_tags` was the prior baseline: dedups the Qwen 0.6B dense
  branches (paired +0.0137 ndcg@20, t=3.1) + tiered tag resolver. union@1000 0.893.
- `all_retrievers` keeps the candidate-generation role (best union/deep
  coverage) for the union-pool reranker workstream (#95).
- `image_devset` retains the single highest NDCG@20 but with far weaker
  coverage (hit@1000 0.626) and no multi-retriever union; retired.
- Historical BM25, dense-only, rewrite, Milvus, LanceDB, and offline reranker
  rows are available in Git history, not in the current working tree.
