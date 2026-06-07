"""Pydantic v0+ ConversationState schema.

Mirrors iteration_1_minimal_schema.md: 7 LLM-extracted fields, flat where possible,
3-value enums for sentiment, 4-value enum for intent_mode.

Used by:
- The extraction prompt builder (prompts.py) for JSON-schema-constrained outputs.
- The labeling workflow — humans fill these models in for the audit set.
- The scorer (score.py) for per-field F1.
"""

from __future__ import annotations

import re as _re
from datetime import date as _date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class IntentMode(str, Enum):
    open_explore = "open_explore"
    refinement = "refinement"
    pivot = "pivot"
    playlist_build = "playlist_build"


class ExplorationPolicy(str, Enum):
    exploit = "exploit"
    diversify_artists = "diversify_artists"
    diversify_albums = "diversify_albums"
    balanced = "balanced"


class EntityRole(str, Enum):
    current_target = "current_target"
    seed = "seed"
    satisfied = "satisfied"
    history = "history"
    contrast = "contrast"
    rejected = "rejected"


class TargetArtistMode(str, Enum):
    same_artist = "same_artist"
    new_artist = "new_artist"
    any_artist = "any_artist"
    unknown = "unknown"


class RetrievalProfile(str, Enum):
    continuation = "continuation"
    novelty = "novelty"
    exact_probe = "exact_probe"
    feature_search = "feature_search"
    hidden_target_search = "hidden_target_search"


class RequestType(str, Enum):
    exact_track = "exact_track"
    exact_album = "exact_album"
    exact_artist = "exact_artist"
    same_artist = "same_artist"
    same_album = "same_album"
    new_artist = "new_artist"
    similar_to_prior = "similar_to_prior"
    attribute_search = "attribute_search"
    hidden_target = "hidden_target"
    unknown = "unknown"


class FactType(str, Enum):
    artist = "artist"
    album = "album"
    track = "track"
    attribute = "attribute"


class AttributeFacet(str, Enum):
    genre = "genre"
    mood = "mood"
    sonic = "sonic"
    instrument = "instrument"
    energy = "energy"
    lyrical_theme = "lyrical_theme"
    visual = "visual"
    popularity = "popularity"
    era = "era"
    performer = "performer"


class FactRole(str, Enum):
    current_target = "current_target"
    satisfied_prior = "satisfied_prior"
    history = "history"
    contrast = "contrast"
    rejected = "rejected"


class AnchorUse(str, Enum):
    must_use = "must_use"
    query_facet = "query_facet"
    partial_anchor = "partial_anchor"
    do_not_use = "do_not_use"


class FactRelation(str, Enum):
    exact_target = "exact_target"
    style_reference = "style_reference"
    liked_prior = "liked_prior"
    satisfied_prior = "satisfied_prior"
    history = "history"
    contrast = "contrast"
    exclude = "exclude"
    query_facet = "query_facet"


class ReusePolicy(str, Enum):
    must_reuse = "must_reuse"
    may_reuse = "may_reuse"
    avoid_exact = "avoid_exact"
    must_exclude = "must_exclude"
    not_applicable = "not_applicable"


class RejectionScope(str, Enum):
    hard = "hard"
    soft = "soft"


class ExclusionScope(str, Enum):
    next_turn_hard = "next_turn_hard"
    soft_preference = "soft_preference"


class TemporalConstraintKind(str, Enum):
    release_date = "release_date"
    style_era = "style_era"
    reference_era = "reference_era"


class ConstraintStrength(str, Enum):
    hard = "hard"
    soft = "soft"


Sentiment = Literal[-1, 0, 1]
_EVIDENCE_MAX_LEN = 240

# Production TalkPlay track_ids are UUID v4 strings, but tests and synthetic
# data use ergonomic ids like "t-fugazi-1". The real attack surface is the
# LLM occasionally hallucinating a stringified row dump as a track_id (e.g.
# `"track_id: 72a..., track_name: when will my life begin..., ..."`) — those
# strings contain quotes, colons, commas, and whitespace and crash the
# catalog's SQL WHERE clause. We accept any "safe identifier" — bare ASCII
# letters / digits / hyphens / underscores — and reject anything with the
# dangerous characters. Covers UUIDs, test ids, and any plausible production
# id format while still catching the hallucinated-row-dump pattern.
_TRACK_ID_SAFE_RE = _re.compile(r"^[A-Za-z0-9_\-]+$")


def _validate_track_id(value: str) -> str:
    if not isinstance(value, str) or not _TRACK_ID_SAFE_RE.match(value):
        raise ValueError(
            f"track_id must be a bare identifier (letters/digits/hyphens/"
            f"underscores only), got {value!r}. Likely cause: LLM emitted a "
            "stringified row dump or other malformed value instead of just "
            "the id."
        )
    return value


def _filter_valid_track_ids(values: list[str]) -> list[str]:
    """Drop entries that aren't safe identifier-shaped. Used on list-of-id
    fields where one bad LLM hallucination shouldn't invalidate the whole
    turn — we silently drop bad ids and keep the rest. For single-value
    fields (TrackFeedback.track_id) we raise instead, because there's no
    graceful per-list-entry recovery."""
    return [v for v in values if isinstance(v, str) and _TRACK_ID_SAFE_RE.match(v)]


class TrackFeedback(BaseModel):
    track_id: str = Field(..., description="A played track_id from played_track_ids.")

    @field_validator("track_id")
    @classmethod
    def _check_track_id(cls, v: str) -> str:
        return _validate_track_id(v)
    overall_sentiment: Sentiment = Field(
        ...,
        description=(
            "-1 negative, 0 neutral/no-signal, 1 positive. 3-value enum, never a scalar."
        ),
    )
    role: Literal["accepted", "rejected", "seed", "neutral", "satisfied", "contrast"] = Field(
        ...,
        description=(
            "accepted: user reacted positively to a played track. Default for any liked track. "
            "rejected: user reacted negatively to a played track. "
            "satisfied: this track met a prior request, but should not automatically carry forward. "
            "contrast: this track is a comparison/negative reference, not a seed. "
            "neutral: sentiment=0 — user acknowledged the track but didn't react positively or "
            "negatively (\"cool but not what I wanted\"). "
            "seed: RESERVED — the user EXPLICITLY pinned this track as THE anchor for what they "
            "want next. The user must either (a) name the track by title (\"more like Clair de "
            "lune\"), (b) refer to it by position (\"like that second one\"), or (c) ask an "
            "analytical question about that one specific track (\"what makes Duality engaging?\"). "
            "Do NOT use `seed` just because a track was the most recent thing played and the user "
            "reacted positively — that's `accepted`. Most positive reactions are `accepted`, not "
            "`seed`. Expect 0 or 1 seeds per turn, never one on every turn."
        ),
    )


