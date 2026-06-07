"""Experimental decision-rubric ConversationState prompt.

This variant keeps the same schema and few-shot examples as `current`, but
adds a compact decision ladder before the schema-heavy instructions. It is for
small replay experiments, not the default production prompt.
"""

from __future__ import annotations

import json
from typing import Any

from mcrs.conversation_state.prompts import current
from mcrs.conversation_state.prompts.common import render_conversation


DECISION_RUBRIC = """

# Experimental decision ladder
Before emitting JSON, make these decisions in this order:

1. Direct target check:
   - "play X", "play X by Y", "from album Z", "the song that says ..." => protect exact entities.
   - Use current_request.request_type=exact_track/exact_artist/exact_album when a named entity is sufficient to retrieve.
   - Use current_request.request_type=hidden_target when the user is recalling a specific unknown title from clues.

2. Entity role check:
   - Current-turn named entity plus "more by/from/their" => current_target or seed.
   - Praised entity plus "what else / something else / other artists / different" => satisfied, not a seed.
   - Old entities not repeated in the latest user turn => history unless explicitly pinned.
   - "not X / no more X / besides X / other than X" => rejected and hard rejection if X is an artist/track/album.

3. Artist policy check:
   - same_artist only when the user explicitly wants the same artist/album/track family.
   - new_artist when the user asks for other artists, new bands, someone else, different scores/albums, or says no more of an artist/album.
   - any_artist when no artist constraint matters.

4. Retrieval profile check:
   - Do not emit a retrieval_profile field. Instead, make facts explicit enough for the bridge/compiler.
   - Continuation evidence should appear as exact_target current facts for artist/album/track family.
   - Novelty evidence should appear as new_artist request type plus query_facet/style_reference facts and exclusions.
   - Feature search evidence should appear as attribute query_facet facts.
   - Hidden-target evidence should appear as hidden_target request type plus lyric/title/era/popularity facts.

5. Temporal check:
   - hard release_date only for literal eligibility: only, released before/after/between, nothing newer/older.
   - decade/era/vibe language is style_era or reference_era, soft, apply_as_filter=false.

If two labels are plausible, choose the one that is safest for candidate
generation: protect exact named targets, suppress rejected entities, and avoid
using satisfied/history entities as retrieval seeds.
"""


SYSTEM = current.SYSTEM + DECISION_RUBRIC
FEW_SHOT_EXAMPLES = current.FEW_SHOT_EXAMPLES
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
