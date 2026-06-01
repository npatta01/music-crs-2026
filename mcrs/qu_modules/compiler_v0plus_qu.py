"""v0+ Compiler wrapped as a QU module for `CRS_BASELINE`.

`V0PlusCompilerQU` owns the full v0+ pipeline as one unit:

    session_memory ──► extract state (LLM, gemma-3-12b) ──► Resolver ──► Compiler ──► top-1000 track_ids

It plugs into `load_qu_module` like the other QUs, but unlike `LLMRewriteQU`
(which returns a query string for the downstream retriever) this one returns
ranked `track_ids` directly. The `CRS_BASELINE` `chat`/`batch_chat` methods
special-case QUs that expose `compile_track_ids(...)` and skip the
`retrieval_type` step entirely.

## Construction inputs (from YAML qu_kwargs)

| Field | Purpose |
|---|---|
| `extractor` | LLM extractor settings: model_name, api_base, temperature, max_tokens |
| `lancedb` | db_uri, table_name, eager_vector_fields — used for BOTH the LanceDbCatalog (metadata + vectors) and the LanceDbRetriever (BM25 + dense channels) |
| `encoder` | Qwen3 encoder settings: backend, device, batch_size, query_instruct |
| `compiler` | `CompilerConfig` knobs (field_boosts, centroid_alpha, ...) |
| `resolver` | `score_cutoff`, topks |

## Preconditions for production runs

1. LanceDB table built at `lancedb.db_uri` / `lancedb.table_name` with the
   metadata + the three `*_qwen3_embedding_0_6b` vector columns + FTS
   indexes on the BM25 text fields. Build it once via
   `scripts/build_lancedb_index.py`; that step (and only that step)
   requires HF auth (`uvx hf auth login`) for the source datasets.
2. LiteLLM proxy running (or OpenRouter API key set) so the extractor LLM
   call can reach `gemma-3-12b-it`.

Inference itself does NOT touch HuggingFace — `LanceDbCatalog` reads the
prebuilt LanceDB locally. For smoke / unit tests, inject `_overrides` to
swap in fakes (see `tests/test_v0plus_compiler_qu.py`).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

# `chat_history_parser` (mcrs/inference_utils.py) rewrites music-role content
# from a bare track_id into the line-oriented metadata blob returned by
# `MusicCatalogDB.id_to_metadata`, starting with:
#   "track_id: 2445ed62-...\ntrack_name: Heart-Shaped Box\n..."
# Other QU types want that prose form. The v0+ extractor wants clean track_ids
# so the LLM has a clean `played_track_ids` list to reference. We undo the
# rewrite here: pull the UUID off the front, then let the catalog produce the
# human-readable label.
_METADATA_BLOB_TRACK_ID_RE = re.compile(r"^track_id:\s*([0-9a-fA-F\-]{36})\b")

from experiments.analysis.conversation_state_extraction_bakeoff.prompts import (
    build_messages,
    json_schema_for_response_format,
)
from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
    ConversationStateV0Plus,
)


def _resolve_prompt_fns(prompt_version: str):
    """Return (build_messages, json_schema_for_response_format) for a prompt
    version. Default 'v1' is the original bakeoff prompt (back-compat). 'v3' is
    the generous-extraction + catalog-bridging rewrite from the
    extractor_prompt_v2 analysis package."""
    pv = (prompt_version or "v1").lower()
    if pv in ("v1", "bakeoff", "default"):
        return build_messages, json_schema_for_response_format
    if pv in ("v2", "v2c"):
        from experiments.analysis.extractor_prompt_v2.prompts_v2 import (
            build_messages as bm,
            json_schema_for_response_format as schema,
        )
        return bm, schema
    if pv == "v3":
        from experiments.analysis.extractor_prompt_v2.prompts_v3 import (
            build_messages as bm,
            json_schema_for_response_format as schema,
        )
        return bm, schema
    if pv == "v4":
        from experiments.analysis.extractor_prompt_v2.prompts_v4 import (
            build_messages as bm,
            json_schema_for_response_format as schema,
        )
        return bm, schema
    raise ValueError(f"unknown extractor prompt_version: {prompt_version!r}")
from mcrs.embeddings.base import EmbeddingClient
from mcrs.embeddings.qwen3_embedding import Qwen3EmbeddingClient
from mcrs.qu_modules.compiler_v0plus import (
    CentroidOnlyBranch,
    CompileResult,
    CompilerConfig,
    DenseBranch,
    V0PlusCompiler,
)
from mcrs.qu_modules.user_embeddings import UserEmbeddings
from mcrs.qu_modules.fuzzy_matcher import FuzzyMatcher, RapidfuzzCatalogMatcher
from mcrs.qu_modules.resolver_v0plus import V0PlusResolver
from mcrs.qu_modules.v0plus_catalog import CompilerCatalog
from mcrs.retrieval_modules.base import Retriever

logger = logging.getLogger(__name__)


def _with_no_store_cache(call_kwargs: dict[str, Any]) -> dict[str, Any]:
    request_kwargs = dict(call_kwargs)
    cache_control = request_kwargs.get("cache")
    cache_control = dict(cache_control) if isinstance(cache_control, dict) else {}
    cache_control["no-store"] = True
    request_kwargs["cache"] = cache_control
    return request_kwargs


def _response_for_cache(response: Any) -> Any:
    model_dump_json = getattr(response, "model_dump_json", None)
    if callable(model_dump_json):
        return model_dump_json()
    return response


def _store_litellm_cache_entry(
    litellm_module,
    response: Any,
    call_kwargs: dict[str, Any],
) -> None:
    cache = getattr(litellm_module, "cache", None)
    add_cache = getattr(cache, "add_cache", None)
    if add_cache is None:
        return
    try:
        add_cache(_response_for_cache(response), **call_kwargs)
    except Exception as exc:
        logger.warning("v0+ extractor cache store failed: %s: %s", type(exc).__name__, exc)


async def _async_store_litellm_cache_entry(
    litellm_module,
    response: Any,
    call_kwargs: dict[str, Any],
) -> None:
    cache = getattr(litellm_module, "cache", None)
    async_add_cache = getattr(cache, "async_add_cache", None)
    if async_add_cache is not None:
        try:
            await async_add_cache(_response_for_cache(response), **call_kwargs)
        except Exception as exc:
            logger.warning(
                "v0+ extractor async cache store failed: %s: %s",
                type(exc).__name__,
                exc,
            )
        return

    await asyncio.to_thread(_store_litellm_cache_entry, litellm_module, response, call_kwargs)


# ----------------------------------------------------------------------
# Encoder factory — shared by single-encoder + encoder-map YAML schemas
# ----------------------------------------------------------------------


def _build_encoder(enc_cfg: dict) -> EmbeddingClient:
    """Build one EmbeddingClient from a YAML encoder spec.

    Supported backends:
      - `local` / (default): in-process Qwen3-0.6B (CPU/CUDA), good for tests.
      - `litellm`: API call via LiteLLM SDK (e.g. DeepInfra Qwen3 endpoint).
      - `modal`: deployed `Qwen3Encoder` Modal class (legacy single-encoder).
      - `modal_multimodal`: shared `MultimodalTextEncoder` Modal class
        exposing both SigLIP-2 text and CLAP-music text. Pick which method to
        call by setting `method: "embed_siglip_text"` or `"embed_clap_text"`.
    """
    backend = str(enc_cfg.get("backend", "local")).lower()

    if backend == "modal":
        from mcrs.embeddings.modal_qwen3_client import ModalQwen3EmbeddingClient

        return ModalQwen3EmbeddingClient(
            app_name=enc_cfg.get("modal_app_name", "music-crs"),
            cls_name=enc_cfg.get("modal_cls_name", "Qwen3Encoder"),
        )

    if backend == "modal_multimodal":
        # Shared SigLIP-2 + CLAP-music text-side service. The `method` key
        # picks which RPC the local client calls (`embed_siglip_text` /
        # `embed_clap_text`). One container hosts both models so the smoke
        # test pays one warm-up.
        from mcrs.embeddings.modal_multimodal_client import (
            ModalMultimodalTextEmbeddingClient,
        )

        method = str(enc_cfg.get("method", "")).strip()
        if method not in {"embed_siglip_text", "embed_clap_text"}:
            raise ValueError(
                f"modal_multimodal encoder needs method=embed_siglip_text "
                f"or method=embed_clap_text; got {method!r}"
            )
        return ModalMultimodalTextEmbeddingClient(
            app_name=enc_cfg.get("modal_app_name", "music-crs"),
            cls_name=enc_cfg.get("modal_cls_name", "MultimodalTextEncoder"),
            method=method,
        )

    if backend == "litellm":
        from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient

        api_key = enc_cfg.get("api_key") or os.environ.get("DEEPINFRA_API_KEY")
        return LiteLLMEmbeddingClient(
            model_name=enc_cfg.get("model_name", "openai/Qwen/Qwen3-Embedding-0.6B"),
            api_base=enc_cfg.get("api_base", "https://api.deepinfra.com/v1/openai"),
            api_key=api_key,
            batch_size=int(enc_cfg.get("batch_size", 32)),
            encoding_format=enc_cfg.get("encoding_format", "float"),
        )

    if backend == "local":
        return Qwen3EmbeddingClient(
            model_name=enc_cfg.get("model_name", "Qwen/Qwen3-Embedding-0.6B"),
            device=enc_cfg.get("device", "cpu"),
            torch_dtype_name=enc_cfg.get("torch_dtype", "float32"),
            max_length=int(enc_cfg.get("max_length", 512)),
            batch_size=int(enc_cfg.get("batch_size", 8)),
            padding_side=enc_cfg.get("padding_side", "left"),
            query_instruct=enc_cfg.get("query_instruct", ""),
        )

    raise ValueError(
        f"Unknown encoder.backend={backend!r}; expected one of "
        f"'local', 'litellm', 'modal', 'modal_multimodal'."
    )


# ----------------------------------------------------------------------
# Extractor LLM adapter
# ----------------------------------------------------------------------


def _hard_filter_is_valid(hf: Any) -> bool:
    """A release_date filter is usable only if its bounds are well-formed."""
    if not isinstance(hf, dict):
        return False
    op = hf.get("op")
    s, e = hf.get("start"), hf.get("end")
    if op == "between":
        return isinstance(s, str) and isinstance(e, str) and s <= e
    if op == ">":
        return isinstance(s, str)
    if op == "<":
        return isinstance(e, str)
    return False


def _sanitize_parsed_state(parsed: Any) -> Any:
    """Generic graceful degradation BEFORE schema validation: a single bad
    optional field should never discard the whole turn's state (→ empty pool).

    Currently: drop malformed `hard_filters` (e.g. a `between` with start > end)
    rather than letting one bad entry fail validation of the entire state. Era /
    decade handling lives in `release_year_range`, which the LLM fills using
    world knowledge and the schema self-normalizes (swaps inverted bounds) — no
    code-side date parsing.
    """
    if not isinstance(parsed, dict):
        return parsed
    hfs = parsed.get("hard_filters")
    if isinstance(hfs, list):
        parsed["hard_filters"] = [hf for hf in hfs if _hard_filter_is_valid(hf)]
    return parsed


@dataclass
class LiteLLMExtractor:
    """Calls a hosted LLM (via litellm) with the v0+ extraction prompt and
    strict json_schema response_format. Returns a parsed
    ConversationStateV0Plus or None on failure."""

    model_name: str
    api_base: str | None = None
    api_key: str | None = None
    temperature: float = 0.0
    max_tokens: int = 1500
    timeout_s: int = 90

    # Which extraction prompt to use. "v1" = original bakeoff prompt (default,
    # back-compat). "v3" = generous-extraction + catalog-bridging rewrite (see
    # experiments/analysis/extractor_prompt_v2/). Resolved to functions in
    # __post_init__.
    prompt_version: str = "v1"

    # Temperature used for the JSON-decode retry. The LLM occasionally enters
    # a degenerative-output mode (one valid field followed by a stutter of
    # whitespace tokens until max_tokens), which is a deterministic function
    # of (model, prompt, temperature). Bumping temperature for the retry both
    # bypasses the LiteLLM cache (key includes temperature) and shifts the
    # sampling trajectory off the degenerative path.
    retry_temperature: float = 0.3

    def __post_init__(self):
        self._build_messages_fn, self._schema_fn = _resolve_prompt_fns(self.prompt_version)

    def _build_kwargs(
        self,
        conversation: list[dict[str, Any]],
        played_track_ids: list[str],
        temperature: float | None = None,
    ) -> dict[str, Any]:
        messages = self._build_messages_fn(conversation, played_track_ids)
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout_s,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        schema = self._schema_fn()
        # Google's Gemini structured-output validator (OpenAPI-3.0 subset, which
        # OpenRouter routes `response_format` to for google/gemini-* models) is
        # stricter than OpenAI/deepseek: it rejects our default Pydantic schema
        # ("schema at properties.mentioned_entities.items requires unspecified
        # property 'type'") because list items are a bare typeless $ref and
        # Optional fields are a typeless {type:null} anyOf union. Rewrite the
        # schema into the Gemini-safe subset (inline $refs, type every node,
        # express Optionals via nullable). Gated on gemini ONLY so the
        # deepseek/openai/gemma path that already works is untouched.
        if self.model_name.startswith("openrouter/google/gemini"):
            from experiments.analysis.extractor_prompt_v2.prompts_v4 import (
                _to_gemini_schema,
            )

            schema = _to_gemini_schema(schema)
        if self.model_name.startswith("openrouter/"):
            # litellm's supports_response_schema() is False for OpenRouter models,
            # so a TOP-LEVEL response_format is silently stripped before the call —
            # the model then gets no schema and degenerates into an unterminated
            # whitespace stutter on long outputs. Send response_format via
            # extra_body so it reaches OpenRouter verbatim, and require_parameters
            # so the request only routes to a provider that actually enforces the
            # schema (fails loudly if none does, rather than silently degrading).
            extra_body: dict[str, Any] = {
                "response_format": schema,
                "provider": {"require_parameters": True},
            }
            # Non-OpenAI hybrid-reasoning models otherwise burn max_tokens on reasoning.
            if not self.model_name.startswith("openrouter/openai/"):
                extra_body["reasoning"] = {"enabled": False}
            kwargs["extra_body"] = extra_body
        else:
            kwargs["response_format"] = schema
        return kwargs

    def _decode(self, raw: str) -> ConversationStateV0Plus:
        """Parse a raw LLM response into a state. Raises:
          - `json.JSONDecodeError` if the response isn't valid JSON. The
            caller treats this as retryable because it's usually a transient
            degenerative-generation failure (whitespace stutter).
          - `pydantic.ValidationError` if the JSON is valid but the schema
            doesn't match. Not retryable — same model + same input on a
            retry will likely produce the same wrong-but-valid structure.
        """
        if not raw:
            # Treat empty content as a JSON parse failure so the retry kicks in.
            raise json.JSONDecodeError("empty response", "", 0)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 2)[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.rsplit("```", 1)[0].strip()
        parsed = json.loads(cleaned)
        parsed = _sanitize_parsed_state(parsed)
        return ConversationStateV0Plus.model_validate(parsed)

    def extract(
        self,
        conversation: list[dict[str, Any]],
        played_track_ids: list[str],
    ) -> ConversationStateV0Plus | None:
        import litellm

        # Try the configured temperature first; if the response is unparseable
        # JSON, try once more with retry_temperature to escape any
        # degenerative path the deterministic call settled into.
        temps = [self.temperature]
        if self.retry_temperature != self.temperature:
            temps.append(self.retry_temperature)
        for attempt, temp in enumerate(temps, start=1):
            call_kwargs = self._build_kwargs(conversation, played_track_ids, temperature=temp)
            try:
                response = litellm.completion(**_with_no_store_cache(call_kwargs))
                raw = response.choices[0].message.content or ""
            except Exception as exc:
                logger.warning(
                    "v0+ extractor LLM call failed (attempt %d, temp=%.2f): %s: %s",
                    attempt, temp, type(exc).__name__, exc,
                )
                return None
            try:
                state = self._decode(raw)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "v0+ extractor JSON decode failed (attempt %d, temp=%.2f): %s | raw=%r",
                    attempt, temp, exc, raw[:6000],
                )
                continue  # next temperature
            except Exception as exc:
                # ValidationError or other schema mismatch — not retryable.
                logger.warning(
                    "v0+ extractor schema validate failed (attempt %d, temp=%.2f): %s: %s | raw=%r",
                    attempt, temp, type(exc).__name__, exc, raw[:6000],
                )
                return None
            _store_litellm_cache_entry(litellm, response, call_kwargs)
            return state
        return None

    async def aextract(
        self,
        conversation: list[dict[str, Any]],
        played_track_ids: list[str],
    ) -> ConversationStateV0Plus | None:
        """Async variant of `extract` — used by `abatch_compile_track_ids` to
        fan out extractor calls concurrently with `asyncio.gather`. Same
        retry semantics as the sync path."""
        import litellm

        temps = [self.temperature]
        if self.retry_temperature != self.temperature:
            temps.append(self.retry_temperature)
        for attempt, temp in enumerate(temps, start=1):
            call_kwargs = self._build_kwargs(conversation, played_track_ids, temperature=temp)
            try:
                response = await litellm.acompletion(**_with_no_store_cache(call_kwargs))
                raw = response.choices[0].message.content or ""
            except Exception as exc:
                logger.warning(
                    "v0+ extractor LLM call failed (async, attempt %d, temp=%.2f): %s: %s",
                    attempt, temp, type(exc).__name__, exc,
                )
                return None
            try:
                state = self._decode(raw)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "v0+ extractor JSON decode failed (async, attempt %d, temp=%.2f): %s | raw=%r",
                    attempt, temp, exc, raw[:6000],
                )
                continue
            except Exception as exc:
                logger.warning(
                    "v0+ extractor schema validate failed (async, attempt %d, temp=%.2f): %s: %s | raw=%r",
                    attempt, temp, type(exc).__name__, exc, raw[:6000],
                )
                return None
            await _async_store_litellm_cache_entry(litellm, response, call_kwargs)
            return state
        return None


# ----------------------------------------------------------------------
# session_memory adapter (CRS_BASELINE format → v0+ extractor format)
# ----------------------------------------------------------------------


def session_memory_to_conversation(
    session_memory: list[dict[str, Any]],
    catalog: CompilerCatalog | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Convert CRS_BASELINE session_memory to the v0+ extractor's conversation
    format and the played_track_ids list.

    CRS_BASELINE session_memory items: `{"role": "user"|"assistant"|"music", "content": str}`
        - For role="music", content is a track_id.
    v0+ extractor conversation items:
        - `{"turn": int, "role": "user"|"assistant", "text": str}`
        - `{"turn": int, "role": "music", "track_id": str, "label": str}`

    Turn numbers are computed by counting user turns (the canonical anchor
    used by the v0+ schema's `source_turn` fields).
    """
    conv: list[dict[str, Any]] = []
    played: list[str] = []
    turn = 0
    for item in session_memory:
        role = item.get("role")
        content = item.get("content", "") or ""
        if role == "user":
            turn += 1
            conv.append({"turn": turn, "role": "user", "text": str(content)})
        elif role == "assistant":
            conv.append({"turn": turn or 1, "role": "assistant", "text": str(content)})
        elif role == "music":
            raw = str(content)
            # `chat_history_parser` upstream rewrites music content from the
            # raw track_id into a yaml-blob via `id_to_metadata`. Strip the
            # blob back to a UUID so `played_track_ids` and music-turn
            # `track_id=` are clean. Without this, the extractor LLM sees
            # 2000-char-per-track blobs in `played_track_ids` and dutifully
            # echoes those blobs back as track_ids in its output, which then
            # crashes downstream code that expects UUIDs.
            m = _METADATA_BLOB_TRACK_ID_RE.match(raw)
            track_id = m.group(1) if m else raw
            played.append(track_id)
            # Use "artist - track" so the label format matches the few-shot
            # examples in prompts.py. Fall back to the UUID prefix when the
            # catalog doesn't know the track.
            label = ""
            if catalog is not None:
                label = catalog.track_label(track_id) or f"track={track_id[:8]}"
            conv.append({"turn": turn or 1, "role": "music", "track_id": track_id, "label": label})
    return conv, played


