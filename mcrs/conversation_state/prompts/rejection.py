"""Experimental rejection-focused ConversationState prompt.

This variant keeps the production prompt intact and adds only synthetic
hard-rejection contrast examples. It tests whether examples, rather than a
broader decision rubric, fix hard-rejection misses without disturbing
continuation/exact cases.
"""

from __future__ import annotations

import json
from typing import Any

from mcrs.conversation_state.prompts import current
from mcrs.conversation_state.prompts.common import render_conversation


REJECTION_FOCUSED_EXAMPLES = [
    {
        "user_prompt": {
            "played_track_ids": ["t-radiohead-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Play a moody Radiohead track."},
                {"turn": 1, "role": "music", "track_id": "t-radiohead-1", "label": "Radiohead - Karma Police"},
                {"turn": 2, "role": "user", "text": "Karma Police is great, but I'm good on Radiohead for now. Give me moody alternative rock tracks from other artists."},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "new_artist",
                "summary": "Moody alternative rock tracks from other artists; no more Radiohead for now.",
                "source_turn": 2,
                "evidence_text": "from other artists",
            },
            "facts": [
                {"type": "artist", "value": "Radiohead", "role": "rejected", "anchor_use": "do_not_use", "relation": "exclude", "reuse": "must_exclude", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "good on Radiohead for now"},
                {"type": "attribute", "facet": "genre", "value": "moody alternative rock", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "moody alternative rock"},
                {"type": "attribute", "facet": "performer", "value": "other artists", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "other artists"},
            ],
            "exclusions": [
                {"type": "artist", "value": "Radiohead", "scope": "next_turn_hard", "source_turn": 2, "evidence_text": "good on Radiohead for now"}
            ],
            "track_feedback": [
                {"track_id": "t-radiohead-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-metallica-1"],
            "conversation": [
                {"turn": 7, "role": "user", "text": "Play something heavy and riff-driven like Metallica."},
                {"turn": 7, "role": "music", "track_id": "t-metallica-1", "label": "Metallica - Sad But True"},
                {"turn": 8, "role": "user", "text": "Sad But True is awesome and Metallica is great, but I want new bands with that heavy riff-driven sound, similar in style to Metallica but not them."},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "new_artist",
                "summary": "New bands with a heavy riff-driven sound similar to Metallica, but not Metallica.",
                "source_turn": 8,
                "evidence_text": "new bands",
            },
            "facts": [
                {"type": "artist", "value": "Metallica", "role": "rejected", "anchor_use": "do_not_use", "relation": "exclude", "reuse": "must_exclude", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "but not them"},
                {"type": "attribute", "facet": "sonic", "value": "heavy riff-driven", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "heavy riff-driven sound"},
                {"type": "attribute", "facet": "performer", "value": "new bands", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "new bands"},
            ],
            "exclusions": [
                {"type": "artist", "value": "Metallica", "scope": "next_turn_hard", "source_turn": 8, "evidence_text": "but not them"}
            ],
            "track_feedback": [
                {"track_id": "t-metallica-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
]


SYSTEM = current.SYSTEM
FEW_SHOT_EXAMPLES = current.FEW_SHOT_EXAMPLES + REJECTION_FOCUSED_EXAMPLES
json_schema_for_response_format = current.json_schema_for_response_format


def build_messages(conversation: list[dict[str, Any]], played_track_ids: list[str]) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM}]
    for ex in FEW_SHOT_EXAMPLES:
        messages.append({
            "role": "user",
            "content": render_conversation(
                ex["user_prompt"]["conversation"],
                ex["user_prompt"]["played_track_ids"],
            ),
        })
        messages.append({"role": "assistant", "content": json.dumps(ex["output"])})
    messages.append({"role": "user", "content": render_conversation(conversation, played_track_ids)})
    return messages
