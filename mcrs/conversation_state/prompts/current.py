"""Current v0+ ConversationState extraction prompt.

This prompt is kept as `prompt_version: current` in configs and also supports
the historical `v4` alias. It extends the previous reference prompt with the
same generous-extraction + vocabulary-bridging philosophy, same
era→release_year_range conversion, same tag-bridging tables, and same public API
(`SYSTEM`, `FEW_SHOT_EXAMPLES`, `build_messages`, `json_schema_for_response_format`).

The ONLY additions over v3 are the two new schema fields introduced in
`ConversationStateV0Plus`:
  - `routing_tags`: 5 additive booleans that route a turn to the right retrieval
    branch (exact_entity_probe, lyric_search, feature_articulation,
    image_or_visual_search, hidden_target_search). Multiple may be true; all
    default false when there is no signal.
  - `lyrical_theme`: a short phrase describing what the lyrics should be ABOUT,
    set only when `lyric_search` is true; otherwise null.

SYSTEM gains a `## routing_tags` section and a `## lyrical_theme` line, and the
few-shot set gains two examples (one lyric-intent, one sonic/feature-intent) so
the model sees valid outputs that populate the new fields.

`json_schema_for_response_format` is DERIVED from
`ConversationStateV0Plus.model_json_schema()` (via shared schema helpers), so
the new fields appear in the response schema automatically — no hardcoded
schema dict to maintain.

Drop-in compatible: same build_messages / json_schema_for_response_format
surface as the previous reference prompt.
"""

from __future__ import annotations

import json
from typing import Any

from mcrs.conversation_state.schema import (
    ConversationStateV0Plus,
)
from mcrs.conversation_state.prompts.common import (
    harden_schema,
    render_conversation,
    strip_schema_annotations,
)

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

## process_constraints.exploration_policy  (enum)
Orthogonal to intent_mode (what the user is doing) — this is how to vary along the artist/album axes. One of:
| value | when |
|---|---|
| `exploit` | SAME source: "more by them", "another by this artist", "more from this album" |
| `diversify_artists` | SAME style/genre/era, DIFFERENT artist: "another <genre> track", "more bands like this", "something else in this vein". ALSO when the user rejects an artist by name but still wants continuation in that style. |
| `diversify_albums` | Same artist OK, different album. Rare. |
| `balanced` | DEFAULT — no clear signal ("more like this", "something similar"). |
Heuristics: "more <genre> tracks" → diversify_artists; "more from <artist>" → exploit; a `kind=artist` explicit_rejection with no replacement artist → diversify_artists. Emit as `{"exploration_policy": "<value>"}`.

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

## routing_tags  (object of 5 booleans)
Additive route flags that tell the compiler which retrieval branch fits this turn. Multiple may be true. Default ALL false when there is no signal.
- `exact_entity_probe`: set true ONLY when the latest user REQUEST names a specific artist/track/album as the thing to retrieve — "play Bohemian Rhapsody", "more by Radiohead", "tracks similar to OK Computer". Do NOT set it when a named entity appears merely as a REACTION to a track already played ("that's a classic!", "love it", "Morphine is perfect", "Nas is great") or when the entity is REJECTED ("not Fugazi") — those are track_feedback / explicit_rejections, not a fetch request. Test: is the named entity what's being asked FOR this turn, or just reacted to? When the turn only reacts and then asks for other qualities (genre, mood, "lighter"), exact_entity_probe is false.
- `lyric_search`: set true ONLY when the user quotes or paraphrases ACTUAL LYRIC WORDS from the song they want — a remembered line, a hook, a phrase that appears IN the lyrics ("the one that goes 'we are young, so let's set the world on fire'", "find the song with the line 'hello darkness my old friend'", "it has the words 'mr. brightside'"). This branch does EXACT/CLOSE lyric matching against real lyric text. Do NOT set it for thematic, topical, or mood requests about what a song is ABOUT ("a song about heartbreak", "something about the ocean", "deep meaningful lyrics") — those are NOT lyric searches; capture the subject/mood as `tag` entities instead. Test: did the user supply actual words that would literally appear in the lyrics? If they only described a topic/feeling, lyric_search is FALSE.
- `feature_articulation`: set true when the user describes the SOUND/feel — sonic descriptors, mood, instrumentation, tempo ("dark and brooding synths", "fast punchy drums", "something mellow and acoustic").
- `image_or_visual_search`: set true when the user describes the album cover / a visual ("the one with the prism on the cover", "a red album cover with a face").
- `hidden_target_search`: set true when the user is trying to recall a specific half-remembered track ("that song that goes da-da-dum", "I forget the name but it was in that movie").

