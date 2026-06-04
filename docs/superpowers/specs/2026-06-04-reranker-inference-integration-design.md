# LambdaMART Reranker — Inference Integration (Phase 2) — Design

> **Status:** design, ready for implementation review.
> **Goal:** Replace weighted RRF (`_rrf_fuse_weighted`) in the live v0+ compiler with the
> LightGBM LambdaMART reranker from `mcrs/rerank/`, trained on the **train** split, and report
> a leak-free devset number via `/run-experiment`.
> **Date:** 2026-06-04. **Branch:** `semih_reranker`.

## 1. Motivation

Phase 1 proved (out-of-fold, leak-free) that the reranker over the branch-pool union beats RRF
on devset by a large margin (NDCG@20 **0.325 vs 0.153**, +112%). That number came from session
GroupKFold OOF scoring — an *offline* evaluation. To actually **deploy** the reranker as the
compiler's final ranker and measure it through the real inference path, we need (a) a single
model trained on data disjoint from devset, and (b) the reranker wired into `_compile`.

## 2. Decisions (locked with user)

- **Methodology:** Phase 2 — train one model on the **train** split, deploy, evaluate on devset.
  This is the only honest "deployed model + valid devset number" (training on devset and
  evaluating on devset would be leakage).
- **Train scope:** the **full** train split (~15,199 sessions ≈ ~120k turns).
- **What the reranker replaces:** the `_rrf_fuse_weighted` + `_apply_soft_adjustments` stage.
  It **keeps** hard-drop (played/rejected removal — invalid recommendations) and popularity
  backfill to `final_topk`. RRF stays available behind a config flag (default).
- **No block G** (sentiment-split embeddings) — dropped in Phase 1 (negligible, redundant).

## 3. Train/serve parity (the linchpin)

The reranker must compute **identical features** offline (training) and online (serving), or the
deployed model sees a different distribution than it trained on. We guarantee this by sharing one
code path:

- `mcrs/rerank/features.py::features_from_frames(candidates, groups, catalog, meta)` — the single
  feature assembler (blocks A/A′/C/D/E/F). *(Implemented.)*
- Offline: `build_features` reads `candidates.parquet`/`groups.jsonl` → `features_from_frames`.
- Online: `mcrs/rerank/online.py::TurnReranker` builds the per-turn `candidates`/`groups` frames
  from one trace entry (reusing `build_dataset._parse_pools`, `_candidate_rows`,
  `build_group_record`) → same `features_from_frames`, with the 47k-row catalog metadata frame
  cached once on the ranker. *(Implemented.)*

The QU layer (`compiler_v0plus_qu.py:709-720`) already assembles each turn into the exact
`{state, resolver, resolved_targets, branches}` structure the offline pipeline consumes, so the
online path feeds the reranker that same structure.

**Parity gate:** `online.validate_parity` builds offline batch features and online per-turn
features for the same devset turns and asserts every feature column matches to < 1e-6.

## 4. Architecture / stages

**Stage 0 — Shared feature function.** *(Done.)* `features_from_frames` + `online.TurnReranker`.

**Stage 1 — Compiler integration.**
- New `mcrs/rerank/ranker.py` (or reuse `online.TurnReranker`): `rank(branch_pools, rs) → tids`.
- In `compiler_v0plus._compile()` replace lines ~697-703 when `cfg.ranker == "lambdamart"`:
  build the union from `named_pools` (requires `branch_trace_topk > 0`), build the per-turn
  feature frame via the shared path, score with the model, order by score → `ranked`. Then the
  existing hard-drop + `_backfill` to `final_topk` run unchanged.
- To avoid re-deriving state, factor the QU's `state`→`resolver` mapping
  (`compiler_v0plus_qu.py:690-720`) into a shared helper used by both the trace builder and the
  online ranker, so `_compile` can build the group record from `rs`/`state` in-process.
- **Config:** add `compiler.ranker: "rrf" | "lambdamart"` (default `rrf`) and
  `compiler.reranker_model_path`. `CompilerConfig` gains the two fields.

