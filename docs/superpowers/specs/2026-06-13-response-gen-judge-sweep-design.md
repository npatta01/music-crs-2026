# Response-Generation Judge Sweep — Design Spec

**Date:** 2026-06-13
**Branch:** `claude/heuristic-williamson-1b10f2`
**Status:** Design — pending implementation plan
**Related:** [`docs/research/2026-06-10-response-generation-bakeoff.md`](../../research/2026-06-10-response-generation-bakeoff.md) (PR #114), `reference_scoring_formula_codabench`

---

## 1. Problem

Our best Blind-A submission scores **composite 0.5336** (nDCG@20 0.4261, catalog 0.0311, lexical 0.7744, **LLM-judge 4.20/5**). The top leaderboard entry is **0.68**. Decomposing the 0.146 gap against the exact scoring formula (`0.50·nDCG + 0.10·catalog + 0.10·lexical + 0.30·(judge−1)/4`, verified to reproduce both scores to the digit):

| Metric | Ours | Top | Gap contribution | % of gap |
|---|---|---|---|---|
| nDCG@20 | 0.4261 | 0.59 | +0.082 | 56% |
| **LLM judge** | **4.20** | **4.95** | **+0.056** | **38%** |
| lexical | 0.7744 | 0.86 | +0.009 | 6% |
| catalog | 0.0311 | 0.03 | ≈0 | 0% |

This spec targets the **response-text front (judge + lexical = 44% of the gap)**. It is independent of retrieval (the nDCG 56% is a separate effort). Closing judge 4.20→4.95 alone is **+0.056 composite**; even 4.20→4.60 is **+0.03**.

> **⚠️ Confirmed prerequisite bug (Codex #9, verified in code) — the 4.2 baseline runs on a half-empty state.** `mentioned_entities`, `explicit_rejections`, and `release_year_range` are plain `@property` on `ConversationStateV0Plus` (`schema.py:1325/1370/1408`), so pydantic `model_dump(mode="json")` (`compiler_qu.py:746`) **silently drops them**. The response path reads that dumped dict (`crs_baseline.py:305` → `format_state_block`), so the `[LISTENER CONTEXT]` block the bake-off tuned actually omits the **mentioned artists/tags/albums, the explicit rejections, and the year range** — only `turn_intent`, `track_feedback`, and `lyrical_theme` survive. Fixing the serialization is **V0**: the corrected-baseline submission that ships *first* (it may move 4.2 on its own and is the honest baseline every variant builds on).

### The real constraint: measurement, not ideas

Response-gen iteration is cheap to *compute* but expensive to *learn from* — there is **no trustworthy offline signal**. The PR #114 bake-off proved this: its proxy judge (gemini-2.5-flash + gpt-5-mini, G-Eval rubric) is a *coarse ranker that inverts among strong models* (it ranked deepseek > qwen; the real Blind-A judge flipped it). So today, every fine-grained response change can only be confirmed by spending a blind submission.

**Budget available:** up to 8 submissions today (2026-06-13) + 10 tomorrow (2026-06-14) = **18 real-judge evaluations — a hard ceiling, not a target.** The intent is to spend *as few as possible*: the offline judge screens the variant space so we submit only a small shortlist and **stop as soon as a config beats the corrected V0 baseline by a predeclared margin `δ`** (see §6 stopping rule). 18 is generous enough that the offline judge no longer has to be perfect — it only has to rank-order well enough to pick the shortlist.

## 2. Goal & success criteria

**Primary (this effort):** ship a Blind-A submission whose real LLM-judge score beats 4.20, spending the **fewest submissions possible** (≤18 hard cap). Stretch: ≥4.60 (+0.03 composite); ceiling 4.95 (+0.056).

**Durable secondary:** a *retained, validated* offline judge that rank-correlates with the real judge on our anchor points, so every future response-gen iteration costs ~$0 to screen instead of a submission. (The bake-off threw its harness away — that is the waste we are correcting.)

**Non-goals (YAGNI):**
- Touching **retrieval** — frozen here; that is the separate nDCG effort.
- Building full multilingual generation. Note (Codex #14, corrected): the response prompt **already instructs same-language replies** (`system_prompts/response_generation.txt:8-9`), and `preferred_language` is **not** injected today (the profile string carries only `user_id/age_group/gender/country_name` — `db_user/user_profile.py:13`). So the cheap probe is not "add a language instruction" but **surface the language signal** — inject `preferred_language` / detected turn language into the context so short or ambiguous turns reply in-language. Lower priority since the instruction already exists; include only if mixed-language turns underperform in screening. No translation models, no per-language tuning.
- A large judge ensemble — 2 judges (Gemini primary + neutral diagnostic).

> **Note — generation model is *in scope*, evidence-gated.** Earlier framing treated the model as settled (qwen). It is not: the real judge is Gemini, and we have no real-judge datapoint for a strong Gemini *generator*. The model is decided by the evidence from arm **M1** (§5), not assumed.

## 3. Design overview — a two-tier funnel

```
                 ┌─────────────────────────── TIER 1: offline (unlimited) ───────────────────────────┐
 frozen retrieval│  variant configs ──────────► response replay ──► reference-FREE Gemini primary    │
 (Blind-A rr2 +  │  (V0..V5 + model arm M1)    (batch_respond, IDs    + neutral diagnostic           │
  devset rr2)    │                              byte-identical)           ▼                            │
                 │                                rank on stratified slice (bootstrap CIs)             │
                 └────────────────────────────────────────────┬───────────────────────────────────────┘
                                                               │  small shortlist (~3–4)
                 ┌──────────────────── TIER 2: real judge (≤18, stop as soon as a winner clears) ───────┐
                 │  submit shortlist to Blind-A ──► real judge scores ──► pick winner / STOP             │
                 │                                          │                                            │
                 │                    recalibrate proxy ◄───┘  (feed real scores back as new anchors)    │
                 └────────────────────────────────────────────────────────────────────────────────────┘
```

Three components: **(A)** the offline judge, **(B)** the retrieval-frozen variant harness, **(C)** the submission protocol. All retained as a lean reusable module under `scripts/respgen/`.

## 4. Component A — Offline judge (`scripts/respgen/offline_judge.py`)

Scores a `(turn, generated_response)` pair on **Personalization** and **Explanation Quality**, each 1–5, normalized `(s−1)/4`, matching the reconstructed challenge rubric. Two upgrades over the thrown-away bake-off proxy:

1. **Reference-FREE is primary; reference-anchored is diagnostic only (Codex #2).** The real CodaBench judge almost certainly scores our reply *given the conversation, with no gold reference* (it's a G-Eval-style rubric, and no reference reply exists at scoring time). So handing the proxy a reference reply makes it a **different task** than the real judge and can bias the ranking. Therefore the **primary proxy is reference-free**. Reference replies (if the devset exposes them — verify at plan start) are used only as a **diagnostic / tiebreak signal — not a hard gate** (Codex fresh-review: gating on reference-agreement isn't warranted until references are confirmed *and* their anchor-correlation is measured). V3 (register-match) still uses references as *style* exemplars — that's a generation input, not a judge input, so it's unaffected.
2. **Gemini-primary panel — match the real judge, don't cancel it.** The real judge is **Gemini**, so the primary proxy is a Gemini judge (`gemini-2.5-flash`): it's the closest predictor of the real score, *including* any same-family affinity the real judge also exhibits. A **neutral second judge** (`gpt-5-mini` or equiv) runs alongside as a **diagnostic only** — a large `Gemini − neutral` gap flags "family affinity / style lineage" vs "genuine quality," which is what we need to interpret the model arm (§5 M1). This deliberately **inverts** the bake-off's use of the neutral judge: the bake-off added it to *avoid* Gemini's bias; here, because the real judge *is* that biased Gemini, we want the proxy to *reproduce* the bias for ranking and use the neutral judge only to understand it. Keep exclude-on-parse-failure (never score 1/1) + generous `max_tokens` (≥4096) — both bake-off lessons.

### Acceptance gate (the discipline the bake-off lacked)

The proxy is **not trusted until it reproduces the real-judge ordering on the 4 anchor points we already hold** (Blind-A, /5):

| | Transcript | State |
|---|---|---|
| qwen3-30b-a3b | 4.0 | **4.2** |
| deepseek-flash | 3.6 | 3.75 |

Required: proxy must reproduce **state > transcript** (within each model) and **qwen > deepseek** (within each conditioning). To check this we regenerate those 4 configs' responses and score them.

**The gate is weak and split-confounded — treat it as a floor, not proof (Codex #1).** Only 4 anchors, and their real scores are on the *full* Blind-A set while the proxy scores a *devset slice* — so a pass/fail conflates judge fidelity with the data-distribution difference. Mitigations: (a) if archived Blind-A *outputs* for those 4 configs exist, score the proxy on **those exact outputs** (removes the data confound); (b) require **rank stability across multiple deterministic devset sub-slices**, not one; (c) until ≥~8 anchors agree, use the proxy only to **cut clearly-weak variants**, never to finely rank strong ones (the bake-off's exact failure). As Tier-2 submissions land, each new `(variant → real score)` pair becomes an anchor; re-check Spearman; a proxy that decorrelates is demoted to weak-filter only.

## 5. Component B — Retrieval-frozen variant harness

Response text never touches retrieval, so we **generate retrieval once and swap only the response stage** per variant. This isolates the measurement (nDCG/catalog identical across variants; only judge + lexical move) and makes producing many submission files cheap (re-run only the LM call, no retrieval recompute).

- **Frozen retrieval sources:** the cached `v0plus_compiler_blindset_A_rr2` run (for submissions) and a `v0plus_compiler_devset_rr2` run (for offline screening). Both already set `branch_trace_topk: 1000`, so per-turn **state** and **branch provenance** are present in the trace / `last_traces` side-channel — V2 and V4 need no extra retrieval cost.
- **A real response-only path is required — this is more than "swap the LM call" (Codex #12).** `batch_chat` computes retrieval *then* response in one flow (`crs_baseline.py` retrieve ~239–296, generate ~301–328); there is no entrypoint that takes cached retrieval. `scripts/respgen/run_variant.py` must call a **new `batch_respond(...)` method** that accepts cached `predicted_track_ids` + cached `trace` (state/provenance) + the dataset row, runs *only* stages 0/2, and **asserts the emitted track IDs are byte-identical to the cached run** (so nDCG/catalog cannot drift). Writes a predictions JSON with the same IDs and a new `predicted_response`.
  - **Cached traces predate V0 (Codex fresh-review) — must be handled.** Existing rr2 trace sidecars contain the *broken* (pre-V0) `trace["state"]` dict with the dropped fields. Since V0 changes only response-state serialization (not retrieval), the clean fix is to **regenerate the frozen devset/blind rr2 runs once, after V0 lands**, and assert their `predicted_track_ids` still match the committed rr2 cache (retrieval is unchanged) — then replay all variants off those V0-corrected traces. (Alternative: have `batch_respond` apply the V0 augmentation helper to cached `trace["state"]` before formatting. Prefer regeneration since V0 ships first anyway.)

### V0 + 5 variants (baseline = qwen3-30b · state-conditioned · 4.2)

Implemented as **boolean/string flags on `explanation_kwargs`** (toggled via CLI override), not forked config files, to avoid config sprawl. **V0 ships first** and becomes the baseline the rest build on.

| # | Variant | Rubric target | What it adds | Code hook |
|---|---|---|---|---|
| **V0** | **fix state serialization** | Personalization (corrects baseline) | Make the dumped response-state actually contain `mentioned_entities`, `explicit_rejections`, `release_year_range` (today dropped — see §1 bug). Build an explicit **response-state dict** (call the properties), not bare `model_dump()`. Likely lifts 4.2 on its own; *all variants below assume the fixed state*. | `compiler_qu.py:746` (emit explicit dict) + regression test on `format_state_block` |
| **V1** | `+ listener_goal` | Personalization | Add the listener goal to `[LISTENER CONTEXT]`. **It is not in the state object** — it lives in `session_meta["conversation_goal"]["listener_goal"]` (Codex #8), so it must be passed into `format_state_block` as a **separate argument**, threaded from the dataset row through `batch_chat`. Leak-safe; reranker reads the same field (`lgbm_reranker.py:81`). | `format_state_block(state, …, listener_goal=…)` + thread `session_meta` in `crs_baseline` |
| **V2** | `+ grounded "why"` | Explanation Quality | Pre-compute a **scaffold of verified facts**, instruct the model to use *only* these: (1) **attribute overlap** = `state asks ∩ top-track metadata`; (2) **relational reason** translated to user terms. **Two corrections:** (a) the v9 reranker reorders *after* branch tracing (`compiler_qu.py:784–794`), so "dominant branch" is post-rerank-ambiguous — use a branch reason **only when the rerank top-1 actually appears in that branch's pool**, else fall back to attribute/state overlap (Codex #10); (b) era/attribute matching needs fields the XML item doesn't expose (it carries only title/artist/album/tags — `response_context.py:27`), so the scaffold must read `release_year`/`release_decade` from track metadata via a **whitelisted field set** (Codex #11). | new `build_grounding_scaffold(state, top_meta, branch_pools)` + expose pools + top-track metadata to `batch_chat` |
| **V3** | `register match` | Both + lexical | Shape length/register/structure to the devset reference replies (Gemini-family distribution the judge rewards) — distilled style instruction (try first) or few-shot exemplars. References here are a **generation input, not a judge input** (so the §4 reference-free judge stance does not conflict). Leak-safe. | prompt-only (system prompt + optional few-shot block) |
| **V4** | `trajectory / turn-delta` | Personalization | Give the reply conversational continuity. **Correction (Codex #13):** under state-conditioning the transcript is *replaced* by the state block (`crs_baseline.py:301–309`), so the previous turn is **not** "already" available to the LM — V4 must **explicitly append** compact prior+current user messages (source (a), simpler) or a state delta t−1→t (source (b)) to the state response context. | add turn-context block in `response_context` + pass prior-turn messages from `crs_baseline` |
| **V5** | `stacked best-of` | Ceiling | Compose the V0+V1–V4 levers that screen positive offline. Composition decided after the offline screen / Wave 0. | flag composition |

V2 carries the most plumbing (branch pools + extra metadata fields → response stage). If costly, **V2 degrades gracefully to attribute/state-overlap only** (drop the relational clause) and is still valuable.

### Model arm M1 — evidence-gated generator swap

The judge is **Gemini**, and the bake-off showed a Gemini judge *inflates Gemini-family outputs*. We have **no real-judge datapoint for a strong Gemini generator** — the bake-off only tested the weak `gemini-flash-lite`, and never in the real 2×2. So qwen-vs-Gemini is genuinely open against the family-affinity hypothesis.

**M1 = swap the generator to a strong Gemini model** (e.g. `gemini-2.5-flash`), same state-conditioning + XML item + profile, and buy **one real-judge datapoint**. Model held fixed otherwise — one informed probe, not a model sweep.

**Switch rule, harmonized with the stop rule (Codex #4):** M1 replaces production *only if* it clears the **same predeclared margin `δ`** as §6 (not the looser "beats 4.2"), is generated at **temperature 0** like every sweep arm, **and** does not regress lexical/composite. Specify the exact Gemini provider model (e.g. `openrouter/google/gemini-2.5-flash`) in its config block. **Treat any M1 gain as official-score optimization, not a durable quality claim (Codex #3):** a Gemini-primary proxy screening a Gemini generator is a circular family-affinity path, so label M1 "durable" only if the **neutral diagnostic also improves** and real CodaBench confirms it. M1 and **V3** attack the same hypothesis from two sides (M1 *is* a Gemini model; V3 *mimics* Gemini prose with qwen) — screen both; submit whichever screens higher; the neutral judge tells us how much is affinity vs quality.

## 6. Component C — Submission protocol (≤18, minimize)

### Screening slice

A **last-turn-only devset slice** — last-turn-only because Blind-A is scored on the last turn only (heard-share ~52%, a different regime than all-turns devset). Stored at `exp/subsets/respgen_screen_slice.json`. **Size it for stability, not just ">8" (Codex #7):** ~30–50 sessions is too small for register/language effects and risks slice-sensitive rankings. Therefore (a) make it a **stratified** slice (language × request-type × heard/unheard), bigger if a full last-turn screen is affordable, and (b) report **bootstrap confidence intervals** on the per-variant proxy scores (or screen over multiple deterministic sub-slices) so we only shortlist gaps that survive resampling. This is offline and cheap — there is no reason to under-power it.

### Judge-score tracker

**No noise-floor resubmissions** — we never spend a slot re-testing an identical config. Every submission is a *distinct* test, logged to `exp/respgen/judge_tracker.md`: variant, flags, real LLM-judge, lexical, composite, offline-proxy score, proxy↔real residual.

**Define the stop margin from a real noise model, NOT leaderboard spread (Codex #5).** Other teams' scores (≈4.45–4.95) are *different systems*, not repeated measurements of ours, so their spread is **not** our measurement noise — using it as the stop threshold is a category error. Instead the stop margin `δ` is a **predeclared fixed value** (proposal: `δ = 0.2` judge points, ≈ +0.015 composite) chosen up front, plus **temperature-0 generation** to remove sampling noise so any score change is attributable to the variant.

> **Temperature-0 must be enforced — the production config contradicts it (Codex fresh-review).** `configs/v0plus_compiler_blindset_A_rr2.yaml:10` sets the response `temperature: 0.7`. **Every sweep arm (V0–V5 and M1) must override `explanation_lm_kwargs.temperature: 0.0`** so comparisons are deterministic; V0's temp-0 real submission becomes the baseline all arms are measured against. The final shipped config inherits the winning arm's temperature (i.e. 0.0), so there is no 0.7-vs-0.0 mismatch at ship time.

Leaderboard scores stay in the tracker purely as **ceiling/context**, never as the noise floor.

### Spend-minimal waves (every submission is a distinct test; stop early)

**Wave 0 — today (offline first, then a *small stratified* shortlist):**
0. Land **V0** (state-serialization fix), then **regenerate the frozen devset/blind rr2 traces once** — assert `predicted_track_ids` match the committed rr2 cache (retrieval unchanged), so every replay below runs off V0-corrected state.
1. Build + acceptance-gate the offline judge (no submissions); all arms generate at **temperature 0**.
2. Offline-screen **V0–V5 + M1** on the slice → rank (reference-free proxy primary; reference-anchored must agree) → compose V5.
3. **Submit V0 first** (the corrected baseline) — it resets the reference point. Then submit a **stratified shortlist, not pure top-N (Codex #6):** because the proxy is known to invert strong models, pick the **best variant per rubric axis** rather than the top 3 by one score — i.e. {best Personalization arm, best Explanation arm, the stacked V5, and M1 if it screens plausibly}. That's ~V0 + 4 ≈ 5 submissions, still well under 8, but hedged against proxy unreliability. Log each + its proxy↔real residual.

**Stopping rule (the point of "don't use all 18"):**
- If a config beats the **corrected V0 baseline by ≥ the predeclared margin `δ`**, **lock it and stop** — optionally one confirmation submission, nothing more.
- Continue to Wave 1 **only if** the best is within `δ` (ambiguous) or the proxy↔real correlation now looks good enough that a data-motivated refinement is worth a slot.
- Untapped budget is a *win*, not waste — record the final spend.

**Wave 1 — tomorrow (only if needed):**
4. Recalibrate the offline judge with the new real anchors.
5. A *minimal* refinement round — only data-motivated configs (a combination of proven winners, one V3 length tweak, or stacking V3 onto M1 if M1 won). Submit a few, not ten.
6. Keep the best as the new `rr2` submission; record it in `changelog.md` / `experiments/experiment_log.md`.

**CodaBench gotcha:** submission name = filename minus `.zip`, capped at 64 chars — keep variant filenames short (e.g. `rr2_v3.zip`).

## 7. Data flow

```
devset rr2 run (cached) ─► state + branch pools + (reference reply, diagnostic) ─┐
                                                                                  ├─► batch_respond (LM only, IDs frozen) ─► variant responses
variant config (V0..V5 + M1) ─────────────────────────────────────────────────────┘                              │
                                                                                                                   ▼
                                              offline_judge (reference-FREE Gemini primary + neutral diag, bootstrap CIs) ─► ranked + acceptance report
                                                                                                                   │ stratified shortlist
blind-A rr2 run (cached) ─► state + branch pools ─► batch_respond ─► V0 + variant submission JSONs ─► CodaBench ─► real judge scores
                                                                                                                   │
                                                                                  fed back as new anchors → recalibrate ◄┘  (stop when ≥ δ over V0)
```

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Proxy ranking on devset doesn't transfer to blind (regime mismatch + small confounded gate, Codex #1) | Reference-free primary proxy (Codex #2); stratified last-turn slice with bootstrap CIs (#7); score the 4 anchors on archived blind *outputs* if available; until ≥~8 anchors agree, proxy only **cuts weak** variants, never finely ranks strong ones; real leaderboard is the tiebreaker. |
| Judge run-to-run noise vs variant deltas | A **predeclared fixed margin `δ`** (not leaderboard spread, Codex #5) + **temperature-0 generation** to remove sampling noise; act only on gaps ≥ `δ`. |
| **State serialization bug masks variant effects (Codex #9)** | **V0 fixes it and ships first** (explicit response-state dict + regression test on `format_state_block`); all variants measured against the corrected baseline. |
| **Response-only replay is real work (Codex #12)** | New `batch_respond(...)` taking cached track-ids + trace; **assert IDs byte-identical** to the cached run so retrieval metrics cannot drift. |
| V2 branch-provenance misattribution post-rerank (Codex #10) / missing metadata fields (#11) | Use a branch reason only when rerank top-1 is in that branch's pool, else fall back to overlap; read `release_year`/`decade` via a whitelisted field set. V2 degrades to attribute/state-overlap only if plumbing is costly. |
| V5 stack underperforms the sum of parts (lever interaction) | We test isolated probes (V1–V4) *and* the stack (V5), so interactions are observable, not assumed. |
| Over-fitting to the proxy | The proxy only screens; the **real leaderboard is the tiebreaker** (explicit in the protocol). |
| **M1 wins only via Gemini family-affinity** (not better prose) | Real points *today* (the judge is Gemini), so we take the win — but it's fragile if organizers swap the judge. The **neutral diagnostic** quantifies how much of the gain is affinity vs quality; prefer configs that gain on *both* judges (robust), and don't bet the whole submission on a fragile affinity gain if a quality-driven variant is close. |
| Submission format / name-cap errors | Reuse PR #114 packaging; short filenames; one Wave-0 submission validates the pipeline end-to-end. |

## 9. Work map (files)

**New (retained module, `scripts/respgen/`):**
- `run_variant.py` — retrieval-frozen response replay; calls `batch_respond(...)`, asserts track-IDs byte-identical, writes predictions JSON.
- `offline_judge.py` — reference-free Gemini-primary + neutral-diagnostic panel; reference-anchored diagnostic; bootstrap CIs; acceptance/correlation report.
- `variants.py` — V0–V5 flag definitions, V5 composition, M1 generator override, language-match flag.

**Modify:**
- `mcrs/qu_modules/compiler_qu.py` — **(V0/#9)** at the trace-emission site (line 746), **augment** the `model_dump(mode="json")` output with the three `@property` values the formatter reads: `mentioned_entities`, `explicit_rejections`, `release_year_range`. Scope confirmed by Codex fresh-review: `lyrical_theme` is already a `Field` (schema.py:1035 → no fix); `routing_tags` is a property but the formatter doesn't read it (no fix). Use a **local augmentation helper, NOT a global `@computed_field`** — `@computed_field` would change *every* `model_dump` caller, not just the response path.
- `mcrs/response_context.py` — `format_state_block(…, listener_goal=…)` separate arg **(V1/#8)**; `build_grounding_scaffold(state, top_meta, branch_pools)` with whitelisted metadata fields + in-pool branch check **(V2/#10,#11)**; explicit prior+current turn block **(V4/#13)**; language-match line **(#14)**. Add a **regression test** asserting the block contains the previously-dropped fields.
- `mcrs/crs_baseline.py` — add **`batch_respond(...)`** (response-only entrypoint, stages 0/2 from cached retrieval, #12); thread `session_meta` (for `conversation_goal`), branch pools, top-track metadata, and prior-turn messages into the response-context builders, gated by `explanation_kwargs` flags.
- `configs/v0plus_compiler_blindset_A_rr2.yaml` — extend `explanation_kwargs` with the variant flags (default off = current behaviour; **V0 default on** once verified); sweep arms override `explanation_lm_kwargs.temperature: 0.0` (production is `0.7` at line 10).

**New data:**
- `exp/subsets/respgen_screen_slice.json` — last-turn-only, mixed-language devset screening slice.
- `exp/respgen/judge_tracker.md` — running log of every submission's judge/lexical/composite + offline-proxy score + proxy↔real residual, plus reference rows for other-team LLM scores.

## 10. Open decisions for the plan

- **Predeclared stop margin `δ`** — proposal 0.2 judge points (≈ +0.015 composite); confirm before Wave 0.
- **V0 serialization shape** — RESOLVED (Codex fresh-review): use a **local augmentation helper** at `compiler_qu.py:746`, not a global `@computed_field` (which would change all `model_dump` callers). Scope = the 3 dropped properties only.
- V4 sourcing: raw turn-pair (a) vs state-delta (b) — default (a), add (b) if time.
- V3 implementation: few-shot exemplars vs distilled style instruction — try the instruction first (cheaper context).
- Whether the **language-match** probe rides as a V0 sub-fix (always reply in-language) or a separate flagged variant.
- Stratified screening-slice composition + size; bootstrap iterations.
- M1 generator choice: `gemini-2.5-flash` vs `gemini-2.5-pro` (cost/latency vs quality) — and whether to also try a second family as a control.
- Proxy judge models: confirm `gemini-2.5-flash` as primary (matching the real judge's likely version) + neutral judge model choice (cost vs reliability).
