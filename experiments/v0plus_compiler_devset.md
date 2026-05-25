# `v0plus_compiler_devset` — full devset run

**Status:** `analyzed`
**Date:** 2026-05-25
**Config:** [`configs/v0plus_compiler_devset.yaml`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/configs/v0plus_compiler_devset.yaml)
**Pipeline:** Full v0+ ConversationState extractor → resolver → compiler. First end-to-end production run of the v0+ compiler on the full 1000-session devset.

## Headline metrics (1000 sessions × 8 turns)

Macro avg, turn-then-session, full-pool rows only (7964 / 8000 = 99.55%):

| Metric | Value |
|---|---|
| **NDCG@20** (competition target) | **0.1005** |
| **Hit@20** | **0.2378** |
| Hit@1 | 0.0257 |
| Hit@5 | 0.0971 |
| Hit@10 | 0.1567 |
| Hit@50 | 0.3443 |
| Hit@100 | 0.4101 |
| Hit@1000 | 0.5780 |
| MRR | 0.0676 |
| Mean rank when found | 133 |
| Median rank when found | 31 |
| Empty predictions | 2 / 8000 (0.03%) |
| Shallow rows (<1000 pool) | 34 / 8000 (0.42%) |

## vs BM25 baseline ([`lancedb_fts_with_tag_list_devset`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/lancedb_fts_with_tag_list_devset.md))

| Metric | BM25 | v0+ | Relative |
|---|---|---|---|
| **NDCG@20** | 0.0739 | **0.1005** | **+36.0%** |
| **Hit@20** | 0.1929 | **0.2378** | **+23.3%** |
| Hit@1 | 0.0091 | 0.0257 | +181.7% |
| Hit@100 | 0.3149 | 0.4101 | +30.2% |
| Hit@1000 | 0.4824 | 0.5780 | +19.8% |
| MRR | 0.0445 | 0.0676 | +52.0% |

v0+'s advantage compounds with conversation depth (per-turn Hit@20):

| Turn | BM25 | v0+ | Δ |
|---|---|---|---|
| 1 | 0.213 | 0.229 | +7% |
| 2 | 0.303 | 0.334 | +10% |
| 3 | 0.219 | 0.277 | +27% |
| 4 | 0.209 | 0.254 | +21% |
| 5 | 0.173 | 0.234 | +35% |
| 6 | 0.148 | 0.213 | +44% |
| 7 | 0.144 | 0.189 | +31% |
| 8 | 0.134 | 0.173 | +29% |

v0+'s multi-turn state (anchor track feedback, explicit rejections, intent_mode, hard filters) is doing real work — BM25 has no memory of prior turns.

## vs v0+ design target

| Metric | Design target | This run | Gap |
|---|---|---|---|
| NDCG@20 | ≥ 0.1092 | 0.1005 | -8% |
| Hit@1000 (offline RRF union ceiling) | 0.7210 | 0.5780 | -16% |

Within striking distance on NDCG@20; the gap is closable with one of: per-artist diversity cap, CF (`cf_bpr`) branch, or cross-encoder rerank.

## What was built in this session

This run is the culmination of a 9-task migration + 4-stage ablation campaign:

### 1. LanceDB-as-source-of-truth migration

