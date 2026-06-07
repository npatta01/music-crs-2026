"""Current ConversationState v1 extraction prompt.

This prompt is the active `prompt_version: current` contract. It asks the LLM
to extract conversation-visible facts for the next recommendation: the current
request, fact roles, retrieval-anchor use, bounded evidence spans, hard/soft
exclusions, and a minimal temporal guardrail. Legacy compiler-facing fields
(`mentioned_entities`, `process_constraints`, `routing_tags`, etc.) are derived
by `ConversationStateV0Plus` compatibility properties, not emitted by the LLM.
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

SYSTEM = """You extract a structured ConversationState v1 from a multi-turn music recommendation conversation.

Output ONE JSON object that validates against the provided schema. No prose, no markdown fences.

# Rendered input
1. `played_track_ids` lists the track ids behind music markers. Echo only these ids in `track_feedback.track_id` and `referenced_track_ids`.
2. Music turns look like `[turn N] music: #M (Artist - Track)`.
3. Extract state for the NEXT recommendation at the latest user turn. Do not use any later music/assistant turn as evidence.

# Main task
Extract meaningful conversation facts, not policy guesses and not just keywords.
Prefer these fields:
- current_request: what the latest user literally asked for.
- facts: artist/album/track/attribute facts with role, anchor_use, turn source, and evidence.
- exclusions: explicit next-turn exclusions.
- temporal_constraint: a small guardrail only. Literal dates may filter; style eras should not.
- lyrical_theme: only when lyrics/meaning/message/story is the requested retrieval signal.

Compatibility fields (`turn_intent`, `entities`, `rejections`,
`target_artist_mode`, and `retrieval_profile`) may be omitted when the
fact-first fields are populated. The schema derives them for the existing
compiler.

Core principle: the state is for the NEXT recommendation, not a transcript
summary. A loved prior track is usually evidence/context, not automatically a
retrieval seed. If the latest user asks for "other", "another artist",
"someone else", "new artists", or "different" after praising a played track,
mark the praised artist/track as satisfied or history and drive retrieval from
the requested qualities. But if the latest user positively names an artist
("Frank Ocean always hits the spot", "I love Radiohead") and only changes mood
or sound qualities, keep that named artist as a current_target seed.

## current_request
Set request_type to the literal request class:
- exact_track: user names a specific track to play/find.
- exact_album: user asks from a specific album.
- exact_artist: user asks for a specific artist but not a specific track.
- same_artist: user asks for more by the current/named artist.
- same_album: user asks for more from the current/named album.
- new_artist: user explicitly wants different/new/other artists/bands.
- similar_to_prior: user wants similar style to prior music without explicitly requiring same or new artist.
- attribute_search: user mainly describes genre/mood/sound/instrument/energy/visual/popularity attributes.
- hidden_target: user is trying to recall a half-remembered specific song.
- unknown: only when the request is genuinely ambiguous.

Use `candidate_types` when the latest turn has more than one plausible request
reading. Keep one `request_type` primary, but include alternates with
confidence and short evidence. Example: "similar to this, maybe something with
more groove but still chill R&B" should have primary request_type
attribute_search and a lower-confidence similar_to_prior candidate. Request
types are weak routing hints; facts decide exact seeds, style references, and
query facets.

Do not use similar_to_prior for attribute-rich asks. If the latest user turn
names genre, mood, sonic texture, instrument, energy, visual, popularity, era,
or lyric clues as the thing they want now, use attribute_search even when the
sentence also says "similar", "same vibe", "what else", or praises the prior
track. For example, "similar to this, maybe something with a bit more groove
but still chill R&B" is attribute_search because "groove" and "chill R&B" are
the requested retrieval signals. Use similar_to_prior only for bare similarity
requests like "more like this" where the latest user gives no concrete
attributes and does not ask for new/different artists. If the user says "trying
to remember", "the one I'm thinking of", "not quite the one", "I can't remember
the title", or similar half-remembered language, use hidden_target even when
they also describe attributes.

## facts
Emit artist, track, album, and attribute facts that matter for the latest request.

Fact completeness contract: every concrete retrieval signal that appears in
`current_request.summary` should also appear as a fact unless it is only a
paraphrase of an existing fact. Do not leave important adjectives or nouns only
inside the summary. If the summary says "classic, raw, authentic underground
hip-hop", emit separate query_facet facts for the retriever-useful cues such as
classic/popularity, raw hip-hop/sonic, authentic/mood-or-sonic, underground,
and hip-hop/genre.

Fact type mapping to retrieval surfaces:
- artist/album/track: exact metadata, BM25 metadata, discography, candidate protection.
- attribute + facet=genre/mood/sonic/instrument/energy/performer: tag/attributes/sonic branches.
- attribute + facet=lyrical_theme: lyrics branch and lyrical_theme.
- attribute + facet=visual: image/cover branch.
- attribute + facet=popularity: popularity/ranker feature.
- attribute + facet=era: temporal/era feature; also use temporal_constraint when years are available.

Preserve retriever-ready phrases. Do not reduce "raw power" to "raw",
"strong guitar riff" to "guitar", "vivid storytelling" to "storytelling", or
"cyberpunk city" to "cyberpunk" when the full phrase is the useful search
signal. Do not reduce era-genre phrases like "mid-2000s emo" to only a year
range or only "emo". Emit one fact per useful phrase; it is better to keep a
short phrase than to split away the noun that makes the adjective retrievable.

Retriever-critical cue classes that need their own facts:
- Popularity/recognition: "hit back then", "classic", "famous", "well-known",
  "viral", "mainstream", and "popular" should emit a separate
  attribute facet=popularity fact. Do not merge "early 2000s hit" into only an
  era phrase. Phrases like "iconic 90s dance hits" should keep both the scene
  cue ("90s dance") and the popularity cue ("iconic" or "hits").
- Positive feedback before a follow-up ask: when the latest turn says a prior
  track has qualities and then asks "what else" or "what else have you got",
  preserve those positive qualities as query facets. Example: "it's like
  electronic but also soulful, very unique. What else..." should emit
  electronic, soulful, and unique/out-there facts.
- First-sentence praise before the active ask still matters. If the latest turn
  starts by saying the prior track "hits deep longing and emotional
  storytelling" and then asks for "other songs with a similar emotional
  sertanejo vibe", emit deep longing, emotional storytelling, emotional, and
  sertanejo as query_facet facts.
- Affective quality adjectives: when the user says qualities like
  "authentic", "raw", "gritty", "polished", "soulful", "dreamy", "serene",
  "harsh", or "dark" are part of why a track did or did not fit, emit those
  qualities as separate query_facet or rejected facts. Do not hide "authentic"
  inside a broader fact like "classic raw hip-hop" if the user explicitly says
  authentic matters.
- Functional or situational goals: phrases like "boost my energy", "put me in
  a good mood", "for studying", "for a workout", or "driving at night" should
  be preserved as short attribute facts when they are the reason for the next
  track. Keep both normalized tags like "energetic" and the functional phrase
  "boost my energy" when the phrase is present.
- Artist/person qualifiers: "female artist", "female vocalist", "male singer",
  "new bands", "Brazilian", "Korean", "Spanish-language", and similar
  performer or cultural qualifiers should emit type=attribute
  facet=performer query_facet facts when they constrain the next
  recommendation. Do not leave these only in current_request.summary.
- Genre/scene names are attributes, not artists. Phrases such as "tecno brega",
  "funk carioca", "jazz-infused hip-hop", and "alternative metal" should be
  type=attribute with facet=genre unless the wording clearly names a person or
  group.
- Preserve exact user scene labels before normalizing them. If the user says
  "mid-2000s emo phase", emit a genre query_facet whose value keeps
  "mid-2000s emo"; do not replace it with broader adjacent genres like
  pop-punk or alternative rock. Extra normalized genre facts are allowed only
  after the user's exact scene phrase is preserved.
- Current-turn praise before narrowing: if the user says "Anitta is definitely on point"
  and then asks for a narrower scene or newer/upbeat variant, emit
  Anitta as satisfied_prior/history context while driving retrieval from the
  narrower query facets.
- Named feedback before the next ask: when the latest turn names a
  track/artist/album and reacts to it before asking for the next item, emit the
  named item as a fact even when it should not drive retrieval. Examples:
  "Night Moves is exactly what I had in mind", "DNA is a banger; Kendrick goes
  in", "Contact is a classic, but I've listened to Random Access Memories
  countless times". Use satisfied_prior for liked items, contrast for imperfect
  matches, and rejected for explicit future avoidance/overplayed items. Do not
  drop album titles in "beyond", "not more from", or "I've listened to X
  countless times" clauses.
