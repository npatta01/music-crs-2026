# Session / Conversation State

> **What it is:** the structured, per-turn understanding of the conversation that drives retrieval. An LLM reads the multi-turn `session_memory`; all active configs (`prompt_version: v1`) get back fact-first `ConversationStateV1` JSON, which is immediately projected into the compiler's actual contract type, `ConversationStateV0Plus`, via `project_v1_to_v0plus()`. A resolver then grounds the projected state's surface-form names to catalog IDs. (`_decode` tries the V1-then-project path first and only falls back to validating raw V0Plus JSON directly if V1 validation fails — the fallback path is what the legacy `prompt_version: previous`/`v0plus` prompt still exercises.)
> **Source of truth:** `mcrs/conversation_state/schema.py` (the Pydantic models, incl. `project_v1_to_v0plus`) + `mcrs/conversation_state/prompts/current.py` (production prompt, emits V1 JSON) + `mcrs/qu_modules/resolver.py` (resolution) + `mcrs/qu_modules/compiler_qu.py` (extractor wiring + the V1→V0Plus decode logic, `_decode()`).
> Last verified: 2026-07-12.

Session state is the contract between the **conversation** and the **retriever**. Everything the compiler does (which branches fire, how they're weighted, what's filtered or demoted — see [`v0plus_retrieval.md`](v0plus_retrieval.md)) is a function of this object. Get the state wrong and no amount of reranking recovers it — fix representation here first.

---

## 1. Two-stage pipeline

```
session_memory  (list of {role, content} turns)
   │
   1. EXTRACT   LiteLLMExtractor (compiler_qu.py)
   │              LLM call, JSON-schema-constrained to the Pydantic model.
   │              prompt_version: v1 (all active configs; an alias for the
   │              "current" prompt) → LLM returns ConversationStateV1 JSON
   │
   1b. PROJECT  project_v1_to_v0plus()  (conversation_state/schema.py)
   │              structural copy of V1 fields onto the compiler's actual
   │              contract type → ConversationStateV0Plus
   │              (prompt_version: previous/v0plus skips this: that legacy
   │              prompt emits V0Plus-shaped JSON directly, and V1 validation
   │              failing is exactly what triggers _decode()'s fallback path)
   │
   2. RESOLVE   V0PlusResolver (resolver.py)
   │              fuzzy-match surface names → catalog artist/track IDs;
   │              resolve rejections; collect played_track_ids
   │
   → ResolvedConversationState   (what the compiler consumes)
```

- **Extract** — `LiteLLMExtractor` sends the conversation + the JSON schema to an LLM. All active configs set `prompt_version: v1`, which resolves to the same `current_prompt` builder as the default (`_resolve_prompt_fns` in `compiler_qu.py` treats `"current"`/`"v4"`/`"default"`/`"v1"` as synonyms) and asks the model for fact-first `ConversationStateV1` JSON. `_decode()` validates the raw JSON as `ConversationStateV1` first and immediately projects it into `ConversationStateV0Plus` via `project_v1_to_v0plus()` — a structural copy, not a rewrite, that lets the V0Plus compatibility model derive its legacy view fields from the V1 facts. Only if V1 validation raises does `_decode()` fall back to validating the JSON directly as `ConversationStateV0Plus` — the path the legacy `prompt_version: previous`/`reference`/`v3`/`v0plus` prompt (`previous_prompt`, the "old generous V0Plus extraction" CLAUDE.md refers to) actually exercises, since that prompt emits V0Plus-shaped JSON that doesn't validate as V1. Validation (of whichever type ends up used) is deliberately *tolerant* (see §5) so one bad field never voids the whole turn.
- **Resolve** — the (projected) state names entities as the user said them ("more like Radiohead"). `V0PlusResolver` turns those surface forms into catalog IDs via `FuzzyMatcher`, resolves rejections, annotates the artist IDs behind track feedback, and attaches the session's `played_track_ids`. The output `ResolvedConversationState` is what `V0PlusCompiler.compile()` actually reads.

