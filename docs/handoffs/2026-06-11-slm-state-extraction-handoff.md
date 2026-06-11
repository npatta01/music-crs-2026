# Handoff: Fine-tune an SLM for V1 State Extraction

**Date:** 2026-06-11
**Source branch:** `claude/busy-ishizaka-f3d4a7` (pushed to origin; contains everything referenced below)
**Goal:** replace the API extractor (deepseek-v4-flash) with a fine-tuned small
open-weight model, distilling the very large prompt into weights. Quality bar =
match the teacher on the replay/eval harnesses below; payoff = cost ≈ 0,
latency down, and the ~20k-token prompt disappears.

---

## 1. Current production extractor (the teacher)

| What | Where |
|---|---|
| Model | `openrouter/deepseek/deepseek-v4-flash` (temperature 0.0, max_tokens 8000) |
| Prompt | `mcrs/conversation_state/prompts/current.py` (~105KB source; rendered prompt ≈ 20k tokens incl. few-shots). Fallback/reference prompt: `prompts/previous.py` |
| Output schema | `mcrs/conversation_state/schema.py` — `ConversationStateV1` (fact-first: `current_request`, `facts[]` with type/facet/value/role/anchor_use/relation/reuse, `exclusions`, `track_feedback`, `temporal_constraint`, `lyrical_theme`, `referenced_track_ids`) + projection to `ConversationStateV0Plus` |
| Call site | `LiteLLMExtractor` in `mcrs/qu_modules/compiler_v0plus_qu.py:283` (`.extract()` at line 395) — this is the code that renders the exact input messages from a conversation; reuse it to generate SFT inputs |
| Config | `configs/v0plus_compiler_pruned_resolved_tags_devset.yaml` → `qu_kwargs.extractor` |

Teacher quality (routing bake-off): lyric F1 0.92, feature F1 0.93, 0% null/format failures.

**Why the extractor matters:** state extraction quality is upstream of all
retrieval ([memory] fix representation before rerankers). Extraction is also
mid-shift to **verbatim/surface-form values** (the LLM stops normalizing
phrases; a downstream tag-resolver grounds them — see
`mcrs/qu_modules/tag_resolver.py`). Train the SLM on the CURRENT prompt's
behavior, but know this shift exists when comparing against older state dumps.

## 2. Extracted-state data (SFT targets)

**Primary: full devset, 8000 turns, current prompt, deepseek-v4-flash:**

```
exp/inference/devset/v0plus_compiler_pruned_resolved_tags_devset_trace.jsonl   # 4.4GB merged
exp/inference/devset/v0plus_compiler_pruned_resolved_tags_devset.run_*shard_{0..4}_trace.jsonl
```
(Also on the Modal `music-crs-results` volume; re-download with
`python modal/download_results.py --tid v0plus_compiler_pruned_resolved_tags_devset`.)

Each JSONL line: `session_id`, `turn_number`, `user_id`, `trace.state` (the V1
state the compiler consumed), plus `trace.resolver`, `routing_tags`,
`intent_mode`. **Caveat:** `trace.state` is the parsed/merged state, not the
raw completion string — minor formatting deltas vs the literal LLM output are
possible.

**The litellm cache does NOT contain inputs.** Format is
`{timestamp, response}` keyed by request-hash
(`cache/litellm/` locally as `dense_litellm/`; Modal volume `music-crs-cache`
under `litellm/<2-hex>/<2-hex>/music-crs:<sha>.json`). Responses (incl. raw
extraction completions) are there, but you cannot recover the prompt from the
key. **To build SFT pairs: re-render inputs with `LiteLLMExtractor`'s prompt
builder over the devset conversations (deterministic, free) and pair with
`trace.state` (or the cached raw completion if you match hashes by re-rendering).**

**Conversations (inputs):** HF `talkpl-ai/TalkPlayData-Challenge-Dataset`
split `test` (devset, 1000 sessions × 8 turns) and `train` (15,199 sessions —
unused so far, the expansion pool). Feed FULL history per turn, not a 3-turn
window ([memory] truncation hurt replay evals).

## 3. Eval harnesses (in priority order)

