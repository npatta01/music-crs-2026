"""Compact structured-state context for state-conditioned response generation.

Reads the per-turn `ConversationStateV0Plus` saved in the devset trace
(record["trace"]["state"]) and renders a short context block, as an alternative
to feeding the raw multi-turn transcript.
"""
from __future__ import annotations

import json


def _track_label(track_id: str, lookup) -> str:
    # "title: X | artist: Y | album: Z | tags: ..." -> "title: X | artist: Y"
    s = lookup.id_to_metadata(track_id)
    return s.split(" | tags:")[0].split(" | album:")[0]


def format_state_block(state: dict | None, lookup) -> str:
    if not state:
        return "[LISTENER CONTEXT]\n(unavailable)"
    lines = ["[LISTENER CONTEXT]"]
    ti = state.get("turn_intent")
    if ti:
        lines.append(f"Current request: {ti}")

    ents = state.get("mentioned_entities") or []
    liked = [e["value"] for e in ents if (e.get("sentiment") or 0) > 0]
    disliked = [e["value"] for e in ents if (e.get("sentiment") or 0) < 0]

    fb = state.get("track_feedback") or []
    accepted = [_track_label(t["track_id"], lookup) for t in fb if t.get("role") == "accepted"]
    rejected = [_track_label(t["track_id"], lookup) for t in fb if t.get("role") == "rejected"]
    liked += accepted
    disliked += rejected

    if liked:
        lines.append("Liked / wants: " + ", ".join(dict.fromkeys(liked)))
    if disliked:
        lines.append("Disliked / avoid: " + ", ".join(dict.fromkeys(disliked)))

    er = state.get("explicit_rejections") or []
    if er:
        lines.append("Explicit rejections: " + ", ".join(f"{x.get('kind')}:{x.get('value')}" for x in er))

    yr = state.get("release_year_range")
    if yr and (yr.get("start") or yr.get("end")):
        lines.append(f"Release year range: {yr.get('start')}-{yr.get('end')}")

    hf = state.get("hard_filters") or []
    if hf:
        lines.append("Filters: " + json.dumps(hf, default=str))

    lt = state.get("lyrical_theme")
    if lt:
        lines.append(f"Lyrical theme: {lt}")

    return "\n".join(lines)


def load_states(trace_path: str, session_ids) -> dict:
    """Stream the (large) trace jsonl; return {(session_id, turn_number): state_dict}
    for the given session_ids. Uses a cheap substring prefilter before json.loads."""
    sset = set(session_ids)
    out = {}
    with open(trace_path) as fh:
        for line in fh:
            if not any(s in line for s in sset):  # avoid parsing 5GB of unrelated lines
                continue
            r = json.loads(line)
            sid = r.get("session_id")
            if sid not in sset:
                continue
            tr = r.get("trace") or {}
            state = tr.get("state") if isinstance(tr, dict) else None
            out[(sid, r.get("turn_number"))] = state
    return out
