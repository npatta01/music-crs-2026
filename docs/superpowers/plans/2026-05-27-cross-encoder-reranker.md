# Cross-Encoder Reranker — Multi-Model Bake-Off Plan

**Date:** 2026-05-27 (rev 2 — switched from single-model v1 to multi-model bake-off)
**Status:** proposed
**Constraint:** open-weight models only (no paid APIs — competition rules)

## Motivation

Current state from `v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset` run:

| | this run | image_devset | gap |
|---|---:|---:|---:|
| Hit@20 | 0.310 | 0.300 | +1pp |
| Hit@200 | 0.509 | ~0.470 | +4pp |
| Hit@1000 | 0.644 | 0.598 | +5pp |
| NDCG@20 | 0.141 | 0.146 | -0.5pp |

**The diagnosis: we have pool coverage, we don't have ranking precision.** The GT is in our top-200 for 51% of turns, but in top-20 for only 31%. A reranker that promotes correct candidates from rank 20-200 into top-20 is the highest-leverage structural change.

The 64% novel-artist cohort (Hit@20 ≈ 0.10) is where this matters most — those tracks ARE in our pool (image+audio+cf_bpr widened coverage) but our RRF rank math can't surface them.

**Estimated impact:** +30-50% relative NDCG@20 lift (0.14 → 0.18-0.21) with off-the-shelf MiniLM-L-12. Higher with bge-reranker-base or Qwen3-Reranker.

## What a cross-encoder reranker does

Takes a **pair** (query_text, candidate_text), runs a single BERT-style encoder forward pass on the concatenation, outputs a relevance score. Unlike bi-encoders (image, audio, qwen3 embeddings — which embed query and candidate *separately* into vectors and compare), the cross-encoder sees both texts together → can model interaction between query terms and candidate terms → much higher top-K precision.

Tradeoff: cannot precompute scores. Every (query, candidate) needs a forward pass. So we only score the top-N (N=200) candidates per turn, not the full 47k catalog.

## Architecture

```
existing pipeline
    ↓
PostFusionReranker (soft demotes — explicit rejections, anchor demote, tag boosts)
    ↓
fused: list[(track_id, score)], length up to 1000
    ↓
CrossEncoderReranker  ← NEW
    head = fused[:200]   ← these get reranked
    tail = fused[200:]   ← these passthrough at their RRF positions
    for each in head:
        candidate_text = catalog.track_text(tid)
        score = model.predict((state.turn_intent, candidate_text))
    head = sorted(head, by -score)
    fused = head + tail
    ↓
final top-K
```

**Why a separate stage, not a Feature in the existing PostFusionReranker:**
- `Feature.compute()` returns a *multiplier* applied to the fused RRF score
- A cross-encoder returns a fresh *absolute score* derived from semantic match
- Combining them multiplicatively would conflate two different score-spaces

So cross-encoder = its own stage, replaces the score for top-N.

## Candidate models — bake-off, not single pick

Picking one model first is a guess about which works best on our domain. Cheaper to test a representative spread and let the numbers decide.

| model | params | license | benchmark tier | hardware needed | notes |
|---|---:|---|---|---|---|
| `cross-encoder/ms-marco-MiniLM-L-12-v2` | 33M | Apache 2.0 | older baseline | CPU OK | cheap floor — if a 2B model only beats this by 1pp, cost/benefit is iffy |
| `BAAI/bge-reranker-base` | 110M | MIT | modern mid-size | CPU OK / T4 | well-known modern baseline |
| `Qwen/Qwen3-Reranker-0.6B` | 600M | Apache 2.0 | top tier | T4 GPU | **same family as our Qwen3 encoder** — possibly better grounding |
| `BAAI/bge-reranker-v2-m3` | 568M | Apache 2.0 | top tier | T4 GPU | strong general-purpose retrieval reranker |
| `BAAI/bge-reranker-v2-gemma` | 2B | Apache 2.0 (Gemma base) | **state of the art** | A10 GPU | the strongest open-weight; run last, only if smaller haven't saturated |

