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

# Conversation rendering format

The user prompt has two parts:

1. `played_track_ids`: an ordered list of track_id values. Item 1 in this list is the FIRST track played, item 2 is the second, etc. These are the same UUIDs you must echo back in the `track_feedback.track_id` and `referenced_track_ids` fields when you reference them.
2. `conversation`: the turns. Music turns are rendered as `[turn N] music: #M (Artist - Track)`. The `#M` is a 1-indexed pointer into `played_track_ids` — `#1` means `played_track_ids[0]`, `#2` means `played_track_ids[1]`, and so on.

# Field rules

## turn_intent  (string)
The user's active ask in 1–2 sentences. MUST verbatim include every artist / track / album / tag name the user named in the LATEST user turn. Do not paraphrase named entities away. Do not invent entities the user didn't say.

## intent_mode  (enum)
| value | when |
|---|---|
| `open_explore` | vibe-led, no anchor — "something chill for studying" |
| `refinement` | tweak current direction, keep anchors — "more like that but slower" |
| `pivot` | change direction, drop anchors — "actually, can we go heavier?" |
| `playlist_build` | cumulative add on top of anchors — "now add some 90s grunge to the mix" |

## track_feedback  (list)
One entry per played track the user ACTUALLY REACTED TO. Silence is not a reaction.

| sentiment | role | Use when |
|---|---|---|
| 1 | `accepted` | Default for any positive reaction (likes, "yes more like this") |
| -1 | `rejected` | User rejected the track or its qualities |
| 0 | `neutral` | User acknowledged it but it wasn't quite right ("cool but not what I wanted") |
| 1 | `seed` | RARE. User EXPLICITLY pins this specific track as THE anchor. Triggers: naming it by title ("more like Clair de lune"), positional ("like that second one"), or analytic ("what makes Duality engaging?"). Never use `seed` for ordinary positive reactions. Expect 0–1 per turn, not one every turn. |

## referenced_track_ids  (list of track_id)
RARE. Use ONLY when the latest user turn uses an explicit pronoun / positional / temporal reference to a previously-played track: "the second one", "that previous track", "the one you just played", "that song from earlier", "the third recommendation". Resolve `#M` markers to the actual UUID from `played_track_ids`.

Do NOT populate just because the user is reacting to the most recent track (that's `track_feedback`). Do NOT populate when the user names the track by title (that's `mentioned_entities` with type=track). Empty (`[]`) on the vast majority of turns.

## mentioned_entities  (list)
Every artist / album / track / tag named or referenced in any turn, with the user's sentiment (-1, 0, 1) toward it. Negatives go here AND also into `explicit_rejections` when the user is excluding them from future recs.

## explicit_rejections  (list)
FUTURE exclusions. Populate when the user says "not X", "no more X", "different from X", "too heavy", "too gloomy", "stop playing X". Stricter than `mentioned_entities[sentiment=-1]` — the compiler will hard-exclude these.

| kind | excludes |
|---|---|
| `artist` | all tracks by that artist |
| `track` | that specific track_id |
| `tag` | soft-demotes tracks whose tag_list overlaps |

## hard_filters  (list)
v0+ supports `release_date` only. Emit dates as YYYY-MM-DD into typed `start` / `end`.

| user phrasing | filter |
|---|---|
| "Songs from the 90s" | `{op:"between", start:"1990-01-01", end:"1999-12-31"}` |
| "Nothing newer than 2010" | `{op:"<", end:"2010-01-01"}` |
| "After 2020" | `{op:">", start:"2020-01-01"}` |

`start` is inclusive for `between`, strict for `>`. `end` is inclusive for `between`, strict for `<`.

# General

