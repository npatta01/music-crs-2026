# Iteration 1: Minimal v0+ Schema for First Retrieval Measurement

Status: proposed
Date: 2026-05-24
Companion to: [`README.md`](README.md) (synthesis), [`final_merged_schema.md`](final_merged_schema.md) (v3 candidate north-star), [`../gen_crs2025_tutorial_music_crs/artifacts/detailed_literature_review.md`](../gen_crs2025_tutorial_music_crs/artifacts/detailed_literature_review.md) (Section 6.1 ConversationState v0 from the literature review)

> **Schema label note:** v0+ is the v3 candidate cut down to the minimum that can plausibly produce a useful first retrieval measurement. It drops most v3 fields, keeps the ones with the strongest literature support (`intent_mode`, tag-level rejections, `referenced_track_ids`), and uses 3-value enums for sentiment instead of scalars to avoid false precision. Iteration 1 commits to a fixed 4-branch compiler (BM25 + dense text + CLAP audio + CF-BPR).

## Why minimal, why now

The schema design pass has produced a defensible 16-field v3 candidate, validated against 1000 sessions of pattern coverage. The pattern-coverage work proves the schema is *populatable*. It does not prove the schema is *useful*.

We have produced **zero retrieval measurements** so far. Every claim about Hit@1000 lift, NDCG@20 gain, or the Fugazi failure-mode fix is a hypothesis grounded in session analysis, not a measured result. Before scaling the schema, the extractor, and the compiler all at once, we need at least one end-to-end measurement to know which fields are pulling weight and which are speculation.

The right move for iteration 1 is the smallest schema that can plausibly beat today's best dev numbers (`NDCG@20 0.1092, Hit@1000 0.5561` from the best LLM rewrite; `Hit@1000 0.7210` from the offline RRF hybrid that has no extraction layer). Anything beyond that risks investing in fields whose contribution we cannot attribute.

## The v0+ schema (7 LLM-extracted fields)

```yaml
# ---------- mechanical (no LLM) ----------
played_track_ids: [<track_id ordered by turn>]
user_id: <uuid>
user_profile: <dict>

# ---------- LLM-extracted, 7 fields ----------
turn_intent: <free text>
  # The active ask, naturally phrased. MUST preserve any artist/track/album names
  # the user named in the latest turn — these are the anchor entities the rewrite
  # wave kept losing.

intent_mode: open_explore | refinement | pivot | playlist_build
  # 4-value enum. Both the Gen-CRS tutorial example and the literature review's
  # ConversationState v0 (§6.1) keep this as the foundational field for
  # retrieval strategy selection. Compiler uses it to pick fusion weights and
  # decide whether to carry over anchors from prior turns (refinement: yes;
  # pivot: no; playlist_build: yes, heavier; open_explore: less anchor weight).

track_feedback:
  - track_id: <track_id>
    overall_sentiment: -1 | 0 | 1   # 3-value enum, not scalar; avoids false precision
    role: accepted | rejected | seed   # 3-value enum; no near_miss/confirmed_target/wrong_item
  # role and sentiment are partly redundant by design — keep both for symmetry
  # with mentioned_entities (which has no role) and for extractor cross-checking.

referenced_track_ids: [<played_track_id>, ...]
  # When the user says "more like the second one" or "that previous track",
  # resolve to the actual played track_id(s). May be empty.
  # Literature review §6.1 calls these out as anchors.referenced_prior_track_ids.

mentioned_entities:
  - type: artist | album | track | tag
    value: <string>
    sentiment: -1 | 0 | 1   # 3-value enum, not scalar
  # Entities the user named or referenced ("like ATCQ", "earlier Radiohead",
  # "remember that song called Bohemian Rhapsody"). No exactness, no resolved_ids,
  # no relation, no first_turn. Compiler does its own fuzzy match against catalog.

hard_filters:
  - field: release_date           # ONLY release_date in v0+
    op: "<" | ">" | "between"
    value: ...
  # Other catalog fields (popularity, artist_id, tag whitelist) deferred to v1.

explicit_rejections:
  - kind: artist | track | tag    # album/attribute deferred to v1
    value: <string>
    source_turn: <int>
  # Populated when the user says "not X", "stop playing X", "different from X",
  # "too heavy", "too gloomy". Critical for the anchor-poisoning failure mode
  # (~4% of sessions where the system keeps recommending a rejected artist)
  # AND for tag-level negatives ("too heavy" — the Gen-CRS tutorial example
  # uses these explicitly).
```

7 LLM-extracted fields, all flat. No nesting beyond what's required for list entries.

