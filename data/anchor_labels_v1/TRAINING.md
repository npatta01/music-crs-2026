# Using these labels for retrieval & reranking

How to consume the POSITIVE / NEGATIVE / DROP / HOLD labels — and the one caveat
that changes everything. Read `DATASET_CARD.md` first for the schema; the data
ships as a GitHub Release (`gh release download anchor-labels-v1 -p '*.jsonl.gz'`),
not in this folder.

> Reviewed against the repo code (claims below cite `file:line`). TL;DR: the
> "labels fight nDCG" thesis is **verified for the DEVSET official harness**;
> the **blind/final leaderboard is NOT this script** (extra server-side metrics —
> see §0 Scope), so treat the devset tension as solid but **don't assume it
> transfers 1:1 to the blind score**. Headline recommendation: **don't feed
> anchor-NEGATIVE grades into the *submitted* reranker** — keep it label-pure,
> run the anchoring fix as a product model + the judge/diversity axes.

---

## 0. The caveat that drives all of this: eval GT = the played track

The challenge's nDCG ground truth for a turn is **the track the system actually
played at that turn**, and there is exactly **one GT track per turn**:
- `evaluator/make_ground_truth.py:22-44` — `parsing_groundtruth` returns the
  `music`-role row of the target turn (the played track); one `ground_truth_track_id`
  per `(session, turn)`.
- `evaluator/evaluate_devset.py:135` scores against the singleton `[gt_id]`;
  `metrics_recsys.py` sets `n_rel = 1`. Single-GT is structural.
- **Smoking gun:** the *current* LambdaMART relevance label is
  `features_v9.py:306` → `"label": int(tid_ == gt)` — **1 iff the candidate is the
  played GT track, else 0**. The deployed reranker is trained to rank the played
  track to the top. Our labels grade that *same* played track NEGATIVE on **58% of
  train turns**. Feeding our NEGATIVEs in as low grades literally **inverts the
  label on the metric's own GT.**

> **Scope — devset vs blind (read this).** The above is the **official DEVSET**
> framework (`evaluator/readme.md:3`) and is verified. The **blind sets (Blind A/B)
> — which decide the actual leaderboard/winners — are explicitly NOT scored by this
> script** (`readme.md:65-71`: "Blind set evaluation is not supported … full
> evaluation on blind sets includes **additional metrics kept server-side**").
> We can't see the blind GT or its full metric, and the blindset is structurally
> different (single prediction per session — anchoring may not even arise without a
> prior played track). So: the played-track / single-GT / "labels fight nDCG"
> finding is **solid for the devset**, **unverified for the blind/final score** —
> which, given the server-side metrics likely weight response/judgment quality,
> may actually *favor* the anchoring fix. Don't over-fit your strategy to the
> devset nDCG tension alone.

So on the **devset**, our labels encode a **cleaner notion of relevance than its
GT**; the anchoring negatives point *away* from the GT track. Consequences (devset):
- nDCG is single-GT, so surfacing a *different* artist above the anchored GT
  **lowers** that turn's nDCG. The anchoring fix and raw nDCG are opposed by
  construction.
- Composite = `0.50·nDCG@20 + 0.10·catalog_diversity + 0.10·lexical + 0.30·(judge−1)/4`.
  **The judge (0.30) + lexical (0.10) score the generated RESPONSE TEXT**, not the
  tracks — a separate generator effort (currently `lm_type: dummy`), grounded in
  the **top-1 track only** (`explanation_generation.md:21,28`); the team's own spec
  calls this front *"independent of retrieval"*. So **these track-labels do not
  directly move the judge.** Their only path to it is changing the **top-1** track
  to a different artist — which is the nDCG@1 GT, so it **trades off nDCG**, not
  free. *(Note: `docs/evaluation.md` calls nDCG@10 the official primary while the
  composite weights nDCG@20 — both single-GT, so the tension holds either way.)*
- Anchoring is only **5% of dev turns** (vs 18.6% train) → invisible on dev. Build
  a **held-out anchoring-rich eval slice**; don't judge the fix by dev nDCG.

> **train vs dev** — train: 50% same-artist · 51% liked · 33% POSITIVE · 18.6%
> anchoring. dev: 27% · 88% · 68% · 5.0%. The label-prior shift is fine for a
> ranking/contrastive model; don't build a thresholded classifier on it.

**Bottom line:** a strong signal for a *cleaner retriever and the judge/diversity
axes*; **not** a drop-in for maximizing nDCG-against-the-played-track.

---

## 1. The core framing: ranking-negative, NOT pool-removal

A NEGATIVE/anchoring label means "for *this* conversation, the played track was a
bad answer." Two ways to use that:

| | Slate respects the ask? | GT track still reachable? | nDCG on that turn |
|---|---|---|---|
| **A) pool removal** (ban the track) | yes | **no — banned** | **0** (you deleted the GT) |
| **B) ranking hard-negative** (down-weight) | yes (top of slate) | **yes** (still in the set) | preserved-ish |

