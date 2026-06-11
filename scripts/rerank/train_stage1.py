"""Stage-1: train the raw-only ranker on the train split, evaluate TRANSFER
on devset REAL pools.

Train: 24.4M rows of sampled-negative groups (`build_train_features.py --mode
train`), user-grouped train/val split within the HF train split.
Transfer eval: raw features over the devset union pools (`--mode devset`),
scored on the SAME user-grouped devset test sessions as the v2 trainer
(seed 13) so numbers are comparable; RRF baseline joined from the v2 parquet.

Also writes per-(session,turn,track) stage-1 scores for the devset, ready to
join into the stage-2 stacker.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ID_COLS = ["session_id", "turn_number", "track_id", "label"]
CATEGORICALS = ["age_group", "gender", "goal_category", "goal_specificity"]


def ndcg20(rank: float) -> float:
    return 1.0 / math.log2(rank + 1) if rank <= 20 else 0.0


def turn_metrics(df: pd.DataFrame, score_col: str, ascending: bool) -> pd.DataFrame:
    rows = []
    for (sid, tn), g in df.groupby(["session_id", "turn_number"], sort=False):
        order = g[score_col].rank(ascending=ascending, method="first", na_option="bottom")
        gt = g["label"] == 1
        if not gt.any():
            continue
        r = float(order[gt].iloc[0])
        rows.append({"session_id": sid, "turn_number": tn, "ndcg20": ndcg20(r),
                     "hit20": float(r <= 20), "hit1": float(r <= 1)})
    return pd.DataFrame(rows)


def prep(part: pd.DataFrame, cols):
    part = part.sort_values(["session_id", "turn_number"], kind="stable")
    groups = part.groupby(["session_id", "turn_number"], sort=False).size().to_numpy()
    return part[cols], part["label"].to_numpy(), groups


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-features", default="exp/analysis/rerank/train_features")
    ap.add_argument("--devset-features", default="exp/analysis/rerank/devset_raw_features.parquet")
    ap.add_argument("--v2-features", default="exp/analysis/rerank/features_v2")
    ap.add_argument("--session-user", default="exp/analysis/rerank/train_session_user.json")
    ap.add_argument("--devset-gt", default="exp/ground_truth/devset.json")
    ap.add_argument("--out-dir", default="exp/analysis/rerank/stage1")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("loading train features ...", flush=True)
    df = pd.read_parquet(args.train_features)
    for c in df.columns:
        if df[c].dtype == np.float64:
            df[c] = df[c].astype(np.float32)
    for c in CATEGORICALS:
        df[c] = df[c].fillna("").astype("category")
    feature_cols = [c for c in df.columns if c not in ID_COLS]
    print(f"  {len(df):,} rows, {len(feature_cols)} features", flush=True)

    sess_user = json.load(open(args.session_user))
    users = sorted(set(sess_user.values()))
    rng = random.Random(args.seed)
    rng.shuffle(users)
    val_users = set(users[: int(0.05 * len(users))])
    val_sids = {s for s, u in sess_user.items() if u in val_users}
    is_val = df.session_id.isin(val_sids)
    tr_x, tr_y, tr_g = prep(df[~is_val], feature_cols)
    va_x, va_y, va_g = prep(df[is_val], feature_cols)
    print(f"  train turns={len(tr_g)} val turns={len(va_g)}", flush=True)

    model = lgb.LGBMRanker(
        objective="lambdarank", n_estimators=4000, learning_rate=0.025,
        num_leaves=127, min_child_samples=100, random_state=args.seed,
        lambdarank_truncation_level=100, n_jobs=-1,
    )
    model.fit(tr_x, tr_y, group=tr_g,
              eval_set=[(va_x, va_y)], eval_group=[va_g],
              eval_at=[20], eval_metric="ndcg",
              callbacks=[lgb.early_stopping(200, verbose=False), lgb.log_evaluation(400)],
              categorical_feature=CATEGORICALS)
    model.booster_.save_model(str(out / "model_stage1.txt"))
    print(f"  best_iter={model.best_iteration_}", flush=True)

    # ---- transfer eval on devset real pools ----
    print("loading devset raw features ...", flush=True)
    dv = pd.read_parquet(args.devset_features)
    for c in dv.columns:
        if dv[c].dtype == np.float64:
            dv[c] = dv[c].astype(np.float32)
    for c in CATEGORICALS:
        dv[c] = dv[c].fillna("").astype("category")
        dv[c] = dv[c].cat.set_categories(df[c].cat.categories)
    dv["stage1_score"] = model.predict(dv[feature_cols])
    dv[["session_id", "turn_number", "track_id", "stage1_score"]].to_parquet(
        out / "devset_stage1_scores.parquet")

    # same user-grouped devset split as train_lgbm.py (seed 13)
    dsess_user = {}
    for r in json.load(open(args.devset_gt)):
        dsess_user[str(r["session_id"])] = str(r["user_id"])
    dsids = sorted(dv.session_id.unique())
    dusers = sorted({dsess_user.get(s, s) for s in dsids})
    rng2 = random.Random(args.seed)
    rng2.shuffle(dusers)
    n_u = len(dusers)
    d_train_u = set(dusers[: int(0.7 * n_u)])
    d_val_u = set(dusers[int(0.7 * n_u): int(0.85 * n_u)])
    test_sids = {s for s in dsids
                 if dsess_user.get(s, s) not in d_train_u and dsess_user.get(s, s) not in d_val_u}
    test = dv[dv.session_id.isin(test_sids)].copy()

    # RRF baseline ranks joined from the v2 parquet
    import pyarrow.dataset as pds
    rrf = pds.dataset(args.v2_features).to_table(
        columns=["session_id", "turn_number", "track_id", "rrf_rank"]).to_pandas()
    test = test.merge(rrf, on=["session_id", "turn_number", "track_id"], how="left")

    s1 = turn_metrics(test, "stage1_score", ascending=False)
    rrf_m = turn_metrics(test, "rrf_rank", ascending=True)
    merged = rrf_m.merge(s1, on=["session_id", "turn_number"], suffixes=("_rrf", "_s1"))
    d = merged.ndcg20_s1 - merged.ndcg20_rrf
    t = d.mean() / (d.std() / math.sqrt(len(d)))
    result = {
        "test_turns": len(merged),
        "rrf": {"ndcg20": float(merged.ndcg20_rrf.mean()), "hit20": float(merged.hit20_rrf.mean())},
        "stage1": {"ndcg20": float(merged.ndcg20_s1.mean()), "hit20": float(merged.hit20_s1.mean()),
                   "hit1": float(merged.hit1_s1.mean())},
        "delta_ndcg20": float(d.mean()), "t": float(t),
        "best_iteration": int(model.best_iteration_ or 0),
    }
    imp = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    result["top_features"] = {k: float(v) for k, v in imp.head(25).items()}
    (out / "report.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2)[:1500], flush=True)


if __name__ == "__main__":
    main()
