"""
Evaluate Music CRS predictions against ground truth.

Reads a predictions file from exp/inference/{split}/{tid}.json and writes
scores to exp/scores/{split}/{tid}.json.

Usage:
    python run_evaluate.py --tid llama1b_bm25_devset
    python run_evaluate.py --tid llama1b_bm25_devset --split devset --exp_dir ./exp
"""

import argparse
import json
import math
import os

import numpy as np
from datasets import load_dataset


def ndcg_at_k(predicted_ids, gt_id, k):
    if not gt_id or not predicted_ids:
        return 0.0
    for rank, tid in enumerate(predicted_ids[:k], start=1):
        if tid == gt_id:
            return 1.0 / math.log2(rank + 1)
    return 0.0


def main(args):
    pred_path = os.path.join(args.exp_dir, "inference", args.split, f"{args.tid}.json")
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"Predictions not found: {pred_path}")

    with open(pred_path) as f:
        raw = json.load(f)
    predictions = {(p["session_id"], p["turn_number"]): p["predicted_track_ids"] for p in raw}
    print(f"Loaded {len(raw):,} predictions from {pred_path}")

    hf_split = "test" if args.split == "devset" else args.split
    print(f"Loading ground truth ({hf_split} split)...")
    conv_ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split=hf_split)
    ground_truth = {
        (s["session_id"], t["turn_number"]): t["content"]
        for s in conv_ds
        for t in s["conversations"]
        if t["role"] == "music"
    }

    print("Loading track catalog...")
    tracks_ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks")
    total_tracks = len(tracks_ds)

    ndcg1_scores, ndcg10_scores, ndcg20_scores = [], [], []
    all_predicted_ids = set()

    for (sid, turn), ptids in predictions.items():
        gt = ground_truth.get((sid, turn))
        ndcg1_scores.append(ndcg_at_k(ptids, gt, 1))
        ndcg10_scores.append(ndcg_at_k(ptids, gt, 10))
        ndcg20_scores.append(ndcg_at_k(ptids, gt, 20))
        all_predicted_ids.update(ptids)

    scores = {
        "tid": args.tid,
        "split": args.split,
        "n_predictions": len(predictions),
        "NDCG@1": float(np.mean(ndcg1_scores)),
        "NDCG@10": float(np.mean(ndcg10_scores)),
        "NDCG@20": float(np.mean(ndcg20_scores)),
        "catalog_diversity": len(all_predicted_ids) / total_tracks,
    }

    scores_path = os.path.join(args.exp_dir, "scores", args.split, f"{args.tid}.json")
    os.makedirs(os.path.dirname(scores_path), exist_ok=True)
    with open(scores_path, "w") as f:
        json.dump(scores, f, indent=2)

    print(f"\n--- Scores for {args.tid} ({args.split}) ---")
    for k, v in scores.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
    print(f"\nScores saved to {scores_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Music CRS predictions.")
    parser.add_argument("--tid", type=str, required=True,
                        help="Task ID matching a predictions file (e.g. llama1b_bm25_devset)")
    parser.add_argument("--split", type=str, default="devset",
                        help="Dataset split: devset, blindset_A, ...")
    parser.add_argument("--exp_dir", type=str, default="exp",
                        help="Base directory for predictions and scores (default: ./exp)")
    args = parser.parse_args()
    main(args)