## What v0+ deliberately gives up (vs v3 candidate)

| v3 field | What v0+ does instead | What we lose |
|---|---|---|
| `target_entities` vs `mentioned_entities` split | One `mentioned_entities` list | Exact-entity probe routing for "play X by Y" — but compiler can still hit BM25 hard on named entities |
| `routing_tags` (5 booleans) | Just `intent_mode` (4-value enum) | Per-route compiler behaviors (hidden_target negative-identity exclusion, lyric branch boost, visual branch logging). `intent_mode` covers the most common refinement-vs-pivot distinction but misses the finer route-level signals. |
| `primary_mode` | Merged with `intent_mode` | (See above — v0+ collapses primary_mode + the most useful routing tag into one enum.) |
| `aspect_feedback` (positive/negative facets per track) | Scalar sentiment only | "Melody yes, lyrics no" dimensional reactions get lossy |
| `segments` + `carryover_policy` | Compiler uses `intent_mode` to decide carryover (refinement → keep, pivot → reset) + recency window | Multi-pivot sessions where each segment needs separate anchor sets |
| `open_requirements` ledger | None | Catalog-gap and unmet-ask tracking; re-recommending unavailable artists |
| `unsupported_signals` | None | Visual/cover-art recall logging (~5% prevalence) |
| `process_constraints` (novelty_pressure, exploration_policy) | None — replaced by `explicit_rejections.kind=artist` | Soft diversification ("more new artists please" before they say "stop Morphine") |
| `activity_context` (structured) | Captured inside `turn_intent` text | Structured routing to activity tags (study, chill, workout) |
| `constraints` (era, genre, instrumentation as structured) | Captured inside `turn_intent` text | The compiler can't apply non-temporal constraints as structured filters |
| Entity `exactness` (exact/fuzzy/remembered/reference) | None — compiler does string match | "Drop Coupes" exact-title lookup vs "the one that goes 'down in a hole'" fuzzy lyric path: both get the same retrieval treatment |
| Entity `resolved_ids` | None — compiler does its own resolution | Slight extra compiler work; no information loss |
| `evidence.field → source_turn_numbers` (lit-review §6.1) | None — provenance not tracked | Debug-only, not retrieval. Can add later for trace logging. |

## Why these specific fields (vs a stricter 5-field minimum)

Three of the seven fields (`intent_mode`, `explicit_rejections.kind: tag`, `referenced_track_ids`) are additions on top of an even-more-minimal 5-field draft. They were added after cross-checking against the Gen-CRS tutorial HTML example and the literature review's own ConversationState v0 (§6.1):

| Field | Source pushing for it | Rationale |
|---|---|---|
| `intent_mode` (enum) | Lit review §6.1, RA-Rec, tutorial example | Both keep it as the foundational field for retrieval strategy selection. Dropping it forces the compiler to infer mode from `turn_intent` text, which is brittle. One enum field is cheap. |
| `explicit_rejections.kind: tag` | Tutorial HTML example, lit review §6.1 (`disliked_tags`) | "Too heavy", "too gloomy" are the tutorial's canonical negative anchors. An artist/track-only enum misses these completely. |
| `referenced_track_ids` | Lit review §6.1 (`anchors.referenced_prior_track_ids`) | Resolves "more like the second one" to a specific played track_id. Low prevalence (~5%) but the literature treats it as a v0 essential. |

## Design notes on the field shapes

A few specific choices worth flagging for the implementer:

- **`mentioned_entities.type` includes `track`.** Track mentions in history ("remember that song called Bohemian Rhapsody") are common and cheap to preserve. Cutting to `artist | album | tag` would miss them.
- **Sentiment is a 3-value enum (`-1 | 0 | 1`), not a scalar.** LLM extractors don't reliably distinguish 0.6 from 0.7; they do reliably distinguish `-1` from `0` from `1`. Symbolic precision is more useful than false numeric precision. The compiler can map enum → continuous weight if it needs one.
- **`track_feedback` has both `role` and `overall_sentiment`.** Partly redundant on purpose — the redundancy lets the extractor and validator cross-check each other.
- **Compiler is a fixed 4-branch set in iteration 1**: BM25 + dense text + CLAP audio + CF-BPR. Lyrics, attributes, and image (SigLIP) branches are deferred to v1. Keeping the first run boring makes per-branch ablation interpretable.

**Estimated coverage from frequency data (N=1000 patterns scan):**

