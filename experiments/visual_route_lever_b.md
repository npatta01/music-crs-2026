# Issue #127 — Visual/Image Retrieval Route (Lever B): findings

- **Branch:** `claude/visual-route` (base commit `a329406`)
- **Date:** 2026-06-15
- **Lane:** P1 visual/image retrieval route (umbrella #130). Visual-gated; isolated
  from open-explore (#126), pivot (#125), reranker calibration (#128),
  candidate-surface/pool-depth (#129).

## TL;DR

Lever B — a **visual-gated SigLIP-2 text→cover-art dense branch** — improves
visual-slice retrieval **coverage** (+4.4pt union@1000) but delivers **zero
top-20 benefit** with the frozen v10 reranker. It is **shipped in the canonical
configs for the retrieval capability** (visual-gated, score-neutral on top-20);
converting that coverage into top-20 is a **reranker** change (#128), not a
retrieval one. Pool-position analysis shows why: the SigLIP branch's incremental
candidates land **too deep** (70% of its hits are beyond rank 100; ~37% beyond
rank 500), below the LGBM's `pool_k=500` scoring cutoff. The reranker is *not*
the weak link — **94% of visual GT that reaches the scorable pool makes top-20**.
The binding constraint is getting visual GT into the top-500 fused pool, and
SigLIP's text→cover-art alignment for music is too weak (standalone r@1000=0.21)
to do that. **The visual gap is retrieval-quality-limited, not reranker-limited.**

## What was built (all TDD-green on `claude/visual-route`)

- `DenseBranch.gated_on` (mcrs/qu_modules/compiler.py): a branch fires
  only when a named `RoutingTags` flag is true; gate-skips **before** the encode
  (no wasted RPC, no candidate injection on non-matching turns); fail-fast
  validation for typo'd gate names. Config parser forwards `gated_on`.
- **Enabled in all three canonical configs** (`state_ranker_v10_lgbm_devset`,
  `_blindset_A`, `_rrf_devset`): the `siglip2_text` encoder + a `query_id=visual_nl`
  dense branch on `image_siglip2`, `gated_on: image_or_visual_search`. Visual-gated
  — non-visual turns are unchanged. **Shipped as a retrieval capability** (see the
  Verdict below): it improves visual candidate coverage; top-20 is flat with the
  frozen reranker. (Note: the slice numbers below were measured with the
  original `query_id=visual` comma query; the shipped config uses `visual_nl`, the
  best-recall query from the query-formulation probe.)
- `run_experiment.py`: `--session_ids_file` now works on the **Modal** backend,
  including **sharded** runs (workers filter to the subset, then split it across
  shards). This made the 65-session run ~7.5 min (10 shards) vs ~16 min in a
  single container.
- Diagnostic tooling used for the analysis below — a paired visual-slice A/B (+
  non-visual regression guard), a GT-rank-by-stage pool tracer, and a Modal
  SigLIP query-variant probe — was exploratory and is **not committed** with the
  feature (the numbers here are the durable record).

## Result — paired sharded A/B, all 65 visual sessions / 253 visual turns

Both runs from this worktree, back-to-back, sharded (identical conditions).

| metric | baseline | treatment | Δ |
|---|---:|---:|---:|
| hit@20 | 0.4704 | 0.4704 | **+0.0000** |
| ndcg@20 | 0.3152 | 0.3152 | −0.0001 |
| mrr | 0.2713 | 0.2712 | −0.0001 |
| union@100 | 0.4704 | 0.4862 | **+0.0158** |
| union@1000 | 0.7589 | 0.8024 | **+0.0435** |

SigLIP visual branch fired on all **253** visual turns (standalone r@100=0.063,
r@1000=0.213). No regression on the 267 non-visual turns in these sessions
(gate inert there; residual −0.0013 ndcg is extractor nondeterminism, see below).

## Pool-position diagnostic — *why* coverage doesn't convert

SigLIP branch GT-coverage depth (treatment): covers GT on **54/253 (21%)** —
≤100: **16**, 101–500: **18**, 501–1000: **20** → 70% deeper than rank 100.

Treatment funnel (GT presence over 253 visual turns):

| stage | n | % |
|---|---:|---:|
| GT in any branch @1000 | 203 | 80.2% |
| GT in fused pool @500 (LGBM-scorable) | 127 | 50.2% |
| GT in LGBM top-20 | 119 | 47.0% |

- **LGBM is highly effective on in-pool GT: 119/127 = 94% reach top-20.** Not the
  weak link.
- **GT newly reachable via SigLIP** (absent from every baseline branch@1000):
  **11 turns**, all SigLIP-contributed → **0 reach top-20** (fusion-rank 501–1000
  or absent after fusion).
- **LGBM top-20 churn: +1 entered / −1 dropped** = net zero (pure churn).

Two compounding gates kill visual candidates:
1. ~20% of visual GT is unreachable by **any** branch@1000 (hard recall ceiling).
2. Of the reachable, **half fall below fusion-rank 500** → never scored by the
   LGBM (`pool_k=500`). SigLIP adds coverage but mostly stacks below this cutoff.

## Verdict: shipped as a retrieval capability; top-20 needs the reranker

The experiment finding stands: Lever B improves visual-slice union without
regression, but the competition scores top-20, where the gain is **zero** with
the frozen reranker.

**Decision (post-experiment): the branch was nonetheless enabled in the three
canonical configs.** Rationale: it is the architecturally-correct capability
(visual queries should hit the cover-art search), it is visual-gated (no
non-visual regression), and it stages the top-20 conversion — which is a reranker
change, not a retrieval one (add a `siglip_query_cos` feature so the reranker can
reward description→cover matches, then retrain; staged for #128). So it ships
**for coverage, score-neutral on top-20** until the reranker learns the signal.
Up-weighting SigLIP in fusion (Lever A) was not pursued — it would help only its
~16 shallow hits, most already covered by other branches.

## Pool-depth probe (#129 bridge): raising `pool_k` at inference BACKFIRES

Tested the natural hypothesis — "the deep visual candidates just need a bigger
scorable pool" — as a 2×2 over the 253 visual turns (baseline/visual × `pool_k`
500/1000, inference-only on the frozen v10 model):

| visual slice | pool_k=500 | pool_k=1000 | Δ |
|---|---:|---:|---:|
| baseline hit@20 | 0.4704 | 0.4387 | **−0.032** |
| baseline ndcg@20 | 0.3152 | 0.2767 | **−0.039** |
| visual hit@20 | 0.4704 | 0.4427 | −0.028 |
| visual ndcg@20 | 0.3152 | 0.2777 | −0.038 |

Raising `pool_k` 500→1000 **hurts** the visual slice (and overall LGBM h@20
0.552→0.535), consistently across both configs; union is unchanged. Most likely
the v10 LGBM was trained on a `pool_k=500` candidate distribution, so scoring
candidates 501–1000 at inference is **out-of-distribution** — it ranks deep
decoys highly and displaces good top-20 picks. So the cheap config-only
pool-depth lever is **negative**; a fair test needs a `pool_k=1000` **retrain**
(#129 **and** #128 together), not a config bump.

## Query-formulation probe (retriever play): wording is a small lever

Is the SigLIP query phrased right? A 6-example probe (a one-off Modal diagnostic,
ranking each GT cover in the full 46,485-cover space) suggested **bare visual
descriptors** (no `"album cover,"` frame, filler stripped) ranked GT 3–28×
higher than the current comma query. But **slice-scale validation (253 turns)
did not confirm it** — the probe was cherry-picked. Three query builders were
run on the full visual slice (`query_id` = `visual` / `visual_nl` / `visual_concrete`):

| query | SigLIP r@100 | SigLIP r@1000 | union@100 Δ | union@1000 Δ | hit@20 Δ |
|---|---:|---:|---:|---:|---:|
| `visual` (comma, current) | 0.063 | 0.213 | +0.016 | +0.044 | +0.000 |
| `visual_nl` (caption) | **0.083** | **0.257** | **+0.036** | +0.040 | +0.000 |
| `visual_concrete` (bare) | 0.075 | 0.198 | +0.020 | +0.028 | −0.000 |

- The **caption** query (`visual_nl`, NL framing + filler strip) is marginally
  the best *retriever* query — best branch r@100 and ~2× the comma query's
  union@100 lift. Bare descriptors (`visual_concrete`) were middling, **not** the
  probe-suggested winner.
- **Every wording is flat on top-20.** SigLIP branch recall is low across the
  board (r@100 ~0.06–0.08) — the cover-art text→image alignment for music is
  fundamentally weak, and no phrasing changes that.

Lesson: query wording is a small candidate-surface lever (caption best), not a
fix; aggregate-validate before trusting a few cherry-picked examples. The
embedding mechanics are correct (model matches catalog, `get_text_features`,
`padding=max_length` is the SigLIP convention, raw+cosine) — so this is content,
not a bug.

## Conversation-constraint cleaning (genre filter): does NOT help top-20

Tested whether stated conversational constraints can prune the noisy cover-art
pool before the reranker. Offline simulation over the 253 visual turns (genre
lexicon from the query, catalog `tag_list` filter on the LGBM pool):

- 54% of visual turns state a genre; 10% an era; 1% an artist.
- **32 addressable** (genre stated, GT in LGBM pool, GT currently rank >20).
- 29/32 — GT's tags match the stated genre (filter rarely drops GT).
- **0/32 move into top-20 after genre filtering** (3 false prunes).

Why: the decoys ranked above GT are **same-genre**, not cross-genre — for "heavy
metal, dark cover" the catalog has hundreds of metal tracks and GT is buried
among genre-matching ones. Filtering removes off-genre covers (which the reranker
— with genre soft-boost — already wasn't fooled by), so GT doesn't rise. The
visual gap is a *ranking* problem among same-genre plausible tracks, not a
cross-genre-noise problem. Branch boosting (`routing_boost`) likewise can't help
— up-weighting a weak, deep SigLIP signal only injects noise.

**Other constraints don't help either.** Of the 32 buried-GT turns: only 3 also
state an era, 0 a popularity word, 3 an explicit rejection (and rejections /
played tracks are *already* hard-dropped by the compiler). Visual turns carry
artist context ~1% of the time (covers are described, not attributed), so
"not-this-artist" exclusions aren't a visual lever (they belong to pivot #125).
Stacking genre+era surfaced **0/32** into top-20. Root reason: the user's
*discriminating* signal is the cover itself, which is not a metadata field — no
genre/era/popularity/exclusion filter can pick GT by its cover from same-genre
peers. Only the (weak) SigLIP embedding carries that signal.

## Pre-rerank candidate re-ordering (the one small positive — and its limits)

The reranker is 94% effective on GT that reaches its `pool_k=500` window, so the
question became: can we push GT into that window by re-weighting fusion?

- **Boost the played-covers branch** (`routing_boost: {image_or_visual_search: 2–3}`,
  visual-gated): hit@20 0.4704 → **0.4783 (+0.0079)** at 2× and 3×; ndcg/mrr rise
  with dose (3×: ndcg +0.0042, mrr +0.0036). Controlling for run drift (non-visual
  control fell ndcg −0.0044 / hit@20 −0.0112), the diff-in-differences is ~+0.019
  hit@20. **Small (~2–5 turns) and near the noise floor, but the only lever that
  moved top-20 the right way.** union unchanged → pure re-ordering, not recall.
- **Boost the cover-description (text) branch** (weight 2×): **flat** — promoting a
  weak branch just promotes its decoys.

## State signal audit — can anything clean/filter the recall? (no)

The compiled state is rich, but none of it surfaces GT:

- **artist references: 66% of visual turns** name artists (mostly `satisfied_prior`,
  `anchor_use=do_not_use`). But for the 30 buried-GT-with-artist turns, GT is in the
  co-listening (`cf_bpr`) top-100 only **10%** of the time and the played-cover
  top-100 **3%** — GT usually isn't *behaviorally* similar to the referenced
  artists (similar only in the user's eye, via the cover). Anchoring on them can't
  reach GT. (This is really pivot lane #125's signal anyway.)
- genre 54% / era 10% / popularity 0% / exclusion 1% — don't discriminate
  (same-category decoys) or are already applied.

**Root cause, final:** the user's only GT-distinguishing detail is the *cover*.
Every metadata signal names a *category with many members*; only the cover points
at GT, and the cover is (a) not in metadata (can't filter) and (b) encoded only by
the weak, fixed SigLIP space. So no state signal can clean the recall to surface GT.

## Where the real lever is (cross-lane)

- **Candidate-surface / pool-depth (#129):** the cheap inference `pool_k` bump is
  negative (above). A higher-pool gain, if any, requires retraining the reranker
  at that depth — combine with #128, not a standalone config change.
- **Reranker (#128):** a visual-branch feature only helps candidates already in
  the scorable pool; it cannot rescue the sub-500 / unreachable ones, and the
  pool-depth probe shows the frozen model degrades when simply shown more.
- **Stronger visual representation (most likely real lever):** SigLIP-2
  text→cover-art alignment for music is weak (r@1000=0.21) and its hits land
  deep. The fix is GT landing *shallow* (a better visual retriever), not more
  candidates or deeper scoring. The ~20% any-branch ceiling also needs this.

## Methodology notes

- **Pipeline nondeterminism noise floor ≈ 0.0013 ndcg.** Even in a paired run
  only 103/267 non-visual turns were byte-identical — the deepseek-v4-flash
  extractor is nondeterministic run-to-run. A/B deltas < ~0.005 ndcg are noise
  on this pipeline at devset scale.
- **Long single-container background runs were killed ~14–15 min in** (cause
  unconfirmed: harness background-timeout or memory pressure). Fix: shard so each
  run is short; the sharded 65-session run completed in ~7.5 min.
- Modal runs from a worktree use the **local worktree code** (`add_local_dir
  copy=True`), so this A/B genuinely exercised the gate + visual branch.

## Reproduce

The visual branch is now enabled in the canonical configs (`query_id=visual_nl`,
`gated_on: image_or_visual_search`). To re-measure the visual-slice A/B, compare
the shipped config (branch ON) against a branch-disabled baseline over the visual
sessions:

```bash
# branch ON (the shipped devset config), 65 visual sessions, sharded:
python run_experiment.py --backend modal --tid state_ranker_v10_lgbm_devset \
  --session_ids_file exp/subsets/visual_sessions.json --num_shards 10 --batch_size 8
# baseline (branch OFF): run the same on a config copy with the image_siglip2
# dense branch removed, then compare the two runs' visual-slice metrics
# (the diagnostic scripts used for this were exploratory and are not committed).
```

## Shipped config delta (added to each of the three canonical configs)

The `siglip2_text` encoder + visual branch added to
`state_ranker_v10_lgbm_devset.yaml`, `_blindset_A.yaml`, and `_rrf_devset.yaml`:

```yaml
# under qu_kwargs.encoders: (alongside qwen_0_6b / qwen_8b / clap_text)
    siglip2_text:
      backend: modal_multimodal
      modal_app_name: music-crs
      modal_cls_name: MultimodalTextEncoder
      method: embed_siglip_text

# under qu_kwargs.compiler.dense_branches: (after the sonic_nl branch)
    - vector_field: image_siglip2
      encoder_id: siglip2_text
      query_id: visual_nl
      weight: 1.0
      distance_type: cosine
      gated_on: image_or_visual_search   # fires only on visual turns
```