Implementation plan: [`docs/superpowers/plans/2026-05-25-lancedb-as-catalog-source-of-truth.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/docs/superpowers/plans/2026-05-25-lancedb-as-catalog-source-of-truth.md).

| Layer | Before | After |
|---|---|---|
| `HardFilter` schema | `value: str \| list[str]` (overloaded) | `start: date \| None, end: date \| None` (typed) |
| Filter `between` value form | Pydantic accepts both list and string; catalog code only handles list → **silent empty filter mask** | One canonical typed form; year-only / year-month auto-expanded by Pydantic validator |
| Production catalog source | `HFTalkPlayCatalog.from_hf()` (duplicate of LanceDB) | `LanceDbCatalog` (reads from the same LanceDB used for retrieval) |
| LanceDB `release_date` storage | `string` | `pyarrow.date32()` with null on empty/malformed |
| Per-turn observability | `predicted_track_ids` only | `predicted_track_ids` + `_trace.json` sidecar (extracted state, resolver counts, compiler counts) |
| Modal inference fan-out | 1 container, all sessions | `run_inference_sharded` over N parallel containers (5 = ~6× wall-time speedup) |

### 2. Bug fix: silent `between` filter

Pre-migration, 9 of 160 turns in a 20-session smoke test (5.6%) returned empty predictions. Root cause: the LLM emitted `value: "2010-01-01, 2013-12-31"` (string) but `HFTalkPlayCatalog.release_date_filter_mask` only handled the list form, silently returning `set()`. The migration eliminated the silent path entirely.

Post-migration 20-session smoke: **0 of 160 empties** (verified).

### 3. Bug fix: `explicit_rejections` ignored by compiler

The resolver translates `state.explicit_rejections` into `rs.resolved_rejections: dict[int, ResolvedRejection]` with both `artist_ids` and `track_ids` per rejection — but the compiler's `_apply_soft_adjustments` only built `rejected_artist_ids` from `state.track_feedback` and **completely ignored `rs.resolved_rejections`**. A test (`test_compiler_hard_drops_resolved_artist_rejections`) was authored expecting hard-exclude semantics but passing for the wrong reason.

Fix at [`mcrs/qu_modules/compiler_v0plus.py:_apply_soft_adjustments`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/qu_modules/compiler_v0plus.py): tracks matching `rs.resolved_rejections.*.track_ids` are dropped entirely; tracks whose artist matches `rs.resolved_rejections.*.artist_ids` are dropped entirely. Soft demote via `same_artist_demote` retained only for `track_feedback`-inferred rejections.

Impact: pivot subset Hit@20 from 0.126 → 0.201 (+60% on the cohort). Macro flat because pivot is 2% of turns.

### 4. Ablation campaign

| Knob | Original | Tried | Picked | Reason |
|---|---|---|---|---|
| `enable_dense` | true | true, **false** | **false** | NDCG@20 +15% with sparse-only — Qwen3 dense branches blurred exact-match precision |
| `centroid_alpha.refinement` | 0.40 | 0.15, **0.30** | **0.30** | 0.15 was overcorrection (lost mid-pool); 0.30 is middle ground |
| `centroid_alpha.playlist_build` | 0.50 | 0.15, **0.30** | **0.30** | same |
| `same_artist_demote` | 0.70 | **1.0** | **1.0** | Variable applies only to soft path now; explicit rejections moved to hard-exclude |
| `max_in_flight` | 8 | 8, 32, **8** | **8** | 32 cold-cache triggered OpenRouter `gemma-3-12b-it` 429s |

## Architecture in this run

```
Conversation turn
  ↓
Gemma-3-12b-it via OpenRouter (LiteLLM disk cache on Modal volume)
  ↓ → ConversationStateV0Plus (typed Pydantic)
       intent_mode, mentioned_entities, track_feedback,
       referenced_track_ids, hard_filters[start,end], explicit_rejections, turn_intent
  ↓
V0PlusResolver (fuzzy match against LanceDbCatalog)
  ↓ → ResolvedConversationState
       resolved_rejections, track_feedback_artist_ids, played_track_ids
  ↓
V0PlusCompiler
  ├ Pre-fusion mask: release_date hard_filters (date32 comparison via LanceDbCatalog)
  ├ Sparse branches: BM25 across {track_name, artist_name, album_name, tag_list}
  ├ Dense branches: DISABLED (enable_dense=false in this run)
  ├ Soft adjustments:
  │   - rejected_tag_multiplier on tag overlap
  │   - positive_tag_multiplier_step on tag overlap
  │   - HARD-EXCLUDE tracks matching rs.resolved_rejections
  │   - soft demote on track_feedback-inferred artists (same_artist_demote=1.0 = noop)
  └ RRF fusion + top-1000 truncation
  ↓
1000 track_ids per turn + trace (saved to {tid}_trace.json)
```

## Failure analysis

Trace + sample CSV joined for the full devset. Key cohort splits:

### Same-artist continuation vs novel-artist (the dominant pattern)

| Cohort | n | Hit@20 | Hit@100 | NDCG@20 |
|---|---|---|---|---|
| GT artist is in prior plays | 3,014 (38%) | **0.488** | **0.816** | 0.198 |
| GT artist is NEW | 4,950 (62%) | **0.086** | **0.163** | 0.041 |
| All | 7,964 | 0.238 | 0.410 | 0.101 |

**The biggest single bottleneck.** The dataset awards a novel-artist GT 62% of the time, and our system — anchored on accepted tracks via `mentioned_entities`, anchor centroid (when dense is on), and BM25 boost on artist_name — implicitly assumes continuation. Same-artist Hit@20 is 0.49 (excellent); novel-artist Hit@20 is 0.09 (poor).

Hit@100 on the novel-artist cohort is only 0.16 — meaning **the GT isn't even in our top-100 for 84% of novel-artist turns**. This is a coverage problem at the operationally-relevant cutoff, not just a ranking problem. A reranker can't fix it.

### State accumulation decay

Hit@20 by number of prior accepted tracks:

| n_accepted | n | Hit@20 |
|---|---|---|
| 0 | 2,063 | 0.205 |
| 1 | 1,116 | **0.311** (peak) |
| 2 | 957 | 0.264 |
| 3 | 888 | 0.219 |
| 4-5 | 1,621 | 0.198 |
| 6+ | 1,319 | **0.155** (-50% vs peak) |

State accumulates (anchor tracks, positive tags, artist boosts) but isn't recency-weighted or capped. By turn 8, the compiler is searching a kitchen-sink query.

### Intent-mode breakdown

| intent | n | Hit@20 | Notes |
|---|---|---|---|
| playlist_build | 567 | 0.309 | best — cumulative add fits our bias |
| open_explore | 1,659 | 0.240 | turn-1 dominated |
| refinement | 5,579 | 0.231 | most common; ranking decays with depth |
| pivot | 159 | 0.201 | up from 0.126 after the hard-exclude fix; LLM-side still misses contrastive mentions ("different from Dookie era") |

### LLM extraction failure modes

| pattern | Hit@20 | Notes |
|---|---|---|
| 0 `mentioned_entities` (extractor returned trivial state) | 0.015 | barely above random — no fallback when LLM fires blank |
| 6+ `mentioned_entities` | 0.186 | LLM over-extracts on chatty turns; signal drowned in noise |
| 1 `hard_filter` extracted | 0.183 | slightly worse than no filter; year info is already in BM25 `release_date_text` |

### NDCG headroom from a perfect reranker on the current pool

| | Hit@20 |
|---|---|
| Current NDCG@20 from top-20 hits | 0.1009 |
| If a magic reranker moved every top-20 hit to rank 1 | 0.2379 |
| Ranking-only headroom | **+0.137 NDCG@20** (+136% relative) |

The retrieval pool already contains 22% of GT tracks in top-20 and 41% in top-100. The biggest unrealized NDCG gain is **ordering within the pool**, not finding more candidates.

## Recommended next steps, in priority order

| # | Change | Expected NDCG@20 impact | Effort |
|---|---|---|---|
| 1 | **Per-artist diversity cap in top-K** — limit any single artist to 2-3 slots in top-20 | +5-10% (closes ~half the same-artist crowding penalty for novel-artist GT) | small |
| 2 | **Cross-encoder reranker on top-100** — directly attacks the 0.137 NDCG headroom | +30-50% | large (new model + serving) |
| 3 | **Add `cf_bpr` track-to-track branch** — co-listening signal, already indexed in LanceDB; centroid query from anchor tracks | +5-10% (helps novel-artist coverage on turns 2+) | small (config + verify the column reads) |
| 4 | **Recency-weight anchor tracks; cap state at last 3 plays** — partially fixes the state-decay problem | +5-10% on turns 4-8 | small |
| 5 | **Soften hard_filters into score multipliers** — instead of pre-fusion mask, multiply by 0.5 on year mismatch | +2-3% | small |
| 6 | **Prompt fix: contrastive entities in pivot context** → `explicit_rejections`, not `mentioned_entities[sentiment=-1]` | small macro impact (pivot is 2% of turns) | small (but invalidates LiteLLM cache) |

## Operational gotchas (non-default toggles + things that bite)

### Config toggles in [`configs/v0plus_compiler_devset.yaml`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/configs/v0plus_compiler_devset.yaml)

- `enable_dense: false` — A/B winner this campaign; re-enable cautiously
- `centroid_alpha: {refinement: 0.30, playlist_build: 0.30}` — middle ground after sweep
- `same_artist_demote: 1.0` — variable is misnamed; now only fires for soft path. Set to 1.0 (effectively no-op) because explicit rejections moved to hard-exclude
- `max_in_flight: 8` — bumping to 32 triggers OpenRouter `gemma-3-12b-it` 429s; only safe with BYOK

### Required infrastructure state

- LanceDB index at `music-crs-models:/lancedb` must have `release_date` as `pa.date32()`. Rebuilding from older code (string release_date) silently breaks the filter mask. Rebuild via `python scripts/build_lancedb_index.py && modal run modal/app.py::upload_lancedb_index` (delete `/lancedb` from the volume first if it exists).
- `DEEPINFRA_API_KEY` required in **worktree `.env`** (not project-root `.env`). Modal `Secret.from_dotenv(__file__)` walks up from `modal/app.py` and stops at the first `.env`.
- LiteLLM disk cache lives on volume `music-crs-litellm-cache`, namespace `music-crs`. Wiping costs ~$5-10 to repopulate at OpenRouter rates.

### Modal runtime

- Use `modal run --detach` for any inference >5 min. Without `--detach` a local client disconnect cancels the run. Hit this once in this campaign.
- Sharded outputs land at `{tid}.shard_{i}.json` and `{tid}.shard_{i}_trace.json` on the results volume; merge with `python scripts/merge_shard_results.py --tid <tid> --num_shards <N>` before evaluating.
- `modal/config.yaml` sets `inference_cpu: 2.0`, `inference_memory: 16384` — right-sized for `max_in_flight: 8` (~1.3 cores used). Bump CPU back to 4-8 if `max_in_flight` ≥ 32.

### Eval quirks

- `evaluator/evaluate_devset.py` hard-codes `require_full_diagnostic_depth: True`. Any row with `pool_depth < 1000` (0.42% of v0+ turns this run, from hard-filter narrowing) **nulls out all deep-cutoff metrics** in the printed summary. Compute the macro metrics from `_samples.csv` filtered to `pool_depth >= 1000` — the headline numbers above use that workaround.

### LiteLLM upstream noise

- Every `litellm.acompletion` to OpenRouter prints ~4 `Provider List: ...` tracebacks per call. Known bug ([litellm#23879](https://github.com/BerriAI/litellm/issues/23879), PR #23987 open but unmerged): `OpenrouterConfig.get_supported_openai_params` calls `litellm.supports_reasoning(model)` *without* the provider prefix as a disjunction-fallback, which fails for non-reasoning models. The exception is caught downstream; the print survives. Silenceable with `litellm.suppress_debug_info = True` but we didn't, because it would also hide real errors.

### OpenRouter rate-limit dynamics

- `is_byok: false` for `google/gemma-3-12b-it` on OpenRouter → DeepInfra shared relay key → user-account-level rate limit doesn't matter, the upstream provider throttles. Cold-cache + `max_in_flight=32` triggers a 429 cascade; even at `max_in_flight=8` we see occasional 429s when the cache is empty. Fix: BYOK at `openrouter.ai/settings/integrations`, or pin a non-DeepInfra provider via `extra_body={"provider": ...}`.

## Artifacts

- Predictions (8000 rows): `exp/inference/devset/v0plus_compiler_devset.json`
- Per-turn state trace (8000 rows): `exp/inference/devset/v0plus_compiler_devset_trace.json`
- Eval summary: `exp/scores/devset/v0plus_compiler_devset.json`
- Per-sample metrics CSV: `exp/scores/devset/v0plus_compiler_devset_samples.csv`

Modal volume mirror: `music-crs-results:/inference/devset/v0plus_compiler_devset{.json, _trace.json}`.

## Commits

| SHA | Subject |
|---|---|
| `959212b` | feat(v0+): type HardFilter with start/end date fields |
| `f024b49` | refactor(v0+): pass HardFilter through release_date_filter_mask |
| `13d0f49` | docs(v0+): clarify HardFilter op semantics |
| `fcb9bc3` | feat(lancedb): store release_date as date32 |
| `40bb0df` | feat(v0+): add LanceDbCatalog |
| `92483af` | fix(v0+): align Lance/HF orderings; guard malformed HardFilter |
| `c50de2f` | feat(v0+): LanceDbCatalog eager-loads vector columns |
| `b222933` | feat(v0+): wire LanceDbCatalog as production catalog |
| `493e46a` | chore(v0+): drop HFTalkPlayCatalog.from_hf production path |
| `a820cad` | feat(v0+): record per-turn state + resolver/compiler trace |
| `f43f6de` | feat(infra): shard devset inference across N Modal containers |
| `bdff308` | feat(v0+): hard-exclude explicit_rejections; tune knobs |
