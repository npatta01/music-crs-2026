"""
Evaluation script for music recommendation systems.

Computes both the headline leaderboard metrics (NDCG@{1,10,20},
catalog_diversity, lexical_diversity) and a richer set of diagnostic
metrics used for dev-set iteration:

- NDCG@{1,5,10,20,50,100,200,500,1000}
- Hit@{1,5,10,20,50,100,200,500,1000}  (== recall@k for single-gold case)
- MRR (over the full retrieved pool) and MRR@{100,200,500,1000}
- Mean / median rank of the GT when it is retrieved at all
- % of turns where the GT is not in top-{20,100,200,500,1000}
- Per-turn (1-8) breakdown of NDCG@20 / Hit@20 / Hit@100

The `ndcg@{1,10,20}` numbers preserve the original macro-averaging
semantics (mean per turn_number across sessions, then mean across turns)
so they remain comparable with published leaderboard scores.
"""

import os
import json
import argparse
from collections import defaultdict
from pathlib import Path

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
K_VALUES = [1, 5, 10, 20, 50, 100, 200, 500, 1000]
# Subset used for the headline leaderboard metrics (preserve backward-compat).
HEADLINE_K = [1, 10, 20]
MRR_K_VALUES = [100, 200, 500, 1000]
REQUIRED_DIAGNOSTIC_DEPTH = max(K_VALUES)


def df_filtering(df, session_id, turn_number):
    mask = (df["session_id"] == session_id) & (df["turn_number"] == turn_number)
    return df[mask].iloc[0]


def _mean(xs):
    return float(np.mean(xs)) if len(xs) else 0.0


def _median(xs):
    return float(np.median(xs)) if len(xs) else 0.0


def _validate_prediction_depths(df_predictions):
    depths = df_predictions["predicted_track_ids"].map(len)
    too_shallow = df_predictions.loc[depths < REQUIRED_DIAGNOSTIC_DEPTH,
                                     ["session_id", "turn_number"]]
    if too_shallow.empty:
        return

    examples = ", ".join(
        f"{row.session_id}/turn-{row.turn_number}"
        for row in too_shallow.head(3).itertuples(index=False)
    )
    raise ValueError(
        "Cannot compute top-1000 diagnostics because some prediction rows are "
        f"shallower than {REQUIRED_DIAGNOSTIC_DEPTH} candidates "
        f"({len(too_shallow)} / {len(df_predictions)} rows affected; "
        f"examples: {examples}). Rerun devset inference with "
        f"`retrieval_topk: {REQUIRED_DIAGNOSTIC_DEPTH}`."
    )


def evaluate(df_predictions, df_ground_truth):
    """Compute per-turn-instance metrics and aggregate them.

    Returns:
        (per_instance_rows, aggregate_dict)
    """
    _validate_prediction_depths(df_predictions)

    rows = []
    ranks_found = []
    rrs_full = []
    rr_at_k = {k: [] for k in MRR_K_VALUES}
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
        if rank is not None:
            ranks_found.append(rank)
        rrs_full.append(rr_full)
        for k in MRR_K_VALUES:
            rr_at_k[k].append(get_reciprocal_rank(gt_id, preds, k=k))

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
            **{f"rr@{k}": rr_at_k[k][-1] for k in MRR_K_VALUES},
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
        **{f"mrr@{k}": _mean(rr_at_k[k]) for k in MRR_K_VALUES},
        "mean_rank_when_found": _mean(ranks_found) if ranks_found else None,
        "median_rank_when_found": _median(ranks_found) if ranks_found else None,
        "pct_gt_not_in_top20":
            float((df_results["hit@20"] == 0).sum() / n_total) if n_total else 0.0,
        "pct_gt_not_in_top100":
            float((df_results["hit@100"] == 0).sum() / n_total) if n_total else 0.0,
        "pct_gt_not_in_top200":
            float((df_results["hit@200"] == 0).sum() / n_total) if n_total else 0.0,
        "pct_gt_not_in_top500":
            float((df_results["hit@500"] == 0).sum() / n_total) if n_total else 0.0,
        "pct_gt_not_in_top1000":
            float((df_results["hit@1000"] == 0).sum() / n_total) if n_total else 0.0,
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
          f"(need >={REQUIRED_DIAGNOSTIC_DEPTH} for full diagnostics)\n")

    print("Ranking quality (macro avg: per-turn, then across turns)")
    for k in K_VALUES:
        print(f"  NDCG@{k:<3}    {m[f'ndcg@{k}']:.4f}")
    print(f"  MRR          {m['mrr']:.4f}")
    for k in MRR_K_VALUES:
        print(f"  MRR@{k:<4}    {m[f'mrr@{k}']:.4f}")
    print()

    print("Retrieval coverage (is the GT even in the pool?)")
    for k in K_VALUES:
        print(f"  Hit@{k:<3}     {m[f'hit@{k}']:.4f}")
    print(f"  % GT not in top-20   {m['pct_gt_not_in_top20']:.1%}")
    print(f"  % GT not in top-100  {m['pct_gt_not_in_top100']:.1%}")
    print(f"  % GT not in top-200  {m['pct_gt_not_in_top200']:.1%}")
    print(f"  % GT not in top-500  {m['pct_gt_not_in_top500']:.1%}")
    print(f"  % GT not in top-1000 {m['pct_gt_not_in_top1000']:.1%}")
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


def _resolve_exp_dir(exp_dir: str | Path | None) -> Path:
    if exp_dir is None:
        return Path("exp")
    return Path(exp_dir)


def main(args):
    from datasets import load_dataset  # lazy to keep pure-metric tests import-free
    exp_dir = _resolve_exp_dir(getattr(args, "exp_dir", None))
    split = getattr(args, "eval_dataset", "devset")
    ground_truth = json.load(open(exp_dir / "ground_truth" / f"{split}.json"))
    if args.session_ids_file:
        with open(args.session_ids_file) as f:
            keep = set(json.load(f)["session_ids"])
        ground_truth = [r for r in ground_truth if r["session_id"] in keep]
    predictions = json.load(open(exp_dir / "inference" / split / f"{args.tid}.json"))

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

    score_dir = exp_dir / "scores" / split
    os.makedirs(score_dir, exist_ok=True)
    out_path = score_dir / f"{args.tid}.json"
    with open(out_path, "w") as f:
        json.dump(agg, f, indent=2)

    samples_path = score_dir / f"{args.tid}_samples.csv"
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
    parser.add_argument("--exp_dir", type=str, default="exp",
                        help="Artifact root containing inference, ground_truth, and scores.")
    args = parser.parse_args()
    main(args)
