import numpy as np

from mcrs.analysis.conversation_semantic import (
    combine_text_and_prior_vectors,
    conversation_input_text,
    hashed_text_vector,
    prior_track_centroid,
    semantic_leaf_map,
    state_to_text,
)


def test_state_to_text_extracts_request_facts_and_routing():
    trace = {
        "intent_mode": "pivot",
        "extracted_state": {
            "current_request": {"summary": "Find upbeat synth pop."},
            "facts": [
                {"type": "attribute", "value": "synth pop", "role": "current_target"},
                {"type": "artist", "value": "Robyn", "role": "avoid"},
            ],
            "temporal_constraint": {"start_year": 2000, "end_year": 2012, "strength": "soft"},
            "routing_tags": {"feature_articulation": True, "lyric_search": False},
        },
    }

    text = state_to_text(trace)

    assert "request: Find upbeat synth pop." in text
    assert "intent: pivot" in text
    assert "attribute=synth pop" in text
    assert "artist=Robyn" in text
    assert "years: 2000-2012 soft" in text
    assert "routes: feature_articulation" in text


def test_conversation_input_text_view_controls_history_and_prior_tracks():
    session = {
        "user_text_by_turn": {
            1: "Play some disco.",
            2: "Now make it darker.",
            3: "Something with a driving bassline.",
        },
        "played_by_turn": {
            1: ["t1"],
            2: ["t2"],
            3: ["future"],
        },
        "listener_goal": "Explore dance music.",
    }
    trace = {
        "extracted_state": {
            "current_request": {"summary": "Driving dark dance track."},
            "facts": [{"type": "attribute", "value": "dark", "role": "current_target"}],
        }
    }
    lookup = {"t1": "Donna Summer - I Feel Love", "t2": "New Order - Blue Monday", "future": "Do Not Use"}

    text = conversation_input_text(
        session,
        trace,
        turn_number=3,
        view="last_turn_state_prior",
        track_lookup=lookup,
    )

    assert "current user: Something with a driving bassline." in text
    assert "state: request: Driving dark dance track." in text
    assert "prior tracks: Donna Summer - I Feel Love | New Order - Blue Monday" in text
    assert "Do Not Use" not in text
    assert "Play some disco." not in text


def test_full_conversation_view_includes_prior_user_turns():
    session = {
        "user_text_by_turn": {1: "First", 2: "Second"},
        "played_by_turn": {1: ["t1"]},
        "listener_goal": "",
    }

    text = conversation_input_text(
        session,
        {},
        turn_number=2,
        view="full_conversation_state_prior",
        track_lookup={"t1": "Track One"},
    )

    assert "conversation: turn 1: First | turn 2: Second" in text
    assert "prior tracks: Track One" in text


def test_hashed_text_vector_is_deterministic_unit_norm_and_signed():
    left = hashed_text_vector("bright bright guitar", dim=16)
    right = hashed_text_vector("bright bright guitar", dim=16)
    other = hashed_text_vector("dark piano", dim=16)

    np.testing.assert_allclose(left, right)
    assert np.isclose(np.linalg.norm(left), 1.0)
    assert not np.allclose(left, other)
    assert np.any(left < 0)


def test_prior_track_centroid_uses_only_tracks_before_turn():
    session = {"played_by_turn": {1: ["a"], 2: ["missing"], 3: ["b"]}}
    track_to_code = {"a": 0, "b": 1}
    item_vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    centroid = prior_track_centroid(
        session,
        turn_number=3,
        track_to_code=track_to_code,
        item_vectors=item_vectors,
    )

    np.testing.assert_allclose(centroid, np.array([1.0, 0.0], dtype=np.float32))


def test_combine_text_and_prior_vectors_concatenates_normalized_blocks():
    text_vec = np.array([3.0, 4.0], dtype=np.float32)
    prior_vec = np.array([0.0, 2.0], dtype=np.float32)

    combined = combine_text_and_prior_vectors(text_vec, prior_vec)

    np.testing.assert_allclose(combined, np.array([0.6, 0.8, 0.0, 1.0], dtype=np.float32))


def test_semantic_leaf_map_groups_tracks_by_valid_codes():
    rows = [
        {"track_id": "a", "sid_l1": 1, "sid_l2": 3},
        {"track_id": "b", "sid_l1": 1, "sid_l2": 3},
        {"track_id": "c", "sid_l1": 2, "sid_l2": 0},
    ]

    leaf_map = semantic_leaf_map(rows)

    assert leaf_map == {(1, 3): ["a", "b"], (2, 0): ["c"]}
