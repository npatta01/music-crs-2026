# Session / Conversation State

> **What it is:** the structured, per-turn understanding of the conversation
> that drives retrieval. An LLM reads `session_memory` and emits
> `ConversationStateV1`; a deterministic bridge projects that fact state into
> the current `ConversationStateV0Plus` compiler contract, and the resolver then
> grounds eligible surface-form names to catalog IDs.
>
> **Source of truth:** `mcrs/conversation_state/schema.py`,
> `mcrs/conversation_state/prompts/current.py`,
> `mcrs/qu_modules/resolver_v0plus.py`, and
> `mcrs/qu_modules/compiler_v0plus_qu.py`.
>
> Last verified: 2026-06-07.

Session state is the contract between the conversation and candidate
generation. The V1 contract is LLM-facing and fact-first: it asks the model for
meaningful conversation facts, not compiler/routing policy. The bridge/projector
exposes derived compatibility views for existing V0Plus compiler code while
downstream retrieval migrates. The active prompt and few-shot examples are the
primary implementation surface; the schema alone is not enough to change
extraction behavior.

---

## 1. Two-stage pipeline

```
session_memory  (list of {role, content} turns)
   |
   1. EXTRACT   LiteLLMExtractor (compiler_v0plus_qu.py)
   |              LLM call, JSON-schema-constrained to ConversationStateV1
   |
   2. PROJECT   project_v1_to_v0plus(schema.py)
   |              structural V1 -> V0Plus compatibility bridge
   |
   3. RESOLVE   V0PlusResolver (resolver_v0plus.py)
   |              fuzzy-match only seed/current-target surface names
   |              resolve hard/soft rejections
   |              collect played_track_ids and feedback artists
   |
   -> ResolvedConversationState   (what the compiler consumes)
```

- **Extract**: `current.py` asks the model to output V1 fields only. It should
  classify whether prior entities are current seeds, satisfied history,
  contrast, or rejected context instead of treating every positive mention as a
  retriever anchor.
- **Project**: `project_v1_to_v0plus()` copies only structured V1 fields and
  derives V0Plus compatibility. It does not inspect raw user text or repair
  phrases with regex-like logic.
- **Resolve**: `V0PlusResolver` consumes derived property views such as
  `mentioned_entities`, `style_reference_entities`, and
  `explicit_rejections`. Exact targets and style references are both resolved
  when useful, but they carry different `resolution_role` values so the
  compiler can route them differently.

---

## 2. `ConversationStateV1` fields

| Field | Type | What it captures | Retrieval implication |
|---|---|---|---|
| `current_request` | `CurrentRequest \| None` | Active ask plus a factual request type such as `new_artist`, `exact_track`, `attribute_search`, or `hidden_target`. | Weak request-kind evidence. The compiler derives route/profile from this plus facts. |
| `facts` | `list[StateFact]` | Atomic artist/album/track/attribute facts with `role`, `anchor_use`, `relation`, and `reuse`. | Primary V1 state contract. Exact targets, style references, query facets, and exclusions project into separate compiler-facing views. |
| `exclusions` | `list[StateExclusion]` | Explicit hard exclusions or soft avoid preferences. | Projects to negative mentions and explicit rejections when eligible. |
| `track_feedback` | `list[TrackFeedback]` | User reaction to played tracks: `accepted`, `rejected`, `seed`, `neutral`, `satisfied`, or `contrast`. | Positive/seed tracks can anchor centroids; rejected/contrast/satisfied roles should not blindly carry forward. |
| `referenced_track_ids` | `list[str]` | Explicit pronoun/position references to played tracks. | Exact track anchors when the user says "the second one" or "that previous track". |
| `temporal_constraint` | `TemporalConstraint \| None` | Minimal date/era guardrail. | Only literal hard release-date asks use `apply_as_filter=true`; style/reference eras stay soft. |
| `lyrical_theme` | `str \| None` | Lyrics topic or quoted lyric phrase. | Lyric dense branch query when present. |

V1 intentionally does **not** contain `turn_intent`, `entities`, `rejections`,
`target_artist_mode`, `retrieval_profile`, `routing_tags`, `hard_filters`, or
`release_year_range`. Those are projected compatibility fields.

### Fact roles

`StateFact` is the main schema surface:

```json
{
  "type": "artist|album|track|attribute",
  "facet": "genre|mood|sonic|instrument|energy|lyrical_theme|visual|popularity|era|performer",
  "value": "Morphine",
  "role": "current_target|satisfied_prior|history|contrast|rejected",
  "anchor_use": "must_use|query_facet|partial_anchor|do_not_use",
  "relation": "exact_target|style_reference|query_facet|exclude|history|contrast|satisfied_prior",
  "reuse": "must_reuse|may_reuse|avoid_exact|must_exclude|not_applicable",
  "source_turn": 4,
  "mentioned_current_turn": true,
  "evidence_text": "another artist"
}
```

Rules:

- `current_target` can drive exact/discography retrieval only when the fact is
  an exact entity target with `reuse=must_reuse`.
- `satisfied_prior`, `history`, `contrast`, and `rejected` are retained for
  context and debugging but do not become exact retrieval seeds.
- `evidence_text` is optional, bounded to 240 characters, and intended only for
  high-risk decisions such as fact role, hard rejection, and temporal
  hard-vs-soft classification.

### Fact relation and reuse