## lyrical_theme  (string | null)
When `lyric_search` is true, set `lyrical_theme` to the ACTUAL LYRIC WORDS the user quoted or paraphrased — verbatim if possible (e.g. 'we are young so let\'s set the world on fire', 'hello darkness my old friend'). This string is matched directly against real lyric text, so it must be lyric words, NOT a description of the topic. Do NOT summarize or abstract it into a theme ('heartbreak', 'nostalgia' are WRONG here). If the user only described what a song is about (a topic/mood) without quoting lyric words, then `lyric_search` is false and `lyrical_theme` is null.

# General
Sentiment is always -1, 0, or 1. Never a decimal.
"""


# Few-shot examples: the v3 set (tag lists demonstrate BRIDGING — user word +
# catalog-canonical forms), plus two v4 examples that exercise routing_tags /
# lyrical_theme (one lyric-intent turn, one sonic/feature turn).
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
            "release_year_range": None,
            "process_constraints": {"exploration_policy": "balanced"},
            "explicit_rejections": [{"kind": "tag", "value": "heavy", "source_turn": 3}],
            # Morphine is a REACTION ("perfect"); the request is "lighter" (an
            # attribute change), not "fetch Morphine" -> exact_entity_probe false.
            "routing_tags": {
                "exact_entity_probe": False,
                "lyric_search": False,
                "feature_articulation": True,
                "image_or_visual_search": False,
                "hidden_target_search": False,
            },
            "lyrical_theme": None,
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
            "process_constraints": {"exploration_policy": "diversify_artists"},
            "explicit_rejections": [],
            "routing_tags": {
                "exact_entity_probe": False,
                "lyric_search": False,
                "feature_articulation": True,
                "image_or_visual_search": False,
                "hidden_target_search": False,
            },
            "lyrical_theme": None,
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
            "process_constraints": {"exploration_policy": "diversify_artists"},
            "explicit_rejections": [{"kind": "artist", "value": "Fugazi", "source_turn": 2}],
            # Fugazi is REJECTED and the request is "anything else in that scene"
            # (genre, not a named target) -> exact_entity_probe false.
            "routing_tags": {
                "exact_entity_probe": False,
                "lyric_search": False,
                "feature_articulation": True,
                "image_or_visual_search": False,
                "hidden_target_search": False,
            },
            "lyrical_theme": None,
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
            "process_constraints": {"exploration_policy": "balanced"},
            "explicit_rejections": [],
            "routing_tags": {
                "exact_entity_probe": True,
                "lyric_search": False,
                "feature_articulation": True,
                "image_or_visual_search": False,
                "hidden_target_search": False,
            },
            "lyrical_theme": None,
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
            "process_constraints": {"exploration_policy": "diversify_artists"},
            "explicit_rejections": [],
            # Nas is a REACTION ("that's a classic! love it"); the request is
            # "another classic boom bap track" (a style, not a named target) ->
            # exact_entity_probe false.
            "routing_tags": {
                "exact_entity_probe": False,
                "lyric_search": False,
                "feature_articulation": True,
                "image_or_visual_search": False,
                "hidden_target_search": False,
            },
            "lyrical_theme": None,
        },
    },
    # Example 6 (v4): LYRIC INTENT — user asks by what the lyrics are ABOUT.
    # lyric_search=true + lyrical_theme set; all other routing tags false.
    {
        "user_prompt": {
            "played_track_ids": [],
            "conversation": [
                {"turn": 1, "role": "user", "text": "I want songs with lyrics about heartbreak and moving on after a breakup."},
            ],
        },
        "output": {
            "turn_intent": "Songs with lyrics about heartbreak and moving on after a breakup.",
            "intent_mode": "open_explore",
            "track_feedback": [],
            "referenced_track_ids": [],
            "mentioned_entities": [
                {"type": "tag", "value": "heartbreak", "sentiment": 1},
                {"type": "tag", "value": "breakup", "sentiment": 1},
                {"type": "tag", "value": "moving on", "sentiment": 1},
            ],
            "hard_filters": [],
            "release_year_range": None,
            "process_constraints": {"exploration_policy": "balanced"},
            "explicit_rejections": [],
            "routing_tags": {
                "exact_entity_probe": False,
                "lyric_search": False,
                "feature_articulation": False,
                "image_or_visual_search": False,
                "hidden_target_search": False,
            },
            "lyrical_theme": "heartbreak and moving on after a breakup",
        },
    },
    # Example 7 (v4): SONIC / FEATURE INTENT — user describes the SOUND/feel.
    # feature_articulation=true; lyrical_theme null.
    {
        "user_prompt": {
            "played_track_ids": [],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Give me something with dark brooding synths, a slow heavy beat, and a cold atmospheric feel."},
            ],
        },
        "output": {
            "turn_intent": "Something with dark brooding synths, a slow heavy beat, and a cold atmospheric feel.",
            "intent_mode": "open_explore",
            "track_feedback": [],
            "referenced_track_ids": [],
            "mentioned_entities": [
                {"type": "tag", "value": "dark", "sentiment": 1},
                {"type": "tag", "value": "brooding", "sentiment": 1},
                {"type": "tag", "value": "synths", "sentiment": 1},
                {"type": "tag", "value": "synth", "sentiment": 1},
                {"type": "tag", "value": "slow", "sentiment": 1},
                {"type": "tag", "value": "heavy", "sentiment": 1},
                {"type": "tag", "value": "atmospheric", "sentiment": 1},
                {"type": "tag", "value": "cold", "sentiment": 1},
            ],
            "hard_filters": [],
            "release_year_range": None,
            "process_constraints": {"exploration_policy": "balanced"},
            "explicit_rejections": [],
            "routing_tags": {
                "exact_entity_probe": False,
                "lyric_search": False,
                "feature_articulation": True,
                "image_or_visual_search": False,
                "hidden_target_search": False,
            },
            "lyrical_theme": None,
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
    schema = harden_schema(ConversationStateV0Plus.model_json_schema())
    schema = strip_schema_annotations(schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ConversationStateV0Plus",
            "strict": True,
            "schema": schema,
        },
    }


# --------------------------------------------------------------------------- #
# Google / Gemini responseSchema compatibility transform
# --------------------------------------------------------------------------- #
# Google's Gemini structured-output validator (the OpenAPI-3.0 subset that
# OpenRouter routes a `response_format` to for `google/gemini-*` models) is
# STRICTER than OpenAI/deepseek about schema shape. It rejects our default
# Pydantic-derived schema with, e.g.:
#     "schema at properties.mentioned_entities.items requires unspecified
#      property 'type'"
# because Pydantic renders `list[MentionedEntity]` items as a bare
# `{"$ref": ...}` (no `type`), and Optional fields as a typeless
# `anyOf:[{...}, {"type":"null"}]`. Per the Gemini docs the supported subset is
# {type, format, description, nullable, enum, maxItems, minItems, properties,
# required, propertyOrdering, items, anyOf}; EVERY node needs a `type`, and
# nullability is expressed via `"nullable": true`, NOT a `{"type":"null"}`
# union. (https://ai.google.dev/gemini-api/docs/structured-output)
#
# This transform produces a Gemini-safe schema:
#   1. Inlines every `$ref` against `$defs` (Gemini routing via OpenRouter does
#      not reliably resolve our local $ref/$defs; inlining is safest).
#   2. Collapses `anyOf:[X, {"type":"null"}]` -> X with `"nullable": true`.
#   3. Flattens any remaining typeless `anyOf` (a union of object variants) into
#      a single `type:"object"` whose `properties` is the union of all variants'
#      properties; `required` keeps only keys present in EVERY variant (flatten
#      makes variant-specific keys optional). Our MentionedEntity/ExplicitRejection
#      lists are single-variant so this is lossless for them, but it stays correct
#      for genuine unions too.
#   4. Drops keys outside the Gemini-supported subset.
# The Pydantic model is still the real validation gate (the extractor re-parses
# the model output into ConversationStateV0Plus), so a slightly more permissive
# wire schema is acceptable.

# Keys Gemini's responseSchema (OpenAPI subset) accepts on a schema node.
_GEMINI_ALLOWED_KEYS = frozenset(
    {
        "type",
        "format",
        "description",
        "nullable",
        "enum",
        "maxItems",
        "minItems",
        "properties",
        "required",
        "propertyOrdering",
        "items",
        "anyOf",
    }
)


def _resolve_ref(ref: str, defs: dict[str, Any]) -> dict[str, Any]:
    # Only local "#/$defs/Name" refs are produced by Pydantic.
    name = ref.split("/")[-1]
    target = defs.get(name)
    if target is None:
        raise KeyError(f"cannot resolve $ref {ref!r}: {name} not in $defs")
    return target


def _gemini_node(node: Any, defs: dict[str, Any]) -> Any:
    """Recursively rewrite one schema node into the Gemini-safe subset."""
    if isinstance(node, list):
        return [_gemini_node(v, defs) for v in node]
    if not isinstance(node, dict):
        return node

    # 1. Inline a bare $ref into its target before doing anything else.
    if "$ref" in node:
        resolved = dict(_resolve_ref(node["$ref"], defs))
        # Carry over any sibling description (Pydantic usually strips these via
        # harden_schema, but be defensive).
        for k in ("description",):
            if k in node and k not in resolved:
                resolved[k] = node[k]
        return _gemini_node(resolved, defs)

    # 2. anyOf handling.
    if "anyOf" in node:
        variants = node["anyOf"]
        non_null = [
            v
            for v in variants
            if not (isinstance(v, dict) and v.get("type") == "null")
        ]
        has_null = len(non_null) != len(variants)

        if len(non_null) == 1:
            # Optional[X] -> X (+ nullable). Merge sibling annotations (e.g.
            # description) onto the single variant.
            inner = _gemini_node(non_null[0], defs)
            if isinstance(inner, dict):
                merged = dict(inner)
                for k, val in node.items():
                    if k in ("anyOf", "default"):
                        continue
                    if k in _GEMINI_ALLOWED_KEYS and k not in merged:
                        merged[k] = val
                if has_null:
                    merged["nullable"] = True
                return merged
            return inner

        # Genuine multi-variant union. Resolve each variant; if all are object
        # variants, flatten into a single object so every node carries a type.
        resolved_variants = [_gemini_node(v, defs) for v in non_null]
        if all(
            isinstance(v, dict) and v.get("type") == "object" for v in resolved_variants
        ):
            merged_props: dict[str, Any] = {}
            required_sets = []
            for v in resolved_variants:
                merged_props.update(v.get("properties", {}))
                required_sets.append(set(v.get("required", [])))
            common_required = (
                sorted(set.intersection(*required_sets)) if required_sets else []
            )
            flattened: dict[str, Any] = {
                "type": "object",
                "properties": merged_props,
                "additionalProperties": False,
                "required": common_required,
            }
            for k, val in node.items():
                if k in ("anyOf", "default"):
                    continue
                if k in _GEMINI_ALLOWED_KEYS and k not in flattened:
                    flattened[k] = val
            if has_null:
                flattened["nullable"] = True
            return _strip_unsupported(flattened)
        # Mixed/non-object union: keep anyOf but each variant is now typed.
        out = {"anyOf": resolved_variants}
        if has_null:
            out["nullable"] = True
        for k, val in node.items():
            if k in ("anyOf", "default"):
                continue
            if k in _GEMINI_ALLOWED_KEYS:
                out[k] = val
        return out

    # 3. Plain node: recurse into properties / items, then strip unsupported keys.
    out = dict(node)
    if "properties" in out and isinstance(out["properties"], dict):
        out["properties"] = {
            k: _gemini_node(v, defs) for k, v in out["properties"].items()
        }
    if "items" in out:
        out["items"] = _gemini_node(out["items"], defs)
    return _strip_unsupported(out)


def _infer_enum_type(node: dict[str, Any]) -> None:
    """Gemini requires a `type` on every node, including enum nodes. Pydantic
    sometimes emits an integer Literal as a bare `{"enum": [-1, 0, 1]}` (no
    type). Infer the type from the enum's value kinds in-place."""
    if "type" in node or "enum" not in node:
        return
    vals = node["enum"]
    if vals and all(isinstance(v, bool) for v in vals):
        node["type"] = "boolean"
    elif vals and all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
        node["type"] = "integer"
    elif vals and all(isinstance(v, (int, float)) for v in vals):
        node["type"] = "number"
    else:
        node["type"] = "string"


