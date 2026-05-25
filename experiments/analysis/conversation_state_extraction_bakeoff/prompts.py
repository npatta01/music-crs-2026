"""v0+ ConversationState extraction prompt.

The prompt is built around three principles:
- Strict JSON adherence is enforced *outside* the prompt via response_format=json_schema
  (we still tell the model what to do for graceful-degrade if a model doesn't honor it).
- Anchor preservation is required by the rules — the rewrite wave's main failure mode
  is dropping named entities, so the prompt is explicit about it.
- Coreference resolution ("the second one") is spelled out with a worked example.
"""

from __future__ import annotations

import json
from typing import Any

from .schema import ConversationStateV0Plus

SYSTEM = """You extract a structured ConversationState (v0+ schema) from a multi-turn music recommendation conversation.

Output ONE JSON object that validates against the provided schema. No prose, no explanation, no markdown fences. Just JSON.

Rules:
1. Anchor preservation. Every artist / track / album / tag name the user named in the LATEST user turn MUST appear in `turn_intent` AND in `mentioned_entities`. Do not paraphrase named entities away.
2. Never invent. If the conversation does not name something, do not produce a value for it. Prefer an empty list over a guess.
3. `referenced_track_ids` is for EXPLICIT pronoun / positional references only — "the second one", "that previous track", "the one you just played", "that song from earlier". Resolve to the actual played track_id(s) using the played_track_ids list (index 0 = first played). DO NOT populate this field just because the user is reacting to the most recently played track — implicit topic continuity is captured by `track_feedback`. DO NOT populate when the user names the track by title (use `mentioned_entities` with type=track). Empty (`[]`) on the vast majority of turns. If you populate it on every turn, you are over-firing.
4. Sentiment is a 3-value enum: -1, 0, 1. Never a decimal.
5. `intent_mode` is the foundational field:
   - `open_explore`: vibe-led, no anchor ("something chill for studying").
   - `refinement`: tweak the current direction ("more like that but slower").
   - `pivot`: change direction ("actually, can we go heavier?").
   - `playlist_build`: cumulative build ("now add some 90s grunge to the mix").
6. `track_feedback` only includes tracks the user actually reacted to. Silence is not a reaction. `role` mirrors sentiment: sentiment=1 -> `accepted` (default for ALL positive reactions); sentiment=-1 -> `rejected`; sentiment=0 -> `neutral` (user acknowledged the track but it wasn't quite right — "cool but not what I wanted"). `seed` is RESERVED — use only when the user EXPLICITLY pins a specific track as THE anchor: naming it by title ("more like Clair de lune"), referring to it by position ("like that second one"), or asking an analytical question about that one track ("what makes Duality engaging?"). Do NOT use `seed` for ordinary positive reactions to the most recently played track — that's `accepted`. Expect 0 or 1 `seed` entries per turn, never one on every turn.
7. `explicit_rejections` is for FUTURE exclusion ("not X", "no more X", "different from X", "too heavy"). It is a stricter version of `mentioned_entities` with sentiment=-1: rejections also imply the compiler will hard-exclude. Duplicate the entity in both lists when the user is explicitly excluding it from future recs.
8. `hard_filters` in v0+ supports `release_date` only. "Songs from the 90s" -> between [1990-01-01, 1999-12-31]. "Nothing newer than 2010" -> < 2010-01-01.
"""


