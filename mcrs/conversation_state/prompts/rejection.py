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
            "turn_intent": "Moody alternative rock tracks from other artists; no more Radiohead for now.",
            "track_feedback": [
                {"track_id": "t-radiohead-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "artist", "value": "Radiohead", "role": "rejected", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "good on Radiohead for now"},
                {"type": "tag", "value": "moody alternative rock", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "moody alternative rock"},
                {"type": "tag", "value": "other artists", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "other artists"}
            ],
            "target_artist_mode": "new_artist",
            "retrieval_profile": "novelty",
            "rejections": [
                {"kind": "artist", "value": "Radiohead", "scope": "hard", "source_turn": 2, "evidence_text": "good on Radiohead for now"}
            ],
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
            "turn_intent": "New bands with a heavy riff-driven sound similar to Metallica, but not Metallica.",
            "track_feedback": [
                {"track_id": "t-metallica-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "artist", "value": "Metallica", "role": "rejected", "source_turn": 8, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "but not them"},
                {"type": "tag", "value": "heavy riff-driven", "role": "current_target", "source_turn": 8, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "heavy riff-driven sound"},
                {"type": "tag", "value": "new bands", "role": "current_target", "source_turn": 8, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "new bands"}
            ],
            "target_artist_mode": "new_artist",
            "retrieval_profile": "novelty",
            "rejections": [
                {"kind": "artist", "value": "Metallica", "scope": "hard", "source_turn": 8, "evidence_text": "but not them"}
            ],
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
