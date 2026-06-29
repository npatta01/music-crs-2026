# Anchor-clean labels: anchor-aware eval + reranker re-label

**Date:** 2026-06-29
**Status:** design (approved decisions inline; pending spec review)

## Problem

The LambdaMART reranker over-anchors: on a "give me a *different* artist" turn it
ranks the just-played artist #1. SHAP on blind-B case `db8ec85f` showed the two
drivers are `artist_best_rank_in_union` (+0.46) and `b1_cos` (+0.37) — both
favor the anchor because the session reference *is* that artist. The model already
has the pivot cross `x_same_artist_wants_new` and `same_artist_as_abandoned` but
weights them **~0**.

Root cause is the **training target**, not a missing feature. The raw GT is the
synthetic next-track; on pivot turns it is frequently the same artist, and
`anchor-labels-v1.1` shows **5,880 turns** where the synthetic reaction was MOVES
("liked") on an anchoring track right after the listener asked for someone else.
Those poisoned positives teach the cross to stay inert. Output demotion (fix1)
loses on raw GT (−0.0105 ndcg@20) because raw GT rewards anchoring.

## Source artifact

`anchor-labels-v1.1` (GitHub release): clean LLM-judged labels over train (106,393
turns) + dev (7,000). Each `(sid, tn)` re-judges the GT/just-played candidate on
two axes — ANCHOR (`asked_for_different_artist AND same_artist`, same_artist is a
deterministic catalog check) and CONTENT (`content_fit`). Labels:
POSITIVE / NEGATIVE(`artist_anchoring`|`content_violation`) / DROP / HOLD, each
with `confidence_weight` (1.0 agree, 0.6 Opus-arbitrated, 0.3 agreed-HOLD).
Join key: `sid, tn`. Local card: `data/anchor_labels_v1/DATASET_CARD.md`.

These are a **cleaning of the existing GT positive**, not new different-artist
candidates.

## Decisions (user-approved)

1. **Poisoned positives → grade-0, keep the rows** (do not drop the turn). Lets us
   revisit later (e.g. inject a different-artist positive) without rebuilding.
2. **Include `content_violation` negatives**, not only `artist_anchoring`.

## Design

### Phase 0 — Validate the contrastive signal exists (pre-flight, blocking)

The de-anchoring gradient comes from **POSITIVE `asked_for_different_artist` turns
whose GT is a different artist** — they let the model learn a negative weight on
`x_same_artist_wants_new`. The grade-0 negatives only *remove poison*; they
supply no gradient on their own (a group with no positive is inert in lambdarank).

Count, in train labels: among `asked_for_different_artist == true` turns, how many
are POSITIVE (GT = different artist, content-valid, liked) vs NEGATIVE-anchoring.
- If POSITIVE asked-different turns are plentiful → reranker re-label can learn
  de-anchoring. Proceed to Phase 1+2.
- If near-zero → the reranker has no contrast to learn from; pivot to the b1
  retriever retrain (the labels' intended target) instead. Stop and re-scope.

### Phase 1 — Anchor-aware eval (independent of training; build first)

Join the 7k dev labels by `sid, tn` to the devset predictions. Two metrics:

1. **Anchoring-violation rate@k** (primary). On `asked_for_different_artist`
   turns, fraction where the model's top-k contains the `just_played` artist —
   computed by the **deterministic catalog same-artist check on the model's recs**
   (not the LLM, not limited to the GT). Report @1 and @20. Lower = better.
2. **Cleaned-GT NDCG@20** (guard). Standard NDCG, but GT positives whose clean
   label is NEGATIVE (anchoring or content) are removed from the relevant set, so
   the model is not credited for surfacing the anchor on a pivot. Confirms we do
   not wreck legit turns.

New module under `evaluator/` (or `scripts/rerank/anchor_labels/`); reads
predictions + dev labels + catalog artist map. No GT-file change.

### Phase 2 — Reranker re-label (training)

Single insertion point: the relevance assignment, today `features_v9.py:345`
`"label": int(tid_ == gt)`.

- Join clean train labels by `sid, tn`. For a turn whose GT clean label is
  NEGATIVE (`artist_anchoring` OR `content_violation`), set the GT row's
  `label` 1 → **0** (grade-0; keep the row).
- Carry `confidence_weight` into the existing sample-weight path
  (`build_label_weights.py` already writes per-row weights — extend it to source
  the anchor-label weight, or multiply).
- No feature changes. `x_same_artist_wants_new` / `same_artist_as_abandoned`
  (train) and `wants_new` / `target_artist_mode` (inference proxy) already exist.

Then retrain via the existing local path (`train_v9.py` build → fold → finalize →
full_model) on the fresh lineage. $0 local.

### Data flow

```
anchor-labels-v1.1 (sid,tn → label, axes, confidence_weight)
  ├─ Phase 1 → join to devset preds → anchoring-violation rate + cleaned NDCG
  └─ Phase 2 → join to train feature parquet → GT label 1→0 on NEG turns
                 + confidence_weight as sample weight → retrain LambdaMART
                 → score with Phase-1 metrics + raw devset GT (for delta)
```

## Success criteria

- **Anchoring-violation@1 drops materially** vs the current reranker, AND
- **Cleaned-GT NDCG@20 holds or improves**.
- Raw GT NDCG@20 may dip (expected — raw GT is the biased metric). Report it but
  do not gate on it.

## Risks / open points

- **Contrastive volume (Phase 0 gate).** If few POSITIVE asked-different turns
  exist, reranker re-label can't learn de-anchoring → retriever retrain instead.
- **Grade-0 is inert per-turn.** Removes poison but adds no push; the win depends
  entirely on Phase-0 contrast. Documented; revisit by injecting a different-artist
  positive later (decision 1 keeps the door open).
- **Default-feature anchoring persists.** Even with clean labels, `b1_cos` /
  `artist_best_rank_in_union` still favor the anchor by default; the reranker may
  under-move. The labels' *intended* target is b1 — likely a phase-2 follow-up
  (retrain b1) for the full fix.
- **Inference proxy mismatch.** Training uses the LLM `asked_for_different_artist`;
  inference uses state `wants_new`/`target_artist_mode`. If these disagree often,
  the learned weight mis-fires. Quantify proxy agreement on dev.

## Out of scope (this spec)

- Retraining the b1 two-tower retriever (separate, larger effort).
- Injecting synthesized different-artist positives for grade-0 turns.
- Judging the model's own recs with the two-axis rubric (full re-judge NDCG).
