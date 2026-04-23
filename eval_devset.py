"""
Offline evaluation for Music CRS devset predictions.

Reads predictions from `exp/inference/devset/{tid}.json`, pulls ground truth
from the HF dataset, and writes a comprehensive metrics report to
`exp/eval/devset/{tid}.json`. Also prints a grouped report to stdout.

The metrics are designed so that iterating on the devset is a reliable
proxy for the final leaderboard — they answer both "is the ground-truth
track retrieved at all?" (Recall@K) and "how well is it ranked?" (NDCG@K,
MRR).

Usage:
    python eval_devset.py --tid llama1b_bm25_devset

To get Recall@100 / NDCG@100 the predictions file must contain >=100
ids per turn. Devset configs ship with `retrieval_topk: 100`; older
prediction files with only 20 ids will still work — metrics at k>20
will just equal their @20 counterparts.
"""

import os
import json
import math
import argparse
from collections import defaultdict

import numpy as np


KS = [1, 5, 10, 20, 50, 100]


def ndcg_at_k(predicted, gt_id, k):
    """Binary-relevance NDCG@k with a single relevant doc (IDCG=1)."""
    for rank, tid in enumerate(predicted[:k], start=1):
        if tid == gt_id:
            return 1.0 / math.log2(rank + 1)
    return 0.0


def recall_at_k(predicted, gt_id, k):
    return 1 if gt_id in predicted[:k] else 0


def rank_of(predicted, gt_id):
    for rank, tid in enumerate(predicted, start=1):
        if tid == gt_id:
            return rank
    return None


def reciprocal_rank(predicted, gt_id, max_k=None):
    rank = rank_of(predicted if max_k is None else predicted[:max_k], gt_id)
    return 1.0 / rank if rank else 0.0


def distinct_n(texts, n):
    """Distinct-n: unique n-grams divided by total n-grams across all texts."""
    total = 0
    seen = set()
    for t in texts:
        tokens = t.split()
        for i in range(len(tokens) - n + 1):
            seen.add(tuple(tokens[i:i + n]))
            total += 1
    return len(seen) / total if total else 0.0


def load_ground_truth(dataset_name, split):
    from datasets import load_dataset
    ds = load_dataset(dataset_name, split=split)
    gt = {}
    for s in ds:
        for t in s["conversations"]:
            if t["role"] == "music":
                gt[(s["session_id"], t["turn_number"])] = t["content"]
    return gt


def evaluate(predictions, ground_truth, catalog_size):
    ndcg = {k: [] for k in KS}
    recall = {k: [] for k in KS}
    rr_all, rr_100 = [], []
    ranks_found = []
    per_turn = defaultdict(lambda: {"ndcg20": [], "recall20": [], "recall100": []})
    all_ids_20, all_ids_100 = set(), set()
    responses = []
    n_skipped = 0
    max_depth = 0

    for pred in predictions:
        key = (pred["session_id"], pred["turn_number"])
        ptids = pred.get("predicted_track_ids", [])
        max_depth = max(max_depth, len(ptids))
        responses.append(pred.get("predicted_response") or "")
        gt = ground_truth.get(key)
        if not gt:
            n_skipped += 1
            continue

        for k in KS:
            ndcg[k].append(ndcg_at_k(ptids, gt, k))
            recall[k].append(recall_at_k(ptids, gt, k))
        rr_all.append(reciprocal_rank(ptids, gt))
        rr_100.append(reciprocal_rank(ptids, gt, max_k=100))

        rank = rank_of(ptids, gt)
        if rank:
            ranks_found.append(rank)

        tn = pred["turn_number"]
        per_turn[tn]["ndcg20"].append(ndcg_at_k(ptids, gt, 20))
        per_turn[tn]["recall20"].append(recall_at_k(ptids, gt, 20))
        per_turn[tn]["recall100"].append(recall_at_k(ptids, gt, 100))

        all_ids_20.update(ptids[:20])
        all_ids_100.update(ptids[:100])

    n = len(rr_all)
    mean = lambda xs: float(np.mean(xs)) if xs else 0.0

    metrics = {
        "n_turns_evaluated": n,
        "n_turns_skipped_no_gt": n_skipped,
        "catalog_size": catalog_size,
        "max_prediction_depth": max_depth,
    }
    for k in KS:
        metrics[f"ndcg@{k}"] = mean(ndcg[k])
        metrics[f"recall@{k}"] = mean(recall[k])
    metrics["mrr"] = mean(rr_all)
    metrics["mrr@100"] = mean(rr_100)
    metrics["mean_rank_when_found"] = mean(ranks_found) if ranks_found else None
    metrics["median_rank_when_found"] = float(np.median(ranks_found)) if ranks_found else None
    metrics["pct_gt_not_in_top20"] = 1.0 - metrics["recall@20"]
    metrics["pct_gt_not_in_top100"] = 1.0 - metrics["recall@100"]
    metrics["catalog_diversity@20"] = len(all_ids_20) / catalog_size if catalog_size else 0.0
    metrics["catalog_diversity@100"] = len(all_ids_100) / catalog_size if catalog_size else 0.0
    metrics["lexical_distinct_1"] = distinct_n(responses, 1)
    metrics["lexical_distinct_2"] = distinct_n(responses, 2)
    metrics["per_turn"] = {
        str(tn): {
            "n": len(v["ndcg20"]),
            "ndcg@20": mean(v["ndcg20"]),
            "recall@20": mean(v["recall20"]),
            "recall@100": mean(v["recall100"]),
        }
        for tn, v in sorted(per_turn.items())
    }
    return metrics