Always **B**. Two terms: **query-local** — bad *for this conversation only* (the
same track is a perfect answer elsewhere; mine it attached to its query, never a
global blocklist). **hard negative** — looks superficially relevant (right
genre/era, just-played), which is what teaches the fine distinction.

---

## 2. Bi-encoder (retriever) — labels → contrastive examples

Encodes query and track separately (conv→track dual encoder, MNRL/InfoNCE-family
loss — `b1_local.py`, GATE-0 results); retrieves by nearest-neighbor → it
**defines the candidate pool**.

**Data:**
- **POSITIVE turn** → `query` = conversation, `positive` = played track. Clean,
  metric-aligned. This is the main positive source.
- **anchoring / content-violation turn** → the played track is a **query-local
  hard negative** (in-batch / mined), paired with positives from POSITIVE turns.
  *Most anchoring turns do not carry their own positive:* only ~**12%** have a
  later same-session POSITIVE by a *different* artist (~2.4k of 19,813), so
  reconstructing a "satisfied-continuation positive" is a **minor** supplement,
  not the main path. Lead with the hard-negative use.
- **DROP / HOLD** → excluded. `confidence_weight` → loss/sample weight.

**Unique risk (applies to *all* NEGATIVE subtypes, not just anchoring):** the
retriever controls *what gets retrieved at all*. Push a NEGATIVE track too hard
and it falls **out of the top-K pool** — and ~5% of the time that track *is* the
GT, so that's **lost recall, unrecoverable by reranking**. Mitigate: moderate
margin/temperature; retrieve a **deep pool (top-1000)**; gate on `% GT not in
top-1000` (`evaluate_devset.py`) so you never push a GT out. Frame the retriever's
job as **"add, don't subtract"**: bring different-artist tracks *into* the pool
*alongside* the anchored GT (recall- and diversity-positive, metric-neutral).

---

## 3. Reranker (LambdaMART) — labels → graded relevance per query group

`scripts/rerank/train_v9.py` (`objective="lambdarank"`, grouped per
`(session,turn)`); serving reorders the pool (`lgbm_reranker.py`), never adds/
removes. Natural home for query-local ranking — **but** see §0: the deployed
reranker's label is `int(tid==gt)`, so anchor NEGATIVEs invert it on the GT.

**Two distinct rerankers — keep them separate:**
- **Submitted (leaderboard) reranker → keep label-pure.** Train exactly as today
  (`label = int(tid==gt)`, played GT = positive). Do **not** feed anchor NEGATIVEs
  as low grades; you'd be demoting the metric's own GT.
- **Product / anchoring reranker (not submitted, for the held-out eval)** → grade
  by our labels: POSITIVE high, anchoring/content NEGATIVE low, **DROP** (in-pool,
  content-valid but disliked) → a *middle* grade between POSITIVE and NEGATIVE (or
  exclude — do **not** grade it as low as anchoring, or you teach the ranker to
  demote on-request tracks), HOLD excluded. `confidence_weight` → instance weight.

**Unique risk:** can't hurt *pool* recall, but **can bury the anchored GT below
the top-20 cutoff** by over-demotion. Cap the demotion so the GT stays in the 20.

---

## 4. Do they differ? Yes.

| | Bi-encoder (retriever) | Reranker (LambdaMART) |
|---|---|---|
| Label → | `(query, pos, hard-neg)` examples | graded labels in per-query groups |
| Controls | **what's in the pool** (recall) | **the order** of a fixed pool (precision) |
| Anchoring signal | pull different-artist *into* the pool | push the anchored track *down* the slate |
| Over-applied → you lose | GT **from the pool** → unrecoverable | GT **below rank 20** → recoverable (cap) |
| Risk / ceiling | higher leverage, higher risk | safer to iterate, lower ceiling |

"Safer to iterate" ≠ "use in the submitted model." The *submitted* reranker is
where the metric conflict is **most** direct (it re-grades the GT). Iterate the
**product** reranker freely; keep the **submitted** one label-pure.

---

