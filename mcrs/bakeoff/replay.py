"""Replay response generation over fixed retrieval results."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from mcrs.bakeoff.track_lookup import TrackMetadataLookup
from mcrs.inference_utils import chat_history_parser


def build_turn_inputs(
    conversations: list[dict],
    target_turn_number: int,
    top_track_id: str,
    lookup: TrackMetadataLookup,
    system_prompt: str,
) -> tuple[str, list[dict], str]:
    """Return (system_prompt, chat_history, recommend_item) for one turn,
    reusing the production chat_history_parser with `lookup` as item_db."""
    music_crs = SimpleNamespace(item_db=lookup)
    chat_history, _user_query = chat_history_parser(
        conversations, music_crs, target_turn_number
    )
    recommend_item = lookup.id_to_metadata(top_track_id)
    return system_prompt, chat_history, recommend_item


def generate_for_model(lm: Any, turns: list[dict], system_prompt: str,
                       lookup: TrackMetadataLookup, conversations_by_session: dict,
                       max_new_tokens: int = 256) -> list[dict]:
    """For each turn record {session_id, turn_number, top_track_id}, generate a
    response with `lm` (a LITELLM_LM). Returns enriched records with `response`."""
    out = []
    for t in turns:
        convs = conversations_by_session[t["session_id"]]
        sys_p, history, item = build_turn_inputs(
            convs, t["turn_number"], t["top_track_id"], lookup, system_prompt
        )
        resp = lm.response_generation(sys_p, history, item, max_new_tokens=max_new_tokens)
        out.append({**t, "response": resp})
    return out
