"""Sidecar constraint features for the reranker (no re-extraction needed).

Streams the devset trace for per-turn resolver rejection lists + played
tracks, joins against the existing feature parquet's (session, turn, track)
triples, and emits four EXACT constraint features:

  is_played_track          candidate already played in this session
  rejected_artist_exact    candidate's artist in resolver rejected_artist_ids
  rejected_track_exact     candidate in resolver rejected_track_ids
  violates_new_artist      same-artist-as-session while state targets new artists

These are modeling features (paired with monotone constraints in the trainer),
not dataset-specific filters — the direction "don't promote explicitly
rejected/played items" is principled for any recommender.
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

from build_features import constraint_feature_row  # noqa: E402
from catalog_utils import catalog_artist_ids  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace-glob", required=True,
                    help="e.g. 'exp/inference/devset/*shard_*_trace.jsonl'")
    ap.add_argument("--features", default="exp/analysis/rerank/v10/features")
    ap.add_argument("--db-uri", required=True)
    ap.add_argument("--out", default="exp/analysis/rerank/v10/constraint_features.parquet")
    args = ap.parse_args()

    print("loading candidate triples ...", flush=True)
    tbl = pds.dataset(args.features).to_table(
        columns=["session_id", "turn_number", "track_id", "same_artist_session",
                 "target_artist_mode"]).to_pydict()

    by_turn: dict[tuple[str, int], list[int]] = defaultdict(list)
    for i, (sid, tn) in enumerate(zip(tbl["session_id"], tbl["turn_number"])):
        by_turn[(str(sid), int(tn))].append(i)
    n = len(tbl["track_id"])
    print(f"  {n:,} rows, {len(by_turn):,} turns", flush=True)

    print("loading catalog scalars (artist ids only) ...", flush=True)
    t = catalog_artist_ids(args.db_uri)
    artists_of = {str(tid): tuple(str(a) for a in (aids or []))
                  for tid, aids in zip(t["track_id"], t["artist_id"])}

    print("streaming trace for resolver state ...", flush=True)
    turn_info: dict[tuple[str, int], dict] = {}
    for path in sorted(glob.glob(args.trace_glob)):
        with open(path) as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = (str(row["session_id"]), int(row["turn_number"]))
                if key not in by_turn:
                    continue
                res = row["trace"].get("resolver") or {}
                turn_info[key] = {
                    "played": frozenset(str(x) for x in res.get("played_track_ids") or []),
                    "rej_artists": frozenset(str(x) for x in res.get("rejected_artist_ids") or []),
                    "rej_tracks": frozenset(str(x) for x in res.get("rejected_track_ids") or []),
                }
    print(f"  matched {len(turn_info):,}/{len(by_turn):,} turns", flush=True)

    is_played = np.zeros(n, dtype=np.float32)
    rej_artist = np.zeros(n, dtype=np.float32)
    rej_track = np.zeros(n, dtype=np.float32)
    viol_new = np.zeros(n, dtype=np.float32)
    tids = tbl["track_id"]
    same_art = tbl["same_artist_session"]
    tam = tbl["target_artist_mode"]
    for key, idxs in by_turn.items():
        info = turn_info.get(key)
        if info is None:
            continue
        for i in idxs:
            tid = str(tids[i])
            feats = constraint_feature_row(
                tid, artists_of.get(tid, ()),
                played=info["played"], rejected_tracks=info["rej_tracks"],
                rejected_artists=info["rej_artists"],
                target_artist_mode=tam[i], same_artist_session=same_art[i])
            is_played[i] = feats["is_played_track"]
            rej_track[i] = feats["rejected_track_exact"]
            rej_artist[i] = feats["rejected_artist_exact"]
            viol_new[i] = feats["violates_new_artist"]

    out = pd.DataFrame({
        "session_id": [str(x) for x in tbl["session_id"]],
        "turn_number": tbl["turn_number"],
        "track_id": [str(x) for x in tids],
        "is_played_track": is_played,
        "rejected_artist_exact": rej_artist,
        "rejected_track_exact": rej_track,
        "violates_new_artist": viol_new,
    })
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out)
    for c in ["is_played_track", "rejected_artist_exact", "rejected_track_exact", "violates_new_artist"]:
        print(f"  {c}: rate={out[c].mean():.4f}")
    print(f"wrote {len(out):,} rows -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
