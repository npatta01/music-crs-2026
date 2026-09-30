"""Tests for the Phase 2 anchor re-label transform."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "rerank" / "anchor_labels"))

from anchor_relabel import negative_turns, relabel_frame, confidence_map  # noqa: E402


def _labels():
    return {
        ("s1", 1): {"label": "NEGATIVE", "label_reason": "artist_anchoring", "confidence_weight": 0.6},
        ("s1", 2): {"label": "NEGATIVE", "label_reason": "content_violation", "confidence_weight": 1.0},
        ("s2", 1): {"label": "POSITIVE", "label_reason": "fits_and_liked", "confidence_weight": 1.0},
        ("s2", 2): {"label": "NEGATIVE", "label_reason": "other_reason", "confidence_weight": 1.0},
    }


def test_negative_turns_only_anchoring_and_content():
    neg = negative_turns(_labels())
    assert neg == {("s1", 1), ("s1", 2)}  # s2,2 has a non-targeted reason


def test_relabel_flips_only_gt_positive_rows_in_negative_turns():
    df = pd.DataFrame([
        {"session_id": "s1", "turn_number": 1, "track_id": "gt1", "label": 1},
        {"session_id": "s1", "turn_number": 1, "track_id": "c", "label": 0},
        {"session_id": "s2", "turn_number": 1, "track_id": "gt2", "label": 1},  # positive turn -> keep
    ])
    out, n = relabel_frame(df, {("s1", 1)})
    assert n == 1
    assert out[(out.session_id == "s1") & (out.track_id == "gt1")].label.iloc[0] == 0
    assert out[(out.session_id == "s2")].label.iloc[0] == 1  # untouched
    assert out[(out.track_id == "c")].label.iloc[0] == 0  # negatives stay 0


def test_confidence_map():
    cm = confidence_map(_labels())
    assert cm[("s1", 1)] == 0.6
    assert cm[("s2", 1)] == 1.0
