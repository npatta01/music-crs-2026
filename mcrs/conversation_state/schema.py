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


Sentiment = Literal[-1, 0, 1]

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
    role: Literal["accepted", "rejected", "seed", "neutral"] = Field(
        ...,
        description=(
            "accepted: user reacted positively to a played track. Default for any liked track. "
            "rejected: user reacted negatively to a played track. "
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
    kind: Literal["artist", "track", "tag"] = Field(
        ..., description="v0+ kinds. album / attribute deferred to v1."
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
    """The 7 LLM-extracted fields from iteration_1_minimal_schema.md."""

    turn_intent: str = Field(
        ...,
        description=(
            "The active ask, naturally phrased. MUST preserve every artist / track / album / "
            "tag name the user named in the latest turn — anchor entities are the thing the "
            "rewrite wave kept losing. One or two sentences is fine. No fabricated entities."
        ),
    )

    intent_mode: IntentMode = Field(
        ...,
        description=(
            "open_explore: broad / vibe-led, no specific anchor. "
            "refinement: tweak/adjust the current direction, keep prior anchors. "
            "pivot: deliberate change of direction; prior anchors should be dropped. "
            "playlist_build: cumulative — keep building on prior anchors heavily."
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

    mentioned_entities: list[MentionedEntity] = Field(
        default_factory=list,
        description=(
            "Entities the user named or referenced in any turn. Includes positive AND neutral "
            "mentions. Negatives go here too (sentiment=-1) AND duplicate into explicit_rejections "
            "if the user is excluding them from future recs."
        ),
    )

    hard_filters: list[HardFilter] = Field(
        default_factory=list,
        description=(
            'Structured filters the compiler can apply at the catalog level. v0+ supports '
            "release_date only. Examples: \"songs from the 90s\" -> between [1990-01-01, 1999-12-31]; "
            '"nothing newer than 2010" -> < 2010-01-01.'
        ),
    )

    explicit_rejections: list[ExplicitRejection] = Field(
        default_factory=list,
        description=(
            'Hard-exclude future recommendations. Populate when the user says "not X", "no more X", '
            '"stop playing X", "different from X", "too heavy", "too gloomy". kind=artist excludes '
            "all tracks by that artist; kind=track excludes that track_id; kind=tag soft-demotes "
            "tracks whose tag_list overlaps."
        ),
    )

    process_constraints: ProcessConstraints = Field(
        default_factory=ProcessConstraints,
        description=(
            "How aggressively the compiler should vary vs continue along the artist/album/novelty "
            "axes. Orthogonal to intent_mode. See ProcessConstraints field docs for the full "
            "decision table."
        ),
    )

    routing_tags: RoutingTags = Field(
        default_factory=RoutingTags,
        description="Per-turn route flags; each true flag up-weights its branch(es).",
    )
    lyrical_theme: str | None = Field(
        default=None,
        description=(
            "What the user wants the lyrics to be ABOUT (theme/subject), when the turn is a "
            "lyric request. Free text. The lyric branch queries the catalog's lyrics column as "
            "'music lyrics :{lyrical_theme}'. Null when not a lyric request."
        ),
    )

    release_year_range: ReleaseYearRange | None = Field(
        default=None,
        description=(
            "Soft temporal hint when the user mentions any era / decade / century / year bound. "
            "Convert the expression to integer year bounds using world knowledge (e.g. "
            "'early 2010s' -> {2010, 2014}; '19th century' -> {1801, 1900}; 'after the 19th "
            "century' -> {1901, null}). Either bound may be null for open-ended. null when the "
            "user states no time period. This is a soft boost signal for the reranker, not a hard filter."
        ),
    )

    @field_validator("referenced_track_ids", mode="after")
    @classmethod
    def _filter_referenced_track_ids(cls, value: list[str]) -> list[str]:
        # Per-entry recovery: one hallucinated id shouldn't void the whole
        # turn. Drop non-UUID-shaped entries silently.
        return _filter_valid_track_ids(value)

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "$comment": (
                "v0+ ConversationState — see docs/architectures/session_state.md"
            )
        }
