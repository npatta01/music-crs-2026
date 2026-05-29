# Cross-Encoder Reranker Bake-Off — Session Journal

**Date:** 2026-05-27 (long iteration session)
**Status:** `analyzed` — **0.6B-structured + DeepInfra is the new canonical reranker.** Full-devset NDCG@20 = **0.1594** (+12.6% vs base, +9.1% vs the prior image-only canonical of 0.1461).
**Base config (the retrieval pool we're reranking):** [`v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset`](v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset.md) — NDCG@20 0.1411 on full devset, NDCG@20 0.1819 on the 240-turn smoke subset.

## ⭐ Headline — full devset (8000 turns), 2026-05-27

| config | NDCG@20 | Hit@20 | Hit@1 | MRR | Hit@100 |
|---|---:|---:|---:|---:|---:|
| base (no rerank) | 0.1415 | 0.3098 | 0.0424 | 0.0987 | 0.4575 |
| image-only canonical (prior best) | 0.1461 | 0.300 | n/a | n/a | 0.440 |
| **0.6B-structured rerank (new canonical)** | **0.1594** | **0.3325** | **0.0545** | **0.1147** | **0.4781** |
| Δ vs base | +0.018 | +0.023 | +0.012 | +0.016 | +0.021 |
| Δ vs base (%) | **+12.6%** | +7.3% | +29% | +16% | +4.5% |

**Cost:** ~$4-5 total all-in for 8000-turn full devset (DeepInfra Qwen3-Reranker-0.6B at $0.010/1M tokens). **Wall time:** 54.5 min with `--turn-workers 8 --max-in-flight 4`.

## TL;DR — what we know now

- **Replace-mode reranking is structurally broken** for our setup (any model). Pure-replace destroys the multi-branch RRF ensemble signal → Hit@20 drops 10-35%.
- **RRF-rank fusion fixes it.** Combine RRF rank + xenc rank: `final = w_rrf/(k+rrf_rank) + w_xenc/(k+xenc_rank)`. Best operating point: `xenc_weight=0.5` (RRF dominates 2:1).
- **Model strength matters more than size.** Qwen3-Reranker-4B = +14% NDCG@20 vs MiniLM-L-12 on smoke. Qwen3-8B ≈ Qwen3-4B (saturated; pick 4B).
- **DeepInfra's hosted endpoint silently ignores `instructions`** — we can't tune the meta-prompt via the API. Switched to vLLM on Modal A10 for full prompt control.
- **vLLM is ~4× faster than HF transformers** in our setup (0.55 vs 0.14 turns/sec). Real win, but less than the 10× expected — vLLM's prefix caching + continuous batching help but a 4B model on A10 has a compute floor.

## Reranker pipeline architecture

The reranker is a **post-fusion stage** on top of the existing RRF + PostFusionReranker output:

```
LLM extracts state → resolver → 5 retrieval branches
                                  ↓ each returns top-1000 by its own score
                              RRF fusion → ~1000 fused candidates
                                  ↓
                              PostFusionReranker (soft demotes: explicit rejections, anchor demote, tag boosts)
                                  ↓
                              fused_top_1000  ← input to cross-encoder
                              ├ head = fused[:200]   ← reranked by Qwen3-Reranker
                              └ tail = fused[200:]   ← passthrough at RRF positions
                                  ↓
                              For each (turn_intent, candidate_text) in head:
                                 score = cross-encoder.score(query, doc)
                              RRF-rank fusion: combine RRF rank + xenc rank
                                  ↓
                              final top-1000 → top-20 for metrics
```

## What's been shipped (code)

| file | purpose |
|---|---|
| `mcrs/qu_modules/cross_encoder_reranker.py` | Reranker class. Backends: sentence-transformers (CPU OK), FlagEmbedding, Qwen3-custom HF, **DeepInfraRerankerBackend** (HTTP). Fusion modes: `replace` and `rrf` (with weights). |
| `mcrs/qu_modules/post_fusion_features.py` | Feature framework — `UserFeedbackFeature`, `SessionAnchorFeature`. Soft demotes (explicit rejections, anchor-artist demote, tag boosts). |
| `mcrs/qu_modules/v0plus_catalog_lance.py`, `..._hf.py`, `v0plus_catalog.py` | Added `track_text()` (rich text rep for reranker), `album_id_of()` (for diversify_albums policy). |
| `experiments/analysis/conversation_state_extraction_bakeoff/schema.py` | Added `ProcessConstraints` model + `ExplorationPolicy` enum. |
| `experiments/analysis/conversation_state_extraction_bakeoff/prompts.py` | Extractor prompt: rules for `exploration_policy`, 2 new few-shots. |
| `scripts/rerank_offline.py` | Offline-replay orchestrator. Reads saved predictions + traces; calls reranker backend; writes new predictions. Supports `--fusion` mode and `--query-template basic|structured` (only for DeepInfra/HF backends, not Modal). |
| `scripts/score_rerank_compare.py`, `score_rerank_multi.py` | Pairwise + N-way evaluation. |
| `modal/rerank.py` | Modal app: vLLM-backed `Qwen3RerankerService` GPU class + `rerank` local entrypoint. Full prompt control (instruction + query). |
| `tests/test_cross_encoder_reranker.py`, `test_post_fusion_features.py` | Unit tests, all pass. |

## Smoke results so far

All smokes on the same 240-turn subset (30 sessions × 8 turns from devset). Base reference = pre-rerank NDCG@20 = 0.1819 on this subset (note: full-devset base is 0.1411).

| variant | NDCG@20 | Hit@20 | MRR | Δ NDCG@20 vs base | notes |
|---|---:|---:|---:|---:|---|
| **base** (no rerank) | 0.1819 | 0.4542 | 0.1116 | — | — |
| MiniLM-L-12, replace, basic | 0.1657 | 0.3667 | 0.1168 | -9% ❌ | replace destroys top-20 |
| MiniLM-L-12, replace, enriched | 0.1305 | 0.2958 | 0.0925 | **-28% ❌** | enriched context HURT MiniLM (over-anchoring) |
| BGE-base, replace, basic | 0.1442 | 0.3250 | 0.1013 | -21% ❌ | bigger model didn't help — architecture issue |
| MiniLM-L-12, rrf-fusion, basic, w=1.0 | 0.1823 | 0.4042 | 0.1275 | ~flat | fusion fixes the regression but no lift |
| **MiniLM-L-12, rrf-fusion, basic, w=0.5** | **0.1906** | 0.4417 | 0.1270 | **+4.8% ✅** | xenc_weight=0.5 wins |
| MiniLM-L-12, rrf-fusion, basic, w=2.0 | 0.1724 | 0.3750 | 0.1226 | -5% | over-eager xenc hurts |
| MiniLM-L-12, rrf-fusion, enriched, w=1.0 | 0.1671 | 0.3833 | 0.1139 | -8% | enrichment still hurts MiniLM even in fusion |
| BGE-base, rrf-fusion, basic, w=1.0 | 0.1795 | 0.4042 | 0.1235 | -1% | basically MiniLM-equivalent in fusion mode |
| **Qwen3-Reranker-4B, rrf-fusion, basic, w=0.5** | **0.2079** | **0.4708** | **0.1393** | **+14% ✅** | first time Hit@20 IMPROVES; model strength matters |
| Qwen3-Reranker-8B, rrf-fusion, basic, w=0.5 | 0.2095 | 0.4750 | 0.1394 | +15% | barely above 4B (saturated) → **use 4B** |

## Full-devset measurement so far

MiniLM-L-12 + fusion w=0.5 was the only variant we ran on the full 8000-turn devset:

| metric | base (no-drag config) | MiniLM rrf-fusion w=0.5 | delta |
|---|---:|---:|---:|
| NDCG@20 | 0.1415 | **0.1453** | +2.6% |
| Hit@1 | 0.0424 | 0.0455 | +7.3% |
| Hit@100 | 0.4575 | 0.4705 | +2.8% |
| MRR | 0.0987 | 0.1028 | +4.2% |

Lift is real but **smaller than smoke** (smoke +4.8% → full +2.6%). High-variance smokes routinely overstate.

**Important**: this still lands at 0.1453, **below the canonical `image_devset` baseline (0.1461)**. MiniLM is not shippable. Qwen3-4B was the path forward — but we haven't run it on full devset yet.

## Key decisions made (and why)

1. **RRF-rank fusion over score-replace**: scored multi-branch consensus is too valuable to discard.
2. **xenc_weight = 0.5**: empirically best on smokes; reranker is useful for nudging but not for driving ranking.
3. **Qwen3-Reranker-4B over 8B**: 8B costs 2× compute for ~0 measurable improvement.
4. **Skip jina-reranker-v3**: CC-BY-NC, not competition-safe (otherwise it'd be a strong candidate at 0.6B params).
5. **Modal + vLLM over DeepInfra HTTP for instruction tuning**: DeepInfra silently drops the `instructions` field. Modal gives full control.
6. **`runner="pooling"` in vLLM 0.11+**: replaces the old `task="score"` API which we hit on first try.
7. **`max_containers=2` for smokes**: caps spend at ~$2.20/hr while iterating prompts.
8. **`@modal.concurrent(max_inputs=8)`**: lets one vLLM container interleave 8 turn-batches; works with vLLM's continuous batching.

## Prompts (the design we landed on)

### Instruction (3 modes available in `modal/rerank.py`)

**Generic (`instruction_mode=generic`):**
> *"Score how well a candidate music track matches the user's next desired recommendation in this multi-turn music conversation. Consider stylistic match (genre, era, mood), similarity to recently played tracks, and the user's stated preferences."*

**Policy-conditional (`instruction_mode=policy`)** — instruction varies by `exploration_policy`:
- `exploit`: "...user wants MORE FROM THE SAME ARTIST OR ALBUM..."
- `diversify_artists`: "...user wants the SAME STYLE BUT A DIFFERENT ARTIST..."
- `diversify_albums`: "...user wants tracks by a different album, same artist OK..."
- `balanced`: generic.

### Query (`query_template=basic|structured`)

**Basic:** just `state.turn_intent`.

**Structured (labeled fields):**
```
Request: {turn_intent}
Just heard: "{artist} - {track}" ({year}, {top 3 tags})
Recent: "{artist1 - track1}" (year, tags); "{artist2 - track2}" (year, tags); ...
User likes: {positive mentioned entities}
Policy: {natural-language hint, only if non-balanced}
```

### Document (the catalog side, unchanged)

```
{artist} - {track} | {album} ({year}) | {top 15 tags}
```

(Per discussion: dropped popularity tier — too noisy.)

## What's running RIGHT NOW

**Smoke C** in background: `rerank --model Qwen/Qwen3-Reranker-4B --query-template structured --instruction-mode policy --num-sessions 30`

Last progress: **220/240 turns scored** at 0.55 turns/sec. ~30 sec to completion.

## What's planned (next steps in order)

### Immediate (when smoke C lands)

1. **Compare smoke C against base + Qwen3-4B-basic baseline** on the same 240-turn subset.
   - If NDCG@20 > 0.208 (current Qwen3-4B-basic baseline): the prompt enrichment helps. Move to step 2.
   - If NDCG@20 ≈ 0.208: prompt enrichment didn't move it. Decide whether to investigate prompt format more or move on.
   - If NDCG@20 < 0.208: enrichment HURT (like MiniLM did). Discuss.

### Conditional (if smoke C wins)

2. **Smokes A (basic + generic) and B (structured + generic)** on Qwen3-4B + vLLM for attribution. Tells us whether the lift comes from (a) the policy-conditional instruction or (b) the structured query content or (c) both.
3. **Round 2 structure test**: same content as the winner, but **natural-language prose** instead of labeled fields. (Per earlier decision: skip XML/JSON.)

### Then (full devset run)

4. **Full devset (8000 turns) on the winning prompt + Qwen3-4B**. Need to first decide infrastructure:
   - Current setup: ~2 hours wall, ~$2-3
   - `max_containers=4`: ~1 hour, same cost
   - A100 + 4 containers: ~30 min, ~$5
   - **Drop to Qwen3-Reranker-0.6B**: ~15 min, possibly comparable quality (worth testing as an aside)
5. **Compare full-devset result** to:
   - Pre-rerank no-drag config (NDCG@20 = 0.1411)
   - Image-only canonical (NDCG@20 = 0.1461)
   - MiniLM full devset (NDCG@20 = 0.1453)
6. **If reranker config beats 0.1461**, ship as new canonical → update `experiments/README.md` Current Bests.

### Deferred (Phase 3, only if Phase 2 saturates)

7. **Listwise LLM reranking via `rank_llm`** (RankZephyr-7B). Per the literature review, listwise is structurally suited to conversational rerank. Would need a separate Modal infra (7B model needs A10/A100).
8. **Fine-tune Qwen3-Reranker on devset cohort labels** (positive = GT, hard negatives = top-K non-GT). A few hours of T4 GPU.

## Optimization debt (technical, not blocking)

These would speed up iteration but don't change correctness:

| optimization | current state | potential win |
|---|---|---|
| Bump `batch_size` in HF path 32 → 200 | not done | ~3× for HF runs |
| Implement manual prefix caching in HF | not done | ~3-5× for HF |
| Bump Modal `max_containers` for full-devset runs | currently 2 | linear with N |
| vLLM with persistent (deployed) container vs ephemeral | ephemeral per run | saves ~100s cold-start per smoke |
| Try Qwen3-Reranker-0.6B (smaller, much faster) | not tested | possibly free win if quality holds |

## Background context (for someone picking this up cold)

- Baseline retrieval is `v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset` — BM25 + 4 dense branches fused via RRF + soft demotes from `PostFusionReranker`.
- Predictions and traces from the base run live in `evaluator/exp/inference/devset/` — load these to replay rerankers offline without re-running inference.
- The reranker's job is to reorder the top-200 of the fused pool. Tail (200-1000) passes through at RRF position.
- The framework purposely keeps fusion mode (`replace` vs `rrf`) and xenc weight tunable so future experiments can A/B without code changes.
- Open-weight only (no paid APIs) per competition rules. That rules out Cohere Rerank and jina-reranker-v3 (CC-BY-NC).

## Commands cheat sheet

```bash
# Offline replay against an existing prediction run (any sentence-transformers
# compatible model — runs locally on CPU/MPS):
python scripts/rerank_offline.py \
    --base-tid v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset \
    --model cross-encoder/ms-marco-MiniLM-L-12-v2 \
    --rerank-top-k 200 --batch-size 64 \
    --no-enrich --fusion rrf --fusion-xenc-weight 0.5

# Same but Qwen3-Reranker on DeepInfra (no instruction control — uses default):
python scripts/rerank_offline.py \
    --base-tid v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset \
    --model Qwen/Qwen3-Reranker-4B --backend deepinfra \
    --rerank-top-k 200 --batch-size 32 \
    --no-enrich --fusion rrf --fusion-xenc-weight 0.5

# Modal vLLM smoke (instruction control, faster) — 1 pair sanity:
modal run modal/rerank.py::smoke --model Qwen/Qwen3-Reranker-4B

# Modal vLLM rerank — full run (N sessions):
modal run modal/rerank.py::rerank \
    --base-tid v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset \
    --model Qwen/Qwen3-Reranker-4B \
    --query-template structured --instruction-mode policy \
    --num-sessions 30   # 0 = full devset

# Compare two prediction files:
python scripts/score_rerank_compare.py \
    --base path/to/base.json \
    --reranked path/to/reranked.json \
    --n-limit 240
```

## Recovery: if a Modal run hangs or fails

```bash
# Kill local modal client
ps aux | grep "modal run modal/rerank" | grep -v grep | awk '{print $2}' | xargs kill -9

# List Modal apps
modal app list | grep music-crs-rerank

# Stop a specific ephemeral app
modal app stop <app_id>
```

## Related files / prior reading

- The 2026-05-26 ablation (`experiments/v0plus_compiler_ablation_2026-05-26.md`) is the source of "image_siglip2 is the dominant retrieval lever; cf_bpr concentrates on same-artist, etc."
- The original cross-encoder plan: `docs/superpowers/plans/2026-05-27-cross-encoder-reranker.md` — written before any data; many specifics changed during the run (e.g., DeepInfra discovery, vLLM switch, prompt enrichment direction).
- v0+ schema reference: `experiments/analysis/conversation_state_design_v2/final_merged_schema.md` (where `process_constraints` came from).
