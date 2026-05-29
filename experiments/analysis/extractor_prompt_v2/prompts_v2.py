"""v0+ ConversationState extraction prompt — v2 (literal-tag-extraction sharpened).

Motivation: 46% of R2 full-devset failures had a GT-tag word the user literally
said but the extractor failed to surface as a `positive_tags` entry — they got
buried inside `turn_intent` prose instead. See
`experiments/v0plus_textside_2026-05-28.md` and the cohort artifact at
`experiments/analysis/extractor_prompt_v2/artifacts/cohort_missed_literal_tags.jsonl`.

What changed vs v1:
- Dedicated "TAG EXTRACTION DISCIPLINE" section: every descriptive content word
  in the latest user turn that is sentiment-bearing becomes a discrete
  mentioned_entities[type=tag] entry. Sentences kept in turn_intent are NOT a
  substitute.
- Worked example showing the failure mode (descriptive words packed into
  turn_intent prose without being lifted into mentioned_entities).
- Decade phrasing ("late 90s / early 2000s / 80s") MUST become a release_date
  hard_filter and a tag (because users phrase era as a tag too).
- Lyric-snippet detection: when the user quotes lyrics, copy the snippet
  verbatim into turn_intent and add a sentiment-positive tag entry like
  "lyric:<snippet>" so downstream knows the goal is lyric-match.
- Anti-anchor parsing slightly sharper: "more like X but Y" → X is positive
  anchor, Y is positive tag, not just turn_intent flavor.

Drop-in compatibility: same `build_messages` / `json_schema_for_response_format`
public surface as the v1 prompt; the v0+ compiler imports `build_messages` —
swap the import path to A/B without code changes elsewhere.
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

SYSTEM = """You extract a structured ConversationState (v0+ schema) from a multi-turn music recommendation conversation.

Output ONE JSON object that validates against the provided schema. No prose, no explanation, no markdown fences. Just JSON.

# Conversation rendering format

The user prompt has two parts:

1. `played_track_ids`: an ordered list of track_id values. Item 1 in this list is the FIRST track played, item 2 is the second, etc. These are the same UUIDs you must echo back in the `track_feedback.track_id` and `referenced_track_ids` fields when you reference them.
2. `conversation`: the turns. Music turns are rendered as `[turn N] music: #M (Artist - Track)`. The `#M` is a 1-indexed pointer into `played_track_ids` — `#1` means `played_track_ids[0]`, `#2` means `played_track_ids[1]`, and so on.

# Field rules

## turn_intent  (string)
The user's active ask in 1–2 sentences. MUST verbatim include every artist / track / album / tag name the user named in the LATEST user turn. Do not paraphrase named entities away. Do not invent entities the user didn't say.

`turn_intent` is the user's request in their own words. It is NOT a substitute for `mentioned_entities`. Anything sentiment-bearing that goes here MUST also be split out into `mentioned_entities` (see TAG EXTRACTION DISCIPLINE below).

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

# ENTITY EXTRACTION DISCIPLINE — DO THIS FIRST, BEFORE TAGS

Before extracting tags, scan the LATEST user turn for every proper noun that is an artist / band / track / album name and emit one `mentioned_entities` entry per name. Artist names embedded inside conversational sentences are the #1 failure mode — don't drop them just because the user is also describing what they want around the name.

For each named entity, set sentiment based on the surrounding clause:

| user phrasing pattern | sentiment | example |
|---|---:|---|
| "I love/like X", "X is great/awesome", "more X songs", "anything by X" | **1** | "Can you recommend more Eminem songs" → `{type=artist, value="Eminem", sent=1}` |
| "X is cool/decent/fine but [different ask]" | **0** | "Megadeth is cool but I've heard a lot of their tracks" → `{type=artist, value="Megadeth", sent=0}` |
| "Not X", "no more X", "different from X", "stop playing X" | **-1** | "Not Fugazi" → `{type=artist, value="Fugazi", sent=-1}` + add to `explicit_rejections` |
| "X is a classic / iconic / legendary" used as a REACTION to a played track | **1** to the played track, but DO NOT also emit X as a separate entity unless X is the artist/track the played item already references. The user is reacting, not requesting. |
| Bare name reference for similarity ("like X", "in the style of X", "X-influenced", "Beatles-esque") | **1** | "in the style of Pink Floyd" → `{type=artist, value="Pink Floyd", sent=1}` |

Coverage rule: if the user wrote a name that is plausibly a real artist / band / track / album (proper-noun shape — capitalized words, or a quoted phrase), it MUST appear in `mentioned_entities`. Missing a named entity costs the retriever its highest-signal anchor.

## FORBIDDEN OMISSION EXAMPLES — these are real failures from our previous run

