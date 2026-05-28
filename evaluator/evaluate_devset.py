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

import argparse
import json
import os
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


def _safe_float(value):
    return None if pd.isna(value) else float(value)


def _safe_int(value):
    return None if pd.isna(value) else int(value)


def _depth_metadata(df_predictions):
    depths = df_predictions["predicted_track_ids"].map(len)
    min_pool_depth = int(depths.min()) if len(depths) else 0
    max_pool_depth = int(depths.max()) if len(depths) else 0
    n_shallow_rows = int((depths < REQUIRED_DIAGNOSTIC_DEPTH).sum())
    return {
        "depths": depths,
        "min_pool_depth": min_pool_depth,
        "max_pool_depth": max_pool_depth,
        "n_shallow_rows": n_shallow_rows,
        "available_cutoffs": list(K_VALUES),
        "available_mrr_cutoffs": list(MRR_K_VALUES),
    }


def _aggregate_metric(df_turnwise: pd.DataFrame, column_name: str):
    if column_name not in df_turnwise:
        return None
    return _safe_float(df_turnwise[column_name].mean())


def _aggregate_group_metric(sub: pd.DataFrame, column_name: str):
    if column_name not in sub:
        return None
    return _safe_float(sub[column_name].mean())


def _format_metric(label: str, value, decimals: int = 4):
    if value is None:
        return f"  {label:<11} n/a"
    return f"  {label:<11} {value:.{decimals}f}"


def _format_percent(label: str, value):
    if value is None:
        return f"  {label} n/a"
    return f"  {label} {value:.1%}"