class MentionedEntity(BaseModel):
    type: Literal["artist", "album", "track", "tag"]
    value: str = Field(..., description="Surface form as the user named it.")
    sentiment: Sentiment = Field(
        ...,
        description="-1 negative, 0 neutral, 1 positive. 3-value enum, never a scalar.",
    )


class StateEntity(BaseModel):
    """Role-typed entity extracted by the v1 state prompt.

    Only `current_target` and `seed` entities with `use_as_retrieval_seed=true`
    should drive exact/discography/anchor retrieval. `satisfied`, `history`,
    and `contrast` are retained for trace/debug context.
    """

    type: Literal["artist", "album", "track", "tag"]
    value: str = Field(..., description="Surface form as the user named it.")
    role: EntityRole
    source_turn: int = Field(..., ge=1)
    mentioned_current_turn: bool
    use_as_retrieval_seed: bool
    evidence_text: str | None = Field(
        default=None,
        max_length=_EVIDENCE_MAX_LEN,
        description="Short user-span evidence for high-risk role decisions.",
    )

    @model_validator(mode="after")
    def _seed_role_consistent(self):
        if self.role in {
            EntityRole.satisfied,
            EntityRole.history,
            EntityRole.contrast,
            EntityRole.rejected,
        }:
            self.use_as_retrieval_seed = False
        return self


class RequestTypeCandidate(BaseModel):
    request_type: RequestType
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Extractor confidence that this request class is also plausible.",
    )
    evidence_text: str | None = Field(default=None, max_length=_EVIDENCE_MAX_LEN)


class CurrentRequest(BaseModel):
    request_type: RequestType = Field(
        ...,
        description=(
            "Literal request class visible in the latest user turn. This is a "
            "conversation fact, not a retriever policy."
        ),
    )
    summary: str = Field(
        ...,
        description="One sentence summary of what the user asked for now.",
    )
    source_turn: int = Field(..., ge=1)
    evidence_text: str | None = Field(default=None, max_length=_EVIDENCE_MAX_LEN)
    candidate_types: list[RequestTypeCandidate] = Field(
        default_factory=list,
        description=(
            "Optional alternate request-type readings. Use when the latest turn "
            "contains both a broad routing cue and concrete retrieval facts, e.g. "
            "`similar to this` plus `more groove and chill R&B`. The compiler "
            "uses facts first; these are weak routing hints."
        ),
    )


class StateFact(BaseModel):
    """Fact-first extractor item.

    Facts capture what the user said. The compiler derives retrieval policy from
    `type`, `facet`, `role`, `anchor_use`, and source recency.
    """

    type: FactType
    facet: AttributeFacet | None = None
    value: str = Field(..., description="Surface form from the conversation.")
    role: FactRole
    anchor_use: AnchorUse
    relation: FactRelation | None = Field(
        default=None,
        description=(
            "Semantic role for compiler projection: exact_target may drive exact "
            "entity fanout; style_reference is a similarity anchor; query_facet "
            "is a descriptive facet; exclude is a future exclusion."
        ),
    )
    reuse: ReusePolicy | None = Field(
        default=None,
        description=(
            "Whether the named item may be reused exactly. The compiler only "
            "hard filters on must_exclude and only exact-fans-out must_reuse."
        ),
    )
    source_turn: int = Field(..., ge=1)
    mentioned_current_turn: bool
    evidence_text: str | None = Field(default=None, max_length=_EVIDENCE_MAX_LEN)

    @model_validator(mode="after")
    def _facet_consistent(self):
        if self.type == FactType.attribute and self.facet is None:
            self.facet = AttributeFacet.sonic
        if self.type != FactType.attribute:
            self.facet = None
        if self.role in {
            FactRole.satisfied_prior,
            FactRole.history,
            FactRole.contrast,
            FactRole.rejected,
        }:
            self.anchor_use = AnchorUse.do_not_use
        if self.role == FactRole.satisfied_prior and (
            self.relation == FactRelation.exact_target or self.reuse == ReusePolicy.must_reuse
        ):
            self.relation = FactRelation.style_reference
            self.reuse = ReusePolicy.may_reuse
        if self.role == FactRole.history and (
            self.relation == FactRelation.exact_target or self.reuse == ReusePolicy.must_reuse
        ):
            self.relation = FactRelation.history
            self.reuse = ReusePolicy.not_applicable
        if self.role == FactRole.contrast and (
            self.relation == FactRelation.exact_target or self.reuse == ReusePolicy.must_reuse
        ):
            self.relation = FactRelation.contrast
            self.reuse = ReusePolicy.avoid_exact
        if self.relation is None:
            self.relation = _default_fact_relation(self.type, self.role, self.anchor_use)
        if self.reuse is None:
            self.reuse = _default_reuse_policy(self.type, self.role, self.anchor_use, self.relation)
        if self.role == FactRole.rejected or self.relation == FactRelation.exclude:
            self.role = FactRole.rejected
            self.anchor_use = AnchorUse.do_not_use
            self.relation = FactRelation.exclude
            self.reuse = ReusePolicy.must_exclude
        return self


class StateExclusion(BaseModel):
    type: FactType
    facet: AttributeFacet | None = None
    value: str = Field(..., description="Excluded surface form.")
    scope: ExclusionScope
    source_turn: int = Field(..., ge=1)
    evidence_text: str | None = Field(default=None, max_length=_EVIDENCE_MAX_LEN)

    @model_validator(mode="after")
    def _facet_consistent(self):
        if self.type == FactType.attribute and self.facet is None:
            self.facet = AttributeFacet.sonic
        if self.type != FactType.attribute:
            self.facet = None
        return self


