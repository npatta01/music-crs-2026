# ConversationState — v3 Candidate Schema

Status: v3 candidate, pending gold-state validation before promotion to v3.

This file is the canonical schema reference for extractor and compiler
implementation. The companion [`README.md`](README.md) explains how the schema
was derived; [`iteration_1_minimal_schema.md`](iteration_1_minimal_schema.md)
is the minimal v0+ subset that should be implemented first.

## Decision Summary

The design is approved as a **v3 candidate**, not final v3. Promotion to final
v3 requires committed gold states and field-level extractor agreement.

Converged decisions:

- Use one shared `ConversationState` for retrieval, ranking, and response
  generation.
- Recompute state from full conversation history each turn.
- Keep the normalized state grounded in observable conversation/catalog facts.
- Separate current-turn `target_entities` from history/reference
  `mentioned_entities`.
- Keep `track_feedback` with aspect-level positive/negative facets.
- Use `routing_tags` as additive compiler route flags.
- Keep `primary_mode` only if extractor validation proves it reliable.
- Keep `played_track_ids` factual only. Replay/exclusion behavior is compiler
  policy.
- Use `explicit_rejections` only for user-declared negative evidence.
- Use `open_requirements` as the single unmet-ask/catalog-gap ledger.
- Keep `unsupported_signals` so multimodal/visual failures are visible.
- Keep centroids, top-K anchor selection, recency windows, and fusion weights in
  the compiler, not in state.

Remaining gated decision:

- `primary_mode` survives only if extractor agreement is at least `80%` on the
  committed gold-state set. If agreement is below `70%`, remove it and let
  routing tags plus compiler defaults handle tie-breaking.

## Production Schema

```yaml
# ---------- mechanical, no LLM extraction ----------
played_track_ids: [<track_id ordered by turn>]
user_id: <uuid>
user_profile: <dict from dataset>

# ---------- high-frequency situational context ----------
activity_context:
  value: <free text or null>             # "studying", "workout", "cozy evening"
  source_turn: <int or null>
  scope: session | active_segment
  confidence: 0.0..1.0

# ---------- active and stable constraints ----------
constraints:
  - facet: era | genre | mood | activity_context | instrumentation
      | vocal_style | language | popularity | lyrics | geography | other
    value: <string>
    source_turn: <int>
    scope: session | active_segment
    polarity: include | exclude | prefer | avoid
    hardness: soft | hard
    confidence: 0.0..1.0

# ---------- current turn ----------
turn_intent: <free text>

target_entities:
  - type: track | artist | album | tag | lyric | unknown
    role: positive | negative | reference
    source_text: <verbatim span from latest user turn>
    resolved_ids: [<catalog_id, ...>]     # may be empty
    resolution_confidence: 0.0..1.0
    exactness: exact | fuzzy | remembered | reference

routing_tags:
  exact_entity_probe: bool
  hidden_target_search: bool
  lyric_search: bool
  feature_articulation: bool
  image_or_visual_search: bool

primary_mode: open_explore | playlist_build | refinement | pivot

# ---------- history-derived evidence ----------
track_feedback:
  - track_id: <track_id>
    overall_sentiment: -1.0..1.0
    role: accepted | rejected | near_miss | confirmed_target | wrong_item | seed
    aspect_feedback:
      positive: [<free-string facets for now>]
      negative: [<free-string facets for now>]
    requirement_refs: [<open_requirements.id>]

mentioned_entities:
  - type: artist | album | track | tag | lyric | unknown
    value: <string>
    source_text: <span or paraphrase>
    resolved_ids: [<catalog_id, ...>]
    resolution_confidence: 0.0..1.0
    sentiment: -1.0..1.0
    first_turn: <int>
    relation:
      kind: temporal_before | temporal_after | same_album
        | same_artist_different_track | attribute_shift | era_match
        | same_genre_different_artist | similar_to | contrast_with | other
      pivot: <track_id or date or string>

explicit_rejections:
  - kind: track | artist | album | tag | attribute
    id_or_value: <catalog_id or text>
    source_turn: <int>
    rationale: <text snippet or null>

# ---------- segmentation and carryover ----------
segments:
  - turn_range: [<start>, <end>]
    primary_mode: <mode>
    track_feedback_ref: [<track_id>]
    notes: <optional text>

carryover_policy:
  anchors: keep_all | drop_all | recent_window | active_only
  constraints: keep | reset_by_scope

# ---------- requirements ledger ----------
open_requirements:
  - id: hash(kind, normalized_description)
    kind: requested_artist | requested_track | requested_attribute
      | lyric_match | visual_recall | catalog_gap | other
    description: <text>
    normalized_description: <canonical lowercase/normalized text>
    status: pending | known_unavailable | partially_satisfied | fulfilled
    first_turn: <int>
    last_updated_turn: <int>

unsupported_signals:
  - kind: visual_album_art | sonic_recall | external_reference | other
    description: <text>
    executable: bool

# ---------- process knobs from user intent, not compiler policy ----------
process_constraints:
  exploration_policy: exploit | diversify_artists | diversify_albums | balanced
  novelty_pressure: none | soft | hard

# ---------- true hard filters only ----------
hard_filters:
  - {field: release_date, op: "<"|">"|"between", value: ...}
  - {field: artist_id, op: "in"|"not_in", value: [...]}
  - {field: album_id, op: "in"|"not_in", value: [...]}
  - {field: popularity, op: ">="|"<=", value: ...}
  - {field: catalog_tag_whitelist, op: "contains"|"not_contains", value: instrumental}

# ---------- diagnostic-only, not emitted at blind inference ----------
_debug_flags:
  benchmark_imitation: bool
```

