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
        gt_row = g[g["label"] == 1]
        gt_rank = float(order[g["label"] == 1].iloc[0])
        rows.append({"session_id": sid, "turn_number": tn,
                     "gt_rank": gt_rank, "ndcg20": ndcg20(gt_rank),
                     "hit20": float(gt_rank <= 20), "hit1": float(gt_rank <= 1),
                     "request_type": str(gt_row["request_type"].iloc[0]) if "request_type" in g else "",
                     "goal_category": str(gt_row["goal_category"].iloc[0]) if "goal_category" in g else "",
                     "warm_user": (float(gt_row["has_user_vec"].iloc[0]) if "has_user_vec" in g else 1.0)})
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

    # Tuned for ~1,258-candidate pools with deep GTs:
    # - truncation_level 200 (was 40): gradients must reach GTs at rank 51-200,
    #   half the addressable misses; 40 starved them.
    # - lr 0.025 + patience 200 (was 0.05/100): v1 stopped at 110 trees —
    #   step too coarse for 5M+ rows.
    # - num_leaves 127 (was 63): capacity matched to data scale.
    model = lgb.LGBMRanker(
        objective="lambdarank",
        n_estimators=4000,
        learning_rate=0.025,
        num_leaves=127,
        min_child_samples=50,
        random_state=seed,
        lambdarank_truncation_level=200,
        n_jobs=-1,
    )
    model.fit(
        tr_x, tr_y, group=tr_g,
        eval_set=[(va_x, va_y)], eval_group=[va_g],
        eval_at=[20], eval_metric="ndcg",
        callbacks=[lgb.early_stopping(200, verbose=False), lgb.log_evaluation(400)],
        categorical_feature=[c for c in cats if c in feature_cols],
    )
    return model


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", required=True)
    ap.add_argument("--out-dir", default="exp/analysis/rerank/model_v1")
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--ground-truth", default="exp/ground_truth/devset.json",
                    help="Used for the session->user mapping (user-grouped split).")
    ap.add_argument("--user-dropout", type=float, default=0.25,
                    help="Fraction of TRAIN sessions whose user_cf features are "
                         "zeroed (cold-start robustness; Gemini review rec).")
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

    # USER-grouped split (Gemini review finding: devset = 500 users x 2
    # sessions; a session-level split puts ~52% of test users' other session
    # in train -> user-preference memorization inflates test metrics).
    sess_user = {}
    for r in json.load(open(args.ground_truth)):
        sess_user[str(r["session_id"])] = str(r["user_id"])
    sids_all = sorted(df.session_id.unique())
    users = sorted({sess_user.get(s, s) for s in sids_all})
    rng = random.Random(args.seed)
    rng.shuffle(users)
    n_u = len(users)
    train_users = set(users[: int(0.7 * n_u)])
    val_users = set(users[int(0.7 * n_u): int(0.85 * n_u)])
    train_sids = {s for s in sids_all if sess_user.get(s, s) in train_users}
    val_sids = {s for s in sids_all if sess_user.get(s, s) in val_users}
    test_sids = set(sids_all) - train_sids - val_sids
    overlap = ({sess_user.get(s) for s in test_sids} &
               {sess_user.get(s) for s in train_sids})
    print(f"  users: {n_u}; sessions: train={len(train_sids)} val={len(val_sids)} "
          f"test={len(test_sids)}; train-test user overlap={len(overlap)} (must be 0)",
          flush=True)
    assert not overlap, "user leakage across split"

    # user-embedding dropout on a fraction of TRAIN sessions
    if args.user_dropout > 0:
        drop_sids = {s for s in train_sids if rng.random() < args.user_dropout}
        mask = df.session_id.isin(drop_sids)
        for col, fill in [("user_cf", 0.0), ("pct_user_cf", 0.5), ("has_user_vec", 0.0)]:
            if col in df.columns:
                df.loc[mask, col] = fill
        print(f"  user-dropout applied to {len(drop_sids)} train sessions", flush=True)

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
             "| arm | ndcg@20 | Δ vs RRF | t | hit@20 | hit@1 | best_iter | train ndcg@20 | val ndcg@20 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]

    train_eval_sids = set(list(train_sids)[:150])
    train_eval_df = df[df.session_id.isin(train_eval_sids)].copy()
    val_df = df[df.session_id.isin(val_sids)].copy()

    for arm_name, cols in arms.items():
        print(f"training arm: {arm_name} ({len(cols)} features) ...", flush=True)
        model = train_arm(df, cols, CATEGORICALS, train_sids, val_sids, args.seed)
        train_eval_df["_score"] = model.predict(train_eval_df[cols])
        val_df["_score"] = model.predict(val_df[cols])
        tr_m = turn_metrics(train_eval_df, "_score", ascending=False)
        va_m = turn_metrics(val_df, "_score", ascending=False)
        test_df["_score"] = model.predict(test_df[cols])
        mm = turn_metrics(test_df, "_score", ascending=False)
        print(f"  {arm_name}: train ndcg@20={tr_m.ndcg20.mean():.4f} "
              f"val={va_m.ndcg20.mean():.4f} test={mm.ndcg20.mean():.4f}", flush=True)
        merged = rrf.merge(mm, on=["session_id", "turn_number"], suffixes=("_rrf", "_m"))
        d = merged.ndcg20_m - merged.ndcg20_rrf
        t = d.mean() / (d.std() / math.sqrt(len(d))) if len(d) > 1 else float("nan")
        report[arm_name] = {
            "ndcg20": float(mm.ndcg20.mean()), "hit20": float(mm.hit20.mean()),
            "hit1": float(mm.hit1.mean()), "delta_ndcg20": float(d.mean()),
            "t": float(t), "best_iteration": int(model.best_iteration_ or 0),
            "train_ndcg20": float(tr_m.ndcg20.mean()),
            "val_ndcg20": float(va_m.ndcg20.mean()),
        }
        lines.append(f"| {arm_name} | {report[arm_name]['ndcg20']:.4f} | "
                     f"{d.mean():+.4f} | {t:+.2f} | {report[arm_name]['hit20']:.4f} | "
                     f"{report[arm_name]['hit1']:.4f} | {report[arm_name]['best_iteration']} | "
                     f"{report[arm_name]['train_ndcg20']:.4f} | {report[arm_name]['val_ndcg20']:.4f} |")
        imp = pd.Series(model.feature_importances_, index=cols).sort_values(ascending=False)
        report[arm_name]["top_features"] = {k: float(v) for k, v in imp.head(30).items()}
        model.booster_.save_model(str(out / f"model_{arm_name}.txt"))
        if arm_name == "full":
            lines.append("\n## Per-cohort conversion (full arm vs RRF, test)\n")
            cohort = merged.copy()
            cohort["request_type"] = cohort.get("request_type_m", cohort.get("request_type", ""))
            cohort["goal_category"] = cohort.get("goal_category_m", cohort.get("goal_category", ""))
            cohort["warm_user"] = cohort.get("warm_user_m", cohort.get("warm_user", 1.0))
            for dim in ["warm_user", "request_type", "goal_category", "turn_number"]:
                lines.append(f"\n### by {dim}\n")
                lines.append("| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |")
                lines.append("|---|---:|---:|---:|---:|")
                for val, grp in cohort.groupby(dim):
                    if len(grp) < 15:
                        continue
                    lines.append(f"| {val} | {len(grp)} | {grp.ndcg20_rrf.mean():.4f} | "
                                 f"{grp.ndcg20_m.mean():.4f} | {grp.hit20_m.mean():.4f} |")
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
