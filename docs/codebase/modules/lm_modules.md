# LM / Response Generation Modules

## Purpose

`mcrs/lm_modules/` is the natural-language response generation layer of the CRS pipeline. After the retrieval module selects candidate tracks, the LM module receives the system prompt, the full chat history, and the top-ranked item, then generates a conversational assistant response that introduces the recommendation to the user.

It sits at the end of the per-turn pipeline:

```
QuModule (query understanding)
  -> RetrievalModule (candidate tracks)
    -> LM Module (natural-language response)
      -> output JSON
```

The layer is accessed exclusively through `CRS_BASELINE` in `mcrs/crs_baseline.py`, which calls `load_lm_module()` at construction time and then calls `response_generation` / `batch_response_generation` at inference time.

---

## Files

| File | Responsibility |
|------|----------------|
| `__init__.py` | Exports `load_lm_module()` factory; dispatches on `lm_type` string to return the correct backend instance. |
| `dummy.py` | No-op LM that returns empty strings; used for retrieval-only experiments where response text is irrelevant. |
| `llama.py` | Local HuggingFace Llama inference via `transformers`; loads model weights on GPU, supports single and batched generation. |
| `litellm_chat.py` | LiteLLM proxy-backed chat LM; wraps `litellm.completion` / `litellm.batch_completion` for any OpenAI-compatible endpoint. |
| `litellm_client.py` | Standalone, lower-level LiteLLM dataclass client (`LiteLLMChatClient`) with no Modal dependency; used directly by `modal/app.py` for smoke tests and cache-status checks. |

---

## Public API

### Factory function

**`load_lm_module(lm_type, device, attn_implementation, dtype, lm_kwargs=None)`** — `mcrs/lm_modules/__init__.py:4`

Instantiates and returns the appropriate LM backend. `lm_type` is the dispatch key:

| `lm_type` value | Returns |
|-----------------|---------|
| `"dummy"` | `DUMMY_LM()` |
| `"litellm"` | `LITELLM_LM(**lm_kwargs)` |
| `"meta-llama/Llama-3.2-1B-Instruct"` | `LLAMA_MODEL(model_name, device, attn_implementation, dtype)` |
| anything else | raises `ValueError` |

`device`, `attn_implementation`, and `dtype` are forwarded only to `LLAMA_MODEL`; they are silently ignored for `dummy` and `litellm` backends.

---

### DUMMY_LM — `mcrs/lm_modules/dummy.py:1`

```python
class DUMMY_LM:
    def response_generation(self, system_prompt, session_memory, recommend_item) -> str
    def batch_response_generation(self, system_prompts, session_memories, recommend_items) -> list[str]
```

`response_generation` always returns `""`. `batch_response_generation` returns `[""] * len(system_prompts)`.

---

### LLAMA_MODEL — `mcrs/lm_modules/llama.py:5`

```python
class LLAMA_MODEL:
    def __init__(self, model_name="meta-llama/Llama-3.2-1B-Instruct",
                 device="cuda", attn_implementation="eager",
                 dtype=torch.bfloat16)

    def response_generation(self, sys_prompt: str, chat_history: list,
                            recommend_item: str, max_new_tokens=512,
                            response_format=None) -> str

    def batch_response_generation(self, sys_prompts: list[str],
                                  chat_histories: list[list],
                                  recommend_items: list[str],
                                  max_new_tokens=64) -> list[str]
```

Loads a HuggingFace causal LM at init time (`_load_model`, line 15). Both generation methods call `_format_chat_history` (line 20) to assemble the prompt via `apply_chat_template`, then run `model.generate` under `torch.inference_mode`.

---

### LITELLM_LM — `mcrs/lm_modules/litellm_chat.py:29`

```python
class LITELLM_LM:
    def __init__(self, model_name: str, api_base: str | None = None,
                 api_key: str | None = None, temperature: float = 0.7,
                 max_tokens: int = 512, **_unused)

    def response_generation(self, sys_prompt: str, chat_history: list,
                            recommend_item: Any, max_new_tokens: int = 512,
                            response_format=None) -> str

    def batch_response_generation(self, sys_prompts: list[str],
                                  chat_histories: list[list],
                                  recommend_items: list,
                                  max_new_tokens: int = 64) -> list[str]
```

`api_base` falls back to `$LITELLM_PROXY_BASE` (default `http://localhost:4000`); `api_key` falls back to `$LITELLM_PROXY_KEY` (default `"sk-anything"`). `litellm` is imported lazily inside each method to avoid a hard import at module load time.

---

### LiteLLMChatClient — `mcrs/lm_modules/litellm_client.py:8`

```python
@dataclass
class LiteLLMChatClient:
    model_name: str
    api_base: str | None = None
    api_key: str | None = None
    temperature: float = 0.0
    max_tokens: int = 128
    extra_params: dict[str, Any] = field(default_factory=dict)

    def build_request_kwargs(self, messages: list[dict[str, str]],
                             cache: dict[str, Any] | None) -> dict[str, Any]

    def chat(self, messages: list[dict[str, str]],
             cache: dict[str, Any] | None = None) -> str
```

Lower-level dataclass wrapping `litellm.completion`. Validates `model_name` and `max_tokens` in `__post_init__` (line 18). `build_request_kwargs` (line 25) is callable externally so that `modal/app.py` can inspect the request before it fires (used for cache-hit detection). `_kwargs` (line 41) is an alias for `build_request_kwargs`; it is not used anywhere internally or externally.

---

## Key Data Structures / Config

**Chat message format** — all three non-dummy backends pass and receive the standard OpenAI messages list:
```python
[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, ...]
```

