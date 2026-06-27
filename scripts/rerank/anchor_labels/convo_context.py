"""Reconstruct the FULL multi-turn conversation for a (session_id, turn) so the judges see the
whole escalation history — not the single truncated `earlier:` line the first pass used.

The first labeling pass fed judges a `request` capped at ~one clipped prior turn, which hid the
strongest anchoring cue (a listener asking for a DIFFERENT artist repeatedly across turns). This
rebuilds the request from the raw TalkPlayData conversation, untruncated, with played tracks marked.
"""
from __future__ import annotations
import json


def load_index(split="train"):
    from datasets import load_dataset
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split=split)
    return {r["session_id"]: r for r in ds}


def load_docmap(path):
    doc = {}
    for line in open(path):
        d = json.loads(line)
        doc[d["track_id"]] = d
    return doc


def track_str(tid, doc):
    d = doc.get(tid)
    if not d:
        return f"[unknown track {tid[:8]}]"
    s = d.get("doc", "")
    s = s.replace("Music track: ", "").split(" | tags")[0].strip()
    return s or d.get("artist", "?")


def build_full_request(sid, tn, sid2row, doc, max_turns=8):
    """Full conversation up to (and including) the user's current ask at turn `tn`.
    The candidate track = music played at turn `tn`, so it is EXCLUDED here (never shown to the judge).
    `just_played` = the music at turn tn-1, marked explicitly for the anchoring judge.

    Assistant replies are STRIPPED (they assert the track is a good fit -> would bias the content
    judge); the neutral `[system played: ...]` markers are kept, which still expose anchoring on their
    own (a repeated same-artist marker across turns is the tell)."""
    conv = sid2row[sid]["conversations"]
    lines = []          # (turn_number, text)
    just_played = None
    for t in conv:
        k = t["turn_number"]
        if k > tn:
            break
        if k == tn and t["role"] in ("music", "assistant"):
            break       # stop at the current user ask; candidate + its response are not shown
        role = t["role"]
        if role == "user":
            tag = " (current request)" if k == tn else ""
            lines.append((k, f"USER{tag}: {t['content'].strip()}"))
        elif role == "music":
            ts = track_str(t["content"], doc)
            just_played = ts
            lines.append((k, f"  [system played: {ts}]"))
        # assistant replies intentionally omitted (see docstring)
    if max_turns:
        keep = sorted({k for k, _ in lines})[-max_turns:]
        lines = [(k, s) for k, s in lines if k in keep]
    body = "\n".join(s for _, s in lines)
    jp = f"\n\njust-played track (immediately before the candidate): {just_played}" if just_played else ""
    return f"conversation so far (most recent message last):\n{body}{jp}"


def _norm_artist(a):
    return (a or "").strip().casefold()


def candidate_tid(sid, tn, sid2row):
    """track_id played at turn `tn` (the candidate being judged)."""
    for t in sid2row[sid]["conversations"]:
        if t["turn_number"] == tn and t["role"] == "music":
            return t["content"]
    return None


def prev_artist(sid, tn, sid2row, doc):
    """Artist of the most recent music turn BEFORE turn `tn` (the just-played artist)."""
    last = None
    for t in sid2row[sid]["conversations"]:
        if t["turn_number"] >= tn:
            break
        if t["role"] == "music":
            d = doc.get(t["content"])
            if d:
                last = d.get("artist")
    return last


def same_artist(sid, tn, sid2row, doc):
    """Deterministic yardstick: is the candidate (music@tn) by the SAME artist as the just-played
    track (most recent music turn before tn)? Exact (case-folded) artist match. Replaces the
    `same_artist` field that the deprecated truncated sheet carried."""
    cand = candidate_tid(sid, tn, sid2row)
    cd = doc.get(cand) if cand else None
    if not cd:
        return False
    pa = prev_artist(sid, tn, sid2row, doc)
    return pa is not None and _norm_artist(cd.get("artist")) == _norm_artist(pa)
