# Explanation / Response Generation

> **What this covers:** how the system produces the natural-language reply that presents/explains a recommended track — and why that path is currently a **no-op** in the experiment configs. Plus the scaffolding that exists for future per-track "why was this recommended" explanations.
> **Source of truth:** `mcrs/crs_baseline.py` (turn flow, stage 2) + `mcrs/lm_modules/` (the LM backends) + `mcrs/system_prompts/` (prompts).
> Last verified: 2026-06-01 (code at `1a8aee5`).

The challenge has two deliverables per turn: **(1)** retrieve 20 tracks, and **(2)** generate a natural-language response. This doc is about deliverable (2) — the "explanation." There are two distinct senses of explanation in the codebase:

- **(A) Conversational response** — the assistant's reply that introduces the top track ("I found *X* by *Y* — moody synth-pop that matches the late-night vibe you asked for…"). This is what `lm_modules` generate. **Live, but currently turned off.**
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

**Now (current experiments):** generation is **deliberately disabled**. ~52 configs set `lm_type: "dummy"` — with the inline note *"response generation is downstream of this experiment's scope."* Only ~5 (archived) configs still use the Llama backend. The reasoning:

- The project's headline metric is **retrieval quality** (NDCG@20 over the candidate list); the devset evaluation scores the *retrieved tracks*, not the prose. Spending GPU/API budget on response text that isn't measured would slow every experiment for no signal.
- Generation is **orthogonal to and downstream of** retrieval — you can bolt any of the three backends back on without touching the retrieval pipeline. So it's kept as a no-op until retrieval is settled.

**To turn generation back on:** set `lm_type` to `"litellm"` (with `lm_kwargs` for `model_name`/`api_base`) or `"meta-llama/Llama-3.2-1B-Instruct"` in the config. No code change — the factory and the two-stage flow already support it. The final submission packaging path will need a real backend here; the devset experiments don't.

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
