"""Reranker pivot-signal liveness audit (read-only, local).

Confirms — on real saved traces — that the pivot-away signals are dead, and sizes
how much the fixes would unlock. Doubles as a before/after harness for the
_abandoned_sets fix (features.py) and the label-weight artist fix
(build_label_weights.py).

Checks:
  A. Format of resolver.rejected_artist_ids / anchor_artist_ids (UUID vs name).
  B. track_feedback role + sentiment distribution.
  C. abandoned-artist set: CURRENT (original broken prod: UUID->catalog_tag_key,
     and fb.get("sentiment")) vs FIXED (the production _abandoned_sets, reused
     verbatim — matches by artist UUID, adds rejected/negative-feedback/pivot-
     satisfied artists). Reports non-empty turns + the pivot subset.
  D. label-weight artist downweight: CURRENT (GT name-keys vs
     catalog_tag_key(next-turn rejected UUID) -> ~0 hits) vs FIXED (GT artist
     UUIDs vs rejected artist UUIDs, directly).

Usage:
  python scripts/rerank/audit_feature_liveness.py \
    --trace-glob '.claude/worktrees/visual-route/exp/inference/devset/state_ranker_v10_lgbm_devset.run_20260616T032406Z-7333e0.shard_*_trace.jsonl'
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
# the OLD (broken) _abandoned_sets read these feedback keys, which never exist
# on TrackFeedback (it has overall_sentiment/role) — kept only to reproduce the
# pre-fix "0 firings" state in column C.
_NEG = ("negative", "reject", "dislike", "bad")


def _is_pivot(mode: str) -> bool:
    return "new" in mode or "different" in mode


class _ShimCat:
    """Minimal catalog exposing exactly what _abandoned_sets reads
    (cat.meta[tid]["artists"] = artist UUIDs), so the audit can call the REAL
    production function (no divergent re-implementation)."""

    def __init__(self, meta: dict):
        self.meta = meta


def main():
    from mcrs.qu_modules.tag_resolver import catalog_tag_key

    from features import _abandoned_sets  # the production logic, reused verbatim

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace-glob", required=True)
    ap.add_argument("--db-uri", default=str(PROJECT_ROOT / "cache/lancedb"))
    ap.add_argument("--table", default="music_track_catalog")
    ap.add_argument("--ground-truth", default=str(PROJECT_ROOT / "exp/ground_truth/devset.json"))
    ap.add_argument("--limit", type=int, default=0, help="max trace rows (0 = all)")
    args = ap.parse_args()

    print("loading catalog artist maps ...", flush=True)
    import lancedb
    t = (lancedb.connect(args.db_uri).open_table(args.table).to_lance()
         .to_table(columns=["track_id", "artist_id", "artist_name"]).to_pydict())
    trk_artist_ids: dict[str, frozenset] = {}   # track_id -> {artist UUIDs} (production)
    trk_artist_keys: dict[str, frozenset] = {}  # track_id -> {artist name-keys} (broken-demo)
    for tid, aids, anames in zip(t["track_id"], t["artist_id"], t["artist_name"]):
        trk_artist_ids[str(tid)] = frozenset(str(a) for a in (aids or []))
        trk_artist_keys[str(tid)] = frozenset(catalog_tag_key(str(a)) for a in (anames or [])) - {""}
    all_name_keys = set().union(*trk_artist_keys.values()) if trk_artist_keys else set()
    print(f"  {len(trk_artist_ids):,} tracks", flush=True)

    gt_map = {(str(r["session_id"]), int(r["turn_number"])): str(r["ground_truth_track_id"])
              for r in json.load(open(args.ground_truth))}

    files = sorted(glob.glob(args.trace_glob))
    assert files, f"no traces match {args.trace_glob}"

    # pass 1: collect per-turn fields needed for both the per-turn and next-turn checks
    turns: dict[tuple, dict] = {}
    n = 0
    fmt_uuid = fmt_other = 0
    role_hist: Counter = Counter()
    sent_hist: Counter = Counter()
    for fp in files:
        for line in open(fp):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            tr = row.get("trace") or row
            sid = str(row.get("session_id") or tr.get("session_id") or "")
            tn = int(row.get("turn_number") or tr.get("turn_number") or 0)
            res = tr.get("resolver") or {}
            es = tr.get("extracted_state") or tr.get("state") or {}
            ra = [str(x) for x in (res.get("rejected_artist_ids") or [])]
            for x in ra:
                if _UUID_RE.match(x):
                    fmt_uuid += 1
                else:
                    fmt_other += 1
            fb = es.get("track_feedback") or []
            for f in fb:
                role_hist[str(f.get("role"))] += 1
                sent_hist[f.get("overall_sentiment")] += 1
            turns[(sid, tn)] = {
                "es": es, "res": res,
                "mode": str(es.get("target_artist_mode") or ""),
                "rejected_artist_ids": ra,
            }
            n += 1
            if args.limit and n >= args.limit:
                break
        if args.limit and n >= args.limit:
            break

    # C. abandoned-artist set, current (original broken prod) vs fixed (production)
    # FIXED calls the REAL production _abandoned_sets (now id-based) so it can never
    # drift from features.
    shim = _ShimCat({tid: {"artists": ids} for tid, ids in trk_artist_ids.items()})
    cur_nonempty = fix_nonempty = fix_pivot_nonempty = pivot_turns = 0
    for (sid, tn), info in turns.items():
        es, res = info["es"], info["res"]
        pivot = _is_pivot(info["mode"])
        pivot_turns += pivot
        # CURRENT (original broken prod): catalog_tag_key on UUID rejected ids (never a
        # name-key) + negative feedback read via the OLD wrong keys (sentiment/feedback).
        cur = {catalog_tag_key(str(a)) for a in (res.get("rejected_artist_ids") or [])} - {""}
        for fb in (es.get("track_feedback") or []):
            sent = str(fb.get("sentiment") or fb.get("feedback") or "").lower()
            if any(w in sent for w in _NEG):
                cur |= trk_artist_keys.get(str(fb.get("track_id") or ""), frozenset())
        if cur & all_name_keys:  # any key that could actually match a candidate artist
            cur_nonempty += 1
        # FIXED: production logic, reused verbatim
        fix_artists, _fix_tags = _abandoned_sets(es, res, shim)
        if fix_artists:
            fix_nonempty += 1
            if pivot:
                fix_pivot_nonempty += 1

    # D. label-weight artist downweight: next-turn rejection of GT's artist
    cur_hits = fix_hits = eligible = 0
    for (sid, tn), gt in gt_map.items():
        nxt = turns.get((sid, tn + 1))
        if not nxt or not nxt["rejected_artist_ids"]:
            continue
        eligible += 1
        gt_ids = trk_artist_ids.get(gt, frozenset())
        if not gt_ids:
            continue
        # CURRENT (broken): GT name-keys vs catalog_tag_key(rejected UUID) -> never matches
        cur_rej = {catalog_tag_key(a) for a in nxt["rejected_artist_ids"]} - {""}
        if trk_artist_keys.get(gt, frozenset()) & cur_rej:
            cur_hits += 1
        # FIXED: GT artist UUIDs vs rejected artist UUIDs, directly
        if gt_ids & set(nxt["rejected_artist_ids"]):
            fix_hits += 1

    print("\n================ PIVOT-SIGNAL LIVENESS AUDIT ================")
    print(f"trace rows: {n:,}   pivot turns (mode∈new/different): {pivot_turns:,}")
    print(f"\nA. rejected_artist_ids format: UUID={fmt_uuid}  non-UUID={fmt_other}")
    print(f"B. track_feedback roles: {dict(role_hist)}")
    print(f"   track_feedback overall_sentiment: {dict(sent_hist)}")
    print(f"\nC. abandoned-artist set non-empty turns:")
    print(f"   CURRENT (broken): {cur_nonempty}   <- expect ~0 (dead feature)")
    print(f"   FIXED:            {fix_nonempty}   (of which pivot: {fix_pivot_nonempty})")
    print(f"\nD. label-weight artist downweight (next-turn rejects GT's artist):")
    print(f"   eligible turns (next-turn has rejected_artist_ids): {eligible}")
    print(f"   CURRENT hits: {cur_hits}   <- expect 0 (UUID vs name)")
    print(f"   FIXED hits:   {fix_hits}")
    print("============================================================")


if __name__ == "__main__":
    main()
