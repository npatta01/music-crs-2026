from __future__ import annotations

import pytest

from mcrs.bakeoff.judge import (
    build_judge_prompt,
    parse_judge_json,
    normalize_score,
    aggregate_model_report,
)


def test_normalize_score_maps_1_to_0_and_5_to_1():
    assert normalize_score(1) == 0.0
    assert normalize_score(5) == 1.0
    assert normalize_score(3) == 0.5


def test_parse_judge_json_extracts_scores():
    raw = 'Sure: {"personalization": 4, "explanation": 2}'
    d = parse_judge_json(raw)
    assert d == {"personalization": 4, "explanation": 2}


def test_parse_judge_json_clamps_and_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_judge_json("no json here")


def test_build_judge_prompt_contains_response_and_axes():
    p = build_judge_prompt(
        conversation="user: hi", response="Try this jazzy track.", track="title: X"
    )
    assert "Try this jazzy track." in p
    assert "personalization" in p.lower()
    assert "explanation" in p.lower()


def test_aggregate_model_report_averages_axes_and_panel():
    per_turn = [
        {"turn": 1, "judges": {"gemini": {"personalization": 5, "explanation": 5},
                                "neutral": {"personalization": 3, "explanation": 3}}},
        {"turn": 2, "judges": {"gemini": {"personalization": 1, "explanation": 1},
                                "neutral": {"personalization": 1, "explanation": 1}}},
    ]
    rep = aggregate_model_report("gemma-27b", per_turn, distinct2=0.42)
    assert rep["tag"] == "gemma-27b"
    assert rep["distinct2"] == 0.42
    assert rep["personalization_by_judge"]["gemini"] == pytest.approx(0.5)
    assert rep["personalization_panel"] == pytest.approx(0.375)
    assert rep["combined"] == pytest.approx(
        (rep["personalization_panel"] + rep["explanation_panel"]) / 2
    )