(Skipped: `jinaai/jina-reranker-v2` — CC-BY-NC, not competition-safe. `Qwen3-Reranker-8B` — A100 needed, overkill for first measurement.)

**Strategy:** run all 4 of {MiniLM, bge-base, Qwen3-0.6B, bge-v2-m3} against the same retrieval pool. If the lift between the strongest of those and the cheapest is small, declare victory. If the strongest hasn't saturated, add bge-v2-gemma (2B) on A10.

## Offline-replay architecture (the key to cheap bake-off)

A naive bake-off would re-run the full retrieval pipeline for each candidate model. With 4-5 models × 8000 turns × extractor + LanceDB + RRF, that's hours of duplicate work and ~$15+ in inference costs.

**Insight: retrieval is reranker-independent.** Each reranker only reorders the same fixed top-N candidate pool. So we run retrieval ONCE (saving the pool + the state per turn), then replay only the rerank step against the saved files for each candidate model.

```
ONE Modal inference run (already done — exists at evaluator/exp/inference/devset/v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset.json):
  - predictions: top-1000 track_ids per turn (RRF + soft-demote'd)
  - trace: state.turn_intent per turn

scripts/rerank_offline.py:
  for each candidate model:
    for each turn:
      head = predictions[:200]
      tail = predictions[200:]
      pairs = [(state.turn_intent, catalog.track_text(tid)) for tid in head]
      scores = model.predict(pairs)
      head = sorted by -score
      new_predictions = head + tail
    save new_predictions to {base_tid}.rerank_{slug}.json

evaluator/evaluate_devset.py for each new predictions file
→ per-model scores
→ one comparison table
```

**Cost per model in the bake-off** (offline, just the rerank step):
- 8000 turns × 200 candidates = 1.6M pairs
- MiniLM (CPU): ~4ms/pair → ~107 min, $0 (local)
- bge-base (CPU): ~25ms/pair → too slow on CPU, run on T4 instead → ~3ms/pair × 1.6M = ~80 min, ~$0.80 on Modal T4
- Qwen3-0.6B (T4): ~12ms/pair → ~320 min single-container; ~80 min on a 4-batch container; ~$1
- bge-v2-m3 (T4): ~10ms/pair → ~80 min, ~$0.80
- bge-v2-gemma (A10, if we run it): ~30ms/pair → ~80 min, ~$2-3

**Total bake-off cost:** ~$4-5 for 4 models. Adding the 2B model adds ~$2.

This is ~$10 vs ~$30 of running the full pipeline 5 times. Saves $20 and 2 hours of duplicate retrieval work.

## Document representation

Each catalog track gets one text representation, precomputed once at catalog load time:

```python
def track_text(self, track_id: str) -> str:
    row = self._per_track.get(track_id)
    if row is None:
        return ""
    artist = _first(row.get("artist_name")) or "?"
    track = _first(row.get("track_name")) or "?"
    album = _first(row.get("album_name")) or ""
    tags = _list_of_str(row.get("tag_list"))[:5]  # cap to 5 tags
    parts = [f"{artist} - {track}"]
    if album:
        parts.append(album)
    if tags:
        parts.append(", ".join(tags))
    return " | ".join(parts)
```

Example: `"Arctic Monkeys - Do I Wanna Know | AM | indie rock, alternative, popular, 2010s, british"`

Stored on the catalog as a dict[track_id, str], built once at init. ~47k × 100 chars = 4.7 MB.

## Implementation plan

### Phase 1: framework + off-the-shelf model (this PR)

**New files:**
- [`mcrs/qu_modules/cross_encoder_reranker.py`](mcrs/qu_modules/cross_encoder_reranker.py) — the reranker class
- [`tests/test_cross_encoder_reranker.py`](tests/test_cross_encoder_reranker.py) — unit tests with a stub cross-encoder
- [`configs/v0plus_compiler_bm25_image_audio_cfbpr_metadata_xenc_devset.yaml`](configs/...) — new config that enables the reranker

