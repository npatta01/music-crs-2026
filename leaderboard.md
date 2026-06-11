# Music Recommender Leaderboard - Devset

This table is intentionally compact. Older rows were pruned from the working
tree because they were stale agent-facing evidence; use Git history for the
full historical leaderboard.

Devset = 1000 sessions x 8 turns = 8000 turns, 47,071-track catalog. Higher is
better for all metrics.

| Rank | Run / config | Role | NDCG@20 | Hit@20 | Hit@1000 | MRR | Report |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | `v0plus_compiler_pruned_resolved_tags_devset` | **Current baseline** (pruned branches + tiered tag resolver, 2026-06-11) | 0.1374 | 0.293 | 0.698 | 0.099 | [report](experiments/v0plus_compiler_pruned_resolved_tags_devset.md) |
| 2 | `v0plus_compiler_all_retrievers_devset` | Candidate-pool generator for the union reranker (2026-06-03) | 0.1255 | 0.274 | **0.7289** | 0.090 | [report](experiments/v0plus_compiler_all_retrievers_devset.md) |
| 3 | `v0plus_compiler_image_devset` | Retired anchor (image-only) | **0.1452** | 0.299 | 0.626 | 0.106 | [report](experiments/v0plus_compiler_image_devset.md) |

## Interpretation

- `pruned_resolved_tags` is the production ranking baseline: dedups the Qwen
  0.6B dense branches (paired +0.0137 ndcg@20, t=3.1 on 800 turns) and grounds
  attribute phrases to catalog tags with scores (retrieval-neutral, feeds
  trained-ranker features). union@1000 0.893.
- `all_retrievers` keeps the candidate-generation role (best union/deep
  coverage) for the union-pool reranker workstream (#95).
- `image_devset` retains the single highest NDCG@20 but with far weaker
  coverage (hit@1000 0.626) and no multi-retriever union; retired.
- Historical BM25, dense-only, rewrite, Milvus, LanceDB, and offline reranker
  rows are available in Git history, not in the current working tree.
