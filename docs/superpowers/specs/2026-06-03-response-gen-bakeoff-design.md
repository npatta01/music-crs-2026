# Response-Generation Model Bake-off — Design

**Date:** 2026-06-03
**Branch:** `claude/response-gen-bakeoff`
**Related:** [Issue #96](https://github.com/npatta01/music-conversational-music-recomender-2026/issues/96) (enable response generation — currently `lm_type: "dummy"` forfeits 40% of score)

## Problem

All active configs emit an empty `predicted_response` (`lm_type: "dummy"`). The challenge scores
response text at ~40% (0.30 Gemini-judge + 0.10 Distinct-2). Before flipping a config to a real LLM
(issue #96 §B), we want evidence for **which** generator model to use — across quality, multilingual
ability, and cost — measured on a curated slice rather than chosen on vibes.

The official server-side judge is Gemini, but its prompt is **undisclosed**. We therefore build a
*reconstructed* proxy judge: useful for **relative** ranking between candidates, not as an absolute
predictor of the leaderboard's 0.30 component.

## Approach — decoupled replay

Retrieval output is identical regardless of which LLM writes the response. So instead of re-running
the full retrieval pipeline per candidate (heavy: LanceDB + Qwen-8B encoders on Mac; wasteful), we
**hold retrieval fixed and replay only the response step**:

- The top-1 recommended track per turn already exists in
  `exp/inference/devset/v0plus_compiler_all_retrievers_devset.json` — the same predictions the slice
  was bucketed from.
- For each candidate model, regenerate only the natural-language response over that fixed track +
  conversation history, reusing the production prompt-building path.

This yields a **perfectly controlled A/B**: every model explains the identical track, so observed
differences are purely response quality.

**Production path reused (zero fidelity drift):**
- `mcrs/inference_utils.py::chat_history_parser(conversations, music_crs, target_turn_number)` — builds
  `chat_history` + `user_query`; rewrites music-role turns via `item_db.id_to_metadata`.
- `recommend_item = item_db.id_to_metadata(top_track_id)` — top-1 from existing predictions
  (mirrors `crs_baseline.py:177`).
- `system_prompt = role_play + response_generation` prompt (mirrors `crs_baseline.py:130`).
- Generation via `LITELLM_LM.response_generation(system_prompt, chat_history, recommend_item)`.

**`item_db` source:** reuse the same catalog the config uses (LanceDB, source of truth). If a local
LanceDB is not built, fall back to the HF-backed catalog — both expose `id_to_metadata`; metadata
strings must be consistent across backends.

**Out of scope (separate work):** full-pipeline integration with the LM toggled on (issue #96 §B, a
one-config flip).

## Components

### 1. `mcrs/lm_modules/litellm_chat.py` (modify)
- **Generic passthrough:** add optional `completion_kwargs: dict` to `__init__`; merge it into the
  dict returned by `_completion_kwargs()` (user dict merged last). Handles `reasoning_effort`,
  `extra_body`, `top_p`, `drop_params`, etc. with one change. `**_unused` no longer silently drops
  inference params that are explicitly passed via `completion_kwargs`.
- **api_base wiring fix (issue #96 §4):** only forward `api_base`/`api_key` when truthy. Drop the
  hardcoded `http://localhost:4000` fallback; `self.api_base = api_base or os.environ.get("LITELLM_PROXY_BASE")`
  (no localhost default). Enables direct `openrouter/…` calls authenticated by `OPENROUTER_API_KEY`,
  while still using the proxy when `LITELLM_PROXY_BASE`/`api_base` is set.

### 2. `configs/bakeoff/models.yaml` (new)
Small registry — NOT full pipeline configs:
- `generators`: list of `{tag, model_name, completion_kwargs}`.
- `judges`: `{gemini: {...}, neutral: {...}}`.

### 3. `scripts/response_bakeoff.py` (new)
Replay generation. Inputs: predictions json, slice file
(`exp/subsets/bakeoff_smoke_8.json`), HF dataset (conversations), `models.yaml`.
For each generator: for each (session, turn) in the slice, build inputs via the production helpers,
call `LITELLM_LM.response_generation`, collect. Output: `exp/bakeoff/responses/{tag}.json`
(one record per turn: session_id, turn_number, top_track_id, response).

### 4. `scripts/judge_responses.py` (new)
Panel judge + lexical diversity + report. For each generator's responses:
- **Distinct-2** via `evaluator`'s `compute_lexical_diversity` (reuse, don't reimplement).
- **Panel judge:** Gemini + neutral, each scoring every turn 1–5 on two axes (see Rubric).
  Normalize `(s−1)/4`, average across turns and across the panel.
Output: `exp/bakeoff/report.md` (ranked table) + `exp/bakeoff/report.json` (raw scores).

## Candidates & judges

**Generators (10, all non-thinking):**

| tag | model_name | completion_kwargs | role |
|---|---|---|---|
| llama-1b | meta-llama/llama-3.2-1b-instruct | — | control / floor |
| gemma-4b | google/gemma-3-4b-it | — | small |
| llama-3b | meta-llama/llama-3.2-3b-instruct | — | small |
| qwen3-8b | qwen/qwen3-8b | `extra_body: {reasoning: {enabled: false}}` | small |
| deepseek-flash | deepseek/deepseek-v4-flash | — | repo-wired |
| gemma-12b | google/gemma-3-12b-it | — | mid |
| gemma-27b | google/gemma-3-27b-it | — | mid (judge-family affinity) |
| qwen3-30b-a3b | qwen/qwen3-30b-a3b-instruct-2507 | — | mid (already non-thinking) |
| gpt5-nano | openai/gpt-5-nano | `reasoning_effort: minimal` | latest small OpenAI |
| gemini-flash-lite | google/gemini-2.5-flash-lite | — | reference (issue's pick) |

**Judge panel:**
- Gemini: `google/gemini-2.5-flash` (approximates real judge).
- Neutral: `openai/gpt-5-mini` (or deepseek) — avoids self-preference when generator is Gemini/Gemma.
- Both score; report panel average + per-judge so the self-preference gap is visible.

## Rubric (G-Eval style)

Per turn, two axes scored 1–5:
- **Personalization** — tailored to the listener's stated taste / request / history, and replies in the
  listener's language.
- **Explanation Quality** — clear "why this track", honest about mismatch instead of overselling,
  natural, non-repetitive.

Normalize each `(s−1)/4 → [0,1]`. Report Personalization and Explanation **separately**, plus a
**combined judge figure = the equal-weight mean of the two normalized axes** (the official split
between the two within the 0.30 weight is undisclosed, so we weight them equally). Distinct-2 is
reported as its own column, not folded into the judge figure.

## Smoke slice

`exp/subsets/bakeoff_smoke_8.json` — 8 sessions, bucketed by per-session mean nDCG@20 over 8 turns:
- **Good x4:** cb99c2a0 (0.643), 3dfbbe08 (0.525), 73301a8d (0.445), 2573807b (0.391)
- **Mediocre x2:** c228efb8 (0.088), 3a4224d3 (0.080, ambient/non-music)
- **Bad x2:** d6e50fb5 (0.000), 907921a3 (0.000, lyric-recall) — test honest-mismatch handling

Good sessions test confident grounded explanation; bad ones test the prompt's
"acknowledge the mismatch instead of overselling" guideline.

## Testing (TDD)

Unit tests with **mocked** `litellm.completion`:
1. `completion_kwargs` merges through to the completion call; `api_base` omitted when None/unset;
   proxy path preserved when `LITELLM_PROXY_BASE` set.
2. Replay rebuilds `chat_history` identically to `chat_history_parser` for a known fixture session;
   `recommend_item` resolves from the top predicted track.
3. Judge output parses to normalized scores; Distinct-2 wiring returns expected value on a fixture.

Real API calls happen only in the smoke run, not in unit tests.

## Success criteria

- Harness runs end-to-end on the 8-session slice and produces a ranked comparison
  (Distinct-2 + panel judge per model).
- Rubric discriminates: the 1B control scores clearly below the mid-tier models.
- Total cost well under $1.

## Known limitations (documented, not fixed here)

- **English-only slice** — multilingual ability (the key small-vs-large discriminator) is NOT tested.
  Follow-up: add non-English sessions before any blind submission.
- **Proxy judge ≠ official judge** — undisclosed prompt; relative ranking signal only.
- **Retrieval held fixed** — does not test full-pipeline integration with the LM on (issue #96 §B).