# ----------------------------------------------------------------------
# QU wrapper
# ----------------------------------------------------------------------


# Default in-flight cap for async batch fan-out. Each batch entry costs
# one extractor LLM call. 8 is conservative enough to stay well under
# OpenRouter's per-key/per-model RPM limits on paid tiers, while still
# delivering ~5-8× speedup vs the prior fully-sequential path.
DEFAULT_MAX_IN_FLIGHT = 8


@dataclass
class V0PlusCompilerQU:
    """The v0+ pipeline behind a `CRS_BASELINE` QU interface."""

    extractor: LiteLLMExtractor
    catalog: CompilerCatalog
    matcher: FuzzyMatcher
    encoder: EmbeddingClient
    retriever: Retriever
    resolver: V0PlusResolver
    compiler: V0PlusCompiler
    max_in_flight: int = DEFAULT_MAX_IN_FLIGHT

    # Per-call side channel: populated by `batch_compile_track_ids`, reset on
    # each call. Lets callers (e.g. `run_inference_devset.py`) save the
    # extractor state + resolver/compiler decisions alongside predictions
    # without changing the batch return shape.
    last_traces: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)

    # ------------------------------------------------------------------
    # CRS_BASELINE QU contract
    # ------------------------------------------------------------------

    def transform_query(self, session_memory: list[dict[str, Any]]) -> str:
        """Return a JSON dump of the extracted v0+ state — used by CRS_BASELINE
        for logging / observability. The actual track_ids come from
        `compile_track_ids` below."""
        conv, played = session_memory_to_conversation(session_memory, self.catalog)
        state = self.extractor.extract(conv, played)
        if state is None:
            return "{}"
        return state.model_dump_json()

    def batch_transform_queries(self, session_memories: list[list[dict[str, Any]]]) -> list[str]:
        return [self.transform_query(sm) for sm in session_memories]

    # ------------------------------------------------------------------
    # v0+ main entry point — CRS_BASELINE calls this instead of qu+retrieval
    # ------------------------------------------------------------------

    def compile_track_ids(
        self,
        session_memory: list[dict[str, Any]],
        topk: int = 1000,
        user_id: str | None = None,
    ) -> list[str]:
        """Return up to `topk` track_ids. May return an empty list when the
        extractor fails or the compiler finds no candidates that satisfy the
        resolver's filters / rejections. Callers (e.g. `CRS_BASELINE.chat`)
        must handle empty results — popularity backfill is intentionally NOT
        applied here because it would bypass the resolver's hard drops and
        silently inflate retrieval metrics.

        `user_id` is forwarded to the compiler so any user-source centroid
        branches (e.g. user_cf_bpr) can look up the user's vector. None is
        fine — user branches just no-op."""
        conv, played = session_memory_to_conversation(session_memory, self.catalog)
        state = self.extractor.extract(conv, played)
        if state is None:
            logger.warning(
                "v0+ empty result: extractor returned None | turns=%d played=%d last_user=%r",
                len(conv), len(played),
                next((c["text"] for c in reversed(conv) if c.get("role") == "user"), "")[:120],
            )
            return []
        rs = self.resolver.resolve(state, played_track_ids=played)
        track_ids = self.compiler.compile(rs, user_id=user_id)[:topk]
        if not track_ids:
            logger.warning(
                "v0+ empty result: compiler returned 0 candidates | "
                "turns=%d played=%d hard_filters=%d rejections=%d intent=%s",
                len(conv), len(played),
                len(state.hard_filters), len(state.explicit_rejections),
                getattr(state.intent_mode, "value", state.intent_mode),
            )
        return track_ids

    async def _acompile_one(
        self,
        idx: int,
        session_memory: list[dict[str, Any]],
        topk: int,
        sem: asyncio.Semaphore,
        user_id: str | None = None,
    ) -> tuple[int, list[str], dict[str, Any]]:
        """Async per-session worker — extractor runs under the semaphore;
        the synchronous compiler runs off the event loop via
        `asyncio.to_thread` so concurrent batch entries don't block each
        other on Python-bound work.

        Returns `(idx, track_ids, trace)`. `idx` lets the caller reassemble
        results in input order; `trace` is the per-turn observability record
        the caller stashes in `last_traces`. `user_id` is forwarded to the
        compiler for user-source centroid branches.
        """
        conv, played = session_memory_to_conversation(session_memory, self.catalog)
        async with sem:
            state = await self.extractor.aextract(conv, played)
        if state is None:
            logger.warning(
                "v0+ empty result: extractor returned None (async) | turns=%d played=%d last_user=%r",
                len(conv), len(played),
                next((c["text"] for c in reversed(conv) if c.get("role") == "user"), "")[:120],
            )
            trace = {
                "idx": idx,
                "intent_mode": None,
                "state": None,
                "resolver": None,
                "compiler": {
                    "n_candidates": 0,
                    "n_hard_filters": 0,
                    "n_explicit_rejections": 0,
                    "extractor_returned_none": True,
                },
            }
            return idx, [], trace

        # Resolver is fast pure-Python work — run inline. Only the compiler
        # (BM25 + dense + reranking) is heavy enough to be worth pushing off
        # the event loop. Inlining the resolver gives us `rs` for the trace.
        rs = self.resolver.resolve(state, played_track_ids=played)

        # Use _compile() (not compile()) to get the full CompileResult, which
        # carries the per-branch pools + fused/final funnel for the trace when
        # `branch_trace_topk > 0`. compile() is the thin public wrapper used by
        # the submission/blindset path (only needs .ranked).
        def _run_compile() -> CompileResult:
            return self.compiler._compile(rs, user_id=user_id)

        compile_result = await asyncio.to_thread(_run_compile)
        track_ids = compile_result.ranked[:topk]
        if not track_ids:
            logger.warning(
                "v0+ empty result: compiler returned 0 candidates (async) | "
                "turns=%d played=%d hard_filters=%d rejections=%d intent=%s",
                len(conv), len(played),
                len(state.hard_filters), len(state.explicit_rejections),
                getattr(state.intent_mode, "value", state.intent_mode),
            )

        # Build the per-turn trace. Resolver fields are pulled directly from
        # `ResolvedConversationState` — currently exposes `resolved_rejections`
        # (per-rejection artist/track ids) and `track_feedback_artist_ids`
        # (resolved artist for each track-feedback entry). We flatten these
        # into top-level rejection id lists for easier downstream inspection.
        rejected_track_ids: list[str] = []
        rejected_artist_ids: list[str] = []
        for rej in rs.resolved_rejections.values():
            rejected_track_ids.extend(rej.track_ids)
            rejected_artist_ids.extend(rej.artist_ids)
        # Track-feedback-derived artist rejections (compiler demotes these).
        for tf in state.track_feedback:
            if tf.role == "rejected":
                aid = rs.track_feedback_artist_ids.get(tf.track_id)
                if aid is not None:
                    rejected_artist_ids.append(aid)
        rejected_tags = [
            er.value for er in state.explicit_rejections
            if er.kind == "tag" and er.value
        ]
        positive_tags = [
            me.value for me in state.mentioned_entities
            if me.sentiment > 0 and me.type == "tag" and me.value
        ]
        # Anchor tracks/artists for centroid + tag expansion (mirrors what
        # the compiler considers a "positive" reference).
        anchor_track_ids: list[str] = []
        for tf in state.track_feedback:
            if tf.role in ("accepted", "seed") and tf.overall_sentiment > 0:
                anchor_track_ids.append(tf.track_id)
        anchor_track_ids.extend(state.referenced_track_ids)
        anchor_artist_ids = [
            me.value for me in state.mentioned_entities
            if me.sentiment > 0 and me.type == "artist" and me.value
        ]
        trace = {
            "idx": idx,
            "intent_mode": getattr(state.intent_mode, "value", str(state.intent_mode)),
            "state": state.model_dump(mode="json"),
            "resolver": {
                "anchor_track_ids": anchor_track_ids,
                "anchor_artist_ids": anchor_artist_ids,
                "rejected_track_ids": rejected_track_ids,
                "rejected_artist_ids": rejected_artist_ids,
                "rejected_tags": rejected_tags,
                "positive_tags": positive_tags,
                "played_track_ids": list(rs.played_track_ids),
            },
            "resolved_targets": [
                {
                    "kind": t.kind,
                    "source_text": t.source_text,
                    "entity_id": t.entity_id,
                    "confidence": t.confidence,
                }
                for t in rs.resolved_targets
            ],
            "routing_tags": state.routing_tags.model_dump(),
            "lyrical_theme": state.lyrical_theme,
            "compiler": {
                "n_candidates": len(track_ids),
                "n_hard_filters": len(state.hard_filters),
                "n_explicit_rejections": len(state.explicit_rejections),
            },
        }
        # Diagnostic: per-retriever pools + fused/final funnel. Only populated
        # when CompilerConfig.branch_trace_topk > 0. Lets offline analysis (see
        # scripts/branch_diagnostics.py) answer "where did the GT rank inside
        # each branch?" and "what's the fusion coverage ceiling?" — telling
        # apart "candidate missing from pool" vs "RRF mis-ranked the pool".
        if compile_result.branch_pools:
            trace["branches"] = compile_result.to_trace_dict()
        return idx, track_ids, trace

    def batch_compile_track_ids(
        self,
        session_memories: list[list[dict[str, Any]]],
        topk: int = 1000,
        user_ids: list[str | None] | None = None,
    ) -> list[list[str]]:
        """Parallel batch fan-out via asyncio + semaphore. Each batch entry
        is independent (extractor is stateless re. prior turns), so we run
        them concurrently capped at `self.max_in_flight` in-flight calls.

        Side effect: populates `self.last_traces` with one trace dict per
        input session, ordered to match the returned list. Callers that want
        observability into extractor / resolver / compiler decisions read
        `last_traces` immediately after this call returns.

        `user_ids`, if provided, must be parallel to `session_memories` and
        is forwarded to the compiler per-row for user-source centroid
        branches. None entries are fine — the user branch just no-ops there.
        """
        if not session_memories:
            self.last_traces = []
            return []

        if user_ids is None:
            user_ids = [None] * len(session_memories)
        elif len(user_ids) != len(session_memories):
            raise ValueError(
                f"user_ids length {len(user_ids)} must match session_memories "
                f"length {len(session_memories)}"
            )

        async def _run() -> list[tuple[int, list[str], dict[str, Any]]]:
            sem = asyncio.Semaphore(self.max_in_flight)
            tasks = [
                self._acompile_one(i, sm, topk, sem, user_id=uid)
                for i, (sm, uid) in enumerate(zip(session_memories, user_ids))
            ]
            return await asyncio.gather(*tasks)

        # `asyncio.run` creates and tears down its own loop. CRS_BASELINE's
        # batch_chat is called from a sync context (run_inference_devset.py),
        # so this is safe. If a future caller already has a running loop,
        # they should call `_run` directly.
        results = asyncio.run(_run())
        # `asyncio.gather` preserves task order, but sort by idx defensively
        # so this stays correct if the run helper ever swaps in `as_completed`.
        results.sort(key=lambda x: x[0])
        self.last_traces = [trace for _, _, trace in results]
        return [track_ids for _, track_ids, _ in results]


