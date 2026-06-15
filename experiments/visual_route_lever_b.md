# Issue #127 — Visual/Image Retrieval Route (Lever B): findings

- **Branch:** `claude/visual-route` (base commit `a329406`)
- **Date:** 2026-06-15
- **Lane:** P1 visual/image retrieval route (umbrella #130). Visual-gated; isolated
  from open-explore (#126), pivot (#125), reranker calibration (#128),
  candidate-surface/pool-depth (#129).

## TL;DR

Lever B — a **visual-gated SigLIP-2 text→cover-art dense branch** — improves
visual-slice retrieval **coverage** (+4.4pt union@1000) but delivers **zero
top-20 benefit** with the frozen v10 reranker, and is **not worth shipping
alone**. Pool-position analysis shows why: the SigLIP branch's incremental
candidates land **too deep** (70% of its hits are beyond rank 100; ~37% beyond
rank 500), below the LGBM's `pool_k=500` scoring cutoff. The reranker is *not*
the weak link — **94% of visual GT that reaches the scorable pool makes top-20**.
The binding constraint is getting visual GT into the top-500 fused pool, and
SigLIP's text→cover-art alignment for music is too weak (standalone r@1000=0.21)
to do that. **The visual gap is retrieval-quality-limited, not reranker-limited.**

## What was built (all TDD-green on `claude/visual-route`)

- `DenseBranch.gated_on` (mcrs/qu_modules/compiler_v0plus.py): a branch fires
  only when a named `RoutingTags` flag is true; gate-skips **before** the encode
  (no wasted RPC, no candidate injection on non-matching turns); fail-fast
  validation for typo'd gate names. Config parser forwards `gated_on`.
- **Experiment config (not committed to `configs/`** — kept off the canonical
  3-config surface per the prune-first posture). It is the lgbm devset baseline
  plus the `siglip2_text` encoder and a `query_id=visual` dense branch on
  `image_siglip2`, `gated_on: image_or_visual_search`. Recreate it from the
  snippet at the end of this report to reproduce or extend (#129).
- `run_experiment.py`: `--session_ids_file` now works on the **Modal** backend,
  including **sharded** runs (workers filter to the subset, then split it across
  shards). This made the 65-session run ~7.5 min (10 shards) vs ~16 min in a
  single container.
- Tooling: `scripts/compare_visual_slice.py` (paired visual-slice A/B +
  non-visual regression guard), `scripts/visual_pool_position.py` (GT
  rank across branches / fusion / LGBM).

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

## Verdict: necessary-not-sufficient — do **not** ship alone

By the issue's success rule Lever B improves visual-slice union without
regression, but the competition scores top-20, where the gain is **zero** with
the frozen reranker. Up-weighting SigLIP in fusion (Lever A) would help only its
~16 shallow hits, most already covered by other branches — so it is not pursued.

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

Is the SigLIP query phrased right? A 6-example probe (`modal/app.py::probe_visual`,
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

First recreate the experiment config (see snippet below) at
`configs/state_ranker_v10_lgbm_devset_visual.yaml` (it is intentionally not
committed — kept off the canonical 3-config surface). Then:

```bash
# 65 visual sessions, sharded, from claude/visual-route:
python run_experiment.py --backend modal --tid state_ranker_v10_lgbm_devset \
  --session_ids_file exp/subsets/visual_sessions.json --num_shards 10 --batch_size 8
python run_experiment.py --backend modal --tid state_ranker_v10_lgbm_devset_visual \
  --session_ids_file exp/subsets/visual_sessions.json --num_shards 10 --batch_size 8
python scripts/compare_visual_slice.py --baseline-preds ... --treatment-preds ... \
  --baseline-trace ... --treatment-trace ... --ground-truth exp/ground_truth/devset.json \
  --sessions-file exp/subsets/visual_sessions.json
python scripts/visual_pool_position.py --baseline-trace ... --treatment-trace ... \
  --ground-truth exp/ground_truth/devset.json --sessions-file exp/subsets/visual_sessions.json
```

## Experiment config (delta vs `configs/state_ranker_v10_lgbm_devset.yaml`)

Copy the lgbm devset config to `configs/state_ranker_v10_lgbm_devset_visual.yaml`
and apply these two additions:

```yaml
# under qu_kwargs.encoders: (alongside qwen_0_6b / qwen_8b / clap_text)
    siglip2_text:
      backend: modal_multimodal
      modal_app_name: music-crs
      modal_cls_name: MultimodalTextEncoder
      method: embed_siglip_text

# under qu_kwargs.compiler.dense_branches: (append after the sonic_nl branch)
    - vector_field: image_siglip2
      encoder_id: siglip2_text
      query_id: visual
      weight: 1.0
      distance_type: cosine
      gated_on: image_or_visual_search    # fires only on image_or_visual_search turns
```