| Pattern | Prevalence | v0+ handles? |
|---|---:|---|
| Anchor-by-reference ("like X") | ~70% | **Yes** via `mentioned_entities` |
| Temporal filtering | ~44% | **Yes** via `hard_filters` (release_date only) |
| Activity context | 53% | Partial — goes into `turn_intent` only |
| New-artists / diversification | 40% | Partial — extreme case via `explicit_rejections.kind=artist`; soft case missed |
| Tag-level negatives ("too heavy") | ~18% | **Yes** via `explicit_rejections.kind=tag` (added in v0+) |
| Pivot mid-session | 11% | **Yes** via `intent_mode=pivot` (added in v0+) — compiler drops prior anchors |
| "More like the second one" reference | ~5% | **Yes** via `referenced_track_ids` (added in v0+) |
| Hidden-target search | 29% | **No** — no routing tag; close-but-not-it tracks are treated as ordinary positives |
| Catalog gap awareness | 17% | **No** — extractor doesn't surface, compiler doesn't pre-filter |
| Visual/cover-art recall | ~5% | **No** — silent failure |
| User dissatisfaction failure | 4% | **Yes** via `explicit_rejections` |

**Rough estimate:** v0+ cleanly handles ~80-85% of sessions, with degraded but acceptable behavior on 5-10%, and silent failures on 5-10%. The silent-failure rate is the same as today's baseline. The lift from v0 to v0+ (3 added fields) closes the pivot, tag-negative, and "second one" gaps for ~30% of sessions combined.

## Why v0+ is still expected to beat current best

The current best dev numbers come from:
- BM25 + tag_list (`NDCG@20 0.0970, Hit@1000 0.6311`) — no extraction, no anchor preservation
- Dense Qwen 8B (`NDCG@20 0.1025, Hit@1000 0.6934`) — same
- Offline RRF hybrid (`NDCG@20 0.1072, Hit@1000 0.7210`) — same
- Best LLM rewrite (`NDCG@20 0.1092, Hit@1000 0.5561`) — single flat rewrite, *drops* anchor entities

v0+ differs structurally from the rewrite wave in four ways that should matter:

1. **Anchor preservation.** `turn_intent` is required to preserve named entities; the prompt enforces it. The rewrite wave loses these.
2. **Audio anchoring (CLAP).** v0+ has enough state (`track_feedback` + `referenced_track_ids` + `played_track_ids`) for the compiler to compute an audio centroid from accepted-anchor tracks and run a CLAP nearest-neighbor branch. (Lyrics, attributes, image branches are deferred to v1 to keep iteration 1 boring and measurable.)
3. **CF-BPR personalization.** `user_id` + the user CF-BPR embedding (already in dataset, currently unused) lets the compiler add a per-user collaborative-filtering branch.
4. **Pivot handling.** `intent_mode=pivot` lets the compiler drop prior-segment anchors when the user breaks direction (~11% of sessions). The rewrite wave just keeps re-injecting them.

If these four changes lift Hit@1000 toward or above the current RRF ceiling (0.7210), and per-branch ablation shows CLAP and CF-BPR pulling unique coverage, v0+ has earned itself.

## The iteration 1 plan

1. **Lock the v0+ schema** at the 7 LLM-extracted fields above. No additions until v0+ is measured end-to-end.
2. **Extractor**: re-use the existing prompt scaffolding, cut down to v0+ keys, keep the few-shot examples from the expanded smoke test. Validate on 5 hand-corrected gold states (much cheaper than 40 under v3).
3. **Compiler v0+** (~60 lines, fixed 4-branch set — keep iteration 1 boring and measurable):
   - **Branch 1 (BM25):** from `turn_intent` + positive-anchor entity terms (from `mentioned_entities` and `track_feedback` with sentiment=1)
   - **Branch 2 (dense text, Qwen):** from `turn_intent`
   - **Branch 3 (CLAP audio-NN):** seeded from positive-anchor track embeddings (high-sentiment `track_feedback` + `referenced_track_ids`); when `intent_mode=pivot`, drop prior-segment anchors
   - **Branch 4 (CF-BPR user×track):** from `user_id`
   - **RRF fusion** (k=60); weights adjusted by `intent_mode` (heavier anchor weight in `refinement` / `playlist_build`, lighter in `pivot` / `open_explore`)
   - **Post-filter:** exclude `played_track_ids`; exclude tracks by `explicit_rejections.kind=artist`; demote tracks whose `tag_list` overlaps `explicit_rejections.kind=tag`
   - **Hard filters:** apply `hard_filters` (release_date only)
   - **Deferred to v1:** lyrics-dense branch, attributes-dense branch, image (SigLIP) branch. These are easy to add later but kept out of iteration 1 to make the first run interpretable.

