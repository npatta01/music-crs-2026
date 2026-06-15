from __future__ import annotations

from mcrs.response_context import format_state_block, is_metadata_echo, xml_track_item, response_state_dict
from mcrs.conversation_state.schema import (
    ConversationStateV0Plus, StateEntity, EntityRole,
    TemporalConstraint, TemporalConstraintKind, ConstraintStrength,
)


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


def _real_state_with_derived_fields() -> ConversationStateV0Plus:
    """A REAL V0Plus (not the test fake) whose three derived @property fields
    are all non-empty: a seed artist (+1), a rejected artist (-1 + rejection),
    and a temporal range."""
    return ConversationStateV0Plus(
        turn_intent="something from the 90s, not Coldplay",
        entities=[
            StateEntity(type="artist", value="Radiohead", role=EntityRole.seed,
                        source_turn=1, mentioned_current_turn=True, use_as_retrieval_seed=True),
            StateEntity(type="artist", value="Coldplay", role=EntityRole.rejected,
                        source_turn=1, mentioned_current_turn=True, use_as_retrieval_seed=False),
        ],
        temporal_constraint=TemporalConstraint(
            kind=TemporalConstraintKind.style_era, strength=ConstraintStrength.soft,
            start_year=1990, end_year=1999,
        ),
    )


def test_model_dump_drops_derived_properties_documents_the_bug():
    raw = _real_state_with_derived_fields().model_dump(mode="json")
    assert "mentioned_entities" not in raw
    assert "explicit_rejections" not in raw
    assert "release_year_range" not in raw


def test_response_state_dict_restores_derived_properties():
    state = _real_state_with_derived_fields()
    d = response_state_dict(state)
    assert d["turn_intent"] == "something from the 90s, not Coldplay"
    values = {m["value"] for m in d["mentioned_entities"]}
    assert {"Radiohead", "Coldplay"} <= values
    assert any(m["sentiment"] > 0 and m["value"] == "Radiohead" for m in d["mentioned_entities"])
    assert any(r["kind"] == "artist" and r["value"] == "Coldplay" for r in d["explicit_rejections"])
    assert d["release_year_range"]["start"] == 1990 and d["release_year_range"]["end"] == 1999


def test_response_state_dict_restores_compiler_policy_properties():
    state = ConversationStateV0Plus(
        turn_intent="play this exact 1995 track",
        retrieval_profile="exact_probe",
        target_artist_mode="new_artist",
        temporal_constraint=TemporalConstraint(
            kind=TemporalConstraintKind.release_date,
            strength=ConstraintStrength.hard,
            start_year=1995,
            end_year=1995,
            apply_as_filter=True,
        ),
    )

    d = response_state_dict(state)

    assert d["intent_mode"] == "refinement"
    assert d["process_constraints"] == {"exploration_policy": "diversify_artists"}
    assert d["routing_tags"] == {
        "exact_entity_probe": True,
        "lyric_search": False,
        "feature_articulation": False,
        "image_or_visual_search": False,
        "hidden_target_search": False,
    }
    assert d["hard_filters"] == [
        {
            "field": "release_date",
            "op": "between",
            "start": "1995-01-01",
            "end": "1995-12-31",
        }
    ]


def test_response_state_dict_release_year_range_none_when_absent():
    d = response_state_dict(ConversationStateV0Plus(turn_intent="anything"))
    assert d["release_year_range"] is None
    assert d["mentioned_entities"] == []
    assert d["explicit_rejections"] == []


def test_format_state_block_renders_derived_fields_via_helper():
    block = format_state_block(response_state_dict(_real_state_with_derived_fields()), None)
    assert "Radiohead" in block
    assert "Coldplay" in block
    assert "Explicit rejections:" in block
    assert "1990-1999" in block