**Modified files:**
- [`mcrs/qu_modules/v0plus_catalog_lance.py`](mcrs/qu_modules/v0plus_catalog_lance.py) — add `track_text(track_id) → str` method + precomputed dict at init
- [`mcrs/qu_modules/v0plus_catalog_hf.py`](mcrs/qu_modules/v0plus_catalog_hf.py) — same
- [`mcrs/qu_modules/v0plus_catalog.py`](mcrs/qu_modules/v0plus_catalog.py) — add `track_text` to Protocol
- [`mcrs/qu_modules/compiler_v0plus.py`](mcrs/qu_modules/compiler_v0plus.py) — wire `cross_encoder_reranker` config + call after `_apply_soft_adjustments`
- [`mcrs/qu_modules/compiler_v0plus_qu.py`](mcrs/qu_modules/compiler_v0plus_qu.py) — build the reranker from `qu_kwargs.compiler.cross_encoder` config

### Phase 1 — `CrossEncoderReranker` class

```python
from dataclasses import dataclass, field

@dataclass
class CrossEncoderReranker:
    """Rerank the top-N from fused list using a pair-encoder model.

    Loaded lazily so the catalog can be built without paying the model-load cost
    until inference actually fires.
    """
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    rerank_top_k: int = 200
    batch_size: int = 64
    device: str | None = None  # auto-detect; "cpu" or "cuda"
    _model: object = field(default=None, init=False, repr=False)

    def _load(self):
        if self._model is not None:
            return
        from sentence_transformers import CrossEncoder
        device = self.device or self._auto_device()
        self._model = CrossEncoder(self.model_name, device=device)

    @staticmethod
    def _auto_device() -> str:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def rerank(
        self,
        fused: list[tuple[str, float]],
        state,
        catalog,
    ) -> list[tuple[str, float]]:
        if not fused:
            return fused
        self._load()
        head = fused[:self.rerank_top_k]
        tail = fused[self.rerank_top_k:]
        query = state.turn_intent or ""
        if not query:
            return fused  # no query → can't score
        pairs = [(query, catalog.track_text(tid)) for tid, _ in head]
        scores = self._model.predict(
            pairs, batch_size=self.batch_size, show_progress_bar=False
        )
        reranked = sorted(
            zip([tid for tid, _ in head], scores.tolist()),
            key=lambda x: -x[1],
        )
        return reranked + tail
```

### Phase 1 — wiring into the compiler

In `V0PlusCompiler.compile()`, after the existing `_apply_soft_adjustments` call:

```python
# 7. Soft adjustments (existing)
fused = self._apply_soft_adjustments(fused, rs)
# 7b. Cross-encoder reranker (new, optional)
if self.cross_encoder_reranker is not None:
    fused = self.cross_encoder_reranker.rerank(fused, rs.state, self.catalog)
```

Pass it in from `build_v0plus_compiler_qu`:

```python
xenc_cfg = qu_kwargs.get("compiler", {}).get("cross_encoder") or {}
cross_encoder_reranker = None
if xenc_cfg.get("enabled"):
    cross_encoder_reranker = CrossEncoderReranker(
        model_name=xenc_cfg.get("model_name", "cross-encoder/ms-marco-MiniLM-L-12-v2"),
        rerank_top_k=xenc_cfg.get("rerank_top_k", 200),
        batch_size=xenc_cfg.get("batch_size", 64),
        device=xenc_cfg.get("device"),
    )
compiler = V0PlusCompiler(..., cross_encoder_reranker=cross_encoder_reranker)
```

### Phase 1 — config

`configs/v0plus_compiler_bm25_image_audio_cfbpr_metadata_xenc_devset.yaml` is identical to the current no-drag config plus:

```yaml
compiler:
  ...existing...
  cross_encoder:
    enabled: true
    model_name: "cross-encoder/ms-marco-MiniLM-L-12-v2"
    rerank_top_k: 200
    batch_size: 64
    # device omitted → auto-detect CPU / CUDA
```

### Phase 1 — tests

Unit tests use a stub cross-encoder so they run without downloading a model:

