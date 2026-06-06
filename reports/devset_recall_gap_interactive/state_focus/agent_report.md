# Music CRS State Focus Report

Generated: 2026-06-06 16:42:05 UTC
TID: `v0plus_compiler_all_retrievers_devset`

## Snapshot Contract

- Status: Baseline state-audit snapshot, not a permanent schema spec.
- Applies to: v0plus_compiler_all_retrievers_devset devset trace, predictions, organizer metadata, and Hugging Face conversation rows at generation time.
- Valid until: Rerun after changing the extractor prompt/schema, resolver, routing profile, ranker features, finalization rules, catalog/index, or evaluation split.
- How to use: Use ideal states and replay packs as small-batch experiments. Once a fix lands, regenerate this report and compare stale-state, novelty-anchor, temporal, rejection, union@20, and final@20 slices.

## Technical Summary

- Final@20 is 27.4%; union@20 is 47.7%; union@100 is 66.2%.
- The highest-value state work is role-typed, current-turn entity state and state-to-retriever routing.
- Routing tags fire 9,094 times, but `routing_boost` is empty, so routing is currently a P0 config/consumption gap.
- Treat union@20 as the state/retriever gap boundary; use union@100 as the near-miss/ranker workbench.

## Work Queue

### P0 Add role-typed current-turn entity state

- Why: 3807 turns have stale positive artist/track state; 3157 have a novelty cue while prior artists remain anchored.
- Change: Change extractor output or resolver annotation so named entities are seed, satisfied, contrast, history, or rejected. Feed only seed/current-positive entities into anchors and discography.
- Validation: State QA: stale positive artist/track rate should drop. Eval: improve new-artist mid-conversation union@20/100 without hurting exact named-track turns.

### P0 Fix inert routing: configure routing_boost and retrieval profiles

- Why: Mid-conversation new-artist turns are 47.2% of turns with final@20 10.0%; routing tags fire 9,094 times but config routing_boost is empty.
- Change: For novelty/diversify turns, downweight prior-artist centroid/discography and upweight tag/metadata/popularity/CF candidate generation. For continuation turns, do the opposite.
- Validation: Track union@20 and union@100 by new-artist vs continuation. Success means candidate generation rises for new-artist turns before final ranker tuning.

### P0 Prototype album-affinity and artist-recency features

- Why: Primary-album continuation is 2,023 turns with union@20 88.8% but final@20 51.7%; the candidate is often nearby but ranked wrong.
- Change: Add same_album_recent, artist_recency, and candidate_artist_role features to a lightweight scorer over union@100/200.
- Validation: Continuation NDCG@20 and same-album final@20 improve; new-artist and exact named-track slices are guardrails.

### P0 Build novelty candidate-generation profiles

- Why: Mid-conversation new-artist union@20 is 19.4%; novelty-cue + new-artist union@20 is 18.0%.
- Change: For novelty/diversify turns, add genre/era-conditioned popularity, user-CF/culture affinity, and tag-first dense/metadata retrieval while suppressing stale prior-artist pools.
- Validation: Raise union@20 and union@100 for mid-conversation new-artist and novelty-cue slices before evaluating final ranker lift.

### P1 Add a release-year guardrail

- Why: 634 turns have release-year state that excludes the GT catalog year.
- Change: Represent era as stylistic cue vs release-date constraint; keep release-year evidence soft unless the user explicitly asks for a date bound.
- Validation: Audit all release-range-excludes-GT turns and run no-year-penalty / soft-year-penalty ablations on final@20 and union@20.

### P1 Make rejections impossible to leak

- Why: 159 turns show final top-20 leakage under this name/id heuristic.
- Change: Add post-final assertions for rejected tracks/artists and test multi-artist track handling.
- Validation: Leak count should be zero on devset trace replays; then verify hit@20 does not regress materially.

### P1 Train or calibrate ranker features that consume state

- Why: Overall union@20 is 47.7% but final@20 is 27.4%; state can tell the ranker when diversity, album affinity, popularity, or exactness should matter.
- Change: Candidate features: branch ranks, candidate_artist_role, is_new_artist, same_album_recent, release_distance, positive_tag_overlap, rejected_flag, popularity, and routing tags.
- Validation: Session-grouped CV over union@100/200 should improve NDCG@20/Hit@20 and report separate new-artist, continuation, LL, and late-turn slices.

## Task Modes

### Exact named track

- Turns: 92
- Final@20: 100.0%
- Union@20: 100.0%
- Union@100: 100.0%
- Read: This should be nearly solved; misses here are precision/state-routing bugs.

### Continuation: same artist

- Turns: 3,223
- Final@20: 46.3%
- Union@20: 83.3%
- Union@100: 93.6%
- Read: Mostly a state-use/ranking problem: the relevant artist is known, but the right track is not chosen.

### New artist mid-conversation

- Turns: 3,777
- Final@20: 10.0%
- Union@20: 19.4%
- Union@100: 44.9%
- Read: The main state/retriever problem: the system must convert state constraints into new-artist candidates.

### Cold open

- Turns: 1,000
- Final@20: 32.0%
- Union@20: 39.6%
- Union@100: 58.6%
- Read: No session state exists yet, so popularity/canonicality and profile priors matter more than state repair.


## State Scorecard

### Positive tag extraction

- Current evidence: 7,720 turns have positive_tags; 76.9% overlap at least one GT catalog tag.
- Decision: Do not make tag extraction the first major state rewrite. Use tags better in ranker/router features.

### Entity role and recency

- Current evidence: 3,807 turns have positive artist/track state not present in the current user turn; 3,157 novelty turns keep prior anchors.
- Decision: P0. Add seed/satisfied/contrast/history/rejected roles and decay history before anchors/discography.

### Release-year state

- Current evidence: 2,164 turns set a release range; 634 exclude the GT release year.
- Decision: P1. Split stylistic era from hard release-date bounds; run no-year and soft-year ablations.

### P0 routing config gap

- Current evidence: Trace routing tags fire 9,094 times (feature_articulation=6,748, exact_entity_probe=1,605, hidden_target_search=391), but config routing_boost is empty.
- Decision: P0. Treat this as a config/consumption bug: wire tags into retriever profile weights before adding new retrievers.

### Rejection enforcement

- Current evidence: 995 turns have rejection state; 97 strict-ID leak turns plus 62 additional name-only audit turns produce 159 broad final top-20 leak flags.
- Decision: P1. Add deterministic post-final assertions and multi-artist rejection tests.


## State Schema Audit

### turn_intent

- Evidence: n=8,000 (100.0%); final@20=27.4%; union@20=47.7%; union@100=66.2%. The normalized intent text names the GT artist on 2,166 turns.
- Failure read: Keep, but do not rely on free text alone. It does not encode whether an entity is the current target, already satisfied, contrast, or old history.
- Decision: Keep as extractor QA/debug text; derive structured target mode and entity roles from it.
- Validation: After rerun, compare intent text to role labels on sampled novelty, continuation, and exact-entity turns.

### mentioned_entities

- Evidence: n=6,124 (76.5%); final@20=31.7%; union@20=53.7%; union@100=70.9%. Stale positive artist/track evidence appears on 3,807 turns; novelty+prior-anchor conflicts appear on 3,157 turns.
- Failure read: This is the main confusing field: positive sentiment is carrying too much meaning and downstream code treats old positives like current anchors.
- Decision: Split into role-typed entities: seed/current_target, satisfied, contrast, history/context, rejected, with source_turn and recency.
- Validation: Primary state QA metric: stale positive artist/track rate and novelty-prior-anchor conflict count should fall without hurting named-artist union@20.

### track_feedback

- Evidence: n=6,978 (87.2%); final@20=26.7%; union@20=48.8%; union@100=67.3%. Observed feedback roles: accepted:22,147, neutral:2,505, seed:1,155, rejected:887.
- Failure read: Useful but underspecified: feedback can mean keep exploring around this track, move on after a satisfied track, or avoid a disliked track.
- Decision: Keep, but align feedback roles with entity roles and expose a candidate-level recency/album/artist feature.
- Validation: Sample feedback turns and assert accepted/satisfied tracks do not automatically become current retrieval seeds on novelty turns.

### referenced_track_ids

- Evidence: n=301 (3.8%); final@20=21.9%; union@20=43.5%; union@100=61.8%
- Failure read: Low-coverage but precise. It is not the broad recall gap, but it should be exact when present.
- Decision: Keep as a surgical exact-reference field; do not make it a P0 schema rewrite.
- Validation: For turns with referenced IDs, assert exact-reference candidates are protected before RRF/finalization.

### positive_tags

- Evidence: n=7,720 (96.5%); final@20=26.0%; union@20=46.7%; union@100=65.7%. When tags are present, 76.9% overlap at least one GT catalog tag; the overlap slice itself is n=5,937 (74.2%); final@20=28.7%; union@20=49.0%; union@100=68.7%.
- Failure read: Tag extraction is not the clearest extractor bug. The larger issue is that tags do not overcome stale anchors or weak novelty routing.
- Decision: Keep tags; canonicalize/map them and use candidate-level overlap/compatibility features instead of adding more raw tag fields.
- Validation: Measure positive-tag-overlap turns by union@20 and final@20 after routing/ranker changes, not just extractor precision.

### release_year_range + hard_filters

- Evidence: Release range present: n=2,164 (27.1%); final@20=21.6%; union@20=40.8%; union@100=63.7%; range excludes GT on 634 turns. Hard filters present: n=1 (0.0%); final@20=0.0%; union@20=0.0%; union@100=0.0%; types: release_date:1.
- Failure read: The state confuses stylistic era with literal release-date constraints. This can suppress correct targets even when the user meant an aesthetic.
- Decision: Collapse into one temporal_constraint object with kind=release_date/style_era/reference_era and strength=hard/soft.
- Validation: Run no-year and soft-year ablations; exact/HH turns are guardrails, release-range-excludes-GT should shrink.

### explicit_rejections

- Evidence: n=995 (12.4%); final@20=15.2%; union@20=39.6%; union@100=56.6%. Strict-ID leak lower bound: 97; broad name audit: 159.
- Failure read: Extraction is probably good enough to detect many rejections; the bigger bug is enforcement and ID/name normalization.
- Decision: Keep, but normalize to rejected_track_ids, rejected_artist_ids, and verified name aliases before finalization.
- Validation: Post-final replay should produce zero strict rejection leaks; hand-label name-only flags before treating them as defects.

### routing_tags + intent_mode + process_constraints

- Evidence: Routing tags present: n=7,528 (94.1%); final@20=28.0%; union@20=48.7%; union@100=67.2%; total active tags=9,094; routing_boost is empty.
- Evidence detail: Process constraints: n=8,000 (100.0%); final@20=27.4%; union@20=47.7%; union@100=66.2%; policies: diversify_artists:4,728, balanced:2,188, exploit:1,026, diversify_albums:58.
- Failure read: The extractor creates useful mode hints, but they are fragmented and not consumed by weighted retrieval.
- Decision: Collapse downstream into a derived retrieval_profile: continuation, novelty, exact_probe, feature_search, hidden_target_search.
- Validation: Populate routing_boost/profiles and report union@20/100 by routing tag and by continuation vs new-artist mode.

### lyrical_theme

- Evidence: n=96 (1.2%); final@20=57.3%; union@20=70.8%; union@100=80.2%
- Failure read: Can matter for lyrics/theme tasks, but it is not the broad state failure in the current trace.
- Decision: Keep as a specialized field; route only to lyric/theme retrieval or a candidate text feature.
- Validation: Evaluate B/category lyric/theme slices separately so this field is not overfit into general retrieval.

### conversation_goal + user_profile

- Evidence: n=8,000 (100.0%); final@20=27.4%; union@20=47.7%; union@100=66.2%.
- Evidence detail: Metadata is session-level and currently not consumed by retrieval/ranking; preferred_musical_culture and listener_goal are the most plausible additions.
- Evidence detail: Blind-A raw rows expose these fields, but the current blindset batch input drops them before retrieval.
- Failure read: Missing pipeline context, not a state extraction bug. Raw constants do not rank candidates within a turn unless converted to candidate-varying affinity.
- Decision: Add to the state/ranker input as context, but derive candidate-level features: culture-conditioned popularity, goal-text compatibility, user-CF affinity.
- Validation: Session-grouped CV. Raw demographic/session features are a guardrail baseline; candidate-varying affinity must beat it.


## Schema Change Queue

### P0 / Roleless entity carryover / Split

- Change: Replace a single positive entity interpretation with role, source_turn, recency, and anchor_strength.
- Why it makes sense: 3,807 stale positive-entity turns and 3,157 novelty-anchor conflicts are direct state-shape failures.
- Validation: Extractor rerun should reduce stale-current positives; retrieval should improve new-artist union@20/100 without named-artist regression.

### P0 / Same-artist vs new-artist mode ambiguity / Add derived field

- Change: Add target_artist_mode: same_artist, new_artist, any_artist, or unknown, derived from cues plus history.
- Why it makes sense: Continuation and mid-conversation new-artist turns have different hit profiles; new-artist union@20 is 19.4%, so mode should change retriever profile before ranking.
- Validation: Track target_artist_mode confusion matrix against GT artist history; route-specific union@20/100 must move.

### P0 / Extracted routing is not consumed / Collapse downstream view

- Change: Collapse routing_tags, intent_mode, and process policy into a retrieval_profile consumed by branch weights.
- Why it makes sense: Routing tags fire 9,094 times while routing_boost is empty.
- Validation: Run routing profile A/B and report exact_probe, hidden_target_search, feature_articulation, continuation, and novelty slices.

### P1 / Era vs hard-date confusion / Collapse and type

- Change: Unify release_year_range and date hard_filters into temporal_constraint(kind, range, strength, evidence_text).
- Why it makes sense: 634 turns have release-year state excluding the GT year.
- Validation: No-year/soft-year ablation should recover excluded-GT turns without hurting explicit date-bound asks.

### P1 / Known rejection not enforced / Keep plus normalize

- Change: Keep explicit_rejections but normalize to strict IDs and alias-verified names before final filtering.
- Why it makes sense: Strict leak lower bound=97; name-only audit adds 62 uncertain cases.
- Validation: Zero strict leaks; human-check name-only sample before widening the assertion.

