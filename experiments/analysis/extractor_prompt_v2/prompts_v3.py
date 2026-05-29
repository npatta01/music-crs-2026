"""v0+ ConversationState extraction prompt — v3 (generous extraction + vocabulary bridging).

Design change from v2/v2c (and WHY):

v2c optimized AGAINST hallucination with a VERBATIM-ONLY hard rule ("every tag
must be a literal substring of the user text; when in doubt, omit"). That was a
mistake. The downstream retriever SOFT-BOOSTS on tags, so the cost asymmetry is:
  - a missing tag → the GT track is unreachable (expensive)
  - an extra plausible tag → mildly diluted ranking (cheap)
So we should extract GENEROUSLY, not conservatively. Moreover the original
textside writeup's #2 failure mode was *vocabulary mismatch*: the user says
"D&B" / "thoughtful", the catalog tags say "drum and bass" / "post-hardcore".
VERBATIM-ONLY forbade exactly the bridging that closes that gap.

v3 principles:
  1. EXTRACT GENEROUSLY. Boosting absorbs false positives; under-extraction is
     the expensive error.
  2. BRIDGE TO CATALOG VOCABULARY. Emit the user's surface words AND their
     standard music-catalog forms (expand abbreviations, add the obvious
     genre/subgenre the words imply).
  3. ONE guardrail: never invent a *specific named entity* (artist / track /
     album / platform) the user didn't reference. Generic descriptors are
     fair game; fabricated proper nouns are not.
  4. Era → release_date is a single, prominent, non-optional step.
  5. No hard-coded stopword lists. The model gets the principle (is this word
     describing the music they WANT, or reacting to a track already played?).

Drop-in compatible: same build_messages / json_schema_for_response_format
surface as v2/v2c.
"""

from __future__ import annotations

import json
from typing import Any

from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
    ConversationStateV0Plus,
)
from experiments.analysis.conversation_state_extraction_bakeoff.prompts import (
    _harden_schema,
    render_conversation,
)
from experiments.analysis.extractor_prompt_v2.prompts_v2 import _strip_comments

