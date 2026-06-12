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
    ap.add_argument("--extra-features", default="",
                    help="Sidecar parquet keyed by (session_id, turn_number, "
                         "track_id); all other columns joined as features via "
                         "sorted alignment.")
    ap.add_argument("--monotone", action="store_true",
                    help="Apply monotone-decreasing constraints to violation "
                         "features (is_played_track, rejected_*_exact, "
                         "violates_new_artist).")
    ap.add_argument("--derive-interactions", action="store_true",
                    help="Append hand-built interaction/consensus features "
                         "(similarity-family products+aggregates, branch-family "
                         "hits, rank variance) — the explicit version of what "
                         "stage1_score and n_branches capture implicitly. "
                         "Excludes mean-reciprocal-rank (== RRF, banned).")
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
    names = dataset.schema.names

    # ids/label/cohorts as a slim pandas frame (small column subset only)
    slim_cols = [c for c in dict.fromkeys(ID_COLS + COHORT_COLS) if c in names]
    slim = dataset.to_table(columns=slim_cols, filter=filt).to_pandas()
    n = len(slim)
    print(f"  {n:,} rows, {len(names)} cols", flush=True)

    feature_cols = [c for c in names if c not in ID_COLS and c not in RRF_COLS]
    stage1 = args.stage1_scores != ""
    extra_names = []
    if args.extra_features:
        import pyarrow.parquet as pq_meta
        extra_names = [c for c in pq_meta.read_schema(args.extra_features).names
                       if c not in ("session_id", "turn_number", "track_id")]
    cat_idx_map = {}

    def derived_spec(cols):
        have = set(cols)
        SIM = [c for c in ["cf_last", "cf_centroid", "user_cf", "clap_last",
                           "clap_centroid", "siglip_centroid", "msg_meta_cos",
                           "msg_attr_cos", "q06_metadata_cos", "tag_emb_cos"]
               if c in have]
        PRODUCTS = [(a, b) for a, b in
                    [("user_cf", "cf_last"), ("user_cf", "cf_centroid"),
                     ("cf_last", "cf_centroid"), ("cf_centroid", "clap_centroid"),
                     ("cf_last", "clap_last"), ("msg_meta_cos", "cf_centroid"),
                     ("user_cf", "msg_meta_cos"), ("clap_centroid", "siglip_centroid")]
                    if a in have and b in have]
        FAMILIES = {
            "fam_text": [c for c in cols if c.startswith("hit__") and ("bm25" in c or "qwen" in c)],
            "fam_audio": [c for c in cols if c.startswith("hit__") and ("clap" in c or "audio" in c)],
            "fam_visual": [c for c in cols if c.startswith("hit__") and "siglip" in c],
            "fam_cf": [c for c in cols if c.startswith("hit__") and "cf_bpr" in c],
            "fam_lookup": [c for c in cols if c.startswith("hit__") and "lookup" in c],
        }
        names_out = ([f"x_{a}__{b}" for a, b in PRODUCTS]
                     + ["sim_mean", "sim_std", "sim_min", "sim_max"]
                     + list(FAMILIES) + ["fam_count", "rank_var_hit", "rank_gap12"])
        return SIM, PRODUCTS, FAMILIES, names_out

    _base_cols = ([c for c in names if c not in ID_COLS and c not in RRF_COLS]
                  + (["stage1_score"] if args.stage1_scores else []) + extra_names)
    _SIM, _PRODUCTS, _FAMILIES, _DERIVED_NAMES = derived_spec(_base_cols) \
        if args.derive_interactions else ([], [], {}, [])
    N_DERIVED = len(_DERIVED_NAMES)
    X = np.empty((n, len(feature_cols) + (1 if stage1 else 0) + len(extra_names)
                  + N_DERIVED), dtype=np.float32)
    for j, c in enumerate(feature_cols):
        # column-streaming: one ~160MB column in memory at a time, never the
        # full float64 table (which was ~20GB and thrashed the 18GB machine)
        col = dataset.to_table(columns=[c], filter=filt).column(c)
        if c in CATEGORICALS:
            codes, _ = pd.factorize(col.to_pandas().fillna(""), sort=True)
            X[:, j] = codes.astype(np.float32)
            cat_idx_map[j] = c
        else:
            X[:, j] = np.nan_to_num(
                col.to_numpy(zero_copy_only=False).astype(np.float32, copy=False), nan=0.0)
        del col
    y = dataset.to_table(columns=["label"], filter=filt).column("label").to_numpy(
        zero_copy_only=False).astype(np.int8)
    gc.collect()
    print(f"  packed X {X.shape} ({X.nbytes/1e9:.1f} GB)", flush=True)

    # int-key join machinery (string keys at 20M rows cost ~5GB; ints ~160MB)
    _sid_code = {v: i for i, v in enumerate(pd.unique(slim.session_id))}
    _trk_code = {v: i for i, v in enumerate(pd.unique(slim.track_id))}

    def _int_keys(sids, turns, tracks):
        out = np.empty(len(sids), dtype=np.int64)
        for i, (a, b, c) in enumerate(zip(sids, turns, tracks)):
            out[i] = ((_sid_code[a] * 10 + int(b)) * 50000) + _trk_code[c]
        return out

    key_left = _int_keys(slim.session_id.to_numpy(), slim.turn_number.to_numpy(),
                         slim.track_id.to_numpy())
    lo = np.argsort(key_left, kind="stable")

    def _aligned_join(path, col_names, base):
        import pyarrow.parquet as pq_
        t = pq_.read_table(path)
        key_right = _int_keys(t.column("session_id").to_pylist(),
                              t.column("turn_number").to_pylist(),
                              t.column("track_id").to_pylist())
        ro = np.argsort(key_right, kind="stable")
        assert len(key_right) == n and (key_left[lo] == key_right[ro]).all(), \
            f"{path}: rows misaligned"
        for k, cname in enumerate(col_names):
            vals = t.column(cname).to_numpy(zero_copy_only=False).astype(np.float32)
            col = np.empty(n, dtype=np.float32)
            col[lo] = vals[ro]
            X[:, base + k] = col
        del t, key_right, ro
        gc.collect()

    if stage1:
        _aligned_join(args.stage1_scores, ["stage1_score"], len(feature_cols))
        print("  joined stage1_score (int-key alignment)", flush=True)

    if extra_names:
        _aligned_join(args.extra_features, extra_names,
                      len(feature_cols) + (1 if stage1 else 0))
        print(f"  joined {len(extra_names)} extra features (int-key alignment)", flush=True)

    del key_left, lo
    gc.collect()
    if stage1:
        feature_cols = feature_cols + ["stage1_score"]
    if extra_names:
        feature_cols = feature_cols + extra_names

    if args.derive_interactions:
        ci = {c: i for i, c in enumerate(feature_cols)}
        SIM, PRODUCTS, FAMILIES = _SIM, _PRODUCTS, _FAMILIES
        rank_cols = [c for c in feature_cols if c.startswith("rank__")]
        new_names = _DERIVED_NAMES
        print(f"  derived spec: {len(PRODUCTS)} products, {len(SIM)} sims, "
              f"{len(FAMILIES)} families -> {len(new_names)} cols", flush=True)
        dbase = X.shape[1] - N_DERIVED  # tail-anchored: immune to bookkeeping drift
        Xd = X[:, dbase:]
        assert Xd.shape[1] == N_DERIVED, (Xd.shape, N_DERIVED)
        k = 0
        for a, b in PRODUCTS:
            Xd[:, k] = X[:, ci[a]] * X[:, ci[b]]; k += 1
        simM = X[:, [ci[c] for c in SIM]]
        Xd[:, k] = simM.mean(axis=1); k += 1
        Xd[:, k] = simM.std(axis=1); k += 1
        Xd[:, k] = simM.min(axis=1); k += 1
        Xd[:, k] = simM.max(axis=1); k += 1
        fam_start = k
        for fam, cols in FAMILIES.items():
            Xd[:, k] = (X[:, [ci[c] for c in cols]].max(axis=1)
                        if cols else 0.0); k += 1
        Xd[:, k] = Xd[:, fam_start:k].sum(axis=1); k += 1
        # rank variance + best/second gap among HITTING branches (sentinel 501 = miss)
        R = X[:, [ci[c] for c in rank_cols]].copy()
        R[R > 500] = np.nan
        with np.errstate(invalid="ignore"):
            Xd[:, k] = np.nan_to_num(np.nanstd(R, axis=1), nan=0.0); k += 1
            Rs = np.sort(np.nan_to_num(R, nan=1e9), axis=1)
            gap = Rs[:, 1] - Rs[:, 0]
            gap[Rs[:, 1] >= 1e9] = 0.0
            Xd[:, k] = gap; k += 1
        del simM, R, Rs
        gc.collect()
        feature_cols = feature_cols + new_names
        print(f"  derived {len(new_names)} interaction/consensus features", flush=True)

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
        rrf_df = rrf_df[rrf_df.session_id.isin(test_sids)]
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

        params = dict(LGB_PARAMS)
        if args.monotone:
            # ONLY is_played_track: mechanically guaranteed by the generator
            # (no-replay; 0/8000 replays measured). Artist/new-artist rejections
            # are SOFT — the generator recycles them (judgment pass: 7/13
            # contradictory GTs) — so they stay unconstrained features.
            MONO = {"is_played_track": -1}
            mono = [MONO.get(feature_cols[j], 0) for j in col_idx]
            if any(mono):
                params["monotone_constraints"] = mono
                print(f"  monotone constraints on "
                      f"{[feature_cols[j] for j in col_idx if MONO.get(feature_cols[j])]}",
                      flush=True)
        evals = {}
        booster = lgb.train(
            params, dtrain, num_boost_round=args.num_boost_round,
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