class ConversationStateV1(BaseModel):
    """Fact-first LLM contract for the next recommendation.

    This model intentionally excludes compiler-facing compatibility fields such
    as `entities`, `rejections`, `target_artist_mode`, and `retrieval_profile`.
    Downstream code gets those through `project_v1_to_v0plus()`.
    """

    current_request: CurrentRequest | None = Field(
        default=None,
        description=(
            "Fact-first current ask. This may include a factual request class "
            "such as exact_track, new_artist, attribute_search, or hidden_target, "
            "but it is not a retriever profile."
        ),
    )
    facts: list[StateFact] = Field(
        default_factory=list,
        description=(
            "Atomic conversation-visible facts for the latest request. The "
            "bridge uses relation/reuse/role to project exact seeds, style "
            "references, query facets, and exclusions."
        ),
    )
    exclusions: list[StateExclusion] = Field(
        default_factory=list,
        description="Explicit next-turn exclusions or soft avoid preferences.",
    )
    track_feedback: list[TrackFeedback] = Field(
        default_factory=list,
        description=(
            "Per-played-track sentiment. Only include tracks the user actually "
            "reacted to or explicitly pinned as a seed."
        ),
    )
    referenced_track_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Explicit pronoun/position references to played tracks, such as "
            "`the second one` or `that previous track`. Do not use for implicit "
            "topic continuity."
        ),
    )
    temporal_constraint: TemporalConstraint | None = Field(
        default=None,
        description=(
            "Minimal date/era guardrail. apply_as_filter=true only for literal "
            "hard release-date asks."
        ),
    )
    lyrical_theme: str | None = Field(
        default=None,
        description=(
            "Optional convenience copy of the lyric/meaning query. Prefer a "
            "facts[] item with facet=lyrical_theme; this field exists for the "
            "current lyric retriever contract."
        ),
    )

    @field_validator("referenced_track_ids", mode="after")
    @classmethod
    def _filter_referenced_track_ids(cls, value: list[str]) -> list[str]:
        return _filter_valid_track_ids(value)

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "$comment": (
                "ConversationStateV1 — LLM-facing fact contract. Use "
                "project_v1_to_v0plus() for compiler compatibility."
            )
        }


def _default_fact_relation(
    fact_type: FactType,
    role: FactRole,
    anchor_use: AnchorUse,
) -> FactRelation:
    if role == FactRole.rejected:
        return FactRelation.exclude
    if role == FactRole.satisfied_prior:
        return FactRelation.satisfied_prior
    if role == FactRole.history:
        return FactRelation.history
    if role == FactRole.contrast:
        return FactRelation.contrast
    if fact_type == FactType.attribute:
        return FactRelation.query_facet
    if anchor_use == AnchorUse.partial_anchor:
        return FactRelation.style_reference
    return FactRelation.exact_target


def _default_reuse_policy(
    fact_type: FactType,
    role: FactRole,
    anchor_use: AnchorUse,
    relation: FactRelation,
) -> ReusePolicy:
    if role == FactRole.rejected or relation == FactRelation.exclude:
        return ReusePolicy.must_exclude
    if relation == FactRelation.style_reference:
        return ReusePolicy.may_reuse
    if relation in {
        FactRelation.satisfied_prior,
        FactRelation.liked_prior,
        FactRelation.contrast,
    }:
        return ReusePolicy.avoid_exact
    if relation == FactRelation.history:
        return ReusePolicy.not_applicable
    if fact_type == FactType.attribute or anchor_use == AnchorUse.query_facet:
        return ReusePolicy.not_applicable
    if relation == FactRelation.exact_target and anchor_use == AnchorUse.must_use:
        return ReusePolicy.must_reuse
    return ReusePolicy.may_reuse


def _request_type_to_target_artist_mode(request_type: str | None) -> str:
    if request_type == RequestType.new_artist.value:
        return TargetArtistMode.new_artist.value
    if request_type in {
        RequestType.same_artist.value,
        RequestType.same_album.value,
    }:
        return TargetArtistMode.same_artist.value
    return TargetArtistMode.unknown.value


def _request_type_to_retrieval_profile(request_type: str | None) -> str:
    if request_type in {
        RequestType.exact_track.value,
        RequestType.exact_album.value,
        RequestType.exact_artist.value,
    }:
        return RetrievalProfile.exact_probe.value
    if request_type == RequestType.hidden_target.value:
        return RetrievalProfile.hidden_target_search.value
    if request_type == RequestType.new_artist.value:
        return RetrievalProfile.novelty.value
    if request_type in {
        RequestType.same_artist.value,
        RequestType.same_album.value,
        RequestType.similar_to_prior.value,
    }:
        return RetrievalProfile.continuation.value
    return RetrievalProfile.feature_search.value


def _fact_role_to_entity_role(role: str | None) -> str:
    return {
        FactRole.current_target.value: EntityRole.current_target.value,
        FactRole.satisfied_prior.value: EntityRole.satisfied.value,
        FactRole.history.value: EntityRole.history.value,
        FactRole.contrast.value: EntityRole.contrast.value,
        FactRole.rejected.value: EntityRole.rejected.value,
    }.get(str(role or ""), EntityRole.history.value)


def _fact_type_to_legacy_entity_type(fact_type: str | None) -> str | None:
    if fact_type == FactType.attribute.value:
        return "tag"
    if fact_type in {"artist", "album", "track"}:
        return fact_type
    return None


def _fact_to_legacy_entity_type(fact: dict) -> str | None:
    if _fact_relation_value(fact) == FactRelation.query_facet.value:
        return "tag"
    return _fact_type_to_legacy_entity_type(fact.get("type"))


def _fact_type_to_rejection_kind(fact_type: str | None) -> str | None:
    if fact_type == FactType.attribute.value:
        return "tag"
    if fact_type in {"artist", "album", "track"}:
        return fact_type
    return None


def _enum_value(value) -> str:
    return value.value if isinstance(value, Enum) else str(value)


def _fact_relation_value(fact: dict) -> str:
    relation = fact.get("relation")
    if relation:
        return _enum_value(relation)
    fact_type = FactType(_enum_value(fact.get("type")))
    role = FactRole(_enum_value(fact.get("role")))
    anchor_use = AnchorUse(_enum_value(fact.get("anchor_use")))
    return _default_fact_relation(fact_type, role, anchor_use).value


