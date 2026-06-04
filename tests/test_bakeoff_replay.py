from __future__ import annotations

from mcrs.bakeoff.replay import build_turn_inputs
from mcrs.bakeoff.track_lookup import TrackMetadataLookup


def _conversations():
    return [
        {"turn_number": 1, "role": "user", "content": "play smoky lounge"},
        {"turn_number": 1, "role": "music", "content": "t1"},
        {"turn_number": 1, "role": "assistant", "content": "Here's a smoky one."},
        {"turn_number": 2, "role": "user", "content": "another like it"},
        {"turn_number": 2, "role": "music", "content": "t2"},
        {"turn_number": 2, "role": "assistant", "content": "Try this."},
    ]


def _lookup():
    return TrackMetadataLookup.from_rows([
        {"track_id": "t1", "track_name": ["Buena"], "artist_name": ["Morphine"],
         "album_name": ["Yes"], "tag_list": ["smoky"]},
        {"track_id": "t9", "track_name": ["Rec"], "artist_name": ["A"],
         "album_name": ["B"], "tag_list": []},
    ])


def test_build_turn_inputs_history_and_recommend_item():
    sys_prompt, chat_history, recommend_item = build_turn_inputs(
        conversations=_conversations(),
        target_turn_number=2,
        top_track_id="t9",
        lookup=_lookup(),
        system_prompt="SYS",
    )
    assert sys_prompt == "SYS"
    roles = [m["role"] for m in chat_history]
    assert roles == ["user", "assistant", "assistant", "user"]
    assert all(r in {"system", "user", "assistant"} for r in roles)
    assert "Buena" in chat_history[1]["content"]  # t1 (music turn) rewritten via lookup
    assert chat_history[-1]["content"] == "another like it"  # current ask appended
    assert "Rec" in recommend_item


def test_generate_for_model_uses_lm():
    from mcrs.bakeoff.replay import generate_for_model

    class FakeLM:
        def response_generation(self, sys_p, history, item, max_new_tokens=2048):
            return f"{sys_p}|resp:{item[:10]}"

    convs = {"s1": _conversations()}
    turns = [{"session_id": "s1", "turn_number": 2, "top_track_id": "t9", "user_id": "u1"}]
    recs = generate_for_model(
        FakeLM(), turns, lambda uid: f"SYS:{uid}", _lookup(), convs
    )
    assert recs[0]["response"].startswith("SYS:u1|resp:")
    assert recs[0]["session_id"] == "s1"


def test_build_turn_inputs_normalizes_invalid_roles():
    _, chat_history, _ = build_turn_inputs(
        conversations=_conversations(),
        target_turn_number=2,
        top_track_id="t9",
        lookup=_lookup(),
        system_prompt="SYS",
    )
    # no 'music' (or any non-standard) role survives — would 422 on OpenRouter
    assert all(m["role"] in {"system", "user", "assistant"} for m in chat_history)


def test_generate_for_model_state_uses_state_block():
    from mcrs.bakeoff.replay import generate_for_model_state

    class FakeLM:
        def response_generation(self, sys_p, history, item, max_new_tokens=2048):
            return history[0]["content"]  # echo the state block we fed

    turns = [{"session_id": "s1", "turn_number": 1, "top_track_id": "t9", "user_id": "u1"}]
    states = {("s1", 1): {"turn_intent": "play something jazzy"}}
    recs = generate_for_model_state(
        FakeLM(), turns, lambda uid: "SYS", states, _lookup(),
    )
    assert "play something jazzy" in recs[0]["response"]
    assert "[LISTENER CONTEXT]" in recs[0]["response"]
