"""5-fold CV v2 — the honest-by-construction full-devset metric.

Protocol upgrades over kfold_eval.py (all from the 2026-06-12 honesty audit):
- LOCKBOX: 20% of users (frozen in exp/analysis/rerank/lockbox_users.json)
  excluded from every fold's training; their turns scored ONCE by fold-0's
  model. Selection can never touch them.
- NESTED EARLY STOPPING: each fold carves 15% of its train users as fold-val
  for early stopping (the audit measured fixed-1500-rounds at -0.014).
- v8 config: derived interaction/consensus features + constraint sidecar +
  monotone(is_played_track), NO stage1/two-tower dependency.

Outputs full-8000-turn metrics (non-playable turns score 0) split into
cv (400 users) / lockbox (100 users) / combined.
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
RRF_COLS = ["rrf_rank", "rrf_score", "pct_rrf_score"]
CATEGORICALS = ["age_group", "gender", "goal_category", "goal_specificity",
                "request_type", "intent_mode", "target_artist_mode",
                "temporal_strength"]

LGB_PARAMS = dict(
    objective="lambdarank", learning_rate=0.025, num_leaves=127,
    min_data_in_leaf=50, lambdarank_truncation_level=200,
    metric="ndcg", ndcg_eval_at=[20], verbosity=-1, num_threads=0,
)


def derived_spec(cols):
    have = set(cols)
    SIM = [c for c in ["cf_last", "cf_centroid", "user_cf", "clap_last",
                       "clap_centroid", "siglip_centroid", "msg_meta_cos",
                       "msg_attr_cos", "q06_metadata_cos", "tag_emb_cos"] if c in have]
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", default="exp/analysis/rerank/features_v4")
    ap.add_argument("--extra-features", default="exp/analysis/rerank/constraint_features_v4.parquet")
    ap.add_argument("--ground-truth", default="exp/ground_truth/devset.json")
    ap.add_argument("--lockbox", default="exp/analysis/rerank/lockbox_users.json")
    ap.add_argument("--out-dir", default="exp/analysis/rerank/kfold_v8_bugfix")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--num-boost-round", type=int, default=3000)
    ap.add_argument("--early-stopping", type=int, default=150)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    import pyarrow.dataset as pds
    import pyarrow.parquet as pq_

    dataset = pds.dataset(args.features)
    names = dataset.schema.names
    slim = dataset.to_table(
        columns=["session_id", "turn_number", "track_id", "label"]).to_pandas()
    n = len(slim)
    print(f"{n:,} rows", flush=True)

    feature_cols = [c for c in names if c not in ID_COLS and c not in RRF_COLS]
    extra_names = [c for c in pq_.read_schema(args.extra_features).names
                   if c not in ("session_id", "turn_number", "track_id")]
    base_cols = feature_cols + extra_names
    SIM, PRODUCTS, FAMILIES, derived_names = derived_spec(base_cols)
    all_cols = base_cols + derived_names
    X = np.empty((n, len(all_cols)), dtype=np.float32)
    cat_idx = []
    for j, c in enumerate(feature_cols):
        col = dataset.to_table(columns=[c]).column(c)
        if c in CATEGORICALS:
            codes, _ = pd.factorize(col.to_pandas().fillna(""), sort=True)
            X[:, j] = codes.astype(np.float32)
            cat_idx.append(j)
        else:
            X[:, j] = np.nan_to_num(
                col.to_numpy(zero_copy_only=False).astype(np.float32, copy=False), nan=0.0)
        del col
    y = slim.label.to_numpy().astype(np.int8)
    gc.collect()

    # int-key sidecar join
    sid_code = {v: i for i, v in enumerate(pd.unique(slim.session_id))}
    trk_code = {v: i for i, v in enumerate(pd.unique(slim.track_id))}

    def int_keys(sids, turns, tracks):
        o = np.empty(len(sids), dtype=np.int64)
        for i, (a, b, c) in enumerate(zip(sids, turns, tracks)):
            o[i] = ((sid_code[a] * 10 + int(b)) * 50000) + trk_code[c]
        return o

    kl = int_keys(slim.session_id.to_numpy(), slim.turn_number.to_numpy(),
                  slim.track_id.to_numpy())
    lo = np.argsort(kl, kind="stable")
    ext = pq_.read_table(args.extra_features)
    kr = int_keys(ext.column("session_id").to_pylist(),
                  ext.column("turn_number").to_pylist(),
                  ext.column("track_id").to_pylist())
    ro = np.argsort(kr, kind="stable")
    assert len(kr) == n and (kl[lo] == kr[ro]).all(), "sidecar misaligned"
    for k, cname in enumerate(extra_names):
        v = ext.column(cname).to_numpy(zero_copy_only=False).astype(np.float32)
        col = np.empty(n, dtype=np.float32)
        col[lo] = v[ro]
        X[:, len(feature_cols) + k] = col
    del ext, kr, ro, kl, lo
    gc.collect()

    # derived features into the tail
    ci = {c: i for i, c in enumerate(base_cols)}
    dbase = X.shape[1] - len(derived_names)
    Xd = X[:, dbase:]
    assert Xd.shape[1] == len(derived_names)
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
        Xd[:, k] = X[:, [ci[c] for c in cols]].max(axis=1) if cols else 0.0; k += 1
    Xd[:, k] = Xd[:, fam_start:k].sum(axis=1); k += 1
    rank_cols = [c for c in base_cols if c.startswith("rank__")]
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
    print(f"packed X {X.shape} ({X.nbytes/1e9:.1f} GB), {len(all_cols)} features", flush=True)

    mono = [(-1 if c == "is_played_track" else 0) for c in all_cols]
    params = dict(LGB_PARAMS, monotone_constraints=mono)

    sess_user = {str(r["session_id"]): str(r["user_id"])
                 for r in json.load(open(args.ground_truth))}
    lockbox_users = set(json.load(open(args.lockbox))["users"])
    sids_all = sorted(slim.session_id.unique())
    cv_users = sorted({sess_user.get(s, s) for s in sids_all} - lockbox_users)
    rng = random.Random(args.seed)
    rng.shuffle(cv_users)
    fold_of_user = {u: i % args.folds for i, u in enumerate(cv_users)}
    user_arr = np.array([sess_user.get(s, s) for s in slim.session_id])
    sid_fold = np.array([fold_of_user.get(u, -1) for u in user_arr])  # -1 = lockbox
    print(f"cv users {len(cv_users)}, lockbox {len(lockbox_users)}; "
          f"lockbox rows {(sid_fold == -1).sum():,}", flush=True)

    sid_codes = pd.factorize(slim.session_id, sort=True)[0]
    turn_arr = slim.turn_number.to_numpy()

    def grouped(idx):
        order = np.lexsort((turn_arr[idx], sid_codes[idx]))
        idx = idx[order]
        keys = sid_codes[idx].astype(np.int64) * 100 + turn_arr[idx]
        _, starts = np.unique(keys, return_index=True)
        groups = np.diff(np.append(np.sort(starts), len(idx)))
        return idx, groups

    scores_all = np.full(n, np.nan, dtype=np.float32)
    best_iters = []
    for fold in range(args.folds):
        # nested split: 15% of this fold's TRAIN users -> early-stop val
        tr_users = [u for u, f in fold_of_user.items() if f != fold]
        rng_f = random.Random(args.seed * 100 + fold)
        rng_f.shuffle(tr_users)
        n_va = max(1, int(0.15 * len(tr_users)))
        va_set = set(tr_users[:n_va])
        tr_set = set(tr_users[n_va:])
        tr_mask = np.isin(user_arr, list(tr_set))
        va_mask = np.isin(user_arr, list(va_set))
        te_mask = sid_fold == fold
        tr_idx, tr_groups = grouped(np.flatnonzero(tr_mask))
        va_idx, va_groups = grouped(np.flatnonzero(va_mask))
        Xtr = np.ascontiguousarray(X[tr_idx])
        dtrain = lgb.Dataset(Xtr, label=y[tr_idx], group=tr_groups,
                             feature_name=all_cols, categorical_feature=cat_idx,
                             free_raw_data=True)
        dtrain.construct()
        del Xtr; gc.collect()
        Xva = np.ascontiguousarray(X[va_idx])
        dval = lgb.Dataset(Xva, label=y[va_idx], group=va_groups,
                           feature_name=all_cols, categorical_feature=cat_idx,
                           reference=dtrain, free_raw_data=True)
        dval.construct()
        del Xva; gc.collect()
        booster = lgb.train(params, dtrain, num_boost_round=args.num_boost_round,
                            valid_sets=[dval], valid_names=["val"],
                            callbacks=[lgb.early_stopping(args.early_stopping, verbose=False)])
        best_iters.append(booster.best_iteration)
        te_idx = np.flatnonzero(te_mask)
        scores_all[te_idx] = booster.predict(X[te_idx],
                                             num_iteration=booster.best_iteration)
        booster.save_model(str(out / f"model_fold{fold}.txt"))
        if fold == 0:
            lb_idx = np.flatnonzero(sid_fold == -1)
            scores_all[lb_idx] = booster.predict(X[lb_idx],
                                                 num_iteration=booster.best_iteration)
        del dtrain, dval; gc.collect()
        print(f"fold {fold} done (best_iter {booster.best_iteration})", flush=True)

    assert not np.isnan(scores_all).any()
    slim["score"] = scores_all
    slim["is_lockbox"] = sid_fold == -1

    def metrics(df, n_total):
        rows = []
        for (sid, tn), g in df.groupby(["session_id", "turn_number"], sort=False):
            gt = g.label == 1
            if not gt.any():
                continue
            r = float(g.score.rank(ascending=False, method="first")[gt].iloc[0])
            rows.append(r)
        res = {f"hit@{k}": float(sum(1 for r in rows if r <= k) / n_total)
               for k in (1, 5, 10, 20, 50)}
        res["ndcg@20"] = float(sum(1 / math.log2(r + 1) for r in rows if r <= 20) / n_total)
        res["n_playable"] = len(rows)
        res["n_total"] = n_total
        return res

    gt_rows = json.load(open(args.ground_truth))
    lb_sids = {str(r["session_id"]) for r in gt_rows
               if str(r["user_id"]) in lockbox_users}
    n_lb_turns = sum(1 for r in gt_rows if str(r["user_id"]) in lockbox_users)
    n_cv_turns = len(gt_rows) - n_lb_turns
    report = {
        "combined": metrics(slim, len(gt_rows)),
        "cv_only": metrics(slim[~slim.is_lockbox], n_cv_turns),
        "lockbox_only": metrics(slim[slim.is_lockbox], n_lb_turns),
        "best_iters": best_iters,
    }
    (out / "metrics.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
