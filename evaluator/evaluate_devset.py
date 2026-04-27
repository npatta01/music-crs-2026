"""
Evaluation script for music recommendation systems.

Computes both the headline leaderboard metrics (NDCG@{1,10,20},
catalog_diversity, lexical_diversity) and a richer set of diagnostic
metrics used for dev-set iteration:

- NDCG@{1,5,10,20,50,100}
- Hit@{1,5,10,20,50,100}  (== recall@k for single-gold case)
- MRR (over the full retrieved pool) and MRR@100
- Mean / median rank of the GT when it is retrieved at all
- % of turns where the GT is not in top-20 / not in top-100
- Per-turn (1-8) breakdown of NDCG@20 / Hit@20 / Hit@100

The `ndcg@{1,10,20}` numbers preserve the original macro-averaging
semantics (mean per turn_number across sessions, then mean across turns)
so they remain comparable with published leaderboard scores.
"""

import os
import json
import argparse
from collections import defaultdict

import numpy as np
import pandas as pd
from tqdm import tqdm

from metrics import (
    compute_recsys_metrics,
    compute_lexical_diversity,
    compute_catalog_diversity,
)
from metrics.metrics_recsys import get_reciprocal_rank, get_rank


# k values used for NDCG / Hit sweeps in the extended report.
K_VALUES = [1, 5, 10, 20, 50, 100]
# Subset used for the headline leaderboard metrics (preserve backward-compat).
HEADLINE_K = [1, 10, 20]


def df_filtering(df, session_id, turn_number):
    mask = (df["session_id"] == session_id) & (df["turn_number"] == turn_number)
    return df[mask].iloc[0]


def _mean(xs):
    return float(np.mean(xs)) if len(xs) else 0.0


def _median(xs):
    return float(np.median(xs)) if len(xs) else 0.0


def evaluate(df_predictions, df_ground_truth):
    """Compute per-turn-instance metrics and aggregate them.

    Returns:
        (per_instance_rows, aggregate_dict)
    """
    rows = []
    ranks_found = []
    rrs_full, rrs_100 = [], []
    recommended_tracks_20 = []
    recommended_tracks_100 = []
    responses = []
    max_pool_depth = 0

    for _, row in tqdm(df_ground_truth.iterrows(), total=len(df_ground_truth),
                       desc="Scoring turns"):
        sid, tn = row["session_id"], row["turn_number"]
        gt_id = row["ground_truth_track_id"]

        pred = df_filtering(df_predictions, sid, tn)
        preds = pred["predicted_track_ids"]
        max_pool_depth = max(max_pool_depth, len(preds))

        recsys_metrics = compute_recsys_metrics(preds, [gt_id], K_VALUES)
        rank = get_rank([gt_id], preds)
        rr_full = get_reciprocal_rank(gt_id, preds)
        rr_100 = get_reciprocal_rank(gt_id, preds, k=100)
        if rank is not None:
            ranks_found.append(rank)
        rrs_full.append(rr_full)
        rrs_100.append(rr_100)

        # Catalog diversity uses the top-20 (submission format) and top-100
        # (dev pool) separately so we can tell the two apart.
        recommended_tracks_20.extend(preds[:20])
        recommended_tracks_100.extend(preds[:100])
        responses.append(pred["predicted_response"])

        rows.append({
            "session_id": sid,
            "turn_number": tn,
            "gt_rank": rank if rank is not None else np.nan,
            "rr": rr_full,
            "rr@100": rr_100,
            **recsys_metrics,
        })

    df_results = pd.DataFrame(rows)
    metric_cols = [c for c in df_results.columns
                   if c not in ("session_id", "turn_number", "gt_rank")]

    # Headline macro-avg: group by turn, take mean over turns (preserves
    # published leaderboard semantics).
    df_turnwise = df_results[metric_cols + ["turn_number"]] \
        .groupby("turn_number").mean()
    headline = df_turnwise.mean(axis=0).to_dict()

    # Per-turn breakdown (mean per turn_number, for diagnostics).
    per_turn = {}
    for tn, sub in df_results.groupby("turn_number"):
        per_turn[int(tn)] = {
            "n": int(len(sub)),
            "ndcg@20": float(sub["ndcg@20"].mean()),
            "hit@20": float(sub["hit@20"].mean()),
            "hit@100": float(sub["hit@100"].mean()),
        }

    n_total = len(df_results)
    agg = {
        "n_turns_evaluated": n_total,
        "max_pool_depth": max_pool_depth,
        # Headline metrics (turn-then-session macro avg) — match leaderboard
        **{f"ndcg@{k}": float(headline.get(f"ndcg@{k}", 0.0)) for k in HEADLINE_K},
        # Full metric sweep (same macro-avg semantics so all metrics are comparable)
        **{f"ndcg@{k}": float(headline.get(f"ndcg@{k}", 0.0)) for k in K_VALUES},
        **{f"hit@{k}":  float(headline.get(f"hit@{k}",  0.0)) for k in K_VALUES},
        **{f"recall@{k}": float(headline.get(f"recall@{k}", 0.0)) for k in K_VALUES},
        "mrr": _mean(rrs_full),
        "mrr@100": _mean(rrs_100),
        "mean_rank_when_found": _mean(ranks_found) if ranks_found else None,
        "median_rank_when_found": _median(ranks_found) if ranks_found else None,
        "pct_gt_not_in_top20":
            float((df_results["hit@20"] == 0).sum() / n_total) if n_total else 0.0,
        "pct_gt_not_in_top100":
            float((df_results["hit@100"] == 0).sum() / n_total) if n_total else 0.0,
        "per_turn": {str(k): v for k, v in sorted(per_turn.items())},
    }
    agg["_recommended_20"] = recommended_tracks_20
    agg["_recommended_100"] = recommended_tracks_100
    agg["_responses"] = responses
    return df_results, agg