def _strip_unsupported(node: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in node.items() if k in _GEMINI_ALLOWED_KEYS}
    _infer_enum_type(out)
    # Gemini's responseSchema only validates `enum` on string types. A non-string
    # enum (e.g. Sentiment `{enum:[-1,0,1], type:integer}`) is rejected by the
    # OpenRouter->Google path, which misreports the error on the parent array
    # `items` node. Drop the constraint on non-string nodes — the Pydantic model
    # still enforces the allowed values when it re-parses the model output.
    if "enum" in out and out.get("type") != "string":
        out.pop("enum", None)
    return out


def _to_gemini_schema(response_format: dict[str, Any]) -> dict[str, Any]:
    """Rewrite a json_schema response_format into Gemini's OpenAPI subset.

    Input is the dict returned by `json_schema_for_response_format()` (the
    `{"type":"json_schema","json_schema":{...,"schema":{...}}}` envelope). The
    returned envelope has the same shape but with a Gemini-safe inner schema
    (all $refs inlined, every node typed, Optionals expressed via `nullable`).
    Only call this for `openrouter/google/gemini-*` extractor models.
    """
    inner = response_format["json_schema"]["schema"]
    defs = inner.get("$defs", {})
    safe = _gemini_node({k: v for k, v in inner.items() if k != "$defs"}, defs)
    out = {
        "type": response_format["type"],
        "json_schema": dict(response_format["json_schema"]),
    }
    out["json_schema"]["schema"] = safe
    return out
