# Union-pool reranker eval harness (issue #95)

**Date:** 2026-06-03
**Issue:** [#95 — does an LLM ranker actually improve ranking?](https://github.com/npatta01/music-conversational-music-recomender-2026/issues/95)
**Status:** design approved, pending implementation plan

## Problem

`v0plus_compiler_all_retrievers_devset` finds the right track *somewhere* far
more often than it ranks it near the top. The question this work answers is
narrow and clean:

> When the correct track is already in our candidate pool, can an LLM ranker
> move it up into the top 20 — beating today's fixed RRF fusion?

We isolate the ranker from retrieval by scoring **only on turns where the GT is
already in the pool** (the "playable" subset). Retrieval is held fixed, so any
metric delta is pure ranking quality.

## Measured prize (already run, `all_retrievers` devset, 8000 turns)

`scripts/branch_diagnostics.py` on the devset trace produced:

| Metric | Value | Reading |
|---|---:|---|
| hit@20 (GT in final top-20) | **0.274** | what we ship today |
| unionhit@20 (GT in union@20 pool) | **0.477** | ceiling if ranker were perfect @20 |
| hit@100 (GT in final top-100) | **0.471** | |
| unionhit@100 (GT in union@100 pool) | **0.662** | recall ceiling for a future @100 funnel |
| fusion_efficiency@20 = hit@20 / unionhit@20 | **0.574** | RRF drops ~43% of already-in-pool answers out of top-20 |
| fusion_efficiency@100 | **0.711** | even at 100, RRF loses ~29% of union-reachable GTs |
| mean union@20 size | **160** | (issue guessed 40–100; real is 160 — favors pointwise / sliding-window listwise) |
| mean union@100 size | **783** | |

**Decision gate passes:** unionhit@20 (0.477) ≫ hit@20 (0.274). Closing that gap
takes Hit@20 from 0.274 toward 0.477 — ≈ +0.20 absolute / +74% relative — with
no retrieval change.

## Architecture

One new orchestrator script, `scripts/rank_eval_union_pool.py`, plus a thin
listwise ranker module (`scripts/listwise_ranker.py`) added in Phase 2. The
script is a **pure offline replay**: reads the existing trace + GT, builds the
candidate pool from saved branch pools, applies a ranker, and scores. No
re-inference, no retrieval changes.

It composes existing pieces rather than reimplementing them:

- `scripts/branch_diagnostics.py` → `union_at_k`, `_branch_topk_ids`,
  `load_ground_truth_file`, `iter_trace` (streaming — the trace is 5.1G and
  will not fit in memory).
- `scripts/rerank_offline.py` → `build_query_structured`, the catalog
  `track_text` dict builder, and the history-metadata dict.
- `mcrs/qu_modules/cross_encoder_reranker.py` →
  `DeepInfraRerankerBackend.score(pairs)` for the hosted pointwise Qwen3-Reranker.

A `--num-sessions N` slice flag drives staged cost control (see Phasing). The
harness is deterministic over whatever session set it is given — the smoke slice
and the full run use identical code.

### Confirmed data shapes (from the trace)

- `trace.branches.pools` = `[{name, hits: [[track_id, score], …]}]`, 1000 hits/branch.
- `trace.branches.fused` = `[[track_id, rrf_score], …]`, length 1000 — the RRF order.
- `trace.branches.final.track_ids` = length 1000 — what ships.
- `trace.state` carries `turn_intent`, `mentioned_entities`, `process_constraints`;
  `trace.resolver.played_track_ids` is the canonical played history.

## Components

### Pool construction & playable subset

For each turn (streamed), for each `k ∈ {20, 100}`:

1. `pool = union_at_k(branches, k)` — dedup union of every branch's top-k.
2. **Playable filter:** keep the turn only if `GT ∈ pool`. Other turns are
   retrieval misses no ranker can fix — excluded from ranking metrics but
   counted (playable fraction == unionhit@k).
3. Three orderings of the **same pool**, scored identically:
   - **RRF baseline** — `fused` order restricted to pool members (ships today).
   - **Ranker** — pointwise or listwise reordering.
   - **Perfect-rank oracle** — GT forced to rank 1; the achievable ceiling and a
     sanity check (Hit@20 on playable == 1.0 by construction).

### Rankers (shared `rank(pool, query, state) -> ordered_ids` interface)

- **RRF** (baseline, free) — restrict `fused` to the pool.
- **Pointwise Qwen3-Reranker** (Phase 1) — `query = build_query_structured(state,
  history)`; `docs = [track_text(t) for t in pool]`; `scores =
  DeepInfraRerankerBackend.score(pairs)`; sort descending. Reuses the existing
  backend; no new model code.
- **Listwise** (Phase 2, hand-rolled — "approach A") — new
  `scripts/listwise_ranker.py`: RankGPT-style sliding window (window 20, stride
  10) over the OpenRouter/litellm client the extractor already uses. Model is a
  `--listwise-model` slug so cheap→expensive is a one-flag sweep. Robust parser
  that falls back to input order on malformed output. Chosen over the `rank_llm`
  package (issue's literal suggestion) to keep the deliverable dependency-light
  (rank_llm pulls torch/vllm and assumes HF/vllm-hosted weights) and to match the
  repo's existing hosted-LLM call conventions.

### Metrics & output

Computed **on the playable subset only**, per k, per ranker:

- **Hit@1, Hit@20, MRR, NDCG@20** (NDCG@20 is the headline).
- Report **n_playable** (subset size) and **mean pool size** for interpretability.
- Output: compact JSON at `exp/inference/devset/rank_eval_union_pool_{k}.json`
  plus a printed table (RRF vs pointwise vs listwise vs oracle), in the
  `branch_diagnostics` report style.
- **Win condition:** ranker NDCG@20 > RRF NDCG@20 on the same turns / same
  candidates. Retrieval is fixed, so any delta is pure ranking quality.

## Phasing (with cost gates)

- **Phase 1 — harness + pointwise, smoke slice.** Build the script; run RRF +
  pointwise + oracle on `--num-sessions 10–25`, k=20. **Gate:** does pointwise
  beat RRF? Report the slice table.
- **Phase 2 — scale pointwise + add listwise.** On go-ahead: full playable
  subset for pointwise (k=20 and k=100); wire listwise (approach A), smoke-slice
  it, then scale. **Gate:** listwise vs pointwise vs RRF.
- **Phase 3 (out of scope, noted only).** If a ranker wins, a follow-on
  GBM/LambdaMART (LambdaMART, `objective="lambdarank"`) pre-filter feeds the LLM
  ranker; its recall target is the measured unionhit@100 = 0.662.

## Cost control

- Pointwise at full scale ≈ 160 candidate-scorings × ~3,800 playable turns ≈
  600k paid DeepInfra pairs; listwise hits OpenRouter per turn. Both cost real
  money, so every phase smoke-tests a ~10–25 session slice, reports, and waits
  for go-ahead before scaling (matches the project's standing Modal/full-devset
  rule).

## Non-goals

- No retrieval changes, no re-inference, no changes to the live pipeline or
  `post_fusion_features.py`.
- No GBM/LambdaMART stage (Phase 3 follow-on, separate issue).
- `rank_llm` package integration (explicitly rejected in favor of approach A).