def print_report(m, tid):
    print(f"\n=== {tid} ===")
    print(f"Turns evaluated: {m['n_turns_evaluated']}   "
          f"Max pool depth: {m['max_pool_depth']}  "
          f"(need >=100 for full Recall@100)\n")

    print("Ranking quality (macro avg: per-turn, then across turns)")
    for k in K_VALUES:
        print(f"  NDCG@{k:<3}    {m[f'ndcg@{k}']:.4f}")
    print(f"  MRR          {m['mrr']:.4f}")
    print(f"  MRR@100      {m['mrr@100']:.4f}\n")

    print("Retrieval coverage (is the GT even in the pool?)")
    for k in K_VALUES:
        print(f"  Hit@{k:<3}     {m[f'hit@{k}']:.4f}")
    print(f"  % GT not in top-20   {m['pct_gt_not_in_top20']:.1%}")
    print(f"  % GT not in top-100  {m['pct_gt_not_in_top100']:.1%}")
    if m["mean_rank_when_found"] is not None:
        print(f"  Mean rank (found)    {m['mean_rank_when_found']:.1f}")
        print(f"  Median rank (found)  {m['median_rank_when_found']:.1f}")
    print()

    print("Diversity")
    print(f"  Catalog diversity @20   {m['catalog_diversity']:.4f}")
    print(f"  Catalog diversity @100  {m['catalog_diversity@100']:.4f}")
    print(f"  Lexical diversity       {m['lexical_diversity']:.4f}\n")

    print("Per-turn  (NDCG@20 / Hit@20 / Hit@100)")
    for tn, v in m["per_turn"].items():
        print(f"  turn {tn}: {v['ndcg@20']:.4f}  {v['hit@20']:.4f}  "
              f"{v['hit@100']:.4f}  (n={v['n']})")


def main(args):
    from datasets import load_dataset  # lazy to keep pure-metric tests import-free
    ground_truth = json.load(open(f"exp/ground_truth/devset.json"))
    if args.session_ids_file:
        with open(args.session_ids_file) as f:
            keep = set(json.load(f)["session_ids"])
        ground_truth = [r for r in ground_truth if r["session_id"] in keep]
    predictions = json.load(open(f"exp/inference/devset/{args.tid}.json"))

    df_predictions = pd.DataFrame(predictions)
    df_ground_truth = pd.DataFrame(ground_truth)

    df_results, agg = evaluate(df_predictions, df_ground_truth)

    music_catalog = load_dataset(  # noqa: F821 — imported above
        "talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks"
    )
    total_catalog_size = len(music_catalog)
    agg["catalog_diversity"] = compute_catalog_diversity(
        agg.pop("_recommended_20"), total_catalog_size
    )
    agg["catalog_diversity@100"] = compute_catalog_diversity(
        agg.pop("_recommended_100"), total_catalog_size
    )
    agg["lexical_diversity"] = compute_lexical_diversity(agg.pop("_responses"))
    agg["total_catalog_size"] = total_catalog_size

    os.makedirs("exp/scores/devset", exist_ok=True)
    out_path = f"exp/scores/devset/{args.tid}.json"
    with open(out_path, "w") as f:
        json.dump(agg, f, indent=2)

    samples_path = f"exp/scores/devset/{args.tid}_samples.csv"
    df_results.to_csv(samples_path, index=False)

    print_report(agg, args.tid)
    print(f"\nSaved: {out_path}")
    print(f"Saved per-sample metrics: {samples_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate music recommendation system predictions"
    )
    parser.add_argument("--tid", type=str, default="llama1b_bm25",
                        help="Experiment id (matches prediction file stem).")
    parser.add_argument("--eval_dataset", type=str, default="devset")
    parser.add_argument("--session_ids_file", type=str, default=None,
                        help="Optional JSON with {session_ids: [...]} to score a subset.")
    args = parser.parse_args()
    main(args)
