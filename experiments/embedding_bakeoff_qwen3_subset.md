# Qwen3-Embedding Bake-Off — encoder size × tags template × query mode (subset)

**Date:** 2026-06-01
**Status:** `analyzed` — measurement run, **not** a leaderboard entry (subset pool, see caveats).
**Branch:** `claude/embedding-tags-metadata-nvrRM`
**Script:** [`modal/embedding_bakeoff.py`](../modal/embedding_bakeoff.py) · **Handoff:** [`modal/EMBEDDING_BAKEOFF_HANDOFF.md`](../modal/EMBEDDING_BAKEOFF_HANDOFF.md)
**Raw artifacts:** [`analysis/embedding_bakeoff/artifacts/`](analysis/embedding_bakeoff/artifacts/) (`fuller_seed0.json`, `fuller_seed1.json`, `smoke_seed0.json`)

## What this answers

Two questions the leaderboard's NDCG@20-only view couldn't separate:

- **A — encoder size.** Does a bigger metadata encoder (Qwen3-Embedding **4B / 8B**) retrieve better than the **0.6B** the catalog was built with — specifically on **deep recall** (Recall@100 / Recall@1000), the real job of a first-stage retriever before a reranker?
- **B — tags representation.** For the attributes/tags branch (which *hurt* in the v0+ ablation), is the damage from **formatting**? Clean test: `attributes_raw` (existing tag-dump, `music attributes, tags :rock,melancholic,90s`) vs `attributes_nl` (NL rewrite of the same tags, `This is a rock, melancholic and 90s track.`) — same tag info, same coverage, only the template differs.

## Setup

- **Subset pool design** (no full re-embed): pool = all gold tracks for the sampled turns + random negatives. Every (model × variant × mode) ranks within the *same* pool against the *same* raw-conversation queries, scored with the repo's own `evaluator.metrics.metrics_recsys.compute_metrics`. Apples-to-apples across models; absolute recall is inflated vs the full 47k catalog.
- **Fuller run (headline):** `--num-sessions 150 --pool-size 8000`, **1200 turns**, gold=1170, `max_length=512`, **two seeds (0 and 1)**. Modal H100, exit 0 both seeds.
- Doc **coverage** ≈100% (metadata 100%, attribute variants 99.8%) — so attribute variants were **not** recall-capped on this pool; the raw-vs-NL comparison is clean.
- Smoke (10 sessions / pool 2000) confirmed the path end-to-end first; numbers below are the fuller run.

## Headline — fuller run, seed-averaged (seed 0 & seed 1, 1200 turns, pool 8000)

Recall is over the **subset pool** — relative ordering only, **not** leaderboard-comparable.

### `metadata` document (the reference branch)

| model | mode | NDCG@20 | Recall@100 | Recall@1000 |
|---|---|---:|---:|---:|
| 0.6B | symmetric | 0.083 | 0.301 | 0.527 |
| 4B | symmetric | 0.126 | 0.481 | 0.768 |
| 8B | symmetric | **0.127** | **0.531** | **0.841** |
| 0.6B | instruct | 0.097 | 0.358 | 0.565 |
| 4B | instruct | **0.135** | 0.518 | 0.793 |
| 8B | instruct | 0.133 | **0.570** | **0.855** |

### Tags branch — `attributes_raw` vs `attributes_nl` (same model + mode = same coverage)

| model | mode | variant | NDCG@20 | Recall@100 | Recall@1000 |
|---|---|---|---:|---:|---:|
| 0.6B | symmetric | raw | 0.049 | 0.253 | 0.635 |
| 0.6B | symmetric | **nl** | **0.069** | **0.309** | **0.674** |
| 4B | symmetric | raw | 0.067 | 0.318 | 0.705 |
| 4B | symmetric | **nl** | **0.098** | **0.412** | **0.811** |
| 8B | symmetric | raw | 0.107 | **0.447** | 0.817 |
| 8B | symmetric | nl | 0.098 | 0.435 | **0.821** |
| 0.6B | instruct | raw | 0.042 | 0.245 | 0.641 |
| 0.6B | instruct | **nl** | **0.074** | **0.333** | **0.701** |
| 4B | instruct | raw | 0.062 | 0.291 | 0.697 |
| 4B | instruct | **nl** | **0.103** | **0.433** | **0.828** |
| 8B | instruct | raw | 0.099 | 0.430 | 0.795 |
| 8B | instruct | **nl** | 0.102 | 0.434 | **0.828** |

