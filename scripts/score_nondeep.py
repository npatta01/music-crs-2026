"""Compute aggregate metrics on rows with full 1000-pool depth.

Used as a quick direction-check when evaluator's strict pool-depth contract
nulls everything because of LLM extractor empty-pool tail.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict

import pandas as pd

TID = sys.argv[1] if len(sys.argv) > 1 else "v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset"
PRED_PATH = f"exp/inference/devset/{TID}.json"
GT_PATH = "evaluator/exp/ground_truth/devset.json"
K_VALUES = [1, 5, 10, 20, 50, 100, 200, 500, 1000]


def dcg(rel: list[int]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rel))


def ndcg_at_k(predicted: list[str], gt: str, k: int) -> float:
    rel = [1 if t == gt else 0 for t in predicted[:k]]
    ideal = [1] + [0] * (k - 1)
    idcg = dcg(ideal)
    return dcg(rel) / idcg if idcg else 0.0


def main():
    print(f"loading: {PRED_PATH}")
    preds = json.load(open(PRED_PATH))
    print(f"  rows: {len(preds)}")
    gt_rows = json.load(open(GT_PATH))
    gt = {(r["session_id"], r["turn_number"]): r["ground_truth_track_id"] for r in gt_rows}

    full = []
    shallow = 0
    empty = 0
    for r in preds:
        pred = r["predicted_track_ids"]
        if len(pred) == 0:
            empty += 1
        elif len(pred) < 1000:
            shallow += 1
        else:
            g = gt.get((r["session_id"], r["turn_number"]))
            if g is not None:
                full.append((pred, g, r["turn_number"]))

    n = len(preds)
    n_full = len(full)
    print(f"  full-pool rows: {n_full}/{n} ({n_full/n:.1%})")
    print(f"  shallow rows:   {shallow}/{n} ({shallow/n:.1%})")
    print(f"  empty rows:     {empty}/{n} ({empty/n:.1%})")

    # Hit / NDCG on full-pool rows
    print("\n=== Metrics on full-pool rows only (apples-to-apples vs other v0+ runs) ===")
    hit = {k: 0 for k in K_VALUES}
    ndcg = {k: 0.0 for k in K_VALUES}
    mrr_sum = 0.0
    rank_when_found = []
    per_turn = defaultdict(lambda: {"n": 0, "hit20": 0, "hit100": 0, "ndcg20": 0.0})
    for pred, g, tn in full:
        try:
            rank = pred.index(g) + 1
            rank_when_found.append(rank)
            mrr_sum += 1.0 / rank
        except ValueError:
            rank = None
        for k in K_VALUES:
            if rank is not None and rank <= k:
                hit[k] += 1
            ndcg[k] += ndcg_at_k(pred, g, k)
        # per-turn
        per_turn[tn]["n"] += 1
        if rank is not None:
            if rank <= 20:
                per_turn[tn]["hit20"] += 1
            if rank <= 100:
                per_turn[tn]["hit100"] += 1
        per_turn[tn]["ndcg20"] += ndcg_at_k(pred, g, 20)

    print(f"  n={n_full}")
    print(f"  {'metric':<12} {'value':>8}")
    print(f"  {'-'*22}")
    for k in K_VALUES:
        print(f"  Hit@{k:<8} {hit[k]/n_full:>8.4f}")
    print(f"  {'MRR':<12} {mrr_sum/n_full:>8.4f}")
    for k in K_VALUES:
        print(f"  NDCG@{k:<7} {ndcg[k]/n_full:>8.4f}")
    if rank_when_found:
        print(f"  mean rank found:  {sum(rank_when_found)/len(rank_when_found):.1f}")
        s = sorted(rank_when_found)
        print(f"  median rank found: {s[len(s)//2]}")

    print("\n=== per-turn ===")
    print(f"  {'turn':<6} {'n':>6} {'Hit@20':>8} {'Hit@100':>8} {'NDCG@20':>8}")
    for tn in sorted(per_turn):
        t = per_turn[tn]
        print(f"  {tn:<6} {t['n']:>6} {t['hit20']/t['n']:>8.4f} {t['hit100']/t['n']:>8.4f} {t['ndcg20']/t['n']:>8.4f}")


if __name__ == "__main__":
    main()
