# Anchor-clean labels: fair eval + de-anchored reranker

Fixes the reranker **anchoring bug** (on a "give me a *different* artist" turn it
ranks the just-played artist #1) by fixing the **training objective** with clean
LLM-judged labels, plus a complementary post-rerank reorder. Includes a fair
**anchor-aware metric** that raw-GT NDCG cannot express.

Design spec: [`docs/superpowers/specs/2026-06-29-anchor-clean-labels-reranker-design.md`](superpowers/specs/2026-06-29-anchor-clean-labels-reranker-design.md).

## Why raw GT is the wrong scoreboard

The raw GT is the synthetic next-track; on pivot turns it is frequently the same
artist. `anchor-labels-v1.1` finds **5,880 train turns** where the synthetic
reaction was "MOVES" (liked) on an anchoring track right after the listener asked
for someone else — poisoned positives that *teach the model to anchor*. So a
correct de-anchoring change *loses* on raw GT (fix1 was −0.0105 ndcg@20) while
being right for the user. SHAP on a blind-B case showed the drivers are
`artist_best_rank_in_union` and `b1_cos` (both favor the anchor because the
session reference *is* that artist); the model already has the pivot cross
`x_same_artist_wants_new` but weights it ~0 — because the labels reward anchoring.

## Two tools (this PR)

1. **Anchor-aware eval** — `scripts/rerank/anchor_labels/anchor_aware_eval.py`
   (joins clean dev labels by `sid,tn`):
   - `anchoring_violation_rate@k`: among `asked_for_different_artist` turns, the
     fraction whose top-k repeats the `just_played` artist (deterministic catalog
     name match on the model's recs). Lower = better.
   - `cleaned_ndcg@k`: single-gold NDCG over turns whose clean label is **not** a
     NEGATIVE (anchoring/content) — guards the legit turns.
2. **Re-label transform** — `scripts/rerank/anchor_labels/anchor_relabel.py`:
   joins clean labels into the reranker feature parquet and flips the GT positive
   (`label` 1→0, grade-0, rows kept) on NEGATIVE turns (`artist_anchoring` and
   `content_violation`); folds `confidence_weight` into the per-turn label weight.
   The existing `x_same_artist_wants_new` cross then gets a real (negative)
   gradient from the **4,660** POSITIVE different-artist pivot turns.
3. **Pivot reorder** — `supply_gated_pivot_reorder` in
   `mcrs/qu_modules/lgbm_reranker.py` (config `qu_kwargs.ranking.pivot_demote_*`,
   default off): post-rerank, demote blocked-artist (rejected ∪ played) tracks
   below non-blocked within the top window, only when ≥ `min_alternatives` exist;
   never removes a track. Runs before the rescue/guard finalize pass.

## Results — devset, held-out (OOF: each turn scored by the fold that didn't train on it)

5,288 held-out turns, 1,035 measurable pivots.

| config | viol@1 | viol@5 | viol@20 | cleaned-NDCG@20 |
|---|---|---|---|---|
| baseline (matched ctrl) | 0.626 | 0.759 | 0.850 | 0.2373 |
| + pivot reorder (fix1) | 0.375 | 0.543 | 0.850 | 0.2353 |
| cleaned-label retrain | 0.549 | 0.729 | 0.828 | 0.2361 |
| **cleaned + reorder** | **0.283** | **0.457** | **0.828** | 0.2329 |

- The two mechanisms are **complementary**: the reorder is sharp at the top
  (@1/@5) but cannot move @20 (reorders within the window); the cleaned model is
  the only thing that moves @20 (demotes the anchor deeper). Stacked, anchoring at
  rank-1 drops **63% → 28% held-out**, ~free on the fair NDCG (−0.004).
- **Synergy:** the reorder on the cleaned base (0.283) beats it on the ctrl base
  (0.375) — the cleaned model surfaces more non-anchor alternatives for the
  supply-gate to promote.

### Caveats
- **In-sample inflates the model effect.** Full-model devset eval (model trained
  on devset) showed viol@1 −0.159; **held-out it is −0.077**. Use the held-out
  numbers. The reorder is a deterministic rule, so its effect generalizes fully.
- **Raw GT dips, by design.** Cleaned-model raw GT ndcg@20 −0.037 (concentrated on
  the poisoned turns whose anchor gold we stopped chasing); the reorder adds ~−0.01.
  cleaned-NDCG (poison excluded) stays flat — the legit turns are unharmed.
- The reranker trains on devset via user-grouped CV + lockbox; **blind-set is the
  true test** but has no anchor labels, so held-out dev OOF is the validation set.

## Reproduce

```bash
# 0. clean labels
gh release download anchor-labels-v1.1 --repo npatta01/music-conversational-music-recomender-2026 \
  --pattern 'dev_labels_full.jsonl.gz' --dir cache/anchor_labels_v1_1

# 1. re-label the reranker feature parquet (devset lineage) + weights
python scripts/rerank/anchor_labels/anchor_relabel.py \
  --features-src exp/analysis/rerank/v10/features_fresh \
  --features-dst rerank_local/features_cleaned \
  --labels cache/anchor_labels_v1_1/dev_labels_full.jsonl.gz \
  --weights-src exp/analysis/rerank/v10/label_weights_fresh.parquet \
  --weights-dst rerank_local/label_weights_cleaned.parquet

# 2. retrain (build -> fold 0..4 -> full_model), assemble bundle (model.txt, meta.json,
#    cat_maps.json, branch_names.json), see docs/reproduce_reranker.md.

# 3. score: devset inference with MCRS_MODEL_DIR=<cleaned bundle>; enable the reorder
#    via qu_kwargs.ranking.pivot_demote_enabled: true (min_alternatives 2, window 20).

# 4. anchor-aware eval
python scripts/rerank/anchor_labels/anchor_aware_eval.py \
  --predictions <preds.json> \
  --dev-labels cache/anchor_labels_v1_1/dev_labels_full.jsonl.gz \
  --ground-truth exp/ground_truth/devset.json --catalog-db-uri cache/lancedb
```

## Next

- Apply the same clean labels to the **b1 two-tower retriever** (the labels'
  intended target; the SHAP root driver) — upstream of the reranker.
- Blind-set qualitative check of the de-anchored config.
- Revisit grade-0 → inject a different-artist positive for the flipped turns.