def _fact_reuse_value(fact: dict) -> str:
    reuse = fact.get("reuse")
    if reuse:
        return _enum_value(reuse)
    fact_type = FactType(_enum_value(fact.get("type")))
    role = FactRole(_enum_value(fact.get("role")))
    anchor_use = AnchorUse(_enum_value(fact.get("anchor_use")))
    relation = FactRelation(_fact_relation_value(fact))
    return _default_reuse_policy(fact_type, role, anchor_use, relation).value


def _fact_uses_retrieval_seed(fact: dict) -> bool:
    if fact.get("role") != FactRole.current_target.value:
        return False
    anchor_use = fact.get("anchor_use")
    if anchor_use == AnchorUse.do_not_use.value:
        return False
    relation = _fact_relation_value(fact)
    reuse = _fact_reuse_value(fact)
    if relation == FactRelation.exclude.value or reuse == ReusePolicy.must_exclude.value:
        return False
    if relation == FactRelation.query_facet.value:
        return relation == FactRelation.query_facet.value and anchor_use in {
            AnchorUse.must_use.value,
            AnchorUse.query_facet.value,
            AnchorUse.partial_anchor.value,
        }
    return (
        relation == FactRelation.exact_target.value
        and reuse == ReusePolicy.must_reuse.value
        and anchor_use == AnchorUse.must_use.value
    )


def _fact_is_style_reference(fact: dict) -> bool:
    if fact.get("type") not in {
        FactType.artist.value,
        FactType.album.value,
        FactType.track.value,
    }:
        return False
    relation = _fact_relation_value(fact)
    reuse = _fact_reuse_value(fact)
    role = _enum_value(fact.get("role"))
    anchor_use = _enum_value(fact.get("anchor_use"))
    if (
        role == FactRole.satisfied_prior.value
        and relation == FactRelation.satisfied_prior.value
        and anchor_use == AnchorUse.do_not_use.value
        and reuse in {
            ReusePolicy.may_reuse.value,
            ReusePolicy.avoid_exact.value,
        }
    ):
        return True
    return (
        relation == FactRelation.style_reference.value
        and reuse in {
            ReusePolicy.may_reuse.value,
            ReusePolicy.avoid_exact.value,
        }
    )


def _state_entity_key(entity_type: str | None, value: str | None) -> tuple[str, str] | None:
    if not entity_type or not value:
        return None
    normalized_value = _re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()
    normalized_value = _re.sub(r"\s+", " ", normalized_value)
    if not normalized_value:
        return None
    return str(entity_type), normalized_value


def _entity_from_fact(fact: dict) -> dict | None:
    entity_type = _fact_to_legacy_entity_type(fact)
    if entity_type is None or not fact.get("value"):
        return None
    return {
        "type": entity_type,
        "value": fact.get("value"),
        "role": _fact_role_to_entity_role(fact.get("role")),
        "source_turn": fact.get("source_turn", 1),
        "mentioned_current_turn": bool(fact.get("mentioned_current_turn")),
        "use_as_retrieval_seed": _fact_uses_retrieval_seed(fact),
        "evidence_text": fact.get("evidence_text"),
    }


def _mentioned_entity_from_fact(fact: "StateFact") -> MentionedEntity | None:
    fact_payload = fact.model_dump(mode="json")
    entity_type = _fact_to_legacy_entity_type(fact_payload)
    if entity_type is None:
        return None
    if fact.role == FactRole.rejected:
        return MentionedEntity(type=entity_type, value=fact.value, sentiment=-1)
    if _fact_uses_retrieval_seed(fact_payload):
        return MentionedEntity(type=entity_type, value=fact.value, sentiment=1)
    return None


def _style_reference_entity_from_fact(fact: "StateFact") -> MentionedEntity | None:
    entity_type = _fact_type_to_legacy_entity_type(fact.type.value)
    if entity_type not in {"artist", "album", "track"}:
        return None
    if _fact_is_style_reference(fact.model_dump()):
        return MentionedEntity(type=entity_type, value=fact.value, sentiment=1)
    return None


def _mentioned_entity_from_exclusion(
    exclusion: "StateExclusion",
) -> MentionedEntity | None:
    entity_type = _fact_type_to_legacy_entity_type(exclusion.type.value)
    if entity_type is None:
        return None
    if (
        entity_type in {"artist", "album", "track"}
        and exclusion.scope != ExclusionScope.next_turn_hard
    ):
        return None
    return MentionedEntity(type=entity_type, value=exclusion.value, sentiment=-1)


def _explicit_rejection_from_exclusion(
    exclusion: "StateExclusion",
) -> ExplicitRejection | None:
    kind = _fact_type_to_rejection_kind(exclusion.type.value)
    if kind is None:
        return None
    if kind == "attribute":
        kind = "tag"
    if kind not in ("artist", "track", "album", "tag"):
        return None
    if kind in {"artist", "track", "album"} and exclusion.scope != ExclusionScope.next_turn_hard:
        return None
    return ExplicitRejection(
        kind=kind,
        value=exclusion.value,
        source_turn=exclusion.source_turn,
    )


def _explicit_rejection_from_fact(fact: "StateFact") -> ExplicitRejection | None:
    if fact.role != FactRole.rejected:
        return None
    kind = _fact_type_to_rejection_kind(fact.type.value)
    if kind is None:
        return None
    if kind == "attribute":
        kind = "tag"
    if kind not in ("artist", "track", "album", "tag"):
        return None
    return ExplicitRejection(kind=kind, value=fact.value, source_turn=fact.source_turn)


def _dedupe_mentions(items: list[MentionedEntity]) -> list[MentionedEntity]:
    out: list[MentionedEntity] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item.type, _re.sub(r"\s+", " ", item.value.casefold()).strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _dedupe_rejections(items: list[ExplicitRejection]) -> list[ExplicitRejection]:
    out: list[ExplicitRejection] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item.kind, _re.sub(r"\s+", " ", item.value.casefold()).strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


class StateRejection(BaseModel):
    kind: Literal["artist", "track", "album", "tag", "style"]
    value: str = Field(..., description="Rejected surface form.")
    scope: RejectionScope = Field(
        ...,
        description="hard means strict future exclusion when resolvable; soft means demote/avoid.",
    )
    source_turn: int = Field(..., ge=1)
    evidence_text: str | None = Field(default=None, max_length=_EVIDENCE_MAX_LEN)


