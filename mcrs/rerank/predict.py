"""Write standard predictions JSON from reranker scores (for the official evaluator).

Turns an OOF (or single-model) score table into the same ``[{session_id, user_id, turn_number,
predicted_track_ids, predicted_response}]`` format the inference pipeline emits, so
``evaluator/evaluate_devset.py`` scores the reranker exactly like any other run -- the reranker
acting as the final ranker over the cached branch-pool retrieval, replacing RRF.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def write_predictions(
    oof_path: str | Path,
    ground_truth_path: str | Path,
    out_path: str | Path,
    top_k: int = 1000,
) -> dict[str, Any]:
    oof = pd.read_parquet(oof_path)
    gt_rows = json.load(open(ground_truth_path))
    user_of = {(r["session_id"], int(r["turn_number"])): r.get("user_id") for r in gt_rows}

    ordered = oof.sort_values(["session_id", "turn_number", "score"],
                              ascending=[True, True, False], kind="stable")
    preds = []
    for (sid, turn), sub in ordered.groupby(["session_id", "turn_number"], sort=False):
        preds.append({
            "session_id": sid,
            "user_id": user_of.get((sid, int(turn))),
            "turn_number": int(turn),
            "predicted_track_ids": sub["track_id"].head(top_k).tolist(),
            "predicted_response": "",
        })
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        json.dump(preds, fh)
    return {"n_turns": len(preds), "out": str(out)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Write predictions JSON from reranker OOF scores.")
    p.add_argument("--oof", required=True)
    p.add_argument("--ground-truth", default="evaluator/exp/ground_truth/devset.json")
    p.add_argument("--out", required=True)
    p.add_argument("--top-k", type=int, default=1000)
    args = p.parse_args(argv)
    print(json.dumps(write_predictions(args.oof, args.ground_truth, args.out, args.top_k), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