FEW_SHOT_EXAMPLES: list[dict[str, Any]] = [
    # Example 1: refinement with a positive anchor and a tag rejection
    {
        "user_prompt": {
            "played_track_ids": [
                "t-aaa-1",  # Morphine - Cure for Pain
                "t-bbb-2",  # Tom Waits - Hold On
            ],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Play me something smoky and slow, like late-night bar music."},
                {"turn": 1, "role": "assistant", "text": "How about Morphine?"},
                {"turn": 1, "role": "music", "track_id": "t-aaa-1", "label": "Morphine - Cure for Pain"},
                {"turn": 2, "role": "user", "text": "Yes Morphine is perfect, but the second one was too heavy. Lighter."},
            ],
        },
        "output": {
            "turn_intent": "Smoky, slow late-night bar music like Morphine — lighter than the previous track.",
            "intent_mode": "refinement",
            "track_feedback": [
                {"track_id": "t-aaa-1", "overall_sentiment": 1, "role": "accepted"},
                {"track_id": "t-bbb-2", "overall_sentiment": -1, "role": "rejected"},
            ],
            "referenced_track_ids": ["t-bbb-2"],
            "mentioned_entities": [
                {"type": "artist", "value": "Morphine", "sentiment": 1},
                {"type": "tag", "value": "heavy", "sentiment": -1},
            ],
            "hard_filters": [],
            "explicit_rejections": [
                {"kind": "tag", "value": "heavy", "source_turn": 2}
            ],
        },
    },
    # Example 2: pivot with release_date filter
    {
        "user_prompt": {
            "played_track_ids": ["t-ccc-3"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Some upbeat pop please."},
                {"turn": 1, "role": "assistant", "text": "Here is a current hit."},
                {"turn": 1, "role": "music", "track_id": "t-ccc-3", "label": "Recent Pop Track"},
                {"turn": 2, "role": "user", "text": "Actually scratch that, take me back to 90s grunge. Nothing newer than 2000."},
            ],
        },
        "output": {
            "turn_intent": "90s grunge — pivot away from current pop. Nothing newer than 2000.",
            "intent_mode": "pivot",
            "track_feedback": [],
            "referenced_track_ids": [],
            "mentioned_entities": [
                {"type": "tag", "value": "grunge", "sentiment": 1},
                {"type": "tag", "value": "90s", "sentiment": 1},
            ],
            "hard_filters": [
                {"field": "release_date", "op": "<", "value": "2000-01-01"}
            ],
            "explicit_rejections": [],
        },
    },
    # Example 3: explicit artist rejection (Fugazi pattern)
    {
        "user_prompt": {
            "played_track_ids": [
                "t-ddd-4",  # Fugazi - Waiting Room
            ],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Some post-hardcore from the 80s."},
                {"turn": 1, "role": "assistant", "text": "Try this one."},
                {"turn": 1, "role": "music", "track_id": "t-ddd-4", "label": "Fugazi - Waiting Room"},
                {"turn": 2, "role": "user", "text": "Not Fugazi. Anything else in that scene."},
            ],
        },
        "output": {
            "turn_intent": "Post-hardcore from the 80s, but not Fugazi.",
            "intent_mode": "refinement",
            "track_feedback": [
                {"track_id": "t-ddd-4", "overall_sentiment": -1, "role": "rejected"}
            ],
            "referenced_track_ids": [],
            "mentioned_entities": [
                {"type": "artist", "value": "Fugazi", "sentiment": -1},
                {"type": "tag", "value": "post-hardcore", "sentiment": 1},
                {"type": "tag", "value": "80s", "sentiment": 1},
            ],
            "hard_filters": [],
            "explicit_rejections": [
                {"kind": "artist", "value": "Fugazi", "source_turn": 2}
            ],
        },
    },
]


def render_conversation(conversation: list[dict[str, Any]], played_track_ids: list[str]) -> str:
    """Render the conversation as a compact text block the model can read."""
    lines = [f"played_track_ids (ordered by turn): {played_track_ids}", "", "conversation:"]
    for turn in conversation:
        role = turn.get("role")
        if role == "music":
            label = turn.get("label", "")
            tid = turn.get("track_id", "")
            lines.append(f"  [turn {turn['turn']}] music: track_id={tid}  ({label})")
        else:
            text = turn.get("text", "").strip()
            lines.append(f"  [turn {turn['turn']}] {role}: {text}")
    return "\n".join(lines)


def build_messages(conversation: list[dict[str, Any]], played_track_ids: list[str]) -> list[dict[str, str]]:
    """Build the chat-completions messages list with few-shot examples."""
    messages = [{"role": "system", "content": SYSTEM}]
    for ex in FEW_SHOT_EXAMPLES:
        messages.append(
            {
                "role": "user",
                "content": render_conversation(
                    ex["user_prompt"]["conversation"],
                    ex["user_prompt"]["played_track_ids"],
                ),
            }
        )
        messages.append({"role": "assistant", "content": json.dumps(ex["output"])})
    messages.append(
        {"role": "user", "content": render_conversation(conversation, played_track_ids)}
    )
    return messages


def _harden_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """OpenAI/Azure strict json_schema requires:
    - every object has additionalProperties: false
    - every object's `required` lists all of its properties
    Pydantic doesn't emit either by default for nested models; patch them in.
    """

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            # OpenAI strict mode rejects $ref nodes that carry sibling keywords.
            if "$ref" in node:
                for k in list(node.keys()):
                    if k != "$ref":
                        node.pop(k)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema


def json_schema_for_response_format() -> dict[str, Any]:
    """The schema we pass as response_format=json_schema for strict-mode hosts."""
    schema = _harden_schema(ConversationStateV0Plus.model_json_schema())
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ConversationStateV0Plus",
            "strict": True,
            "schema": schema,
        },
    }
