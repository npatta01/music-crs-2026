# ConversationState Schema Design

Status: `analyzed`.
Audience: anyone reviewing or implementing the schema, extractor, or compiler.

> **Schema label:** the proposed schema is a **v3 candidate**, not v3. Promotion to v3 is gated on committed gold states + field-level extractor agreement (see the validation section below).
>
> **Canonical merged schema:** [`final_merged_schema.md`](final_merged_schema.md) — use this for implementation. This README explains how the schema was derived and what trade-offs it makes.
>
> **Iteration-1 minimal cut:** [`iteration_1_minimal_schema.md`](iteration_1_minimal_schema.md) — a 7-field v0+ subset that should be implemented first to produce a useful retrieval measurement before investing in the full v3 extractor.

## Final position

The agreed production schema is captured in [`final_merged_schema.md`](final_merged_schema.md).

Standardized agreements:

- `activity_context` remains top-level, but structured with `value`, `source_turn`, `scope`, and `confidence`.
- `track_feedback.unmet_ask` is replaced by `requirement_refs` pointing into `open_requirements`.
- `open_requirements.id` is deterministic: `hash(kind, normalized_description)`.
- `process_constraints` uses `novelty_pressure: none | soft | hard`; no scalar novelty strength.
- `hard_filters` can use `catalog_tag_whitelist`, initially only `instrumental`.
- `preferred_language` is not a hard filter unless a track-side language field is proven.
- `routing_tags.image_or_visual_search` is kept for per-turn visual-search demand.
- `_debug_flags.benchmark_imitation` is dev/audit-only and must not affect blind inference routing.
- `primary_mode` is gated: keep if extractor agreement is at least `80%`; drop if below `70%`.

No more schema fields should be added until committed gold-state validation fails in a way that requires one.

## Purpose of this document

This document derives a ConversationState schema for the Music-CRS pipeline through an iterative pass over the `test` split (10 → 30 → 25 → 500 → 1000 sessions). The reason to do this carefully: every schema field becomes a slot the extractor prompt must populate, a field the compiler must route, and a labeling-guide concept the team must agree on. Fields are not cheap. We want to commit once.

The output is two complementary schemas:

- **v3 candidate** ([`final_merged_schema.md`](final_merged_schema.md)) — the full schema, kept as north star.
- **v0+ iteration 1** ([`iteration_1_minimal_schema.md`](iteration_1_minimal_schema.md)) — a 7-field cut for the first end-to-end retrieval measurement.

This README captures the design history and trade-offs that led to both.

---

## Problem framing

The competition asks for top-20 track retrieval from a 47k-track catalog conditioned on a multi-turn conversation. Today's best dev numbers are:

- BM25 + tag_list: `NDCG@20 0.0970, Hit@1000 0.6311`
- Dense Qwen3-8B: `NDCG@20 0.1025, Hit@1000 0.6934`
- Offline RRF hybrid: `NDCG@20 0.1072, Hit@1000 0.7210`
- Best LLM rewrite: `NDCG@20 0.1092, Hit@1000 0.5561`

The ceiling problem: **~28% of dev turns have the gold track absent from top-1000 entirely**, so no reranker can save them. Text-only retrieval has saturated.

The rewrite paradox: rewrites lift `NDCG@20` while *destroying* `Hit@1000`, because a single flat rewritten string drops anchor entities. From the query-intent labels: 99.6% of sessions need carryover from prior user *and* assistant/music turns; 50% of failure risk is `long_range_callback`.

The structural diagnosis is that the system needs a **conversation-state representation** richer than "concatenate the prefix" and richer than "one rewritten query string". That representation feeds a compiler that emits retrieval branches, fusion, and filters.

This document is about the shape of that representation.

---

## Data realities the schema must respect

Critical to get right before designing fields:

