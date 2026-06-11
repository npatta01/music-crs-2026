from __future__ import annotations

from mcrs.response_context import format_state_block, is_metadata_echo, xml_track_item


def test_xml_track_item_caps_tags_and_wraps():
    meta = {
        "track_name": ["Buena"], "artist_name": ["Morphine"], "album_name": ["Yes"],
        "tag_list": [f"t{i}" for i in range(20)],
    }
    out = xml_track_item(meta, track_id="x", max_tags=10)
    assert out.startswith("<recommended_track>")
    assert "<title>Buena</title>" in out and "<artist>Morphine</artist>" in out
    assert out.count(",") == 9  # 10 tags -> 9 separators
    assert "t10" not in out  # capped


def test_xml_track_item_missing_meta_falls_back_to_id():
    out = xml_track_item(None, track_id="abc")
    assert "<track_id>abc</track_id>" in out


def test_format_state_block_renders_fields_and_resolves_tracks():
    state = {
        "turn_intent": "something acoustic",
        "mentioned_entities": [
            {"type": "tag", "value": "acoustic", "sentiment": 1},
            {"type": "tag", "value": "polka", "sentiment": -1},
        ],
        "track_feedback": [{"track_id": "t1", "role": "accepted"}],
        "release_year_range": {"start": 1990, "end": 1999},
    }
    block = format_state_block(state, lambda tid: "title: Olvidarte | artist: Arjona | tags: x")
    assert "Current request: something acoustic" in block
    assert "acoustic" in block and "polka" in block
    assert "Olvidarte" in block and "tags:" not in block  # label trimmed before tags
    assert "1990-1999" in block


def test_format_state_block_none():
    assert "unavailable" in format_state_block(None, None)


def test_is_metadata_echo():
    assert is_metadata_echo("")
    assert is_metadata_echo("title: X | artist: Y | tags: a, b")
    assert is_metadata_echo("<recommended_track><title>X</title>")
    assert not is_metadata_echo("Great pick — this jazzy track fits your mood.")
