# `mcrs/qu_modules` — Query Understanding / Compiler

> For the **retrievers, end-to-end flow, and fusion rankers** as a single reference (including the #80 CLAP-text / era-popularity / discography / year-BM25 branches), see [`docs/architectures/v0plus_retrieval.md`](../../architectures/v0plus_retrieval.md). This module doc covers per-file responsibilities; some line numbers below predate recent refactors.

## Purpose

This module group is the **conversation-to-retrieval layer** of the Music-CRS pipeline. Its job is to transform a raw `session_memory` (a list of `{"role", "content"}` turns) into the top-1000 ranked `track_id` list that the challenge requires.

It sits between `CRS_BASELINE` (the orchestration harness that calls QU modules) and `mcrs/retrieval_modules` / `mcrs/lancedb` (the actual search backends).

There are two distinct families:

1. **Simple QU modules** (`base.py`, `llm_rewrite.py`) — return a rewritten query *string*. These predate the v0+ work and are retained for tests/tooling; `CRS_BASELINE` no longer wires them to a separate retriever.
2. **v0+ Compiler pipeline** — extracts a structured `ConversationStateV0Plus` from the conversation via an LLM, resolves surface-form entity names to catalog IDs, and produces ranked `track_ids` directly. `CRS_BASELINE` requires this full-pipeline interface via `compile_track_ids` or `batch_compile_track_ids`.

The v0+ pipeline is the active/canonical path for all current experiment configs. The simple QU modules remain for ablation and legacy runs.

---

## Files

| File | Responsibility |
|---|---|
| `__init__.py` | `load_qu_module` factory — dispatches `qu_type` string to the right class; entry point from `CRS_BASELINE`. |
| `base.py` | Five simple stateless QU classes: `PassthroughQU`, `LastUserTurnQU`, `UserTurnsOnlyQU`, `LastNUserTurnsQU`, `NoMusicHistoryQU`. No LLM, no retrieval. |
| `llm_rewrite.py` | `LLMRewriteQU` — LLM-backed query rewriter (Llama/Gemma4/LiteLLM backends). Returns a plain query string via `QUERY:` prefix parsing. |
| `catalog.py` | `CompilerCatalog` Protocol — the narrow contract Resolver and Compiler use to talk to the track catalog. |
| `catalog_lance.py` | `LanceDbCatalog` — **production** `CompilerCatalog` impl backed by a LanceDB table. Scans once at init, builds in-memory caches, optionally eager-loads named vector columns. |
| `catalog_hf.py` | `HFTalkPlayCatalog` — **test-only** `CompilerCatalog` impl backed by HuggingFace datasets. Retained solely for unit tests via `from_rows`. |
| `fuzzy_matcher.py` | `FuzzyMatcher` Protocol + `RapidfuzzCatalogMatcher` impl — resolves entity surface forms to catalog IDs using `rapidfuzz.token_set_ratio`. Pre-bakes name→id maps at init. |
| `resolver.py` | `V0PlusResolver` — takes a `ConversationStateV0Plus` (raw LLM output) and produces a `ResolvedConversationState` with rejection IDs resolved to catalog IDs. |
| `compiler.py` | `V0PlusCompiler` — executes BM25 + dense ANN retrieval, weighted RRF fusion, hard drops, soft adjustments, and backfill to produce the final top-N track list. |
| `compiler_qu.py` | `V0PlusCompilerQU` + `LiteLLMExtractor` — wraps the full v0+ pipeline as a `CRS_BASELINE` QU interface; `batch_compile_track_ids` fans out async extractor calls; `build_v0plus_compiler_qu` is the YAML-driven factory. |
| `user_embeddings.py` | `UserEmbeddings` — loads TalkPlayData user-side CF-BPR vectors (9 k users, ~4.4 MB) for `centroid_source="user"` branches. |

---

## Public API

Functions and classes called by code outside this module group.

### `__init__.py`

**`load_qu_module(qu_type, cache_dir, device, attn_implementation, dtype, **qu_kwargs) -> QU`** (`__init__.py:11`)

Factory called by `CRS_BASELINE` at pipeline construction time. Dispatches on `qu_type`:
- `"passthrough"`, `"last_user_turn"`, `"user_turns_only"`, `"last_2_user_turns"`, `"last_3_user_turns"`, `"no_music_history"` → simple QU classes from `base.py`; these do not satisfy the active `CRS_BASELINE` full-pipeline requirement by themselves.
- `"llm_rewrite"` → `LLMRewriteQU` with an appropriate model adapter; also returns query text rather than track IDs.
- `"v0plus_compiler"` → calls `build_v0plus_compiler_qu(qu_kwargs=qu_kwargs)` from `compiler_qu.py`.
- `"state_ranker"` → calls `build_state_ranker_qu(qu_kwargs=qu_kwargs)` from `state_ranker_qu.py`; this is the path all active `state_ranker_v10_*` configs use, and it satisfies the active inference contract.

### `base.py` — Simple QU classes

All share the same two-method interface used by `CRS_BASELINE`:
- `transform_query(session_memory: list) -> str`
- `batch_transform_queries(session_memories: List[list]) -> List[str]`

`PassthroughQU` (`base.py:8`) — returns full conversation as `"role: content"` lines, relabeling `music` turns to `assistant`.  
`LastUserTurnQU` (`base.py:26`) — returns only the last user turn's text.  
`UserTurnsOnlyQU` (`base.py:39`) — concatenates all user turns.  
`LastNUserTurnsQU(n)` (`base.py:51`) — last N user turns.  
`NoMusicHistoryQU` (`base.py:65`) — like `PassthroughQU` but drops music recommendation turns.

### `compiler_qu.py` — v0+ pipeline entry points

**`V0PlusCompilerQU.compile_track_ids(session_memory, topk=1000, user_id=None) -> list[str]`** (`compiler_qu.py:338`)

Single-session synchronous entry point used by `CRS_BASELINE.chat`. Runs extract → resolve → compile and returns up to `topk` track IDs. Returns `[]` on extractor failure.

**`V0PlusCompilerQU.batch_compile_track_ids(session_memories, topk=1000, user_ids=None) -> list[list[str]]`** (`compiler_qu.py:490`)

Batch entry point. Fans out async extractor calls (bounded by `max_in_flight` semaphore, default 8). After this returns, `self.last_traces` holds one trace dict per session for observability. Called by `run_inference_devset.py` and `run_inference_blindset.py`.

**`build_v0plus_compiler_qu(qu_kwargs, _overrides=None) -> V0PlusCompilerQU`** (`compiler_qu.py:546`)

YAML-driven factory. Builds catalog → matcher → encoder → retriever → extractor → resolver → compiler in order. `_overrides` dict lets tests swap in fakes for any component.

**`session_memory_to_conversation(session_memory, catalog=None) -> tuple[list[dict], list[str]]`** (`compiler_qu.py:237`)

Converts `CRS_BASELINE` session memory to the v0+ extractor's conversation format. Strips `chat_history_parser` YAML-blob rewrites back to bare UUIDs so the extractor LLM sees clean `played_track_ids`.

### `compiler.py`

**`V0PlusCompiler.compile(rs: ResolvedConversationState, user_id=None) -> list[str]`** (`compiler.py:191`)

Core retrieval and ranking. Returns up to `cfg.final_topk` track IDs. See Internal Flow section for the step-by-step breakdown.

### `resolver.py`

**`V0PlusResolver.resolve(state: ConversationStateV0Plus, played_track_ids=None) -> ResolvedConversationState`** (`resolver.py:87`)

Resolves `explicit_rejections` surface forms to catalog IDs via `FuzzyMatcher`, annotates `track_feedback` entries with their artist IDs, and packages everything into a `ResolvedConversationState`.

### `catalog.py`

**`CompilerCatalog`** (`catalog.py:27`) — `@runtime_checkable` Protocol. Key methods:
- `artist_names -> list[str]`, `track_names -> list[str]` (for fuzzy matching)
- `artist_id_of(track_id) -> str | None`
- `tracks_by_artist_id(artist_id) -> list[str]`
- `tag_list(track_id) -> list[str]`
- `track_label(track_id) -> str` (for extractor prompt rendering)
- `vector(track_id, vector_field) -> list[float] | None`
- `release_date_filter_mask(hf: HardFilter) -> set[str]`
- `all_track_ids() -> list[str]`
- `popularity_sorted_track_ids() -> list[str]`

### `fuzzy_matcher.py`

**`RapidfuzzCatalogMatcher(catalog: CompilerCatalog)`** (`fuzzy_matcher.py:64`)  
**`.match(query, entity_type, *, topk=20, score_cutoff=80) -> list[tuple[str, float]]`** (`fuzzy_matcher.py:106`)

Pre-bakes catalog name→id maps at init; `match` uses `rapidfuzz.fuzz.token_set_ratio` with `processor=str.lower`.

### `user_embeddings.py`

**`UserEmbeddings(dataset_name, splits)`** (`user_embeddings.py:37`)  
**`.vector(user_id, vector_field) -> list[float] | None`** (`user_embeddings.py:73`)  
**`UserEmbeddings.from_dict(vectors) -> UserEmbeddings`** (`user_embeddings.py:90`) — test helper, no HF call.

---

## Key Data Structures / Config

### `ConversationStateV0Plus` (Pydantic — `mcrs/conversation_state/schema.py`)

The 7 LLM-extracted fields that drive retrieval:

| Field | Type | Purpose |
|---|---|---|
| `turn_intent` | `str` | Free-text active ask; routed to BM25 `track_name` + `tag_list` and dense query. |
| `intent_mode` | `IntentMode` enum | `open_explore`, `refinement`, `pivot`, `playlist_build`. Controls centroid mixing alpha. |
| `track_feedback` | `list[TrackFeedback]` | Per-played-track reactions: `role` ∈ `{accepted, rejected, seed, neutral}` and `overall_sentiment` ∈ `{-1, 0, 1}`. |
| `referenced_track_ids` | `list[str]` | Explicit pronoun/positional back-references (rare, ~5% of turns). |
| `mentioned_entities` | `list[MentionedEntity]` | Named artists/albums/tracks/tags with sentiment. Positive ones drive BM25 + dense. |
| `hard_filters` | `list[HardFilter]` | Structured catalog-level filters; v0+ supports `release_date` only. |
| `explicit_rejections` | `list[ExplicitRejection]` | Hard-exclude future recs; `kind` ∈ `{artist, track, tag}`. |

### `ResolvedConversationState` (`resolver.py:47`)

Frozen dataclass wrapping a `ConversationStateV0Plus` with resolver annotations:
- `state: ConversationStateV0Plus`
- `played_track_ids: tuple[str, ...]`
- `resolved_rejections: dict[int, ResolvedRejection]` — rejection index → `{artist_ids, track_ids}`
- `track_feedback_artist_ids: dict[str, str | None]` — track_id → artist_id

### `CompilerConfig` (`compiler.py:89`)

Dataclass with all compiler knobs (all overridable from YAML):

| Field | Default | Purpose |
|---|---|---|
| `bm25_k` | 1000 | Candidates from BM25. |
| `dense_k` | 1000 | Candidates per dense branch. |
| `rrf_k` | 60 | RRF smoothing constant. |
| `final_topk` | 1000 | Output list length. |
| `field_boosts` | `{track_name:3, artist_name:3, album_name:2, tag_list:1.5}` | Per-field BM25 boost. |
| `centroid_alpha` | `{refinement:0.4, playlist_build:0.5, pivot:0, open_explore:0}` | Anchor-centroid mixing per intent mode. |
| `anchor_tag_expansion_n` | 5 | Top-N anchor tags appended to `tag_list` BM25 channel. |
| `rejected_tag_multiplier` | 0.5 | Per-overlapping-rejected-tag score multiplier. |
| `positive_tag_multiplier_step` | 0.15 | Per-overlapping-positive-tag additive promotion. |
| `same_artist_demote` | 0.7 | Demote factor for artists of feedback-rejected tracks. |
| `dense_branches` | `[metadata_qwen3, attributes_qwen3, lyrics_qwen3]` | Dense ANN branches; each fires one `search_embedding` call. |
| `enable_dense` | `True` | Master kill-switch for all dense branches. |
| `centroid_only_branches` | `[]` | Branches without encoded query text; centroid from anchor tracks or user vectors. |
| `enable_cf_bpr` | `False` | Legacy single-CF-BPR knob (back-compat; superseded by `centroid_only_branches`). |

### `DenseBranch` / `CentroidOnlyBranch` (`compiler.py:50`, `compiler.py:63`)

`DenseBranch(vector_field, weight=1.0, distance_type="cosine")` — text-encoded query ANN-searched in `vector_field`.

`CentroidOnlyBranch(vector_field, weight=1.0, topk=1000, distance_type="cosine", centroid_source="anchor_tracks")` — no encoded query; centroid is either the mean of positive-anchor track vectors (`centroid_source="anchor_tracks"`) or the user's precomputed vector (`centroid_source="user"`). Used for `cf_bpr`, `audio_laion_clap`, `image_siglip2`.

### `FieldQuery` (`mcrs/retrieval_modules/base.py:33`)

Frozen dataclass `FieldQuery(field, query, boost=1.0)` — one BM25 clause passed to `Retriever.search`.

### `LiteLLMExtractor` (`compiler_qu.py:83`)

Dataclass holding LLM connection settings. Notable: `retry_temperature=0.3` used on JSON decode failure to escape degenerative output paths.

---

## Internal Flow

The following describes one call to `V0PlusCompilerQU.compile_track_ids` for a single session (the batch path in `batch_compile_track_ids` parallelises the extractor step with asyncio):

1. **Format conversion** (`session_memory_to_conversation`, `compiler_qu.py:237`) — CRS_BASELINE session memory is converted to the extractor format; music-turn YAML blobs are stripped back to bare UUIDs; `played_track_ids` is extracted.

2. **State extraction** (`LiteLLMExtractor.extract`, `compiler_qu.py:150`) — sends the formatted conversation to gemma-3-12b-it (via litellm, default OpenRouter) with a JSON-schema `response_format`. Returns a validated `ConversationStateV0Plus` Pydantic object, or `None` on failure. On `JSONDecodeError`, retries once with `retry_temperature=0.3`.

3. **Resolution** (`V0PlusResolver.resolve`, `resolver.py:87`) — for each `explicit_rejection` of kind `artist` or `track`, calls `RapidfuzzCatalogMatcher.match` to resolve the surface form to catalog IDs. Artist IDs are further expanded to `tracks_by_artist_id`. Track-feedback entries are annotated with their artist IDs. Packages everything into `ResolvedConversationState`.

4. **Pre-fusion catalog mask** (`V0PlusCompiler._release_date_mask`, `compiler.py:379`) — applies any `hard_filters.release_date` constraints to produce a `candidate_mask: set[str]` of allowed track IDs.

5. **Query construction** (`compiler.py:283–357`) — two parallel query representations are built:
   - BM25: `_build_bm25_clauses` assembles `FieldQuery` objects from positive `mentioned_entities`, anchor-tag expansion, and `turn_intent`.
   - Dense: `_build_dense_query_text` encodes `turn_intent + artists + tags` into a normalized vector via the `EmbeddingClient` (Qwen3-Embedding-0.6B).

6. **Retrieval** (`compiler.py:202–246`) — issues:
   - 1 BM25 call: `retriever.search(bm25_clauses, topk=bm25_k)`
   - 1 `search_embedding` call per enabled `DenseBranch` (default: 3 — metadata/attributes/lyrics Qwen3 columns), with the encoded query optionally mixed with the anchor centroid for that field.
   - 1 `search_embedding` call per enabled `CentroidOnlyBranch` (CF-BPR, CLAP audio, SigLIP-2 image) when positive anchors exist, or per-user vector when `centroid_source="user"`.
   - All results are post-hoc filtered by `candidate_mask`.

7. **Hard-drop filtering** (`_hard_drop_set`, `compiler.py:395`) — removes played tracks, feedback-rejected tracks, and all tracks/artists from `resolved_rejections` from every result list.

8. **Weighted RRF fusion** (`_rrf_fuse_weighted`, `compiler.py:427`) — merges all retrieval pools (BM25 weight=1.0, each dense branch at its configured weight, each centroid-only branch at its weight) using `weight / (rrf_k + rank)` per clause.

9. **Soft adjustments** (`_apply_soft_adjustments`, `compiler.py:448`) — multiplicatively scales RRF scores: `rejected_tag_multiplier^|overlap|` for tag rejections, `(1+positive_tag_multiplier_step)^|overlap|` for positive tags, `same_artist_demote` for artists of feedback-rejected tracks.

10. **Backfill** (`_backfill`, `compiler.py:510`) — if fewer than `final_topk` candidates remain after fusion+soft adjustments, pads the list with `popularity_sorted_track_ids()` respecting `candidate_mask` and `hard_drop`.

11. **Return** — up to `final_topk` (1000) track IDs.

---

## Dependencies

### Internal `mcrs` modules

| Module | Used by |
|---|---|
| `mcrs/retrieval_modules/base.py` (`FieldQuery`, `Retriever` Protocol) | `compiler.py`, `compiler_qu.py` |
| `mcrs/lancedb/retriever.py` (`LanceDbRetriever`) | `build_v0plus_compiler_qu` (production retriever) |
| `mcrs/embeddings/base.py` (`EmbeddingClient`) | `compiler.py`, `compiler_qu.py` |
| `mcrs/embeddings/qwen3_embedding.py` (`Qwen3EmbeddingClient`) | `build_v0plus_compiler_qu` (local encoder) |
| `mcrs/embeddings/modal_qwen3_client.py` | `build_v0plus_compiler_qu` (modal encoder backend) |
| `mcrs/embeddings/litellm_client.py` | `build_v0plus_compiler_qu` (litellm encoder backend) |
| `mcrs/conversation_state/schema.py` | `compiler.py`, `resolver.py`, `compiler_qu.py` — `ConversationStateV0Plus`, `HardFilter`, etc. |
| `mcrs/conversation_state/prompts/current.py` | `LiteLLMExtractor._build_kwargs` — `build_messages`, `json_schema_for_response_format` |
| `mcrs/conversation_state/prompts/previous.py` | `_resolve_prompt_fns` — previous extractor prompt retained as reference/rollback |

### External libraries

| Library | Usage |
|---|---|
| `lancedb` | `LanceDbCatalog.__post_init__`, `LanceDbCatalog.vector` (cold path) |
| `rapidfuzz` | `RapidfuzzCatalogMatcher.match` |
| `litellm` | `LiteLLMExtractor.extract` / `aextract`, `LiteLLMTextAdapter.generate_batch` |
| `pydantic` | `ConversationStateV0Plus` and related schema models |
| `torch`, `transformers` | `TextCausalAdapter`, `Gemma4TextAdapter` in `llm_rewrite.py` |
| `datasets` (HuggingFace) | `UserEmbeddings.__post_init__`, `HFTalkPlayCatalog` (test/init only) |
| `asyncio` | `V0PlusCompilerQU.batch_compile_track_ids` async fan-out |

---

## Gotchas

1. **`HFTalkPlayCatalog` is test-only.** Despite living in `catalog_hf.py` in the production source tree, this class should not be used in inference. Production code always gets `LanceDbCatalog`. The CLAUDE.md note "HF-backed `HFTalkPlayCatalog` is retained only for unit tests" applies here.

2. **Runtime prompts live outside `experiments/`.** `experiments/` is for one-off reports and current-state notes only. Production schema/prompt code lives under `mcrs/conversation_state/`, with `current` as the extractor prompt and `previous` as the single reference prompt.

3. **`enable_cf_bpr` is legacy back-compat.** `CompilerConfig.enable_cf_bpr` (`compiler.py:160`) and its four companion knobs (`cf_bpr_topk`, `cf_bpr_weight`, etc.) are superseded by the more general `centroid_only_branches` list. They still work via `_resolve_centroid_only_branches` (`compiler.py:553`) but should not be used in new configs.

4. **`metadata_vector` is a back-compat convenience wrapper.** `CompilerCatalog.metadata_vector` (`catalog.py:81`) and both catalog impls' `metadata_vector` methods are kept only because early v0+ compiler code called them directly. New code uses `vector(track_id, vector_field)`.

5. **`centroid_alpha` applies per dense branch, not globally.** The same `alpha` from `centroid_alpha[intent_mode]` is applied to every `DenseBranch`, but each branch mixes with its *own field's* centroid, not a shared metadata centroid. The old `_anchor_centroid` method (`compiler.py:599`) always used the metadata field and is only a back-compat alias.

6. **Lyrics vector coverage is sparse.** The `lyrics_qwen3_embedding_0_6b` column has many null entries in the LanceDB table. `_anchor_centroid_for_field` silently returns `None` when no anchor track has a non-null vector for that field, so the lyrics branch fires for fewer anchors than the metadata/attributes branches.

7. **`transform_query` on `V0PlusCompilerQU` is a stub for observability.** It runs a synchronous extractor call and returns the JSON-dumped state. It is NOT the path that actually produces track IDs — that is `compile_track_ids`. The `transform_query` signature exists only to satisfy the base QU Protocol so the object can be passed anywhere a QU is expected; `CRS_BASELINE` bypasses it when it detects `compile_track_ids`.

8. **Async batch uses `asyncio.run`** (`compiler_qu.py:533`), creating a fresh event loop each call. This is safe because `CRS_BASELINE.batch_chat` is always called from a synchronous context. If a future caller already has a running loop, they must call `_run()` directly via `asyncio.get_event_loop().run_until_complete`.

9. **`last_traces` is a mutable side channel** (`compiler_qu.py:315`). It is reset on every call to `batch_compile_track_ids` and NOT thread-safe. Callers that read it must do so before any subsequent batch call.

10. **`RapidfuzzCatalogMatcher` does not support `album` entity type** (`fuzzy_matcher.py:81`). The `FuzzyMatcher` Protocol declares `album` as valid (listed in `VALID_ENTITY_TYPES`), but `RapidfuzzCatalogMatcher.__init__` only pre-bakes `artist` and `track` maps. Calling `.match(..., "album")` raises `ValueError`. Album support in the Protocol is aspirational, not implemented.

11. **`LanceDbCatalog.vector` cold path uses a per-call SQL query** (`catalog_lance.py:256`). For vector fields not listed in `eager_vector_fields`, each call to `vector(track_id, field)` issues a LanceDB search with a `where` clause. This is slow when called in a hot loop (e.g., `_anchor_centroid_for_field` iterating over many anchors). Always pass the compiler's dense-branch fields in `eager_vector_fields` at startup to avoid this.

12. **`_METADATA_BLOB_TRACK_ID_RE` regex** (`compiler_qu.py:56`) — strips `chat_history_parser`'s YAML metadata blobs back to bare UUIDs. Without this, the extractor LLM receives multi-kilobyte blobs as `played_track_ids` and echoes blobs as output IDs, breaking all downstream UUID lookups. This is an important coupling between `mcrs/inference_utils.py` (which does the rewrite) and this module (which undoes it).