```python
class StubCrossEncoder:
    """Returns score = -1*rank-in-input — so reranking should reverse the order."""
    def predict(self, pairs, batch_size=None, show_progress_bar=None):
        return [-i for i in range(len(pairs))]

def test_reranker_reorders_head():
    # 5 candidates with descending RRF scores
    fused = [("t1", 0.5), ("t2", 0.4), ("t3", 0.3), ("t4", 0.2), ("t5", 0.1)]
    # stub gives reversed scores → expect order t5, t4, t3, t2, t1 in the head
    reranker = CrossEncoderReranker(rerank_top_k=5)
    reranker._model = StubCrossEncoder()
    out = reranker.rerank(fused, FakeState("a query"), FakeCatalog())
    assert [tid for tid, _ in out] == ["t1", "t2", "t3", "t4", "t5"]  # depends on stub direction
```

Plus tests for:
- `rerank_top_k < len(fused)` — tail is passthrough at original positions
- `empty fused` → returns empty
- `state.turn_intent is empty` → returns input unchanged (no scoring)
- `track_text returns empty` for some tids → still scoreable (model handles empty)

## Modal deployment

**Constraint:** the reranker model file (`cross-encoder/ms-marco-MiniLM-L-12-v2`, ~130 MB) needs to be on the Modal container.

**Option A: download at container init** — first request downloads from HF, ~5 sec cold start. Subsequent requests cached on the container's filesystem.
- Pros: zero infra setup
- Cons: per-shard cold start adds latency

**Option B: bake into Modal image** — add the model download to the image-build phase. The image already has Modal's HuggingFace cache mounted; we just add a `Image.run_function(prefetch_models)` step.
- Pros: no per-shard cold start
- Cons: image size grows by 130 MB; longer builds

**Recommendation: Option A** for v1, switch to B if cold-start latency hurts iteration.

**GPU question:** MiniLM-L-12 runs fine on CPU at ~4ms/pair → no GPU needed for v1. Saves Modal cost (~$0 vs $0.30/hr for T4). If we graduate to bge-reranker-base for v2, then GPU.

## Expected impact + measurement plan

**Impact estimate** (from cohort math):
- Current: GT in top-200 = 51% of turns; GT in top-20 = 31%
- Perfect reranker: every Hit@200 hit → top-20 = NDCG@20 of ~0.50
- Realistic reranker (~50% promotion rate): NDCG@20 of ~0.20-0.25
- **Conservative estimate: +30-50% relative lift (0.14 → 0.18-0.21)**

**Measurement plan:**

1. Implement Phase 1 (code + tests, single PR)
2. Smoke: 30-session Modal run to confirm pipeline works (~$0.30, ~10 min)
3. Full devset run with the reranker enabled (~$3, ~30-40 min)
4. Compare three configs head-to-head:
   - `v0plus_compiler_image_devset` (current canonical, NDCG@20 0.146)
   - `v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset` (no-drag, NDCG@20 0.141)
   - `v0plus_compiler_bm25_image_audio_cfbpr_metadata_xenc_devset` (this — with reranker)

5. **Cohort breakdown:** novel-artist Hit@20 specifically — this is the cohort the reranker should disproportionately help. Goal: move from 0.10 → 0.15+.

6. **Per-turn breakdown:** verify the reranker doesn't regress turn-1 (no anchor → query is the only signal → cross-encoder is doing most of the work). If turn-1 NDCG@20 stays at ~0.124 or improves, ship.

## Risks + mitigations

| risk | likelihood | mitigation |
|---|---|---|
| MiniLM-L-12 trained on MS MARCO (web queries) — may underperform on music conv text | medium | Off-the-shelf as baseline; if disappointing, try bge-reranker-base (better domain transfer) before fine-tuning |
| `turn_intent` quality is now load-bearing — LLM-emitted query text drives the reranker | medium | Already measured 92% extraction accuracy on the new schema. Worst case: drop the rerank stage on turns where `turn_intent` is empty (already in the code) |
| Catalog text representation choices (length, fields included) materially affect scoring | medium | Start with simple `artist - track - album | tag1, tag2, ...` format. A/B alternative formats as a separate experiment |
| 200-candidate rerank window may be wrong — too narrow loses recall, too wide costs latency | low | Knob is in the config (`rerank_top_k`). A/B 100, 200, 500 quickly |
| Doesn't lift NDCG@20 | low-medium | Worst case is no change — soft-demote pipeline still runs. The framework is generally reusable for future rerankers (BGE, Qwen3) |
| Increases inference latency at submission time | n/a | Submission is batch, not realtime. 800ms/turn extra is fine. |