**`_format_chat_history` template** (`llama.py:20`) — appends `recommend_item` as an `assistant` turn before calling `apply_chat_template(..., add_generation_prompt=True)`, meaning the model sees the item string in the assistant role and is prompted to continue that turn.

**`_build_messages` template** (`litellm_chat.py:13`) — formats the `recommend_item` dict/string as a final `user` turn with the instruction "Recommend the following track...". This is structurally different from the `LLAMA_MODEL` convention (assistant role vs. user role).

**`load_lm_module` dispatch key** (`__init__.py:4`) — only the exact string `"meta-llama/Llama-3.2-1B-Instruct"` routes to `LLAMA_MODEL`. Any other HuggingFace model path would fall through to the `ValueError` branch; new Llama variants require an explicit `elif` addition.

**`lm_kwargs`** — an opaque dict forwarded only to `LITELLM_LM(**lm_kwargs)`. The `**_unused` in `LITELLM_LM.__init__` silently drops any unexpected keys; `LLAMA_MODEL` is initialized with positional args and does not receive `lm_kwargs`.

---

## Internal Flow

1. **Construction** — `CRS_BASELINE.__init__` calls `load_lm_module(lm_type, device, attn_implementation, dtype, lm_kwargs)` (`crs_baseline.py:78`). The factory in `__init__.py:4` instantiates one of `DUMMY_LM`, `LITELLM_LM`, or `LLAMA_MODEL` and returns it; the object is stored as `self.lm`.

2. **Single-turn inference** — `CRS_BASELINE.process_turn` (around `crs_baseline.py:179`) assembles `system_prompt` from role/generation prompt templates, then calls `self.lm.response_generation(system_prompt, self.session_memory, recommend_item)`.

3. **Batch inference** — `CRS_BASELINE` checks `hasattr(self.lm, 'batch_response_generation')` (`crs_baseline.py:270`) and calls it when present; otherwise it loops over `response_generation`. All four classes expose `batch_response_generation`, so the fallback is never hit in practice.

4. **LLAMA_MODEL generation path** — `response_generation` calls `_format_chat_history` -> `tokenizer(...)` -> `model.generate` -> `batch_decode(outputs[:, input_ids.shape[1]:]...)` to strip the prompt tokens from the output.

5. **LITELLM_LM generation path** — `response_generation` calls module-level `_build_messages` -> `litellm.completion(**kwargs)` -> extracts `choices[0].message.content`. `batch_response_generation` calls `litellm.batch_completion` and wraps each response in a `try/except`, returning `""` on any per-item failure.

6. **LiteLLMChatClient** operates independently of the above. It is called directly by `modal/app.py:chat_once_with_cache_status` for Modal smoke-test endpoints; it is not wired into `CRS_BASELINE`.

---

## Dependencies

**Internal mcrs modules:**
- None — `lm_modules` has no imports from other `mcrs.*` packages. It is a leaf node.

**External libraries:**
- `torch`, `transformers` (HuggingFace) — required only by `LLAMA_MODEL` (`llama.py`)
- `litellm` — required by `LITELLM_LM` (`litellm_chat.py`) and `LiteLLMChatClient` (`litellm_client.py`); imported lazily inside methods to avoid hard dependency at module load
- `os` — used in `litellm_chat.py` to read `LITELLM_PROXY_BASE` / `LITELLM_PROXY_KEY` environment variables
- `dataclasses` — used by `litellm_client.py`

**Callers:**
- `mcrs/crs_baseline.py` — primary consumer via `load_lm_module()` and the `response_generation` / `batch_response_generation` protocol
- `modal/app.py` — directly imports `LiteLLMChatClient` for Modal smoke-test endpoints

---

## Gotchas

1. **Prompt role asymmetry**: `LLAMA_MODEL._format_chat_history` places `recommend_item` as an `assistant` role message (`llama.py:23`), while `LITELLM_LM._build_messages` places it as a `user` role message (`litellm_chat.py:17-25`). This means the two backends receive structurally different prompts for the same input; outputs are not comparable across backends.

2. **Hard-coded model string in factory**: `__init__.py:11` dispatches to `LLAMA_MODEL` only when `lm_type == "meta-llama/Llama-3.2-1B-Instruct"`. Using any other model path (e.g., a 3B or 8B Llama) raises `ValueError` without reaching `LLAMA_MODEL`. The `LLAMA_MODEL` class itself accepts any HuggingFace model name — only the factory is restricted.

3. **`LiteLLMChatClient` is not in the `load_lm_module` dispatch**: it cannot be selected via `lm_type`. It is only used directly in `modal/app.py`; it is not interchangeable with `LITELLM_LM` for pipeline purposes.

4. **`_kwargs` alias is dead code**: `LiteLLMChatClient._kwargs` (`litellm_client.py:41`) is an alias for `build_request_kwargs` that is called nowhere in the codebase.

5. **`response_format` parameter accepted but ignored**: Both `LLAMA_MODEL.response_generation` and `LITELLM_LM.response_generation` accept a `response_format` keyword argument that is never used inside those methods. It appears to be a stub for future structured-output support.

6. **`max_new_tokens` default mismatch**: `LITELLM_LM.response_generation` defaults to `max_new_tokens=512` but `batch_response_generation` defaults to `64` (`litellm_chat.py:59` vs `74`). Same pattern in `LLAMA_MODEL` (`llama.py:27` vs `37`). Batched calls produce much shorter responses by default.

7. **No `__init__.py` re-export for `LITELLM_LM` or `LiteLLMChatClient`**: `__init__.py` only imports `LLAMA_MODEL` and `DUMMY_LM` at the top level (lines 1-2). `LITELLM_LM` is imported lazily inside `load_lm_module`. `LiteLLMChatClient` is never re-exported from the package; callers must import it directly from `mcrs.lm_modules.litellm_client`.