`StateFact` is the preferred v1 extractor surface. `role` says what the fact is
in the conversation; `relation` and `reuse` say what the compiler may do with
it.

```json
{
  "type": "artist",
  "value": "Sadistik",
  "role": "satisfied_prior",
  "anchor_use": "do_not_use",
  "relation": "style_reference",
  "reuse": "avoid_exact",
  "source_turn": 3,
  "mentioned_current_turn": true,
  "evidence_text": "big fan of his work but branch out"
}
```

Compiler rules:

- `exact_target` + `must_reuse` projects to positive `mentioned_entities`; this
  can drive BM25 exact fields, exact-track/artist resolution, and resolved
  artist discography.
- `style_reference` + `may_reuse|avoid_exact` projects to
  `style_reference_entities`, not positive `mentioned_entities`. This can feed
  dense query text and centroid/similar-artist anchors without causing exact
  artist discography fanout.
- `satisfied_prior` entity facts with `do_not_use` and `avoid_exact|may_reuse`
  also project to `style_reference_entities`. This preserves liked prior
  artists/tracks as soft context without exact/discography fanout when the LLM
  keeps the raw relation as satisfied context instead of explicit
  `style_reference`.
- `query_facet` + `not_applicable` projects attributes to positive tag/query
  text.
- `exclude` + `must_exclude` projects to negative `mentioned_entities` and
  `explicit_rejections`.

This split is intentional. A turn like "different artists with Sadistik's
style" should keep Sadistik available as a soft style anchor while also
preventing exact Sadistik tracks from being recommended.

### Temporal guardrail

Temporal extraction is deliberately small:

- Literal hard date asks, such as "only 1990s tracks" or "nothing newer than
  2010", become `kind=release_date`, `strength=hard`,
  `apply_as_filter=true`.
- Style language, such as "late 70s sound", "golden era", or "90s vibe",
  becomes `kind=style_era` or `reference_era`, `strength=soft`,
  `apply_as_filter=false`.

The compiler's release-date mask now requires `apply_as_filter=true`; soft style
eras do not drop out-of-range catalog items.

---

## 3. Compatibility views

The extractor emits `ConversationStateV1`; `project_v1_to_v0plus()` returns a
`ConversationStateV0Plus` compatibility object so existing compiler code can
migrate gradually:

| Derived view | Source in v1 |
|---|---|
| `turn_intent` | `current_request.summary`. |
| `target_artist_mode` | `current_request.request_type` plus projected exact/new-artist evidence. |
| `retrieval_profile` | `current_request.request_type` plus exact/feature/hidden-target evidence. |
| `intent_mode` | Derived V0Plus `retrieval_profile`: novelty -> pivot, continuation/exact -> refinement, otherwise open explore. |
| `process_constraints` | Derived V0Plus `target_artist_mode` and `retrieval_profile`. |
| `routing_tags` | Derived V0Plus `retrieval_profile` plus `lyrical_theme`. |
| `mentioned_entities` | Negative exclusions plus exact/query facts that may drive current exact retrieval. Style references are excluded. |
| `style_reference_entities` | Artist/album/track facts with `relation=style_reference`; consumed as soft reference anchors, not exact targets. |
| `explicit_rejections` | Hard artist/track rejections plus tag/style demotions. |
| `release_year_range` | `temporal_constraint` year bounds. |
| `hard_filters` | Only hard release-date temporal constraints with `apply_as_filter=true`. |

Legacy-shaped trace/test dictionaries are accepted by a `model_validator` and
coerced into v1. This preserves historical tests while making the current LLM
schema smaller and less ambiguous.

---

## 4. Replay-pack evaluator

The replay evaluator is an optional follow-up harness for checking a small batch
after prompt changes. It is not the state-v1 deliverable by itself. The first
deliverable is a clear extractor prompt contract plus examples in
`mcrs/conversation_state/prompts/current.py`.

Default focused packs:

- `P0_roleless_stale_entity_failure`
- `P0_novelty_prior_anchor_failure`
- `P0_new_artist_union20_gap_failure`
- `P1_temporal_constraint_failure`
- `P1_rejection_guardrail_failure`
- `POS_exact_entity_success_control`
- `POS_clean_final_hit_control`

Run the local oracle smoke test:

```bash
uv run python scripts/evaluate_state_replay_pack.py --state-source ideal --packs focused
```

Run a live extractor experiment on the same 70 focused examples:

```bash
OPENROUTER_API_KEY=... uv run python scripts/evaluate_state_replay_pack.py --state-source live --packs focused --output scripts/state_replay_results.json
```

The evaluator trims each sample to evidence visible at extraction time, scores
schema validity, role correctness, target-artist mode, retrieval profile,
temporal semantics, rejection normalization, and positive-control preservation,
then reports aggregate and per-pack pass rates.

---

## 5. Pointers

- Schema source: `mcrs/conversation_state/schema.py`
- Active prompt: `mcrs/conversation_state/prompts/current.py`
- Prompt contract notes: `mcrs/conversation_state/prompts/README.md`
- Previous reference prompt: `mcrs/conversation_state/prompts/previous.py`
- Resolver: `mcrs/qu_modules/resolver_v0plus.py`
- Extractor wiring: `mcrs/qu_modules/compiler_v0plus_qu.py`
- Replay evaluator: `mcrs/conversation_state/replay_eval.py`
- CLI: `scripts/evaluate_state_replay_pack.py`
