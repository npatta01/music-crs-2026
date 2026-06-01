# Cross-Encoder Reranker — Learnings

**Date:** 2026-05-27
**Status:** `analyzed`
**Companion:** [`experiments/cross_encoder_rerank_bakeoff.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/cross_encoder_rerank_bakeoff.md) (session journal with the actual numbers)

## TL;DR

We built a reranker framework and tested 5 model variants (MiniLM-L-12, BGE-base, Qwen3-Reranker 0.6B/4B/8B) across 7+ prompt/config permutations. Final result: **Qwen3-Reranker-0.6B + structured query via DeepInfra**, NDCG@20 lift of +12.6% on full devset (0.1411 → 0.1594). Modest. Most of the lift went to the *continuation* cohort that didn't need help. The novel-artist cohort (64% of turns, the actual bottleneck) barely moved.

The reranker is **off by default in the live pipeline** — invoked only via the opt-in offline script `scripts/rerank_offline.py`. We shipped the framework and the measurement; the decision to wire it into submission is held pending the broader gap analysis.

This doc captures the lessons from the journey so we don't repeat them.

---

## What we tested

| model | params | backend | result |
|---|---:|---|---|
| `cross-encoder/ms-marco-MiniLM-L-12-v2` | 33M | sentence-transformers (local CPU/MPS) | weak; replace mode regressed -9%, fusion mode +2.6% on full devset |
| `BAAI/bge-reranker-base` | 110M | sentence-transformers (local CPU/MPS) | basically same as MiniLM in fusion mode |
| `Qwen/Qwen3-Reranker-0.6B` | 600M | DeepInfra HTTP | **canonical winner** — +12.6% NDCG@20 |
| `Qwen/Qwen3-Reranker-4B` | 4B | DeepInfra HTTP | +14% on smoke (240 turns); slightly better than 0.6B but 5× expensive |
| `Qwen/Qwen3-Reranker-8B` | 8B | DeepInfra HTTP | within noise of 4B on smoke (saturated) |
| `Qwen/Qwen3-Reranker-4B` | 4B | Modal vLLM (A10) | never produced a clean full-devset result — see "Infrastructure scars" |

Skipped:
- `jinaai/jina-reranker-v3` — CC-BY-NC, not competition-safe
- `BAAI/bge-reranker-v2-gemma` (2B), `BAAI/bge-reranker-v2-m3` (568M) — deprioritized after 0.6B captured most of the achievable lift
- RankZephyr / listwise rerankers — Phase 3 work, not started

---

## Technical learnings

### 1. Replace-mode reranking is structurally broken for multi-branch RRF retrieval

**The pattern that failed:** take top-N from fused RRF, score each with the cross-encoder, sort by xenc score, drop the RRF score entirely.

```python
# WRONG for our setup
reranked = sorted(top_n, key=lambda x: -cross_encoder.score(query, x.doc))
```

Result: **-9% NDCG@20 (MiniLM) to -28% NDCG@20 (BGE-base)**. Bigger model didn't fix it.

Root cause: an item at rank 5 in the fused list is there because *multiple branches* voted for it (BM25, image, audio, cf_bpr, metadata). The cross-encoder only sees `(turn_intent, doc_text)` and has no idea this candidate had strong consensus. So it may push it below rank 20 in favor of a candidate with stronger surface text match but weaker ensemble signal.

**Fix:** **RRF-rank fusion** — combine the candidate's RRF rank with its xenc rank using the standard RRF formula:

```python
final_score = w_rrf / (k + rrf_rank) + w_xenc / (k + xenc_rank)
```

This preserves the ensemble consensus while letting the reranker contribute a rank vote. Works across all models we tested.

### 2. Soft xenc weighting (xenc_weight = 0.5) outperforms equal or aggressive weights

In fusion mode, we A/B'd `xenc_weight ∈ {0.5, 1.0, 2.0}` (RRF weight fixed at 1.0):

| weight | NDCG@20 on smoke |
|---|---:|
| 0.5 | **0.1906** ← best |
| 1.0 | 0.1823 |
| 2.0 | 0.1724 |

Letting RRF dominate 2:1 wins. The reranker is useful as a *nudge* but is too noisy to drive ranking on its own.

### 3. Enriched query content can backfire — it depends on the model

We tested two query templates:
- **basic:** just `turn_intent` (the LLM-extracted single-sentence ask)
- **structured:** labeled fields with `Request:`, `Just heard: ... (year, tags)`, `Recent: ...`, `User likes: ...`, `Policy: ...` (mirrors the conversational state)

Results vary by model (240-turn smoke NDCG@20):

| model | basic | structured | winner |
|---|---:|---:|---|
| MiniLM-L-12 | 0.1906 | 0.1671 | basic (structured -8% on this model) |
| Qwen3-Reranker-4B | **0.2079** | 0.2051 | basic (tie, structured slightly worse) |
| Qwen3-Reranker-0.6B | 0.1875 (extrapolated) | **0.1957** | structured (the smaller model benefited from explicit structure) |

**Why:**
- MiniLM is trained on MS MARCO (short web queries, 1-3 words) — long structured input is way off its training distribution
- 4B is strong enough that turn_intent alone captures most of the signal; adding context provides no marginal lift
- 0.6B benefits from explicit structure because the model needs more guidance to disambiguate music semantics

**Lesson:** prompt design is model-specific. Test before assuming "more context = better."

### 4. Model size has sharp diminishing returns past 0.6B

| comparison | NDCG@20 delta on smoke |
|---|---:|
| MiniLM (33M) → Qwen3-Reranker-4B | +14% |
| Qwen3-Reranker-0.6B → 4B (structured) | +5% (smoke); the model-vs-model delta is small |
| Qwen3-Reranker-4B → 8B | +1% (within noise on smoke) |

**At our scale, Qwen3-Reranker-0.6B is the right cost/quality knee:**
- 6× cheaper inference than 4B
- ~5× less wall time on DeepInfra
- ~95% of the 4B quality

8B is pure waste at this point in the curve.

### 5. The reranker can only help what retrieval surfaces

Most important lesson. From the gap analysis on the full-devset run:

| GT location | % of all turns |
|---|---:|
| Already in base top-20 (rerank has minor role) | 31.0% |
| In base top-21–200 (rerank reachable) | 19.8% |
| **In base top-201–1000 (rerank out of window)** | **13.5%** |
| **Not in base top-1000 (retrieval miss entirely)** | **35.8%** |

**~49% of turns have GT outside top-200.** The reranker is structurally incapable of touching those. We cannot improve them with any reranker, no matter how strong.

Of the 50.8% reachable cohort (GT in base top-200), the reranker promoted only **+182 net turns into top-20** out of a possible +1586 = **11.5% capture of achievable lift**. That's the headroom on the reachable cohort. With a stronger / fine-tuned reranker we could plausibly capture 30-50% of that = +0.04 to +0.07 macro NDCG@20.

But the **bigger lever is retrieval**: closing the 49% out-of-pool gap would let any reranker pay back more.

### 6. The reranker helps the cohort that needed it least

Cohort breakdown of the +0.018 macro NDCG@20:

| cohort | % turns | abs Hit@20 lift | macro contribution |
|---|---:|---:|---:|
| Continuation (already-strong, Hit@20 = 0.66 baseline) | 36% | +0.049 | +0.018 |
| Novel-artist (the bottleneck, Hit@20 = 0.11 baseline) | 64% | +0.008 | +0.005 |

Same relative lift (~7%) but the continuation cohort has way more absolute room to swing. The novel-artist cohort — the 64% that's our actual problem — got essentially nothing from the reranker.

**Why:** the reranker is anchor-free, but it's reranking a pool that was assembled by *anchor-centric* retrieval (BM25 with `mentioned_entities` boost, image/audio/cf_bpr centroids of accepted tracks). Most novel-artist GTs aren't in the pool. The reranker can't promote what wasn't surfaced.

---

## Infrastructure scars

This was a much bigger time sink than it should have been.

### Modal + vLLM rabbit hole

We spent ~3 hours fighting Modal/vLLM infra before pivoting to DeepInfra. The failure modes, in order:

1. `transformers==4.46` didn't recognize `qwen3` model type → required ≥4.51
2. vLLM 0.10 had `task="score"` API; rejected by `EngineArgs.__init__` with newer transformers → had to bump vLLM
3. vLLM 0.11 renamed `task` → `runner="pooling"` → another image rebuild
4. A10 (24 GB) VRAM stalls with `max_inputs=8` and `max_model_len=4096` → vLLM scheduler deadlocks waiting for KV cache slots
5. Chunking 200 pairs → 4 chunks per turn introduced a length-mismatch bug → 96% turns fell through to passthrough
6. Spawning 240 futures at once raced Modal's per-input timeout → cascading timeouts + container reschedules + cold-start death spiral
7. `@modal.concurrent(max_inputs=4)` triggered vLLM 0.11 ZMQ router-socket assertion (`Assertion failed: !_current_out`) → containers crash-looped
8. `max_inputs=1` finally stable, but EngineCore crashed during `_dummy_pooler_run` warmup on one run

**We never produced a clean full-devset result via vLLM.** DeepInfra produced one in 55 min, ~$4.

### What worked on Modal infrastructure (when it worked)

- `@modal.concurrent(max_inputs=1)` was the only stable config for vLLM 0.11 + pooling — but we hit other crashes anyway
- `scaledown_window=300` (5 min) is wrong for chunked runs because containers can scale down mid-job; combined with deep queues this kills inputs that were already in flight
- Local-side rate limiting via `ThreadPoolExecutor + .remote()` is much better than spawning all futures upfront → Modal's per-input timeout only starts when a slot actually opens

### What worked on DeepInfra

- Pricing is **shockingly cheap** at the 0.6B tier ($0.010/1M tokens). ~$4 for a full devset run.
- The `instructions` field in the API is **silently ignored** for Qwen3-Reranker. You can only control the instruction by baking it into the query string.
- HTTP-API call latency is fine (~200-500ms per batched call). Throughput scales linearly with concurrent connections.
- 37k requests for 267M tokens across the day → no rate-limit issues.

### Modal vs DeepInfra honest comparison

| | Modal vLLM (in theory) | DeepInfra (what shipped) |
|---|---|---|
| Per-token cost | ~$0 (just GPU time) | $0.010/1M |
| Full-devset cost | ~$3-5 (GPU compute) | ~$4 |
| Instruction control | yes (full template) | **no** (silently dropped) |
| Wall time | TBD — never produced one | 55 min |
| Engineering investment | ~3 hrs debug, never working | ~30 min, worked first try |

For our scale, DeepInfra is the right answer. We don't gain enough from instruction control to justify the infra debt. If we needed the instruction control AT scale (e.g., 100 full-devset runs for hyperparameter sweep), Modal+vLLM might pay back the setup investment.

---

## Strategic learnings

### 1. Cross-encoder reranker isn't a silver bullet for our problem

We went into this expecting "+30-50% NDCG@20" based on the literature. We got +12.6%. The lit projections assume the retrieval pool already contains the GT — when half your GTs are missing from top-200, no reranker can close that gap.

**Heuristic for future projects:** before investing in reranker, measure Hit@N where N is the rerank window. If Hit@200 ≪ 1.0, the reranker's ceiling is already capped.

### 2. The offline-replay pattern is gold for reranker experimentation

Once we had `scripts/rerank_offline.py` reading saved predictions + traces, we could iterate freely on rerankers without re-running retrieval. Each smoke was ~5 min and ~$0.20. Without this pattern, every model variant would have cost ~$10 (full pipeline) and 60 min.

**Specifically useful for:**
- Hyperparameter sweeps (fusion weights, prompt variants)
- Model comparisons (5 models in an afternoon)
- Sanity checks (does this prompt actually score sensibly on 3 known pairs?)

Going forward: any new retrieval+rerank work should save predictions+traces so reranker iteration stays cheap.

### 3. Don't pivot infrastructure mid-iteration

We oscillated: HF transformers → DeepInfra → Modal vLLM → back to DeepInfra. Each pivot ate setup time. In hindsight, the right move was to commit to DeepInfra after the first 4B smoke worked (NDCG@20 = 0.208) and only revisit Modal IF instruction control proved necessary for a measurable gain.

**Heuristic:** stop changing your backend in the same session you're trying to measure something.

### 4. The "smoke first, then full" rule is non-negotiable

We saved multiple bad full-devset runs because the user insisted on smoke tests. Examples that would have wasted full-devset budget:
- vLLM `task="score"` API mismatch (broken before any work happened)
- Chunking length-mismatch (96% of turns fell through)
- ZMQ socket race (containers crash-looping)
- DeepInfra ignoring `instructions` field (would have spent $15+ measuring an effect that wasn't actually applied)

Smokes caught all of these in 5 min, $0.50.

---

## What we'd do differently next time

If we restarted the reranker project knowing what we know now:

1. **Day 1**: Measure Hit@200 of the current retrieval pool. Confirm the reranker ceiling. ✅ (didn't do this; should have)
2. **Day 1**: Test Qwen3-Reranker-0.6B via DeepInfra with basic query + RRF fusion (xenc_weight=0.5). Full devset. ~$4. Should land in ~1 hour.
3. **Day 2**: Cohort breakdown. See where the lift is. Decide whether to push the reranker (4B, fine-tune, listwise) or pivot to retrieval coverage.

Total: 2 days of measurement, vs the multi-day infra rabbit hole we actually did.

---

## What's shipping in this PR

- ✅ The post-fusion feature framework (`mcrs/qu_modules/post_fusion_features.py`) — behavior-preserving for current canonical, opens the door to policy-conditional behavior when exploration_policy is non-balanced
- ✅ `mcrs/qu_modules/cross_encoder_reranker.py` — reranker framework with DeepInfra, SentenceTransformers, FlagEmbedding, Qwen3 custom backends. **Dormant** — not invoked from the live compiler pipeline.
- ✅ `modal/rerank.py` — Modal vLLM service + offline-replay entrypoint. **Dormant** for same reason.
- ✅ `scripts/rerank_offline.py` — offline orchestrator (opt-in via CLI). Production-ready for future reranker experiments.
- ✅ The schema extension (`ProcessConstraints` field) — extracted on every turn but default `balanced` policy maps to no-op in the live compiler. Zero behavior change for current production.
- ✅ Catalog additions (`album_id_of`, `track_text`) — used by the dormant reranker, no impact on live pipeline.
- ✅ New "no-drag" config (`configs/v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset.yaml`) — used as the retrieval base for reranker experiments. Modest +0.014 NDCG@20 lift vs canonical image-only on full devset.
- ✅ Gap analysis + reranker bake-off journal in `experiments/`.
- ✅ Tests: 14 for post_fusion_features, 11 for cross_encoder_reranker, updates for loosened HardFilter.

**Cross-encoder rerank is OFF in the live pipeline.** To enable it, a future PR would either:
- Plumb `CrossEncoderReranker.rerank()` into `compiler_v0plus.py.compile()` after `_apply_soft_adjustments`
- Or run `scripts/rerank_offline.py` as a post-inference step in the submission pipeline

Neither is wired up. Decision to enable is held pending the retrieval-coverage work (the bigger lever per the gap analysis).
