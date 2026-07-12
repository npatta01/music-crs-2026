# Cross-Encoder (Qwen3-Reranker) for Music-CRS — Exploration Report

**Date:** 2026-06-21/22 · **Status:** complete · **Author:** Claude (agent session) · **Branch:** `claude/angry-tereshkova-f218e8`

**Skip to:** [TL;DR](#tldr-read-this-first) · [E1 labeler](#3-experiment-1--offline-data-labeler--works-modest) · [E2 ablation](#4-experiment-2--model--prompt--context-ablation-what-makes-the-ce-see-the-gt) · [E3 serving reranker](#5-experiment-3--serving-reranker--filter--the-main-negative-result) · [Root cause](#6-root-cause-verified-by-an-adversarial-review--offline-tests) · [Cost](#8-cost-analysis-modal-feature-generation) · [Reproduce](#9-how-to-reproduce) · [Limitations](#95-limitations--what-was-not-tested) · [Next steps](#10-recommendation--next-steps)

This is a standalone record of an exploration into whether an off-the-shelf **Qwen3-Reranker**
cross-encoder can improve the conversational music recommender. It covers what was tested, the
results, the exact prompts and inputs/outputs, the Modal cost analysis, how to reproduce, and the
recommended next steps. It is written to be read on its own.

---

## TL;DR (read this first)

We evaluated a cross-encoder (Qwen3-Reranker, 0.6B / 4B / 8B, used **zero-shot** — never fine-tuned)
for **three different roles**. Verdicts:

| Role | Question | Verdict |
|---|---|---|
| **Serving reranker / filter** | Rerank the LightGBM top-K at inference to improve nDCG@20? | **❌ DEAD.** Net-negative nDCG@20 in *every* mode (replace, RRF-fusion, filter, promote) and across a full threshold sweep. Do **not** add it to the blindset. |
| **Offline data labeler** | Clean false-negatives & mine soft-positives for bi-encoder training? | **✅ WORKS, but modest.** Use **4B + full-conversation query**; mine via *cross-encoder proposes → independent LLM judge confirms*. ~10% of mined negatives are genuine false-negatives. |
| **LightGBM feature** | Add the CE score as a 145th reranker feature (retrain)? | **➖ Not tested here**, but prior work logged **+0.022 nDCG on the hard_pivot lane** ("bankable"). Costs ~$2–40 on Modal to build the feature (see [Cost](#8-cost-analysis-modal-feature-generation)). Modest ROI. |

**Bottom line:** the cross-encoder is **not** a serving reranker for this pipeline — it cannot beat
the label-trained LightGBM and it *damages* the turns the pipeline already gets right. Its only
clear value is **offline** (labeler / teacher). The higher-ROI lever for retrieval quality is the
**bi-encoder retriever**, not the cross-encoder.

**Why the serving role fails (one sentence):** on the real task — ranking the ground-truth track
against the *other ~100 already-plausible candidates in the pool* — the zero-shot cross-encoder is
at **chance** (AUC 0.51 on the turns that matter), and any reranking aggressive enough to help the
~25% of "missed" turns also demotes the ground-truth on the ~75% of "already-correct" turns.

**Key terms.** *nDCG@20* — score of the single ground-truth (GT) track's rank in the top 20 (1.0 at
rank 1, 0 below 20). *recoverable miss* — a turn the deployed pipeline got wrong (GT not in top-20)
but where the GT is still in the candidate pool, so a reranker *could* help. *control* — a turn
already correct (GT in top-20), where a reranker can only *hurt*. *floored GT* — the cross-encoder
scored the true track ≈0 (effectively didn't recognize it). *pool_k* — the 500 candidates the
LightGBM reranks per turn. *clean-negative rate* — fraction of mined negatives the CE scores below
the GT. *net ΔnDCG* — gains on misses minus losses on controls, weighted by how common each is.

---

## 1. Context

**The system.** Music-CRS (RecSys 2026 challenge). Given a multi-turn conversation, retrieve 20
tracks from a 47k-track catalog. Deployed pipeline:

```
retrieval branches (lexical + dense)  →  RRF fusion  →  LightGBM reranker (v10)  →  top-20
```

The LightGBM reranker scores `pool_k = 500` candidates per turn using 144 features. Scoring metric
of interest: **nDCG@20** with a **single** ground-truth (GT) track per turn:
`nDCG@20(rank) = 1/log2(rank+1)` if `rank ≤ 20` else `0`. (The CodaBench composite is
`0.50·nDCG@20 + 0.10·catalog_div + 0.10·lexical_div + 0.30·(judge−1)/4`; nDCG@20 is the dominant,
single-GT-rank-driven term.)

**Three models — don't confuse them.** This exploration touched three distinct models:

| Model | What it is | Trained here? |
|---|---|---|
| **Cross-encoder** — `Qwen/Qwen3-Reranker-{0.6B,4B,8B}` | Scores a `(query, candidate)` pair → relevance via a yes/no token-probability | **No** — used zero-shot |
| **LightGBM reranker (v10)** | The deployed ranker; orders the 500-candidate pool | Already trained (on a 30k-turn subsample) |
| **Bi-encoder** — fine-tuned `Qwen3-Embedding-0.6B` | The conv→track retriever (separate GATE-0 work) | Yes (separate effort) |

**What this report is about:** the **cross-encoder**, in the three roles above.

---

## 2. How the cross-encoder is scored (shared mechanics)

All experiments score a `(query, document)` pair with the Qwen3-Reranker yes/no template and read a
single relevance probability `P(yes) ∈ [0,1]`. **The `system` line is the model's *fixed, official*
Qwen3-Reranker scaffold** (do not rewrite it — it's how the yes/no head was trained); the
**task-specific, music context goes in the `<Instruct>` field**. Schema (byte-identical to the
deployed `mcrs/qu_modules/cross_encoder_reranker.py` Qwen3 backend):

```
<|im_start|>system
Judge whether the Document meets the requirements based on the Query and the Instruct provided.
Note that the answer can only be "yes" or "no".<|im_end|>
<|im_start|>user
<Instruct>: {instruct}      ← MUSIC task description goes here (see below)
<Query>: {query}            ← the conversation (current request + prior context)
<Document>: {document}       ← the candidate track text
<|im_end|>
<|im_start|>assistant
<think>

</think>
```

**Filled example (a real phase-3 call — note it *is* music-specific via `<Instruct>` + the query/doc):**

```
<|im_start|>system
Judge whether the Document meets the requirements based on the Query and the Instruct provided.
Note that the answer can only be "yes" or "no".<|im_end|>
<|im_start|>user
<Instruct>: You are evaluating candidate tracks for a music recommendation system. Judge whether
the candidate track satisfies the user's CURRENT (last) request; use any earlier context only to
resolve references.
<Query>: user (previous): play something chill
recommended: Bonobo - Kong
user (current request): now something more upbeat and danceable
<Document>: Justice - D.A.N.C.E. | Cross | electronic, dance, french house, funk, upbeat
<|im_end|>
<|im_start|>assistant
<think>

</think>
```

Score = `softmax([logit("no"), logit("yes")])[1]` from the final-token logits. Left-padded batches.
The exact `<Instruct>` strings used (concise vs elaborate) are in §4 and the Appendix.

**Document text** (the candidate track) = the catalog `track_text`:
`"{artist} - {title} | {album} | {tag1, …, tag5}"` (no audio, no "known-for" line).

---

## 3. Experiment 1 — Offline data labeler (✅ works, modest)

**Goal.** Can the cross-encoder clean the bi-encoder's mined hard-negatives (drop false-negatives)
and surface "soft positives" (valid tracks beyond the single GT)? This is an **offline** use on the
**train** split — no serving cost.

**Method.** Two stages, non-circular:
1. `probe_xenc_mining.py` — score, per train MOVES turn: the GT, the mined `negs_filt`, the
   in-session `DOES_NOT` tracks (diagnostic), and ~20 random catalog tracks (easy-negative floor).
2. `judge_softpos.py` — an **independent** judge (DeepSeek-V3 via OpenRouter, a *different* model
   family from Qwen) rates the cross-encoder's flagged candidates VALID/INVALID, breaking
   circularity.

**Independent judge prompt** (`judge_softpos.py`):

```
SYSTEM: You are a STRICT music recommendation judge. Given a user's request from a conversation
and ONE candidate track, rate how SPECIFICALLY the track matches what the user actually asked for
(genre / mood / era / artist intent). Be discriminating: a track that is merely generically
listenable but does not match the specific request is NOT a good match. Answer with exactly one
word:  GOOD = clearly matches the specific request | WEAK = only loosely related / generic | BAD.
USER: User request:\n{query}\n\nCandidate track: {track_text}\n\nHow specifically does this track
match the request? Answer GOOD, WEAK, or BAD.
```
(A first, lenient phrasing rated *random* tracks VALID 100% — non-discriminating. The strict rubric
above fixed it: random→GOOD 2%, the validity gate.)

**Results** (300 train MOVES turns; 90 turns / 194 flagged candidates judged):

| metric | value | reading |
|---|---|---|
| AUC(GT vs random) — kill-switch | **0.90** | CE separates GT from junk → usable labeler |
| AUC(GT vs in-session DOES_NOT) | **0.52** (≈chance) | DOES_NOT is *request-relevant*, **not** a clean negative |
| GT `P(yes)` median | **0.045** (bimodal: 29% ≥0.5, 51% <0.05) | CE floors the GT on ~half of turns (see E2) |
| mined-neg ranks above its GT | 31% | "false-negative candidates" |
| Judge: random GOOD | 2.2% | validity gate passes |
| Judge: GT GOOD | 44.4% | even the true GT is "clearly good" only ~44% (text ceiling) |
| Judge: flagged-candidate GOOD | **33.5%** | → **~10% of mined negs are genuine false-negatives** (31%×33.5%) |

**Takeaways.**
- **Mining must be two-stage** (CE proposes → judge confirms): raw CE flags are only 33.5% precise.
- **Negative cleaning:** remove only judge-confirmed flags (~10% of negs). Don't drop all 31% — most
  are CE noise (driven by the floored GT), and dropping them strips the hardest *true* negatives.
- **Soft positives:** ~0.7 judge-confirmed/turn; use them only as **false-negative masks**, never as
  positive rows (that collapses the MNRL contrastive signal).
- **`DOES_NOT` is not a clean negative** for a retrieval bi-encoder (AUC 0.52). It's request-relevant
  but unengaged — an *engagement* signal, not a *relevance* one.

---

## 4. Experiment 2 — Model / prompt / context ablation (what makes the CE "see" the GT)

**Goal.** The labeler's bottleneck is that the small CE "recognizes" the GT (gives it non-trivial
`P(yes)`) on only ~half of turns. Does a **bigger model**, a **better prompt**, or **more context**
fix it? Script: `probe_xenc_ablation.py` (n=150, all metrics rank-based so local-0.6B and Modal-4B
are comparable; **placebo** arm = matched-length filler to detect token-inflation).

**Why the 0.6B GT score is low — it's legibility, not a bug.** Same query/doc/scoring; only the
weights differ, and 4B scores the same GTs at median 0.764 vs 0.6B's 0.045. The split:

| | GT artist appears verbatim in the conversation |
|---|---|
| turns the CE *recognizes* (P(yes)≥0.05) | **88%** |
| turns the CE *floors* (P(yes)<0.05) | **31%** |

So the small CE essentially only "recognizes" the GT when the artist is **lexically present**; when
the GT must be *inferred* (the hard, valuable case), it collapses to ~0. Bigger model = more world
knowledge = recovers many of those.

**Headline metric = clean-negative rate** (fraction of mined negs scoring below the GT) on the
**unrecognized half** (the bottleneck):

| model / variant | clean-neg on unrecognized half | AUC(GT vs random) |
|---|---|---|
| 0.6B / base | 0.507 | 0.90 |
| 4B / base | 0.658 | 0.96 |
| 4B / **richquery** (full prior conversation + profile + goal) | **0.741** | 0.97 |
| 8B / base | 0.732 | 0.96 |

**Takeaways.**
- **Model size is the lever** (0.6B→4B = +0.15; 4B→8B = +0.07, diminishing). Use **4B**.
- **Full-conversation context is a *real* win on the big model** (4B/richquery beats the placebo by
  +0.11 — not token inflation), the opposite of 0.6B where prompt changes ≈ placebo (pure inflation).
- **8B ≈ 4B+richquery** — not worth the extra cost over 4B+context.
- **Use 4B + richquery as the labeler.**

---

## 5. Experiment 3 — Serving reranker / filter (❌ the main negative result)

**Goal.** Add the cross-encoder as a **3rd phase** at inference: take the LightGBM top-`k=100` and
rerank/filter it, hoping to lift nDCG@20 (especially for the blindset, which is final-turn-only and
cheap to run). Script: `probe_xenc_zeroshot.py` (4B, fp16, arm B query).

**Eval set.** Devset turns split into:
- **recoverable misses** (`hit=0 ∧ oracle=1`: GT not in deployed top-20 but in the pool) — where a
  reranker *could* gain. Population ≈ 1,709; sampled 397.
- **controls** (`hit=1 ∧ oracle=1`: GT already in top-20) — where a reranker risks *regression*.
  Population ≈ 4,865; sampled 200.

**Modes tried** (all from one scoring pass; see [orderings() in appendix](#appendix-key-code)):
`replace` (sort by CE), `rrf` (RRF-fuse CE rank + LightGBM rank), `filter@τ` (demote candidates
scoring <τ), `promote@τ` (pull candidates scoring ≥τ to the front). Plus BM25 and random baselines.

**The number that decides it — population-weighted NET ΔnDCG@20** (1,709 miss : 4,865 ctrl), with a
**full offline threshold sweep** over the saved per-candidate scores:

| mode | NET ΔnDCG@20 | miss | ctrl |
|---|---|---|---|
| filter@0.0005 | **+0.0020** | +0.0006 | +0.0025 |
| filter@0.001 | −0.0001 | +0.0012 | −0.0006 |
| filter@0.05 | −0.042 | +0.016 | −0.062 |
| promote@0.99 | −0.066 | +0.000 | −0.089 |
| promote@0.95 | −0.158 | +0.011 | −0.217 |
| rrf | −0.202 | +0.024 | −0.281 |
| promote@0.9 | −0.208 | +0.015 | −0.286 |
| replace | −0.378 | +0.041 | −0.525 |

**Every mode that does real work is net-negative.** The only net-positive config (`filter@0.0005`,
+0.002) is a **no-op** — it removes only `P(yes)≈0` absolute junk, recovers essentially nothing
(+0.0006 on misses), and +0.002 is noise-level.

**Diagnostic (B:replace) — split by whether the CE recognizes the GT:**

| group | subset | rank before→after | ΔnDCG |
|---|---|---|---|
| miss | GT-recognized (≥0.5) | 43 → 18 | **+0.271** |
| miss | GT-floored (<0.05) | 46 → 80 | +0.004 |
| ctrl | GT-recognized (≥0.5) | 3 → 14 | **−0.445** |
| ctrl | GT-floored (<0.05) | 5 → 67 | −0.639 |

The CE *does* recover buried GTs **where it recognizes them** (+0.27). But (a) that's only ~half the
miss turns and is selected on the answer (not knowable at serving), and (b) on controls it demotes
the already-correct GT — pure `replace` throws away the LightGBM order, and even a "recognized"
control GT at rank 3 falls to 14 because the top-100 of a correct turn is full of *other* tracks the
CE scores higher.

> ⚠️ **Two caveats so this isn't mis-read.** (1) The **+0.271** is **posthoc and NOT
> serving-knowable** — that group is selected *on the GT's own score*, which you don't have at
> inference; it is not evidence the CE helps in production. (2) These phase-3 runs used the
> **concise** music `<Instruct>` (arm B). A more elaborate music instruction (`MUSIC_INSTRUCT`,
> §4) was tested in E2 and came out **≈ placebo** (no real gain beyond token inflation); given the
> chance-level in-pool AUC (§6), a heavier instruct would not plausibly flip this — but to be exact,
> the net-negative table was *not* re-run with the elaborate instruct.

---

## 6. Root cause (verified by an adversarial review + offline tests)

The disappointing result was rechecked by an adversarial agent (mandate: *find the bug that flips
it*) plus two code/data reviewers. **No bug** — reproduced to the digit — and the real cause is
deeper than "controls outnumber misses":

- **The "AUC 0.96" was GT vs a *random* catalog track (easy).** On the **actual** task — GT vs the
  other ~99 *in-pool* candidates the LightGBM already chose — AUC collapses to **0.513 on misses
  (≈chance)** and **0.725 on controls** (recomputed from the committed raw scores). The CE genuinely
  **cannot pick the GT out of plausible candidates**.
- A **cheating oracle gate** that applies the CE *only to true misses and never touches a control*
  still nets only **+0.0009** (≈6 of 1,709 recovered). So control-damage is a *symptom*; the disease
  is chance-level in-pool discrimination.
- **~half the miss GTs (199/397) are outside the LightGBM top-100 entirely** — structurally
  unreachable by any top-100 reranker.
- **Richer query makes it *worse* for this purpose:** the "all" context raises AUC-vs-random
  (0.96→0.98) but *drops* AUC-vs-in-pool-distractor (0.54→0.39, worse than chance) — more context
  makes the CE pick whatever matches the conversation, including the distractors.
- **`promote-only` does not "protect controls by construction"** (an early hope): a control GT
  scoring below the promote threshold is still demoted by the number of promoted items.

Data integrity confirmed: control `before`-rank matches `lanes.rank` exactly (0/200 mismatch); all
controls genuinely rank ≤20; scores are 1:1 aligned with candidates; query has no current-turn
GT/assistant leak.

---

## 7. Experiment 4 — Precision / quantization (for compute cost only)

`probe_xenc_precision.py` (4B, 100 turns, local GB10):

| precision | AUC(GT vs random) | clean-neg | throughput | peak mem |
|---|---|---|---|---|
| fp16 | 0.9563 | 0.7270 | 13.3 pairs/s | 10.8 GB |
| bf16 | 0.9563 | 0.7302 | 13.2 pairs/s | 10.8 GB |
| fp8 | — | — | **failed locally** (`kernels` triton fp8 pkg breaks transformers 5.6.2) | 4.7 GB loaded |

*(These E4 numbers are from a one-off local GPU run; no precision result JSON is committed, so unlike
E1/E2/E3 they aren't re-derivable from the committed artifacts — re-run `probe_xenc_precision.py` to
regenerate.)*

**Takeaways.** bf16 is **exactly lossless** but gives no speedup/memory benefit on this box. fp8/int8
are not viable *locally* (the GB10 is aarch64 + cuda-capability sm_121; the `kernels` upgrade clobbers
the required `torch 2.9.1+cu130`). On **Modal x86 datacenter GPUs**, fp8 (H100) / int8-W8A8 *do*
speed up — see cost section. Precision changes cost only via throughput; the model already fits cheap
GPUs at fp16, so quantization is a throughput/$ play, not a fitting need.

---

## 8. Cost analysis (Modal feature generation)

This applies to the **LightGBM-feature** role (the only remaining live serving use): to add the CE
score as a feature you must compute it on the reranker's **training** candidates (to retrain), the
**devset** candidates (to evaluate), and the **blind** candidates (to submit).

**Volumes** (deployed reranker trains on `features_train_deep30k` = **30,000 turns × ~331 candidates
= 9.9M pairs**; devset = 8,000 turns; full train split = **15,199 sessions ≈ 121,592 turns**):

| pass | turns | pairs (~331 cand) |
|---|---|---|
| train (deployed 30k subsample) | 30,000 | 9.9M |
| devset eval | 8,000 | 2.6M |
| blind_a (final-turn-only) | ~1–2.5k | ~0.3–1M |
| **total (30k-scale)** | — | **~13M** |
| train at **full 121k** | 121,592 | ~40M |

**Cost** = `pairs ÷ throughput ÷ 3600 × $/GPU-hr`. Qwen3-Reranker-4B realistic batched throughput is
~300–800 pairs/s on a datacenter GPU; ~$2–4/GPU-hr:

| scenario | $ (Modal, approx) |
|---|---|
| 30k-scale, full depth (~13M), fp16 | **~$13–40** |
| 30k-scale, fp8 + vLLM | ~$5–15 |
| 30k-scale, **+ cap candidates to top-50** | **~$2–5** |
| **full 121k**, full depth | ~$50–160 (fp16) / ~$20–60 (fp8+vLLM) / ~$8–20 (capped) |

Caveats: the **bigger** cost of "train on all 121k" is *not* the CE — it's re-running the full
retrieval + 144-feature pipeline on the extra 91k turns (the 30k feature set is all that exists on
disk). The CE is one column on top of that. A quick fp8/int8 **parity check** (~100 turns) is
required before trusting a quantized build (bf16 is already verified lossless).

---

## 9. How to reproduce

**Committed artifacts (verify the findings *without* a GPU).** The small result files are checked in
under [`cross_encoder_artifacts/`](cross_encoder_artifacts/) (see its README). The key one is
`xenc_phase3_4b_v2_rawscores.jsonl` (per-turn cross-encoder scores) — it regenerates the entire §5
net table in seconds:

```bash
python scripts/rerank/sweep_phase3_offline.py \
    docs/research/cross_encoder_artifacts/xenc_phase3_4b_v2_rawscores.jsonl
```

To **regenerate the scores from scratch** (needs the 4B model + the inputs below):

**Environment.** Run from the **main checkout** (the worktree lacks the data artifacts). Python
3.10/3.12 venv with `torch` (cu130 build on the GB10 — see `docs/` GB10 notes), `transformers`,
`lancedb`, `datasets`. `Qwen/Qwen3-Reranker-0.6B` is small; 4B/8B download ~8/16 GB. `.env` needs
`OPENROUTER_API_KEY` (judge) and optionally `DEEPINFRA_API_KEY` (hosted 4B/8B). HF auth for the
dataset/blind splits.

**Inputs (committed-or-derivable):**
- Catalog text: LanceDB `cache/lancedb` table `music_track_catalog` (`track_text`).
- Devset trace (LightGBM pool + `turn_intent`): `exp/inference/devset/state_ranker_v10_lgbm_devset_trace.jsonl`
  (`trace.ranking.stages` → `candidate_fusion` + `lgbm_v10`; `trace.extracted_state.turn_intent`).
- Lanes: `exp/analysis/rerank/devset_lanes_v10.jsonl` (`hit`, `oracle`, `lane`, `rank`).
- Ground truth: `exp/ground_truth/devset.json`. Train pairs: `exp/analysis/retrieval_exploration/retriever_pairs.jsonl`.
- (All `exp/…` paths are gitignored local artifacts; regenerate via the rerank build scripts.)

**Commands** (scripts in `scripts/rerank/`):

```bash
# E1 — labeler kill-switch + judge
python scripts/rerank/probe_xenc_mining.py --limit 300
python scripts/rerank/judge_softpos.py --limit 120 --max-per-turn 3   # needs OPENROUTER_API_KEY

# E2 — model/prompt/context ablation (placebo-controlled)
python scripts/rerank/probe_xenc_ablation.py --limit 150 --batch-size 16 --big-variants base,richquery,all,placebo

# E3 — serving reranker (replace/rrf/filter/promote + raw-score save for offline sweeps)
python scripts/rerank/probe_xenc_zeroshot.py --model Qwen/Qwen3-Reranker-4B \
    --k 100 --arms B --limit 400 --controls 200 --batch-size 32 \
    --out exp/analysis/retrieval_exploration/xenc_phase3_4b_v2.json
#   then sweep thresholds offline (free) over the *_rawscores.jsonl it writes.

# E4 — precision parity (run per precision)
python scripts/rerank/probe_xenc_precision.py --precision fp16 --limit 100
```

**Example input/output** (E3, one turn):
- *Query* (arm B): `"user (previous): play something chill\nrecommended: Bonobo - Kong\nuser (current request): now something more upbeat and danceable"`
- *Document*: `"Justice - D.A.N.C.E. | Cross | electronic, dance, french house, funk, upbeat"`
- *CE call*: the yes/no template in §2 with `INSTRUCT` (§ appendix) → `P(yes)=0.83`
- *Effect*: candidate's score used to reorder the LightGBM top-100; ΔnDCG@20 = nDCG(after)−nDCG(before).

---

## 9.5 Limitations / what was NOT tested

So the trust boundaries are in one place:
- **Zero-shot only.** The cross-encoder was never fine-tuned. A *fine-tuned* cross-encoder on
  play/gpa labels is a different (untested) animal and could behave differently.
- **Sampled, then population-weighted.** E3 nets come from a **397-miss / 200-control sample**;
  the headline "net" multiplies the per-group means by the true devset populations (1,709 / 4,865).
  E1 used 300 turns (90 / 194 judged); E2 used 150. Magnitudes are directional, not ±0.001-precise.
- **The +0.271 recognized-miss recovery is posthoc / not serving-knowable** (group selected on the
  GT's own score) — it is *not* evidence the CE helps in production.
- **Serving instruct.** E3 used the *concise* music `<Instruct>`; the elaborate `MUSIC_INSTRUCT`
  (≈placebo in E2) was not re-run through the full net table.
- **Top-100 ceiling.** E3 reranks the LightGBM top-100; ~half the miss GTs sit deeper and are
  structurally unreachable by this experiment (a deeper rerank wasn't run — but it only adds cost,
  and §6's chance-level AUC says it wouldn't help).
- **The independent judge (DeepSeek) is itself imperfect** — it rates even the *true* GT "GOOD"
  only 44%, so soft-positive precision is a conservative proxy, not ground truth.
- **Not tested here:** CE as a fine-tuned reranker; CE reranking the *fusion* pool (pre-LightGBM);
  CE as a LightGBM feature end-to-end (only prior-logged +0.022); the full-121k reranker retrain.

---

## 10. Recommendation / next steps

1. **Do not add a cross-encoder serving reranker/filter** (any mode) to the deployed pipeline or the
   blindset. Verified net-negative ~4 independent ways. Closed.
2. **Cross-encoder = offline labeler/teacher only.** If pursuing bi-encoder label hygiene, use the
   validated **4B + richquery → judge-confirm** recipe (E1) — but note it's **second-order** (prior
   GATE-0 work shows label hygiene barely moves the bi-encoder).
3. **CE-as-LightGBM-feature** is the only live serving use (prior +0.022 hard_pivot). It's **not
   wired into the feature pipeline** and costs ~$2–40 on Modal to build (§8). **Low ROI** — the
   prior gain is **+0.022 nDCG on the hard_pivot *lane*** (~47% of turns), so roughly **+0.01 overall
   nDCG → ~+0.005 composite** (nDCG is 0.50 of the composite) — modest vs the build/integration
   effort. Park it as a costed option for a final push.
4. **Spend the budget on the bi-encoder instead.** It is the higher-ROI retrieval lever (e.g. the
   `b1` max-len truncation fix recently bought **+7.4 r@20** nearly for free). Levers: 4B capacity,
   iterative (ANCE) hard-negative re-mining, grounded track-level doc text (within-artist collapse).
5. If reranker training is revisited at all, the **bigger** win is likely **scaling the LightGBM
   training from 30k → full 121k turns** (the learning curve was monotonic: 0.110→0.127→0.137) — a
   separate, larger project (full feature rebuild), independent of the cross-encoder.

---

## Appendix: key code

**Cross-encoder instruction (`probe_xenc_zeroshot.py`, the `<Instruct>` line):**
```
You are evaluating candidate tracks for a music recommendation system. Judge whether the candidate
track satisfies the user's CURRENT (last) request; use any earlier context only to resolve references.
```
**Ablation instruction variants (`probe_xenc_ablation.py`):** `GENERIC_INSTRUCT` = the line above;
`MUSIC_INSTRUCT` = *"You are a music recommendation engine. Decide whether the candidate track is one
this specific listener would want played NEXT … Reward a track that matches the requested genre /
mood / era / artist intent; do not reward a track that is merely generally popular or loosely
on-topic."*

**Query construction (`build_query`, arm B = chronological context, leak-safe):**
```python
def build_query(arm, key, rec, um, played, meta, n_turns):
    sid, tn = key
    if arm == "A":                                   # baseline = the distilled turn_intent
        return rec["turn_intent"] or um.get(sid, {}).get(tn, "")
    lines = []                                        # arm B/C: chronological, strictly-prior context
    for k in range(max(1, tn - n_turns), tn):         # turns < current only (no leak)
        if um.get(sid, {}).get(k):
            lines.append(f"user (previous): {um[sid][k]}")
        for ptid in played.get(sid, {}).get(k, []):   # prior recommended tracks (as text, not ids)
            m = meta.get(ptid)
            if m: lines.append(f"recommended: {m['artist']} - {m['title']}")
    lines.append(f"user (current request): {um.get(sid, {}).get(tn, '')}")  # current request LAST
    return "\n".join(lines)
```

**Reranking modes — all derived free from one scoring pass (`orderings`):**
```python
def orderings(cand, tail, sc, gt, fusion_k=60, taus=(0.05, 0.2), ptaus=(0.8, 0.9)):
    n = len(cand); out = {}
    od = sorted(range(n), key=lambda i: -sc[i])
    out["replace"] = after_rank([cand[i] for i in od], tail, gt)        # sort head by CE score
    xrank = {i: r for r, i in enumerate(od)}
    rrf = sorted(range(n), key=lambda i: -(1/(fusion_k+i) + 1/(fusion_k+xrank[i])))
    out["rrf"] = after_rank([cand[i] for i in rrf], tail, gt)            # fuse CE rank + lgbm rank
    for tau in taus:                                                     # demote candidates < tau
        keep = [cand[i] for i in range(n) if sc[i] >= tau]
        drop = [cand[i] for i in range(n) if sc[i] < tau]
        out[f"filter{tau}"] = after_rank(keep + drop, tail, gt)
    for ptau in ptaus:                                                   # promote-only (>= ptau to front)
        promoted = sorted([i for i in range(n) if sc[i] >= ptau], key=lambda i: -sc[i])
        rest = [i for i in range(n) if sc[i] < ptau]
        out[f"promote{ptau}"] = after_rank([cand[i] for i in promoted + rest], tail, gt)
    return out
```

**Scripts** (in `scripts/rerank/`, committed with this report): `probe_xenc_mining.py`,
`judge_softpos.py`, `probe_xenc_ablation.py`, `probe_xenc_zeroshot.py`, `probe_xenc_precision.py`.