> User: "Megadeth is cool, good stuff, but I've heard a lot of their tracks. Can you hit me with something with that classic heavy metal sound..."
>
> WRONG (omits the artist): `mentioned_entities: [{type:tag, value:"heavy metal", sent:1}, ...]`
> RIGHT: `mentioned_entities: [{type:artist, value:"Megadeth", sent:0}, {type:tag, value:"heavy metal", sent:1}, ...]`

> User: "Oh, this is wonderful! Ennio Morricone is truly a master, and 'Marcia - Marcetta' is exactly the kind of iconic, grand cinematic piece I was hoping for."
>
> WRONG: tags only, no artist entry
> RIGHT: `mentioned_entities` MUST include `{type:artist, value:"Ennio Morricone", sent:1}` and `{type:track, value:"Marcia - Marcetta", sent:1}` alongside the descriptor tags.

> User: "Can you recommend more Eminem songs that have a bit of a darker or more serious tone, like 'Stan'?"
>
> WRONG: `[{type:tag, value:"darker", sent:1}, {type:tag, value:"serious", sent:1}]`
> RIGHT: `[{type:artist, value:"Eminem", sent:1}, {type:track, value:"Stan", sent:1}, {type:tag, value:"darker", sent:1}, {type:tag, value:"serious", sent:1}]`

> User: "Oh, cool! Destiny's Child is awesome too! 'Happy Face' is a pretty good song. Can you play something else super upbeat and fun from the 2000s pop era?"
>
> WRONG: drops both artist and track
> RIGHT: `[{type:artist, value:"Destiny's Child", sent:1}, {type:track, value:"Happy Face", sent:1}, {type:tag, value:"upbeat", sent:1}, {type:tag, value:"fun", sent:1}, {type:tag, value:"2000s", sent:1}, {type:tag, value:"pop", sent:1}]`

# TAG EXTRACTION DISCIPLINE — read carefully, this is the most error-prone field

The downstream retriever indexes on `mentioned_entities[type=tag, sentiment=1]`. If a descriptive word the user said never makes it into this list, the retriever cannot use it — `turn_intent` prose is invisible to the retriever.

## TWO HARD RULES — VIOLATING EITHER CAUSES RETRIEVAL FAILURES

**Rule 1 — VERBATIM-ONLY.** Every tag value MUST be a literal substring (case-insensitive) of words the user actually typed somewhere in the conversation. Single tokens (`"rock"`, `"chill"`, `"80s"`) OR multi-word phrases the user actually wrote (`"alternative rock"`, `"late 90s"`). The only allowed normalizations are lowercasing and trimming punctuation. NO synonyms, NO catalog jargon the user didn't use, NO inferred descriptors, NO genres you think apply, NO platform names, NO style adjectives the user didn't say. If the user did not literally type the characters of the word, the word is FORBIDDEN as a tag.

  *Examples of FORBIDDEN hallucinations (do NOT emit these unless the user literally typed them):*
  `TikTok`, `Spotify`, `anthemic`, `melodic`, `Christian` (when user wrote "christian" — lowercase is fine but DO NOT add invented values), `headbang-inducing`, `crushing`, `personal faith message`, `relying on faith`, `feel-good`, `groovy`, `iconic`, `nostalgic`, `summer vibes` — UNLESS the user typed that exact phrase.

  When in doubt, omit. A missing-but-true tag is recoverable downstream. A hallucinated tag pollutes ranking and is not recoverable.

**Rule 2 — COMPLETE COVERAGE OF LITERAL DESCRIPTORS.** Every sentiment-bearing content word/phrase in the LATEST user turn that the user used to describe the music they want becomes its own `mentioned_entities[type=tag]` entry. Don't bury descriptive words in `turn_intent` prose without also lifting them into tag entries. One tag entry per descriptive concept the user actually wrote.

The categories below are a CHECKLIST for what to lift WHEN the user actually wrote one of those words. The lists are NOT a vocabulary to draw from — they are a reminder of word classes that often get missed. Only emit a category word if the user wrote it.

