# Explanation / Response Generation

> **What this covers:** how the system produces the natural-language reply that presents/explains a recommended track. This is a **no-op on devset** configs but **live** on the actual Blind-A/B submission configs (see §3). Plus the scaffolding that exists for future per-track "why was this recommended" explanations.
> **Source of truth:** `mcrs/crs_baseline.py` (turn flow, stage 2) + `mcrs/lm_modules/` (the LM backends) + `mcrs/response_context.py` (state-conditioning + XML item formatting) + `mcrs/system_prompts/` (prompts) + `run_inference_blindset.py` (the `explanation_lm_type` override, blindset-only).
> Last verified: 2026-07-12.

The challenge has two deliverables per turn: **(1)** retrieve 20 tracks, and **(2)** generate a natural-language response. This doc is about deliverable (2) — the "explanation." There are two distinct senses of explanation in the codebase:

- **(A) Conversational response** — the assistant's reply that introduces the top track ("I found *X* by *Y* — moody synth-pop that matches the late-night vibe you asked for…"). This is what `lm_modules` generate. **Off on devset configs, live on the Blind-A/B submission configs** — see §3, this is the part that most needs reading before assuming the shipped submissions have no response text.
- **(B) Per-track provenance** — *why* a specific track surfaced (which retriever branch, which intent). **Not built yet**, but the trace scaffolding for it exists (§4).

---

## 1. Where generation happens in a turn

`CRS_BASELINE.chat()` / `batch_chat()` run two stages (`crs_baseline.py`):

```
stage 0  build system_prompt = roleplay.txt + response_generation.txt [+ personalization + user_profile]
stage 1  RETRIEVE   qu.compile_track_ids(...) → retrieval_items (top-K track IDs)
         recommend_item = item_db.id_to_metadata(retrieval_items[0])   # top track's metadata, or None if empty
stage 2  GENERATE   response = lm.response_generation(system_prompt, session_memory, recommend_item)
return { retrieval_items, recommend_item, response, trace }
```

Key points:

