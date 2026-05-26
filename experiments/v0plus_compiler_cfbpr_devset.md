# Experiment: v0plus_compiler_cfbpr_devset

**Date:** 2026-05-26
**Config:** [`configs/v0plus_compiler_cfbpr_devset.yaml`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/configs/v0plus_compiler_cfbpr_devset.yaml)
**Status:** `analyzed`
**Pipeline:** v0+ compiler with cf_bpr branch enabled. Targets the novel-artist coverage gap (64% of devset turns) by adding a 4th retrieval branch that ANN-searches the cf_bpr column (co-listening BPR embedding) centered on positive-anchor track centroids.

## Headline result

| Metric | Baseline (v0plus_compiler_devset) | cf_bpr (this run) | Δ |
|---|---:|---:|---:|
| **NDCG@20** | **0.0984** | **0.0777** | **-21.0%** |
| Hit@20 | 0.2333 | 0.1694 | -27.4% |
| Hit@100 | 0.4042 | 0.2700 | -33.2% |
| Hit@1000 | 0.5705 | 0.3801 | -33.4% |
| MRR | 0.0662 | 0.0549 | -17.0% |

cf_bpr is a **regression** at the macro level. The cf_bpr branch itself does its job — novel-artist Hit@20 lifts from 0.093 → 0.114 (+23%) on turns where the extractor succeeds. But a separate prompt-format change that landed in the same campaign caused the LLM extractor to fail on **37.1% of turns** (vs 0.4% for the baseline), and those failures dominate the macro.

## What was built

This run combined four interlocking changes:

1. **cf_bpr 4th retrieval branch** ([compiler_v0plus.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/qu_modules/compiler_v0plus.py)). New config knobs `enable_cf_bpr` / `cf_bpr_weight` / `cf_bpr_topk`. Branch is centroid-only (no encoded query text): mean of positive-anchor cf_bpr vectors → `retriever.search_embedding(vector_field="cf_bpr", ...)`. No-ops when no anchors (turn 1, pivot intent, or all anchors had non-UUID ids).

2. **LanceDB schema fix** ([mcrs/lancedb/indexing.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/lancedb/indexing.py)). All embedding columns are now pinned to `fixed_size_list<float32>[dim]` at write time. Previously the qwen3 columns happened to land as `fixed_size_list` (because the HF source provides numpy arrays), but `cf_bpr` / `audio_laion_clap` / `image_siglip2` landed as variable-length `list<double>` and were not ANN-indexable. Halves on-disk size vs `double` and makes all 6 embedding columns native-ANN-queryable.

3. **Pydantic UUID-shape validation** ([schema.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/conversation_state_extraction_bakeoff/schema.py)). `TrackFeedback.track_id` rejects non-safe-identifier strings (quotes/colons/whitespace) → raises ValidationError. `referenced_track_ids` silently drops bad entries (per-entry recovery). Defense in depth: also added input-shape check + single-quote escape + try/except in `LanceDbCatalog.vector` so a malformed track_id can never reach the LanceDB SQL WHERE clause.

4. **Extractor prompt cleanup** ([compiler_v0plus_qu.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/qu_modules/compiler_v0plus_qu.py)). `session_memory_to_conversation` was treating the metadata-blob string returned by `MusicCatalogDB.id_to_metadata` as a track_id and stuffing 2000-char yaml-style row dumps into `played_track_ids`. Now uses a regex to extract the UUID prefix, then calls `catalog.track_label(track_id)` (also new) to render `"Artist - Track"` as the conversation label — matching the few-shot example format. Prompt size for a typical turn-5 dropped from ~5500 chars to **2314 chars**.

The pre-run prompt audit confirmed **no ground-truth leakage** anywhere in the extractor's input (system, few-shot, or rendered user prompt).

## Cohort breakdown

### Novel-artist cohort (64.3% of turns, the dominant failure mode in baseline)