### P2 / Metadata context absent from state/ranker / Add context, not raw ranker constants

- Change: Thread available conversation_goal and user_profile fields through devset/blindset batch inputs; derive goal/culture affinity per candidate.
- Why it makes sense: Organizer metadata is available in Blind-A raw rows and semantically useful, but raw session constants previously showed no within-turn lift and current inference drops them.
- Validation: Candidate-varying affinity must beat raw session/category/demographic features in session-grouped CV and remain usable in Blind-A inference.

### Do not start here / More raw tags / raw demographics / Do not add

- Change: Avoid adding extra raw tag buckets or feeding raw demographics/category as direct candidate features.
- Why it makes sense: Tags already overlap GT often enough to be useful; raw demographics/category are candidate-constant unless transformed.
- Validation: Only revisit if candidate-varying tag or affinity features beat the simpler role/routing/ranker changes.


## Ideal State Targets To Try Extracting

Use this as the small-batch extractor contract: test the ideal shape, keep the minimum viable state if the full shape is unreliable, and fall back to deterministic derived features when extraction is too expensive or noisy.

### P0 / role_typed_entities

- Failure classes: Roleless entity carryover; Novelty prior-anchor failure
- Minimum viable state: For each entity: type, value/id, role, source_turn, use_as_retrieval_seed.
- Extraction probe: On each 10-turn pack, ask whether every prior positive artist/track is current_target, seed, satisfied, history, contrast, or rejected.
- Fallback if too hard: Keep mentioned_entities, but derive current_turn_entity and seed_allowed booleans from current utterance plus source_turn recency.
- Downstream use: Only current_target/seed entities should fan out discography and exact-entity branches; satisfied/history entities become context or recency features.
- Replay packs: P0_roleless_stale_entity_failure; P0_novelty_prior_anchor_failure

Ideal state shape:

```json
{
  "entities": [
    {
      "type": "artist|track|album|tag",
      "value": "Lana Del Rey",
      "id": "optional_catalog_id",
      "role": "current_target|seed|satisfied|history|contrast|rejected",
      "source_turn": 4,
      "mentioned_current_turn": true,
      "anchor_strength": "0.0-1.0",
      "use_as_retrieval_seed": true,
      "evidence_text": "more like Lana but not the same artist"
    }
  ],
  "current_target_entities": [
    "entity_id_or_value"
  ],
  "history_context_entities": [
    "entity_id_or_value"
  ]
}
```

### P0 / target_artist_mode

- Failure classes: Same-artist vs new-artist ambiguity; New-artist union@20 gap
- Minimum viable state: target_artist_mode enum plus evidence_text and confidence.
- Extraction probe: Check whether novelty and diversify asks reliably become new_artist or any_artist instead of continuation.
- Fallback if too hard: Derive with rules: explicit 'more by X' => same_artist; 'different/new/other artists' => new_artist; otherwise unknown.
- Downstream use: Switch retriever profile before fusion: continuation keeps album/artist branches; novelty boosts tag, CF, popularity, and similar-artist branches.
- Replay packs: P0_novelty_prior_anchor_failure; P0_new_artist_union20_gap_failure

Ideal state shape:

```json
{
  "target_artist_mode": "same_artist|new_artist|any_artist|unknown",
  "confidence": "0.0-1.0",
  "evidence_text": "different artist, same vibe",
  "anchor_policy": "keep_recent|decay_prior|suppress_prior|suppress_rejected"
}
```

### P0 / retrieval_profile

- Failure classes: Extracted routing is not consumed; Good tag state but union@20 gap
- Minimum viable state: retrieval_profile enum plus positive branch hints and suppressions.
- Extraction probe: For each sampled turn, label which retriever branches should get more fanout and which old anchors should be suppressed.
- Fallback if too hard: Do not spend LLM calls first; map existing routing_tags into routing_boost/profile configs and replay.
- Downstream use: Consumes state before candidate generation, so union@20 can move instead of only final ranking.
- Replay packs: P0_new_artist_union20_gap_failure; P1_positive_tag_retrieval_gap_failure

Ideal state shape:

```json
{
  "retrieval_profile": "continuation|novelty|exact_probe|feature_search|hidden_target_search",
  "branch_weights": {
    "artist_discography": 0.2,
    "tag_metadata": 1.4,
    "cf": 1.2
  },
  "suppressions": [
    "prior_artist_discography"
  ],
  "fanout_topk": 100
}
```

### P1 / temporal_constraint

- Failure classes: Era vs hard-date confusion
- Minimum viable state: kind, range, strength, and apply_as_filter.
- Extraction probe: Ask whether the user meant literal release years or an aesthetic era; hard should be rare and explicit.
- Fallback if too hard: Treat all inferred era ranges as soft boosts unless the user explicitly asks for a year/decade/date constraint.
- Downstream use: Hard filters only for literal constraints; style/reference eras become compatibility features.
- Replay packs: P1_temporal_constraint_failure

Ideal state shape:

```json
{
  "temporal_constraint": {
    "kind": "release_date|style_era|reference_era",
    "range": [
      1995,
      2004
    ],
    "strength": "hard|soft",
    "apply_as_filter": false,
    "evidence_text": "late 90s sound"
  }
}
```

### P1 / normalized_rejections

- Failure classes: Known rejection not enforced
- Minimum viable state: kind, value, scope, source_turn, plus strict IDs when resolver can provide them.
- Extraction probe: Check whether each negative phrase is a hard rejection, a soft preference, or a contrast-only cue.
- Fallback if too hard: Keep strict ID rejection as the canonical assertion; route name-only and style-only flags into manual/audit buckets.
- Downstream use: Finalization guardrail: strict rejected IDs must be filtered after ranking; soft rejections become negative features.
- Replay packs: P1_rejection_guardrail_failure

Ideal state shape:

```json
{
  "rejections": [
    {
      "kind": "track|artist|album|tag|style",
      "value": "metal",
      "ids": [
        "optional_catalog_or_alias_id"
      ],
      "scope": "hard|soft",
      "source_turn": 8,
      "evidence_text": "not metal"
    }
  ]
}
```

### P0 / feedback_carry_forward

- Failure classes: Track feedback underused; Same-album ranker failure
- Minimum viable state: track_id, role, source_turn, carry_forward.
- Extraction probe: Separate 'I liked this, keep going' from 'that satisfied the ask, now move on'.
- Fallback if too hard: Do not rerun extraction; derive same_album_recent, same_artist_recent, and rejected_track flags from play history and existing feedback.
- Downstream use: Ranker features for same_album_recent, artist_recency, accepted-track proximity, and avoid flags.
- Replay packs: P0_same_album_ranker_failure; P0_good_state_ranker_near_miss_failure

Ideal state shape:

```json
{
  "track_feedback": [
    {
      "track_id": "catalog_track_id",
      "role": "accepted|satisfied|seed|rejected|contrast",
      "source_turn": 3,
      "carry_forward": "seed|context|avoid|none",
      "artist_keep_strength": "0.0-1.0",
      "album_keep_strength": "0.0-1.0"
    }
  ]
}
```

### P0 / album_artist_recency_features

- Failure classes: Same-album continuation rank loss; Good state low recall
- Minimum viable state: No new extractor field required; compute same_album_recent, same_artist_recent, and recency deltas from history.
- Extraction probe: No LLM probe. Verify feature computation on same-album and clean-hit packs.
- Fallback if too hard: Use binary same_album_recent and same_artist_recent only.
- Downstream use: Trained ranker/reranker feature; should improve final@20 without changing union@20.
- Replay packs: P0_same_album_ranker_failure; POS_clean_final_hit_control

Ideal state shape:

```json
{
  "candidate_features": {
    "same_album_recent": true,
    "same_artist_recent": true,
    "artist_last_seen_turn_delta": 2,
    "album_last_seen_turn_delta": 1,
    "accepted_anchor_similarity": "0.0-1.0"
  }
}
```

### P1 / positive_tag_compatibility

- Failure classes: Positive tag retrieval gap
- Minimum viable state: canonical tag, role, confidence, source_turn.
- Extraction probe: Check whether tags are current target features or merely old context; normalize synonyms without adding many new fields.
- Fallback if too hard: Keep raw positive_tags; add candidate tag-overlap and tag-compatibility features from catalog metadata.
- Downstream use: Candidate generation/ranker compatibility feature; not a standalone reason to rerun the whole extractor.
- Replay packs: P1_positive_tag_retrieval_gap_failure

Ideal state shape:

```json
{
  "positive_tags": [
    {
      "raw": "late-night",
      "canonical": "late night",
      "role": "target_feature|context|contrast",
      "confidence": "0.0-1.0",
      "source_turn": 2
    }
  ],
  "negative_tags": [
    {
      "raw": "too heavy",
      "canonical": "heavy metal",
      "scope": "soft"
    }
  ]
}
```

### P1 / exact_reference_guard

- Failure classes: Exact entity success control; Named artist ranker failure
- Minimum viable state: kind, value/id, confidence, protect_topk.
- Extraction probe: Verify explicit named-track controls stay exact and named-artist cases protect artist candidates without overfitting common words.
- Fallback if too hard: Use strict title/artist lexical resolver and branch protection; avoid broad fuzzy matching for short/common titles.
- Downstream use: Candidate protection and ranker exactness feature; also regression guardrail for any state rewrite.
- Replay packs: P0_named_artist_ranker_failure; POS_exact_entity_success_control

Ideal state shape:

```json
{
  "exact_references": [
    {
      "kind": "track|artist|album",
      "value": "Dreams",
      "ids": [
        "catalog_id"
      ],
      "confidence": "0.0-1.0",
      "protect_topk": 20,
      "evidence_text": "play Dreams"
    }
  ]
}
```

### P2 / goal_profile_context

- Failure classes: Metadata context absent from state/ranker
- Minimum viable state: Thread existing listener_goal, category, specificity, and preferred_musical_culture from raw rows into the state/ranker pack.
- Extraction probe: No expensive per-turn extraction first; Blind-A raw rows already have these fields. Test whether metadata improves candidate-varying affinity features in CV.
- Fallback if too hard: Use metadata only for slicing and diagnostics until candidate-varying features show lift; do not emulate fields that Blind-A already provides.
- Downstream use: Novelty and popularity retrieval/ranker features; raw session constants are not enough.
- Replay packs: P0_new_artist_union20_gap_failure; POS_clean_final_hit_control

Ideal state shape:

```json
{
  "goal_context": {
    "listener_goal": "discover energetic songs for workouts",
    "category": "J",
    "specificity": "LH",
    "preferred_musical_culture": "US mainstream",
    "use_for": "routing|candidate_affinity|analysis_only",
    "candidate_varying_features": [
      "culture_conditioned_popularity",
      "goal_text_match",
      "user_cf_affinity"
    ]
  }
}
```


## State Confusion / Field Economy Plan

More state is not automatically better. These are the fields that can confuse the extractor or downstream code if they overlap, plus the simplification rule to test first.

### mentioned_entities treated as positive anchors

- Risk: The extractor stores prior liked/satisfied/history mentions in a field that downstream retrieval reads as current intent.
- Decision: Split roles instead of adding more positive-entity fields.
- Field-economy move: Replace positive/current ambiguity with role_typed_entities and seed_allowed/use_as_retrieval_seed.
- Small test: On stale and novelty packs, every old artist/track should be satisfied, history, contrast, or rejected unless the current user explicitly reuses it.

### turn_intent, intent_mode, routing_tags, and process_constraints all describe mode

- Risk: Multiple mode fields can disagree, and the current config does not consume routing_boost anyway.
- Decision: Collapse downstream to one retrieval_profile plus target_artist_mode.
- Field-economy move: Keep raw fields for QA/debug; expose only retrieval_profile to candidate generation.
- Small test: For novelty packs, retrieval_profile should suppress old-artist fanout and boost tag/CF/popularity branches.

### release_year_range plus date hard_filters

- Risk: The system can misread a style-era cue as a literal release-date filter.
- Decision: Collapse to temporal_constraint(kind, range, strength, apply_as_filter).
- Field-economy move: One temporal object beats separate range/filter fields.
- Small test: In year-excludes-GT samples, style_era/reference_era should be soft and apply_as_filter=false unless the user asks for literal years.

### positive_tags, lyrical_theme, attributes, and genre descriptors

- Risk: More tag-like fields can fragment the same signal and dilute retrieval/ranker features.
- Decision: Keep specialized fields, but canonicalize and assign roles instead of adding more raw buckets.
- Field-economy move: Use positive_tag_compatibility with raw/canonical/role/source_turn; keep lyrical_theme for lyric/theme routing.
- Small test: Positive-tag gap samples should preserve current target tags and avoid promoting old context tags.

### explicit_rejections mixed with soft dislikes or contrast cues

- Risk: A contrast cue can become an over-hard filter, while true rejected IDs can still leak without normalization.
- Decision: Keep rejections separate from contrast; normalize strict IDs and aliases.
- Field-economy move: Use normalized_rejections with hard/soft scope and keep contrast as an entity role.
- Small test: Rejected-ID samples should have zero strict leaks; name/style-only samples stay audit-only until hand-labeled.

### track_feedback, referenced_track_ids, and exact references

- Risk: A referenced track can mean exact target, satisfied prior item, seed, contrast, or rejection.
- Decision: Keep exact_reference_guard separate from feedback_carry_forward.
- Field-economy move: Exact references protect candidates; feedback roles decide seed/context/avoid/none.
- Small test: Exact controls stay final@20; same-album samples compute recency features without making every played track a seed.

### candidate features requested from the extractor

- Risk: Asking the LLM for derived ranker features increases cost and inconsistency.
- Decision: Do not extract deterministic features.
- Field-economy move: Compute same_album_recent, same_artist_recent, artist_recency, album_recency, branch ranks, and exactness outside the LLM.
- Small test: Same-album/ranker packs should test feature computation and trained scoring, not state reruns.

### organizer session metadata blended into turn state

- Risk: Session constants can look important but cannot rank candidates within a turn unless transformed.
- Decision: Keep organizer metadata in a separate goal_context namespace.
- Field-economy move: Use listener_goal/category/specificity/profile as context, slices, or candidate-varying affinity; do not ask the extractor to recreate them.
- Small test: Goal/profile experiments must beat raw-constant baselines in session-grouped CV.