| Field | In `test` data | At inference (`blind_a/b`) | Currently used by baseline |
|---|---|---|---|
| `conversation_goal.listener_goal` | yes (gold) | **no** — it's a ground-truth label | no |
| `conversation_goal.category/specificity` | yes | no | no |
| `assistant.thought` | yes | **no** at inference (we generate the turn) | no |
| `goal_progress_assessments` | yes | no | no |
| `user_profile` | yes | yes | partially (string injection only) |
| `user_id` + user CF-BPR embedding | yes | yes | **no** |
| Played `track_id`s + 6 embedding modalities | yes | yes | **no** |
| Prior user turns (text) | yes | yes | yes |
| Prior assistant turns (text only) | yes | yes | yes |

The extractor at inference sees: **user turns, assistant turns, played track_ids, user_profile, user_id**. It does **not** see the listener_goal or the assistant's `thought` field. The schema must be derivable from this strict subset.

The compiler additionally has access to the catalog (47k tracks with metadata + 6 embedding modalities) and the user's CF-BPR vector. **The compiler can do a lot of embedding-space work that the extractor cannot.**

---

## Iteration history

Five rounds, all on `test` split:

| Round | Sessions | Method | Outcome |
|---|---:|---|---|
| 1 | 10 | Deep read, hand-trace each turn | Identified 7 gap modes; first draft schema (4 fields) |
| 2 | 30 | Pattern scan + selective deep read | Refined schema to 11 fields; added `segments`, `process_constraints`, `unmet_asks`/`catalog_gaps` |
| 3 | 25 | Pattern scan + 4 deep reads | Added `anchor_entities`, `activity_context`, `feature_articulation` mode → 13 fields ("v2") |
| 4 | 500 (fresh) | Tightened pattern scan + 5 outlier deep reads | v2 covered 99.7% of pattern-firing sessions; no new fields |
| 5 | 1000 (full test split) | Final pattern scan + 1 outlier deep read | 100% schema coverage; frequencies stabilized; declared v2 "done" |

Total unique sessions read: 65 deep + 1000 scanned (with overlap).

**Critical caveat:** my pattern scanner uses regex tagging. Earlier rounds over-counted some patterns (e.g. `pivot` jumped from 40% at N=30 to 11% at N=500 when I tightened the regex). The final N=1000 numbers below are more reliable than any earlier batch.

### Final pattern frequencies (N=1000)

```
activity_context              53.4%
temporal_explicit             44.2%
similar_to_played             43.4%
new_artist_meta               40.2%
tempo_explicit                37.9%
anchor_artist_named           37.6%
temporal_era                  35.9%
multi_artist_anchor           32.3%
hidden_target                 28.9%
lyric_search                  20.9%
popularity_tier               17.6%
comparative_neg               17.2%
instrumental_constraint       16.7%
unmet_catalog                 16.5%
specific_instrument_req       14.7%
pivot                         11.3%
collab_request                 8.1%
female_voc_req                 4.7%
user_dissatisfaction           4.1%   ← failure mode the schema must prevent
feature_articulation           3.6%
language_other                 3.2%
emotional_state                2.5%
goal_complete                  0.5%
```

Per-goal-category coverage was 98.7–100% across all 11 categories. Median session populates 5 fields; p95 populates 9.

### Where the pass declared v2 "done"

13 fields, organized as:
- Mechanical (3): `played_track_ids`, `user_id`, `user_profile`
- Session-stable (2): `session_constraints`, `activity_context`
- Turn-stateful, segmented (1 container with sub-fields): `segments` containing `turn_range`, `mode`, `reset_prior`, `track_sentiments`, `anchor_entities`, `hard_filters`, `catalog_gaps`, `unmet_asks`
- Active retrieval (2): `turn_intent`, `process_constraints`

`mode` enum: `open_explore | lyric_search | hidden_target_search | playlist_build | find_more_like_this | pivot | feature_articulation`.

---

## Revisions that shaped the v3 candidate

After locking v2, the schema was revised in several places. The revisions are the difference between v2 and the v3 candidate captured in [`final_merged_schema.md`](final_merged_schema.md):