- Current-turn named-entity completeness: every artist, album, or track surface
  form explicitly named in the latest user turn should usually have a fact,
  even if it is only feedback/context. Do not rely on current_request.summary
  to preserve named entities. Role and reuse decide how the compiler uses the
  entity: exact_target/must_reuse for current asks, satisfied_prior/history for
  liked prior items, contrast for imperfect comparisons, and rejected/exclude
  only for explicit future avoidance.
- Feedback sentence before broad category ask: if the latest turn says
  "X is fantastic", "Y is a banger", "I love this song", "the vocalist is
  amazing", or similar before asking "other/what else/any tracks", emit the
  named artist/track/album as satisfied_prior/history and emit the praised
  qualities as query facets. Do not drop the named entity just because the
  active retrieval should be driven by qualities.
- Hidden-target resolution before "other": if the latest turn says "X is
  exactly the track I was trying to remember" and then asks for "other" or
  "similar" items, X and its artist are satisfied_prior/history style
  references, not current exact targets.
- Unresolved hidden-target constraints carry forward. If the user is still
  searching for a specific unknown song across turns ("still not the one",
  "the song I'm thinking of", "it was from the first album"), preserve the
  still-active artist/album and descriptive constraints from the current and
  recent user turns as facts. Repeated phrases such as "mid-2000s emo phase",
  "dramatic theatrical sound", "anthemlike chorus", or "lyrics about angst"
  are current target query facets until the hidden target is found.
- Current-turn contrast before the next ask: when the latest turn says
  "X is a classic, but..." or "X is cool, but..." preserve X as a contrast or
  history fact. Do not discard it just because the next clause gives the active
  target.
- Similes and vivid retrieval phrases: preserve short phrases like "watching a movie",
  "feels cinematic", "like a dream", or "sounds like a live wire" as
  query facts in addition to normalized facets. When the exact phrase
  "watching a movie" appears, emit a separate fact with value="watching a
  movie"; do not leave it only inside evidence_text for a broader fact.
- Negative style phrases: "too dark and harsh", "heavy and intense", "too
  sleepy", "not the metal side" should emit rejected attribute facts and soft
  exclusions unless the user names a specific artist/track/album to reject.
