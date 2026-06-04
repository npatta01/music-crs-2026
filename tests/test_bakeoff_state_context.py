from __future__ import annotations

import json
from pathlib import Path

from mcrs.bakeoff.state_context import format_state_block, load_states
from mcrs.bakeoff.track_lookup import TrackMetadataLookup


def _lookup():
    return TrackMetadataLookup.from_rows([
        {"track_id": "t1", "track_name": ["Olvidarte"], "artist_name": ["Ricardo Arjona"],
         "album_name": ["A"], "tag_list": ["balada"]},
    ])


def test_format_state_block_renders_key_fields():
    state = {
        "turn_intent": "something acoustic like Arjona",
        "mentioned_entities": [
            {"type": "artist", "value": "Ricardo Arjona", "sentiment": 1},
            {"type": "tag", "value": "polka", "sentiment": -1},
        ],
        "track_feedback": [{"track_id": "t1", "role": "accepted", "overall_sentiment": 1}],
        "release_year_range": {"start": 1990, "end": 1999},
        "lyrical_theme": None,
    }
    block = format_state_block(state, _lookup())
    assert "Current request: something acoustic like Arjona" in block
    assert "Ricardo Arjona" in block          # liked entity
    assert "Olvidarte" in block               # accepted track resolved via lookup
    assert "polka" in block                   # disliked entity
    assert "1990-1999" in block


def test_format_state_block_handles_none():
    assert "unavailable" in format_state_block(None, _lookup())


def test_load_states_filters_and_keys_by_session_turn(tmp_path):
    p = tmp_path / "trace.jsonl"
    rows = [
        {"session_id": "s1", "turn_number": 1, "trace": {"state": {"turn_intent": "a"}}},
        {"session_id": "s2", "turn_number": 1, "trace": {"state": {"turn_intent": "b"}}},
        {"session_id": "s1", "turn_number": 2, "trace": {"state": {"turn_intent": "c"}}},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows))
    states = load_states(str(p), {"s1"})
    assert set(states.keys()) == {("s1", 1), ("s1", 2)}
    assert states[("s1", 1)]["turn_intent"] == "a"