| Field area | v2 position | Revised position in v3 candidate |
|---|---|---|
| Aspect-level feedback per track | Dropped, on the theory that embedding centroids would absorb it | **Restored.** Embedding centroids can rank but cannot tell the dense branch what facet to ask for next ("more melodic, less heavy" requires a symbolic field). Aspect feedback must be in state. |
| Current-turn ask vs history references | Conflated into one `anchor_entities` list | **Split** into `target_entities` (current ask) vs `mentioned_entities` (history). Same shape, different compiler routing — current-ask drives exact-entity probes; history references drive anchor lookups. |
| Carryover at segment boundaries | `reset_prior: bool` per segment | **Graded.** Two independent knobs: `anchors` (`keep_all / drop_all / recent_window / active_only`) and `constraints` (`keep / reset_by_scope`). Boolean was too coarse — a pivot may drop anchor tracks but keep era/genre constraints. |
| Visual / cover-art / sonic-recall cues | Missed entirely | **Added** as `unsupported_signals` with `executable: bool`. Logs the failure mode visibly so a future multimodal branch can flip `executable: true`. |
| Unmet asks + catalog gaps | Two separate fields (`unmet_asks`, `catalog_gaps`) | **Merged** into `open_requirements` with `kind` + `status`. Lifecycle is identical; two lists invite drift. |
| Routing | `mode` as exclusive enum | **Feature flags** (`routing_tags`) plus a single `primary_mode`. Turns can be simultaneously `lyric_search` AND `hidden_target_search`; the enum forced a choice. |
| Diversification | `process_constraints.prefer_new_artists` (single knob) | **Structured** as `exploration_policy` (`exploit / diversify_artists / diversify_albums / balanced`) plus `novelty_pressure` enum. |
| Played-tracks exclusion | Treated as part of carryover policy | **Split.** `played_track_ids` is a factual ledger. `explicit_rejections` is user-declared. "Don't replay" is a compiler default, not schema state. |
| Entity resolution | Bare `{type, value, role}` | **Enriched** with `source_text`, `resolved_ids`, `resolution_confidence`, and (for `target_entities`) `exactness: exact|fuzzy|remembered|reference`. The compiler routes "Play Drop Coupes" (exact) and "the song that goes 'down in a hole'" (remembered) very differently. |

Turn 5–8 miss rates climb monotonically (16.6% at T2 → 27.6% at T8 in independent state-pressure audits). That's the long-range callback failure mode, and it's what motivated graded carryover and explicit segment-aware state.

### Things v2 got right and v3 keeps unchanged

- `played_track_ids` is mechanical and structural; do not route it through the extractor.
- `track_feedback` is universal (every turn has played tracks to rate).
- `turn_intent` is always populated.
- Stable session constraints (era, genre, etc.) belong separate from per-turn intent.
- The ~4% `user_dissatisfaction` rate is the canonical anchor-poisoning failure mode that the schema's exclusion machinery must prevent.

The compiler-side coverage story: the 70%+ of sessions that use "like X" / "in the vein of Y" / multi-artist anchor language sum across `similar_to_played` + `anchor_artist_named` + `multi_artist_anchor` patterns. This is what justifies the `mentioned_entities` slot in v3 and the compiler's ability to look up named artists' catalog tracks → use their audio/lyrics/attribute embeddings as anchors.

---

## Proposed v3 candidate schema

