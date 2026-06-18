"""State-conditioned graded relevance labels for reranker training (train-time only).

Replaces the binary single-positive label (`int(track == ground_truth)`) with a
graded, conversation-state-aware target. Per candidate row in a (session, turn)
group, evaluated top-down (first match wins):

  grade 3  the ground-truth track (GT)
  grade 2  future-accepted: GT of a LATER turn in the session, or a later
           positively-rated feedback track (minus tracks already heard before
           this turn, minus GT itself)
  -- hard-negative FLOOR (grade stays 0, per-row weight raised to --w-neg):
       * pivot-to-new AND same-artist-as-abandoned (the confirmed over-anchor), or
       * candidate matches a current-turn explicit rejection (rejected track id,
         or candidate artist id in resolver rejected_artist_ids)
  grade 1  state-consistent catalog neighbor of GT (artist + shared tags only),
           with the direction GATED on intent:
             continuation/refinement -> same-artist-as-GT OR >=K shared tags
             pivot-to-new            -> >=K shared tags with GT (the new direction)
  grade 0  everything else

`pivot_to_new` := intent_mode == "pivot" (or target_artist_mode in new/different)
AND the GT artist is NOT in the abandoned set — i.e. GT is verified to be a *new*
artist. So the same-artist push-down never fires when over-anchoring is correct
(GT == the pivoted-away artist), and a later-accepted track (grade 2) is never
floored because future-accepted is checked first.

Parity: the abandoned set is computed with `features_v9._abandoned_sets` and the
artist/tag keys are built with the same `catalog_tag_key` normalization the model
features use, so `same_artist_as_abandoned` here matches the served feature.

Output: parquet (session_id, turn_number, track_id, grade, neg_weight). Never a
feature — consumed by train_v9 as the LightGBM label + a sample-weight multiplier.

  python scripts/rerank/build_label_grades.py \
      --trace-glob "exp/inference/devset/state_ranker_v10_rrf_devset*shard_*_trace.jsonl" \
      --features exp/analysis/rerank/v10/features \
      --db-uri <lancedb_uri> \
      --out exp/analysis/rerank/v10/label_grades.parquet
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as pds

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcrs.qu_modules.tag_resolver import catalog_tag_key  # noqa: E402
from build_features import feature_trace_view  # noqa: E402
from features_v9 import _abandoned_sets  # noqa: E402

EMPTY: frozenset = frozenset()


class _MetaCat:
    """Minimal shim exposing `.meta[tid]['artist_name_keys']` for _abandoned_sets."""

    def __init__(self, artist_keys_of: dict[str, frozenset]):
        self.meta = {t: {"artist_name_keys": a} for t, a in artist_keys_of.items()}


def _wants_new(tam: str) -> bool:
    return "new" in tam or "different" in tam


def _positive_fb_tracks(state: dict) -> set[str]:
    """Track ids the user reacted to positively (accepted/satisfied/seed / +1)."""
    out: set[str] = set()
    for fb in (state.get("track_feedback") or []):
        tid = str(fb.get("track_id") or "")
        if not tid:
            continue
        role = str(fb.get("role") or "").lower()
        sent = str(fb.get("sentiment") or fb.get("feedback") or "").lower()
        sent_num = fb.get("overall_sentiment")
        if (role in ("accepted", "satisfied", "seed")
                or any(w in sent for w in ("positive", "like", "love", "accept"))
                or sent_num in (1, "1")):
            out.add(tid)
    return out


def grade_candidate(tid, info, artist_keys_of, tag_keys_of, artists_of, k, w_neg,
                    use_future=True, use_neighbor=True):
    """(grade, neg_weight) for one candidate. Rules (top-down) in the module docstring.

    `info` is the per-turn context built in main(): gt, gt_art, gt_tags,
    pivot_to_new, aband, future, rej_tracks, rej_artist_ids.

    Ablation toggles: `use_future` (grade-2 future-accepted) and `use_neighbor`
    (grade-1 catalog neighbor). Disabling both leaves binary positives (GT=3) plus
    the gated hard-negative weighting — the metric-safe "option A".
    """
    if tid == info["gt"]:
        return 3, 1.0
    if use_future and tid in info["future"]:
        return 2, 1.0
    c_art = artist_keys_of.get(tid, EMPTY)
    same_aband = bool(c_art & info["aband"])
    rej_artist_ids = info["rej_artist_ids"]
    is_rej = (tid in info["rej_tracks"]) or (
        bool(rej_artist_ids) and any(a in rej_artist_ids for a in artists_of.get(tid, ())))
    if (info["pivot_to_new"] and same_aband) or is_rej:
        return 0, w_neg  # confirmed hard negative: floor grade, raise weight
    if not use_neighbor:
        return 0, 1.0
    c_tags = tag_keys_of.get(tid, EMPTY)
    if info["pivot_to_new"]:
        return (1 if len(c_tags & info["gt_tags"]) >= k else 0), 1.0
    if (c_art & info["gt_art"]) or len(c_tags & info["gt_tags"]) >= k:
        return 1, 1.0
    return 0, 1.0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace-glob", required=True,
                    help="e.g. 'exp/inference/devset/*shard_*_trace.jsonl'")
    ap.add_argument("--features", default="exp/analysis/rerank/v10/features")
    ap.add_argument("--ground-truth", default="exp/ground_truth/devset.json")
    ap.add_argument("--db-uri", required=True)
    ap.add_argument("--table-name", default="music_track_catalog")
    ap.add_argument("--out", default="exp/analysis/rerank/v10/label_grades.parquet")
    ap.add_argument("--tag-overlap-k", type=int, default=6,
                    help="Min shared tags with GT for a grade-1 neighbor. Tags are "
                         "coarse (genre-level); measured on devset, K=2 tags ~42%% of "
                         "candidates while K=6 ~12%% — keep grade-1 a selective minority.")
    ap.add_argument("--w-neg", type=float, default=3.0,
                    help="Sample-weight multiplier on confirmed hard negatives.")
    ap.add_argument("--disable-future", action="store_true",
                    help="Ablation: drop grade-2 future-accepted positives.")
    ap.add_argument("--disable-neighbor", action="store_true",
                    help="Ablation: drop grade-1 catalog neighbors. With both disabled, "
                         "labels are binary positives (GT) + gated hard-negative weights.")
    args = ap.parse_args()
    K = args.tag_overlap_k

    print("loading candidate triples ...", flush=True)
    tbl = pds.dataset(args.features).to_table(
        columns=["session_id", "turn_number", "track_id"]).to_pydict()
    by_turn: dict[tuple[str, int], list[int]] = defaultdict(list)
    for i, (sid, tn) in enumerate(zip(tbl["session_id"], tbl["turn_number"])):
        by_turn[(str(sid), int(tn))].append(i)
    tids = [str(x) for x in tbl["track_id"]]
    n = len(tids)
    print(f"  {n:,} rows, {len(by_turn):,} turns", flush=True)

    print("loading catalog scalars (artist ids/names + tags) ...", flush=True)
    import lancedb
    t = lancedb.connect(args.db_uri).open_table(args.table_name).to_lance().to_table(
        columns=["track_id", "artist_id", "artist_name", "tag_list"]).to_pydict()
    artists_of: dict[str, tuple] = {}      # artist *ids* (for explicit-rejection match)
    artist_keys_of: dict[str, frozenset] = {}  # artist name-keys (abandoned / neighbor)
    tag_keys_of: dict[str, frozenset] = {}
    for tid, aids, a_raw, tags in zip(
            t["track_id"], t["artist_id"], t["artist_name"], t["tag_list"]):
        tid = str(tid)
        artists_of[tid] = tuple(str(a) for a in (aids or []))
        if not isinstance(a_raw, (list, tuple, np.ndarray)):
            a_raw = [a_raw]
        artist_keys_of[tid] = frozenset(
            k for k in (catalog_tag_key(str(a or "")) for a in a_raw) if k)
        tag_keys_of[tid] = frozenset(catalog_tag_key(str(x)) for x in (tags or [])) - {""}
    shim = _MetaCat(artist_keys_of)

    gt_map = {(str(r["session_id"]), int(r["turn_number"])): str(r["ground_truth_track_id"])
              for r in json.load(open(args.ground_truth))}
    session_turns: dict[str, list[int]] = defaultdict(list)
    for (sid, tn) in gt_map:
        session_turns[sid].append(tn)

    print("streaming trace for per-turn state ...", flush=True)
    turn_raw: dict[tuple[str, int], dict] = {}
    pos_fb: dict[tuple[str, int], set] = {}
    for path in sorted(glob.glob(args.trace_glob)):
        with open(path) as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = (str(row["session_id"]), int(row["turn_number"]))
                tv = feature_trace_view(row.get("trace") or {})
                state = tv.get("state") or {}
                res = tv.get("resolver") or {}
                turn_raw[key] = {
                    "intent": str(tv.get("intent_mode") or ""),
                    "tam": str(state.get("target_artist_mode") or ""),
                    "state": state,
                    "resolver": res,
                    "played": frozenset(str(x) for x in (res.get("played_track_ids") or [])),
                    "rej_tracks": frozenset(str(x) for x in (res.get("rejected_track_ids") or [])),
                    "rej_artist_ids": frozenset(str(x) for x in (res.get("rejected_artist_ids") or [])),
                }
                pos_fb[key] = _positive_fb_tracks(state)
    print(f"  matched {len(set(turn_raw) & set(by_turn)):,}/{len(by_turn):,} turns", flush=True)

    # per-turn precomputed grading context
    info_by_turn: dict[tuple[str, int], dict] = {}
    n_pivot_to_new = 0
    for key in by_turn:
        raw = turn_raw.get(key)
        gt = gt_map.get(key)
        if raw is None or gt is None:
            continue
        aband_artists, _aband_tags = _abandoned_sets(raw["state"], raw["resolver"], shim)
        gt_art = artist_keys_of.get(gt, EMPTY)
        is_pivot = (raw["intent"] == "pivot") or _wants_new(raw["tam"])
        pivot_to_new = is_pivot and not (gt_art & aband_artists)
        n_pivot_to_new += int(pivot_to_new)
        sid, tn = key
        future: set[str] = set()
        for tp in session_turns.get(sid, ()):
            if tp <= tn:
                continue
            g = gt_map.get((sid, tp))
            if g:
                future.add(g)
            future |= pos_fb.get((sid, tp), set())
        future -= raw["played"]
        future.discard(gt)
        info_by_turn[key] = {
            "gt": gt,
            "gt_art": gt_art,
            "gt_tags": tag_keys_of.get(gt, EMPTY),
            "pivot_to_new": pivot_to_new,
            "aband": aband_artists,
            "future": future,
            "rej_tracks": raw["rej_tracks"],
            "rej_artist_ids": raw["rej_artist_ids"],
        }

    grade = np.zeros(n, dtype=np.int8)
    neg_weight = np.ones(n, dtype=np.float32)
    for key, idxs in by_turn.items():
        info = info_by_turn.get(key)
        if info is None:
            continue
        for i in idxs:
            g, nw = grade_candidate(tids[i], info, artist_keys_of, tag_keys_of,
                                    artists_of, K, args.w_neg,
                                    use_future=not args.disable_future,
                                    use_neighbor=not args.disable_neighbor)
            grade[i] = g
            if nw != 1.0:
                neg_weight[i] = nw

    out = pd.DataFrame({
        "session_id": [str(x) for x in tbl["session_id"]],
        "turn_number": tbl["turn_number"],
        "track_id": tids,
        "grade": grade,
        "neg_weight": neg_weight,
    })
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out)
    dist = pd.Series(grade).value_counts().sort_index().to_dict()
    print(f"wrote {len(out):,} rows -> {args.out}", flush=True)
    print(f"  grade distribution: {dist}", flush=True)
    print(f"  neg_weight>1: {int((neg_weight > 1).sum()):,} rows "
          f"({(neg_weight > 1).mean():.4f})", flush=True)
    print(f"  pivot_to_new turns: {n_pivot_to_new:,}/{len(by_turn):,}", flush=True)


if __name__ == "__main__":
    main()