# ----------------------------------------------------------------------
# Factory: build a V0PlusCompilerQU from YAML qu_kwargs
# ----------------------------------------------------------------------


def build_v0plus_compiler_qu(
    qu_kwargs: dict[str, Any] | None = None,
    _overrides: dict[str, Any] | None = None,
) -> V0PlusCompilerQU:
    """Construct the full v0+ pipeline from a YAML kwargs dict.

    `_overrides` lets tests swap in pre-built fakes for any of the heavyweight
    components: keys are `extractor`, `catalog`, `matcher`, `encoder`,
    `retriever`, `resolver`, `compiler`. When an override is provided, the
    corresponding qu_kwargs section is ignored.
    """
    qu_kwargs = qu_kwargs or {}
    _overrides = _overrides or {}

    # ----- Catalog -----
    # Production: LanceDB-backed (single source of truth for v0+ metadata).
    # Tests and synthetic-data callers pass `_overrides["catalog"]` to bypass.
    if "catalog" in _overrides:
        catalog: CompilerCatalog = _overrides["catalog"]
    else:
        lance_cfg = dict(qu_kwargs.get("lancedb") or {})
        db_uri = os.environ.get("MCRS_LANCEDB_URI") or lance_cfg.get("db_uri")
        if not db_uri:
            raise ValueError(
                "v0+ catalog requires a LanceDB URI. Set qu_kwargs.lancedb.db_uri "
                "or the MCRS_LANCEDB_URI environment variable."
            )
        from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog
        eager_fields = lance_cfg.get("eager_vector_fields")
        if eager_fields is None:
            # Match the dense branches from configs/v0plus_compiler_devset.yaml — the
            # compiler queries these per-call during centroid mixing, so eager-load
            # them at startup to avoid per-call LanceDB queries.
            eager_fields = (
                "metadata_qwen3_embedding_0_6b",
                "attributes_qwen3_embedding_0_6b",
                "lyrics_qwen3_embedding_0_6b",
            )
        catalog = LanceDbCatalog(
            db_uri=db_uri,
            table_name=lance_cfg.get("table_name", "music_track_catalog"),
            eager_vector_fields=tuple(eager_fields),
        )

    # ----- Matcher (prebakes catalog state) -----
    matcher: FuzzyMatcher = _overrides.get("matcher") or RapidfuzzCatalogMatcher(catalog)

    # ----- Encoder(s) -----
    # Two YAML schemas, both supported:
    #
    # Legacy single encoder (today's configs):
    #   encoder:
    #     backend: litellm
    #     model_name: openai/Qwen/Qwen3-Embedding-0.6B
    #
    # New encoder map (multi-modal text-side configs):
    #   encoders:
    #     default:        { backend: litellm, model_name: ... }
    #     siglip2_text:   { backend: modal, modal_cls_name: MultimodalTextEncoder, method: embed_siglip_text }
    #     clap_text:      { backend: modal, modal_cls_name: MultimodalTextEncoder, method: embed_clap_text }
    #
    # Either accepted; mixing legacy + map promotes the legacy entry to `default`.
    if "encoders" in _overrides:
        encoders: dict[str, EmbeddingClient] = dict(_overrides["encoders"])
    else:
        encoders = {}
        legacy_cfg = qu_kwargs.get("encoder")
        if legacy_cfg is not None:
            encoders["default"] = _build_encoder(dict(legacy_cfg))
        for name, sub_cfg in (qu_kwargs.get("encoders") or {}).items():
            encoders[str(name)] = _build_encoder(dict(sub_cfg))
        if "encoder" in _overrides:
            encoders["default"] = _overrides["encoder"]
        if not encoders:
            # Back-compat default: build the legacy Qwen3 local encoder
            # when the YAML supplies neither `encoder:` nor `encoders:`.
            encoders["default"] = _build_encoder({})
    encoder: EmbeddingClient = encoders.get("default") or next(iter(encoders.values()))

    # ----- Retriever (LanceDB) -----
    if "retriever" in _overrides:
        retriever: Retriever = _overrides["retriever"]
    else:
        from mcrs.lancedb.retriever import LanceDbRetriever

        lance_cfg = dict(qu_kwargs.get("lancedb") or {})
        # Honor Modal's MCRS_LANCEDB_URI override (set by modal/app.py for the
        # CPU-inference path) before falling back to the YAML value.
        db_uri = os.environ.get("MCRS_LANCEDB_URI") or lance_cfg.get("db_uri")
        if not db_uri:
            raise ValueError(
                "v0+ compiler needs a LanceDB URI. Set qu_kwargs.lancedb.db_uri "
                "or the MCRS_LANCEDB_URI env var."
            )
        retriever_config: dict[str, Any] = {
            "db_uri": db_uri,
            "table_name": lance_cfg.get("table_name", "music_track_catalog"),
            "fusion": {"method": "weighted_rrf"},
            "device": "cpu",
        }
        # `searches` is optional for callers using only the Protocol API.
        if "searches" in lance_cfg:
            retriever_config["searches"] = lance_cfg["searches"]
        retriever = LanceDbRetriever.from_retrieval_config(retriever_config)

    # ----- Extractor LLM -----
    if "extractor" in _overrides:
        extractor: LiteLLMExtractor = _overrides["extractor"]
    else:
        ex_cfg = dict(qu_kwargs.get("extractor") or {})
        extractor = LiteLLMExtractor(
            model_name=ex_cfg.get("model_name", "openrouter/google/gemma-3-12b-it"),
            api_base=ex_cfg.get("api_base") or os.environ.get("LITELLM_PROXY_BASE"),
            api_key=ex_cfg.get("api_key") or os.environ.get("LITELLM_PROXY_KEY"),
            temperature=float(ex_cfg.get("temperature", 0.0)),
            max_tokens=int(ex_cfg.get("max_tokens", 1500)),
            timeout_s=int(ex_cfg.get("timeout_s", 90)),
            prompt_version=str(ex_cfg.get("prompt_version", "v1")),
        )

    # ----- Resolver -----
    if "resolver" in _overrides:
        resolver: V0PlusResolver = _overrides["resolver"]
    else:
        res_cfg = dict(qu_kwargs.get("resolver") or {})
        resolver = V0PlusResolver(
            matcher,
            catalog,
            score_cutoff=int(res_cfg.get("score_cutoff", 80)),
            artist_match_topk=int(res_cfg.get("artist_match_topk", 20)),
            track_match_topk=int(res_cfg.get("track_match_topk", 5)),
        )

    # ----- Compiler -----
    if "compiler" in _overrides:
        compiler: V0PlusCompiler = _overrides["compiler"]
    else:
        comp_cfg = dict(qu_kwargs.get("compiler") or {})

        # Parse dense_branches from YAML if present; each entry may be a dict
        # with vector_field / weight / distance_type, or just the field name.
        raw_branches = comp_cfg.get("dense_branches")
        dense_branches: list[DenseBranch] | None = None
        if raw_branches is not None:
            dense_branches = []
            for entry in raw_branches:
                if isinstance(entry, str):
                    dense_branches.append(DenseBranch(vector_field=entry))
                else:
                    dense_branches.append(
                        DenseBranch(
                            vector_field=str(entry["vector_field"]),
                            weight=float(entry.get("weight", 1.0)),
                            distance_type=str(entry.get("distance_type", "cosine")),
                            encoder_id=str(entry.get("encoder_id", "default")),
                            query_id=str(entry.get("query_id", "intent")),
                        )
                    )

        # Parse centroid_only_branches the same way (each entry: vector_field
        # + optional weight/topk/distance_type/centroid_source). Used for
        # cf_bpr / audio / image-style branches that have no encoded query
        # text. `centroid_source` defaults to "anchor_tracks"; set to "user"
        # to query the user's precomputed vector instead of the mean of
        # positive-anchor tracks.
        raw_centroid = comp_cfg.get("centroid_only_branches")
        centroid_only_branches: list[CentroidOnlyBranch] | None = None
        if raw_centroid is not None:
            centroid_only_branches = []
            for entry in raw_centroid:
                if isinstance(entry, str):
                    centroid_only_branches.append(CentroidOnlyBranch(vector_field=entry))
                else:
                    centroid_only_branches.append(
                        CentroidOnlyBranch(
                            vector_field=str(entry["vector_field"]),
                            weight=float(entry.get("weight", 1.0)),
                            topk=int(entry.get("topk", 1000)),
                            distance_type=str(entry.get("distance_type", "cosine")),
                            centroid_source=str(entry.get("centroid_source", "anchor_tracks")),
                        )
                    )

        config_kwargs: dict[str, Any] = {
            k: v
            for k, v in comp_cfg.items()
            if k in {
                "field_boosts",
                "centroid_alpha",
                "anchor_tag_expansion_n",
                "rejected_tag_multiplier",
                "positive_tag_multiplier_step",
                "same_artist_demote",
                "enable_dense",
                "enable_cf_bpr",
                "cf_bpr_weight",
                "cf_bpr_topk",
                "cf_bpr_vector_field",
                "cf_bpr_distance_type",
                "branch_trace_topk",
                "enable_resolved_artist_discography",
                "disco_weight",
                "disco_cap",
                "disco_confidence_threshold",
                "disco_gated_intents",
                "enable_era_popularity",
                "era_pop_weight",
                "era_pop_cap",
                "enable_release_year_filter",
                "release_year_filter_min_keep",
                "routing_boost",
                "enable_similar_artist_anchors",
                "similar_artist_anchor_topk",
                "similar_artist_confidence_threshold",
                "similar_artist_max_artists",
                "similar_artist_anchor_intents",
                "similar_artist_anchor_on_exact_entity",
            }
        }
        if dense_branches is not None:
            config_kwargs["dense_branches"] = dense_branches
        if centroid_only_branches is not None:
            config_kwargs["centroid_only_branches"] = centroid_only_branches

        # Load UserEmbeddings only if any centroid branch needs it. Avoids
        # paying the HF dataset load + ~4 MB RAM when nothing uses it.
        user_embeddings = None
        if centroid_only_branches and any(
            b.centroid_source == "user" for b in centroid_only_branches
        ):
            ue_cfg = dict(qu_kwargs.get("user_embeddings") or {})
            user_embeddings = _overrides.get("user_embeddings") or UserEmbeddings(
                dataset_name=ue_cfg.get(
                    "dataset_name", "talkpl-ai/TalkPlayData-Challenge-User-Embeddings"
                ),
                splits=tuple(ue_cfg.get("splits") or ("train", "test_warm", "test_cold")),
            )

        # Validate every branch's encoder_id resolves before constructing
        # the compiler — fail-fast with a clear message instead of at first
        # call from the inference loop.
        if dense_branches:
            unknown_ids = sorted(
                {b.encoder_id for b in dense_branches} - set(encoders)
            )
            if unknown_ids:
                raise KeyError(
                    f"dense_branches reference encoder_id(s) {unknown_ids!r} "
                    f"not present in `encoders` map. Available: {sorted(encoders)}."
                )

        compiler = V0PlusCompiler(
            catalog,
            retriever,
            encoder=encoder,  # kept for back-compat with .encoder accessor
            encoders=encoders,
            config=CompilerConfig(
                bm25_k=int(comp_cfg.get("bm25_k", 1000)),
                dense_k=int(comp_cfg.get("dense_k", 1000)),
                rrf_k=int(comp_cfg.get("rrf_k", 60)),
                final_topk=int(comp_cfg.get("final_topk", 1000)),
                **config_kwargs,
            ),
            user_embeddings=user_embeddings,
        )

    # Concurrency cap for the async batch fan-out. Conservative default (8)
    # to stay well under OpenRouter / HF rate limits on paid tiers; dial
    # higher in config if you see consistent throughput-bound runs.
    max_in_flight = int(qu_kwargs.get("max_in_flight", DEFAULT_MAX_IN_FLIGHT))

    return V0PlusCompilerQU(
        extractor=extractor,
        catalog=catalog,
        matcher=matcher,
        encoder=encoder,
        retriever=retriever,
        resolver=resolver,
        compiler=compiler,
        max_in_flight=max_in_flight,
    )
