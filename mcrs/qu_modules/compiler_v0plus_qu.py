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
| `lancedb` | retriever settings: db_uri, table_name |
| `catalog` | HF catalog settings (defaulted to challenge datasets) |
| `encoder` | Qwen3 encoder settings: device, batch_size, query_instruct |
| `compiler` | `CompilerConfig` knobs (field_boosts, centroid_alpha, ...) |
| `resolver` | `score_cutoff`, topks |

## Preconditions for production runs

1. LanceDB table built at `lancedb.db_uri` / `lancedb.table_name` with the
   `metadata_qwen3_embedding_0_6b` vector column + FTS indexes on the BM25
   text fields. See `scripts/build_lancedb_index.py`.
2. LiteLLM proxy running (or OpenRouter API key set) so the extractor LLM
   call can reach `gemma-3-12b-it`.
3. HF auth (`uvx hf auth login`) for the catalog metadata + embeddings
   datasets.

For smoke / unit tests, inject `_overrides` to swap in fakes for any of
the heavyweight components (see `tests/test_v0plus_compiler_qu.py`).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from experiments.analysis.conversation_state_extraction_bakeoff.prompts import (
    build_messages,
    json_schema_for_response_format,
)
from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
    ConversationStateV0Plus,
)
from mcrs.embeddings.base import EmbeddingClient
from mcrs.embeddings.qwen3_embedding import Qwen3EmbeddingClient
from mcrs.qu_modules.compiler_v0plus import CompilerConfig, DenseBranch, V0PlusCompiler
from mcrs.qu_modules.fuzzy_matcher import FuzzyMatcher, RapidfuzzCatalogMatcher
from mcrs.qu_modules.resolver_v0plus import V0PlusResolver
from mcrs.qu_modules.v0plus_catalog import CompilerCatalog
from mcrs.retrieval_modules.base import Retriever

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Extractor LLM adapter
# ----------------------------------------------------------------------


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

    def _build_kwargs(
        self,
        conversation: list[dict[str, Any]],
        played_track_ids: list[str],
    ) -> dict[str, Any]:
        messages = build_messages(conversation, played_track_ids)
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout_s,
            "response_format": json_schema_for_response_format(),
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        # Non-OpenAI hybrid-reasoning models need this or they consume max_tokens on internal reasoning.
        if self.model_name.startswith("openrouter/") and not self.model_name.startswith("openrouter/openai/"):
            kwargs["extra_body"] = {"reasoning": {"enabled": False}}
        return kwargs

    def _parse_response(self, raw: str) -> ConversationStateV0Plus | None:
        if not raw:
            logger.warning("v0+ extractor parse: LLM returned empty content")
            return None
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 2)[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.rsplit("```", 1)[0].strip()
        try:
            parsed = json.loads(cleaned)
            return ConversationStateV0Plus.model_validate(parsed)
        except Exception as exc:
            logger.warning(
                "v0+ extractor parse/validate failed: %s: %s | raw=%r",
                type(exc).__name__, exc, raw[:300],
            )
            return None

    def extract(
        self,
        conversation: list[dict[str, Any]],
        played_track_ids: list[str],
    ) -> ConversationStateV0Plus | None:
        import litellm

        try:
            response = litellm.completion(**self._build_kwargs(conversation, played_track_ids))
            raw = response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("v0+ extractor LLM call failed: %s: %s", type(exc).__name__, exc)
            return None
        return self._parse_response(raw)

    async def aextract(
        self,
        conversation: list[dict[str, Any]],
        played_track_ids: list[str],
    ) -> ConversationStateV0Plus | None:
        """Async variant of `extract` — used by `abatch_compile_track_ids` to
        fan out extractor calls concurrently with `asyncio.gather`."""
        import litellm

        try:
            response = await litellm.acompletion(**self._build_kwargs(conversation, played_track_ids))
            raw = response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning(
                "v0+ extractor LLM call failed (async): %s: %s", type(exc).__name__, exc,
            )
            return None
        return self._parse_response(raw)


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
            track_id = str(content)
            played.append(track_id)
            label = ""
            if catalog is not None:
                aid = catalog.artist_id_of(track_id)
                # Cheap label: just track_id when we have no easy display string
                label = f"track={track_id[:8]} artist_id={aid or '?'}"
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
    ) -> list[str]:
        """Return up to `topk` track_ids. May return an empty list when the
        extractor fails or the compiler finds no candidates that satisfy the
        resolver's filters / rejections. Callers (e.g. `CRS_BASELINE.chat`)
        must handle empty results — popularity backfill is intentionally NOT
        applied here because it would bypass the resolver's hard drops and
        silently inflate retrieval metrics."""
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
        track_ids = self.compiler.compile(rs)[:topk]
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
        session_memory: list[dict[str, Any]],
        topk: int,
        sem: asyncio.Semaphore,
    ) -> list[str]:
        """Async per-session worker — extractor runs under the semaphore;
        the synchronous resolver/compiler runs off the event loop via
        `asyncio.to_thread` so concurrent batch entries don't block each
        other on Python-bound work."""
        conv, played = session_memory_to_conversation(session_memory, self.catalog)
        async with sem:
            state = await self.extractor.aextract(conv, played)
        if state is None:
            logger.warning(
                "v0+ empty result: extractor returned None (async) | turns=%d played=%d last_user=%r",
                len(conv), len(played),
                next((c["text"] for c in reversed(conv) if c.get("role") == "user"), "")[:120],
            )
            return []

        def _resolve_and_compile() -> tuple[list[str], int, int]:
            rs = self.resolver.resolve(state, played_track_ids=played)
            ids = self.compiler.compile(rs)[:topk]
            return ids, len(state.hard_filters), len(state.explicit_rejections)

        track_ids, n_filters, n_rejections = await asyncio.to_thread(_resolve_and_compile)
        if not track_ids:
            logger.warning(
                "v0+ empty result: compiler returned 0 candidates (async) | "
                "turns=%d played=%d hard_filters=%d rejections=%d intent=%s",
                len(conv), len(played), n_filters, n_rejections,
                getattr(state.intent_mode, "value", state.intent_mode),
            )
        return track_ids

    def batch_compile_track_ids(
        self,
        session_memories: list[list[dict[str, Any]]],
        topk: int = 1000,
    ) -> list[list[str]]:
        """Parallel batch fan-out via asyncio + semaphore. Each batch entry
        is independent (extractor is stateless re. prior turns), so we run
        them concurrently capped at `self.max_in_flight` in-flight calls."""
        if not session_memories:
            return []

        async def _run() -> list[list[str]]:
            sem = asyncio.Semaphore(self.max_in_flight)
            tasks = [self._acompile_one(sm, topk, sem) for sm in session_memories]
            return await asyncio.gather(*tasks)

        # `asyncio.run` creates and tears down its own loop. CRS_BASELINE's
        # batch_chat is called from a sync context (run_inference_devset.py),
        # so this is safe. If a future caller already has a running loop,
        # they should call `_run` directly.
        return asyncio.run(_run())


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

    # ----- Encoder (Qwen3-Embedding-0.6B) -----
    # Three backends:
    #   local  — in-process CPU/CUDA (~1-2 s/call); good for tests / no cloud creds
    #   modal  — deployed T4 GPU class (~181 ms warm, ~30 s cold start); no caching
    #   litellm — API call via LiteLLM SDK (e.g. DeepInfra $0.01/1M tokens, ~200 ms);
    #             flows through the shared litellm disk cache so reruns are free
    if "encoder" in _overrides:
        encoder: EmbeddingClient = _overrides["encoder"]
    else:
        enc_cfg = dict(qu_kwargs.get("encoder") or {})
        backend = str(enc_cfg.get("backend", "local")).lower()
        if backend == "modal":
            from mcrs.embeddings.modal_qwen3_client import ModalQwen3EmbeddingClient

            encoder = ModalQwen3EmbeddingClient(
                app_name=enc_cfg.get("modal_app_name", "music-crs"),
                cls_name=enc_cfg.get("modal_cls_name", "Qwen3Encoder"),
            )
        elif backend == "litellm":
            # API-backed encoder — cheaper than Modal GPU, no cold starts, cacheable.
            # encoding_format="float" is mandatory for DeepInfra (422 without it).
            from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient

            api_key = enc_cfg.get("api_key") or os.environ.get("DEEPINFRA_API_KEY")
            encoder = LiteLLMEmbeddingClient(
                model_name=enc_cfg.get("model_name", "openai/Qwen/Qwen3-Embedding-0.6B"),
                api_base=enc_cfg.get("api_base", "https://api.deepinfra.com/v1/openai"),
                api_key=api_key,
                batch_size=int(enc_cfg.get("batch_size", 32)),
                encoding_format=enc_cfg.get("encoding_format", "float"),
            )
        elif backend == "local":
            encoder = Qwen3EmbeddingClient(
                model_name=enc_cfg.get("model_name", "Qwen/Qwen3-Embedding-0.6B"),
                device=enc_cfg.get("device", "cpu"),
                torch_dtype_name=enc_cfg.get("torch_dtype", "float32"),
                max_length=int(enc_cfg.get("max_length", 512)),
                batch_size=int(enc_cfg.get("batch_size", 8)),
                padding_side=enc_cfg.get("padding_side", "left"),
                query_instruct=enc_cfg.get("query_instruct", ""),
            )
        else:
            raise ValueError(
                f"Unknown encoder.backend={backend!r}; expected 'local', 'litellm', or 'modal'"
            )

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
            }
        }
        if dense_branches is not None:
            config_kwargs["dense_branches"] = dense_branches

        compiler = V0PlusCompiler(
            catalog,
            retriever,
            encoder,
            config=CompilerConfig(
                bm25_k=int(comp_cfg.get("bm25_k", 1000)),
                dense_k=int(comp_cfg.get("dense_k", 1000)),
                rrf_k=int(comp_cfg.get("rrf_k", 60)),
                final_topk=int(comp_cfg.get("final_topk", 1000)),
                **config_kwargs,
            ),
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
