# Music Recommender Leaderboard - Devset

This table is intentionally compact. Older rows were pruned from the working
tree because they were stale agent-facing evidence; use Git history for the
full historical leaderboard.

Devset = 1000 sessions x 8 turns = 8000 turns, 47,071-track catalog. Higher is
better for all metrics.

| Rank | Run / config | Role | NDCG@20 | Hit@20 | Hit@1000 | MRR | Report |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | `v0plus_compiler_image_devset` | Current score anchor | **0.1452** | 0.299 | 0.626 | 0.106 | [report](experiments/v0plus_compiler_image_devset.md) |
| 2 | `v0plus_compiler_all_retrievers_devset` | Latest coverage experiment | 0.1219 | 0.266 | **0.6967** | 0.087 | [report](experiments/v0plus_compiler_all_retrievers_devset.md) |

## Interpretation

- `v0plus_compiler_image_devset` remains the current top-20 ranking baseline.
- `v0plus_compiler_all_retrievers_devset` has better deep candidate coverage,
  but weaker head ranking. Treat it as reranker/candidate-pool evidence rather
  than the canonical ranking config.
- Historical BM25, dense-only, rewrite, Milvus, LanceDB, and offline reranker
  rows are available in Git history, not in the current working tree.