1. `mcrs/conversation_state/replay_eval.py` — in-distribution replay eval of
   extraction quality (built on the codex branch; ~790 lines).
2. `mcrs/conversation_state/state_fact_eval.py`, `state_role_eval.py` — fact
   and role-level scoring.
3. Focused-110 frozen states (probe set, NOT training data):
   `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_goal_current_all110_reprojected_audit.jsonl`
4. Hand-labeled gold (~800 turns, Claude-authored labels):
   `state_elements_focused70_labels.json`, `state_fact_labels_v1.json` and
   relatives in the same analysis dir. **Warning:** machine-authored
   `state_experiment_pack.json` labels ran ~75% noisy historically — audit
   any label pack before trusting it.
5. End-to-end: swap the extractor in the config, run the paired seeded smoke
   (`python run_experiment.py --backend modal --tid v0plus_compiler_pruned_resolved_tags_devset --num_sessions 50`),
   compare per-turn paired vs the deepseek run (samples CSVs in
   `exp/scores/devset/`). Same seeded sessions guaranteed by the wrapper.

## 4. Costs (live OpenRouter pricing, 2026-06-11)

| Item | Number |
|---|---|
| deepseek-v4-flash | $0.0983/M input, $0.1966/M output |
| deepseek-v4-pro | $0.435/M in, $0.87/M out |
| Rendered prompt | ≈20k tokens input/turn + ~1k output |
| Devset extraction (8000 turns) | already paid; states in the trace above |
| Train-split extraction (121,592 turns) | ≈$260–290 uncached; ≈$50 if provider prompt-caching hits the 20k static prefix. **Worth paying only as SFT data generation** (more teacher demonstrations), not for features — the miss audit (`experiments/miss_audit_2026_06_11.md`) showed ranker features don't need state |

## 5. Serving infra for the fine-tuned SLM

- Modal vLLM app already exists: `music-crs-vllm` (serves qwen3-embedding-8b,
  scale-to-zero). Pattern in `modal/vllm_serve.py`. **Pin `vllm>=0.11.2`**
  (0.11.0 breaks on transformers 5.x).
- Wiring an OpenAI-compatible endpoint into the extractor = set
  `qu_kwargs.extractor.model_name` to the endpoint (litellm route); the
  config plumbing already supports custom api_base via the encoder pattern.
- Candidate sizes: Qwen3-4B-Instruct first (the task is structured JSON
  emission against a fixed schema); 1.7B as the stretch-cheap arm.

## 6. Gotchas

- **Strict JSON schema output is the whole game** — teacher has 0% format
  failures; an SLM that drops to even 2% null breaks the pipeline. Use
  constrained decoding (vLLM guided_json with the Pydantic schema) from day 1.
- Per-turn extraction consumes full conversation history; turn 8 inputs are
  long. Set SLM context ≥16k (without the 20k teacher prompt, history alone
  is ~1–3k tokens, so this is comfortable).
- The state is extracted PER TURN independently in the current design; merge
  semantics live downstream in the compiler. Don't train on merged states
  from later turns as if they were single-turn outputs — pair each turn's
  state with that turn's history only.
- Role-typed state work (#111, branch `claude/flamboyant-lovelace-a0784f`)
  and the verbatim-extraction shift may change the schema after you train —
  coordinate before investing in a large training run; consider holding out
  the prompt-version question until #111 lands.
- Evidence is context-bound per branch ([memory]): verify any cited prior
  result still holds on the branch you're working from.

## 7. Suggested sequence

1. Build SFT pairs: re-render inputs via `LiteLLMExtractor` over devset
   conversations → pair with `trace.state` JSON (8k examples, free).
2. Train/val split by SESSION (not turn) to avoid history leakage.
3. Fine-tune Qwen3-4B with guided-JSON eval each epoch; gate on
   `replay_eval.py` parity with teacher.
4. If parity is close, generate +20–50k more pairs from the train split
   (~$50–120 with caching) and retrain.
5. End-to-end paired seeded smoke (50 sessions) vs the deepseek extractor
   before any full-devset claim. Full devset needs owner approval.