| category | examples of words to extract |
|---|---|
| **Genre** | rock, pop, jazz, hip-hop, hip hop, hardcore, post-hardcore, grunge, electronic, country, classical, R&B, indie, metal, punk, folk, ambient, lo-fi, trap, house, techno, soul, funk, blues, EDM, reggae, dance, world music |
| **Subgenre / scene** | alternative rock, melodic hardcore, dream pop, math rock, dubstep, drill, shoegaze, post-punk, indie folk, vaporwave |
| **Mood / vibe** | chill, mellow, upbeat, melancholy, melancholic, sad, happy, energetic, aggressive, dark, bright, dreamy, romantic, angry, hopeful, nostalgic, atmospheric, intimate, intense, raw, smooth, hard, soft, heavy, light, gritty |
| **Sonic / production** | acoustic, electric, instrumental, distorted, lo-fi, hi-fi, fuzzy, clean, layered, minimal, dense, sparse, polished, raw, loud, quiet, fast, slow, mid-tempo |
| **Era** | 60s, 70s, 80s, 90s, 2000s, early 2000s, late 90s, modern, vintage, contemporary, classic, recent — ALSO emit a `release_date` hard_filter (see hard_filters) |
| **Setting / function** | study, workout, party, driving, sleep, focus, background, late-night, road-trip |
| **Other descriptors** | popular, mainstream, underground, deep cuts, hits, obscure, iconic, legendary, reflective, storytelling, lyrical, danceable, headphone, anthemic, cinematic |
| **Lyric snippets** | when the user quotes 3+ consecutive words in quotes or says "the one that goes ...", emit a `lyric:<snippet>` tag (e.g. `lyric:do you have the time`) |

DO NOT extract tags for: filler/connective words ("song", "track", "music", "artist", "thing", "song(s)", "track(s)"), pronouns, conversational verbs ("play", "give", "want", "love", "like", "thanks"), grading words ("great", "awesome", "perfect", "good", "amazing" — the user is reacting, not describing), words inside a negative clause unless they're the rejected concept itself, or any word that is not literally present in the conversation text.

Examples — what the extractor MUST do (every tag below comes from a word the user literally wrote):

> User: "Something popular alternative rock with a reflective or atmospheric quality, similar to Red Hot Chili Peppers, from the late 90s or early 2000s."
>
> mentioned_entities MUST include AT LEAST:
> - {type:artist, value:"Red Hot Chili Peppers", sentiment:1}
> - {type:tag, value:"popular", sentiment:1}
> - {type:tag, value:"alternative rock", sentiment:1}
> - {type:tag, value:"reflective", sentiment:1}
> - {type:tag, value:"atmospheric", sentiment:1}
> - {type:tag, value:"late 90s", sentiment:1}
> - {type:tag, value:"early 2000s", sentiment:1}
>
> hard_filters MUST include:
> - {field:"release_date", op:"between", start:"1995-01-01", end:"2005-12-31"}

> User: "80s American hardcore punk bands known for their raw energy and short, intense songs."
>
> tags: 80s, American, hardcore punk, hardcore, raw, raw energy, intense, short
> hard_filters: {field:"release_date", op:"between", start:"1980-01-01", end:"1989-12-31"}

> User: "Play the song with the lyrics 'Do you have the time to listen to me whine'"
>
> tags: {type:tag, value:"lyric:do you have the time to listen to me whine", sentiment:1}

Splitting vs not splitting multi-word phrases: when the user wrote a phrase that is itself a recognized genre/scene/style ("hardcore punk", "post-hardcore", "lo-fi"), emit it as a single tag entry. When the user wrote two independent descriptors next to each other ("dark and dreamy"), emit each as its own tag. When in doubt and BOTH appear as literal substrings of the user's text: emit BOTH the phrase AND each meaningful word. Still — never emit a phrase or token the user did not write.

## FORBIDDEN HALLUCINATION EXAMPLE — what to AVOID