SYSTEM = """You extract a structured ConversationState (v0+ schema) from a multi-turn music recommendation conversation.

Output ONE JSON object that validates against the provided schema. No prose, no markdown fences. Just JSON.

# How the conversation is rendered
1. `played_track_ids`: ordered list of track_id UUIDs. `#M` markers in the conversation point at `played_track_ids[M-1]`. Echo these UUIDs in `track_feedback.track_id` / `referenced_track_ids`.
2. `conversation`: the turns. Music turns look like `[turn N] music: #M (Artist - Track)`.

# Your goal
Capture everything a music librarian would need to find the user's NEXT track: the named artists/tracks/albums they care about, the descriptive qualities they want, any era constraint, and anything they're rejecting. The downstream retriever soft-boosts on what you emit, so **lean toward extracting more, not less** — a missing signal makes the target unreachable; an extra plausible one barely costs anything.

---

## mentioned_entities  (the core field — list of {type, value, sentiment})
`type` ∈ artist | album | track | tag. `sentiment` ∈ -1 | 0 | 1. Do TWO passes over the LATEST user turn:

### Pass 1 — NAMED ENTITIES (proper nouns)
Every artist / band / track / album the user names goes in, even when it's buried mid-sentence ("more Eminem songs", "Destiny's Child is awesome", "in the style of Pink Floyd"). These are the retriever's strongest anchors — never drop them.

Sentiment from the surrounding clause:
| pattern | sentiment |
|---|---:|
| "I love/like X", "more X", "anything by X", "like X", "in the style of X" | 1 |
| "X is cool/fine but [wants something else]" — comparison, not a request for more X | 0 |
| "not X", "no more X", "different from X", "stop playing X" | -1 (also add to explicit_rejections) |

GUARDRAIL: only emit names the user actually referenced. Never invent an artist/track/album/platform the user didn't say.

### Pass 2 — DESCRIPTIVE TAGS (extract generously + bridge to catalog vocabulary)
Emit a tag for every quality the user uses to describe the music they want. For each one, emit BOTH:
  - the user's own word(s), AND
  - the standard music-catalog form(s) of that concept.

Bridging is the point — the catalog uses canonical tags, the user uses casual language. Examples of good bridging:
| user wrote | emit (all of) |
|---|---|
| "D&B" | `D&B`, `drum and bass`, `dnb` |
| "hip hop" | `hip hop`, `hip-hop` |
| "old school rap" | `old school rap`, `old school hip hop`, `hip-hop` |
| "songs to chill to" | `chill`, `chillout`, `mellow` |
| "stuff that slaps" | `energetic`, `upbeat`, `banger` |
| "music for a workout" | `workout`, `energetic`, `high-energy` |
| "classic rock" | `classic rock`, `rock`, `classic` |
| "female-fronted metal" | `female fronted`, `female vocalist`, `metal` |

Also emit the obvious genre/subgenre a knowledgeable listener would infer from named artists ("like Megadeth" → `thrash metal`, `metal`; "like Burial" → `dubstep`, `electronic`). This is allowed even though it's not a literal word — it bridges to how the catalog tags those tracks.

What is NOT a tag: words that REACT to a track already played rather than describe what they want next. "That's a classic!", "this is awesome", "love it", "perfect", "great pick" — these express approval of the current track (capture via track_feedback sentiment), not a quality to search for. BUT the same word IS a tag when it describes the request: "give me a *classic* rock song", "something *upbeat*". Judge by role in the sentence, not the word.

When unsure whether a descriptor is worth emitting: emit it. Generosity is safe here.

---

## turn_intent  (string)
The user's active ask in 1–2 sentences, in their words. Include every named entity verbatim. This is for humans/logging; the retriever uses mentioned_entities, so anything important here must ALSO be in mentioned_entities.

## intent_mode  (enum)
`open_explore` (vibe, no anchor) | `refinement` (tweak, keep anchors) | `pivot` (change direction, drop anchors) | `playlist_build` (add on top of anchors).

## track_feedback  (list — one per played track the user actually reacted to)
sentiment 1 `accepted` (any positive reaction) | -1 `rejected` | 0 `neutral` ("cool but not it") | 1 `seed` (RARE — user explicitly pins THIS track as the anchor: names it, "the second one", "what makes X engaging"). Silence is not a reaction.

## referenced_track_ids  (list — RARE)
Only for explicit pronoun/positional/temporal references to a played track ("the second one", "that previous track"). Resolve `#M` → UUID. Empty on most turns.

## explicit_rejections  (list of {kind, value, source_turn})
FUTURE exclusions: "not X", "no more X", "too heavy", "different from X". kind ∈ artist | track | tag. Stricter than a -1 sentiment — the compiler hard-excludes artist/track and soft-demotes tag.
Note: "more like X but Y" means X is a POSITIVE anchor and Y a positive tag — NOT a rejection of X.

## Era / decade / century → release_year_range
If the user mentions ANY time period — a decade ("80s", "early 2010s", "the nineties"), a century ("19th century"), or a year bound ("after 2015", "nothing newer than 2010") — convert it to integer year bounds in `release_year_range`, using your world knowledge. Also emit the era phrase as a positive `tag`.

`release_year_range` = `{start: <year|null>, end: <year|null>}`. Either bound may be null for open-ended. ALWAYS make start ≤ end.

| user says | release_year_range |
|---|---|
| "early 2010s" | `{start: 2010, end: 2014}` |
| "late 90s" | `{start: 1995, end: 1999}` |
| "the 80s" | `{start: 1980, end: 1989}` |
| "19th century" | `{start: 1801, end: 1900}` |
| "after the 19th century" | `{start: 1901, end: null}` |
| "after 2015" | `{start: 2015, end: null}` |
| "nothing newer than 2010" / "before 2010" | `{start: null, end: 2010}` |
| (no time period mentioned) | omit / null |

This is a SOFT hint for the reranker, not a hard filter. Leave `hard_filters: []` unless the user states an absolute, non-negotiable cutoff. Do the year conversion yourself with world knowledge (you know "19th century" = 1801–1900); do not leave it as prose.

# General
Sentiment is always -1, 0, or 1. Never a decimal.
"""