Per-seed tables and the smoke run are in the JSON artifacts. **Both seeds agree on every ordering claim below** (the deltas are far larger than the seed-to-seed wobble, which is ≤~0.013 on any cell).

## Verdict (against handoff §6)

### A — encoder size: a real recall lever, against the going-in prior

- **0.6B → 4B is a large, consistent lift.** `metadata` Recall@100 (sym) **0.30 → 0.48** (+60% rel), Recall@1000 **0.53 → 0.77**; NDCG@20 **0.083 → 0.126**. The prior assumption ("encoder size isn't the lever") does **not** hold on deep recall.
- **4B → 8B is deep-recall-only.** NDCG@20 is flat (0.126 ≈ 0.127 sym; 0.135 vs 0.133 instruct — 4B even edges 8B at the head), but **Recall@1000 keeps climbing 0.77 → 0.84** and Recall@100 0.48 → 0.53. So 8B's gain over 4B is exactly the signal NDCG@20-only misses: a deeper, richer first-stage pool, not better head ranking.
- **Takeaway:** if re-embedding the full catalog, **4B is the sweet spot** for head + most of the recall; **8B only pays off if a downstream reranker can exploit the deeper Recall@1000 tail** (it has nothing extra to offer top-20 directly). Either is a big step up from the 0.6B the catalog ships with — quantify the full-catalog re-embed cost before committing.

### B — tags template: NL formatting helps at the encoder size we actually use

- **`attributes_nl` beats `attributes_raw` clearly at 0.6B and 4B**, both modes, both seeds (e.g. 4B sym Recall@100 **0.412 vs 0.318**, NDCG **0.098 vs 0.067**). Same tags, same coverage → the v0+ tags branch was being hurt by the **raw tag-dump formatting**, not (only) by the tag vocabulary. The catalog's live encoder is **0.6B**, so for the production attributes branch this is a **cheap, high-value fix** (rewrite the template, re-embed only the attributes column).
- **The advantage vanishes at 8B** (raw ≈ nl; raw marginally higher on NDCG). A strong enough encoder parses the raw tag-dump fine — so "formatting" is an encoder-capacity problem, and the fix matters precisely because we're on the small encoder.
- **Bonus, easy to miss:** at 0.6B and 4B, `attributes_nl` Recall@1000 actually **exceeds `metadata`** (0.6B: 0.674 vs 0.527; 4B: 0.811 vs 0.768). Tags carry **complementary deep-recall** coverage that the metadata branch misses — consistent with tags being *additive in fusion* even though their head (NDCG) is weak. This argues for keeping an **NL-rewritten tags branch as a recall contributor in the fusion ensemble**, not demoting it outright. (At the head, `metadata` still dominates both attribute variants — that was never the question.)

### Query mode: instruct ≥ symmetric on metadata — a free win

- The Qwen3 asymmetric **instruct** query prefix beats `symmetric` on `metadata` across all three models and both seeds (Recall@100: 0.30→0.36 at 0.6B, 0.48→0.52 at 4B, 0.53→0.57 at 8B; NDCG up too). It's a query-side-only change (no re-embed), independent of encoder size — **adopt it.** On the attributes branch the effect is smaller/mixed.

## Caveats

- **Subset pool inflates absolute recall** — do not compare these numbers to the leaderboard or read Recall@1000≈0.85 as catalog-wide. Compare models/variants/modes **to each other within this run**.
- `max_length=512` right-truncates long 8-turn conversations; consistent across models so the comparison is fair. A `--max-length 1024` re-run could shift absolute levels.
- Re-encoded 0.6B ≠ the organizer's stored 0.6B vectors (dtype/normalization differ); all three models go through one identical code path here, which is the point.
- Attribute variants are **tags-only** (tempo/key/chord aren't in the published metadata).

## Recommended next steps

1. **Query side (cheapest, no re-embed):** turn on the Qwen3 **instruct** prefix for the dense-text/metadata branch.
2. **Tags branch (cheap):** re-embed only the attributes column with the **NL template** (`_render_attributes_nl`) and re-evaluate it as a *fusion recall* branch (its Recall@1000 > metadata at 0.6B/4B).
3. **Encoder size (costly, quantify first):** scope a full-catalog re-embed at **4B**; reserve **8B** for the case where the reranker demonstrably converts the deeper Recall@1000 pool. This is the only step that touches the 47k-track catalog vectors.

> **No leaderboard row:** the leaderboard is devset NDCG@20 on the *full* catalog; this is a subset-pool measurement. Subset recall must not be mistaken for a headline metric.
