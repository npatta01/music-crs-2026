"""Train a LambdaMART reranker on devset union-pool features (local CPU).

Session-level split (70/15/15), lambdarank@NDCG, paired per-turn eval vs the
RRF baseline ordering on held-out sessions, feature importances, and a
pool-features-off ablation arm.

Usage:
  python scripts/rerank/train_lgbm.py \
      --features exp/analysis/rerank/features.parquet \
      --out-dir exp/analysis/rerank/model_v1
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ID_COLS = ["session_id", "turn_number", "track_id", "label"]
# RRF-derived columns are NEVER model inputs (user decision 2026-06-11): the
# ranker must not depend on the fusion it replaces. rrf_rank stays in the
# parquet only to compute the eval baseline.
RRF_COLS = ["rrf_rank", "rrf_score", "pct_rrf_score"]
CATEGORICALS = ["age_group", "gender", "goal_category", "goal_specificity",
                "request_type", "intent_mode", "target_artist_mode",
                "temporal_strength"]
POOL_PREFIXES = ("rank__", "score__", "hit__")
POOL_COLS = ["n_branches", "best_branch_rank"]


def ndcg20(rank: float | None) -> float:
    if rank is None or (isinstance(rank, float) and (math.isnan(rank) or rank > 20)):
        return 0.0
    return 1.0 / math.log2(rank + 1)


def turn_metrics(df: pd.DataFrame, score_col: str, ascending: bool) -> pd.DataFrame:
    rows = []
    for (sid, tn), g in df.groupby(["session_id", "turn_number"], sort=False):
        order = g[score_col].rank(ascending=ascending, method="first", na_option="bottom")
        gt_rank = float(order[g["label"] == 1].iloc[0])
        rows.append({"session_id": sid, "turn_number": tn,
                     "gt_rank": gt_rank, "ndcg20": ndcg20(gt_rank),
                     "hit20": float(gt_rank <= 20), "hit1": float(gt_rank <= 1)})
    return pd.DataFrame(rows)


def train_arm(df: pd.DataFrame, feature_cols: list[str], cats: list[str],
              train_sids: set, val_sids: set, seed: int):
    def prep(part: pd.DataFrame):
        part = part.sort_values(["session_id", "turn_number"], kind="stable")
        groups = part.groupby(["session_id", "turn_number"], sort=False).size().to_numpy()
        x = part[feature_cols]
        return x, part["label"].to_numpy(), groups, part

    tr_x, tr_y, tr_g, _ = prep(df[df.session_id.isin(train_sids)])
    va_x, va_y, va_g, _ = prep(df[df.session_id.isin(val_sids)])

    model = lgb.LGBMRanker(
        objective="lambdarank",
        n_estimators=2000,
        learning_rate=0.05,
        num_leaves=63,
        min_child_samples=50,
        random_state=seed,
        lambdarank_truncation_level=40,
        n_jobs=-1,
    )
    model.fit(
        tr_x, tr_y, group=tr_g,
        eval_set=[(va_x, va_y)], eval_group=[va_g],
        eval_at=[20], eval_metric="ndcg",
        callbacks=[lgb.early_stopping(100, verbose=False), lgb.log_evaluation(200)],
        categorical_feature=[c for c in cats if c in feature_cols],
    )
    return model


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", required=True)
    ap.add_argument("--out-dir", default="exp/analysis/rerank/model_v1")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("loading parquet ...", flush=True)
    df = pd.read_parquet(args.features)
    for c in df.columns:
        if df[c].dtype == np.float64:
            df[c] = df[c].astype(np.float32)
    for c in CATEGORICALS:
        if c in df.columns:
            df[c] = df[c].fillna("").astype("category")
    feature_cols = [c for c in df.columns if c not in ID_COLS and c not in RRF_COLS]
    print(f"  {len(df):,} rows, {len(feature_cols)} features, "
          f"{df.groupby(['session_id','turn_number']).ngroups} turns", flush=True)

    sids = sorted(df.session_id.unique())
    rng = random.Random(args.seed)
    rng.shuffle(sids)
    n = len(sids)
    train_sids = set(sids[: int(0.7 * n)])
    val_sids = set(sids[int(0.7 * n): int(0.85 * n)])
    test_sids = set(sids[int(0.85 * n):])
    print(f"  sessions: train={len(train_sids)} val={len(val_sids)} test={len(test_sids)}", flush=True)

    test_df = df[df.session_id.isin(test_sids)].copy()
    rrf = turn_metrics(test_df, "rrf_rank", ascending=True)

    arms = {
        "full": feature_cols,
        "no_pool": [c for c in feature_cols
                    if not c.startswith(POOL_PREFIXES) and c not in POOL_COLS],
    }
    report = {"n_test_turns": len(rrf), "rrf": {
        "ndcg20": float(rrf.ndcg20.mean()), "hit20": float(rrf.hit20.mean()),
        "hit1": float(rrf.hit1.mean())}}
    lines = [f"# Reranker v1 — devset union-pool LambdaMART ({pd.Timestamp.now().date()})",
             f"\nTest sessions: {len(test_sids)} ({len(rrf)} playable turns). "
             f"RRF baseline: ndcg20={report['rrf']['ndcg20']:.4f} "
             f"hit20={report['rrf']['hit20']:.4f} hit1={report['rrf']['hit1']:.4f}\n",
             "| arm | ndcg@20 | Δ vs RRF | t | hit@20 | hit@1 | best_iter |",
             "|---|---:|---:|---:|---:|---:|---:|"]

    for arm_name, cols in arms.items():
        print(f"training arm: {arm_name} ({len(cols)} features) ...", flush=True)
        model = train_arm(df, cols, CATEGORICALS, train_sids, val_sids, args.seed)
        test_df["_score"] = model.predict(test_df[cols])
        mm = turn_metrics(test_df, "_score", ascending=False)
        merged = rrf.merge(mm, on=["session_id", "turn_number"], suffixes=("_rrf", "_m"))
        d = merged.ndcg20_m - merged.ndcg20_rrf
        t = d.mean() / (d.std() / math.sqrt(len(d))) if len(d) > 1 else float("nan")
        report[arm_name] = {
            "ndcg20": float(mm.ndcg20.mean()), "hit20": float(mm.hit20.mean()),
            "hit1": float(mm.hit1.mean()), "delta_ndcg20": float(d.mean()),
            "t": float(t), "best_iteration": int(model.best_iteration_ or 0),
        }
        lines.append(f"| {arm_name} | {report[arm_name]['ndcg20']:.4f} | "
                     f"{d.mean():+.4f} | {t:+.2f} | {report[arm_name]['hit20']:.4f} | "
                     f"{report[arm_name]['hit1']:.4f} | {report[arm_name]['best_iteration']} |")
        imp = pd.Series(model.feature_importances_, index=cols).sort_values(ascending=False)
        report[arm_name]["top_features"] = {k: float(v) for k, v in imp.head(30).items()}
        model.booster_.save_model(str(out / f"model_{arm_name}.txt"))
        if arm_name == "full":
            lines.append("\n## Top-25 features (gain, full arm)\n")
            lines.append("| feature | importance |")
            lines.append("|---|---:|")
            for k, v in imp.head(25).items():
                lines.append(f"| {k} | {v:.0f} |")
            lines.append("")

    (out / "report.json").write_text(json.dumps(report, indent=2))
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rrf"} | {"rrf": report["rrf"]},
                     indent=2, default=str)[:2000], flush=True)
    print(f"wrote {out}/report.md", flush=True)


if __name__ == "__main__":
    main()
