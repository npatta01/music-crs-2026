"""HardFilter date typing and op-required-field validation."""
from datetime import date

import pytest
from pydantic import ValidationError

from mcrs.conversation_state.schema import (
    ConversationStateV1,
    HardFilter,
    project_v1_to_v0plus,
)


class TestHardFilterDateTypes:
    def test_between_accepts_full_iso_dates(self):
        f = HardFilter(field="release_date", op="between", start="2010-01-01", end="2013-12-31")
        assert f.start == date(2010, 1, 1)
        assert f.end == date(2013, 12, 31)

    def test_between_accepts_year_only_start(self):
        f = HardFilter(field="release_date", op="between", start="2010", end="2013")
        assert f.start == date(2010, 1, 1)
        assert f.end == date(2013, 12, 31)

    def test_between_accepts_year_month(self):
        f = HardFilter(field="release_date", op="between", start="2010-06", end="2013-08")
        assert f.start == date(2010, 6, 1)
        assert f.end == date(2013, 8, 31)

    def test_lt_accepts_year_only_end(self):
        f = HardFilter(field="release_date", op="<", end="2000")
        assert f.end == date(2000, 12, 31)

    def test_gt_accepts_year_only_start(self):
        f = HardFilter(field="release_date", op=">", start="2020")
        assert f.start == date(2020, 1, 1)


class TestHardFilterBoundsTolerant:
    """Schema accepts missing-bound filters; compiler skips them downstream.

    Rationale: the LLM occasionally emits `op="between"` with both bounds
    None on hard turns. Old behavior: schema raised → whole-state validation
    failed → turn returned 0 candidates. New behavior: schema accepts → the
    compiler treats the filter as a no-op and the rest of the state drives
    retrieval. See `compiler._release_date_mask` for the skip.
    """

    def test_lt_accepts_missing_end(self):
        f = HardFilter(field="release_date", op="<", start="2010-01-01")
        assert f.end is None  # constructed, not raised

    def test_gt_accepts_missing_start(self):
        f = HardFilter(field="release_date", op=">", end="2010-01-01")
        assert f.start is None

    def test_between_accepts_missing_bounds(self):
        f1 = HardFilter(field="release_date", op="between", end="2010-12-31")
        assert f1.start is None
        f2 = HardFilter(field="release_date", op="between", start="2010-01-01")
        assert f2.end is None
        f3 = HardFilter(field="release_date", op="between")
        assert f3.start is None and f3.end is None

    def test_between_still_rejects_inverted_range(self):
        with pytest.raises(ValidationError, match="start.*end"):
            HardFilter(
                field="release_date", op="between",
                start="2015-01-01", end="2010-01-01",
            )

    def test_invalid_op_rejected(self):
        with pytest.raises(ValidationError):
            HardFilter(field="release_date", op="<=", end="2010-01-01")

    def test_unknown_op_rejected_by_pydantic(self):
        """Regression: removed test_release_date_unknown_op_returns_all_track_ids from
        the catalog tests because Pydantic's Literal now rejects unknown ops at
        construction. Pin that contract here."""
        with pytest.raises(ValidationError):
            HardFilter(field="release_date", op="!=", end="2010-01-01")

    def test_malformed_date_rejected(self):
        with pytest.raises(ValidationError):
            HardFilter(field="release_date", op="<", end="January 2010")


class TestV1ProjectionSwitchAway:
    def test_hard_switch_away_rejects_satisfied_prior_style_anchor(self):
        state = project_v1_to_v0plus(
            ConversationStateV1.model_validate(
                {
                    "current_request": {
                        "request_type": "attribute_search",
                        "summary": (
                            "Something raw and intense, far from comfort zone, "
                            "with heavy beat or aggressive vocals."
                        ),
                        "source_turn": 3,
                    },
                    "facts": [
                        {
                            "type": "artist",
                            "value": "Gang Starr",
                            "role": "satisfied_prior",
                            "anchor_use": "do_not_use",
                            "relation": "satisfied_prior",
                            "reuse": "avoid_exact",
                            "source_turn": 3,
                            "mentioned_current_turn": True,
                            "evidence_text": "still getting classic hip-hop",
                        },
                        {
                            "type": "attribute",
                            "facet": "genre",
                            "value": "hardcore",
                            "role": "current_target",
                            "anchor_use": "query_facet",
                            "relation": "query_facet",
                            "reuse": "not_applicable",
                            "source_turn": 3,
                            "mentioned_current_turn": True,
                            "evidence_text": "hardcore",
                        },
                    ],
                    "exclusions": [
                        {
                            "type": "artist",
                            "value": "Gang Starr",
                            "scope": "next_turn_hard",
                            "source_turn": 3,
                            "evidence_text": "still getting classic hip-hop",
                        }
                    ],
                }
            )
        )

        assert state.retrieval_profile.value == "novelty"
        assert state.target_artist_mode.value == "new_artist"
        assert state.intent_mode.value == "pivot"
        assert state.facts[0].role.value == "rejected"
        assert state.facts[0].relation.value == "exclude"
        assert state.facts[0].reuse.value == "must_exclude"
        assert state.style_reference_entities == []
        assert any(
            item.type == "artist" and item.value == "Gang Starr" and item.sentiment < 0
            for item in state.mentioned_entities
        )

    def test_ordinary_satisfied_prior_remains_style_reference(self):
        state = project_v1_to_v0plus(
            ConversationStateV1.model_validate(
                {
                    "current_request": {
                        "request_type": "attribute_search",
                        "summary": "I love System of a Down, give me new bands with that sound.",
                        "source_turn": 2,
                    },
                    "facts": [
                        {
                            "type": "artist",
                            "value": "System of a Down",
                            "role": "satisfied_prior",
                            "anchor_use": "do_not_use",
                            "relation": "satisfied_prior",
                            "reuse": "avoid_exact",
                            "source_turn": 2,
                            "mentioned_current_turn": True,
                            "evidence_text": "with that sound",
                        }
                    ],
                }
            )
        )

        assert state.retrieval_profile.value == "feature_search"
        assert state.target_artist_mode.value == "unknown"
        assert [
            (item.type, item.value, item.sentiment)
            for item in state.style_reference_entities
        ] == [("artist", "System of a Down", 1)]

    def test_hard_exclusion_without_switch_language_keeps_similarity_signal(self):
        state = project_v1_to_v0plus(
            ConversationStateV1.model_validate(
                {
                    "current_request": {
                        "request_type": "attribute_search",
                        "summary": "Miles Davis never disappoints; find trumpet-led jazz like that.",
                        "source_turn": 4,
                    },
                    "facts": [
                        {
                            "type": "artist",
                            "value": "Miles Davis",
                            "role": "satisfied_prior",
                            "anchor_use": "do_not_use",
                            "relation": "satisfied_prior",
                            "reuse": "avoid_exact",
                            "source_turn": 4,
                            "mentioned_current_turn": True,
                            "evidence_text": "Miles Davis never disappoints",
                        }
                    ],
                    "exclusions": [
                        {
                            "type": "artist",
                            "value": "Miles Davis",
                            "scope": "next_turn_hard",
                            "source_turn": 4,
                            "evidence_text": "not the exact same artist",
                        }
                    ],
                }
            )
        )

        assert state.retrieval_profile.value == "feature_search"
        assert [
            (item.type, item.value, item.sentiment)
            for item in state.style_reference_entities
        ] == [("artist", "Miles Davis", 1)]
