# State V1 Satisfied-Anchor Devset Smoke

Date: 2026-06-08

This smoke checks whether the focused-110 candidate-recall changes show any
early generalization on a small devset slice before spending on a full devset
run.

## Run

- Experiment: `v0plus_compiler_all_retrievers_devset`
- Backend: Modal
- Slice: 20 devset sessions, 160 turns
- Output dir: `exp/smoke_satisfied_anchor_20260608`
- Current code change under test: satisfied track feedback is projected as a
  positive soft anchor; focused matrix hard-drop branch logic is already
  committed separately.

## Important Caveat

The "old" comparison uses the existing main-worktree full-devset artifact,
filtered to the exact same 20 session IDs. That artifact is from an older run,
so this is a same-subset directional smoke, not a pure single-change A/B.

## Same-Subset Ranking Metrics

| Metric | Old artifact | New smoke | Delta |
|---|---:|---:|---:|
| NDCG@20 | 0.1184 | 0.1167 | -0.0018 |
| Hit@20 | 0.2813 | 0.2563 | -0.0250 |
| Hit@50 | 0.3938 | 0.4000 | +0.0062 |
| Hit@100 | 0.5000 | 0.4875 | -0.0125 |
| Hit@200 | 0.5562 | 0.5500 | -0.0062 |
| Hit@500 | 0.6687 | 0.6562 | -0.0125 |
| Hit@1000 | 0.7188 | 0.7188 | +0.0000 |
| MRR | 0.0798 | 0.0840 | +0.0042 |
| Mean found rank | 137.9 | 146.8 | +8.9 |
| Median found rank | 39.0 | 33.0 | -6.0 |

Top-20 final recall moved down by four turns on this slice: 45/160 to 41/160.

## Same-Subset Branch Union

| Metric | Old artifact | New smoke | Delta |
|---|---:|---:|---:|
| union@20 | 0.4750 | 0.4813 | +0.0063 |
| union@50 | 0.5938 | 0.6250 | +0.0312 |
| union@100 | 0.6562 | 0.6875 | +0.0312 |
| union@200 | 0.7375 | 0.8000 | +0.0625 |
| union@1000 | 0.9125 | 0.9313 | +0.0188 |
| fusion efficiency @20 | 0.5921 | 0.5325 | -0.0596 |
| fusion efficiency @100 | 0.7619 | 0.7091 | -0.0528 |
| fusion efficiency @1000 | 0.7877 | 0.7718 | -0.0159 |

The branch pool got slightly broader and found more GTs in union, especially at
50/100/200. The final top-20 ranker/fusion did not convert that extra coverage.

## Read

This is not a clean win yet.

Positive signal:
- Candidate union improved on the same 20-session slice.
- union@50 and union@100 improved by five turns each.
- union@200 improved by ten turns.

Negative signal:
- Final Hit@20 dropped by four turns.
- Fusion efficiency worsened at every reported cutoff.
- The extra candidates are arriving below the final top-20, so simply adding
  more branch candidates is not enough.

## Decision

Do not run the full devset as a leaderboard candidate from this change alone.

Keep the satisfied-anchor projection as a candidate-source improvement, but the
next measured work should be a gated/ranked production variant:

1. Gate satisfied-prior/same-album expansion to continuation, accepted, and
   satisfied turns.
2. Gate scene, era, popularity, and temporal branch expansion only when the
   projected state has explicit evidence for that branch.
3. Keep hard drops limited to explicit resolved artist/track/album exclusions.
4. Evaluate whether the union-improved turns can be moved into final top-20
   with branch-local scoring or fusion weights before broadening more branches.

The current evidence says the remaining gap is not only source coverage. It is
now also branch gating and final candidate selection.

## Files

- Predictions: `exp/smoke_satisfied_anchor_20260608/inference/devset/v0plus_compiler_all_retrievers_devset.json`
- Trace: `exp/smoke_satisfied_anchor_20260608/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl`
- Scores: `exp/smoke_satisfied_anchor_20260608/scores/devset/v0plus_compiler_all_retrievers_devset.json`
- Branch diagnostics: `exp/smoke_satisfied_anchor_20260608/scores/devset/v0plus_compiler_all_retrievers_devset_branch_diagnostics.json`
- Same-subset comparison: `exp/smoke_satisfied_anchor_20260608/scores/devset/v0plus_compiler_all_retrievers_devset_smoke_comparison.json`