```yaml
# ---------- mechanical (no LLM call) ----------
played_track_ids: [<track_id ordered by turn>]   # factual ledger only; not a rejection signal
user_id: <uuid>
user_profile: <dict from dataset>

# ---------- activity context (top-level optional; the common case is stable) ----------
activity_context: <free text or null>   # e.g. "studying", "cozy evening", "cheer me up"
                                         # null when user gives no situational signal.
                                         # Mid-session shifts go in constraints[] below
                                         # (facet: activity_context, scope: active_segment).

# ---------- constraints (era, genre, instrumentation, vocal_style, language, etc.) ----------
constraints:
  - facet: era              # examples: era, genre, language, instrumentation, vocal_style,
    value: "90s"            #           activity_context (only when used as a mid-session override)
    source_turn: 1
    scope: session            # session | active_segment
    hardness: soft            # soft | hard
  - facet: genre
    value: "rap"
    source_turn: 1
    scope: session
    hardness: soft
  - facet: instrumentation
    value: "instrumental only"
    source_turn: 4
    scope: active_segment
    hardness: hard            # earned over turns when user re-asserts

# ---------- current turn (always reflects the latest user turn) ----------
turn_intent: <free text>                # the active ask, naturally phrased
target_entities:                        # entities in THIS turn's ask
  - type: track | artist | album | tag
    role: positive | negative | reference
    source_text: <verbatim span from the user turn>
    resolved_ids: [<catalog_id, ...>]   # may be empty; extractor or compiler resolves
    resolution_confidence: 0..1
    exactness: exact | fuzzy | remembered | reference
    # exact:      "Play 'Drop Coupes' by Nipsey Hussle"
    # fuzzy:      "Down In A Hole by Alice in Chains" (close paraphrase)
    # remembered: "the one with the lyric 'down in a hole'" (no clean entity)
    # reference:  "like A Tribe Called Quest" (anchor, not target of playback)

routing_tags:                           # feature flags for the compiler; not exclusive
  exact_entity_probe: bool
  hidden_target_search: bool
  lyric_search: bool
  feature_articulation: bool            # rare (3.6%); E-goal sessions
primary_mode: open_explore | playlist_build | refinement | pivot

# ---------- history-derived ----------
track_feedback:                         # one entry per played track
  - track_id
    overall_sentiment: -1..+1
    aspect_feedback:
      positive: [<facets: mood, instrument, vocal_style, etc.>]
      negative: [<facets>]
    unmet_ask: [<things asked at this turn but not delivered>]
mentioned_entities:                     # entities surfaced from prior feedback or history
  - type: artist | album | track | tag
    value
    resolved_ids: [<catalog_id, ...>]
    sentiment: -1..+1
    first_turn
    relation?: {kind: temporal_before | temporal_after | same_album
                     | same_artist_different_track | attribute_shift
                     | era_match | same_genre_different_artist,
                pivot: <track_id or date>}

explicit_rejections:                    # ← NEW; user actually said no
  - kind: track | artist | tag
    id_or_value
    source_turn
    rationale?: <text snippet>

# ---------- carryover and segmentation ----------
segments:                               # ≥1; new segment when intent meaningfully shifts
  - turn_range: [start, end]
    primary_mode
    track_feedback_ref: [<track_ids included in this segment>]
    notes?: <text>
carryover_policy:                       # graded; replaces v2's reset_prior bool
  anchors:    keep_all | drop_all | recent_window | active_only
  constraints: keep | reset_by_scope    # session-scope kept, active_segment-scope drops on pivot
  # NOTE: there is intentionally no "exclusions" knob here. played_track_ids is
  # factual; explicit_rejections is user-declared. Whether to *use* either as
  # a retrieval exclusion is a compiler policy, not schema state.

# ---------- requirements ledger ----------
open_requirements:                      # unifies unmet_asks + catalog_gaps + unresolved entities
  - kind: requested_artist | requested_attribute | lyric_match | visual_recall
    description: <text>
    status: pending | known_unavailable | partially_satisfied | fulfilled
    first_turn

unsupported_signals:                    # visual / sonic / external cues, with executable status
  - kind: visual_album_art | sonic_recall | external_reference
    description: <text>
    executable: bool                    # false today; flip true when a multimodal branch ships

# ---------- process and filters ----------
process_constraints:
  exploration_policy: exploit | diversify_artists | diversify_albums | balanced

hard_filters:                           # clean, explicit catalog fields when the user has been clear
  - {field: release_date,       op: "<"|">"|"between", value: ...}
  - {field: artist_id,          op: "in"|"not_in",     value: [...]}
  - {field: album_id,           op: "in"|"not_in",     value: [...]}
  - {field: popularity,         op: ">="|"<=",         value: ...}
  - {field: preferred_language, op: "==",              value: ...}
  - {field: tag_list,           op: "contains"|"not_contains", value: ...}
    # tag_list filtering is RESTRICTED to a whitelist of well-defined tags:
    #   - "instrumental" (binary, clean)
    #   - language tags (clean)
    #   - explicit-content flag (clean)
    # Free-form mood / genre / vibe tags (e.g. "chill", "dark", "smooth") must NOT
    # appear here — they belong in constraints (hardness=soft) or turn_intent,
    # where the dense branch and post-scoring can weight without false negatives.

# ---------- diagnostic-only (not state for the compiler) ----------
# These fields exist on dev/audit runs only. The extractor does not emit them
# at inference. The compiler must not route on them.
_debug_flags:
  benchmark_imitation: bool             # "this looks like dataset-shape imitation" — audit only
```