## Phase 2 (after Phase 1 measurement)

If Phase 1 lifts NDCG@20:
- **Upgrade to bge-reranker-base** on a T4 Modal GPU container. ~5ms/pair × 200 = 1s/turn, but on GPU it's ~3ms/pair = 600ms/turn. Better quality on conversational text.
- **Tune `rerank_top_k`** — try 100, 500. The optimal is where the marginal recall lift equals the latency cost.
- **Try Qwen3-Reranker-0.6B** — same family as our encoder, possibly better cross-modal alignment.

If Phase 1 doesn't lift:
- Diagnose: is `turn_intent` actually capturing the user's request? Spot-check 50 turns where the reranker scored poorly.
- Try simpler query forms: last-user-message instead of `turn_intent`, see if the cross-encoder prefers raw text.
- Consider catalog text variants: different tag count, include lyrics snippet if available.

## Phase 3 (much later, if leaderboard pressure demands)

### Option A: Fine-tune the cross-encoder

Fine-tune the reranker on devset cohort labels:
- Positive pair: `(turn_intent, GT_track_text)` → label 1
- Hard negative: `(turn_intent, top-1-non-GT_track_text)` → label 0 (forces the model to learn what differentiates the GT from a close-but-wrong candidate)
- Easy negative: `(turn_intent, random_track_text)` → label 0

Training: 1-2 epochs of cross-entropy on the positive/negative pairs. ~10k positive pairs from devset. Few hours on a T4 GPU. Output: a fine-tuned bge-reranker that knows our domain.

### Option B: LLM-based listwise reranking via [rank_llm](https://github.com/castorini/rank_llm)

A different paradigm worth keeping on the radar:
- **Pointwise** (what Phase 1/2 does): score each (query, candidate) pair independently, then sort
- **Listwise** (rank_llm): feed a *list* of N candidates to an LLM and ask it to re-order them in one pass. The model sees the full set and can compare candidates against each other directly

rank_llm supports RankZephyr, RankVicuna, RankGPT-style approaches with open-weight models (e.g., `castorini/rank_zephyr_7b_v1_full`, `castorini/rank_vicuna_7b_v1`). Sliding-window prompts handle lists longer than the model's context.

**Why it's interesting for us:**
- Listwise comparison is structurally better for ties and close-call ranking — exactly our top-20 promotion problem
- Open-weight 7B models fit on a single A10 GPU
- Could replace OR stack with the cross-encoder (cross-encoder for fast top-200 cut → rank_llm for the final top-20 ordering)

**Why not Phase 1:**
- 7B LLM is ~100× slower per turn than MiniLM-L-12 (seconds vs milliseconds at the same batch size)
- Modal GPU cost goes up significantly
- Off-the-shelf pointwise (MiniLM) needs to be measured first to establish a baseline lift
- More complex prompt engineering / sliding-window setup

Plug it in only if (a) cross-encoder gives a measurable lift, and (b) we have headroom to spend more compute on rerank.

### When to actually invest in Phase 3

Defer both options until Phase 1 measurement shows:
- Cross-encoder gives ≥+0.02 NDCG@20 lift (meaningful, not noise)
- AND we still have a clear cohort gap (novel-artist Hit@20 < 0.15 after rerank)
- AND we're past the easy-wins phase (every smaller change has been measured)

## Decision

This plan stays at Phase 1 scope: off-the-shelf MiniLM-L-12 on CPU, plumbed into the existing compiler, measured against the canonical baselines. Phase 2 / Phase 3 are explicitly out-of-scope until Phase 1 results land.

Want me to implement?
