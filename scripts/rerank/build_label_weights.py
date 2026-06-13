"""Per-turn label-quality weights for reranker training (train-time only).

The generator's GT is a real-session sibling pick that sometimes does not fit
the request (measured: 62% clear / 26% loose / 11% none) — and the data tells
us which: the NEXT turn's goal_progress_assessment judges the turn-t
recommendation, and the NEXT turn's extracted rejections name it directly.

Weight rules (multiplicative, floor 0.2):
  x0.3  next turn's goal_progress_assessment == DOES_NOT_MOVE_TOWARD_GOAL
  x0.3  next turn's resolver rejected_track_ids contains the turn-t GT
  x0.6  next turn's rejected artists include the GT's artist (soft: the
        generator is known to recycle rejected artists)

Output: parquet (session_id, turn_number, weight). Never used as a feature.

  python scripts/rerank/build_label_weights.py \
      --trace-glob "exp/inference/devset/v0plus_compiler_pruned_resolved_tags_devset.*shard_*_trace.jsonl" \
      --out exp/analysis/rerank/label_weights_v9.parquet
"""

from __future__ import annotations

import argparse
import ast
import glob
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcrs.qu_modules.tag_resolver import catalog_tag_key  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace-glob", required=True)
    ap.add_argument("--ground-truth", default="exp/ground_truth/devset.json")
    ap.add_argument("--db-uri",
                    default="/Users/npatta01/data/projects/music-conversational-music-recomender-2026/cache/lancedb")
    ap.add_argument("--out", default="exp/analysis/rerank/label_weights_v9.parquet")
    args = ap.parse_args()

    gt_map = {(str(r["session_id"]), int(r["turn_number"])): str(r["ground_truth_track_id"])
              for r in json.load(open(args.ground_truth))}

    # GT artist name-keys from the catalog
    import lancedb
    cat = lancedb.connect(args.db_uri).open_table("music_track_catalog").to_pandas()
    artist_keys_of = {
        r.track_id: frozenset(catalog_tag_key(str(a)) for a in (r.artist_name if r.artist_name is not None else [])) - {""}
        for r in cat.itertuples()}

    # next-turn rejections from the trace (resolver block per turn)
    rej_tracks: dict[tuple, set] = {}
    rej_artist_keys: dict[tuple, set] = {}
    files = sorted(glob.glob(args.trace_glob))
    assert files, f"no trace files match {args.trace_glob}"
    for p in files:
        with open(p) as f:
            for line in f:
                r = json.loads(line)
                k = (str(r["session_id"]), int(r["turn_number"]))
                res = (r.get("trace") or {}).get("resolver") or {}
                rej_tracks[k] = {str(t) for t in (res.get("rejected_track_ids") or [])}
                rej_artist_keys[k] = {catalog_tag_key(str(a))
                                      for a in (res.get("rejected_artist_ids") or [])} - {""}

    # next-turn goal assessments from the conversations dataset
    from datasets import load_dataset
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    away: dict[tuple, bool] = {}
    for row in ds:
        sid = str(row["session_id"])
        g = row["goal_progress_assessments"]
        if isinstance(g, str):
            g = ast.literal_eval(g)
        for a in g:
            away[(sid, int(a["turn_number"]))] = (
                str(a.get("goal_progress_assessment")) == "DOES_NOT_MOVE_TOWARD_GOAL")

    rows, n_away, n_rt, n_ra = [], 0, 0, 0
    for (sid, tn), gt in gt_map.items():
        w = 1.0
        nxt = (sid, tn + 1)
        if away.get(nxt):
            w *= 0.3
            n_away += 1
        if gt in rej_tracks.get(nxt, ()):  # explicit next-turn rejection of the GT
            w *= 0.3
            n_rt += 1
        elif artist_keys_of.get(gt) and (artist_keys_of[gt] & rej_artist_keys.get(nxt, set())):
            w *= 0.6
            n_ra += 1
        rows.append({"session_id": sid, "turn_number": tn, "weight": max(w, 0.2)})

    df = pd.DataFrame(rows)
    df.to_parquet(args.out)
    print(f"wrote {len(df)} turn weights -> {args.out}")
    print(f"  away_from_goal x0.3: {n_away} | gt-track-rejected x0.3: {n_rt} | "
          f"gt-artist-rejected x0.6: {n_ra}")
    print(f"  weight distribution: {df.weight.value_counts().sort_index().to_dict()}")


if __name__ == "__main__":
    main()
