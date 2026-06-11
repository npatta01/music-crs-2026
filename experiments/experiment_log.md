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
- Explicit branch-survivor slots also create zero valid current-miss top-20
  rescues on saved pools; the rescued GTs are branch-local rank 8-18-ish among
  many plausible candidates, so a few reserved slots do not solve selection.
- A capped top100-per-branch, top500-unique, 3-fold learned listwise diagnostic
  over protected+promoted pools also creates zero valid current-miss top-20
  rescues. This weakens the "just learn a selector" hypothesis for the current
  feature set.
- A feature-weight sweep over the same protected+promoted scorer pool also
  creates zero valid current-miss top-20 rescues, even at 8x feature weight.
  Existing hand features are therefore not merely underweighted; the next lever
  needs sharper query/source signals or richer candidate features.
- The residual source-gap worksheet now joins each family back to the all-on
  branch pools: all 19 compact residual source-gap rows are either absent from
  all-on top100 or only present at rank101+. This makes lyric/hidden-target,
  visual text-to-image, temporal scene/popularity, and artist-neighbor source
  work the next grounded candidate-recall lever, not another scalar scorer.
- A stricter recency/new-artist constraint ablation improves over baseline but
  trails the promoted feature family, so reject it as a replacement rather than
  shipping stronger hand-tuned constraints.
- A cached anchor-tag/style-neighbor probe over all catalog tracks gets 15 valid
  branch-only top20 hits but zero current-miss rescues at @20/@50/@100; it only
  finds five misses deep at @1000. Do not add this as a standalone
  candidate-recall branch without a stronger selector.
- Only 2 valid GTs are absent from all saved deep pools in this focused pack;
  most remaining misses are rank/order, query specificity, or state-role
  consumption issues.

Next step:

- Do not keep adding scalar hand-tuned constraints or feature-weight sweeps.
  The next focused experiment should create sharper source/query branches for
  hidden-target/lyric, visual cover/artwork, temporal scene/popularity, and
  novelty artist-neighbor slices, then re-run additive union@20 on the focused
  pack before any expensive full-devset cache-miss run.

## 2026-06-08 - Focused 110 Satisfied-Anchor + Hard-Drop Gap Fix

Decision:

- Keep positive `track_feedback.role="satisfied"` as a soft compiler anchor for
  centroid/tag expansion; pivot gates still prevent stale-anchor tag carryover.
- Keep the retriever-matrix harness fix that applies branch-local rules to
  analysis branches, not only compiler branches.
- Keep `all_candidate_plus_targeted_v4_hard_drop` as the conservative
  diagnostic/prototype variant; reject the full soft rule set as a blanket
  reranker because it hurts valid top-20 on the residual source-gap slice.

Current read:

- On all 110 focused turns, hard-drop targeted branches reach 79/110 additive
  union@20, 92/110 union@50, and 100/110 union@100 against protected saved
  pools; valid-only is 70/97, 82/97, and 89/97.
- As an additive source on top of the prior promoted feature family, coverage
  reaches 87/110 all and 76/97 valid at union@20, and 104/110 all / 93/97 valid
  at union@100.
- On the compact 19 residual source-gap slice, valid top-20 improves from 1/16
  in the prior v4 source-gap run to 3/16 with satisfied anchors plus hard-drop
  analysis-branch rules.
- Remaining gaps are not fixed by scalar soft constraints: lyric/hidden-target,
  visual cover/artwork, temporal scene/popularity, and stale-entity ordering
  still need sharper source/query branches and production gating.

Next step:

- Run one combined saved-pool pass for promoted feature family OR hard-drop
  targeted branches, then evaluate a small production-gating config. Do not
  claim full-devset or leaderboard lift until focused-gated gains survive a
  real devset run.

## 2026-06-11 - Pruned Branches + Tiered Tag Resolver = New Baseline

Decision:

- Promote `v0plus_compiler_pruned_resolved_tags_devset` to the production
  ranking baseline (NDCG@20 0.1374, +9.5% over all_retrievers on the full
  devset; paired-smoke validated at t=3.1 before the full run).
- Retire `bm25_v1_attribute_tag_policy: "catalog_exact"` (consistent paired
  regression) and the `image_devset` score anchor.
- Keep `all_retrievers` as the candidate-pool generator for the union-pool
  reranker (#95); do not delete its config.
- Skip the LLM tier of the tag resolver: on 271 real attribute phrases the
  lexical tiers ground 97% (exact 43% / substring 54%), embedding 3%,
  unresolved 0%.

Current read:

- Branch dedup (Qwen 0.6B duplicates removed) is the causal win: paired
  +0.0137 ndcg@20 (t=3.1, 43/13 hit@20 flips, n=800); fusion_efficiency@20
  0.57 -> 0.72. Full devset: hit@20 0.293, hit@1000 0.698, union@1000 0.893.
- The tiered resolver is retrieval-neutral (+0.0006 paired) but ships
  per-fact `(tag, score, tier)` resolution metadata for trained-ranker
  features.
- Method note: smoke slices must be compared PAIRED on identical seeded
  sessions (`run_experiment.py --num_sessions N`); comparing slice numbers
  to full-devset numbers misled an earlier readout (the seed-50 slice runs
  ~2pp harder than the full devset).

Next step:

- Union-pool reranker (#95) over all_retrievers pools, consuming resolver
  metadata + `.state_features` scorer outputs as features; train on the
  unused train split.
