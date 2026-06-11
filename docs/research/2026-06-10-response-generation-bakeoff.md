# Response-Generation Bake-off — Research Report

**Date:** 2026-06-10
**Branch:** `claude/response-gen-bakeoff`
**Related:** [Issue #96](https://github.com/npatta01/music-conversational-music-recomender-2026/issues/96)

## 1. Problem

Every turn the system must produce two things: a ranked list of 20 tracks (done) and a
natural-language reply to the listener. All active configs used `lm_type: "dummy"`, which emits an
empty `predicted_response`. The challenge scores the reply text at **~40%** of the total
(0.30 LLM-judge + 0.10 Distinct-2), so empty replies forfeit that 40%.

Goal: pick the best response-generation **model** and **conditioning** (what context the model is
given), validate it, and enable it for the blind set.

## 2. Method — decoupled "replay" bake-off

Retrieval is identical regardless of which LLM writes the reply, so we held retrieval fixed (reused
the top-1 track per turn from `v0plus_compiler_all_retrievers_devset.json`) and replayed **only** the
response step across 10 candidate models on a curated 8-session / 64-turn devset slice
(`exp/subsets/bakeoff_smoke_8.json`, bucketed good/mediocre/bad by retrieval nDCG).

**Scoring (proxy):** a 2-judge panel — Gemini (`gemini-2.5-flash`) + a neutral judge
(`gpt-5-mini`) — using a reconstructed G-Eval rubric (Personalization + Explanation, each 1–5,
normalized `(s−1)/4`), plus Distinct-2. The official challenge judge prompt is undisclosed, so the
proxy is a **relative** signal only.

**Two conditionings compared:**
- **Transcript** — feed the raw multi-turn conversation (+ current ask + user profile).
- **State** — feed the compact `ConversationStateV0Plus` block extracted by the v0+ extractor
  (turn intent, liked/disliked entities, accepted/rejected tracks, filters, year range) instead of
  the transcript.

Code: `mcrs/bakeoff/` (`track_lookup`, `replay`, `judge`, `state_context`), `scripts/response_bakeoff.py`,
`scripts/judge_responses.py`, `configs/bakeoff/models.yaml`.

## 3. Bugs found and fixed (several hit production too)

| Bug | Effect | Fix |
|---|---|---|
| `chat_history_parser` emits `role:"music"` | OpenAI-style chat APIs 422 on unknown role; would break the issue #96 §B litellm flip | normalize `music`→`assistant` in `LITELLM_LM._build_messages` (prod + bake-off) |
| `batch_response_generation` default cap = 64 tokens | production replies truncated / reasoning models emptied | default → `None` → falls back to configurable `self.max_tokens` |
| Reasoning models starved by tight `max_tokens` | deepseek-v4-flash / gpt-5-nano emitted empty/truncated text at 256 | generation cap → 2048 |
| Judge `gpt-5-mini` (reasoning) starved at 512 | ~9% empty/truncated JSON → scored 1/1 → corrupted rankings | neutral judge → 4096 tokens + **exclude-on-failure** (never 1/1) + per-turn audit trail |
| Metadata echo | models parroted the raw `title:…\|tags:(45 tags)` blob (~10%) | present track as XML `<recommended_track>` + ≤10 tags + "never output verbatim" line |

## 4. Proxy results (devset, after all fixes)

Focused 6-model run, role+goal "track explainer" prompt, clean judge (`parse_failures=0`):

| Model | Transcript (combined) | State (combined) |
|---|---|---|
| qwen3-30b-a3b | 0.733 | **0.848** |
| deepseek-flash | **0.820** | 0.841 |
| gemma-27b | 0.747 | 0.715 |
| gpt5-nano | 0.734 | 0.727 |
| gemini-flash-lite *(issue #96 default)* | 0.641 | 0.580 |
| llama-1b *(control)* | 0.466 | 0.468 |

- Control (`llama-1b`) floors the rubric → the proxy discriminates.
- `gemini-flash-lite` is robustly weak; the Gemini judge inflates it (self-preference: gemini ~0.75
  vs neutral ~0.45) — the neutral judge was worth including.

## 5. Real leaderboard — the ground truth (Blind-A raw LLM score, /5)

Submitting actual backfilled predictions resolved the proxy's ambiguity. **Complete 2×2:**

| Model ↓ / Conditioning → | Transcript | **State** | State gain |
|---|---|---|---|
| **qwen3-30b-a3b** | 4.0 | **4.2 (best)** | **+0.2** |
| deepseek-flash | 3.6 | 3.75 | +0.15 |

### Findings
1. **State-conditioning is a robust win** — +0.15 to +0.2 on *both* models on the real judge.
   Feeding the compact extracted state beats the raw transcript. Adopt it for production.
2. **qwen3-30b-a3b is genuinely the better model** — it beats deepseek-flash in *both* conditionings.
3. **The proxy judge is a coarse ranker only.** Its transcript arm ranked deepseek (0.820) above qwen
   (0.733) — the real judge inverted this (qwen 4.0 > deepseek 3.6). Use the proxy to filter weak
   models, not to choose between strong ones; the real leaderboard is the tiebreaker.
4. deepseek-flash is also more verbose; length may be penalized by the real judge.

**Best submission: `qwen3-30b-a3b · state-conditioned = 4.2`** (up from 0.0 with empty replies).

## 6. Recommendations

- **Model:** `qwen3-30b-a3b` (non-thinking instruct: reliable, cheap, 0 empties, best on the real judge).
- **Conditioning:** structured **state**, not the raw transcript.
- **Do not** ship `gemini-flash-lite` (issue #96's suggested default — weakest of the candidates).
- Keep the **role+goal prompt**, **XML track block + ≤10 tags**, **profile**, and the **echo/empty retry guard**.

## 7. How to reproduce — single full run

The best (4.2) setup is now wired **into the live pipeline** and gated by config, so one ordinary
inference run reproduces it — no backfill/post-processing:

```bash
python run_inference_blindset.py --tid v0plus_compiler_blindset_A --eval_dataset blindset_A --batch_size 16
# (or via Modal: run_experiment.py --backend modal --tid v0plus_compiler_blindset_A ...)
```

`CRS_BASELINE.batch_chat` reads `response_kwargs` from the config and, when `conditioning: state`,
feeds the per-session `ConversationStateV0Plus` (already extracted during retrieval and stashed in
the QU's `last_traces`) as the compact `[LISTENER CONTEXT]` block instead of the transcript; with
`item_format: xml` it presents the track as a delimited `<recommended_track>` block with capped tags;
`echo_retries` regenerates any reply that parrots the metadata. Helpers live in
`mcrs/response_context.py`.

- The standalone scripts (`scripts/backfill_blindset_responses.py`,
  `scripts/backfill_blindset_state.py`) remain for offline re-scoring/iteration but are **not needed**
  to produce a submission.
- **CodaBench gotcha:** the submission *name* = filename minus `.zip`, capped at **64 chars** — keep
  filenames short.

## 8. Enablement status & follow-ups

- **Blind set reproduces 4.2 in a single run.** `configs/v0plus_compiler_blindset_A.yaml`:
  `lm_type: litellm` + `qwen3-30b-a3b`, plus `response_kwargs: {conditioning: state, item_format: xml,
  max_tags: 10, echo_retries: 3}`. The devset config stays `dummy` with no `response_kwargs`
  (default = legacy transcript behaviour), so only the blind set is affected.
- **Wired (this branch):** state side-channel exposed to `batch_chat` via the QU's `last_traces`; XML
  track item + capped tags + no-verbatim prompt line; echo/empty regeneration — all in
  `mcrs/response_context.py` + `mcrs/crs_baseline.py`, config-gated, unit-tested.
- **Follow-ups (not done):** (a) feed `conversation_goal.listener_goal` (leak-safe, on Blind-A, still
  unused) — the best untried lever to push past 4.2; (b) expand the eval slice beyond 8 English-only
  sessions; (c) wire the same options into single-turn `chat()` (only `batch_chat` is on the inference
  path today).
