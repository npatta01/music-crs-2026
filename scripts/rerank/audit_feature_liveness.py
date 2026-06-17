"""Reranker pivot-signal liveness audit (read-only, local).

Confirms — on real saved traces — that the pivot-away signals are dead, and sizes
how much the fixes would unlock. Doubles as a before/after harness for the
_abandoned_sets fix (features_v9.py) and the label-weight artist fix
(build_label_weights.py).

Checks:
  A. Format of resolver.rejected_artist_ids / anchor_artist_ids (UUID vs name).
  B. track_feedback role + sentiment distribution.
  C. abandoned-artist set: CURRENT logic (broken: UUID->catalog_tag_key, and
     fb.get("sentiment")) vs FIXED logic (resolve UUID->artist name-key + treat
     prior satisfied/accepted artists as abandoned on a pivot). Reports how many
     turns each produces a non-empty set, and the pivot subset.
  D. label-weight artist downweight: CURRENT intersection (GT name-keys vs
     catalog_tag_key(next-turn rejected UUID) -> ~0 hits) vs FIXED (resolve the
     UUID first).

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
_NEG = ("negative", "reject", "dislike", "bad")
_SATISFIED_ROLES = {"satisfied", "accepted"}


def _is_pivot(mode: str) -> bool:
    return "new" in mode or "different" in mode


def main():
    from mcrs.qu_modules.tag_resolver import catalog_tag_key

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
    aid_to_key: dict[str, str] = {}       # artist UUID -> artist name-key
    trk_artist_keys: dict[str, frozenset] = {}  # track_id -> {artist name-keys}
    for tid, aids, anames in zip(t["track_id"], t["artist_id"], t["artist_name"]):
        aids = [str(a) for a in (aids or [])]
        anames = [str(a) for a in (anames or [])]
        trk_artist_keys[str(tid)] = frozenset(catalog_tag_key(a) for a in anames) - {""}
        for a, nm in zip(aids, anames):
            k = catalog_tag_key(nm)
            if k:
                aid_to_key[a] = k
    print(f"  {len(trk_artist_keys):,} tracks, {len(aid_to_key):,} artist ids", flush=True)

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
                "mode": str(es.get("target_artist_mode") or ""),
                "rejected_artist_ids": ra,
                "feedback": [(str(f.get("track_id")), str(f.get("role") or ""),
                              str(f.get("sentiment") or f.get("feedback") or "").lower())
                             for f in fb],
            }
            n += 1
            if args.limit and n >= args.limit:
                break
        if args.limit and n >= args.limit:
            break

    # C. abandoned-artist set, current (broken) vs fixed
    cur_nonempty = fix_nonempty = fix_pivot_nonempty = pivot_turns = 0
    for (sid, tn), info in turns.items():
        mode, ra, fb = info["mode"], info["rejected_artist_ids"], info["feedback"]
        pivot = _is_pivot(mode)
        pivot_turns += pivot
        # CURRENT: catalog_tag_key on UUIDs (never a name-key) + fb negative via wrong key
        cur = {catalog_tag_key(a) for a in ra} - {""}
        cur |= {k for tid, role, sent in fb if any(w in sent for w in _NEG)
                for k in trk_artist_keys.get(tid, ())}
        # whether any of those keys could match a real artist name-key
        cur_match = cur & set(aid_to_key.values())
        if cur_match:
            cur_nonempty += 1
        # FIXED: resolve UUID->name-key; on pivot, add prior satisfied/accepted artists
        fix = {aid_to_key[a] for a in ra if a in aid_to_key}
        if pivot:
            for tid, role, sent in fb:
                if role in _SATISFIED_ROLES:
                    fix |= trk_artist_keys.get(tid, frozenset())
        if fix:
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
        gt_keys = trk_artist_keys.get(gt, frozenset())
        if not gt_keys:
            continue
        cur_rej = {catalog_tag_key(a) for a in nxt["rejected_artist_ids"]} - {""}  # UUID-keys
        fix_rej = {aid_to_key[a] for a in nxt["rejected_artist_ids"] if a in aid_to_key}
        if gt_keys & cur_rej:
            cur_hits += 1
        if gt_keys & fix_rej:
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
