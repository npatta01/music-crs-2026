# Experiment Log

This log is intentionally short. Historical wave notes and raw artifacts were
pruned from the working tree; use Git history or PRs for old details.

## 2026-06-02 - Pruned Experiment Workspace

Decision:

- Keep only current configs in `configs/`.
- Keep only the latest all-retrievers report and the current image score-anchor report.
- Keep runtime prompt/schema Python modules under `experiments/analysis/`.
- Remove archived configs, stale per-run notes, and raw analysis artifacts from source control.

Current read:

- `v0plus_compiler_image_devset` remains the score anchor: NDCG@20 0.1452.
- `v0plus_compiler_all_retrievers_devset` remains the latest coverage experiment: NDCG@20 0.1219, Hit@1000 0.6967.
- The all-retrievers config is useful as a candidate-pool/reranker direction, not as the best top-20 ranker.

Next step:

- When a new run lands, update only `experiments/README.md`, this file,
  `leaderboard.md`, and `changelog.md` with a concise current-state entry.
  Avoid adding checked-in raw artifacts unless explicitly requested.