## Good State, Low Recall Slices

### Positive tags overlap GT

- Turns: 5,937
- Final@20: 28.7%
- Union@20: 49.0%
- Union@100: 68.7%
- Not union@20: 3,030
- Union@20 not final: 1,307
- Read: The tag state often contains a semantically relevant signal, but that does not guarantee the GT reaches union@20.
- Work: Do not rewrite tags first; route/tag-rank candidates better and add tag-overlap features to the trained scorer.

### Current user names GT artist

- Turns: 1,671
- Final@20: 61.1%
- Union@20: 90.2%
- Union@100: 98.2%
- Not union@20: 163
- Union@20 not final: 503
- Read: The user gave an explicit artist signal, so misses here are usually track selection, final ranking, or exact-artist candidate protection.
- Work: Protect named-artist candidates, then train ranker features for branch rank, artist recency, album affinity, exactness, and popularity.

### GT primary album already heard

- Turns: 2,023
- Final@20: 51.7%
- Union@20: 88.8%
- Union@100: 95.5%
- Not union@20: 227
- Union@20 not final: 756
- Read: History is informative and the candidate is often nearby, but final ranking still underuses album/artist recency.
- Work: Add same_album_recent and artist_recency features; measure continuation NDCG@20 and new-artist guardrails.

### Routing tag active

- Turns: 7,528
- Final@20: 28.0%
- Union@20: 48.7%
- Union@100: 67.2%
- Not union@20: 3,859
- Union@20 not final: 1,660
- Read: The state detects a route signal, but the config does not translate it into branch weights.
- Work: Wire retrieval_profile/routing_boost before adding new retrievers; measure union@20/100 per tag.

### Popularity cue + new artist

- Turns: 1,211
- Final@20: 9.2%
- Union@20: 18.7%
- Union@100: 45.9%
- Not union@20: 985
- Union@20 not final: 141
- Read: The user cue is clear, but novelty plus popularity needs canonical candidates outside old anchors.
- Work: Add target_artist_mode and genre/era-conditioned popularity or CF retrieval for novelty profiles.

### Release range present and GT in range

- Turns: 1,530
- Final@20: 28.2%
- Union@20: 46.6%
- Union@100: 71.0%
- Not union@20: 817
- Union@20 not final: 330
- Read: Temporal state can be correct and still not retrieve the target; this is not just a year-extraction bug.
- Work: Use temporal compatibility as a soft feature and focus hard-filter work on the exclude-GT failures.

### Track feedback present

- Turns: 6,978
- Final@20: 26.7%
- Union@20: 48.8%
- Union@100: 67.3%
- Not union@20: 3,570
- Union@20 not final: 1,633
- Read: The state has behavioral feedback, but it needs a downstream role: keep-near, move-on, avoid, or satisfied.
- Work: Map feedback to entity roles plus artist/album recency features; sample accepted vs novelty turns.


## Small Subset Experiment Packs

Use these deterministic sample turns for future before/after recall tests when state extraction reruns are expensive.

### P0_roleless_stale_entity_failure

- Class type: failure
- Turns: 10 sampled; target=10
- Hypothesis: A role-typed state rerun should stop stale/satisfied entities from acting like current anchors.
- State targets: role_typed_entities; feedback_carry_forward
- State terms to check: For each entity: type, value/id, role, source_turn, use_as_retrieval_seed. | track_id, role, source_turn, carry_forward.
- Success metric: State QA first: stale-current-positive count drops on all sampled turns. Retrieval QA second: union@20/100 should not get worse, and target branch rank should improve on at least some samples.

#### 0b9d547f-e748-464a-90e2-2199149f915c::t6

- Class type: failure
- GT: Give It To Me Baby by Rick James
- Ranks: final=158; fused=218; best_branch=101 (dense.qwen_8b.attributes.attributes_qwen3_embedding_8b)
- Expected change: After extraction rerun, stale prior entities should move out of current positive anchors or get lower anchor_strength.

#### e66c6a88-88ba-4117-9114-363bfa96294a::t7

- Class type: failure
- GT: Test Drive by John Powell
- Ranks: final=117; fused=178; best_branch=101 (dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b)
- Expected change: After extraction rerun, stale prior entities should move out of current positive anchors or get lower anchor_strength.

#### 0858f444-c9af-4f08-a9fc-2a731a24182b::t5

- Class type: failure
- GT: Armature by Emptyset
- Ranks: final=368; fused=384; best_branch=101 (dense.clap_text.sonic.audio_laion_clap)
- Expected change: After extraction rerun, stale prior entities should move out of current positive anchors or get lower anchor_strength.

#### 41367174-552b-4117-9caa-d0ba1b307d37::t2

- Class type: failure
- GT: Mercy by Muse
- Ranks: final=682; fused=-; best_branch=102 (bm25)
- Expected change: After extraction rerun, stale prior entities should move out of current positive anchors or get lower anchor_strength.

#### 10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7

- Class type: failure
- GT: I Can't Go to Sleep by Wu-Tang Clan
- Ranks: final=-; fused=-; best_branch=102 (dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b)
- Expected change: After extraction rerun, stale prior entities should move out of current positive anchors or get lower anchor_strength.

#### 9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4

- Class type: failure
- GT: The Carbon Stampede by Cattle Decapitation
- Ranks: final=256; fused=248; best_branch=102 (centroid.user.cf_bpr)
- Expected change: After extraction rerun, stale prior entities should move out of current positive anchors or get lower anchor_strength.

#### 5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2

- Class type: failure
- GT: Shaft by Kashmere Stage Band
- Ranks: final=965; fused=681; best_branch=102 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: After extraction rerun, stale prior entities should move out of current positive anchors or get lower anchor_strength.

#### 78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8

- Class type: failure
- GT: In the Shadows by The Rasmus
- Ranks: final=-; fused=-; best_branch=103 (centroid.user.cf_bpr)
- Expected change: After extraction rerun, stale prior entities should move out of current positive anchors or get lower anchor_strength.

#### 88af7ec3-c368-421b-9512-d0180da3d1f6::t2

- Class type: failure
- GT: I Believe in a Thing Called Love by The Darkness
- Ranks: final=-; fused=-; best_branch=103 (centroid.anchor_tracks.image_siglip2)
- Expected change: After extraction rerun, stale prior entities should move out of current positive anchors or get lower anchor_strength.

#### d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2

- Class type: failure
- GT: Move Along by The All-American Rejects
- Ranks: final=113; fused=275; best_branch=103 (centroid.anchor_tracks.audio_laion_clap)
- Expected change: After extraction rerun, stale prior entities should move out of current positive anchors or get lower anchor_strength.

### P0_novelty_prior_anchor_failure

- Class type: failure
- Turns: 10 sampled; target=10
- Hypothesis: Novelty/diversify turns should not keep old artists as active positive anchors.
- State targets: role_typed_entities; target_artist_mode; retrieval_profile
- State terms to check: For each entity: type, value/id, role, source_turn, use_as_retrieval_seed. | target_artist_mode enum plus evidence_text and confidence. | retrieval_profile enum plus positive branch hints and suppressions.
- Success metric: State QA: prior anchors are not current positive seeds. Recall QA: best_branch_rank or union@20 improves for novelty/new-artist targets.

#### c7a965c3-cd7f-46f6-b166-9dce9a800e0a::t3

- Class type: failure
- GT: S&M by Rihanna
- Ranks: final=163; fused=181; best_branch=101 (dense.qwen_8b.attributes.attributes_qwen3_embedding_8b)
- Expected change: Prior artists should be labeled satisfied/history/contrast rather than current seed; retrieval_profile should reduce old-artist discography and centroid pressure.

#### 88beb200-0334-4aba-be15-8e1303725766::t6

- Class type: failure
- GT: Used To by Lil Wayne, Drake
- Ranks: final=522; fused=252; best_branch=101 (dense.clap_text.sonic.audio_laion_clap)
- Expected change: Prior artists should be labeled satisfied/history/contrast rather than current seed; retrieval_profile should reduce old-artist discography and centroid pressure.

#### daeef24e-b041-4140-9101-882820c63408::t7

- Class type: failure
- GT: The Analog Kid by Rush
- Ranks: final=240; fused=316; best_branch=101 (bm25)
- Expected change: Prior artists should be labeled satisfied/history/contrast rather than current seed; retrieval_profile should reduce old-artist discography and centroid pressure.

#### 8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7

- Class type: failure
- GT: Transcentience by Animals As Leaders
- Ranks: final=-; fused=-; best_branch=101 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Prior artists should be labeled satisfied/history/contrast rather than current seed; retrieval_profile should reduce old-artist discography and centroid pressure.

#### 380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3

- Class type: failure
- GT: God Hates a Coward by Tomahawk
- Ranks: final=65; fused=312; best_branch=102 (dense.clap_text.sonic.audio_laion_clap)
- Expected change: Prior artists should be labeled satisfied/history/contrast rather than current seed; retrieval_profile should reduce old-artist discography and centroid pressure.

#### 5f085552-b56b-440e-830b-b4e40b58f854::t6

- Class type: failure
- GT: Redneck Yacht Club by Craig Morgan
- Ranks: final=136; fused=291; best_branch=102 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Prior artists should be labeled satisfied/history/contrast rather than current seed; retrieval_profile should reduce old-artist discography and centroid pressure.

#### d6e50fb5-a135-4008-80b6-d0be434369ac::t3

- Class type: failure
- GT: Volare (Nel Blu Di Pinto Di Blu) - 1998 - Remastered by Dean Martin
- Ranks: final=151; fused=147; best_branch=103 (centroid.anchor_tracks.image_siglip2)
- Expected change: Prior artists should be labeled satisfied/history/contrast rather than current seed; retrieval_profile should reduce old-artist discography and centroid pressure.

#### 38d8ba41-a4ea-48ea-b460-bd93d164302a::t4

- Class type: failure
- GT: Woo Hah!! Got You All In Check by Busta Rhymes
- Ranks: final=412; fused=405; best_branch=103 (centroid.anchor_tracks.image_siglip2)
- Expected change: Prior artists should be labeled satisfied/history/contrast rather than current seed; retrieval_profile should reduce old-artist discography and centroid pressure.

#### 8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6

- Class type: failure
- GT: Exit Theme (feat. Astronautalis & Lotte Kestner) by Astronautalis, Sadistik, Lotte Kestner
- Ranks: final=485; fused=344; best_branch=103 (bm25)
- Expected change: Prior artists should be labeled satisfied/history/contrast rather than current seed; retrieval_profile should reduce old-artist discography and centroid pressure.

#### cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3

- Class type: failure
- GT: Gib ihn einfach (Dies das 2) by Ghanaian Stallion
- Ranks: final=-; fused=-; best_branch=103 (dense.qwen_8b.attributes.attributes_qwen3_embedding_8b)
- Expected change: Prior artists should be labeled satisfied/history/contrast rather than current seed; retrieval_profile should reduce old-artist discography and centroid pressure.

### P0_new_artist_union20_gap_failure

- Class type: failure
- Turns: 10 sampled; target=10
- Hypothesis: Novelty/new-artist turns need a different retrieval profile, not just better final ranking.
- State targets: target_artist_mode; retrieval_profile; goal_profile_context
- State terms to check: target_artist_mode enum plus evidence_text and confidence.
- State terms to check detail: retrieval_profile enum plus positive branch hints and suppressions.
- State terms to check detail: Thread existing listener_goal, category, specificity, and preferred_musical_culture from raw rows into the state/ranker pack.
- Success metric: Primary: GT enters union@20 or improves best_branch_rank. Secondary: final@20 after a stable ranker should improve without continuation regression.

#### a930da0d-07f1-46c6-909d-e4fd95ae1148::t6

- Class type: failure
- GT: Without You by Christina Aguilera
- Ranks: final=413; fused=423; best_branch=101 (centroid.anchor_tracks.cf_bpr)
- Expected change: target_artist_mode should become new_artist/any_artist, prior artists should be satisfied/history, and routing should upweight tag/metadata/popularity/CF branches.

#### 5ee0dbbc-c1d1-4bed-ba09-7dafeec198bc::t8

- Class type: failure
- GT: You Reposted in the Wrong Neighborhood I Glue70 Mashup by Shokk
- Ranks: final=-; fused=878; best_branch=102 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: target_artist_mode should become new_artist/any_artist, prior artists should be satisfied/history, and routing should upweight tag/metadata/popularity/CF branches.

#### 4e2482dc-a76c-4f4b-9d3f-7becec2f8a3a::t4

- Class type: failure
- GT: Goodbye Pork Pie Hat by Charles Mingus
- Ranks: final=173; fused=139; best_branch=103 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: target_artist_mode should become new_artist/any_artist, prior artists should be satisfied/history, and routing should upweight tag/metadata/popularity/CF branches.

#### 5861afef-85c0-4163-b8b9-5a11e308f352::t4

- Class type: failure
- GT: Carmesí by Vicente Garcia
- Ranks: final=334; fused=406; best_branch=104 (dense.qwen_8b.attributes.attributes_qwen3_embedding_8b)
- Expected change: target_artist_mode should become new_artist/any_artist, prior artists should be satisfied/history, and routing should upweight tag/metadata/popularity/CF branches.

#### 15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6

- Class type: failure
- GT: Hong Kong 2046 by Hong Kong Express
- Ranks: final=699; fused=760; best_branch=104 (centroid.anchor_tracks.audio_laion_clap)
- Expected change: target_artist_mode should become new_artist/any_artist, prior artists should be satisfied/history, and routing should upweight tag/metadata/popularity/CF branches.

#### 907921a3-d08f-4ba1-8cce-0e760a9e7044::t7

- Class type: failure
- GT: Sunrise - Slow Hands Remix by Kasper Bjørke
- Ranks: final=589; fused=685; best_branch=104 (centroid.user.cf_bpr)
- Expected change: target_artist_mode should become new_artist/any_artist, prior artists should be satisfied/history, and routing should upweight tag/metadata/popularity/CF branches.

#### ab5eac17-909e-4271-8cf9-40c06b27ee56::t2

- Class type: failure
- GT: Sparks by Hilary Duff
- Ranks: final=206; fused=481; best_branch=105 (bm25)
- Expected change: target_artist_mode should become new_artist/any_artist, prior artists should be satisfied/history, and routing should upweight tag/metadata/popularity/CF branches.