class TemporalConstraint(BaseModel):
    """Minimal temporal guardrail.

    The key distinction is whether the user asked for literal release dates
    (`apply_as_filter=true`) or a style/reference era (`apply_as_filter=false`).
    """

    kind: TemporalConstraintKind
    start_year: int | None = None
    end_year: int | None = None
    strength: ConstraintStrength
    apply_as_filter: bool = False
    evidence_text: str | None = Field(default=None, max_length=_EVIDENCE_MAX_LEN)

    @model_validator(mode="after")
    def _normalize_year_bounds(self):
        if (
            self.start_year is not None
            and self.end_year is not None
            and self.start_year > self.end_year
        ):
            self.start_year, self.end_year = self.end_year, self.start_year
        if self.kind != TemporalConstraintKind.release_date:
            self.apply_as_filter = False
        return self


class HardFilter(BaseModel):
    field: Literal["release_date"] = Field(
        ..., description="v0+ supports release_date only; other fields are deferred to v1."
    )
    op: Literal["<", ">", "between"]
    start: _date | None = Field(
        default=None,
        description=(
            "Lower bound. For op='>' tracks with release_date strictly greater than start match; "
            "for op='between' start is inclusive. Emit as YYYY-MM-DD; 'YYYY' expands to YYYY-01-01, "
            "'YYYY-MM' to YYYY-MM-01."
        ),
    )
    end: _date | None = Field(
        default=None,
        description=(
            "Upper bound. For op='<' tracks with release_date strictly less than end match; "
            "for op='between' end is inclusive. Emit as YYYY-MM-DD; 'YYYY' expands to YYYY-12-31, "
            "'YYYY-MM' to the last day of that month."
        ),
    )

    @field_validator("start", "end", mode="before")
    @classmethod
    def _coerce_partial(cls, v, info):
        if v is None or isinstance(v, _date):
            return v
        s = str(v).strip()
        if not s:
            return None
        is_end = info.field_name == "end"
        # Year-only: "2016" -> 2016-01-01 (start) or 2016-12-31 (end)
        if len(s) == 4 and s.isdigit():
            return _date(int(s), 12, 31) if is_end else _date(int(s), 1, 1)
        # Year-month: "2016-06" -> 2016-06-01 (start) or last-of-month (end)
        if len(s) == 7 and s[4] == "-" and s[:4].isdigit() and s[5:].isdigit():
            y, m = int(s[:4]), int(s[5:7])
            if is_end:
                from calendar import monthrange
                return _date(y, m, monthrange(y, m)[1])
            return _date(y, m, 1)
        # Otherwise let Pydantic try ISO parse (YYYY-MM-DD)
        return v

    @model_validator(mode="after")
    def _check_consistent_bounds(self):
        # Tolerant: missing-bound filters (e.g. `between` with start=None) are
        # accepted at the schema level and treated as no-ops downstream by the
        # compiler. The LLM occasionally emits these on hard turns; rejecting
        # them at validation time used to blow up the whole turn's state
        # (losing turn_intent, mentioned_entities, etc.) for a single bad
        # filter. The compiler now skips non-actionable filters; the schema
        # only enforces semantic consistency (inverted ranges).
        if (
            self.op == "between"
            and self.start is not None
            and self.end is not None
            and self.start > self.end
        ):
            raise ValueError(f"between: start ({self.start}) must be <= end ({self.end})")
        return self


class ReleaseYearRange(BaseModel):
    """Soft temporal hint for a downstream reranker's date-boosting (NOT a hard
    filter). The LLM converts any era/decade/century/year expression to integer
    year bounds using world knowledge; the reranker boosts candidates whose
    release year falls in (or near) this range. Either bound may be null = open.

    Examples the LLM should produce:
      "early 2010s"        -> {start: 2010, end: 2014}
      "90s"                -> {start: 1990, end: 1999}
      "19th century"       -> {start: 1801, end: 1900}
      "after 19th century" -> {start: 1901, end: null}
      "before 2000"        -> {start: null, end: 1999}
    """

    start: int | None = Field(default=None, description="Inclusive lower bound year, or null for open-ended.")
    end: int | None = Field(default=None, description="Inclusive upper bound year, or null for open-ended.")

    @model_validator(mode="after")
    def _normalize(self):
        # Safety net only: if the model inverts the bounds, swap rather than
        # reject — a soft hint should never crash extraction. Correct mapping is
        # the prompt's job; this just guarantees start <= end.
        if self.start is not None and self.end is not None and self.start > self.end:
            self.start, self.end = self.end, self.start
        return self


class ProcessConstraints(BaseModel):
    """How aggressively to vary or stay-the-course on the next recommendation.

    Orthogonal to `intent_mode`: intent says what the user is *doing*
    (refining, pivoting, etc.), process_constraints says how the system
    should *behave* along the artist/album axes. A user can be in
    `intent_mode=refinement` AND `exploration_policy=diversify_artists` —
    "more in this style, but different artists."
    """

    exploration_policy: ExplorationPolicy = Field(
        default=ExplorationPolicy.balanced,
        description=(
            "exploit: stick with the current artist/album; the user signals continuation "
            "of the same source ('more by them', 'another by this artist', 'more from this album'). "
            "diversify_artists: keep the style/genre/era, but explicitly look for OTHER artists "
            "('another <genre> track', 'more bands like this', 'something else in this vein'). "
            "Most common when the user re-states a style descriptor instead of an artist anchor. "
            "ALSO fires when the user rejects an artist by name (explicit_rejections.kind=artist) "
            "and is still asking for continuation in the same style. "
            "diversify_albums: same artist OK but prefer different albums ('another song by them, "
            "different album', 'more from earlier in their career'). Rare. "
            "balanced: default when the user gives no signal — e.g. 'more like this', 'something similar'. "
            "Compiler can mix continuation and variation."
        ),
    )


class ExplicitRejection(BaseModel):
    kind: Literal["artist", "track", "album", "tag"] = Field(
        ...,
        description=(
            "Compiler-facing explicit rejection kind. The resolver grounds "
            "artist/track today; album is preserved for album-aware suppression."
        ),
    )
    value: str = Field(..., description="Surface form. Compiler resolves to ids.")
    source_turn: int = Field(..., description="1-indexed turn number that introduced the rejection.")