def print_report(m, tid):
    print(f"\n=== {tid} ===")
    print(f"Turns evaluated: {m['n_turns_evaluated']}  "
          f"(skipped, no GT: {m['n_turns_skipped_no_gt']})")
    print(f"Max prediction depth: {m['max_prediction_depth']}  "
          f"(need >=100 for full Recall@100)\n")

    print("Ranking quality")
    for k in KS:
        print(f"  NDCG@{k:<3}    {m[f'ndcg@{k}']:.4f}")
    print(f"  MRR         {m['mrr']:.4f}")
    print(f"  MRR@100     {m['mrr@100']:.4f}\n")

    print("Retrieval coverage (is the GT even in the pool?)")
    for k in KS:
        print(f"  Recall@{k:<3}  {m[f'recall@{k}']:.4f}")
    print(f"  % GT not in top-20   {m['pct_gt_not_in_top20']:.1%}")
    print(f"  % GT not in top-100  {m['pct_gt_not_in_top100']:.1%}")
    if m["mean_rank_when_found"] is not None:
        print(f"  Mean rank (when found)   {m['mean_rank_when_found']:.1f}")
        print(f"  Median rank (when found) {m['median_rank_when_found']:.1f}")
    print()

    print("Diversity")
    print(f"  Catalog diversity @20   {m['catalog_diversity@20']:.4f}")
    print(f"  Catalog diversity @100  {m['catalog_diversity@100']:.4f}")
    print(f"  Response distinct-1     {m['lexical_distinct_1']:.4f}")
    print(f"  Response distinct-2     {m['lexical_distinct_2']:.4f}\n")

    print("Per-turn  (NDCG@20 / Recall@20 / Recall@100)")
    for tn, v in m["per_turn"].items():
        print(f"  turn {tn}: {v['ndcg@20']:.4f}  {v['recall@20']:.4f}  "
              f"{v['recall@100']:.4f}  (n={v['n']})")


def main():
    parser = argparse.ArgumentParser(description="Offline devset evaluation for Music CRS.")
    parser.add_argument("--tid", required=True,
                        help="Task id. Reads exp/inference/devset/{tid}.json.")
    parser.add_argument("--pred_file", default=None,
                        help="Override prediction JSON path.")
    parser.add_argument("--dataset_name",
                        default="talkpl-ai/TalkPlayData-Challenge-Dataset")
    parser.add_argument("--split", default="test")
    parser.add_argument("--catalog_name",
                        default="talkpl-ai/TalkPlayData-Challenge-Track-Metadata")
    parser.add_argument("--catalog_split", default="all_tracks")
    parser.add_argument("--out_dir", default="exp/eval/devset")
    args = parser.parse_args()

    from datasets import load_dataset

    pred_file = args.pred_file or f"exp/inference/devset/{args.tid}.json"
    with open(pred_file) as f:
        predictions = json.load(f)

    ground_truth = load_ground_truth(args.dataset_name, args.split)
    catalog_size = len(load_dataset(args.catalog_name, split=args.catalog_split))

    metrics = evaluate(predictions, ground_truth, catalog_size)

    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, f"{args.tid}.json")
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print_report(metrics, args.tid)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