> User: "Yes! This is brilliant! Love the smooth flow and uplifting feel. What else can you recommend that's in this same great vein of liquid D&B?"
>
> CORRECT mentioned_entities tags (every word literally in the user text):
>   smooth, uplifting, liquid D&B (multi-word phrase user wrote), liquid, D&B
>
> FORBIDDEN tags (the user did not write these — do NOT emit):
>   melodic, ambient, drum-and-bass (expansion of "D&B" — the user didn't write the expansion), feel-good (the user wrote "feel", not "feel-good"), summer, hospital-records (catalog jargon), great (reaction word — not a music descriptor).

## explicit_rejections  (list)
FUTURE exclusions. Populate when the user says "not X", "no more X", "different from X", "too heavy", "too gloomy", "stop playing X". Stricter than `mentioned_entities[sentiment=-1]` — the compiler will hard-exclude these.

| kind | excludes |
|---|---|
| `artist` | all tracks by that artist |
| `track` | that specific track_id |
| `tag` | soft-demotes tracks whose tag_list overlaps |

When the user says "more like X but Y" / "X is great but I want more Y", X is the POSITIVE anchor (`mentioned_entities[type=artist, sentiment=1]`) and Y is a POSITIVE tag, NOT a rejection of X.

## hard_filters  (list)
v0+ supports `release_date` only. Emit dates as YYYY-MM-DD into typed `start` / `end`.

| user phrasing | filter |
|---|---|
| "Songs from the 90s" | `{op:"between", start:"1990-01-01", end:"1999-12-31"}` |
| "80s" | `{op:"between", start:"1980-01-01", end:"1989-12-31"}` |
| "Late 90s" | `{op:"between", start:"1995-01-01", end:"1999-12-31"}` |
| "Early 2000s" | `{op:"between", start:"2000-01-01", end:"2005-12-31"}` |
| "Late 90s or early 2000s" | `{op:"between", start:"1995-01-01", end:"2005-12-31"}` |
| "Nothing newer than 2010" | `{op:"<", end:"2010-01-01"}` |
| "After 2020" | `{op:">", start:"2020-01-01"}` |

`start` is inclusive for `between`, strict for `>`. `end` is inclusive for `between`, strict for `<`.

Whenever you emit a release_date hard_filter, ALSO emit the era word(s) as positive tags (users phrase era as a tag and the catalog uses era tags too).

# General

Sentiment is always one of `-1`, `0`, `1`. Never a decimal.
"""


# v2 few-shot examples — kept tight; first three preserved from v1 for behavior
# continuity, then two new examples target the missed-literal-tags failure mode.
FEW_SHOT_EXAMPLES: list[dict[str, Any]] = [
    # Example 1: refinement with a positive anchor and a tag rejection.
    {
        "user_prompt": {
            "played_track_ids": [
                "a1111111-1111-4111-8111-111111111111",
                "b2222222-2222-4222-8222-222222222222",
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
                {"type": "tag", "value": "smoky", "sentiment": 1},
                {"type": "tag", "value": "slow", "sentiment": 1},
                {"type": "tag", "value": "late-night", "sentiment": 1},
                {"type": "tag", "value": "bar music", "sentiment": 1},
                {"type": "tag", "value": "lighter", "sentiment": 1},
                {"type": "tag", "value": "heavy", "sentiment": -1},
            ],
            "hard_filters": [],
            "explicit_rejections": [
                {"kind": "tag", "value": "heavy", "source_turn": 3}
            ],
        },
    },
    # Example 2: pivot with release_date filter — era tag MUST also appear in mentioned_entities.
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
    # Example 3: explicit artist rejection (Fugazi pattern).
    {
        "user_prompt": {
            "played_track_ids": [
                "d4444444-4444-4444-8444-444444444444",
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
            "hard_filters": [
                {"field": "release_date", "op": "between", "start": "1980-01-01", "end": "1989-12-31"}
            ],
            "explicit_rejections": [
                {"kind": "artist", "value": "Fugazi", "source_turn": 2}
            ],
        },
    },
    # Example 4 (NEW): the Sun King failure — long descriptive sentence MUST decompose
    # into per-word tags AND a release_date filter.
    {
        "user_prompt": {
            "played_track_ids": [
                "e5555555-5555-4555-8555-555555555555",
            ],
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
                {"type": "tag", "value": "alternative", "sentiment": 1},
                {"type": "tag", "value": "rock", "sentiment": 1},
                {"type": "tag", "value": "reflective", "sentiment": 1},
                {"type": "tag", "value": "atmospheric", "sentiment": 1},
                {"type": "tag", "value": "late 90s", "sentiment": 1},
                {"type": "tag", "value": "early 2000s", "sentiment": 1},
            ],
            "hard_filters": [
                {"field": "release_date", "op": "between", "start": "1995-01-01", "end": "2005-12-31"}
            ],
            "explicit_rejections": [],
        },
    },
    # Example 5 (NEW): lyric-snippet detection.
    {
        "user_prompt": {
            "played_track_ids": [],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Play the song with the exact lyrics 'Do you have the time to listen to me whine'."},
            ],
        },
        "output": {
            "turn_intent": "Play the song with the lyrics 'Do you have the time to listen to me whine'.",
            "intent_mode": "open_explore",
            "track_feedback": [],
            "referenced_track_ids": [],
            "mentioned_entities": [
                {"type": "tag", "value": "lyric:do you have the time to listen to me whine", "sentiment": 1},
            ],
            "hard_filters": [],
            "explicit_rejections": [],
        },
    },
]


def build_messages(conversation: list[dict[str, Any]], played_track_ids: list[str]) -> list[dict[str, str]]:
    """Build the chat-completions messages list with v2 few-shot examples."""
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


def _strip_comments(node: Any) -> Any:
    """Anthropic's strict-mode rejects $comment (and other non-schema annotations).
    OpenAI tolerates them. Strip them recursively before sending."""
    if isinstance(node, dict):
        for k in ("$comment", "examples", "title", "description"):
            node.pop(k, None) if k == "$comment" else None
        for v in node.values():
            _strip_comments(v)
    elif isinstance(node, list):
        for v in node:
            _strip_comments(v)
    return node


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