#### 324ddfb5-8a18-4729-9acb-c851907a297c::t3

- Class type: failure
- GT: Acknowledge by Masta Ace
- Ranks: final=311; fused=263; best_branch=105 (centroid.user.cf_bpr)
- Expected change: target_artist_mode should become new_artist/any_artist, prior artists should be satisfied/history, and routing should upweight tag/metadata/popularity/CF branches.

#### b466a64b-b3cc-4c62-8a70-8261434f915f::t2

- Class type: failure
- GT: Two To Make It Right by Seduction
- Ranks: final=162; fused=449; best_branch=105 (dense.clap_text.sonic.audio_laion_clap)
- Expected change: target_artist_mode should become new_artist/any_artist, prior artists should be satisfied/history, and routing should upweight tag/metadata/popularity/CF branches.

#### ba68a3cc-5278-4680-917a-4ca66d33ef31::t5

- Class type: failure
- GT: Buttons by The Pussycat Dolls
- Ranks: final=328; fused=404; best_branch=106 (centroid.anchor_tracks.image_siglip2)
- Expected change: target_artist_mode should become new_artist/any_artist, prior artists should be satisfied/history, and routing should upweight tag/metadata/popularity/CF branches.

### P1_temporal_constraint_failure

- Class type: failure
- Turns: 10 sampled; target=10
- Hypothesis: Temporal state should distinguish style-era cues from hard release-date filters.
- State targets: temporal_constraint
- State terms to check: kind, range, strength, and apply_as_filter.
- Success metric: Target remains eligible and best_branch_rank improves under soft/no-year ablation; explicit date-bound turns stay clean.

#### d5fcb591-3744-4ebb-9d1a-5c57c314b7d0::t5

- Class type: failure
- GT: Love Train by The O'Jays
- Ranks: final=160; fused=369; best_branch=106 (centroid.anchor_tracks.audio_laion_clap)
- Expected change: Temporal constraints should separate style-era from hard release-date bounds, with soft compatibility used for aesthetic eras.

#### f2d85aa5-2086-4b1e-9974-d188c43621db::t8

- Class type: failure
- GT: Leraine by Kettel
- Ranks: final=416; fused=567; best_branch=108 (dense.qwen_8b.attributes.attributes_qwen3_embedding_8b)
- Expected change: Temporal constraints should separate style-era from hard release-date bounds, with soft compatibility used for aesthetic eras.

#### 67b9ba8a-382f-4b70-af76-576848d8cf67::t8

- Class type: failure
- GT: Gangsta Gangsta by N.W.A.
- Ranks: final=995; fused=652; best_branch=109 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Temporal constraints should separate style-era from hard release-date bounds, with soft compatibility used for aesthetic eras.

#### 9468e467-d396-461b-be29-b30b6cf87c35::t5

- Class type: failure
- GT: Midnight by A Tribe Called Quest
- Ranks: final=587; fused=417; best_branch=110 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Temporal constraints should separate style-era from hard release-date bounds, with soft compatibility used for aesthetic eras.

#### e978bb5b-26af-4c7d-b720-b9210bdddf25::t8

- Class type: failure
- GT: Dear Yvette by Jane Doe, Masta Ace
- Ranks: final=940; fused=651; best_branch=113 (centroid.user.cf_bpr)
- Expected change: Temporal constraints should separate style-era from hard release-date bounds, with soft compatibility used for aesthetic eras.

#### 3676005d-5b7c-4c48-9b73-3e10dd509c07::t3

- Class type: failure
- GT: Conquest of Paradise by Vangelis
- Ranks: final=553; fused=780; best_branch=114 (dense.clap_text.sonic.audio_laion_clap)
- Expected change: Temporal constraints should separate style-era from hard release-date bounds, with soft compatibility used for aesthetic eras.

#### a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6

- Class type: failure
- GT: Thriller by Fall Out Boy
- Ranks: final=67; fused=91; best_branch=116 (centroid.anchor_tracks.image_siglip2)
- Expected change: Temporal constraints should separate style-era from hard release-date bounds, with soft compatibility used for aesthetic eras.

#### 3676005d-5b7c-4c48-9b73-3e10dd509c07::t1

- Class type: failure
- GT: Breath and Life by Audiomachine
- Ranks: final=658; fused=449; best_branch=116 (dense.qwen_8b.attributes.attributes_qwen3_embedding_8b)
- Expected change: Temporal constraints should separate style-era from hard release-date bounds, with soft compatibility used for aesthetic eras.

#### c4c0c288-dbcd-4970-ad52-901aafe91b88::t4

- Class type: failure
- GT: I Juswanna Chill by Large Professor
- Ranks: final=651; fused=307; best_branch=117 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Temporal constraints should separate style-era from hard release-date bounds, with soft compatibility used for aesthetic eras.

#### 71bb177a-dab1-4bbc-8508-22d809b05c31::t6

- Class type: failure
- GT: Constant Craving - Remastered by k.d. lang
- Ranks: final=253; fused=128; best_branch=118 (dense.qwen_8b.attributes.attributes_qwen3_embedding_8b)
- Expected change: Temporal constraints should separate style-era from hard release-date bounds, with soft compatibility used for aesthetic eras.

### P1_rejection_guardrail_failure

- Class type: failure
- Turns: 10 sampled; target=10
- Hypothesis: Rejected entities should never leak into final top-20.
- State targets: normalized_rejections
- State terms to check: kind, value, scope, source_turn, plus strict IDs when resolver can provide them.
- Success metric: Zero strict rejected ID leakage; name-only flags are hand-labeled before widening assertions.

#### 4d0afb6b-3705-493f-ab16-ca75ea311e1a::t7

- Class type: failure
- GT: Pilot by Benjamin Wallfisch, Hans Zimmer
- Ranks: final=-; fused=-; best_branch=1 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Rejected IDs and verified aliases should be normalized and filtered after finalization.

#### 1e14a07f-7369-4d24-9285-9343b6b18353::t8

- Class type: failure
- GT: Nordlys by Myrkur
- Ranks: final=32; fused=1; best_branch=1 (dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b)
- Expected change: Rejected IDs and verified aliases should be normalized and filtered after finalization.

#### d265b5a9-af57-4070-90f5-692a960c5aaa::t6

- Class type: failure
- GT: Get Lucky (feat. Pharrell Williams &amp; Nile Rodgers) - Radio Edit by Nile Rodgers, Pharrell Williams, Daft Punk
- Ranks: final=-; fused=-; best_branch=2 (lookup.resolved_artist_discography)
- Expected change: Rejected IDs and verified aliases should be normalized and filtered after finalization.

#### b2582e52-6d13-40b4-8552-2d8b63fa6c75::t8

- Class type: failure
- GT: Soil by System Of A Down
- Ranks: final=-; fused=-; best_branch=2 (bm25)
- Expected change: Rejected IDs and verified aliases should be normalized and filtered after finalization.

#### d265b5a9-af57-4070-90f5-692a960c5aaa::t8

- Class type: failure
- GT: Motherboard by Daft Punk
- Ranks: final=-; fused=-; best_branch=2 (centroid.anchor_tracks.image_siglip2)
- Expected change: Rejected IDs and verified aliases should be normalized and filtered after finalization.

#### 3a4224d3-1e5b-4bb9-a424-886d5c45d5d3::t8

- Class type: failure
- GT: Brain Relaxation Sky by Sample Rain Library
- Ranks: final=124; fused=90; best_branch=2 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Rejected IDs and verified aliases should be normalized and filtered after finalization.

#### 963b3ee7-17d1-4bb3-8a3f-0bc528a1f096::t5

- Class type: failure
- GT: Go Go Gadget Flow by Lupe Fiasco
- Ranks: final=57; fused=12; best_branch=2 (dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b)
- Expected change: Rejected IDs and verified aliases should be normalized and filtered after finalization.

#### 08bea603-846a-428b-aa27-de4dfede7ba9::t8

- Class type: failure
- GT: Silhouette by Julia Holter
- Ranks: final=-; fused=-; best_branch=2 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Rejected IDs and verified aliases should be normalized and filtered after finalization.

#### 0fc60312-9a9d-4658-a950-06fc2441a2ac::t8

- Class type: failure
- GT: Music Will Untune the Sky by Have A Nice Life
- Ranks: final=26; fused=1; best_branch=2 (dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b)
- Expected change: Rejected IDs and verified aliases should be normalized and filtered after finalization.

#### 3ebc2b49-0f5c-4161-bbcf-e1615821103f::t2

- Class type: failure
- GT: The Animus 2.0 by Jesper Kyd
- Ranks: final=28; fused=23; best_branch=2 (dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b)
- Expected change: Rejected IDs and verified aliases should be normalized and filtered after finalization.

### P0_named_artist_ranker_failure

- Class type: failure
- Turns: 10 sampled; target=10
- Hypothesis: Named-artist turns usually have the right entity but still lose the right track in ranking/finalization.
- State targets: exact_reference_guard; role_typed_entities
- State terms to check: kind, value/id, confidence, protect_topk. | For each entity: type, value/id, role, source_turn, use_as_retrieval_seed.
- Success metric: GT moves into final top-20 without hurting exact-track or rejection guardrails.

#### 37097db6-54b8-491b-8512-1df70648548b::t2

- Class type: failure
- GT: White Ferrari by Frank Ocean
- Ranks: final=70; fused=16; best_branch=1 (centroid.anchor_tracks.image_siglip2)
- Expected change: A state-aware scorer should protect named-artist candidates and use branch rank, exactness, album/artist recency, and popularity features.

#### f4115525-7e44-40df-8957-e38df99f214d::t4

- Class type: failure
- GT: Young And Beautiful by Lana Del Rey
- Ranks: final=219; fused=19; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A state-aware scorer should protect named-artist candidates and use branch rank, exactness, album/artist recency, and popularity features.

#### eee89ca2-fc86-4a9a-b4c5-2d77cb3346c8::t7

- Class type: failure
- GT: Change (In the House of Flies) - In The House Of Flies LP Version by Deftones
- Ranks: final=46; fused=44; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A state-aware scorer should protect named-artist candidates and use branch rank, exactness, album/artist recency, and popularity features.

#### 44c3948c-bc44-4e40-ae77-82c2fec9c944::t7

- Class type: failure
- GT: Me Dediqué a Perderte by Alejandro Fernandez, Alejandro Fernández
- Ranks: final=219; fused=6; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A state-aware scorer should protect named-artist candidates and use branch rank, exactness, album/artist recency, and popularity features.

#### 899f906b-9b0b-42a6-9689-643eb9f1ed31::t8

- Class type: failure
- GT: Crawling by Linkin Park
- Ranks: final=-; fused=-; best_branch=1 (centroid.anchor_tracks.image_siglip2)
- Expected change: A state-aware scorer should protect named-artist candidates and use branch rank, exactness, album/artist recency, and popularity features.

#### 93199894-d3db-4335-8278-e1be175944e4::t6

- Class type: failure
- GT: Smells Like Teen Spirit by Nirvana
- Ranks: final=32; fused=81; best_branch=1 (dense.qwen_8b.attributes.attributes_qwen3_embedding_8b)
- Expected change: A state-aware scorer should protect named-artist candidates and use branch rank, exactness, album/artist recency, and popularity features.

#### 7d2bb60e-1046-4956-91d0-cf1dd73037cc::t3

- Class type: failure
- GT: Hung Up by Madonna
- Ranks: final=30; fused=36; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A state-aware scorer should protect named-artist candidates and use branch rank, exactness, album/artist recency, and popularity features.

#### 1b406c88-9dfd-42cd-a1f5-9683f35f849b::t1

- Class type: failure
- GT: 93 'Til Infinity by Souls Of Mischief
- Ranks: final=25; fused=7; best_branch=1 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: A state-aware scorer should protect named-artist candidates and use branch rank, exactness, album/artist recency, and popularity features.

#### 7be411cd-f002-459e-8326-3ebe8be10b42::t6

- Class type: failure
- GT: Army Dreamers by Kate Bush
- Ranks: final=-; fused=-; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A state-aware scorer should protect named-artist candidates and use branch rank, exactness, album/artist recency, and popularity features.

#### fc78453a-8798-4402-a01a-e9c557f08a03::t2

- Class type: failure
- GT: En el 2000 by Natalia Lafourcade
- Ranks: final=22; fused=22; best_branch=1 (bm25)
- Expected change: A state-aware scorer should protect named-artist candidates and use branch rank, exactness, album/artist recency, and popularity features.

### P0_same_album_ranker_failure

- Class type: failure
- Turns: 10 sampled; target=10
- Hypothesis: Album-continuation turns need album/artist recency features, not another state extraction pass.
- State targets: feedback_carry_forward; album_artist_recency_features
- State terms to check: track_id, role, source_turn, carry_forward. | No new extractor field required; compute same_album_recent, same_artist_recent, and recency deltas from history.
- Success metric: Same-album continuation final@20/NDCG@20 improves while new-artist slices do not regress.

#### 84803908-48e7-41b7-9269-a465a44f4c10::t2

- Class type: failure
- GT: Runaway by Pusha T, Kanye West
- Ranks: final=29; fused=10; best_branch=1 (centroid.anchor_tracks.image_siglip2)
- Expected change: Ranker should consume same_album_recent, artist_recency, track_feedback role, and branch-rank features.

#### 6d825b33-dc20-4b3c-a277-0c8214163007::t6

- Class type: failure
- GT: Super Rich Kids by Frank Ocean, Earl Sweatshirt
- Ranks: final=21; fused=3; best_branch=1 (centroid.anchor_tracks.image_siglip2)
- Expected change: Ranker should consume same_album_recent, artist_recency, track_feedback role, and branch-rank features.

#### 942c0b23-c5ad-4270-b23f-3ba456ea0ccf::t5

- Class type: failure
- GT: Alive by Pearl Jam
- Ranks: final=28; fused=5; best_branch=1 (centroid.anchor_tracks.audio_laion_clap)
- Expected change: Ranker should consume same_album_recent, artist_recency, track_feedback role, and branch-rank features.

#### 19c7e5bf-0797-40c5-b798-4d024af9558d::t4

