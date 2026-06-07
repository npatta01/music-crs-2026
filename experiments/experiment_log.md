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

## 2026-06-06 - Devset Recall-Gap Baseline Snapshot

Decision:

- Keep the durable recall-gap analysis under `experiments/analysis/` instead of
  a top-level `reports/` folder so it is clearly an experiment snapshot.
- Treat the HTML/JSON/Markdown package as a replay contract for follow-up state,
  routing, and ranker work, not as evergreen product documentation.

Current read:

- The snapshot is scoped to `v0plus_compiler_all_retrievers_devset` and the
  devset trace/prediction/ground-truth artifacts available at generation time.
- Rerun the report after extractor, retriever, ranker/fusion, catalog/index, or
  split changes before acting on old cohort counts or example diagnoses.

Next step:

- Use the included state experiment packs for small before/after tests, then
  update or replace this snapshot if the new system changes the conclusions.

## 2026-06-07 - Focused 110 Additive Candidate-Recall Matrix

Decision:

- Keep the focused 110-pack additive matrix as candidate-source evidence for
  frozen V1 state/projection work.
- Measure branch pools additively against protected saved-trace baseline pools;
  do not replace the baseline when judging candidate recall.

Current read:

- Protected saved-trace baseline is 60/110 at union@20, union@50, and union@100
  on the focused pack.
- Existing all-candidate branches improve additive union@20 to 66/110.
- New synthetic tag/popularity/artist-neighbor branches improve additive
  union@20 to 64/110 on their own, and diagnostic OR with saved branches reaches
  71/110 at union@20 and 88/110 at union@100.
- Candidate recall improves, but the remaining misses show this is not solved
  by branch gating alone; ranking/fusion and possibly source/query design remain
  separate follow-up work.

Next step:

- Use the additive report's rescued and still-missed examples to decide which
  branches are worth production gating, then run a separate ranking/fusion goal.
