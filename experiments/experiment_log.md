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

## 2026-06-14 - State-Ranker v10 Cleanup

Decision:

- Replace the active v0plus compiler surface with `state_ranker_v10_*` configs.
- Make the trace contract explicit: `extracted_state`, `compiled_state`,
  `retrieval.branches`, ordered `ranking.stages`, and canonical
  `final_recommendation`.
- Keep response generation and evaluator output tied to
  `final_recommendation.primary_track_id` / `track_ids`.

Current read:

- `state_ranker_v10_rrf_devset`: NDCG@20 0.1492, Hit@20 0.3183, branch
  union@1000 0.8919.
- `state_ranker_v10_lgbm_devset`: NDCG@20 0.4562, Hit@20 0.6138, MRR 0.4102.
- `state_ranker_v10_lgbm_blindset_A`: CodaBench submission `797598`, nDCG@20
  0.4380, catalog diversity 0.0313, lexical diversity 0.7670, LLM judge 4.2000,
  composite 0.5389.
- The learned-ranker stage improves over previous `v0plus_compiler_devset_rr2`
  by +0.1112 NDCG@20, +0.0833 Hit@20, and +0.1194 MRR.

Next step:

- Merge the v10 cleanup PR, then remove any remaining stale local/source
  references in a follow-up only if they are not needed for audit history.

## 2026-06-15 - Issue #127 visual route (Lever B): coverage up, top-20 flat

Decision:

- Added a visual-gated SigLIP-2 text->cover-art dense branch (`DenseBranch.gated_on`;
  experiment config kept OUT of `configs/` to preserve the canonical 3-config
  surface — recreate from the snippet in `experiments/visual_route_lever_b.md`).
  Paired sharded A/B on all 253 visual turns: **union@1000 0.759 -> 0.802
  (+0.044)** but **hit@20/ndcg@20 flat** (frozen v10 reranker does not promote the
  new candidates). Verdict: validated coverage lever, **necessary-not-sufficient,
  do not ship alone.** Full writeup: `experiments/visual_route_lever_b.md`.

Current read:

- Pool-position diagnostic: SigLIP's incremental candidates land deep (70% beyond
  rank 100); ~half of visual GT never reaches the LGBM `pool_k=500` scorable pool.
  LGBM is 94% effective on in-pool GT, so the bottleneck is retrieval depth, not
  the reranker. Real levers live in pool-depth (#129) / reranker (#128) / a
  stronger visual retriever, not in branch wiring.
- Reusable infra on `claude/visual-route`: `gated_on` dense branches and
  `--session_ids_file` support on Modal incl. sharding (curated subset filtered
  then sharded -> ~7.5 min vs ~16 min single-container).