## 5. Recommended strategy (ranked — leaderboard vs product)

The single-GT tension **plus** the fact that the judge scores *prose, not tracks*
mean these labels have **no clean positive home in the submitted ranking model**.
In order of ROI:

1. **Use the POSITIVE turns for retrieval recall — the one leaderboard-safe use.**
   Clean (query → played-track) positives that *match* the nDCG GT. Improve the
   retriever/reranker on the ~33% of turns where the played track was genuinely
   right. This is metric-aligned; do it.
2. **A1 — keep the SUBMITTED reranker label-pure.** It trains on
   `label = int(track==gt)` (`features_v9.py:306`); anchor-NEGATIVE grades invert
   the metric's own GT. Don't feed them in.
3. **A4 — anchoring NEGATIVES → product retriever + held-out slice (+ maybe blind).**
   "Add don't subtract": pull different-artist tracks into the top-1000 pool
   alongside the anchored GT, as moderate-margin hard negatives; gate on
   `% GT not in top-1000`. **Not** the submitted model; measure on a held-out
   anchoring-rich slice. The blind eval *may* reward this (unverified — §7).
4. **The judge (0.30) + lexical (0.10) is a SEPARATE workstream — not these labels.**
   It scores the generated response *text* (prose, grounded in the **top-1 track**,
   `lm_type: dummy` today). These track-labels reach it **only** via a better top-1,
   which trades off nDCG. The judge lever is the **response-gen sweep**
   (`docs/superpowers/specs/2026-06-13-response-gen-judge-sweep-design.md`) — it
   tunes the prose/model/state, independent of which tracks you retrieve. Don't
   credit these labels toward the judge.
5. **A2 — clean positives (low risk).** Down-weight / stop trusting the synthetic
   `MOVES` on the **6,234 poisoned-MOVES** turns wherever it leaks into auxiliary
   positives. Removes noise without fighting the metric.
6. **A5 — one reranker with capped asymmetric demotion (only if A1 is off the
   table).** Anchoring/content NEGATIVE = 0 **only when the track is not the GT**;
   when anchored == GT keep it ≥ the positive floor. Train-time join against
   `make_ground_truth`. Complex; still partly fights the metric on the 6,234
   poisoned-MOVES turns.

---

## 6. Recommended use by label (product / retriever model)

| label | retriever (bi-encoder) | product reranker |
|---|---|---|
| POSITIVE | positive | high grade |
| NEGATIVE · anchoring | query-local hard negative (moderate margin) | low grade |
| NEGATIVE · content_violation | query-local hard negative (moderate margin) | low grade |
| DROP (fit-but-disliked) | exclude | **middle** grade (or exclude) — not as low as anchoring |
| HOLD (unverifiable) | exclude | exclude |
| weight | sample/loss weight = `confidence_weight` | instance weight = `confidence_weight` |

(The **submitted** leaderboard reranker stays on `label = int(tid==gt)` — see §3/§5.)

---

## 7. Open questions to verify before a training run (load-bearing)

1. **The blind/final eval is unknown — don't over-fit to the devset tension.**
   The devset harness is official (`evaluator/readme.md:3`) but blind A/B use
   **additional server-side metrics** (`readme.md:65-71`). The whole "labels fight
   nDCG" conclusion is a **devset** statement. The blind score — which decides the
   leaderboard — may weight response/judgment quality (where the anchoring fix
   helps) and the blindset may be structurally single-turn (no anchoring at all).
   Find out (challenge page / Codabench / a probe submission) what the blind metric
   actually rewards before committing a leaderboard strategy.
2. **Confirm GT = one played track per turn on a built artifact.** Code says yes
   (`make_ground_truth.py:22-44`, `evaluate_devset.py:135`), but the GT json
   wasn't materialized when reviewed — re-run `make_ground_truth.py` and diff
   against the played track for 2–3 devset turns. The devset reasoning rests on this.
2. **nDCG@10 vs @20** — reconcile `docs/evaluation.md` (@10 "official primary")
   with the Codabench composite (@20). Doesn't change the tension; do change which
   number you report.
3. **Net composite A/B:** does demoting the anchored GT on ~5% of dev turns cost
   more nDCG (×0.50) than it gains in judge (×0.30) + diversity (×0.10)? Measure
   before trusting either direction.
4. **Positive recovery is ~12%** (measured: ~2.4k of 19,813 anchoring turns have a
   later same-session different-artist POSITIVE). Decide whether that thin slice is
   worth the mining, or whether anchoring turns are negatives-only.