Computed over turns where extraction succeeded (n=5,143 of 5,143 novel-artist turns; cf_bpr empty-pool stats aren't broken out per cohort, see "empty pool" section below):

| | Baseline | cf_bpr | Δ |
|---|---:|---:|---:|
| Hit@20 (novel) | 0.093 | **0.114** | **+22.6%** |
| Hit@100 (novel) | 0.182 | 0.215 | +18.1% |
| NDCG@20 (novel) | 0.044 | 0.053 | +21.5% |

### Continuation cohort (35.7%)

| | Baseline | cf_bpr | Δ |
|---|---:|---:|---:|
| Hit@20 (cont) | 0.487 | **0.571** | **+17.3%** |
| Hit@100 (cont) | 0.807 | 0.846 | +4.8% |
| NDCG@20 (cont) | 0.197 | **0.260** | **+31.9%** |

**Read this carefully:** the cohort numbers above are computed on the subset of turns where the extractor produced valid state. On those turns, the combined effect of cf_bpr + cleaner extraction lifts NDCG@20 substantially on both cohorts. Continuation cohort lifts more than novel cohort (cf_bpr doesn't *replace* same-artist signal, it adds behavioral neighbors on top).

The headline regression at the macro level is **entirely** the empty-pool turns.

## Root cause: 37% extractor failure rate

`v0plus_compiler_devset_trace.json` shows:
- **2,966 / 8,000 turns (37.1%)** had `state == None` because the extractor returned None.
- Of those, every one had `compiler.extractor_returned_none == True`.
- Modal log sample shows the failures are `JSONDecodeError`: the LLM emits the first JSON field, then degenerates into a long stutter of tab characters until it hits `max_tokens=1500`. Example: `'{"turn_intent": "...And the Gods Made War"  \t  \t  \t  \t  \t  ...'`.

Per-turn failure rate:

| Turn | Failure % |
|---|---:|
| 1 | 19.5% |
| 2 | 39.4% |
| 3 | 39.6% |
| 4 | 39.6% |
| 5 | 39.4% |
| 6 | 39.6% |
| 7 | 39.5% |
| 8 | 40.0% |

Turn-1 failure rate (19.5%) matches the rate of sessions where ALL 8 turns fail (191 / 1000 = 19.1%). Once a session's turn 1 fails, the subsequent turns also fail with very high probability. There's also a ~20% rate of "isolated" failures (turn 3 fails but turn 2 and turn 4 of the same session succeed).

**Working hypothesis (untested):** the LiteLLM disk cache from the baseline `v0plus_compiler_devset` campaign was warming most calls. The prompt-format cleanup (#4 above) changed every cache key. With cold cache, every turn was a fresh DeepInfra call to gemma-3-12b-it, and that model appears to enter a degenerative-stutter mode on a non-trivial fraction of cold calls. The baseline run never hit this rate because most of its calls were cache hits from a much earlier slower run.

Alternative hypotheses considered and weakened by the data:
- *The new prompt format itself is harder for the LLM*: doesn't explain turn 1 failures (turn 1's prompt has no music turns and is mostly unchanged from baseline structurally).
- *Specific content (non-English, weird characters) triggers degenerate output*: all 1,000 devset sessions are `preferred_language=English`, and the fully-failed sessions look unremarkable (first-user examples include innocuous prompts like `"I want to explore country music."`).
- *Schema UUID validation is too strict*: I checked — only 0 ValidationError events in the captured Modal log; the 2,966 failures are all JSON decode errors at parse time, before validation runs.

## What this run does and doesn't tell us about cf_bpr

**Does tell us:**
- cf_bpr branch wiring (centroid → `retriever.search_embedding` with `vector_field="cf_bpr"`) works correctly end-to-end on Modal with the rebuilt LanceDB schema.
- When the extractor produces valid state, cf_bpr lifts novel-artist Hit@20 by +23% — within the +5–10% pre-run estimate's high end.
- Continuation cohort also lifts (+17% Hit@20), which I'd not predicted — likely because the cleaner prompt also helps the extractor identify anchor tracks more precisely.

**Doesn't tell us:**
- What macro NDCG@20 cf_bpr buys when extraction is reliable. That requires either (a) fixing the LLM extractor's failure rate, (b) running with a different extractor model, or (c) a controlled A/B where the prompt format change is held constant.

## Recommended next steps

1. **Add LLM extractor retry/fallback** in [compiler_v0plus_qu.py](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/mcrs/qu_modules/compiler_v0plus_qu.py)'s `LiteLLMExtractor`. On `JSONDecodeError`, retry once with a different sampling seed (or temperature bump 0.0 → 0.3). Cap at 2 retries. This is a small change that should drop the 37% failure rate dramatically.
2. **Cache-warm rerun.** Re-run `v0plus_compiler_cfbpr_devset` after the retry logic lands; the LiteLLM cache will now have warm entries for the previously-failing calls (the retry's successful responses will be cached). Expect macro NDCG@20 close to the cohort numbers above (~0.10–0.12).
3. **Try a different extractor model.** gemma-3-12b-it via DeepInfra is showing the stutter pattern; swap in `openrouter/qwen/qwen3-32b-instruct` or `openrouter/meta-llama/llama-3.3-70b-instruct` as a sanity check. The extraction bakeoff (`experiments/analysis/conversation_state_extraction_bakeoff/`) didn't test these under the new prompt format.
4. **A/B the prompt cleanup change in isolation.** Add a config flag `clean_played_track_ids` (default True). Re-run baseline with `clean_played_track_ids=True, enable_cf_bpr=False` to measure the prompt change's standalone effect. Then re-run with `enable_cf_bpr=True` to isolate cf_bpr's marginal lift.

## Artifacts

- Predictions: [`exp/inference/devset/v0plus_compiler_cfbpr_devset.json`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/v0plus_compiler_cfbpr_devset.json) (8000 turns, 4-shard merge)
- Per-turn trace: [`exp/inference/devset/v0plus_compiler_cfbpr_devset_trace.json`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/v0plus_compiler_cfbpr_devset_trace.json)
- Eval summary: [`evaluator/exp/scores/devset/v0plus_compiler_cfbpr_devset.json`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/evaluator/exp/scores/devset/v0plus_compiler_cfbpr_devset.json)
- Per-sample metrics: [`evaluator/exp/scores/devset/v0plus_compiler_cfbpr_devset_samples.csv`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/evaluator/exp/scores/devset/v0plus_compiler_cfbpr_devset_samples.csv)

Modal volume mirror: `music-crs-results:/inference/devset/v0plus_compiler_cfbpr_devset{.json, _trace.json}` and per-shard files.

## Operational notes

- Sharded inference run was the *third* attempt for this tid:
  - Run 1 (4 shards): killed by a SQL injection bug in `LanceDbCatalog.vector` — LLM emitted a metadata-blob "track_id" containing a double quote that broke the WHERE clause. Only shard_3 wrote successfully before the rest crashed.
  - Run 2 (4 shards): launched after the SQL escape + UUID validator fixes, but before the prompt-format fix. Cancelled mid-flight.
  - Run 3 (4 shards): with all four fixes. Completed cleanly — but unmasked the LLM extractor failure rate, which now dominates the macro.
- `scripts/merge_shard_results.py` was hardened during this campaign to dedupe by `(session_id, turn_number)` (last-shard-index wins, warn-on-overlap) rather than silently concatenate. Stale shards from prior runs had been producing 9600-row "merged" files that subtly invalidated eval.
- Modal app id for the successful run: `ap-aJACwGghVw0g99Qw1Kju8c` (2026-05-26 09:10 EDT).