4. **Eval — diagnostic gates, not single-number pass/fail:**
   - **Hit@1000 baseline check:** does v0+ preserve or beat the offline RRF union ceiling (`0.7210`)? Landing at `0.70` with clear branch lift is still useful evidence.
   - **No rewrite-style collapse:** does Hit@1000 stay above the best rewrite's `0.5561`? This is the floor.
   - **Branch contribution:** per-branch Hit@1000 (BM25, dense text, CLAP, CF-BPR independently); did the new branches (CLAP, CF-BPR) actually pull weight, or is fusion still BM25+dense?
   - **Coverage delta:** what fraction of gold tracks does v0+ find that offline RRF did not? Per-branch unique contributions matter.
   - **NDCG@20 target:** ≥ `0.1092` (best rewrite without losing pool depth).
   - **Per-pattern slice:** how does v0+ perform on pivot turns specifically (where `intent_mode=pivot` and `referenced_track_ids` matter most)?

5. **Decision rubric:**
   - If Hit@1000 meets ceiling AND branch ablation shows new branches contributing: ship v0+ to blindset_A, then iterate to v1 (adding routing_tags + segments + aspect_feedback) on devset.
   - If Hit@1000 lifts but branch ablation shows only BM25+dense pulling weight: investigate embedding quality and fusion config before adding schema fields.
   - If Hit@1000 regresses: **diagnose by branch ablation** before concluding the cause. Failure could be any of: schema (wrong fields), extractor (wrong values), compiler (wrong routing), embeddings (broken centroids), or fusion (bad weights). Per-branch and per-pattern slicing tells us which.

## What v0+ explicitly does not do

These are deferred to v1+ pending measured evidence:

- No fine-grained routing tags (only the 4-way `intent_mode` enum). Hidden-target search, lyric search, feature articulation, and visual search all collapse under `refinement` or `open_explore`.
- No multi-segment carryover model. Compiler uses `intent_mode` as a single switch; sessions with two distinct pivots (~3-5% of sessions) get the second segment's behavior only.
- No catalog-gap pre-filtering.
- No diversification beyond hard exclusion.
- No lyrics, attributes, or image (SigLIP) branches in the compiler — only BM25 + dense text + CLAP audio + CF-BPR for iteration 1.
- No reranker (let RRF do the work; add reranker only if NDCG@20 ranking is the bottleneck).
- No `evidence.field → source_turns` provenance tracking (lit-review §6.1 includes it; useful for debugging, not for retrieval).
- No aspect-level (positive/negative facet) feedback per track — scalar (3-value enum) only.

## Open question for the team

The honest tension is whether `track_feedback.role: rejected` is sufficient for the Fugazi case (anchor poisoning) or whether we need full `explicit_rejections` even in v0+. I included both above (`role` enum AND `explicit_rejections`) because they encode different things:

- `role: rejected` means "this played track is a negative anchor"
- `explicit_rejections.kind=artist` means "exclude all tracks by this named artist, even ones not yet played"

The Fugazi session shows the second pattern: the user says "not Fugazi" referring to a future recommendation, not the specific track that just played. v0+ needs both, or it fails the case.

If we cut `explicit_rejections` from v0+, we lose the only place that catches the 4.4% `user_dissatisfaction` mode. I'd keep it; it's one field.

## What this doc commits us to

- Schema work pauses here until v0+ measures end-to-end.
- The v3 candidate ([`final_merged_schema.md`](final_merged_schema.md)) remains the north star but is not implemented in iteration 1.
- Any new field proposal must reference a measured v0+ failure that demands it.

## Recommendation

**Go simpler. Build v0+, measure, then decide.**

The full v3 candidate is good design work and shouldn't be thrown away — but shipping it before any retrieval measurement is the kind of over-investment that kills iteration speed on ML projects. If v0+'s 7 fields lift Hit@1000 over the current ceiling, we'll have evidence-driven priorities for which v3 fields to add next. If they don't, we'll have learned something more important: the bottleneck is the compiler or the embedding branches, not the schema.

The 1-week gap between locking the v3 schema and shipping iteration 1 is the kind of cost we should avoid. Lock v0+ today; ship something measurable this week.

The "+" in v0+ represents the three small additions surfaced by cross-checking against the Gen-CRS tutorial and the literature review's own ConversationState v0 (§6.1): `intent_mode`, tag-level rejections, and `referenced_track_ids`. They're cheap (one enum, one enum extension, one ID list), well-supported in the literature, and close gaps that a strict 5-field v0 would have left visibly broken.
