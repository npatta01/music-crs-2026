# Retrieval Trace & Branch Diagnostics — Design

**Date:** 2026-06-01
**Status:** Approved (pending spec review)

## Goal

Instrument the v0+ retrieval pipeline so the per-branch candidate lists it
already computes (and currently discards) are persisted to disk, and add a
diagnostics tool that reports per-retriever recall plus richer coverage
metrics. This makes the pipeline **pickup-ready** for two future stages we are
*not* building now — reranking and explanation generation — by emitting the
artifacts those stages will need (the extracted state, already persisted today;
the per-branch generated candidates; the fused list; the final recommendation;
and the single headline track an explanation would target).

### Explicit non-goals

- No reranker model or rerank stage is built. We only persist the per-branch
  scored pools a reranker would consume.
- No explanation generator is built. We only persist `recommended.top1_track_id`
  (the headline track) as its target hook.
- No change to the submission / blindset output path or format.
- The evaluator git submodule is **not** modified.

## Background — current state

- `V0PlusCompiler.compile(rs, user_id)` (`mcrs/qu_modules/compiler_v0plus.py`)
  fuses BM25 + dense branches (e.g. `image_siglip2`) + centroid branches
  (`cf_bpr`, `user_cf_bpr`) via weighted RRF, applies soft (de)promotes, backfills
  to `final_topk` by popularity, and **returns a flat `list[str]`**. The
  per-branch pools (`bm25_hits`, `dense_branch_results`, `centroid_branch_results`)
  and the `fused` list exist only as locals and are discarded.
- `V0PlusCompilerQU` (`mcrs/qu_modules/compiler_v0plus_qu.py`) already builds a
  per-turn **trace** dict capturing the extracted `state`, resolver fields, and a
  compiler summary (counts only). Traces are stashed in `last_traces` and written
  to `exp/inference/devset/{tid}_trace.json` by `run_inference_devset.py`. The
  blindset/submission path does **not** write traces.
- The evaluator (`evaluator/metrics/metrics_recsys.py`, `evaluate_devset.py`)
  computes Recall@k / NDCG@k / "% GT not in top-k" over the **final fused** list
  only. It has no notion of per-branch contribution or a union-of-branches pool.

So "extracted state" is already persisted; the gap is the **per-branch candidate
lists**, the **fused** list, the **final** recommendation co-located in the trace,
and the **diagnostics** over them.

## Architecture (Approach C — structured internal result)

```
V0PlusCompiler._compile(rs, user_id) -> CompileResult        # NEW internal
   .ranked: list[str]                       # final top-1000 (unchanged output)
   .branch_pools: list[BranchPool]          # NEW — one per retriever branch that fired
        .name: str                          # stable branch name (see naming)
        .hits: list[tuple[str, float]]      # post-mask, post-hard-drop, top-1000 (id, score)
   .fused: list[tuple[str, float]]          # RRF output, pre-soft-adjust, top-1000
   .n_from_fusion: int                      # how many final ids came from the fused pool
   .n_from_backfill: int                    # how many came from popularity backfill

V0PlusCompiler.compile(rs, user_id) -> list[str]
   return self._compile(rs, user_id).ranked  # thin wrapper; submission path byte-identical

V0PlusCompilerQU._compile_one(...)           # devset path only
   res = compiler._compile(rs, user_id)
   trace["branches"] = { ...res... }         # attach pools + fused + final + recommended

run_inference_devset.py
   writes exp/inference/devset/{tid}_trace.json  (existing file; new "branches" key)

scripts/branch_diagnostics.py                # NEW standalone tool
   reads trace + ground truth -> per-branch recall + hit@k + unionhit@k report
```

**Why Approach C:** branch compilation runs off the event loop via
`asyncio.to_thread`, and the QU fans branches/turns out concurrently. A
side-effect attribute (`self.last_branch_pools`) would be a shared-state hazard
under that fan-out. Returning a `CompileResult` value is thread-safe, needs no
config flag, and keeps the public `compile()` output identical. The per-branch
pools are already locals, so the only added cost is *retaining* them, incurred
only on the devset path that reads them.

### Branch naming (stable keys)

| Source | Name in trace |
|---|---|
| BM25 multi-field query | `bm25` |
| Dense branch on vector field `F` | `dense:F` (e.g. `dense:image_siglip2`) |
| Centroid branch (anchor source) on field `F` | `centroid:F` (e.g. `centroid:cf_bpr`) |
| Centroid branch (user source) on field `F` | `centroid_user:F` (e.g. `centroid_user:user_cf_bpr`) |

A branch that does not fire on a turn (e.g. a centroid branch skipped for lack of
anchors) is **omitted** from `branch_pools` — not emitted empty — so diagnostics
can distinguish "fired but missed" from "did not fire."

## Trace schema additions