- Class type: failure
- GT: Satisfied by Original Broadway Cast of Hamilton, Renée Elise Goldsberry
- Ranks: final=281; fused=41; best_branch=1 (centroid.anchor_tracks.image_siglip2)
- Expected change: Ranker should consume same_album_recent, artist_recency, track_feedback role, and branch-rank features.

#### 71b80ec3-6cca-48b4-b471-08efa00afa2d::t4

- Class type: failure
- GT: That Would Be Enough by Lin-Manuel Miranda, Phillipa Soo
- Ranks: final=23; fused=20; best_branch=1 (centroid.anchor_tracks.image_siglip2)
- Expected change: Ranker should consume same_album_recent, artist_recency, track_feedback role, and branch-rank features.

#### 692611f0-d9ef-406c-8327-902575197aee::t8

- Class type: failure
- GT: YAH. by Kendrick Lamar
- Ranks: final=85; fused=9; best_branch=1 (centroid.anchor_tracks.image_siglip2)
- Expected change: Ranker should consume same_album_recent, artist_recency, track_feedback role, and branch-rank features.

#### 8071d14d-7e0f-4f72-90a6-0941db80a371::t5

- Class type: failure
- GT: Stay Down by Brent Faiyaz
- Ranks: final=24; fused=1; best_branch=1 (centroid.anchor_tracks.image_siglip2)
- Expected change: Ranker should consume same_album_recent, artist_recency, track_feedback role, and branch-rank features.

#### c863175a-bbaf-4f6c-aef7-cb16f2792cb5::t6

- Class type: failure
- GT: Cinderella (feat. Ty Dolla $ign) by Mac Miller
- Ranks: final=47; fused=2; best_branch=1 (centroid.user.cf_bpr)
- Expected change: Ranker should consume same_album_recent, artist_recency, track_feedback role, and branch-rank features.

#### c96d7bb9-65d4-44be-9bc2-891e8e485f4e::t7

- Class type: failure
- GT: Sentimento Louco - Ao Vivo by Marília Mendonça
- Ranks: final=33; fused=7; best_branch=1 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Ranker should consume same_album_recent, artist_recency, track_feedback role, and branch-rank features.

#### e6ba98e1-9bee-4cc9-a6b7-0a8dcd767a1f::t7

- Class type: failure
- GT: Boom by P.O.D.
- Ranks: final=59; fused=39; best_branch=1 (centroid.anchor_tracks.audio_laion_clap)
- Expected change: Ranker should consume same_album_recent, artist_recency, track_feedback role, and branch-rank features.

### P1_positive_tag_retrieval_gap_failure

- Class type: failure
- Turns: 10 sampled; target=10
- Hypothesis: Good tag state can still fail candidate generation when stale anchors or weak routing dominate.
- State targets: positive_tag_compatibility; retrieval_profile
- State terms to check: canonical tag, role, confidence, source_turn. | retrieval_profile enum plus positive branch hints and suppressions.
- Success metric: GT enters union@20 or best_branch_rank improves; tag-overlap final@20 does not regress.

#### ad5348a7-d3bc-4882-bfca-54aa655eac96::t5

- Class type: failure
- GT: Glitter by Tyler, The Creator
- Ranks: final=137; fused=216; best_branch=101 (centroid.user.cf_bpr)
- Expected change: Use tag compatibility in retrieval_profile/ranker features and reduce stale-anchor pressure before rewriting tag extraction.

#### 2bbc0a7e-3ab0-4376-8135-182cd4ae075f::t1

- Class type: failure
- GT: Las Almas Del Silencio by Ricky Martin
- Ranks: final=119; fused=326; best_branch=101 (dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b)
- Expected change: Use tag compatibility in retrieval_profile/ranker features and reduce stale-anchor pressure before rewriting tag extraction.

#### 464477e4-f186-47fb-8cb0-55691c8b8f57::t6

- Class type: failure
- GT: Where Eagles Dare by Glenn Danzig, Misfits
- Ranks: final=475; fused=593; best_branch=102 (centroid.anchor_tracks.image_siglip2)
- Expected change: Use tag compatibility in retrieval_profile/ranker features and reduce stale-anchor pressure before rewriting tag extraction.

#### 13066d2c-2d5e-4162-b3dc-354ecef3aff5::t5

- Class type: failure
- GT: You Know What I Mean by Cults
- Ranks: final=755; fused=-; best_branch=102 (dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b)
- Expected change: Use tag compatibility in retrieval_profile/ranker features and reduce stale-anchor pressure before rewriting tag extraction.

#### a2cface7-c4fc-4eb5-80b2-e0c516093732::t3

- Class type: failure
- GT: The City Is At War by Cobra Starship
- Ranks: final=98; fused=294; best_branch=102 (centroid.user.cf_bpr)
- Expected change: Use tag compatibility in retrieval_profile/ranker features and reduce stale-anchor pressure before rewriting tag extraction.

#### dd686049-59ba-439b-8c51-949a0876e1b3::t1

- Class type: failure
- GT: Vengeance (The Return of the Night Driving Avenger) [Bonus Track] by Perturbator
- Ranks: final=752; fused=779; best_branch=102 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Use tag compatibility in retrieval_profile/ranker features and reduce stale-anchor pressure before rewriting tag extraction.

#### a8df96e2-c196-462c-9484-72aa093aedf4::t1

- Class type: failure
- GT: Do Everything by Steven Curtis Chapman
- Ranks: final=289; fused=297; best_branch=102 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Use tag compatibility in retrieval_profile/ranker features and reduce stale-anchor pressure before rewriting tag extraction.

#### 5a0dfe9d-ec8a-4449-97df-35535cbf162f::t1

- Class type: failure
- GT: A New World by Harry Gregson-Williams
- Ranks: final=350; fused=311; best_branch=102 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Expected change: Use tag compatibility in retrieval_profile/ranker features and reduce stale-anchor pressure before rewriting tag extraction.

#### 1c567917-f931-4609-9695-a9c0f8e39f3d::t2

- Class type: failure
- GT: Arregaçada / U Can't Touch This by Banda Uó
- Ranks: final=-; fused=-; best_branch=102 (dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b)
- Expected change: Use tag compatibility in retrieval_profile/ranker features and reduce stale-anchor pressure before rewriting tag extraction.

#### 54cda581-3b2e-4245-a479-1a27589760d2::t3

- Class type: failure
- GT: Deliberation - Studio by Katatonia
- Ranks: final=143; fused=384; best_branch=103 (centroid.user.cf_bpr)
- Expected change: Use tag compatibility in retrieval_profile/ranker features and reduce stale-anchor pressure before rewriting tag extraction.

### P0_good_state_ranker_near_miss_failure

- Class type: failure
- Turns: 10 sampled; target=10
- Hypothesis: Some extraction is already good enough; these turns should test state-aware ranking rather than an extractor rerun.
- State targets: feedback_carry_forward; album_artist_recency_features; exact_reference_guard
- State terms to check: track_id, role, source_turn, carry_forward. | No new extractor field required; compute same_album_recent, same_artist_recent, and recency deltas from history. | kind, value/id, confidence, protect_topk.
- Success metric: GT moves into final top-20 while rejection/year/exact guardrails stay clean.

#### 13066d2c-2d5e-4162-b3dc-354ecef3aff5::t3

- Class type: failure
- GT: Yellow by Coldplay
- Ranks: final=32; fused=85; best_branch=1 (lookup.era_popularity)
- Expected change: A trained scorer should consume branch ranks, role labels, same_album_recent, artist_recency, tag overlap, exactness, popularity, and guardrail flags.

#### a62ed6fc-e634-4d57-afab-36d9ffc0fcc1::t1

- Class type: failure
- GT: Iris by The Goo Goo Dolls
- Ranks: final=30; fused=84; best_branch=1 (lookup.era_popularity)
- Expected change: A trained scorer should consume branch ranks, role labels, same_album_recent, artist_recency, tag overlap, exactness, popularity, and guardrail flags.

#### be88097f-b6b0-4fb4-bed9-857a92a733c0::t3

- Class type: failure
- GT: Dreams - 2004 Remaster by Fleetwood Mac
- Ranks: final=186; fused=203; best_branch=1 (lookup.era_popularity)
- Expected change: A trained scorer should consume branch ranks, role labels, same_album_recent, artist_recency, tag overlap, exactness, popularity, and guardrail flags.

#### 2eb984dc-9c71-449a-a335-caaa113d2c2b::t3

- Class type: failure
- GT: Tennessee Whiskey by Chris Stapleton
- Ranks: final=60; fused=3; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A trained scorer should consume branch ranks, role labels, same_album_recent, artist_recency, tag overlap, exactness, popularity, and guardrail flags.

#### 43a0926b-882e-403d-8cf7-2b0a598e0cc5::t2

- Class type: failure
- GT: Devil In A New Dress by Rick Ross, Kanye West
- Ranks: final=64; fused=20; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A trained scorer should consume branch ranks, role labels, same_album_recent, artist_recency, tag overlap, exactness, popularity, and guardrail flags.

#### 401c369d-1eba-41b2-8eca-d93a6faeeddc::t3

- Class type: failure
- GT: Walk by Pantera
- Ranks: final=36; fused=33; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A trained scorer should consume branch ranks, role labels, same_album_recent, artist_recency, tag overlap, exactness, popularity, and guardrail flags.

#### 2db3ddc8-78a1-412c-a71e-e0d748aab0e7::t2

- Class type: failure
- GT: Old Time Rock & Roll by Bob Seger
- Ranks: final=22; fused=3; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A trained scorer should consume branch ranks, role labels, same_album_recent, artist_recency, tag overlap, exactness, popularity, and guardrail flags.

#### b4ffa800-8173-4f16-800a-4b5e765d7f80::t4

- Class type: failure
- GT: And I Love Her - Remastered by The Beatles
- Ranks: final=-; fused=-; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A trained scorer should consume branch ranks, role labels, same_album_recent, artist_recency, tag overlap, exactness, popularity, and guardrail flags.

#### 66ff896f-fcbc-4c42-9d69-b0b5b5ae5a56::t3

- Class type: failure
- GT: Hungry Heart by Bruce Springsteen
- Ranks: final=33; fused=15; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A trained scorer should consume branch ranks, role labels, same_album_recent, artist_recency, tag overlap, exactness, popularity, and guardrail flags.

#### c4c0c288-dbcd-4970-ad52-901aafe91b88::t1

- Class type: failure
- GT: Electric Relaxation by A Tribe Called Quest
- Ranks: final=22; fused=11; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: A trained scorer should consume branch ranks, role labels, same_album_recent, artist_recency, tag overlap, exactness, popularity, and guardrail flags.

### POS_exact_entity_success_control

- Class type: positive_control
- Turns: 10 sampled; target=10
- Hypothesis: Exact or very explicit entity cases should remain solved after any state/ranker change.
- State targets: exact_reference_guard
- State terms to check: kind, value/id, confidence, protect_topk.
- Success metric: All sampled exact-entity controls remain final@20 after state/routing/ranker changes.

#### 0681d55b-98a0-4773-a9df-075a8050d805::t1

- Class type: positive_control
- GT: Numb by Linkin Park
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: No change should demote exact named-track candidates or break entity lookup.

#### 8bee6f03-8cae-44ae-9325-455dc1138549::t1

- Class type: positive_control
- GT: Africa by TOTO, Toto
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: No change should demote exact named-track candidates or break entity lookup.

#### d62387d0-3743-4ddc-bc92-8204c951ccee::t1

- Class type: positive_control
- GT: In the End by Linkin Park
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: No change should demote exact named-track candidates or break entity lookup.

#### bd2aa024-68e7-43c2-aa87-afce9b4d7cf1::t2

- Class type: positive_control
- GT: Shut Up and Dance by WALK THE MOON
- Ranks: final=2; fused=2; best_branch=1 (bm25)
- Expected change: No change should demote exact named-track candidates or break entity lookup.

#### 028027d3-ad67-4cfb-baca-516772ae7399::t1

- Class type: positive_control
- GT: Toxic by Britney Spears
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: No change should demote exact named-track candidates or break entity lookup.

#### fada63d6-1275-47a1-b3ab-30eae222fd72::t1

- Class type: positive_control
- GT: Toxic by Britney Spears
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: No change should demote exact named-track candidates or break entity lookup.

#### 7c3154c5-d1c2-4f07-9b8d-96d187334f1b::t1

- Class type: positive_control
- GT: Way Down We Go by Kaleo, KALEO
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: No change should demote exact named-track candidates or break entity lookup.

#### ba3da7b0-1e81-4d2a-90fa-65ee1f4d7348::t1

- Class type: positive_control
- GT: Heart-Shaped Box by Nirvana
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: No change should demote exact named-track candidates or break entity lookup.

#### 3664db63-1623-4ae7-9910-dd8bc3c2bd83::t1

- Class type: positive_control
- GT: No Scrubs by TLC
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: No change should demote exact named-track candidates or break entity lookup.

#### 7b550636-72fe-490e-ad38-a1912d08449f::t1

- Class type: positive_control
- GT: Believe by Cher
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: No change should demote exact named-track candidates or break entity lookup.

### POS_clean_final_hit_control

- Class type: positive_control
- Turns: 10 sampled; target=10
- Hypothesis: Clean final hits should stay stable while failure classes improve.
- State targets: role_typed_entities; album_artist_recency_features; positive_tag_compatibility
- State terms to check: For each entity: type, value/id, role, source_turn, use_as_retrieval_seed.
- State terms to check detail: No new extractor field required; compute same_album_recent, same_artist_recent, and recency deltas from history.
- State terms to check detail: canonical tag, role, confidence, source_turn.
- Success metric: All sampled clean-hit controls remain final@20; ranks should not degrade materially.

#### 737a65cf-9c45-4b1d-910d-2f1f1ef5eab7::t8

- Class type: positive_control
- GT: Feel Good Inc by Gorillaz
- Ranks: final=7; fused=1; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: State/routing/ranker changes should preserve final@20 and avoid introducing rejection/year/exact regressions.

#### 4a02d862-623b-4fab-a42c-2905f31a96db::t1

- Class type: positive_control
- GT: Dreams - 2004 Remaster by Fleetwood Mac
- Ranks: final=4; fused=5; best_branch=1 (bm25)
- Expected change: State/routing/ranker changes should preserve final@20 and avoid introducing rejection/year/exact regressions.

