"""Compute retrieval metrics for given tids ON Modal, reading prediction jsons +
ground truth straight from the results volume — sidesteps the slow/degraded
local volume download. Mirrors the evaluator's single-relevant-item metrics but
ungated (computes @k even with shallow pools).

Usage:  modal run experiments/analysis/extractor_prompt_v2/scripts/score_on_modal.py --tids "a,b"
"""
from __future__ import annotations
import json, math
from pathlib import Path
import modal

results_vol = modal.Volume.from_name("music-crs-results", create_if_missing=False)
image = modal.Image.debian_slim(python_version="3.11")
app = modal.App("score-on-modal")


@app.function(image=image, volumes={"/data": results_vol}, timeout=900)
def score(tids: list[str]) -> dict:
    gt_path = Path("/data/ground_truth/devset.json")
    gt = {(r["session_id"], r["turn_number"]): r["ground_truth_track_id"]
          for r in json.load(gt_path.open())}
    out = {}
    for tid in tids:
        p = Path(f"/data/inference/devset/{tid}.json")
        if not p.exists():
            out[tid] = {"error": "predictions not found on volume"}
            continue
        preds = {(r["session_id"], r["turn_number"]): (r.get("predicted_track_ids") or [])
                 for r in json.load(p.open())}
        keys = [k for k in preds if k in gt]
        R = [(preds[k].index(gt[k]) + 1) if gt[k] in preds[k] else None for k in keys]
        found = [r for r in R if r]
        def hit(k): return sum(1 for r in R if r and r <= k) / len(R)
        def ndcg(k): return sum(1 / math.log2(r + 1) for r in R if r and r <= k) / len(R)
        n_empty_pool = sum(1 for k in keys if len(preds[k]) == 0)
        out[tid] = {
            "n_turns": len(keys),
            "NDCG@20": round(ndcg(20), 4),
            "Hit@20": round(hit(20), 4),
            "Hit@100": round(hit(100), 4),
            "Hit@1000": round(hit(1000), 4),
            "MRR": round(sum(1 / r for r in found) / len(R), 4) if R else 0,
            "n_empty_or_miss": sum(1 for r in R if r is None),
            "n_empty_pool": n_empty_pool,   # extractor/compiler produced 0 candidates
        }
    return out


@app.local_entrypoint()
def main(tids: str):
    res = score.remote([t.strip() for t in tids.split(",") if t.strip()])
    print(json.dumps(res, indent=2))