Roughly 11 top-level slots in the production schema (excluding `_debug_flags`). Smaller than the pre-review v3 because `activity_context` and the carryover "exclusions" knob both folded out.

### What v3 is NOT

- **Not** a compiler. Things like "anchor recency window", "top-K positive anchor selection", "centroid weighting" are compiler concerns. The state declares signal; the compiler decides retrieval behavior.
- **Not** a place to store embeddings. Embeddings are catalog-side; the state references entities by ID.
- **Not** sentiment-free. Scalar `overall_sentiment` on `track_feedback` and on `mentioned_entities` is required for ranking and weighting.
- **Not** a place for derivations the compiler can do for free. E.g. `played_artist_ids` is a join on `played_track_ids`; don't store it.

---

## Design decisions and open questions

Each decision lists what was settled and what remains worth pressure-testing during gold-state validation or extractor implementation.

### 1. `target_entities` vs `mentioned_entities` — same shape, different role; both carry resolution metadata

**Decision:** keep separate. Both carry `source_text`, `resolved_ids`, `resolution_confidence`, and (for `target_entities`) `exactness ∈ {exact, fuzzy, remembered, reference}`.

**Reasoning:** the compiler routes them differently. `target_entities` ("play X by Y") drives exact-entity probes; `mentioned_entities` ("like A Tribe Called Quest") drives anchor lookups. The resolution fields are critical:
- `source_text` lets the compiler fall back to fuzzy lexical match if `resolved_ids` is empty;
- `resolution_confidence` lets fusion weight high-confidence resolutions higher;
- `exactness` distinguishes "play this exact track" (probe) from "I remember a song" (fuzzy fallback) from "like this artist" (anchor reference). The wrong exactness label leads to different failure modes — confusing `remembered` with `exact` causes the probe to miss and the user looks like they're being ignored.

Failed resolutions (`resolved_ids: []`) automatically create an `open_requirements` entry with `kind: requested_artist` (or appropriate kind) and `status: pending`. The extractor doesn't have to do this bookkeeping; the compiler can derive it.