- The LM only sees the **#1 ranked track's metadata** (`recommend_item`), not the full list — generation explains the single top pick.
- Empty retrieval → `recommend_item=None` (the LM is told there's nothing, rather than crashing on `retrieval_items[0]`; eval scores the empty list as zero hits — no popularity backfill to inflate it).
- The **system prompt** is assembled from `mcrs/system_prompts/`:
  - `roleplay.txt` — "You are an expert music recommendation assistant…"
  - `response_generation.txt` — a 6-point instruction: ground the reply in the recommended track, acknowledge match/mismatch, share title/artist/genre/mood, **briefly explain why it's a good match**, and invite follow-up.
  - `personalization.txt` + the user profile string — appended when a `user_id` is present.

---

## 2. The LM backends (`mcrs/lm_modules/`)

`load_lm_module(lm_type, …)` selects a backend by the config's `lm_type`:

| `lm_type` | Class | What it does |
|---|---|---|
| `"dummy"` | `DUMMY_LM` (`dummy.py`) | **No-op.** Returns `""` for every response. Used by all retrieval-only experiments. |
| `"litellm"` | `LITELLM_LM` (`litellm_chat.py`) | API-based generation via a LiteLLM proxy / OpenAI-compatible endpoint. `batch_completion` for batches. |
| `"meta-llama/Llama-3.2-1B-Instruct"` | `LLAMA_MODEL` (`llama.py`) | Local on-device generation with a HF causal LM (chat template, batched generate). |

All three implement the same interface — `response_generation(system_prompt, chat_history, recommend_item)` and `batch_response_generation(...)` — so they're swappable purely via config.

---

## 3. What the code WAS doing vs. what it's doing NOW

**Was (original baseline):** end-to-end *generative* recommendation. The challenge baseline shipped with `LLAMA_MODEL` (Llama-3.2-1B-Instruct) actually generating a response per turn, prompted by `response_generation.txt`. Historical `llama1b_*` rows were pruned from the current leaderboard but remain available in Git history. `LITELLM_LM` was later added (#42) as a cheaper API alternative to running a local model.

**Devset (`state_ranker_v10_*_devset.yaml`):** generation is a true no-op — `lm_type: dummy`, no `explanation_lm_type` override. The devset evaluation scores the *retrieved tracks*, not the prose, so response generation is deliberately skipped there to keep retrieval-quality iteration cheap and fast.

**Blind-A / Blind-B submission configs — generation is LIVE, not a no-op.** `configs/state_ranker_v10_lgbm_blindset_{A,B}.yaml` set `lm_type: dummy` at the top level too, but `run_inference_blindset.py` (`load_crs_baseline(lm_type=config.get("explanation_lm_type", "dummy"), ...)`) reads a **separate** `explanation_lm_type` key that overrides it when present. Both blindset configs set:

```yaml
explanation_lm_type: litellm
explanation_lm_kwargs:
  model_name: openrouter/qwen/qwen3-30b-a3b-instruct-2507
  temperature: 0.0
  max_tokens: 2048
explanation_kwargs:
  template: phase2_best_qwen
  conditioning: latest_state
  item_format: xml
  max_tags: 10
  echo_retries: 0
```

So the actual submitted `prediction.json` responses are generated by `LITELLM_LM` (qwen3-30b-a3b via OpenRouter), with `mcrs/response_context.py` doing state-conditioning (prioritizes the latest extracted state/request over older turns) and rendering the recommended track as a delimited `<recommended_track>` XML block (capped at 10 tags) rather than a raw metadata string — the `phase2_best_qwen` template (`RESPONSE_TEMPLATE_DEFAULTS` in `response_context.py`) bundles these defaults plus a "1-2 concise sentences, honest about constraint conflicts" style instruction. See `docs/research/2026-06-22-phase2-response-template-findings.md` for how this template was selected.

**To reproduce or modify generation:** for devset, set `lm_type` to `"litellm"` or `"meta-llama/Llama-3.2-1B-Instruct"` directly. For a blindset-style config, set `explanation_lm_type`/`explanation_lm_kwargs`/`explanation_kwargs` — the top-level `lm_type` is irrelevant once `explanation_lm_type` is present.

---

## 4. Per-track explanation scaffolding (sense B — not yet built)

A richer explanation — *why this track, from which signal* — needs the retrieval **provenance**, and that is already captured (but unused for prose today). When `CompilerConfig.branch_trace_topk > 0`, `V0PlusCompiler._compile()` returns a `CompileResult` carrying, per turn (`compiler.py`):

- `branch_pools` — each retriever branch's raw top-K `(track_id, score)` hits (named: `bm25`, `dense.*`, `centroid.*`, `lookup.*`).
- `fused` — the RRF-fused list before soft (de)promotes.
- `n_from_fusion` / `n_from_backfill` — how much of the final list is real retrieval vs. popularity padding.

The dataclass docstring states this is persisted *"for downstream rerank / explanation pickup."* That means a future explainer can answer "the top pick came from the **image-SigLIP2 centroid** branch (cover-art similarity to a track you liked) and was reinforced by **BM25** on the artist name" — grounded provenance instead of a hallucinated rationale. The trace is written to the devset trace's `branches` key (`CompileResult.to_trace_dict()`); `scripts/branch_diagnostics.py` already reads it for per-branch recall/hit diagnostics. See [`v0plus_retrieval.md`](v0plus_retrieval.md) §2 for branch names.

**Status:** the data exists; no module yet converts branch provenance into user-facing explanation text. This is the natural place for a future explanation feature to plug in.

---

## Pointers

- Turn flow: `mcrs/crs_baseline.py` (`chat`, `batch_chat`)
- LM backends: `mcrs/lm_modules/{dummy,litellm_chat,llama}.py`
- Prompts: `mcrs/system_prompts/{roleplay,response_generation,personalization}.txt`
- Retrieval provenance for sense-B explanations: [`v0plus_retrieval.md`](v0plus_retrieval.md), `scripts/branch_diagnostics.py`
- Session state that conditions the response: [`session_state.md`](session_state.md)
