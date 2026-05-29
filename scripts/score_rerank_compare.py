"""Side-by-side metrics: base (no rerank) vs reranked predictions on a shared turn-set.

Computes Hit@K and NDCG@K on the intersection of turns scored in both runs.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

K_VALUES = [1, 5, 10, 20, 50, 100, 200, 500, 1000]


def dcg(rel):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rel))


def ndcg_at_k(predicted, gt, k):
    rel = [1 if t == gt else 0 for t in predicted[:k]]
    idcg = dcg([1] + [0] * (k - 1))
    return dcg(rel) / idcg if idcg else 0.0


def load_preds(path):
    return json.loads(Path(path).read_text())


def score(rows, gt_map, n_limit=None):
    """Score the first n_limit rows (None = all). Skip turns with empty pools."""
    hit = defaultdict(int)
    ndcg = defaultdict(float)
    mrr_sum = 0.0
    n = 0
    for r in rows[:n_limit] if n_limit else rows:
        sid = r.get("session_id")
        tn = r.get("turn_number")
        pred = r.get("predicted_track_ids") or []
        if not pred:
            continue
        g = gt_map.get((sid, int(tn)))
        if g is None:
            continue
        n += 1
        try:
            rank = pred.index(g) + 1
            mrr_sum += 1.0 / rank
        except ValueError:
            rank = None
        for k in K_VALUES:
            if rank is not None and rank <= k:
                hit[k] += 1
            ndcg[k] += ndcg_at_k(pred, g, k)
    return {
        "n": n,
        "hit": {k: hit[k] / n if n else 0.0 for k in K_VALUES},
        "ndcg": {k: ndcg[k] / n if n else 0.0 for k in K_VALUES},
        "mrr": mrr_sum / n if n else 0.0,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="Path to base predictions JSON")
    p.add_argument("--reranked", required=True, help="Path to reranked predictions JSON")
    p.add_argument("--gt", default="evaluator/exp/ground_truth/devset.json")
    p.add_argument("--n-limit", type=int, default=0, help="Only score first N rows (0 = all)")
    args = p.parse_args()

    gt_rows = json.loads(Path(args.gt).read_text())
    gt_map = {(r["session_id"], r["turn_number"]): r["ground_truth_track_id"] for r in gt_rows}

    base = load_preds(args.base)
    rerk = load_preds(args.reranked)
    n_limit = args.n_limit if args.n_limit > 0 else None

    print(f"Scoring base:     {args.base}")
    print(f"Scoring reranked: {args.reranked}")
    if n_limit:
        print(f"  (limited to first {n_limit} rows)")
    print()
    s_base = score(base, gt_map, n_limit=n_limit)
    s_rerk = score(rerk, gt_map, n_limit=n_limit)

    print(f"  base    n={s_base['n']}, reranked n={s_rerk['n']}")
    print()
    print(f"  {'metric':<14} {'base':>10} {'reranked':>10} {'delta':>10}")
    print(f"  {'-'*46}")
    for k in K_VALUES:
        b, r = s_base["hit"][k], s_rerk["hit"][k]
        print(f"  Hit@{k:<10} {b:>10.4f} {r:>10.4f} {r-b:>+10.4f}")
    print(f"  {'MRR':<14} {s_base['mrr']:>10.4f} {s_rerk['mrr']:>10.4f} {s_rerk['mrr']-s_base['mrr']:>+10.4f}")
    for k in K_VALUES:
        b, r = s_base["ndcg"][k], s_rerk["ndcg"][k]
        print(f"  NDCG@{k:<9} {b:>10.4f} {r:>10.4f} {r-b:>+10.4f}")


if __name__ == "__main__":
    main()