**Open question:** are there sessions where the distinction between `target` and `mentioned` is genuinely ambiguous and the extractor will guess wrong? Intuition says no (the user's grammar usually disambiguates: "play X" vs "like X"), but this has not been measured.

### 2. Aspect feedback as structured lists, not scalar

**Decision:** include `aspect_feedback` (positive/negative facet lists per played track).

**Reasoning:** independent per-turn audits measured a 25% miss rate on this signal across 2122 firing turns. Dropping it on the theory that embedding centroids would absorb the facet structure implicitly is wrong because the compiler also needs to *construct the next dense query* and the next set of `hard_filters`, both of which require symbolic facet awareness ("more melodic, less heavy" → keyword bias + tag filter).

**Open question:** can the facet vocabulary be open (free strings) or must it be closed (enum)? An enum is more reliable but capped; open strings are flexible but extractor-dependent. Recommended starting point: open, lock to an enum after seeing 100 extractor outputs.

### 3. `routing_tags` as feature flags, not enum modes

**Decision:** booleans for `exact_entity_probe`, `hidden_target_search`, `lyric_search`, `feature_articulation`; plus a single `primary_mode` for the dominant intent. A `benchmark_imitation` flag is held in `_debug_flags` (audit-only, not for production routing).

**Reasoning:** turns can fire multiple routes simultaneously. Session `608bc394` (Einaudi) fires both `exact_entity_probe` AND a popularity hard filter. An exclusive enum forces a choice. `benchmark_imitation` — "the system should imitate what the dataset looks like" — bakes devset weirdness into inference state and is not a real user signal; the audit flag lets us still log "this turn looked like dataset-shape imitation" without polluting compiler routing.

**Open question:** is `primary_mode` redundant once we have routing tags? Possibly — but it helps the compiler resolve fusion weights when tags conflict.

### 4. Graded `carryover_policy` — two knobs

**Decision:** two knobs only — `anchors` and `constraints`. There is intentionally no third knob for exclusions, because that would conflate three different concepts (factual played history, explicit user rejection, and the compiler's replay policy) into a single schema rule.

**Reasoning:** `played_track_ids` is a factual ledger and `explicit_rejections` is a user-declared list; whether to use either for retrieval exclusion is a compiler policy choice (the default is yes, but on e.g. a "playlist build" with explicit replay request the compiler can override). Constraints are graded by scope (`session` survives pivots; `active_segment` drops on pivot if `constraints: reset_by_scope`). Anchors carry over per the explicit policy.

**Open question:** the `recent_window` value for anchors is unspecified (window size of what?). Recommended placement: compiler config, not state schema — but worth surfacing during compiler implementation.

### 5. Unified `open_requirements` instead of split `unmet_asks` + `catalog_gaps`

**Decision:** one ledger with `kind` + `status`.

**Reasoning:** lifecycle is identical: a thing was asked → it has a resolution status. Two lists with overlapping items invite drift.

**Open question:** does the merge make the extractor's job harder by forcing it to classify status mid-extraction? Possibly. Alternative: have the extractor emit *unresolved-only* and let the compiler maintain the resolution log across turns.

### 6. `unsupported_signals` as a documented "executable: false" log

**Decision:** include the field even though no current branch can act on it.

**Reasoning:** 5.5% of turns have visual/sonic/cover-art cues. Today they fail silently because no field surfaces them. With the field present and `executable: false`, we can (a) log the failure rate on dev, (b) ship a multimodal branch later that flips `executable: true` for `kind: visual_album_art` via `image-siglip2`.

**Open question:** is putting a field in the schema purely to log a failure mode a smell? Or is it the right place because the schema is the agreed-upon vocabulary?

### 7. `activity_context` as top-level optional with a constraint-override path

**Decision:** keep `activity_context` as a top-level optional field for the common stable case; allow a `constraints[]` entry with `facet: activity_context` and `scope: active_segment` as the **override** path for mid-session shifts.

**Reasoning:**

- 53% of sessions have an explicit activity context, and across the 1000-session scan the context is **stable** in the vast majority of those (rough estimate: 95%+). The mid-session shift case is ~3–5% of sessions.
- A generic `constraints[]` fold makes the extractor responsible for emitting a specific facet-name string (`activity_context`) consistently across turns. If it emits `study` once and `activity_context` next time, compiler routing silently breaks. A reserved top-level slot has no such risk.
- The compiler has clean access without scanning a list for facet-name match. Tag-list query expansion for activity-context tags (`study`, `chill`, `workout`) is the highest-frequency compiler routing decision; making it indirect costs a lot for a small gain.

The compromise — top-level slot **plus** override entry in `constraints[]` — matches the actual distribution: cheap fast path for the stable case, an explicit override for the rare shift case.

**Open question:** is the override path actually disambiguable from the top-level field? If the top-level says `studying` and a later `constraints[]` entry says `dancing` with `scope: active_segment`, the compiler must know to prefer the segment override.

### 8. `mentioned_entities.relation` as an enumerated kind, not free text

**Decision:** small enum of relations (`temporal_before`, `temporal_after`, `same_album`, `same_artist_different_track`, `attribute_shift`, `era_match`, `same_genre_different_artist`).

**Reasoning:** the compiler must execute these against the catalog. Free-text relations can't be reliably compiled into filters. Enum forces the extractor to fail explicitly when something doesn't fit.

**Open question:** is the enum complete enough? The current pass found ~7 kinds; there may be more (e.g. cover-art relations, sonic-similarity relations on unsupported signals).

### 9. `hard_filters.tag_list` allowed for a small whitelist

**Decision:** `tag_list` may appear in `hard_filters` only for a whitelist: `instrumental`, language tags, explicit-content flag. Free-form mood/genre/vibe tags must not be hard-filtered.

**Reasoning:** a blanket ban on tag-list filtering is overcautious. Session `b16f68b0` (study music) shows the user escalating "instrumental" from soft preference to non-negotiable over 7 turns, and the system kept playing vocal tracks because every retrieval treated `instrumental` as soft evidence. If the schema makes `instrumental` *never* filterable, that user is structurally underserved.

The whitelist isolates clean cases:
- `instrumental` — binary, well-defined in the catalog tag space.
- Language tags — clean, finite vocabulary.
- Explicit-content flag — binary.

Fuzzy mood/genre tags (`chill`, `dark`, `smooth`, `melancholic`) stay soft because they're noisy: a track tagged `chill` may or may not be what *this* user means by chill. Soft handling via dense + tag-overlap scoring is the right move there.

**Open question:** is the whitelist complete? Other candidates worth considering: `live` (binary), specific clean genre tags like `classical` (well-defined enough?), decade tags if present. Worth a 30-minute audit of the catalog's tag distribution to pick the whitelist deliberately.

---

## Validation evidence — what we have vs what we need

What the iteration history claim does and does not prove:

### What "1000/1000 schema-covered" actually means

It means: for every test session, **at least one regex pattern in our scanner fires** AND that pattern maps to a slot in the v3-candidate schema. This is **pattern coverage**, not extractor reliability and not retrieval lift. It tells us the schema has *somewhere to put* every signal we know how to look for. It does not tell us:

- whether an LLM extractor can populate those fields correctly,
- whether the compiler can route them into queries that improve retrieval,
- whether the regex scanner itself missed signal types entirely.

The 4 risk patterns (user_dissatisfaction 4.1%, language_other 3.2%, emotional_state 2.5%, goal_complete 0.5%) all co-occurred with covered patterns and did not demand new top-level slots. That's a meaningful negative result, but it is still pattern-level.

### Hand-authored gold states — not yet committed

The v3 candidate has not yet been validated against committed hand-authored gold states. Drafts exist in conversation logs but are not in this package and do not yet reflect the full v3-candidate field set (entity resolution fields, scoped constraints, `explicit_rejections`, restricted `hard_filters`).

**Uncommitted gold states are the blocker for promoting the schema from "candidate" to v3.**

### Required gold-state coverage

To clear the validation gate, the package needs gold states covering at least the following session archetypes:

- Pure-accept (baseline playlist build with no rejections).
- Hidden-target search (close-but-not-it across multiple turns).
- Pivot mid-session (explicit "actually, switch to X").
- Rotating per-turn intent within a stable session goal.
- Meta-constraint escalation ("more new artists please" intensifying turn over turn).
- `unsupported_signals` — visual/cover-art recall.
- `target_entities` with `exactness: remembered` or `fuzzy` that fails resolution (`resolved_ids: []`) — testing the failed-resolution → `open_requirements` flow.
- `feature_articulation` — session-E examples (rare at 3.6%, but the routing tag exists).
- Long-range callback / anchor-poisoning failure — tests `explicit_rejections` population from "not X" language across multiple turns.
- Exact-mismatch cases — sessions where the user names a track and the catalog has a different track of the same name (testing `exactness: exact` with low `resolution_confidence`).

### Extractor agreement gate

Once gold states are committed, the extractor prompt is judged by **field-level agreement** against the committed gold:

| Field | Pass threshold | Why this threshold |
|---|---:|---|
| `track_feedback.overall_sentiment` | ≥85% | Universal field; mistakes here cascade everywhere |
| `target_entities.exactness` | ≥80% | Determines compiler routing; wrong routing = silent miss |
| `target_entities.resolved_ids` (when extractor resolves) | ≥75% | Lower bar because compiler can fall back to lexical match |
| `mentioned_entities` (presence) | ≥80% | High prevalence; missing it kills artist-anchor branch |
| `constraints` (facet + scope + hardness) | ≥75% | Three-tuple agreement is hard; loosened bar |
| `hard_filters` (when explicit user signal) | ≥85% | Wrong filters cause hard misses, not soft drift |
| `routing_tags` (any) | ≥80% | Per-tag F1; routing errors are silent |
| `explicit_rejections` (presence on relevant turns) | ≥80% | Directly maps to the `user_dissatisfaction` failure mode |
| `open_requirements` | ≥70% | Most-derived field; lower bar acceptable |
| `unsupported_signals` | informational only | Too rare for a hard threshold; track presence rate |

These thresholds are proposed, not measured. They should be sanity-checked against the first gold-state run.

---

## Open questions

In rough priority order:

1. **Is v3 too big for reliable extraction?** Median session populates 5 of 12 top-level slots. p95 populates 9. Extractor prompts at this size often regress on small models. Iteration 1 deliberately uses the v0+ subset to test this before committing to v3.

2. **`aspect_feedback` vocabulary: open or closed?** Closed enum (mood, instrumentation, vocal_style, tempo, era, lyrics) is more reliable but caps expressiveness. Open strings handle long-tail but make compiler routing harder. Recommended: start open, lock to an enum after seeing ~100 extractor outputs.

3. **`primary_mode` after `routing_tags` — redundant or load-bearing?** It helps the compiler resolve fusion weights when multiple tags fire. But it's also one more thing the extractor must agree with the tags on. Gated on extractor agreement: keep if ≥80%, drop if <70%.

4. **`segments` granularity — turn-level or intent-shift level?** Today v3 says new segment on intent shift. Alternative: each turn implicitly its own segment with explicit `extends_prior` flag. Cleaner for the extractor; more verbose state.

5. **`carryover_policy` defaults — encoded in the schema or in the compiler?** v3 declares carryover at the state level. Alternative: the compiler has fixed defaults (anchors: recent_window, stable: keep) and the state only emits *overrides*.

6. **`unsupported_signals` — keep or drop?** The argument for keep: makes the failure mode visible and forward-compatible. The argument against: extractor work for a field nothing can act on today. Current position: keep.

7. **`mentioned_entities.relation` enum completeness.** Are there common relations the current 7-value enum misses? Especially around lyric content, cover art, music video, and live performance references.

8. **Is `track_feedback.unmet_ask` (per-track) double-bookkeeping vs `open_requirements`?** v3 has both. Per-track unmet asks are tied to a specific recommendation moment; `open_requirements` is the rolling ledger. Could collapse to one if the overhead matters.

9. **Compiler-level: should we pursue the full v3 extractor before validating the embedding-centroid hypothesis?** The Phase 1 multimodal branches (CF-BPR, CLAP-audio, lyrics-embedding) might lift Hit@1000 enough that the state-extraction layer is less critical. A 1-day notebook validation on dev could redirect priorities. **Recommended: do this first.** This is also why [`iteration_1_minimal_schema.md`](iteration_1_minimal_schema.md) exists.

---

## Recommended next concrete steps

The hard rule: **commit gold states for the v0+ schema and measure end-to-end retrieval before adding any new schema fields.** Pattern coverage at 1000 sessions does not give permission to skip extractor-reliability evidence.

Recommended sequence:

1. **Start with iteration 1** ([`iteration_1_minimal_schema.md`](iteration_1_minimal_schema.md)) rather than the full v3 candidate. v0+ is the minimum that can plausibly produce a useful retrieval measurement.
2. **Commit gold states under v0+** covering the archetypes listed above. The full v3 set can wait until iteration 1 lands measurable results.
3. **Run the extractor + compiler end-to-end on dev** using v0+ and report against diagnostic gates (per-branch Hit@1000, no rewrite-style collapse, coverage delta vs offline RRF).
4. **If v0+ measures well**, expand to v3 fields one at a time, each gated on a measured failure mode that demands it. Don't add `aspect_feedback`, `segments + carryover_policy`, `open_requirements`, `unsupported_signals`, or finer routing tags until a v0+ failure says so.
5. **In parallel**, run the embedding-centroid validation in a notebook (open question 9) — it can redirect priorities away from extraction work entirely if multimodal branches alone close the Hit@1000 gap.

Once measured agreement on the v3 candidate passes the field-level gates and retrieval lifts over the current ceiling, the schema can be promoted from "v3 candidate" to "v3" and the package status moves from `analyzed` to `done`.