#### 5b44bff3-76ed-495e-9dc1-0f075e3d178b::t1

- Class type: positive_control
- GT: Dreams - 2004 Remaster by Fleetwood Mac
- Ranks: final=9; fused=25; best_branch=1 (lookup.era_popularity)
- Expected change: State/routing/ranker changes should preserve final@20 and avoid introducing rejection/year/exact regressions.

#### a61b366c-8cf5-48ad-a13f-181c033b9d89::t2

- Class type: positive_control
- GT: Pumped Up Kicks by Foster The People
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: State/routing/ranker changes should preserve final@20 and avoid introducing rejection/year/exact regressions.

#### 55388720-92b7-4972-9bb2-beb37c33c86b::t1

- Class type: positive_control
- GT: Ivy by Frank Ocean
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: State/routing/ranker changes should preserve final@20 and avoid introducing rejection/year/exact regressions.

#### 13552d56-f3d8-443a-9272-11ec16c80fa1::t1

- Class type: positive_control
- GT: Congratulations by Quavo, Post Malone
- Ranks: final=13; fused=13; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: State/routing/ranker changes should preserve final@20 and avoid introducing rejection/year/exact regressions.

#### 737a65cf-9c45-4b1d-910d-2f1f1ef5eab7::t3

- Class type: positive_control
- GT: DARE by Gorillaz
- Ranks: final=4; fused=15; best_branch=1 (bm25)
- Expected change: State/routing/ranker changes should preserve final@20 and avoid introducing rejection/year/exact regressions.

#### 93199894-d3db-4335-8278-e1be175944e4::t1

- Class type: positive_control
- GT: Even Flow by Pearl Jam
- Ranks: final=1; fused=1; best_branch=1 (bm25)
- Expected change: State/routing/ranker changes should preserve final@20 and avoid introducing rejection/year/exact regressions.

#### a9b423bf-d05c-418d-98af-2a3b1e1d7917::t1

- Class type: positive_control
- GT: It Was A Good Day by Ice Cube
- Ranks: final=2; fused=2; best_branch=1 (lookup.resolved_artist_discography)
- Expected change: State/routing/ranker changes should preserve final@20 and avoid introducing rejection/year/exact regressions.

#### 5080d5a0-336e-4bd1-b5bc-4cc611983429::t1

- Class type: positive_control
- GT: Rock with You - Single Version by Michael Jackson
- Ranks: final=1; fused=1; best_branch=1 (dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b)
- Expected change: State/routing/ranker changes should preserve final@20 and avoid introducing rejection/year/exact regressions.


## Entity Role Taxonomy

### SEED

- Cue: "similar to / like / in the vein of X"
- Desired behavior: anchor ON (this is the one case binary gets right)
- Evidence: Current-user GT artist named: n=1,671, union@20=90.2%; exact named-track slice has n=92.

### SATISFIED

- Cue: "X was great, now more / other / else"
- Desired behavior: anchor OFF, decay — user got X, wants beyond it
- Evidence: Stale positive artist/track state appears in 3,807 turns; many are prior played artists that should be context, not fresh anchors.

### CONTRAST

- Cue: "different from / not like / besides / instead of X"
- Desired behavior: anchor OFF, optionally repel
- Evidence: Contrast-cue turns: n=81; novelty + prior-anchor conflicts: n=3,157.

### HISTORY

- Cue: X named in an earlier turn, NOT this one
- Desired behavior: DROP entirely from current targets
- Evidence: Roleless history is the broadest defect: n=3,807, detected when positive entities are absent from the current user turn.

### REJECTED

- Cue: "not X / no more X / stop X"
- Desired behavior: hard drop (already correct)
- Evidence: Explicit rejection state exists in 995 turns; leak audit flags 159 turns.


### Role Bug Examples

#### e0631f94 t4

- Ask: "Dorothy is awesome... more ARTISTS with powerful female vocalists"
- Anchored: Dorothy, Gun In My Hand
- Ideal: Dorothy should be marked “satisfied” (done, don’t search for it). The search should use the style tags (female vocalist, blues-rock) to find NEW artists with a similar sound.

#### b4550ccd t6