**Stage 1.5 — Cheap checkpoint (before any expensive run).** Validate the full integration on the
**existing** devset trace with a throwaway devset-trained model: confirm the compiler path runs,
orders sanely, and online features match offline (parity gate). Leakage ⇒ the number is not
reported; this only de-risks Stages 2-4.

**Stage 2 — Train-split retrieval pass (long pole).**
- Extend the harness to run inference over an arbitrary HF split (today `run_experiment.py:130`
  hardcodes `split="test"`): add a `train` path + a Modal `_inference_train` sharded function +
  `--eval_dataset train` plumbing. `make_ground_truth(split="train")` for labels.
- Run sharded on Modal over the full train split with `branch_trace_topk > 0`.
- **Trace format note:** the current harness writes traces as **JSONL** (`{tid}_trace.jsonl`),
  not the legacy single JSON array. `build_dataset.iter_trace` must accept JSONL (stream lines)
  in addition to the array form.

**Stage 3 — Train the deployable model.** `build_dataset` + `features` over the train trace; train
ONE LambdaMART model on all train turns (no CV — devset is the held-out report). New
`train.py --single` (or `train_full.py`) saves `model.txt` + `model.features.json`
(`feature_columns` for serve-time column order).

**Stage 4 — Package + devset run.** Add `lightgbm` to the Modal inference image; ship the model
file (Modal volume or image COPY). New config
`configs/v0plus_compiler_all_retrievers_reranked_devset.yaml` (= all_retrievers +
`ranker: lambdamart` + model path). `/run-experiment` sharded on devset → valid NDCG@20 vs RRF
0.1253.

## 5. Leakage guardrails

1. Model trained **only** on train-split turns; devset is the untouched report split.
2. Catalog popularity / cf_bpr are fixed catalog properties (same for both splits), not re-fit.
3. No GT-derived features (label is the training target only).
4. Parity gate ensures serve features == train features.

## 6. Components

| File | Change |
|---|---|
| `mcrs/rerank/features.py` | `features_from_frames()` *(done)* |
| `mcrs/rerank/online.py` | `TurnReranker`, `validate_parity` *(done)* |
| `mcrs/rerank/build_dataset.py` | accept JSONL traces; reusable `_parse_pools`/`_candidate_rows`/`build_group_record` *(reused)* |
| `mcrs/rerank/train.py` | `--single` full-train mode; persist `model.features.json` |
| `mcrs/qu_modules/compiler_v0plus.py` | `ranker` flag; reranker branch in `_compile`; shared state→record helper |
| `mcrs/qu_modules/compiler_v0plus_qu.py` | factor state→resolver mapping into shared helper |
| harness (`run_experiment.py`, `modal/app.py`, inference script) | train-split inference |
| `modal/app.py` image | add `lightgbm`; ship model file |
| `configs/…_reranked_devset.yaml` | new deploy config |

## 7. Verification

1. **Parity gate** — `online.validate_parity` < 1e-6 on devset turns.
2. **Checkpoint** — devset compiler run with a throwaway model produces sane orderings (Stage 1.5).
3. **Offline cross-check** — train-split OOF NDCG@20 sanity before deploying.
4. **Final** — `/run-experiment` devset with the train-split model; compare NDCG@20/Hit@20/MRR vs
   RRF 0.1253; expect a large lift consistent with the 0.325 Phase-1 OOF ceiling (devset is a
   different split from train, so the deployed number is an honest generalization estimate).

## 8. Risks

- **Cost/time:** the ~120k-turn train retrieval pass is ~15× the devset run (hours of Modal + API
  spend). Mitigated by doing all integration + the cheap checkpoint first.
- **Per-turn latency:** online feature build adds work per turn; the cached catalog meta + a
  vectorized single-group path keep it bounded. Measure in the checkpoint.
- **Modal packaging:** model file + `lightgbm` must be in the inference image/volume.

## 9. Out of scope

Re-tuning branch logic; block G; cross-encoder rerankers; blindset submission (separate step once
devset validates).