Sentiment is always one of `-1`, `0`, `1`. Never a decimal.
"""


FEW_SHOT_EXAMPLES: list[dict[str, Any]] = [
    # Example 1: refinement with a positive anchor and a tag rejection.
    # Real-data structure: each turn_number has exactly one music entry; the
    # "second one" reference resolves across turns to #2 = played_track_ids[1].
    # IDs are synthetic UUIDs (not real catalog ids) — they only need to teach format.
    {
        "user_prompt": {
            "played_track_ids": [
                "a1111111-1111-4111-8111-111111111111",  # Morphine - Cure for Pain
                "b2222222-2222-4222-8222-222222222222",  # Tom Waits - Hold On
            ],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Play me something smoky and slow, like late-night bar music."},
                {"turn": 1, "role": "music", "track_id": "a1111111-1111-4111-8111-111111111111", "label": "Morphine - Cure for Pain"},
                {"turn": 1, "role": "assistant", "text": "How about Morphine? This one's a classic of the late-night barfly genre."},
                {"turn": 2, "role": "user", "text": "Perfect. Got another one in that vein?"},
                {"turn": 2, "role": "music", "track_id": "b2222222-2222-4222-8222-222222222222", "label": "Tom Waits - Hold On"},
                {"turn": 2, "role": "assistant", "text": "Try this — Tom Waits scratches a similar itch but a bit heavier."},
                {"turn": 3, "role": "user", "text": "Yes Morphine is perfect, but the second one was too heavy. Lighter."},
            ],
        },
        "output": {
            "turn_intent": "Smoky, slow late-night bar music like Morphine — lighter than the previous track.",
            "intent_mode": "refinement",
            "track_feedback": [
                {"track_id": "a1111111-1111-4111-8111-111111111111", "overall_sentiment": 1, "role": "accepted"},
                {"track_id": "b2222222-2222-4222-8222-222222222222", "overall_sentiment": -1, "role": "rejected"},
            ],
            "referenced_track_ids": ["b2222222-2222-4222-8222-222222222222"],
            "mentioned_entities": [
                {"type": "artist", "value": "Morphine", "sentiment": 1},
                {"type": "tag", "value": "heavy", "sentiment": -1},
            ],
            "hard_filters": [],
            "explicit_rejections": [
                {"kind": "tag", "value": "heavy", "source_turn": 3}
            ],
        },
    },
    # Example 2: pivot with release_date filter
    {
        "user_prompt": {
            "played_track_ids": ["c3333333-3333-4333-8333-333333333333"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Some upbeat pop please."},
                {"turn": 1, "role": "assistant", "text": "Here is a current hit."},
                {"turn": 1, "role": "music", "track_id": "c3333333-3333-4333-8333-333333333333", "label": "Recent Pop Track"},
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
                {"field": "release_date", "op": "<", "end": "2000-01-01"}
            ],
            "explicit_rejections": [],
        },
    },
    # Example 3: explicit artist rejection (Fugazi pattern)
    {
        "user_prompt": {
            "played_track_ids": [
                "d4444444-4444-4444-8444-444444444444",  # Fugazi - Waiting Room
            ],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Some post-hardcore from the 80s."},
                {"turn": 1, "role": "assistant", "text": "Try this one."},
                {"turn": 1, "role": "music", "track_id": "d4444444-4444-4444-8444-444444444444", "label": "Fugazi - Waiting Room"},
                {"turn": 2, "role": "user", "text": "Not Fugazi. Anything else in that scene."},
            ],
        },
        "output": {
            "turn_intent": "Post-hardcore from the 80s, but not Fugazi.",
            "intent_mode": "refinement",
            "track_feedback": [
                {"track_id": "d4444444-4444-4444-8444-444444444444", "overall_sentiment": -1, "role": "rejected"}
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
    """Render the conversation as a compact text block the model can read.

    Music turns use a 1-indexed positional marker `#M` that maps to
    `played_track_ids[M-1]`. The marker is what the model uses when resolving
    pronoun references ("the second one") into `referenced_track_ids`; the
    raw UUID is omitted from each line because it's already in the header
    list and would otherwise be repeated in every music line."""
    # Render played_track_ids as numbered lines so the #M marker is visually
    # anchored to its UUID. A python list literal works too but the numbered
    # form makes the mapping unambiguous for the model.
    lines = ["played_track_ids:"]
    for idx, tid in enumerate(played_track_ids, start=1):
        lines.append(f"  #{idx}: {tid}")
    if not played_track_ids:
        lines.append("  (none yet)")
    lines.extend(["", "conversation:"])
    # Per-turn music-marker counter so each music turn gets the right #M.
    music_idx = 0
    for turn in conversation:
        role = turn.get("role")
        if role == "music":
            music_idx += 1
            label = turn.get("label", "")
            label_part = f" ({label})" if label else ""
            lines.append(f"  [turn {turn['turn']}] music: #{music_idx}{label_part}")
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