# Few-shot examples: the v2c set, but the tag lists now demonstrate BRIDGING
# (user word + catalog-canonical forms) rather than verbatim-only.
FEW_SHOT_EXAMPLES: list[dict[str, Any]] = [
    # Example 1: refinement; bridge "smoky/bar music" → catalog vocab.
    {
        "user_prompt": {
            "played_track_ids": [
                "a1111111-1111-4111-8111-111111111111",
                "b2222222-2222-4222-8222-222222222222",
            ],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Play me something smoky and slow, like late-night bar music."},
                {"turn": 1, "role": "music", "track_id": "a1111111-1111-4111-8111-111111111111", "label": "Morphine - Cure for Pain"},
                {"turn": 1, "role": "assistant", "text": "How about Morphine?"},
                {"turn": 2, "role": "user", "text": "Perfect. Got another one in that vein?"},
                {"turn": 2, "role": "music", "track_id": "b2222222-2222-4222-8222-222222222222", "label": "Tom Waits - Hold On"},
                {"turn": 2, "role": "assistant", "text": "Try this — Tom Waits."},
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
                {"type": "tag", "value": "smoky", "sentiment": 1},
                {"type": "tag", "value": "slow", "sentiment": 1},
                {"type": "tag", "value": "late-night", "sentiment": 1},
                {"type": "tag", "value": "bar music", "sentiment": 1},
                {"type": "tag", "value": "lounge", "sentiment": 1},
                {"type": "tag", "value": "mellow", "sentiment": 1},
                {"type": "tag", "value": "heavy", "sentiment": -1},
            ],
            "hard_filters": [],
            "explicit_rejections": [{"kind": "tag", "value": "heavy", "source_turn": 3}],
        },
    },
    # Example 2: pivot; era → release_date + era tag; bridge "grunge".
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
                {"type": "tag", "value": "alternative rock", "sentiment": 1},
                {"type": "tag", "value": "rock", "sentiment": 1},
            ],
            # era ("Nothing newer than 2000") is left to the downstream parser, which reads turn_intent
            "hard_filters": [],
            "release_year_range": {"start": 1990, "end": 1999},
            "explicit_rejections": [],
        },
    },
    # Example 3: rejection + era + bridge "post-hardcore".
    {
        "user_prompt": {
            "played_track_ids": ["d4444444-4444-4444-8444-444444444444"],
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
                {"type": "tag", "value": "hardcore punk", "sentiment": 1},
                {"type": "tag", "value": "punk", "sentiment": 1},
                {"type": "tag", "value": "80s", "sentiment": 1},
            ],
            "hard_filters": [],
            "release_year_range": {"start": 1980, "end": 1989},
            "explicit_rejections": [{"kind": "artist", "value": "Fugazi", "source_turn": 2}],
        },
    },
    # Example 4: embedded artist + track + descriptor decomposition + era filter.
    {
        "user_prompt": {
            "played_track_ids": ["e5555555-5555-4555-8555-555555555555"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Some popular alternative rock from the late 90s."},
                {"turn": 1, "role": "assistant", "text": "Here's one."},
                {"turn": 1, "role": "music", "track_id": "e5555555-5555-4555-8555-555555555555", "label": "Red Hot Chili Peppers - On Mercury"},
                {"turn": 2, "role": "user", "text": "Another highly popular alternative rock track with a reflective or atmospheric quality, similar to Red Hot Chili Peppers - On Mercury, from the late 90s or early 2000s."},
            ],
        },
        "output": {
            "turn_intent": "Another highly popular alternative rock track with a reflective or atmospheric quality, similar to Red Hot Chili Peppers - On Mercury, from the late 90s or early 2000s.",
            "intent_mode": "refinement",
            "track_feedback": [
                {"track_id": "e5555555-5555-4555-8555-555555555555", "overall_sentiment": 1, "role": "accepted"}
            ],
            "referenced_track_ids": [],
            "mentioned_entities": [
                {"type": "artist", "value": "Red Hot Chili Peppers", "sentiment": 1},
                {"type": "track", "value": "On Mercury", "sentiment": 1},
                {"type": "tag", "value": "popular", "sentiment": 1},
                {"type": "tag", "value": "alternative rock", "sentiment": 1},
                {"type": "tag", "value": "rock", "sentiment": 1},
                {"type": "tag", "value": "reflective", "sentiment": 1},
                {"type": "tag", "value": "atmospheric", "sentiment": 1},
                {"type": "tag", "value": "late 90s", "sentiment": 1},
                {"type": "tag", "value": "early 2000s", "sentiment": 1},
            ],
            "hard_filters": [],
            "release_year_range": {"start": 1995, "end": 2004},
            "explicit_rejections": [],
        },
    },
    # Example 5: "classic" as a STYLE descriptor (a tag), plus reaction "classic" that is NOT a tag.
    {
        "user_prompt": {
            "played_track_ids": ["f6666666-6666-4666-8666-666666666666"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Play some classic 90s hip hop."},
                {"turn": 1, "role": "assistant", "text": "Here you go."},
                {"turn": 1, "role": "music", "track_id": "f6666666-6666-4666-8666-666666666666", "label": "Nas - N.Y. State of Mind"},
                {"turn": 2, "role": "user", "text": "Oh that's a classic! Love it. Give me another classic boom bap track from that era."},
            ],
        },
        "output": {
            "turn_intent": "Another classic boom bap track from the 90s, after enjoying Nas - N.Y. State of Mind.",
            "intent_mode": "refinement",
            "track_feedback": [
                {"track_id": "f6666666-6666-4666-8666-666666666666", "overall_sentiment": 1, "role": "accepted"}
            ],
            "referenced_track_ids": [],
            "mentioned_entities": [
                {"type": "artist", "value": "Nas", "sentiment": 1},
                {"type": "track", "value": "N.Y. State of Mind", "sentiment": 1},
                {"type": "tag", "value": "classic", "sentiment": 1},
                {"type": "tag", "value": "boom bap", "sentiment": 1},
                {"type": "tag", "value": "90s", "sentiment": 1},
                {"type": "tag", "value": "hip hop", "sentiment": 1},
                {"type": "tag", "value": "hip-hop", "sentiment": 1},
                {"type": "tag", "value": "east coast hip hop", "sentiment": 1}
            ],
            "hard_filters": [],
            "release_year_range": {"start": 1990, "end": 1999},
            "explicit_rejections": [],
        },
    },
]


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


def json_schema_for_response_format() -> dict[str, Any]:
    schema = _harden_schema(ConversationStateV0Plus.model_json_schema())
    schema = _strip_comments(schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ConversationStateV0Plus",
            "strict": True,
            "schema": schema,
        },
    }
