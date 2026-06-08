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

## 2026-06-07 - Focused 110 All-On Branch Attribution

Decision:

- Keep the all-on branch-pool report as the focused-pack source-recall audit
  for frozen V1 state/projection.
- Do not promote the added lyric/raw-attribute branches from this pass; they are
  valid diagnostics but add no current-baseline rescues on the focused pack.

Current read:

- Current focused baseline is existing modal+synthetic OR plus query-text tag
  popularity: 75/110 union@20, 87/110 union@50, and 91/110 union@100.
- Expanded all-on v3 plus protected saved-trace pools reaches 74/110 union@20,
  85/110 union@50, and 89/110 union@100.
- Current plus all-on v3 remains 75/110, 87/110, and 91/110, with zero new
  current-baseline rescues at @20, @50, or @100.

Next step:

- Treat the remaining 19 current union@100 misses as source/query-design work.
- Treat the 16 current top100 tail misses as a separate branch-local ordering
  or survivor-slot experiment, not as a global RRF/ranker replacement yet.

## 2026-06-08 - Focused 110 Non-Prompt Candidate-Quality Diagnostic

Decision:

- Freeze V1 state extraction/prompt for this pass; the cached role/projection
  gates are good enough for retrieval diagnostics.
- Keep candidate-level catalog, anchor-CF, and branch-local hybrid features as
  the next measured direction; do not promote direct RRF branch duplication or
  broad branch-family weighting from this pass.

Current read:

- Current+targeted focused baseline is 77/110 union@20, 90/110 union@50, and
  93/110 union@100.
- The promoted non-prompt feature family reaches 84/110 branch-local union@20,
  95/110 union@50, and 100/110 union@100; after tightening two obvious noisy
  GT labels, valid-GT-only union@20 moves 69/97 -> 74/97.
- Plain all-on branches, compiler-aware branch-family scoring, and the capped
  candidate-level scorer create zero valid current-miss final-like top-20
  rescues. The useful signal is branch-local candidate ordering; it still needs
  a stronger learned/listwise scorer or separately measured survivor policy.
- Only 2 valid GTs are absent from all saved deep pools in this focused pack;
  most remaining misses are rank/order, query specificity, or state-role
  consumption issues.

Next step:

- Build a capped top100-200 candidate-level scorer or learned ranker smoke over
  the focused pack before any new full-devset cache-miss run. Use candidate
  metadata, state/catalog feature overlap, anchor-CF, and hard drops only for
  explicit resolved entity exclusions.