One new top-level key, `branches`, per turn record. All existing keys (`idx`,
`intent_mode`, `state`, `resolver`, `compiler`) are unchanged.

```jsonc
"branches": {
  "depth": 1000,                              // top-N stored per branch
  "pools": [
    { "name": "bm25",
      "hits": [["tk_8821", 14.2], ["tk_0034", 12.9], ...] },   // [track_id, score]; rank = index
    { "name": "dense:image_siglip2", "hits": [["tk_5500", 0.81], ...] },
    { "name": "centroid:cf_bpr",     "hits": [["tk_1190", 0.77], ...] }
    // branches that did not fire are omitted
  ],
  "fused": [["tk_8821", 0.0163], ...],        // RRF scores, pre-soft-adjust, top-1000
  "final": {                                   // the full diagnostic recommendation pool
    "track_ids": ["tk_8821", "tk_0034", ...], // post soft-adjust + backfill, top-1000, returned order
    "n_from_fusion": 612,
    "n_from_backfill": 388
  },
  "recommended": {
    "top1_track_id": "tk_8821"                // headline rec; explanation target; == final.track_ids[0]
  }
}
```

Notes:
- `hits` are branch-native raw scores (BM25 score, cosine sim) — real signal for a
  future reranker; the diagnostics tool only needs id ordering.
- Funnel is fully visible: **per-branch pools → fused → final (top-1000 pool) →
  recommended (top-1 headline)**. Any user-facing top-k (incl. top-20) is
  `final.track_ids[:k]`; `recommended.top1_track_id` is the headline track.
- Devset-only and JSON; ~4 branches × 1000 × up to 8 turns per session. Accepted.

## Diagnostics script

`scripts/branch_diagnostics.py` — standalone; does not touch the evaluator submodule.

```bash
python scripts/branch_diagnostics.py \
  --trace exp/inference/devset/{tid}_trace.json \
  --ground-truth evaluator/exp/ground_truth/devset.json \
  [--out exp/diagnostics/devset/{tid}.json]   # optional JSON dump; always prints a table
```

Single GT track per turn, so recall@k = hit@k = 1 iff GT ∈ set.

| Metric | Definition | Measured against |
|---|---|---|
| `hit@1` | GT == headline rec | `recommended.top1_track_id` |
| `hit@{20,50,100,200,1000}` | GT in top-k of the final recommendation | `final.track_ids` |
| `unionhit@{20,50,100,200}` | GT in the union of every branch's top-k | `∪ pools[*].hits[:k]` |
| `recall@{100,200,1000}` per branch | GT in that branch's top-k | each `pools[i].hits` |
| `union_size@{20,50,100,200}` | mean distinct candidates in the union | `pools` |
| `fusion_efficiency@k` | `hit@k(final) / unionhit@k` | reachable recall fusion+backfill keeps |

- Turn alignment: trace turns are matched to GT by `session_id` + turn index.
- Per-branch recall denominator = turns the branch **fired**; the fired-count is
  reported alongside each branch so the numbers are honest (a branch that fires
  rarely but hits often is not flattered).
- Output: printed table (per-branch recall rows + union/final columns) and the
  optional JSON dump.

### Error handling

- Trace lacking a `branches` key (non-v0+ run, or pre-change run): report clearly
  and exit non-zero rather than emitting zeros.
- Missing GT for a session/turn: skip that turn, report the skipped count.
- Empty `pools` on a turn (all branches skipped, e.g. extractor returned None):
  counted as a non-firing turn for every branch; still contributes to `final`/
  `recommended` hit metrics if a final list exists.

## Testing

- `_compile()` returns populated `branch_pools`, `fused`, `final`,
  `n_from_fusion`/`n_from_backfill` on a tiny synthetic catalog.
- `compile()` output equals `_compile(...).ranked` (submission path unchanged).
- Branches that don't fire are omitted from `branch_pools` (assert a skipped
  centroid branch is absent, not empty).
- Fixture trace + fixture GT through `branch_diagnostics.py` asserting known
  `hit@k`, `unionhit@k`, and per-branch recall values, including the
  fired-count denominator behavior.
- Diagnostics script exits non-zero and reports clearly on a trace with no
  `branches` key.

## Files touched

- `mcrs/qu_modules/compiler_v0plus.py` — add `CompileResult` + `BranchPool`
  dataclasses, `_compile()`, retain pools; `compile()` becomes a thin wrapper.
- `mcrs/qu_modules/compiler_v0plus_qu.py` — attach `branches` to the per-turn trace.
- `scripts/branch_diagnostics.py` — NEW standalone diagnostics tool.
- `tests/` — new unit tests as above.
- `docs/evaluation.md` — document the new trace `branches` key and the diagnostics
  script (the metrics there describe the evaluator; this is an adjacent tool).
```
