from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "response_bakeoff", Path("scripts/response_bakeoff.py")
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_collect_turns_filters_slice_and_takes_top1():
    predictions = [
        {"session_id": "s1", "user_id": "u1", "turn_number": 1, "predicted_track_ids": ["a", "b"]},
        {"session_id": "s1", "user_id": "u1", "turn_number": 2, "predicted_track_ids": ["c"]},
        {"session_id": "s2", "user_id": "u2", "turn_number": 1, "predicted_track_ids": ["d"]},
    ]
    turns = mod.collect_turns(predictions, session_ids={"s1"})
    assert turns == [
        {"session_id": "s1", "turn_number": 1, "top_track_id": "a", "user_id": "u1"},
        {"session_id": "s1", "turn_number": 2, "top_track_id": "c", "user_id": "u1"},
    ]


def test_collect_turns_skips_empty_predictions():
    predictions = [{"session_id": "s1", "user_id": "u1", "turn_number": 1, "predicted_track_ids": []}]
    assert mod.collect_turns(predictions, session_ids={"s1"}) == []