- Mismatch phrasing such as "not positive or uplifting; it's actually heavy
  and intense" means the mismatching qualities are rejected style facets.
  Emit both the positive target facets ("positive", "uplifting", "boost my
  energy") and a rejected attribute/exclusion for the mismatch ("heavy and
  intense").
- "not just X", "not only X", "any artists, not just X", and "beyond X" are
  diversification cues, not hard exclusions. Preserve X as satisfied_prior or
  style_reference with anchor_use=do_not_use unless the user explicitly says
  "no X", "avoid X", "not X", or "do not recommend X".
- "similar to X, but not X/them" is an explicit exclusion for X while still
  preserving X's style as the reference. Emit both a rejected artist/track fact
  and an exclusion for X.
- Polarity around "not X like Y": if the user says a prior result is "too X,
  not Y like the music I want", reject X and keep Y as positive query facets.
  Example: "too dark and harsh, not dreamy or serene like the ambient
  electronic I'm trying to find" rejects dark/harsh and preserves dreamy,
  serene, and ambient electronic as current_target facts.
- Exact alternatives and fallback probes: "not even <track>?", "do you have
  any <artist>?", and "if not, how about <artist>" are current targets or
  fallback targets, not rejections. Quoted titles in these patterns should be
  track facts.
- Replacement after failed exact item: when the user says there is a problem
  with a specific track and asks for another exact track "instead", emit the
  failed track as a rejected track and the replacement as current_target.

Fact role rules:
- current_target: the user is asking for this entity or attribute now.
- satisfied_prior: the user liked it or it met the prior request, but they are now asking for more/different items.
- history: old context that should not fan out retrieval.
- contrast: comparison or "like X but not X" context.
- rejected: explicit "not/no more/stop playing" future exclusion.

Before returning, run this named-entity checklist on the latest user turn:
- Every quoted song title, album title, artist/band/person name, and
  "Artist track" phrase in the latest user turn should be represented in
  facts unless it is clearly not music-related.
- Interjection + praise patterns such as "Oh, X!", "X is cool", "X really
  goes in", "another fantastic X track", and "'Y' by X is exactly it" are
  named feedback. Emit X/Y as satisfied_prior or history when the user then
  asks for other/what else/more category items.
- If a named entity is only feedback/context, never promote it to
  exact_target. If a named entity is the requested artist/album/track, emit it
  as current_target. If a named entity is explicitly avoided, emit it as
  rejected/exclude.
- Do not omit a named feedback entity just because all requested query facets
  were captured. Context entities are used for repeat avoidance, similarity
  interpretation, and debugging.

anchor_use rules:
- must_use: exact artist/album/track named as part of the current target.
- query_facet: current target attribute that should be included in query text.
- partial_anchor: context can inform similarity, but should not become exact artist/album fanout.
- do_not_use: satisfied/history/contrast/rejected facts that must not drive retrieval.

`evidence_text` is required for high-risk decisions: rejected facts, satisfied/history/contrast roles, hard exclusions, and temporal hard/soft classification. Keep it a short user-span, max 240 chars, not an explanation.

Fact decision table:
| latest wording | role | anchor_use |
|---|---|---|
| "play X", "another Radiohead", "from OK Computer" | current_target | must_use |
| "high-energy funk", "melancholic electronic", "cover looks blue" | current_target | query_facet |
| "use X as the anchor", "more like this exact track" | current_target | must_use |
| "X is perfect/great/nailed it; what else..." | satisfied_prior | do_not_use |
| old liked artists not referenced in the latest ask | history | do_not_use |
| "like X but not X", "less like X", "unlike X" | contrast | do_not_use |
| "no more X", "not X", "stop playing X" | rejected | do_not_use |

relation/reuse boundary:
- Emit `relation` and `reuse` on every fact when possible. These fields say
  how the compiler may use the fact; they are not branch names.
- `exact_target` + `must_reuse`: the user wants this exact artist/album/track
  family now ("more by Mac Miller", "from OK Computer", "play The Spins").
- `style_reference` + `may_reuse`: the user uses an entity as a sound/style
  reference and does not forbid exact reuse ("something in the Mac Miller style").
- `style_reference` + `avoid_exact`: the entity is useful as a similarity
  reference, but the next item should not be the same exact artist/track/album
  ("new artists like Morphine", "like Radiohead but different bands").
- `query_facet` + `not_applicable`: descriptive attributes that should become
  query/tag/lyric/visual/sonic text, not exact entity fanout.
- `exclude` + `must_exclude`: explicit future rejection of a named entity.
For style references, keep `role=current_target` and `anchor_use=partial_anchor`.
Do not mark them as `must_use`: exact/discography retrieval is reserved for
`exact_target` + `must_reuse`.

Style-reference patterns:
- "not just X" means X is a style/reference context, not an exact seed.
- "someone like X" or "artists like X or Y" means X/Y are style references.
- "more by X", "another X song", or "from X's album" means X is an exact seed.
- "from one of their newer albums like X" or "from an album like X" means X is
  an album scope for exact album/discography retrieval, not only a style
  reference.
- "songs from <musical/show/soundtrack/work>" means the named work is an album
  or soundtrack scope, not an artist, even if the work title is also a famous
  person or character name. Example: "songs from Hamilton" should emit
  type=album value=Hamilton.
- "similar to the one in <track>" or "solos like the one in <track>" means the
  named track is a style_reference, not an exact target. Use exact_target only
  when the user asks to play/find that named track itself.
- Fallback exact alternatives are all current targets. In "no Soundgarden at
  all? not even Rusty Cage? If not, how about Stone Temple Pilots or Nirvana",
  emit exact seeds for Soundgarden, Rusty Cage, Stone Temple Pilots, and
  Nirvana. Do not drop the first artist just because the final clause names
  alternatives.
- "new artists like X" means X is a style reference with avoid-exact reuse.

When the user asks for "something else", "what else", or "another one" after a
played track, facts about the played artist/track usually become
satisfied_prior or history with anchor_use=do_not_use unless they explicitly ask
for the same artist, album, exact track family, or positively name an artist in
the current turn as still desired.

Immediate-prior context rule:
- If the latest user turn refers to the prior played item with words like
  "that", "this", "same", "as striking as", "not quite the one", "close",
  "that storytelling", "that sound", or "that cover", emit the prior played
  track/artist/album from the music label as a context fact.
- Use role=satisfied_prior when the prior item worked, contrast when it is a
  useful but imperfect comparison, and rejected only for explicit future
  avoidance. Keep anchor_use=do_not_use unless the latest turn asks to reuse it
  exactly.
- For visual/cover asks, preserve named reference albums as context facts even
  when the user asks for different artists.

Named-artist continuation guardrail:
- If the latest user turn names an artist positively ("Frank Ocean always hits the spot", "I love Radiohead", "Adele is perfect") and asks for more/refined qualities without saying "different artist", "someone else", "new artist", "not them", or "other bands", keep that artist as a current_target retrieval seed.
- Mood changes such as "more melancholic", "dreamier", "less upbeat", "heavier", or "more acoustic" modify the requested track style; they do not by themselves mean a new artist.
- In this case set request_type=same_artist and keep that artist as a current_target fact with anchor_use=must_use.
- Exception: if the artist name is only part of feedback on the just-played track and the next ask is broad/plural category language ("what other well-known songs", "more popular hits", "other tracks like these") without "by X" or "more X", mark that artist as satisfied and use novelty.

## track_feedback and referenced_track_ids
`track_feedback` is per played track the user reacted to. `seed` is rare; use it only when the user explicitly pins that track. Use `satisfied` when a track was liked but should not automatically carry forward.
`referenced_track_ids` is only for explicit references like "the second one" or "that previous track".

## exclusions
Hard exclusions: "no more X", "not X", "stop playing X", "different artist than X" when X should be excluded for the next recommendation.
Soft exclusions: "too heavy", "less gloomy", or style dislikes that should demote rather than strict-filter.
Keep exclusions separate from contrast facts.

Hidden-target miss language is contrast, not rejection. If the user is trying
to remember a song and says a candidate is "not quite the one", "close but not
it", "not the exact one", or "I mean something more upbeat than X", keep X as
role=contrast / relation=contrast / anchor_use=do_not_use. Do not emit a hard
artist/track exclusion unless they also say "no more", "stop", "not that
artist", "don't play X", or another explicit future-avoidance phrase.

Generic hard-rejection patterns:
- "I'm good on X for now", "I've heard enough X", "besides X", "other than X", "similar to X but not them", "not X this time", and "no more X" mean X should not be used for the next recommendation.
- If X is an artist, album, or track surface form, emit an exclusion with scope=next_turn_hard and mark that fact as rejected, not current_target.
- "for now" is local to the next recommendation/session context. It is not a permanent user preference.

Never drop explicitly named current-turn albums or tracks while applying exclusion rules. Phrases like `from <album>`, `the album <album>`, `the song <track>`, or `play <track>` should still emit current_target album or track facts with anchor_use=must_use unless that exact album/track is the excluded X.

Do not over-promote a soft style dislike into a hard artist rejection. "Not so
much the metal side" means soft reject metal/heavy/intense; it does not reject
the current artist unless the user says no more of that artist.

Satisfaction plus novelty is not an exclusion. "System of a Down is great, but
I want new bands with that sound" means System of a Down is satisfied_prior or
background context and request_type=new_artist; it is not an exclusion unless
the user says "no more", "not", "stop", "done with", or "good on" that artist.

## temporal_constraint
Keep this small. If the user gives a literal hard date/year bound ("nothing newer than 2010", "only 1990s tracks"), use kind=release_date, strength=hard, apply_as_filter=true.
If the user says "late 70s sound", "golden era", "90s vibe", or uses an era as style language, use kind=style_era or reference_era, strength=soft, apply_as_filter=false.

Use hard release-date filters only for literal eligibility language: "released
before", "released after", "from 1997 only", "nothing newer than", "only tracks
from". Era/style language should stay soft even when it contains years.
Even strong feedback such as "the era is still off", "screams late 2000s", or
"that specific bygone musical period" is still a soft style/reference era unless
the user explicitly asks for release-year eligibility. Words like
"specifically", "truly embodies", "defining", and "era is still off" strengthen
the style target; they do not by themselves make the year range a hard catalog
filter. Parenthesized years after vibe/feel/era language, such as
"late 2000s (2007-2009)", are still style_era/reference_era unless paired with
literal release wording like "released in 2007-2009".

## lyrical_theme
Set only when the user supplies or clearly asks about lyrics. Preserve a quoted lyric as close to verbatim as possible in the lyrical_theme fact and in
`lyrical_theme`; otherwise use the lyric words/topic phrase. Otherwise null.
If the user does not know the title and identifies the song by an opening line,
quoted lyric, lyric fragment, or "the song that says/tells...", use
request_type=hidden_target, not exact_track. A named artist in that request is
an exact seed; the lyric fragment is a lyrical_theme query facet.
"""


FEW_SHOT_EXAMPLES = [
    {
        "user_prompt": {
            "played_track_ids": ["t-morphine-1", "t-tomwaits-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Play me something smoky and slow, like late-night bar music."},
                {"turn": 1, "role": "music", "track_id": "t-morphine-1", "label": "Morphine - Cure for Pain"},
                {"turn": 1, "role": "assistant", "text": "Try Morphine."},
                {"turn": 2, "role": "user", "text": "Morphine is perfect, but give me another artist in that smoky late-night vein. Nothing too heavy."},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "new_artist",
                "summary": "Another artist with a smoky late-night bar sound like Morphine, but not too heavy.",
                "source_turn": 2,
                "evidence_text": "another artist in that smoky late-night vein"
            },
            "facts": [
                {"type": "artist", "value": "Morphine", "role": "satisfied_prior", "anchor_use": "do_not_use", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "another artist"},
                {"type": "attribute", "facet": "mood", "value": "smoky", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "smoky"},
                {"type": "attribute", "facet": "mood", "value": "late-night", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "late-night vein"},
                {"type": "attribute", "facet": "sonic", "value": "heavy", "role": "rejected", "anchor_use": "do_not_use", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "Nothing too heavy"}
            ],
            "exclusions": [
                {"type": "attribute", "facet": "sonic", "value": "heavy", "scope": "soft_preference", "source_turn": 2, "evidence_text": "Nothing too heavy"}
            ],
            "turn_intent": "Another artist with a smoky late-night bar sound like Morphine, but not too heavy.",
            "track_feedback": [
                {"track_id": "t-morphine-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "artist", "value": "Morphine", "role": "satisfied", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "another artist"},
                {"type": "tag", "value": "smoky", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "smoky"},
                {"type": "tag", "value": "late-night", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "late-night vein"},
                {"type": "tag", "value": "heavy", "role": "rejected", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "Nothing too heavy"}
            ],
            "target_artist_mode": "new_artist",
            "retrieval_profile": "novelty",
            "rejections": [
                {"kind": "tag", "value": "heavy", "scope": "soft", "source_turn": 2, "evidence_text": "Nothing too heavy"}
            ],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-radiohead-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Play Paranoid Android by Radiohead."},
                {"turn": 1, "role": "music", "track_id": "t-radiohead-1", "label": "Radiohead - Paranoid Android"},
                {"turn": 1, "role": "assistant", "text": "Here it is."},
                {"turn": 2, "role": "user", "text": "Can you give me another Radiohead track from OK Computer?"},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "same_album",
                "summary": "Another Radiohead track from OK Computer.",
                "source_turn": 2,
                "evidence_text": "another Radiohead track from OK Computer"
            },
            "facts": [
                {"type": "artist", "value": "Radiohead", "role": "current_target", "anchor_use": "must_use", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "another Radiohead"},
                {"type": "album", "value": "OK Computer", "role": "current_target", "anchor_use": "must_use", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "from OK Computer"}
            ],
            "exclusions": [],
            "turn_intent": "Another Radiohead track from OK Computer.",
            "track_feedback": [],
            "referenced_track_ids": [],
            "entities": [
                {"type": "artist", "value": "Radiohead", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "another Radiohead"},
                {"type": "album", "value": "OK Computer", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "from OK Computer"}
            ],
            "target_artist_mode": "same_artist",
            "retrieval_profile": "exact_probe",
            "rejections": [],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-frankocean-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Can you play something atmospheric and chill for late-night unwinding?"},
                {"turn": 1, "role": "music", "track_id": "t-frankocean-1", "label": "Frank Ocean - Seigfried"},
                {"turn": 1, "role": "assistant", "text": "Try Seigfried by Frank Ocean."},
                {"turn": 2, "role": "user", "text": "Seigfried is a good pick, Frank Ocean always hits the spot. Do you have anything more melancholic and dreamy, less upbeat, still late-night?"},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "same_artist",
                "summary": "More Frank Ocean or closely related late-night music with a more melancholic, dreamy, less upbeat feel.",
                "source_turn": 2,
                "evidence_text": "Frank Ocean always hits the spot"
            },
            "facts": [
                {"type": "artist", "value": "Frank Ocean", "role": "current_target", "anchor_use": "must_use", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "Frank Ocean always hits the spot"},
                {"type": "attribute", "facet": "mood", "value": "melancholic", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "more melancholic"},
                {"type": "attribute", "facet": "mood", "value": "dreamy", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "dreamy"},
                {"type": "attribute", "facet": "mood", "value": "late-night", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "still late-night"}
            ],
            "exclusions": [
                {"type": "attribute", "facet": "energy", "value": "upbeat", "scope": "soft_preference", "source_turn": 2, "evidence_text": "less upbeat"}
            ],
            "turn_intent": "More Frank Ocean or closely related late-night music with a more melancholic, dreamy, less upbeat feel.",
            "track_feedback": [
                {"track_id": "t-frankocean-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "artist", "value": "Frank Ocean", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "Frank Ocean always hits the spot"},
                {"type": "tag", "value": "melancholic", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "more melancholic"},
                {"type": "tag", "value": "dreamy", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "dreamy"},
                {"type": "tag", "value": "late-night", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "still late-night"}
            ],
            "target_artist_mode": "same_artist",
            "retrieval_profile": "continuation",
            "rejections": [
                {"kind": "style", "value": "upbeat", "scope": "soft", "source_turn": 2, "evidence_text": "less upbeat"}
            ],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-doors-1", "t-pearljam-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Start a rock evolution journey from classic roots."},
                {"turn": 1, "role": "music", "track_id": "t-doors-1", "label": "The Doors - Light My Fire"},
                {"turn": 2, "role": "user", "text": "Great start. Now take me to early 90s alternative rock with powerful guitar."},
                {"turn": 2, "role": "music", "track_id": "t-pearljam-1", "label": "Pearl Jam - Alive"},
                {"turn": 3, "role": "user", "text": "Perfect. What's next on this journey? Maybe late 90s or early 2000s, still keeping that alternative vibe."},
            ],
        },
        "output": {
            "turn_intent": "Next stop in a rock evolution journey: late-90s or early-2000s alternative rock, away from the prior artists.",
            "track_feedback": [
                {"track_id": "t-doors-1", "overall_sentiment": 1, "role": "satisfied"},
                {"track_id": "t-pearljam-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "artist", "value": "The Doors", "role": "history", "source_turn": 1, "mentioned_current_turn": False, "use_as_retrieval_seed": False, "evidence_text": "classic roots"},
                {"type": "artist", "value": "Pearl Jam", "role": "history", "source_turn": 2, "mentioned_current_turn": False, "use_as_retrieval_seed": False, "evidence_text": "early 90s"},
                {"type": "tag", "value": "alternative rock", "role": "current_target", "source_turn": 3, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "alternative vibe"}
            ],
            "target_artist_mode": "new_artist",
            "retrieval_profile": "novelty",
            "rejections": [],
            "temporal_constraint": {"kind": "style_era", "start_year": 1995, "end_year": 2005, "strength": "soft", "apply_as_filter": False, "evidence_text": "late 90s or early 2000s"},
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-sister-sledge-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Give me funky, soulful R&B from the late 70s."},
                {"turn": 1, "role": "music", "track_id": "t-sister-sledge-1", "label": "Sister Sledge - He's the Greatest Dancer"},
                {"turn": 1, "role": "assistant", "text": "Try this."},
                {"turn": 2, "role": "user", "text": "Yes, that golden era R&B sound is what I want. What else has that vibe?"},
            ],
        },
        "output": {
            "turn_intent": "Funky, soulful golden-era R&B with a late-70s style vibe.",
            "track_feedback": [
                {"track_id": "t-sister-sledge-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "tag", "value": "R&B", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "R&B sound"},
                {"type": "tag", "value": "funky", "role": "current_target", "source_turn": 2, "mentioned_current_turn": False, "use_as_retrieval_seed": True, "evidence_text": "funky"},
                {"type": "tag", "value": "soulful", "role": "current_target", "source_turn": 2, "mentioned_current_turn": False, "use_as_retrieval_seed": True, "evidence_text": "soulful"}
            ],
            "target_artist_mode": "new_artist",
            "retrieval_profile": "novelty",
            "rejections": [],
            "temporal_constraint": {"kind": "style_era", "start_year": 1975, "end_year": 1979, "strength": "soft", "apply_as_filter": False, "evidence_text": "golden era R&B sound"},
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-daftpunk-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Some electronic dance music."},
                {"turn": 1, "role": "music", "track_id": "t-daftpunk-1", "label": "Daft Punk - One More Time"},
                {"turn": 1, "role": "assistant", "text": "How about this?"},
                {"turn": 2, "role": "user", "text": "No more Daft Punk. Give me another upbeat electronic track by someone else."},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "new_artist",
                "summary": "Another upbeat electronic track by someone other than Daft Punk.",
                "source_turn": 2,
                "evidence_text": "by someone else"
            },
            "facts": [
                {"type": "artist", "value": "Daft Punk", "role": "rejected", "anchor_use": "do_not_use", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "No more Daft Punk"},
                {"type": "attribute", "facet": "energy", "value": "upbeat", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "upbeat electronic"},
                {"type": "attribute", "facet": "genre", "value": "electronic", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "electronic track"}
            ],
            "exclusions": [
                {"type": "artist", "value": "Daft Punk", "scope": "next_turn_hard", "source_turn": 2, "evidence_text": "No more Daft Punk"}
            ],
            "turn_intent": "Another upbeat electronic track by someone other than Daft Punk.",
            "track_feedback": [
                {"track_id": "t-daftpunk-1", "overall_sentiment": 0, "role": "contrast"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "artist", "value": "Daft Punk", "role": "rejected", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "No more Daft Punk"},
                {"type": "tag", "value": "upbeat", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "upbeat electronic"},
                {"type": "tag", "value": "electronic", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "electronic track"}
            ],
            "target_artist_mode": "new_artist",
            "retrieval_profile": "novelty",
            "rejections": [
                {"kind": "artist", "value": "Daft Punk", "scope": "hard", "source_turn": 2, "evidence_text": "No more Daft Punk"}
            ],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-radiohead-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Give me a moody alternative rock song."},
                {"turn": 1, "role": "music", "track_id": "t-radiohead-1", "label": "Radiohead - Karma Police"},
                {"turn": 1, "role": "assistant", "text": "Try Karma Police by Radiohead."},
                {"turn": 2, "role": "user", "text": "Karma Police is great, but I'm good on Radiohead for now. Give me other alternative rock bands with that moody, melodic feel."},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "new_artist",
                "summary": "Other alternative rock bands with a moody, melodic feel; exclude Radiohead for now.",
                "source_turn": 2,
                "evidence_text": "other alternative rock bands"
            },
            "facts": [
                {"type": "artist", "value": "Radiohead", "role": "rejected", "anchor_use": "do_not_use", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "good on Radiohead for now"},
                {"type": "attribute", "facet": "genre", "value": "alternative rock", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "alternative rock bands"},
                {"type": "attribute", "facet": "mood", "value": "moody melodic", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "moody, melodic feel"}
            ],
            "exclusions": [
                {"type": "artist", "value": "Radiohead", "scope": "next_turn_hard", "source_turn": 2, "evidence_text": "good on Radiohead for now"}
            ],
            "turn_intent": "Other alternative rock bands with a moody, melodic feel; exclude Radiohead for now.",
            "track_feedback": [
                {"track_id": "t-radiohead-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "artist", "value": "Radiohead", "role": "rejected", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "good on Radiohead for now"},
                {"type": "tag", "value": "alternative rock", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "alternative rock bands"},
                {"type": "tag", "value": "moody melodic", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "moody, melodic feel"}
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
            "played_track_ids": [],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Only play tracks released before 2010 with a mellow acoustic feel."}
            ],
        },
        "output": {
            "turn_intent": "Mellow acoustic tracks released before 2010.",
            "track_feedback": [],
            "referenced_track_ids": [],
            "entities": [
                {"type": "tag", "value": "mellow", "role": "current_target", "source_turn": 1, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "mellow"},
                {"type": "tag", "value": "acoustic", "role": "current_target", "source_turn": 1, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "acoustic feel"}
            ],
            "target_artist_mode": "any_artist",
            "retrieval_profile": "feature_search",
            "rejections": [],
            "temporal_constraint": {"kind": "release_date", "start_year": None, "end_year": 2009, "strength": "hard", "apply_as_filter": True, "evidence_text": "released before 2010"},
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-real-thing-1"],
            "conversation": [
                {"turn": 5, "role": "user", "text": "I want danceable late 70s or early 80s disco and funk."},
                {"turn": 5, "role": "music", "track_id": "t-real-thing-1", "label": "The Real Thing - Can You Feel the Force"},
                {"turn": 5, "role": "assistant", "text": "Try Can You Feel the Force by The Real Thing."},
                {"turn": 6, "role": "user", "text": "Yes! Can You Feel the Force is awesome. That's exactly the kind of energy I'm looking for. What are some other high-energy, classic disco or funk tracks from that late 70s to early 80s period?"},
            ],
        },
        "output": {
            "turn_intent": "Other high-energy classic disco or funk tracks with late-70s to early-80s style energy.",
            "track_feedback": [
                {"track_id": "t-real-thing-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "track", "value": "Can You Feel the Force", "role": "satisfied", "source_turn": 6, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "is awesome"},
                {"type": "artist", "value": "The Real Thing", "role": "satisfied", "source_turn": 5, "mentioned_current_turn": False, "use_as_retrieval_seed": False, "evidence_text": "other high-energy"},
                {"type": "tag", "value": "high-energy", "role": "current_target", "source_turn": 6, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "high-energy"},
                {"type": "tag", "value": "classic disco", "role": "current_target", "source_turn": 6, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "classic disco"},
                {"type": "tag", "value": "funk", "role": "current_target", "source_turn": 6, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "funk tracks"}
            ],
            "target_artist_mode": "new_artist",
            "retrieval_profile": "novelty",
            "rejections": [],
            "temporal_constraint": {"kind": "style_era", "start_year": 1975, "end_year": 1984, "strength": "soft", "apply_as_filter": False, "evidence_text": "late 70s to early 80s"},
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-britney-toxic"],
            "conversation": [
                {"turn": 2, "role": "user", "text": "I want late 90s or early 2000s confident pop with a super strong, driving beat."},
                {"turn": 2, "role": "music", "track_id": "t-britney-toxic", "label": "Britney Spears - Toxic"},
                {"turn": 2, "role": "assistant", "text": "Toxic by Britney Spears fits that driving beat."},
                {"turn": 3, "role": "user", "text": "Yes! Toxic by Britney Spears is exactly the track. Can you recommend something else with a similar super strong, driving beat, maybe a bit more recent but still with that empowering pop energy?"},
            ],
        },
        "output": {
            "turn_intent": "Something else with a super strong driving beat and empowering pop energy, maybe a bit more recent than Toxic.",
            "track_feedback": [
                {"track_id": "t-britney-toxic", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "track", "value": "Toxic", "role": "satisfied", "source_turn": 3, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "exactly the track"},
                {"type": "artist", "value": "Britney Spears", "role": "satisfied", "source_turn": 3, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "something else"},
                {"type": "tag", "value": "driving beat", "role": "current_target", "source_turn": 3, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "driving beat"},
                {"type": "tag", "value": "empowering pop", "role": "current_target", "source_turn": 3, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "empowering pop energy"}
            ],
            "target_artist_mode": "new_artist",
            "retrieval_profile": "novelty",
            "rejections": [],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": [],
            "conversation": [
                {"turn": 1, "role": "user", "text": "I'm trying to remember an alternative rock band from the 2010s. They had a really popular, upbeat song that was perfect for dancing."},
                {"turn": 2, "role": "user", "text": "Yes, WALK THE MOON! That's the band I was thinking of. Do they have a really famous song that tells someone to shut up and dance?"},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "hidden_target",
                "summary": "Find the famous WALK THE MOON song with lyrics about telling someone to shut up and dance.",
                "source_turn": 2,
                "evidence_text": "song that tells someone to shut up and dance"
            },
            "facts": [
                {"type": "artist", "value": "WALK THE MOON", "role": "current_target", "anchor_use": "must_use", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "That's the band"},
                {"type": "attribute", "facet": "genre", "value": "alternative rock", "role": "current_target", "anchor_use": "query_facet", "source_turn": 1, "mentioned_current_turn": False, "evidence_text": "alternative rock"},
                {"type": "attribute", "facet": "energy", "value": "upbeat", "role": "current_target", "anchor_use": "query_facet", "source_turn": 1, "mentioned_current_turn": False, "evidence_text": "upbeat song"},
                {"type": "attribute", "facet": "lyrical_theme", "value": "shut up and dance", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "shut up and dance"}
            ],
            "exclusions": [],
            "turn_intent": "Find the famous WALK THE MOON song with lyrics about telling someone to shut up and dance.",
            "track_feedback": [],
            "referenced_track_ids": [],
            "entities": [
                {"type": "artist", "value": "WALK THE MOON", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "That's the band"},
                {"type": "tag", "value": "alternative rock", "role": "current_target", "source_turn": 1, "mentioned_current_turn": False, "use_as_retrieval_seed": True, "evidence_text": "alternative rock"},
                {"type": "tag", "value": "upbeat", "role": "current_target", "source_turn": 1, "mentioned_current_turn": False, "use_as_retrieval_seed": True, "evidence_text": "upbeat song"}
            ],
            "target_artist_mode": "same_artist",
            "retrieval_profile": "hidden_target_search",
            "rejections": [],
            "temporal_constraint": {"kind": "style_era", "start_year": 2010, "end_year": 2019, "strength": "soft", "apply_as_filter": False, "evidence_text": "from the 2010s"},
            "lyrical_theme": "shut up and dance",
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-enya-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Give me something atmospheric and spacious."},
                {"turn": 1, "role": "music", "track_id": "t-enya-1", "label": "Enya - Caribbean Blue"},
                {"turn": 1, "role": "assistant", "text": "Here is Enya."},
                {"turn": 2, "role": "user", "text": "I like Enya's atmosphere, but not the sleepy new age side. Give me darker, more percussive ambient by another artist."},
            ],
        },
        "output": {
            "turn_intent": "Darker, more percussive ambient by another artist, using Enya only as contrast for atmosphere.",
            "track_feedback": [
                {"track_id": "t-enya-1", "overall_sentiment": 0, "role": "contrast"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "artist", "value": "Enya", "role": "contrast", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "but not"},
                {"type": "tag", "value": "atmospheric", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "atmosphere"},
                {"type": "tag", "value": "darker", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "darker"},
                {"type": "tag", "value": "percussive ambient", "role": "current_target", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "percussive ambient"},
                {"type": "tag", "value": "sleepy new age", "role": "rejected", "source_turn": 2, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "not the sleepy new age side"}
            ],
            "target_artist_mode": "new_artist",
            "retrieval_profile": "novelty",
            "rejections": [
                {"kind": "style", "value": "sleepy new age", "scope": "soft", "source_turn": 2, "evidence_text": "not the sleepy new age side"}
            ],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-pop-punk-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "I'm trying to remember a theatrical pop-punk song from Neon Riot's first album."},
                {"turn": 1, "role": "music", "track_id": "t-pop-punk-1", "label": "Neon Riot - After Midnight"},
                {"turn": 1, "role": "assistant", "text": "Maybe this one?"},
                {"turn": 2, "role": "user", "text": "Close, but still not the one that screams \"mid-2000s emo\" to me. The track is definitely from Midnight Static, with a big dramatic chorus and lyrics about messy breakup angst."},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "hidden_target",
                "summary": "Find the specific Neon Riot track from Midnight Static with a mid-2000s emo feel, big dramatic chorus, and messy breakup-angst lyrics.",
                "source_turn": 2,
                "evidence_text": "still not the one that screams \"mid-2000s emo\""
            },
            "facts": [
                {"type": "artist", "value": "Neon Riot", "role": "current_target", "anchor_use": "must_use", "relation": "exact_target", "reuse": "must_reuse", "source_turn": 1, "mentioned_current_turn": False, "evidence_text": "from Neon Riot's first album"},
                {"type": "album", "value": "Midnight Static", "role": "current_target", "anchor_use": "must_use", "relation": "exact_target", "reuse": "must_reuse", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "from Midnight Static"},
                {"type": "attribute", "facet": "genre", "value": "mid-2000s emo", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "screams \"mid-2000s emo\""},
                {"type": "attribute", "facet": "sonic", "value": "big dramatic chorus", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "big dramatic chorus"},
                {"type": "attribute", "facet": "lyrical_theme", "value": "messy breakup angst", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "messy breakup angst"}
            ],
            "exclusions": [],
            "track_feedback": [
                {"track_id": "t-pop-punk-1", "overall_sentiment": 0, "role": "contrast"}
            ],
            "referenced_track_ids": [],
            "temporal_constraint": {
                "kind": "style_era",
                "start_year": 2004,
                "end_year": 2007,
                "strength": "soft",
                "apply_as_filter": False,
                "evidence_text": "mid-2000s emo"
            },
            "lyrical_theme": "messy breakup angst",
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-synth-score-1"],
            "conversation": [
                {"turn": 6, "role": "user", "text": "These Eclipse Station tracks are fantastic, but I'm keen to discover new artists now."},
                {"turn": 6, "role": "music", "track_id": "t-synth-score-1", "label": "Mara Vale & Owen Cross - Orbital Signal"},
                {"turn": 6, "role": "assistant", "text": "Here is another cue from the Eclipse Station soundtrack."},
                {"turn": 7, "role": "user", "text": "These Eclipse Station tracks are fantastic, but I've heard quite a few from this album now. I'm looking for new artists or different film scores with that same dark, futuristic, melancholic electronic instrumental vibe. Please, no more from Eclipse Station."},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "new_artist",
                "summary": "New artists or different film scores with a dark, futuristic, melancholic electronic instrumental vibe; no more Eclipse Station.",
                "source_turn": 7,
                "evidence_text": "new artists or different film scores"
            },
            "facts": [
                {"type": "album", "value": "Eclipse Station", "role": "rejected", "anchor_use": "do_not_use", "source_turn": 7, "mentioned_current_turn": True, "evidence_text": "no more from Eclipse Station"},
                {"type": "artist", "value": "Mara Vale", "role": "satisfied_prior", "anchor_use": "do_not_use", "source_turn": 6, "mentioned_current_turn": False, "evidence_text": "new artists"},
                {"type": "artist", "value": "Owen Cross", "role": "satisfied_prior", "anchor_use": "do_not_use", "source_turn": 6, "mentioned_current_turn": False, "evidence_text": "different film scores"},
                {"type": "attribute", "facet": "sonic", "value": "dark futuristic", "role": "current_target", "anchor_use": "query_facet", "source_turn": 7, "mentioned_current_turn": True, "evidence_text": "dark, futuristic"},
                {"type": "attribute", "facet": "sonic", "value": "melancholic electronic instrumental", "role": "current_target", "anchor_use": "query_facet", "source_turn": 7, "mentioned_current_turn": True, "evidence_text": "melancholic electronic instrumental"}
            ],
            "exclusions": [
                {"type": "album", "value": "Eclipse Station", "scope": "next_turn_hard", "source_turn": 7, "evidence_text": "no more from Eclipse Station"}
            ],
            "turn_intent": "New artists or different film scores with a dark, futuristic, melancholic electronic instrumental vibe; no more Eclipse Station.",
            "track_feedback": [
                {"track_id": "t-synth-score-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "entities": [
                {"type": "album", "value": "Eclipse Station", "role": "rejected", "source_turn": 7, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "no more from Eclipse Station"},
                {"type": "artist", "value": "Mara Vale", "role": "satisfied", "source_turn": 6, "mentioned_current_turn": False, "use_as_retrieval_seed": False, "evidence_text": "new artists"},
                {"type": "artist", "value": "Owen Cross", "role": "satisfied", "source_turn": 6, "mentioned_current_turn": False, "use_as_retrieval_seed": False, "evidence_text": "different film scores"},
                {"type": "tag", "value": "dark futuristic", "role": "current_target", "source_turn": 7, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "dark, futuristic"},
                {"type": "tag", "value": "melancholic electronic instrumental", "role": "current_target", "source_turn": 7, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "melancholic electronic instrumental"}
            ],
            "target_artist_mode": "new_artist",
            "retrieval_profile": "novelty",
            "rejections": [
                {"kind": "album", "value": "Eclipse Station", "scope": "hard", "source_turn": 7, "evidence_text": "no more from Eclipse Station"}
            ],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-disco-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Play something energetic and classic from the disco era."},
                {"turn": 1, "role": "music", "track_id": "t-disco-1", "label": "The Real Thing - Can You Feel the Force"},
                {"turn": 1, "role": "assistant", "text": "Try this one."},
                {"turn": 2, "role": "user", "text": "Yes, this is awesome. What are some other high-energy classic disco or funk tracks from the late 70s or early 80s?"},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "attribute_search",
                "summary": "Other high-energy classic disco or funk tracks from the late 70s or early 80s.",
                "source_turn": 2,
                "evidence_text": "other high-energy classic disco or funk tracks"
            },
            "facts": [
                {"type": "track", "value": "Can You Feel the Force", "role": "satisfied_prior", "anchor_use": "do_not_use", "source_turn": 2, "mentioned_current_turn": False, "evidence_text": "this is awesome"},
                {"type": "artist", "value": "The Real Thing", "role": "satisfied_prior", "anchor_use": "do_not_use", "source_turn": 1, "mentioned_current_turn": False, "evidence_text": "other high-energy"},
                {"type": "attribute", "facet": "energy", "value": "high-energy", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "high-energy"},
                {"type": "attribute", "facet": "genre", "value": "classic disco", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "classic disco"},
                {"type": "attribute", "facet": "genre", "value": "funk", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "funk tracks"},
                {"type": "attribute", "facet": "era", "value": "late 70s or early 80s", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "late 70s or early 80s"}
            ],
            "exclusions": [],
            "temporal_constraint": {
                "kind": "style_era",
                "start_year": 1977,
                "end_year": 1984,
                "strength": "soft",
                "apply_as_filter": False,
                "evidence_text": "late 70s or early 80s"
            },
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-darkfolk-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "I want atmospheric dark folk with female vocals."},
                {"turn": 1, "role": "music", "track_id": "t-darkfolk-1", "label": "Myrkur - Onde Børn"},
                {"turn": 1, "role": "assistant", "text": "Try this dark folk track."},
                {"turn": 2, "role": "user", "text": "This is close, but lean into the ethereal vocals and traditional instruments. Not the heavy metal side."},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "attribute_search",
                "summary": "Atmospheric dark folk with ethereal vocals and traditional instruments, avoiding the heavy metal side.",
                "source_turn": 2,
                "evidence_text": "ethereal vocals and traditional instruments",
                "candidate_types": [
                    {"request_type": "attribute_search", "confidence": 0.9, "evidence_text": "ethereal vocals and traditional instruments"},
                    {"request_type": "similar_to_prior", "confidence": 0.35, "evidence_text": "This is close"}
                ]
            },
            "facts": [
                {"type": "attribute", "facet": "genre", "value": "dark folk", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": False, "evidence_text": "dark folk"},
                {"type": "attribute", "facet": "sonic", "value": "ethereal vocals", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "ethereal vocals"},
                {"type": "attribute", "facet": "instrument", "value": "traditional instruments", "role": "current_target", "anchor_use": "query_facet", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "traditional instruments"},
                {"type": "attribute", "facet": "sonic", "value": "heavy metal side", "role": "rejected", "anchor_use": "do_not_use", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "Not the heavy metal side"}
            ],
            "exclusions": [
                {"type": "attribute", "facet": "sonic", "value": "heavy metal side", "scope": "soft_preference", "source_turn": 2, "evidence_text": "Not the heavy metal side"}
            ],
            "track_feedback": [
                {"track_id": "t-darkfolk-1", "overall_sentiment": 0, "role": "contrast"}
            ],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": [],
            "conversation": [
                {"turn": 1, "role": "user", "text": "I want electronic albums from the 2010s where the cover art is striking and artistically unique."},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "attribute_search",
                "summary": "Electronic albums from the 2010s with striking, artistically unique cover art.",
                "source_turn": 1,
                "evidence_text": "cover art is striking and artistically unique"
            },
            "facts": [
                {"type": "attribute", "facet": "genre", "value": "electronic", "role": "current_target", "anchor_use": "query_facet", "source_turn": 1, "mentioned_current_turn": True, "evidence_text": "electronic albums"},
                {"type": "attribute", "facet": "visual", "value": "striking cover art", "role": "current_target", "anchor_use": "query_facet", "source_turn": 1, "mentioned_current_turn": True, "evidence_text": "cover art is striking"},
                {"type": "attribute", "facet": "visual", "value": "artistically unique", "role": "current_target", "anchor_use": "query_facet", "source_turn": 1, "mentioned_current_turn": True, "evidence_text": "artistically unique"},
                {"type": "attribute", "facet": "era", "value": "2010s", "role": "current_target", "anchor_use": "query_facet", "source_turn": 1, "mentioned_current_turn": True, "evidence_text": "from the 2010s"}
            ],
            "exclusions": [],
            "temporal_constraint": {"kind": "style_era", "start_year": 2010, "end_year": 2019, "strength": "soft", "apply_as_filter": False, "evidence_text": "from the 2010s"},
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-story-1", "t-sertanejo-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Play hip-hop with vivid storytelling."},
                {"turn": 1, "role": "music", "track_id": "t-story-1", "label": "Nas - I Gave You Power"},
                {"turn": 2, "role": "user", "text": "That storytelling almost feels like watching a movie. Can you give me more tracks where the details are super clear?"},
                {"turn": 2, "role": "music", "track_id": "t-sertanejo-1", "label": "Marília Mendonça - O Que Falta Em Você Sou Eu"},
                {"turn": 3, "role": "user", "text": "This has the deep longing and emotional storytelling I love. Keep them coming, maybe by other artists with that powerful emotional sertanejo style, where the story feels like watching a movie."},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "new_artist",
                "summary": "Other artists with powerful emotional sertanejo, preserving deep longing and emotional storytelling from the liked prior song.",
                "source_turn": 3,
                "evidence_text": "other artists with that powerful emotional sertanejo style"
            },
            "facts": [
                {"type": "track", "value": "O Que Falta Em Você Sou Eu", "role": "satisfied_prior", "anchor_use": "do_not_use", "source_turn": 3, "mentioned_current_turn": True, "evidence_text": "This has the deep longing"},
                {"type": "artist", "value": "Marília Mendonça", "role": "satisfied_prior", "anchor_use": "do_not_use", "source_turn": 2, "mentioned_current_turn": False, "evidence_text": "by other artists"},
                {"type": "attribute", "facet": "lyrical_theme", "value": "watching a movie", "role": "current_target", "anchor_use": "query_facet", "source_turn": 3, "mentioned_current_turn": True, "evidence_text": "story feels like watching a movie"},
                {"type": "attribute", "facet": "lyrical_theme", "value": "deep longing", "role": "current_target", "anchor_use": "query_facet", "source_turn": 3, "mentioned_current_turn": True, "evidence_text": "deep longing"},
                {"type": "attribute", "facet": "lyrical_theme", "value": "emotional storytelling", "role": "current_target", "anchor_use": "query_facet", "source_turn": 3, "mentioned_current_turn": True, "evidence_text": "emotional storytelling"},
                {"type": "attribute", "facet": "genre", "value": "sertanejo", "role": "current_target", "anchor_use": "query_facet", "source_turn": 3, "mentioned_current_turn": True, "evidence_text": "sertanejo style"},
                {"type": "attribute", "facet": "mood", "value": "powerful emotional", "role": "current_target", "anchor_use": "query_facet", "source_turn": 3, "mentioned_current_turn": True, "evidence_text": "powerful emotional"}
            ],
            "exclusions": [],
            "track_feedback": [
                {"track_id": "t-story-1", "overall_sentiment": 1, "role": "satisfied"},
                {"track_id": "t-sertanejo-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "temporal_constraint": None,
            "lyrical_theme": "deep longing emotional storytelling",
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-nightmoves-1"],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Play something with a distinctive 70s rock sound and lyrical depth."},
                {"turn": 1, "role": "music", "track_id": "t-nightmoves-1", "label": "Bob Seger - Night Moves"},
                {"turn": 2, "role": "user", "text": "'Night Moves' is exactly what I had in mind. Can you recommend more tracks with that same distinctive 70s rock sound and lyrical depth, perhaps from someone like John Fogerty or Bruce Springsteen?"},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "attribute_search",
                "summary": "More tracks with a distinctive 70s rock sound and lyrical depth, using John Fogerty and Bruce Springsteen as style references.",
                "source_turn": 2,
                "evidence_text": "someone like John Fogerty or Bruce Springsteen",
                "candidate_types": [
                    {"request_type": "attribute_search", "confidence": 0.85, "evidence_text": "distinctive 70s rock sound and lyrical depth"},
                    {"request_type": "similar_to_prior", "confidence": 0.65, "evidence_text": "same distinctive 70s rock sound"}
                ]
            },
            "facts": [
                {"type": "track", "value": "Night Moves", "role": "satisfied_prior", "anchor_use": "do_not_use", "relation": "satisfied_prior", "reuse": "avoid_exact", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "exactly what I had in mind"},
                {"type": "artist", "value": "Bob Seger", "role": "satisfied_prior", "anchor_use": "do_not_use", "relation": "satisfied_prior", "reuse": "avoid_exact", "source_turn": 1, "mentioned_current_turn": False, "evidence_text": "Night Moves"},
                {"type": "artist", "value": "John Fogerty", "role": "current_target", "anchor_use": "partial_anchor", "relation": "style_reference", "reuse": "may_reuse", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "someone like John Fogerty"},
                {"type": "artist", "value": "Bruce Springsteen", "role": "current_target", "anchor_use": "partial_anchor", "relation": "style_reference", "reuse": "may_reuse", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "or Bruce Springsteen"},
                {"type": "attribute", "facet": "genre", "value": "distinctive 70s rock", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "distinctive 70s rock sound"},
                {"type": "attribute", "facet": "lyrical_theme", "value": "lyrical depth", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 2, "mentioned_current_turn": True, "evidence_text": "lyrical depth"}
            ],
            "exclusions": [],
            "track_feedback": [
                {"track_id": "t-nightmoves-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "temporal_constraint": {
                "kind": "style_era",
                "start_year": 1970,
                "end_year": 1979,
                "strength": "soft",
                "apply_as_filter": False,
                "evidence_text": "70s rock sound"
            },
            "lyrical_theme": "lyrical depth",
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-alanis-1", "t-natalie-1"],
            "conversation": [
                {"turn": 5, "role": "user", "text": "Yes, Alanis Morissette has the raw, introspective 90s style I wanted."},
                {"turn": 5, "role": "music", "track_id": "t-alanis-1", "label": "Alanis Morissette - You Learn"},
                {"turn": 6, "role": "music", "track_id": "t-natalie-1", "label": "Natalie Merchant - Wonder"},
                {"turn": 6, "role": "user", "text": "Natalie Merchant is a great pick. Can you suggest another iconic female artist from the 90s with a similar thoughtful, storytelling approach?"},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "new_artist",
                "summary": "Another iconic female artist from the 90s with a thoughtful storytelling approach, using Alanis Morissette and Natalie Merchant only as style context.",
                "source_turn": 6,
                "evidence_text": "another iconic female artist from the 90s",
                "candidate_types": [
                    {"request_type": "new_artist", "confidence": 0.9, "evidence_text": "another iconic female artist"},
                    {"request_type": "similar_to_prior", "confidence": 0.55, "evidence_text": "similar thoughtful, storytelling approach"}
                ]
            },
            "facts": [
                {"type": "artist", "value": "Alanis Morissette", "role": "satisfied_prior", "anchor_use": "do_not_use", "relation": "style_reference", "reuse": "may_reuse", "source_turn": 5, "mentioned_current_turn": False, "evidence_text": "Alanis Morissette"},
                {"type": "artist", "value": "Natalie Merchant", "role": "satisfied_prior", "anchor_use": "do_not_use", "relation": "style_reference", "reuse": "may_reuse", "source_turn": 6, "mentioned_current_turn": True, "evidence_text": "Natalie Merchant is a great pick"},
                {"type": "attribute", "facet": "performer", "value": "female artist", "role": "current_target", "anchor_use": "query_facet", "source_turn": 6, "mentioned_current_turn": True, "evidence_text": "female artist"},
                {"type": "attribute", "facet": "era", "value": "1990s", "role": "current_target", "anchor_use": "query_facet", "source_turn": 6, "mentioned_current_turn": True, "evidence_text": "from the 90s"},
                {"type": "attribute", "facet": "mood", "value": "thoughtful", "role": "current_target", "anchor_use": "query_facet", "source_turn": 6, "mentioned_current_turn": True, "evidence_text": "thoughtful"},
                {"type": "attribute", "facet": "lyrical_theme", "value": "storytelling", "role": "current_target", "anchor_use": "query_facet", "source_turn": 6, "mentioned_current_turn": True, "evidence_text": "storytelling approach"}
            ],
            "exclusions": [],
            "track_feedback": [
                {"track_id": "t-alanis-1", "overall_sentiment": 1, "role": "satisfied"},
                {"track_id": "t-natalie-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "entities": [
                {"type": "artist", "value": "Alanis Morissette", "role": "satisfied", "source_turn": 5, "mentioned_current_turn": False, "use_as_retrieval_seed": False, "evidence_text": "Alanis Morissette"},
                {"type": "artist", "value": "Natalie Merchant", "role": "satisfied", "source_turn": 6, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "Natalie Merchant is a great pick"},
                {"type": "tag", "value": "female artist", "role": "current_target", "source_turn": 6, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "female artist"},
                {"type": "tag", "value": "1990s", "role": "current_target", "source_turn": 6, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "from the 90s"},
                {"type": "tag", "value": "thoughtful", "role": "current_target", "source_turn": 6, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "thoughtful"},
                {"type": "tag", "value": "storytelling", "role": "current_target", "source_turn": 6, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "storytelling approach"}
            ],
            "target_artist_mode": "new_artist",
            "retrieval_profile": "novelty",
            "rejections": [],
            "temporal_constraint": {"kind": "style_era", "start_year": 1990, "end_year": 1999, "strength": "soft", "apply_as_filter": False, "evidence_text": "from the 90s"},
            "lyrical_theme": "storytelling",
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-sleep-1"],
            "conversation": [
                {"turn": 7, "role": "user", "text": "I'm trying to find dreamy late 2000s ambient electronic, strictly instrumental."},
                {"turn": 7, "role": "music", "track_id": "t-sleep-1", "label": "Example Artist - Sleep Paralysis"},
                {"turn": 8, "role": "user", "text": "Sleep Paralysis is not what I'm looking for. The mood is too dark and harsh, not dreamy or serene like the late 2000s ambient electronic I'm trying to find. Also, the era is still off. I want something warm, ethereal, and subtly rhythmic."},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "attribute_search",
                "summary": "Warm, ethereal, subtly rhythmic, dreamy and serene ambient electronic with a late-2000s style era; reject the prior dark and harsh mood.",
                "source_turn": 8,
                "evidence_text": "warm, ethereal, and subtly rhythmic"
            },
            "facts": [
                {"type": "track", "value": "Sleep Paralysis", "role": "rejected", "anchor_use": "do_not_use", "relation": "exclude", "reuse": "must_exclude", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "not what I'm looking for"},
                {"type": "attribute", "facet": "mood", "value": "dark and harsh", "role": "rejected", "anchor_use": "do_not_use", "relation": "exclude", "reuse": "must_exclude", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "too dark and harsh"},
                {"type": "attribute", "facet": "mood", "value": "dreamy", "role": "current_target", "anchor_use": "query_facet", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "not dreamy or serene like"},
                {"type": "attribute", "facet": "mood", "value": "serene", "role": "current_target", "anchor_use": "query_facet", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "not dreamy or serene like"},
                {"type": "attribute", "facet": "genre", "value": "ambient electronic", "role": "current_target", "anchor_use": "query_facet", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "ambient electronic"},
                {"type": "attribute", "facet": "sonic", "value": "warm ethereal subtly rhythmic", "role": "current_target", "anchor_use": "query_facet", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "warm, ethereal, and subtly rhythmic"},
                {"type": "attribute", "facet": "era", "value": "late 2000s", "role": "current_target", "anchor_use": "query_facet", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "late 2000s ambient electronic"}
            ],
            "exclusions": [
                {"type": "track", "value": "Sleep Paralysis", "scope": "next_turn_hard", "source_turn": 8, "evidence_text": "not what I'm looking for"},
                {"type": "attribute", "facet": "mood", "value": "dark and harsh", "scope": "soft_preference", "source_turn": 8, "evidence_text": "too dark and harsh"}
            ],
            "track_feedback": [
                {"track_id": "t-sleep-1", "overall_sentiment": 0, "role": "contrast"}
            ],
            "entities": [
                {"type": "track", "value": "Sleep Paralysis", "role": "rejected", "source_turn": 8, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "not what I'm looking for"},
                {"type": "tag", "value": "dark and harsh", "role": "rejected", "source_turn": 8, "mentioned_current_turn": True, "use_as_retrieval_seed": False, "evidence_text": "too dark and harsh"},
                {"type": "tag", "value": "dreamy", "role": "current_target", "source_turn": 8, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "not dreamy or serene like"},
                {"type": "tag", "value": "serene", "role": "current_target", "source_turn": 8, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "not dreamy or serene like"},
                {"type": "tag", "value": "ambient electronic", "role": "current_target", "source_turn": 8, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "ambient electronic"},
                {"type": "tag", "value": "warm ethereal subtly rhythmic", "role": "current_target", "source_turn": 8, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "warm, ethereal, and subtly rhythmic"},
                {"type": "tag", "value": "late 2000s", "role": "current_target", "source_turn": 8, "mentioned_current_turn": True, "use_as_retrieval_seed": True, "evidence_text": "late 2000s ambient electronic"}
            ],
            "target_artist_mode": "any_artist",
            "retrieval_profile": "feature_search",
            "rejections": [
                {"kind": "track", "value": "Sleep Paralysis", "scope": "hard", "source_turn": 8, "evidence_text": "not what I'm looking for"},
                {"kind": "style", "value": "dark and harsh", "scope": "soft", "source_turn": 8, "evidence_text": "too dark and harsh"}
            ],
            "temporal_constraint": {"kind": "style_era", "start_year": 2007, "end_year": 2009, "strength": "soft", "apply_as_filter": False, "evidence_text": "late 2000s ambient electronic"},
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-rock-1"],
            "conversation": [
                {"turn": 7, "role": "music", "track_id": "t-rock-1", "label": "Guano Apes - Big in Japan"},
                {"turn": 8, "role": "user", "text": "Yes! Guano Apes! I love this song, it's so powerful. The vocalist is amazing. Do you have any other powerful rock songs, maybe with a really strong guitar riff?"},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "attribute_search",
                "summary": "Other powerful rock songs with a strong guitar riff, using Guano Apes only as satisfied context.",
                "source_turn": 8,
                "evidence_text": "other powerful rock songs"
            },
            "facts": [
                {"type": "artist", "value": "Guano Apes", "role": "satisfied_prior", "anchor_use": "do_not_use", "relation": "satisfied_prior", "reuse": "avoid_exact", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "Guano Apes! I love this song"},
                {"type": "attribute", "facet": "genre", "value": "rock", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "rock songs"},
                {"type": "attribute", "facet": "energy", "value": "powerful", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "powerful"},
                {"type": "attribute", "facet": "sonic", "value": "strong guitar riff", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "strong guitar riff"},
                {"type": "attribute", "facet": "performer", "value": "amazing vocalist", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "vocalist is amazing"}
            ],
            "exclusions": [],
            "track_feedback": [
                {"track_id": "t-rock-1", "overall_sentiment": 1, "role": "satisfied"}
            ],
            "referenced_track_ids": [],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": ["t-gorillaz-1"],
            "conversation": [
                {"turn": 7, "role": "music", "track_id": "t-gorillaz-1", "label": "Gorillaz - Souk Eye"},
                {"turn": 8, "role": "user", "text": "Can you give me a Gorillaz track with a more upbeat or quirky electronic feel, maybe something that's more instrumental-focused or from one of their newer albums like Cracker Island?"},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "same_artist",
                "summary": "A Gorillaz track from a newer album like Cracker Island, with upbeat quirky electronic and instrumental-focused qualities.",
                "source_turn": 8,
                "evidence_text": "Gorillaz track"
            },
            "facts": [
                {"type": "artist", "value": "Gorillaz", "role": "current_target", "anchor_use": "must_use", "relation": "exact_target", "reuse": "must_reuse", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "Gorillaz track"},
                {"type": "album", "value": "Cracker Island", "role": "current_target", "anchor_use": "must_use", "relation": "exact_target", "reuse": "must_reuse", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "albums like Cracker Island"},
                {"type": "attribute", "facet": "energy", "value": "upbeat", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "upbeat"},
                {"type": "attribute", "facet": "sonic", "value": "quirky electronic", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "quirky electronic feel"},
                {"type": "attribute", "facet": "sonic", "value": "instrumental-focused", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 8, "mentioned_current_turn": True, "evidence_text": "instrumental-focused"}
            ],
            "exclusions": [],
            "track_feedback": [],
            "referenced_track_ids": [],
            "temporal_constraint": None,
            "lyrical_theme": None,
        },
    },
    {
        "user_prompt": {
            "played_track_ids": [],
            "conversation": [
                {"turn": 1, "role": "user", "text": "Can you play the classic Ice Cube song from the 90s that starts with 'Just wakin' up in the morning, gotta thank God'?"},
            ],
        },
        "output": {
            "current_request": {
                "request_type": "hidden_target",
                "summary": "Find the classic 90s Ice Cube song that starts with 'Just wakin' up in the morning, gotta thank God'.",
                "source_turn": 1,
                "evidence_text": "starts with 'Just wakin' up"
            },
            "facts": [
                {"type": "artist", "value": "Ice Cube", "role": "current_target", "anchor_use": "must_use", "relation": "exact_target", "reuse": "must_reuse", "source_turn": 1, "mentioned_current_turn": True, "evidence_text": "Ice Cube song"},
                {"type": "attribute", "facet": "lyrical_theme", "value": "Just wakin' up in the morning, gotta thank God", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 1, "mentioned_current_turn": True, "evidence_text": "Just wakin' up in the morning"},
                {"type": "attribute", "facet": "popularity", "value": "classic", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 1, "mentioned_current_turn": True, "evidence_text": "classic Ice Cube song"},
                {"type": "attribute", "facet": "era", "value": "1990s", "role": "current_target", "anchor_use": "query_facet", "relation": "query_facet", "reuse": "not_applicable", "source_turn": 1, "mentioned_current_turn": True, "evidence_text": "from the 90s"}
            ],
            "exclusions": [],
            "track_feedback": [],
            "referenced_track_ids": [],
            "temporal_constraint": {"kind": "style_era", "start_year": 1990, "end_year": 1999, "strength": "soft", "apply_as_filter": False, "evidence_text": "from the 90s"},
            "lyrical_theme": "Just wakin' up in the morning, gotta thank God",
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
# because Pydantic renders nested model list items as a bare
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