class RoutingTags(BaseModel):
    """Additive compiler route flags (north-star routing_tags). Each true flag
    up-weights the matching retrieval branch(es). All default False so old
    states stay valid and routing is inert until the compiler is configured."""

    exact_entity_probe: bool = Field(default=False, description="User names a specific artist/track/album to find. Routes to bm25 + resolved-artist discography.")
    lyric_search: bool = Field(default=False, description="User asks by lyrical content / theme / words. Routes to the lyric branch.")
    feature_articulation: bool = Field(default=False, description="User describes the SOUND/feel (sonic descriptors, mood, instrumentation). Routes to audio/CLAP + metadata.")
    image_or_visual_search: bool = Field(default=False, description="User describes cover art or a visual. Routes to the image branch (deferred).")
    hidden_target_search: bool = Field(default=False, description="User is recalling a half-remembered track. Routes to broad/recency + popularity.")


class ConversationStateV0Plus(BaseModel):
    """v1 conversation state extracted by the LLM.

    The public extractor schema exposes role-typed entities and operational
    modes directly. Legacy compiler-facing views (`mentioned_entities`,
    `explicit_rejections`, `intent_mode`, etc.) are derived properties below so
    existing retrieval code can migrate gradually.
    """

    current_request: CurrentRequest | None = Field(
        default=None,
        description=(
            "Fact-first current ask. Preferred extractor-facing field. Legacy "
            "`turn_intent`, `target_artist_mode`, and `retrieval_profile` are "
            "derived from this when omitted."
        ),
    )

    facts: list[StateFact] = Field(
        default_factory=list,
        description=(
            "Conversation-visible facts for the latest request. Preferred "
            "extractor-facing field. Legacy `entities` are derived from this "
            "for existing compiler code."
        ),
    )

    exclusions: list[StateExclusion] = Field(
        default_factory=list,
        description=(
            "Explicit next-turn exclusions. Preferred extractor-facing field. "
            "Legacy `rejections` are derived from this for existing compiler code."
        ),
    )

    turn_intent: str = Field(
        default="",
        description=(
            "The active ask, naturally phrased. MUST preserve every artist / track / album / "
            "tag name the user named in the latest turn — anchor entities are the thing the "
            "rewrite wave kept losing. One or two sentences is fine. No fabricated entities."
        ),
    )

    track_feedback: list[TrackFeedback] = Field(
        default_factory=list,
        description=(
            "Per-played-track sentiment. Only include tracks the user actually reacted to "
            "(positively, negatively, or as a seed). Tracks the user said nothing about are omitted."
        ),
    )

    referenced_track_ids: list[str] = Field(
        default_factory=list,
        description=(
            "RESERVED for EXPLICIT pronoun / positional / temporal references. Populate ONLY when "
            "the latest user turn uses a referring expression that points back at a specific "
            "previously-played track AND the track is not named by title. Triggers: \"the second "
            "one\", \"that previous track\", \"the one you just played\", \"that song from earlier\", "
            "\"the third recommendation\". "
            "Do NOT populate just because the user is reacting to the most recently played track "
            "— implicit topic continuity is captured by `track_feedback`, not here. Do NOT populate "
            "when the user names the track by title (that's `mentioned_entities` with type=track). "
            "Empty (`[]`) on almost every turn — expect this field to fire on ~5% of turns at most. "
            "If you find yourself populating this on every turn, you are wrong."
        ),
    )

    entities: list[StateEntity] = Field(
        default_factory=list,
        description=(
            "Every relevant named entity/tag with a role. Only current_target/seed entities with "
            "use_as_retrieval_seed=true should drive retrieval seeds."
        ),
    )

    target_artist_mode: TargetArtistMode = Field(
        default=TargetArtistMode.unknown,
        description="Whether the next target should stay with the same artist or seek a new one.",
    )

    retrieval_profile: RetrievalProfile = Field(
        default=RetrievalProfile.feature_search,
        description="Operational retrieval mode downstream code can consume.",
    )

    rejections: list[StateRejection] = Field(
        default_factory=list,
        description="Hard/soft future exclusions, separate from contrast or historical context.",
    )

    temporal_constraint: TemporalConstraint | None = Field(
        default=None,
        description=(
            "Minimal date/era guardrail. apply_as_filter=true only for literal hard date asks."
        ),
    )

    lyrical_theme: str | None = Field(
        default=None,
        description=(
            "What the user wants the lyrics to be ABOUT (theme/subject), when the turn is a "
            "lyric request. Free text. The lyric branch queries the catalog's lyrics column as "
            "'music lyrics :{lyrical_theme}'. Null when not a lyric request."
        ),
    )

    @field_validator("referenced_track_ids", mode="after")
    @classmethod
    def _filter_referenced_track_ids(cls, value: list[str]) -> list[str]:
        # Per-entry recovery: one hallucinated id shouldn't void the whole
        # turn. Drop non-UUID-shaped entries silently.
        return _filter_valid_track_ids(value)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_state(cls, data):
        """Accept old test/trace-shaped state dicts while the compiler migrates.

        The extractor JSON schema no longer exposes these legacy fields because
        they are not part of the v1 LLM contract.
        """
        if not isinstance(data, dict):
            return data
        out = dict(data)

        current_request = out.get("current_request")
        if isinstance(current_request, BaseModel):
            current_request = current_request.model_dump()
        if isinstance(current_request, dict):
            request_type = current_request.get("request_type")
            if "turn_intent" not in out and current_request.get("summary"):
                out["turn_intent"] = current_request["summary"]
            if "target_artist_mode" not in out:
                out["target_artist_mode"] = _request_type_to_target_artist_mode(
                    request_type
                )
            if "retrieval_profile" not in out:
                out["retrieval_profile"] = _request_type_to_retrieval_profile(
                    request_type
                )

        raw_facts = out.get("facts")
        fact_items: list[dict] = []
        if isinstance(raw_facts, list):
            for raw in raw_facts:
                fact_items.append(
                    raw.model_dump() if isinstance(raw, BaseModel) else dict(raw)
                )

        if fact_items:
            entities_by_key: dict[tuple[str, str], dict] = {}
            entity_order: list[tuple[str, str]] = []

            raw_entities = out.get("entities")
            if isinstance(raw_entities, list):
                for raw in raw_entities:
                    entity = raw.model_dump() if isinstance(raw, BaseModel) else dict(raw)
                    key = _state_entity_key(entity.get("type"), entity.get("value"))
                    if key is None:
                        continue
                    entities_by_key[key] = entity
                    entity_order.append(key)

            for fact in fact_items:
                entity = _entity_from_fact(fact)
                if entity is None:
                    continue
                key = _state_entity_key(entity.get("type"), entity.get("value"))
                if key is None:
                    continue
                if key in entities_by_key:
                    continue
                entity_order.append(key)
                entities_by_key[key] = entity

            out["entities"] = [entities_by_key[key] for key in entity_order]

        if fact_items and not out.get("lyrical_theme"):
            for fact in fact_items:
                if (
                    fact.get("type") == FactType.attribute.value
                    and fact.get("facet") == AttributeFacet.lyrical_theme.value
                    and fact.get("role") == FactRole.current_target.value
                    and fact.get("value")
                ):
                    out["lyrical_theme"] = fact["value"]
                    break

        raw_exclusions = out.get("exclusions")
        exclusion_items: list[dict] = []
        if isinstance(raw_exclusions, list):
            for raw in raw_exclusions:
                exclusion_items.append(
                    raw.model_dump() if isinstance(raw, BaseModel) else dict(raw)
                )
        if "rejections" not in out and (exclusion_items or fact_items):
            rejections: list[dict] = []
            for exclusion in exclusion_items:
                kind = _fact_type_to_rejection_kind(exclusion.get("type"))
                if kind is None:
                    continue
                rejections.append(
                    {
                        "kind": kind,
                        "value": exclusion.get("value"),
                        "scope": (
                            "hard"
                            if exclusion.get("scope")
                            == ExclusionScope.next_turn_hard.value
                            else "soft"
                        ),
                        "source_turn": exclusion.get("source_turn", 1),
                        "evidence_text": exclusion.get("evidence_text"),
                    }
                )
            for fact in fact_items:
                if fact.get("role") != FactRole.rejected.value:
                    continue
                kind = _fact_type_to_rejection_kind(fact.get("type"))
                if kind is None:
                    continue
                candidate = {
                    "kind": kind,
                    "value": fact.get("value"),
                    "scope": "hard",
                    "source_turn": fact.get("source_turn", 1),
                    "evidence_text": fact.get("evidence_text"),
                }
                if candidate not in rejections:
                    rejections.append(candidate)
            out["rejections"] = rejections

        legacy_entities = out.pop("mentioned_entities", None)
        if "entities" not in out and isinstance(legacy_entities, list):
            entities: list[dict] = []
            for raw in legacy_entities:
                item = raw.model_dump() if isinstance(raw, BaseModel) else dict(raw)
                sentiment = item.get("sentiment", 0)
                role = (
                    EntityRole.rejected.value
                    if sentiment < 0
                    else EntityRole.current_target.value
                )
                entities.append(
                    {
                        "type": item.get("type"),
                        "value": item.get("value"),
                        "role": role,
                        "source_turn": 1,
                        "mentioned_current_turn": True,
                        "use_as_retrieval_seed": sentiment > 0,
                    }
                )
            out["entities"] = entities

        legacy_rejections = out.pop("explicit_rejections", None)
        if "rejections" not in out and isinstance(legacy_rejections, list):
            rejections: list[dict] = []
            for raw in legacy_rejections:
                item = raw.model_dump() if isinstance(raw, BaseModel) else dict(raw)
                kind = item.get("kind")
                rejections.append(
                    {
                        "kind": kind,
                        "value": item.get("value"),
                        "scope": "soft" if kind == "tag" else "hard",
                        "source_turn": item.get("source_turn", 1),
                    }
                )
            out["rejections"] = rejections

        legacy_policy = out.pop("process_constraints", None)
        legacy_intent = out.pop("intent_mode", None)
        legacy_routing = out.pop("routing_tags", None)
        legacy_hard_filters = out.pop("hard_filters", None)
        legacy_release_range = out.pop("release_year_range", None)

        if "target_artist_mode" not in out:
            policy_value = None
            if isinstance(legacy_policy, ProcessConstraints):
                policy_value = legacy_policy.exploration_policy.value
            elif isinstance(legacy_policy, dict):
                policy_value = legacy_policy.get("exploration_policy")
            if policy_value == ExplorationPolicy.exploit.value:
                out["target_artist_mode"] = TargetArtistMode.same_artist.value
            elif policy_value in {
                ExplorationPolicy.diversify_artists.value,
                ExplorationPolicy.diversify_albums.value,
            }:
                out["target_artist_mode"] = TargetArtistMode.new_artist.value
            else:
                out["target_artist_mode"] = TargetArtistMode.unknown.value

        if "retrieval_profile" not in out:
            routing_dict = (
                legacy_routing.model_dump()
                if isinstance(legacy_routing, BaseModel)
                else legacy_routing if isinstance(legacy_routing, dict)
                else {}
            )
            intent_value = legacy_intent.value if isinstance(legacy_intent, IntentMode) else legacy_intent
            if routing_dict.get("exact_entity_probe"):
                out["retrieval_profile"] = RetrievalProfile.exact_probe.value
            elif routing_dict.get("hidden_target_search"):
                out["retrieval_profile"] = RetrievalProfile.hidden_target_search.value
            elif routing_dict.get("feature_articulation"):
                out["retrieval_profile"] = RetrievalProfile.feature_search.value
            elif intent_value == IntentMode.pivot.value:
                out["retrieval_profile"] = RetrievalProfile.novelty.value
            elif intent_value == IntentMode.open_explore.value:
                out["retrieval_profile"] = RetrievalProfile.feature_search.value
            elif out.get("target_artist_mode") == TargetArtistMode.new_artist.value:
                out["retrieval_profile"] = RetrievalProfile.novelty.value
            else:
                out["retrieval_profile"] = RetrievalProfile.continuation.value

        if "temporal_constraint" not in out:
            release = (
                legacy_release_range.model_dump()
                if isinstance(legacy_release_range, BaseModel)
                else legacy_release_range
            )
            if isinstance(release, dict) and (
                release.get("start") is not None or release.get("end") is not None
            ):
                out["temporal_constraint"] = {
                    "kind": "style_era",
                    "start_year": release.get("start"),
                    "end_year": release.get("end"),
                    "strength": "soft",
                    "apply_as_filter": False,
                }
            elif isinstance(legacy_hard_filters, list) and legacy_hard_filters:
                hf_raw = legacy_hard_filters[0]
                hf = hf_raw.model_dump() if isinstance(hf_raw, BaseModel) else dict(hf_raw)
                start = hf.get("start")
                end = hf.get("end")
                out["temporal_constraint"] = {
                    "kind": "release_date",
                    "start_year": getattr(start, "year", None),
                    "end_year": getattr(end, "year", None),
                    "strength": "hard",
                    "apply_as_filter": True,
                }

        return out

    @property
    def intent_mode(self) -> IntentMode:
        if self.retrieval_profile == RetrievalProfile.novelty:
            return IntentMode.pivot
        if self.retrieval_profile == RetrievalProfile.continuation:
            return IntentMode.refinement
        if self.retrieval_profile == RetrievalProfile.exact_probe:
            return IntentMode.refinement
        return IntentMode.open_explore

    @property
    def process_constraints(self) -> ProcessConstraints:
        if self.target_artist_mode == TargetArtistMode.same_artist:
            policy = ExplorationPolicy.exploit
        elif self.target_artist_mode == TargetArtistMode.new_artist:
            policy = ExplorationPolicy.diversify_artists
        elif self.retrieval_profile == RetrievalProfile.novelty:
            policy = ExplorationPolicy.diversify_artists
        else:
            policy = ExplorationPolicy.balanced
        return ProcessConstraints(exploration_policy=policy)

    @property
    def routing_tags(self) -> RoutingTags:
        has_visual = any(
            fact.type == FactType.attribute
            and fact.facet == AttributeFacet.visual
            and fact.role == FactRole.current_target
            and fact.anchor_use != AnchorUse.do_not_use
            for fact in self.facts
        )
        return RoutingTags(
            exact_entity_probe=self.retrieval_profile == RetrievalProfile.exact_probe,
            lyric_search=bool(self.lyrical_theme),
            feature_articulation=self.retrieval_profile == RetrievalProfile.feature_search,
            image_or_visual_search=has_visual,
            hidden_target_search=self.retrieval_profile == RetrievalProfile.hidden_target_search,
        )

    @property
    def mentioned_entities(self) -> list[MentionedEntity]:
        if self.facts or self.exclusions:
            negative_items: list[MentionedEntity] = []
            positive_items: list[MentionedEntity] = []
            for exclusion in self.exclusions:
                item = _mentioned_entity_from_exclusion(exclusion)
                if item is not None:
                    negative_items.append(item)
            for fact in self.facts:
                item = _mentioned_entity_from_fact(fact)
                if item is None:
                    continue
                if item.sentiment < 0:
                    negative_items.append(item)
                else:
                    positive_items.append(item)
            return _dedupe_mentions(negative_items + positive_items)

        out: list[MentionedEntity] = []
        for entity in self.entities:
            if entity.role == EntityRole.rejected:
                out.append(
                    MentionedEntity(type=entity.type, value=entity.value, sentiment=-1)
                )
            elif entity.use_as_retrieval_seed and entity.role in {
                EntityRole.current_target,
                EntityRole.seed,
            }:
                out.append(
                    MentionedEntity(type=entity.type, value=entity.value, sentiment=1)
                )
        return out

    @property
    def style_reference_entities(self) -> list[MentionedEntity]:
        if self.facts:
            out: list[MentionedEntity] = []
            for fact in self.facts:
                item = _style_reference_entity_from_fact(fact)
                if item is not None:
                    out.append(item)
            return _dedupe_mentions(out)
        return []

    @property
    def explicit_rejections(self) -> list[ExplicitRejection]:
        if self.facts or self.exclusions:
            out: list[ExplicitRejection] = []
            for exclusion in self.exclusions:
                item = _explicit_rejection_from_exclusion(exclusion)
                if item is not None:
                    out.append(item)
            for fact in self.facts:
                item = _explicit_rejection_from_fact(fact)
                if item is not None:
                    out.append(item)
            return _dedupe_rejections(out)

        out: list[ExplicitRejection] = []
        for rejection in self.rejections:
            if rejection.kind in ("artist", "track") and rejection.scope != RejectionScope.hard:
                continue
            kind = "tag" if rejection.kind == "style" else rejection.kind
            if kind in ("artist", "track", "album", "tag"):
                out.append(
                    ExplicitRejection(
                        kind=kind,
                        value=rejection.value,
                        source_turn=rejection.source_turn,
                    )
                )
        for entity in self.entities:
            if entity.role == EntityRole.rejected and entity.type in ("artist", "track", "album", "tag"):
                candidate = ExplicitRejection(
                    kind=entity.type,
                    value=entity.value,
                    source_turn=entity.source_turn,
                )
                if candidate not in out:
                    out.append(candidate)
        return out

    @property
    def release_year_range(self) -> ReleaseYearRange | None:
        tc = self.temporal_constraint
        if tc is None or (tc.start_year is None and tc.end_year is None):
            return None
        return ReleaseYearRange(start=tc.start_year, end=tc.end_year)

    @property
    def hard_filters(self) -> list[HardFilter]:
        tc = self.temporal_constraint
        if tc is None or not tc.apply_as_filter or tc.kind != TemporalConstraintKind.release_date:
            return []
        if tc.start_year is not None and tc.end_year is not None:
            return [
                HardFilter(
                    field="release_date",
                    op="between",
                    start=f"{tc.start_year}-01-01",
                    end=f"{tc.end_year}-12-31",
                )
            ]
        if tc.start_year is not None:
            return [
                HardFilter(
                    field="release_date",
                    op=">",
                    start=f"{tc.start_year}-01-01",
                )
            ]
        if tc.end_year is not None:
            return [
                HardFilter(
                    field="release_date",
                    op="<",
                    end=f"{tc.end_year}-12-31",
                )
            ]
        return []

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "$comment": (
                "v0+ ConversationState — see docs/architectures/session_state.md"
            )
        }


def project_v1_to_v0plus(state: ConversationStateV1) -> ConversationStateV0Plus:
    """Project the fact-first LLM state into the existing compiler contract.

    This is intentionally structural: it copies V1 fields and lets the V0Plus
    compatibility model derive legacy views from those fields. It does not
    inspect the raw conversation text or repair phrases with ad hoc matching.
    """

    return ConversationStateV0Plus.model_validate(
        state.model_dump(mode="json", exclude_none=True)
    )
