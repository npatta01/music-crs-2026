"""HardFilter date typing and op-required-field validation."""
from datetime import date

import pytest
from pydantic import ValidationError

from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
    HardFilter,
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
    retrieval. See `compiler_v0plus._release_date_mask` for the skip.
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
