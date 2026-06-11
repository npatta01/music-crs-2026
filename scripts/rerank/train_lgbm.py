"""Train a LambdaMART reranker on devset union-pool features (local CPU).

Memory-conscious design (18GB machine):
- parquet -> arrow scan (filter + float32 cast at scan time)
- ONE packed numpy float32 matrix for all features (categoricals as int codes);
  the pandas frame keeps only ids/label/cohort columns
- native lgb.train + lgb.Dataset(free_raw_data) so raw slices release after
  binning; per-arm train/val binaries saved for instant sweep reuse
- user-grouped split (devset = 500 users x 2 sessions), deterministic
  sampling, all-pair overlap asserts

Usage:
  python scripts/rerank/train_lgbm.py --features exp/analysis/rerank/features_v3 \
      --max-pool-rank 200 --out-dir exp/analysis/rerank/model_X
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import random
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ID_COLS = ["session_id", "turn_number", "track_id", "label"]
# RRF-derived columns are NEVER model inputs (user decision 2026-06-11).
RRF_COLS = ["rrf_rank", "rrf_score", "pct_rrf_score"]
CATEGORICALS = ["age_group", "gender", "goal_category", "goal_specificity",
                "request_type", "intent_mode", "target_artist_mode",
                "temporal_strength"]
POOL_PREFIXES = ("rank__", "score__", "hit__", "margin__")
POOL_COLS = ["n_branches", "best_branch_rank", "margin_min", "pct_margin_min"]
COHORT_COLS = ["request_type", "goal_category", "has_user_vec"]

LGB_PARAMS = dict(
    objective="lambdarank",
    learning_rate=0.025,
    num_leaves=127,
    min_data_in_leaf=50,
    lambdarank_truncation_level=200,
    metric="ndcg",
    ndcg_eval_at=[20],
    verbosity=-1,
    num_threads=0,
)


def ndcg20(rank: float) -> float:
    return 1.0 / math.log2(rank + 1) if rank <= 20 else 0.0


def turn_metrics(df: pd.DataFrame, score_col: str, ascending: bool) -> pd.DataFrame:
    rows = []
    for (sid, tn), g in df.groupby(["session_id", "turn_number"], sort=False):
        order = g[score_col].rank(ascending=ascending, method="first", na_option="bottom")
        gt = g["label"] == 1
        if not gt.any():
            continue
        gt_row = g[gt]
        r = float(order[gt].iloc[0])
        rows.append({"session_id": sid, "turn_number": tn,
                     "gt_rank": r, "ndcg20": ndcg20(r),
                     "hit20": float(r <= 20), "hit1": float(r <= 1),
                     "request_type": str(gt_row["request_type"].iloc[0]) if "request_type" in g else "",
                     "goal_category": str(gt_row["goal_category"].iloc[0]) if "goal_category" in g else "",
                     "warm_user": float(gt_row["has_user_vec"].iloc[0]) if "has_user_vec" in g else 1.0})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", required=True)
    ap.add_argument("--out-dir", default="exp/analysis/rerank/model_v1")
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--ground-truth", default="exp/ground_truth/devset.json")
    ap.add_argument("--user-dropout", type=float, default=0.25)
    ap.add_argument("--max-pool-rank", type=int, default=0)
    ap.add_argument("--stage1-scores", default="")
    ap.add_argument("--reuse-bins", action="store_true",
                    help="Load previously saved train/val .bin datasets (same "
                         "out-dir, same arm) instead of rebinning — for sweeps.")
    ap.add_argument("--num-boost-round", type=int, default=4000)
    ap.add_argument("--early-stopping", type=int, default=200)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("loading parquet (arrow scan) ...", flush=True)
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.dataset as pds
    dataset = pds.dataset(args.features)
    filt = (pc.field("best_branch_rank") <= args.max_pool_rank) if args.max_pool_rank > 0 else None
    tbl = dataset.to_table(filter=filt)
    names = tbl.schema.names
    n = tbl.num_rows
    print(f"  {n:,} rows, {len(names)} cols", flush=True)

    # ids/label/cohorts as a slim pandas frame
    slim_cols = list(dict.fromkeys(ID_COLS + COHORT_COLS))
    slim = tbl.select([c for c in slim_cols if c in names]).to_pandas()

    feature_cols = [c for c in names if c not in ID_COLS and c not in RRF_COLS]
    stage1 = args.stage1_scores != ""
    cat_idx_map = {}
    X = np.empty((n, len(feature_cols) + (1 if stage1 else 0)), dtype=np.float32)
    for j, c in enumerate(feature_cols):
        col = tbl.column(c)
        if c in CATEGORICALS:
            codes, _ = pd.factorize(col.to_pandas().fillna(""), sort=True)
            X[:, j] = codes.astype(np.float32)
            cat_idx_map[j] = c
        else:
            X[:, j] = np.nan_to_num(
                col.to_numpy(zero_copy_only=False).astype(np.float32, copy=False), nan=0.0)
    y = tbl.column("label").to_numpy(zero_copy_only=False).astype(np.int8)
    del tbl
    gc.collect()
    print(f"  packed X {X.shape} ({X.nbytes/1e9:.1f} GB)", flush=True)

    if stage1:
        # memory-light join: both sides sorted by the (sid, turn, track) triple,
        # then scores scattered back — no pandas merge frames.
        import pyarrow.parquet as pq_
        s1t = pq_.read_table(args.stage1_scores)
        key_left = (slim.session_id + "|" + slim.turn_number.astype(str) + "|"
                    + slim.track_id).to_numpy()
        key_right = np.array([f"{a}|{b}|{c}" for a, b, c in zip(
            s1t.column("session_id").to_pylist(),
            s1t.column("turn_number").to_pylist(),
            s1t.column("track_id").to_pylist())])
        sc = s1t.column("stage1_score").to_numpy(zero_copy_only=False).astype(np.float32)
        del s1t
        lo = np.argsort(key_left, kind="stable")
        ro = np.argsort(key_right, kind="stable")
        assert len(key_left) == len(key_right) and \
            (key_left[lo[:1000]] == key_right[ro[:1000]]).all(), "stage1 rows misaligned"
        col = np.empty(n, dtype=np.float32)
        col[lo] = sc[ro]
        X[:, len(feature_cols)] = col
        feature_cols = feature_cols + ["stage1_score"]
        del key_left, key_right, sc, lo, ro, col
        gc.collect()
        print("  joined stage1_score (sorted alignment)", flush=True)

    # user-grouped split
    sess_user = {str(r["session_id"]): str(r["user_id"])
                 for r in json.load(open(args.ground_truth))}
    sids_all = sorted(slim.session_id.unique())
    users = sorted({sess_user.get(s, s) for s in sids_all})
    rng = random.Random(args.seed)
    rng.shuffle(users)
    n_u = len(users)
    train_users = set(users[: int(0.7 * n_u)])
    val_users = set(users[int(0.7 * n_u): int(0.85 * n_u)])
    train_sids = {s for s in sids_all if sess_user.get(s, s) in train_users}
    val_sids = {s for s in sids_all if sess_user.get(s, s) in val_users}
    test_sids = set(sids_all) - train_sids - val_sids
    u = lambda S: {sess_user.get(s) for s in S}
    assert not (u(train_sids) & u(test_sids)) and not (u(train_sids) & u(val_sids)) \
        and not (u(val_sids) & u(test_sids)), "user leakage across split"
    print(f"  users={n_u} sessions tr/va/te = {len(train_sids)}/{len(val_sids)}/{len(test_sids)}",
          flush=True)

    # drop GT-less groups (after pool-rank filter some turns lose their GT)
    grp_has_gt = slim.groupby(["session_id", "turn_number"])["label"].transform("max").to_numpy() == 1
    sid_arr = slim.session_id.to_numpy()
    membership = np.full(n, 2, dtype=np.int8)  # 0 train 1 val 2 test
    membership[np.isin(sid_arr, list(train_sids))] = 0
    membership[np.isin(sid_arr, list(val_sids))] = 1

    # user-dropout on TRAIN rows only
    if args.user_dropout > 0:
        drop_sids = {s for s in sorted(train_sids) if rng.random() < args.user_dropout}
        dmask = np.isin(sid_arr, list(drop_sids))
        for col, fill in [("user_cf", 0.0), ("pct_user_cf", 0.5), ("has_user_vec", 0.0)]:
            if col in feature_cols:
                X[dmask, feature_cols.index(col)] = fill
        print(f"  user-dropout on {len(drop_sids)} train sessions", flush=True)

    # group ordering: lexsort by (session, turn) within each membership slice
    turn_arr = slim.turn_number.to_numpy()
    sid_codes = pd.factorize(sid_arr, sort=True)[0]

    def split_arrays(mem_val, require_gt=True):
        mask = membership == mem_val
        if require_gt:
            mask = mask & grp_has_gt
        idx = np.flatnonzero(mask)
        order = np.lexsort((turn_arr[idx], sid_codes[idx]))
        idx = idx[order]
        keys = sid_codes[idx].astype(np.int64) * 100 + turn_arr[idx]
        _, starts = np.unique(keys, return_index=True)
        starts = np.sort(starts)
        groups = np.diff(np.append(starts, len(idx)))
        return idx, groups

    arms = {
        "full": list(range(len(feature_cols))),
        "no_pool": [j for j, c in enumerate(feature_cols)
                    if not c.startswith(POOL_PREFIXES) and c not in POOL_COLS],
    }

    tr_idx, tr_groups = split_arrays(0)
    va_idx, va_groups = split_arrays(1)
    te_idx, _ = split_arrays(2)
    test_slim = slim.iloc[te_idx].copy()
    rrf_scores = None
    rrf_path_cols = [c for c in names if c == "rrf_rank"]
    if rrf_path_cols:
        import pyarrow.dataset as pds2
        rrf_tbl = pds2.dataset(args.features).to_table(
            columns=["session_id", "turn_number", "track_id", "rrf_rank"], filter=filt)
        rrf_df = rrf_tbl.to_pandas()
        test_slim = test_slim.merge(rrf_df, on=["session_id", "turn_number", "track_id"], how="left")
        del rrf_tbl, rrf_df

    rrf_m = turn_metrics(test_slim, "rrf_rank", ascending=True)
    report = {"n_test_turns": len(rrf_m),
              "rrf": {"ndcg20": float(rrf_m.ndcg20.mean()),
                      "hit20": float(rrf_m.hit20.mean()), "hit1": float(rrf_m.hit1.mean())}}
    lines = [f"# Reranker — packed-matrix trainer ({pd.Timestamp.now().date()})",
             f"\nTest: {len(test_sids)} sessions, {len(rrf_m)} playable turns. RRF: "
             f"ndcg20={report['rrf']['ndcg20']:.4f} hit20={report['rrf']['hit20']:.4f}\n",
             "| arm | ndcg@20 | Δ vs RRF | t | hit@20 | hit@1 | best_iter | val ndcg@20 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]

    for arm_name, col_idx in arms.items():
        print(f"arm {arm_name}: {len(col_idx)} features", flush=True)
        cat_features = [k for k, j in enumerate(col_idx) if j in cat_idx_map]
        bin_tr = out / f"train_{arm_name}.bin"
        bin_va = out / f"val_{arm_name}.bin"
        if args.reuse_bins and bin_tr.exists() and bin_va.exists():
            dtrain = lgb.Dataset(str(bin_tr), free_raw_data=True)
            dval = lgb.Dataset(str(bin_va), free_raw_data=True, reference=dtrain)
        else:
            Xtr = np.ascontiguousarray(X[tr_idx][:, col_idx])
            dtrain = lgb.Dataset(Xtr, label=y[tr_idx], group=tr_groups,
                                 feature_name=[feature_cols[j] for j in col_idx],
                                 categorical_feature=cat_features,
                                 free_raw_data=True)
            dtrain.construct()
            bin_tr.unlink(missing_ok=True)
            dtrain.save_binary(str(bin_tr))
            del Xtr
            gc.collect()
            Xva = np.ascontiguousarray(X[va_idx][:, col_idx])
            dval = lgb.Dataset(Xva, label=y[va_idx], group=va_groups,
                               feature_name=[feature_cols[j] for j in col_idx],
                               categorical_feature=cat_features,
                               reference=dtrain, free_raw_data=True)
            dval.construct()
            bin_va.unlink(missing_ok=True)
            dval.save_binary(str(bin_va))
            del Xva
            gc.collect()

        evals = {}
        booster = lgb.train(
            LGB_PARAMS, dtrain, num_boost_round=args.num_boost_round,
            valid_sets=[dval], valid_names=["val"],
            callbacks=[lgb.early_stopping(args.early_stopping, verbose=False),
                       lgb.record_evaluation(evals), lgb.log_evaluation(400)])
        booster.save_model(str(out / f"model_{arm_name}.txt"))
        val_best = float(max(evals["val"]["ndcg@20"])) if evals.get("val") else float("nan")

        test_slim["_score"] = booster.predict(X[te_idx][:, col_idx])
        mm = turn_metrics(test_slim, "_score", ascending=False)
        merged = rrf_m.merge(mm, on=["session_id", "turn_number"], suffixes=("_rrf", "_m"))
        d = merged.ndcg20_m - merged.ndcg20_rrf
        t = d.mean() / (d.std() / math.sqrt(len(d)))
        report[arm_name] = {
            "ndcg20": float(mm.ndcg20.mean()), "hit20": float(mm.hit20.mean()),
            "hit1": float(mm.hit1.mean()), "delta_ndcg20": float(d.mean()), "t": float(t),
            "best_iteration": int(booster.best_iteration), "val_ndcg20": val_best,
        }
        imp = pd.Series(booster.feature_importance("gain"),
                        index=[feature_cols[j] for j in col_idx]).sort_values(ascending=False)
        report[arm_name]["top_features"] = {k: float(v) for k, v in imp.head(30).items()}
        lines.append(f"| {arm_name} | {report[arm_name]['ndcg20']:.4f} | {d.mean():+.4f} | "
                     f"{t:+.2f} | {report[arm_name]['hit20']:.4f} | "
                     f"{report[arm_name]['hit1']:.4f} | {booster.best_iteration} | {val_best:.4f} |")
        if arm_name == "full":
            cohort = merged.copy()
            cohort["request_type"] = cohort.get("request_type_m", "")
            cohort["goal_category"] = cohort.get("goal_category_m", "")
            cohort["warm_user"] = cohort.get("warm_user_m", 1.0)
            lines.append("\n## Per-cohort (full arm vs RRF, test)\n")
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
            lines.append("| feature | gain |")
            lines.append("|---|---:|")
            for k, v in imp.head(25).items():
                lines.append(f"| {k} | {v:.0f} |")
        del dtrain, dval
        gc.collect()

    (out / "report.json").write_text(json.dumps(report, indent=2))
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: (v if k != "rrf" else v) for k, v in report.items()
                      if k in ("rrf", "full", "no_pool")}, indent=2, default=str)[:1200], flush=True)
    print(f"wrote {out}/report.md", flush=True)


if __name__ == "__main__":
    main()
