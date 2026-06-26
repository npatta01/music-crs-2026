"""Goal-free v_struct_pt query construction — the EXACT renderer the b1 4B model
was trained on. Kept dependency-free (no `modal`) so the serving path (b1_live)
can import it without pulling Modal into the reranker process.

Mirrors scripts/rerank/modal_build_data.py:{short_track,prev_track_str,build_q}
verbatim; tests/test_b1_query_parity asserts they stay identical.
"""
from __future__ import annotations
import re


def short_track(doc: str) -> str:
    # "artist — title" from "Music track: artist — title (year) | tags...": drop tags/known-for
    # and a TRAILING (YYYY) only, so titles containing "(...)" are preserved.
    if not doc:
        return ""
    s = doc.split(" | ")[0].replace("Music track: ", "", 1)
    return re.sub(r"\s*\(\d{4}\)\s*$", "", s).strip()


def prev_track_str(played_sid: dict, tn: int, doc_by_tid: dict, exclude_tid=None) -> str:
    """Most-recent previously-played track rendered as text. Never returns the GT track
    (exclude_tid) — a code-enforced leak guard (a no-op on current data: the GT is never
    replayed at an earlier turn)."""
    for k in range(tn - 1, 0, -1):
        if played_sid.get(k):
            tid = played_sid[k][-1]
            if tid and tid != exclude_tid:
                return short_track(doc_by_tid.get(tid, ""))
    return ""


def build_q(variant: str, prev: str, now: str, pt: str) -> str:
    """GOAL-FREE query renderer (no [goal]/<|goal|> anywhere). Returns '' iff body is empty."""
    turns = " / ".join(t for t in (prev, now) if t)
    if variant == "baseline":
        return ("[msg] " + turns).strip() if turns else ""
    if variant in ("v_struct", "v_struct_pt"):
        s = ""
        if prev:
            s += f"[prev] {prev}"
        if now:
            s += (" " if s else "") + f"[now] {now}"
        if variant == "v_struct_pt" and pt:
            s += (" " if s else "") + f"[prev_track] {pt}"
        return s.strip()
    if variant == "v_tok":
        s = ""
        if prev:
            s += f"<|prev|> {prev}"
        if now:
            s += (" " if s else "") + f"<|now|> {now}"
        return s.strip()
    raise ValueError(f"unknown variant {variant!r}")