def evaluate(df_predictions, df_ground_truth):
    """Compute per-turn-instance metrics and aggregate them.

    Returns:
        (per_instance_rows, aggregate_dict)
    """
    depth_meta = _depth_metadata(df_predictions)

    rows = []
    ranks_found = []
    rrs_full = []
    rr_at_k = {k: [] for k in MRR_K_VALUES}
    recommended_tracks_20 = []
    recommended_tracks_100 = []
    responses = []

    for _, row in tqdm(df_ground_truth.iterrows(), total=len(df_ground_truth),
                       desc="Scoring turns"):
        sid, tn = row["session_id"], row["turn_number"]
        gt_id = row["ground_truth_track_id"]

        pred = df_filtering(df_predictions, sid, tn)
        preds = pred["predicted_track_ids"]
        pred_depth = len(preds)

        recsys_metrics = compute_recsys_metrics(preds, [gt_id], K_VALUES)
        rank = get_rank([gt_id], preds)
        rr_full = get_reciprocal_rank(gt_id, preds)
        if rank is not None:
            ranks_found.append(rank)
        rrs_full.append(rr_full)
        rr_values = {k: get_reciprocal_rank(gt_id, preds, k=k) for k in MRR_K_VALUES}
        for k in MRR_K_VALUES:
            rr_at_k[k].append(rr_values[k])

        # Catalog diversity uses the top-20 (submission format) and top-100
        # (dev pool) separately so we can tell the two apart.
        recommended_tracks_20.extend(preds[:20])
        recommended_tracks_100.extend(preds[:100])
        responses.append(pred["predicted_response"])

        rows.append({
            "session_id": sid,
            "turn_number": tn,
            "pool_depth": pred_depth,
            "gt_rank": rank if rank is not None else np.nan,
            "rr": rr_full,
            **{f"rr@{k}": rr_values[k] for k in MRR_K_VALUES},
            **recsys_metrics,
        })

    df_results = pd.DataFrame(rows)
    metric_cols = [c for c in df_results.columns
                   if c not in ("session_id", "turn_number", "gt_rank", "pool_depth")]

    # Headline macro-avg: group by turn, take mean over turns (preserves
    # published leaderboard semantics).
    df_turnwise = df_results[metric_cols + ["turn_number"]] \
        .groupby("turn_number").mean()
    # Per-turn breakdown (mean per turn_number, for diagnostics).
    per_turn = {}
    for tn, sub in df_results.groupby("turn_number"):
        per_turn[int(tn)] = {
            "n": int(len(sub)),
            "ndcg@20": _aggregate_group_metric(sub, "ndcg@20"),
            "hit@20": _aggregate_group_metric(sub, "hit@20"),
            "hit@100": _aggregate_group_metric(sub, "hit@100"),
        }

    n_total = len(df_results)
    agg = {
        "n_turns_evaluated": n_total,
        "require_full_diagnostic_depth": False,
        "full_diagnostic_depth": REQUIRED_DIAGNOSTIC_DEPTH,
        "available_cutoffs": depth_meta["available_cutoffs"],
        "min_pool_depth": depth_meta["min_pool_depth"],
        "max_pool_depth": depth_meta["max_pool_depth"],
        "n_shallow_rows": depth_meta["n_shallow_rows"],
        # Headline metrics (turn-then-session macro avg) — match leaderboard
        **{f"ndcg@{k}": _aggregate_metric(df_turnwise, f"ndcg@{k}") for k in HEADLINE_K},
        # Full metric sweep (same macro-avg semantics so all metrics are comparable)
        **{f"ndcg@{k}": _aggregate_metric(df_turnwise, f"ndcg@{k}") for k in K_VALUES},
        **{f"hit@{k}": _aggregate_metric(df_turnwise, f"hit@{k}") for k in K_VALUES},
        **{f"recall@{k}": _aggregate_metric(df_turnwise, f"recall@{k}") for k in K_VALUES},
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
    print(
        f"Turns evaluated: {m['n_turns_evaluated']}   "
        f"Min pool depth: {m['min_pool_depth']}   "
        f"Max pool depth: {m['max_pool_depth']}   "
        f"Shallow rows: {m['n_shallow_rows']}"
    )
    print(
        f"Full diagnostic depth required: {m['require_full_diagnostic_depth']} "
        f"(target depth={REQUIRED_DIAGNOSTIC_DEPTH}); metric cutoffs: {m['available_cutoffs']}\n"
    )

    print("Ranking quality (macro avg: per-turn, then across turns)")
    for k in K_VALUES:
        print(_format_metric(f"NDCG@{k}", m[f"ndcg@{k}"]))
    print(_format_metric("MRR", m["mrr"]))
    for k in MRR_K_VALUES:
        print(_format_metric(f"MRR@{k}", m[f"mrr@{k}"]))
    print()

    print("Retrieval coverage (is the GT even in the pool?)")
    for k in K_VALUES:
        print(_format_metric(f"Hit@{k}", m[f"hit@{k}"]))
    print(_format_percent("% GT not in top-20  ", m["pct_gt_not_in_top20"]))
    print(_format_percent("% GT not in top-100 ", m["pct_gt_not_in_top100"]))
    print(_format_percent("% GT not in top-200 ", m["pct_gt_not_in_top200"]))
    print(_format_percent("% GT not in top-500 ", m["pct_gt_not_in_top500"]))
    print(_format_percent("% GT not in top-1000", m["pct_gt_not_in_top1000"]))
    if m["mean_rank_when_found"] is not None:
        print(f"  Mean rank (found)    {m['mean_rank_when_found']:.1f}")
        print(f"  Median rank (found)  {m['median_rank_when_found']:.1f}")
    print()

    print("Diversity")
    print(_format_metric("Catalog div @20", m["catalog_diversity"]))
    print(_format_metric("Catalog div @100", m["catalog_diversity@100"]))
    print(f"  Lexical diversity       {m['lexical_diversity']:.4f}\n")

    print("Per-turn  (NDCG@20 / Hit@20 / Hit@100)")
    for tn, v in m["per_turn"].items():
        ndcg20 = "n/a" if v["ndcg@20"] is None else f"{v['ndcg@20']:.4f}"
        hit20 = "n/a" if v["hit@20"] is None else f"{v['hit@20']:.4f}"
        hit100 = "n/a" if v["hit@100"] is None else f"{v['hit@100']:.4f}"
        print(f"  turn {tn}: {ndcg20}  {hit20}  {hit100}  (n={v['n']})")


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
    recommended_20 = agg.pop("_recommended_20")
    recommended_100 = agg.pop("_recommended_100")
    agg["catalog_diversity"] = compute_catalog_diversity(recommended_20, total_catalog_size)
    agg["catalog_diversity@100"] = compute_catalog_diversity(recommended_100, total_catalog_size)
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