- Ask: "Funky Child is awesome... what else can you hit me with that kind [of vibe]"
- Anchored: 11 artists: Eminem, Method Man, CZARFACE, Lupe Fiasco, Freddie Gibbs...
- Ideal: Only Funky Child is relevant (and it's already heard — mark it 'satisfied'). All 11 old artists should be dropped from active search. Use classic/hip-hop style tags to find something new.

#### 58855168 t8

- Ask: "...keen to discover something NEW now, a DIFFERENT artist entirely" than Enya
- Anchored: Enya
- Ideal: Enya should be marked 'contrast' — meaning actively steer AWAY from Enya's sound. Use ambient/atmospheric style tags but search for genuinely different artists.

#### 39d9709b t3

- Ask: "...another band, completely DIFFERENT [from Tenacious D]. Heavy industrial dark"
- Anchored: Tenacious D, Master Exploder
- Ideal: Tenacious D should be marked 'contrast' — meaning steer AWAY from it. The search should be driven by the style the user asked for: industrial, heavy, dark.

#### f8d468c3 t8

- Ask: "I like Snow Patrol... just send more alternative rock, ANYTHING"
- Anchored: Nothing But Thieves, MISSIO
- Ideal: Drop Nothing But Thieves and MISSIO (they're history, not current). Snow Patrol is 'satisfied' (already discussed). Cast a wide net with broad alternative-rock style tags — the user literally said 'anything.'


## Continuation Deep Dive

Continuation turns are 3,223 turns with final@20 46.3%, union@20 83.3%, and union@100 93.6%. Primary-album continuations are 2,023 turns with final@20 51.7% and union@20 88.8%. The broader any-album sensitivity is 2,249 turns.

### Right artist IN our top-20, wrong track

- Turns: 916
- Share: 53.0%
- Cause: within-artist RANKING — we return the artist's popular track, GT is a deep cut / next album track
- Fix: sequence/album-aware discography (predict the NEXT track of the artist/album, not their hit). Artist already surfaced → cheap, high-confidence.

### Heard artist NOT surfaced at all

- Turns: 814
- Share: 47.0%
- Cause: the relevant (recent) artist crowded out by competing stale anchors
- Fix: keep-strength: weight the MOST-RECENT artist up, decay older anchors so they stop crowding the pool.

### Album-affinity current cohort

- Turns: 2,249
- Final@20: 51.4%
- Union@20: 88.3%
- Primary miss fused buckets: fused<=20/final-missed=454; 21-100=301; 101-1000=90; absent=133; sum=978
- Action: Prototype album-affinity and recent-artist features inside a ranker over union@100/200; track continuation NDCG@20 separately.


## New-Artist Deep Dive

Mid-conversation new-artist turns are 3,777 turns with final@20 10.0%, union@20 19.4%, and union@100 44.9%. Even explicit novelty-cue + new-artist turns are weak: n=1,990, final@20 9.0%, union@20 18.0%.

### Genre-fit AND popular

- Turns: 1,351
- Share: 36.0%
- Cause: GT matches the requested genre and is popular (pop>=50) — a findable new artist we bury
- Fix: genre/era-conditioned POPULARITY prior + cross-session user CF. ~23% of ALL misses. Biggest addressable cell.

### Genre-fit but obscure

- Turns: 1,500
- Share: 39.0%
- Cause: matches genre, low popularity — buried among thousands of genre-mates (broad-tag dilution)
- Fix: stronger item encoders (the hard retrieval-capability gap). Lower ceiling.

### Noise / no-fit

- Turns: 926
- Share: 25.0%
- Cause: 12% organizer DOES_NOT_MOVE + vague no-handle turns
- Fix: accept — GT contradicts the request, unwinnable.


## Organizer Metadata

Current retrieval state is extracted from session_memory. UserProfileDB renders only user_id, age_group, gender, and country_name for response generation; conversation_goal and preferred_musical_culture are not consumed by current retrieval/ranking. Blind-A raw rows were probed separately: Verified Blind-A raw rows include conversation_goal, user_profile, and goal_progress_assessments on 80/80 rows. Current blindset inference does not pass those objects into retrieval/compiler state.
Category descriptions are derived from observed listener_goal examples in this devset because the local docs do not provide official labels for A-K.

### Blind-A Availability Check

Verified Blind-A raw rows include conversation_goal, user_profile, and goal_progress_assessments on 80/80 rows. Current blindset inference does not pass those objects into retrieval/compiler state.
### Blind-A raw HF rows

- Blind-A status: available
- Evidence: 80 rows in talkpl-ai/TalkPlayData-Challenge-Blind-A test; columns include session_id, user_id, session_date, user_profile, conversation_goal, conversations, goal_progress_assessments.
- Report decision: Organizer metadata is available in Blind-A raw rows; do not pay extractor calls to emulate it first.

### conversation_goal

- Blind-A status: available
- Evidence: missing=0, empty=0; keys=category, listener_goal, specificity.
- Report decision: Thread category, specificity, and listener_goal into retrieval/ranker context when testing metadata features.

### user_profile

- Blind-A status: available
- Evidence: missing=0, empty=0; keys=age, age_group, country_code, country_name, gender, preferred_language, preferred_musical_culture, user_id, user_split.
- Report decision: Use preferred_musical_culture/profile as context or candidate-varying affinity; do not infer demographics from text.

### goal_progress_assessments

- Blind-A status: partially labeled
- Evidence: missing=0, empty=0; keys=goal_progress_assessment, turn_number; non-null assessments=210/290; last-row assessment non-null=60/80.
- Report decision: Use with leakage review. Visible progress can be useful, but do not treat it as a hidden GT label.

### current blindset inference path

- Blind-A status: metadata dropped before retrieval
- Evidence: run_inference_blindset.py builds batch_data with user_query, user_id, and session_memory only; output metadata keeps session_id, user_id, turn_number.
- Report decision: The next implementation step is plumbing available metadata into the compiler/ranker input, not emulating Blind-A metadata.


### Use vs Emulate / Extract Decision

### conversation_goal.listener_goal

- Available as: Organizer session-level natural-language goal; verified present in Blind-A raw rows.
- Use directly: Yes. Feed as immutable session context for routing/query text and as a goal-text compatibility feature.
- Emulate or extract: Do not emulate for Blind-A: it is available. Only extract a replacement for a future split that lacks listener_goal.
- Ranking shape: Candidate-varying goal_text_match, goal-conditioned popularity, or retrieval profile; not a raw constant score.
- First test: First plumb listener_goal through run_inference_blindset/devset batch inputs; then compare novelty/broad-goal packs with and without it.

### conversation_goal.category A-K

- Available as: Organizer session-level code with no official local codebook; verified present in Blind-A raw rows.
- Use directly: Use for slicing, guardrails, and coarse route priors when available.
- Emulate or extract: Do not spend extractor calls predicting A-K for Blind-A. If useful, derive operational route labels from listener_goal/state instead of matching organizer codes.
- Ranking shape: Category-conditioned retriever profile or evaluation slice; raw category is candidate-constant within a turn.
- First test: Measure union@20/final@20 by A-K and only promote categories that map to different successful retriever profiles.

### conversation_goal.specificity LL/LH/HL/HH

- Available as: Organizer session-level specificity code; verified present in Blind-A raw rows, but official axis definitions are not in local docs.
- Use directly: Use as guardrail slices: HH exactness should not regress; LL broad discovery needs better candidate generation.
- Emulate or extract: Do not emulate the code itself for Blind-A. If needed, extract simpler operational fields: exactness_required, broad_discovery, constraint_strength.
- Ranking shape: Route exact/high-specificity turns toward entity protection; route low-specificity turns toward popularity/CF/tag exploration.
- First test: Run exact-reference controls by HH-like turns and novelty-popularity packs by LL-like turns.

### user_profile.preferred_musical_culture

- Available as: Organizer user-profile field; verified present in Blind-A raw rows and standalone user metadata.
- Use directly: Use as context for culture-conditioned popularity, CF priors, and response style.
- Emulate or extract: Do not infer culture from conversation when profile is present; that is noisy and can create bias/leakage.
- Ranking shape: Candidate-varying culture/user affinity, not a constant feature attached to every candidate.
- First test: Test culture-conditioned popularity or user-CF affinity on new-artist and popularity-cue packs.

### age_group, gender, country, preferred_language

- Available as: Organizer user-profile demographics and language metadata; verified present in Blind-A raw rows.
- Use directly: Use mainly for response style, analysis slices, leakage/fairness checks, and maybe language/local catalog priors.
- Emulate or extract: Do not extract or infer these from conversation text.
- Ranking shape: Only candidate-varying features after validation; raw demographics showed no within-turn ranking lift as constants.
- First test: Keep as guardrail slices while testing stronger behavioral features first.

### goal_progress_assessments

- Available as: Organizer turn-level assessment labels; structurally present in Blind-A raw rows and partially populated.
- Use directly: Use only after leakage review. Prior visible progress may help; the current row's assessment should be treated carefully.
- Emulate or extract: Do not emulate first. If used, prefer visible previous-turn labels and audit current-turn labels for leakage.
- Ranking shape: Satisfaction/move-on signal, not a hidden GT label.
- First test: Ablate previous-turn assessment features separately from conversation text/state features and inspect exact-target cases.


### Specificity Codes

### LL

- Sessions: 278
- Share: 27.8%
- Meaning: Low / low specificity: observed goals are broad discovery or multi-item asks with weak exact-entity constraints.
- Example goal: explore and discover new ambient and downtempo electronic music, refining the sound based on mood and preference

### LH

- Sessions: 313
- Share: 31.3%
- Meaning: Low / high specificity: observed goals often name a target type or memory, but the surface clue is vague.
- Example goal: identify one specific artist (VNV Nation) or find their defining song(s) from a vague description of their electronic, epic, and introspective style.

### HL

- Sessions: 307
- Share: 30.7%
- Meaning: High / low specificity: observed goals have concrete genres, artists, eras, or journey constraints but multiple acceptable tracks.
- Example goal: find multiple songs from punk and hardcore punk artists with specific sub-genre characteristics, lyrical themes, or historical periods.

### HH

- Sessions: 102
- Share: 10.2%
- Meaning: High / high specificity: observed goals often identify exact titles, artists, lyrics, albums, or tightly constrained targets.
- Example goal: play one specific song that is known for its high popularity within its genre or era.


### Category Codes

### Category A

- Sessions: 61
- Share: 6.1%
- Observed pattern: sonic/audio characteristics, instrumentation, tempo, or production feel
- Example goal: find one specific instrumental track from "The Elder Scrolls Online Original Game Soundtrack" remembered by its distinctive orchestral sound, mood, or thematic quality (e.g., a...

### Category B

- Sessions: 142
- Share: 14.2%
- Observed pattern: lyrics, lyrical phrase, theme, story, or named lyrical content
- Example goal: find a specific song by its exact lyrical phrase

### Category C

- Sessions: 58
- Share: 5.8%
- Observed pattern: album art / cover-art visual memory or visual-mood matching
- Example goal: find one specific album remembered by its distinctive, dark, and abstract or unsettling cover art.

### Category D

- Sessions: 86
- Share: 8.6%
- Observed pattern: situational use case, soundtrack memory, activity, or scene mood
- Example goal: find one specific song from the Moana soundtrack that evokes a sense of epic journey and exploration, but the listener can't remember its exact title.

### Category E

- Sessions: 95
- Share: 9.5%
- Observed pattern: guided progression through a musical journey or preference refinement
- Example goal: progress through a specific musical journey from classic EBM to modern synthpop and futurepop, emphasizing melodic elements and avoiding overly harsh industrial sounds

### Category F

- Sessions: 95
- Share: 9.5%
- Observed pattern: specific era, artist, subgenre, or catalog constraint discovery
- Example goal: find multiple electronic/dance tracks from the late 90s and early 2000s with specific characteristics (e.g., energetic, downtempo, vocal-focused)

### Category G

- Sessions: 77
- Share: 7.7%
- Observed pattern: emotional outcome: uplifting, comfort, grief, hope, or mood regulation
- Example goal: find some positive and uplifting hip-hop tracks to boost my energy and put me in a good mood.

### Category H

- Sessions: 135
- Share: 13.5%
- Observed pattern: specific artist/song/composer or subgenre identity from vague clues
- Example goal: find multiple songs from punk and hardcore punk artists with specific sub-genre characteristics, lyrical themes, or historical periods.

### Category I

- Sessions: 18
- Share: 1.8%
- Observed pattern: globally popular or internationally recognizable exact/near-exact targets
- Example goal: play a specific globally popular song by exact title and artist

### Category J

- Sessions: 77
- Share: 7.7%
- Observed pattern: popularity within genre/era, classics, hits, or culturally defining songs
- Example goal: play one specific song that is known for its high popularity within its genre or era.

### Category K

- Sessions: 156
- Share: 15.6%
- Observed pattern: broad discovery by era/style/aesthetic with looser starting constraints
- Example goal: discover multiple instrumental pieces from a broad era, particularly film scores or contemporary classical works, that evoke a timeless or classic feel.


### User Profile Fields

### age

- Current use: available in organizer metadata; not used by current retrieval/ranking
- Recommended use: available inline; not rendered by UserProfileDB default profile string

### age_group

- Current use: rendered in UserProfileDB profile string
- Recommended use: rendered in response-generation profile string; weak diagnostic/personalization feature

### country_code

- Current use: available in organizer metadata; not used by current retrieval/ranking
- Recommended use: available inline; not rendered by default profile string

### country_name

- Current use: rendered in UserProfileDB profile string
- Recommended use: rendered in response-generation profile string; weak cultural/localization feature

### gender

- Current use: rendered in UserProfileDB profile string
- Recommended use: rendered in response-generation profile string; diagnostics/guardrails only

### preferred_language

- Current use: available in organizer metadata; not used by current retrieval/ranking
- Recommended use: available inline; useful for response style and weak language/culture cues

### preferred_musical_culture

- Current use: available in organizer metadata; not used by current retrieval/ranking
- Recommended use: available inline; highest-value user metadata feature to test for router/ranker personalization

### user_id

- Current use: rendered in UserProfileDB profile string
- Recommended use: join key; passed through inference, not a semantic ranker feature

### user_split

- Current use: available in organizer metadata; not used by current retrieval/ranking
- Recommended use: organizer split marker; diagnostic only


## Measured Lever Evidence

### Album-affinity / album completion

- Status: measured counterfactual
- Result: 479 of 964 same-album misses are rescuable from fused rank 21-100; 326 sit at 101-1000 and 159 are absent. Reported ceiling: about +6pp Hit@20.
- Decision: Keep as a P0 ranker feature: same_album_recent plus artist_recency, with continuation and new-artist guardrails.
- Source: album counterfactual audit

### Current trace album fused-rank anatomy

- Status: trace recount
- Result: Primary-album misses=978; fused<=20/final-missed=454, fused 21-100=301, fused 101-1000=90, absent=133; bucket sum=978.
- Decision: Read fused<=20 as post-fusion/finalization loss, not album-retrieval absence.
- Source: current trace rows

### RRF-fused cross-encoder reranker

- Status: measured adjacent-pool bakeoff
- Result: NDCG@20 0.1415 -> 0.1594 (12.7% relative); Hit@20 0.3098 -> 0.3325. Scope: Adjacent full-devset reranker bakeoff on v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset, not the all-retrievers trace in this report.
- Decision: Use rank fusion or a trained scorer over RRF/branch features; do not replace RRF with raw cross-encoder score.
- Source: cross_encoder_rerank_bakeoff.md

### Candidate-level is_new_artist feature

- Status: measured small positive
- Result: +1% reranker on novelty
- Decision: Use as a ranker feature, but still fix candidate generation because new-artist GTs are often outside union@20.
- Source: feature experiment audit

### Raw session/category/demographic features in a within-turn ranker

- Status: measured no lift
- Result: 0 lift — candidate-constant within a turn.
- Decision: Do not feed raw constants directly; derive candidate-varying culture/user-CF/popularity affinity or use them for routing/slicing.
- Source: feature-ablation audit

### Rarity-weighted / IDF tags

- Status: measured negative
- Result: WORSE than raw; tags cap ~0.19 hit@50.
- Decision: Do not prioritize IDF-tag weighting; tags are useful, but role/routing and candidate-varying behavioral features are stronger.
- Source: feature-ablation audit


## Ranker Feature Catalog

### candidate_artist_role

- Grain: turn x candidate
- Why: Separates seed, satisfied, contrast, history, and rejected entities instead of treating all positive mentions as anchors.
- Validation: Lower stale positive state rate; improve new-artist union@20 without exact/continuation regression.

### artist_recency / keep_strength

- Grain: turn x candidate artist
- Why: Continuation needs the most recent relevant artist, while novelty needs older anchors decayed.
- Validation: Continuation NDCG@20 up; new-artist candidate gap not worse.

### same_album_recent

- Grain: turn x candidate album
- Why: Album-mates are highly retrievable and often rank just outside top-20.
- Validation: Same-album continuation final@20/NDCG@20; inspect same-artist diversity side effects.

### is_new_artist_for_session

- Grain: turn x candidate artist
- Why: Novelty asks should favor unseen artists; continuation asks should not.
- Validation: New-artist union/final@20 by novelty-cue slice; continuation guardrail.

### genre_or_era_conditioned_popularity

- Grain: turn x candidate
- Why: Broad novelty asks often need a canonical/popular candidate within requested tags or era.
- Validation: Lift on popularity-cue and LL/J/K slices without generic popularity takeover.

### user_cf_or_culture_affinity

- Grain: turn x candidate
- Why: Raw demographics are candidate-constant, but user/culture affinity varies by track.
- Validation: Session-grouped CV; preferred_musical_culture slices; no user-id leakage.

### constraint_satisfaction

- Grain: turn x candidate
- Why: Year and rejection state should be modeled/guarded, not allowed to silently suppress valid targets or leak invalid ones.
- Validation: Zero rejection leaks; lower year-excludes-GT miss rate; no exact-turn regression.

### branch_rank_bundle

- Grain: turn x candidate
- Why: Replacing RRF needs the ranker to see which branch found the candidate and at what rank.
- Validation: Session-grouped CV over union@100/200 beats RRF on NDCG@20.


## What Not To Work On First

### Use union@1000 as the ranker target

- Decision: Do not headline it.
- Evidence: Union@1000 is 90.5%, but it is an oracle over very large branch pools. Use union@20 as the gap line and union@100/200 as ranker workbench.

### Feed raw category/specificity/demographics directly into a within-turn ranker

- Decision: Use them as slices or derive candidate-varying features.
- Evidence: Category, specificity, and demographics are session constants within a candidate list. They can condition retrieval/ranker behavior but cannot distinguish candidate A vs B unless transformed.

### Overhaul tag extraction first

- Decision: Not first.
- Evidence: Positive tags overlap a GT tag on 76.9% of tagged turns; entity role/recency has a broader and clearer failure signature.

### Tune RRF alone

- Decision: Insufficient.
- Evidence: New-artist union@20 is only 19.4%. RRF replacement helps near misses, not absent candidates.

### Replace RRF with raw cross-encoder score

- Decision: Do not use replace mode.
- Evidence: The adjacent reranker bakeoff found replace-mode reranking structurally harmful; rank-fuse RRF and reranker scores or train a scorer over branch/state features.

### IDF-weight positive tags

- Decision: Not first.
- Evidence: WORSE than raw; tags cap ~0.19 hit@50.


## Counting Caveats And Reconciliation

### GT primary album already heard

- Report value: 2,023
- Alternate value: 2,249 any-album
- Basis: Primary/first album_id is the conservative continuation count; any album_id overlap includes multi-album catalog metadata.
- Decision: Use primary-album as the canonical strict album-continuation count; keep any-album as broader sensitivity.

### Album miss fused-rank buckets

- Report value: primary misses=978; buckets sum=978
- Alternate value: album counterfactual miss_total=964; 21-100=479; 101-1000=326; absent=159
- Basis: The current report's trace proxy buckets by fused_rank and now includes fused<=20/final-missed rows; the album-completion counterfactual uses a separate replay denominator.
- Decision: Use the trace proxy for failure anatomy and the counterfactual for measured upside. Do not compare raw bucket values without the denominator.

### Rejection leak turns

- Report value: 159
- Alternate value: 97 strict ID; 62 additional name-only
- Basis: Broad audit catches rejected track/artist IDs plus explicit rejection names; strict audit only counts resolver IDs.
- Decision: Treat broad count as an upper audit bound and strict count as the verified lower bound until a hand sample labels name-only cases.

### Routing tag counts

- Report value: exact_entity_probe=1,605; hidden_target_search=391
- Alternate value: Sample extrapolations can differ.
- Basis: Full trace pass counts active boolean routing tags on all 8,000 rows.
- Decision: Keep the full-trace counts. The important bug is not extraction frequency; routing_boost is empty, so tags are not consumed by weighted routing.

### Current user names GT artist

- Report value: 1,671
- Alternate value: Alias/partial-name methods can move the count by roughly tens of turns.
- Basis: Lexical phrase match against catalog artist_name values in the current user turn.
- Decision: Rates are the stable takeaway: named-artist turns have very high union@20 but lower final@20, so they are a track-selection/ranking slice.

### Stale positive entity turns

- Report value: 3,807
- Alternate value: More inclusive substring heuristics count slightly more.
- Basis: Positive artist/track state value not lexically present in the current user turn.
- Decision: Use as a directional state QA metric, not a perfect semantic label.

### Exact named-track turns

- Report value: 92
- Alternate value: Looser title-substring methods count more.
- Basis: Strict current-turn track-title match with safeguards for short/common titles.
- Decision: Keep the stricter count to avoid false positives from common words.


### Full Trace Routing Counts

### feature_articulation

- Active turns: 6,748
- Consumed: no weighted routing effect because config routing_boost is empty

### exact_entity_probe

- Active turns: 1,605
- Consumed: no weighted routing effect because config routing_boost is empty

### hidden_target_search

- Active turns: 391
- Consumed: no weighted routing effect because config routing_boost is empty

### image_or_visual_search

- Active turns: 268
- Consumed: no weighted routing effect because config routing_boost is empty

### lyric_search

- Active turns: 82
- Consumed: no weighted routing effect because config routing_boost is empty


## Experiment Backlog And Measurement Contract

### Role-typed entity-state extractor QA

- Status: not run in this report
- Why: Diagnostics show stale/roleless entity state, but the extractor/schema change needs a before/after run.
- Measurement: stale positive entity rate, novelty-prior-anchor conflict count, final/union@20 by new-artist and continuation.

### Album-affinity / artist-recency ranker A/B

- Status: measured counterfactual exists; implementation A/B still needed
- Why: Primary-album misses=978; fused<=20/final-missed=454; fused 21-100=301; fused 101-1000=90; fused absent=133. Any-album sensitivity misses=1,092.
- Measurement: session-grouped CV or replayed scorer over union@100/200; continuation NDCG@20, same-album final@20, new-artist guardrail.

### Routing-boost configuration A/B

- Status: not run in this report
- Why: Routing tags fire 9,094 times, but routing_boost is empty; this means turn-type signals are not changing branch weights.
- Measurement: Run explicit routing profiles by tag; report union@20/100 by exact_entity_probe, hidden_target_search, feature_articulation, novelty, and continuation slices.

### Novelty retriever profile A/B

- Status: not run in this report
- Why: New-artist union@20 is 19.4%; ranker changes cannot rescue absent candidates.
- Measurement: new-artist and novelty-cue union@20/100 first, then final@20/NDCG@20.

### No-year / soft-year penalty ablation

- Status: not run in this report
- Why: 634 turns have a release range that excludes the GT year.
- Measurement: release-range slice final@20/NDCG@20 and exact/HH guardrails.

### Strict rejection assertion replay

- Status: not run in this report
- Why: Strict ID leak lower bound is 97; broad name audit adds 62 cases.
- Measurement: zero strict leaks after finalization; hand-label name-only sample for false positives.

### IDF-tag / session-feature tests

- Status: already de-prioritized by feature-ablation measurements
- Why: Positive tag overlap is 76.9%, while entity role/recency has a larger confirmed failure surface.
- Measurement: Session/demographic raw features show 0 lift as candidate constants; IDF tags were worse than raw. Revisit only as candidate-varying affinity/tag-precision features.


## Validated State Defects

### Roleless or stale state entities

- Turns: 3,807
- Share: 47.6%
- Final@20: 27.7%
- Union@20: 50.8%
- Work: Add entity role and decay: seed, satisfied, contrast, history, rejected. Drop history from current anchors.

### Novelty asks keep old anchors

- Turns: 3,157
- Share: 39.5%
- Final@20: 28.3%
- Union@20: 52.0%
- Work: Make novelty/diversify state lower prior-artist centroid and discography influence unless the user asks for same artist.

### Era state contradicts GT release year

- Turns: 634
- Share: 7.9%
- Final@20: 5.8%
- Union@20: 26.7%
- Work: Distinguish hard release constraints from stylistic-era cues; use softer penalties and audit 80s/90s style wording.

### Rejected entities leak into top-20

- Turns: 159
- Share: 2.0%
- Final@20: 25.2%
- Union@20: 56.0%
- Work: Add a deterministic post-final assertion and fix multi-artist/name/id rejection matching.

### Exact named-track misses

- Turns: 0
- Share: 0.0%
- Final@20: n/a
- Union@20: n/a
- Work: Treat exact named tracks as a protected retrieval and finalization path.


## Failure Example Explanations


### Stale Artist Or Track State

#### ae45c487-5dfa-48c5-bfd7-c54727ebeb9e turn 4

- GT: Give Me Everything (feat. Ne-Yo, Afrojack & Nayer) by Pitbull, Afrojack, Ne-Yo
- Ranks: final=-; branch=321 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Why wrong: The extracted release range (1990, 2004) excludes the target release year 2011. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away before ranking.
- What should change: Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- Regression test: Run a no-year and soft-year replay for this turn; the target should remain eligible, and exact/HH turns should not regress when explicit date constraints are present.

#### 391b1c73-8778-4087-a933-6ef24495b488 turn 7

- GT: Closer by The Chainsmokers, Halsey
- Ranks: final=-; branch=170 (dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b)
- Why wrong: The user asks for novelty or a different direction, but the state still keeps Coldplay, The Script as positive anchors. That sends retrievers toward already-satisfied artists instead of the new target space.
- What should change: Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- Regression test: Replay this turn and assert prior anchors are marked satisfied/history, not current seed; measure union@20/100 for novelty + new-artist turns before checking final ranking.

#### 73a85b67-a5fa-4932-927d-ea3d04f7558e turn 4

- GT: Hips Don't Lie by Wyclef Jean, Shakira
- Ranks: final=-; branch=- (NONE)
- Why wrong: The user asks for novelty or a different direction, but the state still keeps Bikini Kill as positive anchors. That sends retrievers toward already-satisfied artists instead of the new target space.
- What should change: Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- Regression test: Replay this turn and assert prior anchors are marked satisfied/history, not current seed; measure union@20/100 for novelty + new-artist turns before checking final ranking.

#### 87727ed3-8330-4269-9f05-a763fcf10ece turn 4

- GT: Hips Don't Lie by Wyclef Jean, Shakira
- Ranks: final=-; branch=- (NONE)
- Why wrong: The state still treats Kendrick Lamar, Alright, King Kunta as positive artist/track evidence even though it is not present in the current user turn.
- Why wrong detail: This can over-anchor retrieval on conversation history rather than the current ask.
- What should change: Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- Regression test: Replay state extraction for this turn and assert stale entities are not emitted as current positive anchors; then compare branch union for current-turn target candidates.

#### 27f40adb-daa8-4622-85f0-d52aca96ae5e turn 4

- GT: Outside (feat. Ellie Goulding) by Calvin Harris, Ellie Goulding
- Ranks: final=-; branch=- (NONE)
- Why wrong: The state still treats Bonobo as positive artist/track evidence even though it is not present in the current user turn. This can over-anchor retrieval on conversation history rather than the current ask.
- What should change: Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions them. The resolver should expose current-vs-history roles to retrievers and the ranker.
- Regression test: Replay state extraction for this turn and assert stale entities are not emitted as current positive anchors; then compare branch union for current-turn target candidates.


### Novelty Prior Anchor Conflict

#### ae45c487-5dfa-48c5-bfd7-c54727ebeb9e turn 4

- GT: Give Me Everything (feat. Ne-Yo, Afrojack & Nayer) by Pitbull, Afrojack, Ne-Yo
- Ranks: final=-; branch=321 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Why wrong: The extracted release range (1990, 2004) excludes the target release year 2011. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away before ranking.
- What should change: Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- Regression test: Run a no-year and soft-year replay for this turn; the target should remain eligible, and exact/HH turns should not regress when explicit date constraints are present.

#### 17aa1a9b-7642-462e-a4ef-cfe3138cc5c5 turn 7

- GT: Without Me by Eminem
- Ranks: final=-; branch=- (NONE)
- Why wrong: The user asks for novelty or a different direction, but the state still keeps Yung Lean as positive anchors. That sends retrievers toward already-satisfied artists instead of the new target space.
- What should change: Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- Regression test: Replay this turn and assert prior anchors are marked satisfied/history, not current seed; measure union@20/100 for novelty + new-artist turns before checking final ranking.

#### 391b1c73-8778-4087-a933-6ef24495b488 turn 7

- GT: Closer by The Chainsmokers, Halsey
- Ranks: final=-; branch=170 (dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b)
- Why wrong: The user asks for novelty or a different direction, but the state still keeps Coldplay, The Script as positive anchors. That sends retrievers toward already-satisfied artists instead of the new target space.
- What should change: Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- Regression test: Replay this turn and assert prior anchors are marked satisfied/history, not current seed; measure union@20/100 for novelty + new-artist turns before checking final ranking.

#### 73a85b67-a5fa-4932-927d-ea3d04f7558e turn 4

- GT: Hips Don't Lie by Wyclef Jean, Shakira
- Ranks: final=-; branch=- (NONE)
- Why wrong: The user asks for novelty or a different direction, but the state still keeps Bikini Kill as positive anchors. That sends retrievers toward already-satisfied artists instead of the new target space.
- What should change: Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- Regression test: Replay this turn and assert prior anchors are marked satisfied/history, not current seed; measure union@20/100 for novelty + new-artist turns before checking final ranking.

#### 942c0b23-c5ad-4270-b23f-3ba456ea0ccf turn 7

- GT: Thunderstruck by AC/DC
- Ranks: final=500; branch=204 (centroid.user.cf_bpr)
- Why wrong: The user asks for novelty or a different direction, but the state still keeps Silverchair as positive anchors. That sends retrievers toward already-satisfied artists instead of the new target space.
- What should change: Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles.
- Regression test: Replay this turn and assert prior anchors are marked satisfied/history, not current seed; measure union@20/100 for novelty + new-artist turns before checking final ranking.


### Release Range Excludes Gt

#### ae45c487-5dfa-48c5-bfd7-c54727ebeb9e turn 4

- GT: Give Me Everything (feat. Ne-Yo, Afrojack & Nayer) by Pitbull, Afrojack, Ne-Yo
- Ranks: final=-; branch=321 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Why wrong: The extracted release range (1990, 2004) excludes the target release year 2011. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away before ranking.
- What should change: Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- Regression test: Run a no-year and soft-year replay for this turn; the target should remain eligible, and exact/HH turns should not regress when explicit date constraints are present.

#### 1f2bf564-8265-412c-9aa8-e208d8f4e780 turn 1

- GT: Shut Up and Dance by WALK THE MOON
- Ranks: final=-; branch=- (NONE)
- Why wrong: The extracted release range (1980, 1989) excludes the target release year 2014. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away before ranking.
- What should change: Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- Regression test: Run a no-year and soft-year replay for this turn; the target should remain eligible, and exact/HH turns should not regress when explicit date constraints are present.

#### cee75c83-bd55-43ae-98aa-c9ab97dc307e turn 8

- GT: Timber (feat. Ke$ha) by Pitbull, Kesha
- Ranks: final=-; branch=- (NONE)
- Why wrong: The extracted release range (1990, 1999) excludes the target release year 2012. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away before ranking.
- What should change: Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- Regression test: Run a no-year and soft-year replay for this turn; the target should remain eligible, and exact/HH turns should not regress when explicit date constraints are present.

#### 60fe2a68-222b-41b0-914b-c315b15f0c2c turn 8

- GT: Back In Black by AC/DC
- Ranks: final=-; branch=232 (dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b)
- Why wrong: The extracted release range (1990, 1995) excludes the target release year 1980. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away before ranking.
- What should change: Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- Regression test: Run a no-year and soft-year replay for this turn; the target should remain eligible, and exact/HH turns should not regress when explicit date constraints are present.

#### 5080d5a0-336e-4bd1-b5bc-4cc611983429 turn 4

- GT: 24K Magic by Bruno Mars
- Ranks: final=-; branch=220 (dense.qwen_8b.metadata.metadata_qwen3_embedding_8b)
- Why wrong: The extracted release range (1977, 1984) excludes the target release year 2016. If this range is treated as a hard constraint or strong demotion, the correct item is pushed away before ranking.
- What should change: Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; only explicit date-bound language should hard-filter or heavily penalize candidates.
- Regression test: Run a no-year and soft-year replay for this turn; the target should remain eligible, and exact/HH turns should not regress when explicit date constraints are present.


### Rejection Leak Top20

#### b4ffa800-8173-4f16-800a-4b5e765d7f80 turn 5

- GT: Wish You Were Here by Pink Floyd
- Ranks: final=782; branch=280 (centroid.anchor_tracks.image_siglip2)
- Why wrong: The state contains an explicit rejection, but final top-20 still includes You Never Give Me Your Money - Remastered by The Beatles, Mean Mr Mustard - Remastered by The Beatles.
- Why wrong detail: That is a strict rejected ID leak, independent of whether the ground-truth target was retrieved.
- What should change: Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- Regression test: For this turn, replay finalization and assert no final slot intersects explicit_rejections by track_id, artist_id, or verified rejected artist name.

#### 9003b58e-05f2-447b-841d-3b8fdc548548 turn 5

- GT: Pyramids by Frank Ocean
- Ranks: final=-; branch=- (NONE)
- Why wrong: The state contains an explicit rejection, but final top-20 still includes Shadowboxin' by GZA. That is a rejected name leak, independent of whether the ground-truth target was retrieved.
- What should change: Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- Regression test: For this turn, replay finalization and assert no final slot intersects explicit_rejections by track_id, artist_id, or verified rejected artist name.

#### b4ffa800-8173-4f16-800a-4b5e765d7f80 turn 6

- GT: Tempo Perdido by Legião Urbana
- Ranks: final=-; branch=312 (dense.clap_text.sonic.audio_laion_clap)
- Why wrong: The state contains an explicit rejection, but final top-20 still includes Hey You by Pink Floyd, Shine On You Crazy Diamond (Pts.
- Why wrong detail: 6-9) by Pink Floyd.
- Why wrong detail: That is a strict rejected ID leak, independent of whether the ground-truth target was retrieved.
- What should change: Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- Regression test: For this turn, replay finalization and assert no final slot intersects explicit_rejections by track_id, artist_id, or verified rejected artist name.

#### ae45c487-5dfa-48c5-bfd7-c54727ebeb9e turn 7

- GT: Never Forget You by MNEK, Zara Larsson
- Ranks: final=-; branch=- (NONE)
- Why wrong: The state contains an explicit rejection, but final top-20 still includes Pop's Rap by Common. That is a rejected name leak, independent of whether the ground-truth target was retrieved.
- What should change: Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- Regression test: For this turn, replay finalization and assert no final slot intersects explicit_rejections by track_id, artist_id, or verified rejected artist name.

#### ca3a5c5c-2c9f-48ac-9e96-7e070d8f3ba9 turn 8

- GT: Life On Mars? - 2015 Remastered Version by David Bowie
- Ranks: final=-; branch=- (NONE)
- Why wrong: The state contains an explicit rejection, but final top-20 still includes A Pocketful Of Stones by David Gilmour. That is a strict rejected ID leak, independent of whether the ground-truth target was retrieved.
- What should change: Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible.
- Regression test: For this turn, replay finalization and assert no final slot intersects explicit_rejections by track_id, artist_id, or verified rejected artist name.


## Hypotheses Tested

### State is worth focusing on before adding more blind retrievers.

- Verdict: validated
- Evidence: Mid-conversation new-artist final@20 is 10.0%; stale/roleless state defects appear in 47.6% of turns.
- Implication: Fix state roles and state-to-retriever routing first; measure union@20/100 by cohort.

### Continuation and new-artist turns need different state use.

- Verdict: validated
- Evidence: Continuation final@20 is 46.3%; new-artist final@20 is 10.0%.
- Implication: One RRF recipe is too blunt; state should select retrieval profile and ranker features.

### Year state can be harmful.

- Verdict: validated with caveat
- Evidence: 634 turns have a range that excludes GT. Some are benchmark/organizer ambiguity, not necessarily extractor errors.
- Implication: Build guardrails and ablations; do not simply delete era extraction.

### Union@1000 should be the ranker target.

- Verdict: not accepted
- Evidence: Union@1000 is 90.5%, but it is thousands of candidates per turn. Union@20 and union@100 are better work boundaries.
- Implication: Use union@20 as the state/retriever gap line and union@100 as the practical near-miss line.


## Sources

- `trace`: `/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl`
- `predictions`: `/Users/npatta01/data/projects/music-conversational-music-recomender-2026/exp/inference/devset/v0plus_compiler_all_retrievers_devset.json`
- `ground_truth`: `/Users/npatta01/data/projects/music-conversational-music-recomender-2026/evaluator/exp/ground_truth/devset.json`
- `config`: `/Users/npatta01/data/projects/music-conversational-music-recomender-2026/configs/v0plus_compiler_all_retrievers_devset.yaml`
- `track_metadata`: `talkpl-ai/TalkPlayData-Challenge-Track-Metadata`
- `conversation_dataset`: `talkpl-ai/TalkPlayData-Challenge-Dataset`
- `docs_data`: `docs/data.md`
- `session_state_docs`: `docs/architectures/session_state.md`
- `user_profile_code`: `mcrs/db_user/user_profile.py`
- `reranker_bakeoff`: `/Users/npatta01/data/projects/music-conversational-music-recomender-2026/.claude/worktrees/interesting-bose-a608d3/experiments/cross_encoder_rerank_bakeoff.md`