## Standardized Agreements

| Topic | Final position |
|---|---|
| State scope | One shared state contract, with retrieval/ranking/response views derived downstream. |
| Recompute strategy | Stateless full-history recompute each turn. |
| Entity split | `target_entities` are current-turn ask targets; `mentioned_entities` are history/reference anchors. |
| Entity resolution | Entities carry `source_text`, `resolved_ids`, `resolution_confidence`, and target exactness. |
| Track feedback | Track-level scalar sentiment plus role plus aspect-positive/aspect-negative facets. |
| Unmet asks | Single `open_requirements` ledger; per-track feedback uses `requirement_refs`. |
| Requirement IDs | Deterministic `hash(kind, normalized_description)`, never extractor-invented local ids. |
| Activity context | Top-level structured fast path with `value/source_turn/scope/confidence`; segment changes use scoped constraints. |
| Carryover | State records anchor/constraint carryover intent; compiler decides windows and weights. |
| Played tracks | Factual ledger only; replay exclusion is compiler policy. |
| Explicit negatives | `explicit_rejections` only when user explicitly rejects a track/artist/tag/attribute. |
| Routing | `routing_tags` are additive booleans. `primary_mode` is gated on extractor reliability. |
| Visual cues | `unsupported_signals` stores cumulative evidence; `routing_tags.image_or_visual_search` flags per-turn demand. |
| Process constraints | Use enums, not false-precision scalars. `novelty_pressure` is `none/soft/hard`. |
| Hard tag filters | Only `catalog_tag_whitelist`, initially `instrumental`. Expand only after catalog audit. |
| User language | `user_profile.preferred_language` is not a hard filter unless a track-side language field is proven. |
| Debug flags | `_debug_flags.benchmark_imitation` is dev/audit-only and must not affect blind inference routing. |

## Open Questions Still Allowed

Only these questions should remain open before implementation:

1. Does `primary_mode` pass extractor agreement strongly enough to keep?
2. Which additional catalog tags, if any, are safe enough for
   `catalog_tag_whitelist` after a tag audit?
3. Does the first gold-state agreement run expose missing schema fields, or only
   extractor/prompt weaknesses?

Everything else should be treated as settled unless validation fails.

## Validation Gate

Before promoting this to final v3:

1. Port the 40 v2-era hand-authored states to this merged schema.
2. Add 5-10 additional sessions covering:
   - visual/cover-art recall,
   - fuzzy or remembered target entities,
   - exact-entity mismatch,
   - feature articulation,
   - user dissatisfaction / explicit rejection,
   - long-range callback.
3. Run extractor agreement against committed gold states.
4. Report field-level pass/fail.

Suggested field gates:

| Field | Gate |
|---|---:|
| `track_feedback.overall_sentiment` | >=85% |
| `target_entities.exactness` | >=80% |
| `target_entities.resolved_ids` when extractor resolves | >=75% |
| `mentioned_entities` presence | >=80% |
| `constraints` facet/scope/hardness | >=75% |
| `hard_filters` when explicit | >=85% |
| `routing_tags` per-tag F1 | >=80% |
| `explicit_rejections` presence on relevant turns | >=80% |
| `open_requirements` | >=70% |
| `primary_mode` | keep if >=80%; drop if <70% |
| `unsupported_signals` | informational until enough examples exist |

Do not add new schema fields until this validation fails in a way that demands
one.
