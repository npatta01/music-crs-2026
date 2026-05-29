"""Score multiple reranked prediction files side-by-side against one base."""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

K_VALUES = [1, 5, 10, 20, 50, 100, 200]


def dcg(rel):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rel))


def ndcg_at_k(predicted, gt, k):
    rel = [1 if t == gt else 0 for t in predicted[:k]]
    idcg = dcg([1] + [0] * (k - 1))
    return dcg(rel) / idcg if idcg else 0.0


def score(rows, gt_map, n_limit=None):
    hit = defaultdict(int)
    ndcg = defaultdict(float)
    mrr_sum = 0.0
    n = 0
    for r in rows[:n_limit] if n_limit else rows:
        pred = r.get("predicted_track_ids") or []
        if not pred:
            continue
        g = gt_map.get((r.get("session_id"), int(r.get("turn_number"))))
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
    p.add_argument("--gt", default="evaluator/exp/ground_truth/devset.json")
    p.add_argument("--n-limit", type=int, default=0)
    p.add_argument("inputs", nargs="+", help="label=path pairs")
    args = p.parse_args()

    gt_rows = json.loads(Path(args.gt).read_text())
    gt_map = {(r["session_id"], r["turn_number"]): r["ground_truth_track_id"] for r in gt_rows}
    n_limit = args.n_limit if args.n_limit > 0 else None

    results = {}
    for spec in args.inputs:
        label, path = spec.split("=", 1)
        rows = json.loads(Path(path).read_text())
        results[label] = score(rows, gt_map, n_limit=n_limit)
        results[label]["path"] = path

    # Table
    labels = list(results.keys())
    print(f"{'metric':<14}" + "".join(f"{l:>14}" for l in labels))
    print("-" * (14 + 14 * len(labels)))
    print(f"{'n':<14}" + "".join(f"{results[l]['n']:>14}" for l in labels))
    for k in K_VALUES:
        print(f"{'Hit@'+str(k):<14}" + "".join(f"{results[l]['hit'][k]:>14.4f}" for l in labels))
    print(f"{'MRR':<14}" + "".join(f"{results[l]['mrr']:>14.4f}" for l in labels))
    for k in K_VALUES:
        print(f"{'NDCG@'+str(k):<14}" + "".join(f"{results[l]['ndcg'][k]:>14.4f}" for l in labels))


if __name__ == "__main__":
    main()
