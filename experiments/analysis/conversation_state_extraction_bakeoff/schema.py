"""Pydantic v0+ ConversationState schema.

Mirrors iteration_1_minimal_schema.md: 7 LLM-extracted fields, flat where possible,
3-value enums for sentiment, 4-value enum for intent_mode.

Used by:
- The extraction prompt builder (prompts.py) for JSON-schema-constrained outputs.
- The labeling workflow — humans fill these models in for the audit set.
- The scorer (score.py) for per-field F1.
"""

from __future__ import annotations

from datetime import date as _date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class IntentMode(str, Enum):
    open_explore = "open_explore"
    refinement = "refinement"
    pivot = "pivot"
    playlist_build = "playlist_build"


Sentiment = Literal[-1, 0, 1]


class TrackFeedback(BaseModel):
    track_id: str = Field(..., description="A played track_id from played_track_ids.")
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
    def _check_required_per_op(self):
        if self.op == "<":
            if self.end is None:
                raise ValueError("op='<' requires end")
        elif self.op == ">":
            if self.start is None:
                raise ValueError("op='>' requires start")
        elif self.op == "between":
            if self.start is None:
                raise ValueError("op='between' requires start")
            if self.end is None:
                raise ValueError("op='between' requires end")
            if self.start > self.end:
                raise ValueError(f"between: start ({self.start}) must be <= end ({self.end})")
        return self


class ExplicitRejection(BaseModel):
    kind: Literal["artist", "track", "tag"] = Field(
        ..., description="v0+ kinds. album / attribute deferred to v1."
    )
    value: str = Field(..., description="Surface form. Compiler resolves to ids.")
    source_turn: int = Field(..., description="1-indexed turn number that introduced the rejection.")


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

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "$comment": (
                "v0+ ConversationState — see experiments/analysis/conversation_state_design_v2/"
                "iteration_1_minimal_schema.md"
            )
        }