---

## 2. `ConversationStateV0Plus` — field reference

This is the **post-projection, compiler-facing** shape — what `resolver.py` and `compiler.py` actually read, regardless of whether it arrived via `project_v1_to_v0plus()` (the active path) or direct validation (the legacy-prompt fallback path). It is *not* what the LLM emits under `prompt_version: v1`: that raw response is fact-first `ConversationStateV1` JSON, which `project_v1_to_v0plus()` derives these legacy view fields from (not a 1:1 field rename — see the function's docstring in `mcrs/conversation_state/schema.py`). `ConversationStateV1`'s own field reference isn't duplicated here; read the schema directly for that.

The state grew from an original **7-field minimal schema** (iteration 1) to **11 fields** today. Each field maps to a concrete retrieval behavior.

| Field | Type | What it captures | Drives in the compiler |
|---|---|---|---|
| `turn_intent` | `str` | The active ask, naturally phrased, preserving every named artist/track/album/tag. | The canonical dense query string + BM25 clause text. |
| `intent_mode` | `IntentMode` enum | What the user is *doing* this turn. | Centroid-α mixing, anchor-tag expansion, centroid-branch skipping, discography gating. |
| `track_feedback` | `list[TrackFeedback]` | Per-played-track sentiment (accepted / rejected / neutral / seed). | Positive tracks become anchors (centroids); rejected ones drive same-artist demotes. |
| `referenced_track_ids` | `list[str]` | EXPLICIT pronoun/positional refs ("the second one") — *not* named-by-title. Fires on ~5% of turns. | Resolves a referring expression to a specific anchor track. |
| `mentioned_entities` | `list[MentionedEntity]` | Every artist/album/track/tag the user named, with sentiment (incl. neutral & negative). | Entity grounding → BM25 fields, tag expansion, resolved-artist discography. |
| `hard_filters` | `list[HardFilter]` | Catalog-level constraints; v0+ supports `release_date` only. | The pre-fusion candidate mask (hard drop of out-of-range tracks). |
| `explicit_rejections` | `list[ExplicitRejection]` | Hard-exclude future recs ("no more X"); kind ∈ artist/track/tag. | Hard-drop (artist/track) or soft-demote (tag) in post-fusion. |
| `process_constraints` | `ProcessConstraints` | *How* to vary vs. continue (exploration_policy). Orthogonal to intent. | SessionAnchor artist/album demotes (diversify vs exploit). |
| `routing_tags` | `RoutingTags` | Per-turn route flags (exact-entity / lyric / feature / visual / hidden-target). | RRF routing multipliers — up-weight the matching branch(es). |
| `lyrical_theme` | `str \| None` | What the user wants the lyrics to be ABOUT, on lyric turns. | The lyric dense branch query: `"music lyrics: {lyrical_theme}"`. |
| `release_year_range` | `ReleaseYearRange \| None` | Soft era/decade/year hint as integer bounds (e.g. "90s" → 1990–1999). | Year-range BM25 boost, era/popularity lookup, ReleaseYearRange soft re-score. **Soft, not a hard filter.** |

### Nested models

- **`TrackFeedback`** — `{track_id, overall_sentiment ∈ {-1,0,1}, role ∈ {accepted, rejected, seed, neutral}}`. `seed` is reserved for a track the user *explicitly pins* as THE anchor (named by title, by position, or asked an analytical question about); most positive reactions are `accepted`, not `seed` (≤1 seed per turn).
- **`MentionedEntity`** — `{type ∈ {artist, album, track, tag}, value (surface form), sentiment}`.
- **`HardFilter`** — `{field: "release_date", op ∈ {<, >, between}, start, end}`. Partial dates expand (`"2016"` → `2016-01-01`/`2016-12-31`); missing-bound filters are accepted and treated as no-ops downstream.
- **`ReleaseYearRange`** — `{start: int|None, end: int|None}`, either bound open. Inverted bounds are swapped, never rejected (a soft hint must not crash extraction).
- **`ProcessConstraints`** — `{exploration_policy}`. See enum below.
- **`ExplicitRejection`** — `{kind ∈ {artist, track, tag}, value (surface form), source_turn}`.
- **`RoutingTags`** — five booleans, all default `False` (routing inert until configured): `exact_entity_probe`, `lyric_search`, `feature_articulation`, `image_or_visual_search`, `hidden_target_search`.

### Enums

- **`IntentMode`** — `open_explore` (broad, no anchor) · `refinement` (tweak, keep anchors) · `pivot` (deliberate change, drop anchors) · `playlist_build` (cumulative, heavy anchors).
- **`ExplorationPolicy`** — `exploit` (same artist/album) · `diversify_artists` (same style, other artists) · `diversify_albums` (same artist, other albums) · `balanced` (default, no signal).

`intent_mode` and `exploration_policy` are **orthogonal**: a user can be in `refinement` + `diversify_artists` ("more in this style, but different artists").

---

## 3. `ResolvedConversationState` — what the compiler reads

`V0PlusResolver.resolve()` wraps the raw state and adds the grounded fields (`resolver.py`):

| Added field | How it's produced |
|---|---|
| `played_track_ids` | Collected from the session's played history. |
| `resolved_rejections` | `explicit_rejections` surface forms fuzzy-matched to catalog artist/track IDs. |
| `track_feedback_artist_ids` | The artist IDs behind each `track_feedback` entry (so rejecting a track can demote its artist). |
| `resolved_targets` | Surface entities (esp. artists) matched to catalog IDs with a confidence score — feeds the resolved-artist discography branch and similar-artist anchoring. |

---

## 4. How state reaches retrieval

The compiler reads `ResolvedConversationState` and maps fields → branch behavior (full detail in [`v0plus_retrieval.md`](v0plus_retrieval.md)):

- **Anchors** (positive `track_feedback`, `referenced_track_ids`, resolved similar-artists) → centroid vectors for the image/audio/CF centroid-only branches.
- **`turn_intent` + `mentioned_entities`** → BM25 field clauses and the dense intent query.
- **`lyrical_theme`** → lyric dense branch; **sonic descriptors** → CLAP-text branch.
- **`hard_filters`** → candidate mask; **`release_year_range`** → year boost + era lookup + soft re-score.
- **`explicit_rejections` / `process_constraints`** → post-fusion hard-drops and soft demotes.
- **`routing_tags`** → RRF weight multipliers.

---

## 5. Validation & safety

Extraction is hostile-input-aware — the LLM occasionally hallucinates malformed values:

- **`track_id` sanitization** — IDs must be bare identifiers (`^[A-Za-z0-9_\-]+$`). This catches the "stringified row dump" failure (the model emitting `"track_id: 72a..., track_name: ..."` which would crash the catalog SQL `WHERE`). Single-value fields (`TrackFeedback.track_id`) **raise**; list fields (`referenced_track_ids`) **silently drop** bad entries so one hallucination doesn't void the turn.
- **Tolerant filters** — `HardFilter` with a missing bound is accepted and no-op'd downstream rather than rejected (rejecting used to lose the whole turn's `turn_intent`/entities over one bad filter). `ReleaseYearRange` swaps inverted bounds instead of failing.

---

## Pointers

- Retrieval consumption: [`v0plus_retrieval.md`](v0plus_retrieval.md)
- Schema source: `mcrs/conversation_state/schema.py`
- Prompt source: `mcrs/conversation_state/prompts/current.py`; previous reference: `mcrs/conversation_state/prompts/previous.py`
- Resolver: `mcrs/qu_modules/resolver.py`; extractor: `mcrs/qu_modules/compiler_qu.py`
- Historical north-star schema notes were pruned from the working tree; use Git
  history if that design lineage is needed.
- Per-module internals: [`docs/codebase/modules/qu_modules.md`](../codebase/modules/qu_modules.md)
