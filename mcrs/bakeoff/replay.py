"""Replay response generation over fixed retrieval results."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from mcrs.bakeoff.track_lookup import TrackMetadataLookup
from mcrs.inference_utils import chat_history_parser

_VALID_ROLES = {"system", "user", "assistant"}


def _normalize_role(role: str) -> str:
    return role if role in _VALID_ROLES else "assistant"


def build_turn_inputs(
    conversations: list[dict],
    target_turn_number: int,
    top_track_id: str,
    lookup: TrackMetadataLookup,
    system_prompt: str,
) -> tuple[str, list[dict], str]:
    """Return (system_prompt, chat_history, recommend_item) for one turn,
    reusing the production chat_history_parser with `lookup` as item_db.
    The current-turn user query is appended last, matching crs_baseline.batch_chat."""
    music_crs = SimpleNamespace(item_db=lookup)
    chat_history, user_query = chat_history_parser(
        conversations, music_crs, target_turn_number
    )
    chat_history = [
        {"role": _normalize_role(m["role"]), "content": m["content"]}
        for m in chat_history
    ]
    chat_history.append({"role": "user", "content": user_query})
    recommend_item = lookup.id_to_metadata(top_track_id)
    return system_prompt, chat_history, recommend_item


def generate_for_model(lm: Any, turns: list[dict], build_system_prompt,
                       lookup: TrackMetadataLookup, conversations_by_session: dict,
                       max_new_tokens: int = 2048) -> list[dict]:
    """For each turn record {session_id, turn_number, top_track_id, user_id}, generate
    a response with `lm`. `build_system_prompt(user_id) -> str` produces the per-turn
    system prompt (so the user profile can be injected like production)."""
    out = []
    for t in turns:
        convs = conversations_by_session[t["session_id"]]
        system_prompt = build_system_prompt(t.get("user_id"))
        sys_p, history, item = build_turn_inputs(
            convs, t["turn_number"], t["top_track_id"], lookup, system_prompt
        )
        resp = lm.response_generation(sys_p, history, item, max_new_tokens=max_new_tokens)
        out.append({**t, "response": resp})
    return out
