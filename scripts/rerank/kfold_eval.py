"""5-fold user-grouped CV: the honest full-devset 'reranker replaces RRF' metric.

Every devset turn is scored by a model whose training folds exclude that
turn's user. Output: full-8000-turn nDCG@20 / hit@k where non-playable turns
(GT outside union@500) score 0 — directly comparable to production's 0.1374.

Reuses the v7b configuration: features_v3 + two-tower stage1 + constraint
sidecar + monotone(is_played_track).
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

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", default="exp/analysis/rerank/features_v3")
    ap.add_argument("--stage1-scores", default="exp/analysis/nextplay_v2/devset_pool_scores_v3.parquet")
    ap.add_argument("--extra-features", default="exp/analysis/rerank/constraint_features.parquet")
    ap.add_argument("--ground-truth", default="exp/ground_truth/devset.json")
    ap.add_argument("--out-dir", default="exp/analysis/rerank/kfold_v7b")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--num-boost-round", type=int, default=1500)
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
    width = len(feature_cols) + 1 + len(extra_names)
    X = np.empty((n, width), dtype=np.float32)
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

    # sorted-alignment joins (same triples, verified)
    key_left = (slim.session_id + "|" + slim.turn_number.astype(str) + "|" + slim.track_id).to_numpy()
    lo = np.argsort(key_left, kind="stable")

    def join(path, col_names, base):
        t = pq_.read_table(path)
        key_right = np.array([f"{a}|{b}|{c}" for a, b, c in zip(
            t.column("session_id").to_pylist(),
            t.column("turn_number").to_pylist(),
            t.column("track_id").to_pylist())])
        ro = np.argsort(key_right, kind="stable")
        assert len(key_right) == n and (key_left[lo] == key_right[ro]).all()
        for k, cname in enumerate(col_names):
            vals = t.column(cname).to_numpy(zero_copy_only=False).astype(np.float32)
            col = np.empty(n, dtype=np.float32)
            col[lo] = vals[ro]
            X[:, base + k] = col

    join(args.stage1_scores, ["stage1_score"], len(feature_cols))
    join(args.extra_features, extra_names, len(feature_cols) + 1)
    all_cols = feature_cols + ["stage1_score"] + extra_names
    print(f"packed X {X.shape}", flush=True)

    mono = [(-1 if c == "is_played_track" else 0) for c in all_cols]
    params = dict(LGB_PARAMS, monotone_constraints=mono)

    sess_user = {str(r["session_id"]): str(r["user_id"])
                 for r in json.load(open(args.ground_truth))}
    sids_all = sorted(slim.session_id.unique())
    users = sorted({sess_user.get(s, s) for s in sids_all})
    rng = random.Random(args.seed)
    rng.shuffle(users)
    fold_of_user = {u: i % args.folds for i, u in enumerate(users)}
    sid_fold = np.array([fold_of_user[sess_user.get(s, s)] for s in slim.session_id])

    sid_codes = pd.factorize(slim.session_id, sort=True)[0]
    turn_arr = slim.turn_number.to_numpy()
    scores_all = np.full(n, np.nan, dtype=np.float32)

    def grouped(idx):
        order = np.lexsort((turn_arr[idx], sid_codes[idx]))
        idx = idx[order]
        keys = sid_codes[idx].astype(np.int64) * 100 + turn_arr[idx]
        _, starts = np.unique(keys, return_index=True)
        groups = np.diff(np.append(np.sort(starts), len(idx)))
        return idx, groups

    for fold in range(args.folds):
        tr_idx = np.flatnonzero(sid_fold != fold)
        te_idx = np.flatnonzero(sid_fold == fold)
        tr_idx, tr_groups = grouped(tr_idx)
        Xtr = np.ascontiguousarray(X[tr_idx])
        dtrain = lgb.Dataset(Xtr, label=y[tr_idx], group=tr_groups,
                             feature_name=all_cols,
                             categorical_feature=cat_idx, free_raw_data=True)
        dtrain.construct()
        del Xtr
        gc.collect()
        booster = lgb.train(params, dtrain, num_boost_round=args.num_boost_round)
        scores_all[te_idx] = booster.predict(X[te_idx])
        booster.save_model(str(out / f"model_fold{fold}.txt"))
        del dtrain
        gc.collect()
        print(f"fold {fold} done", flush=True)

    slim["score"] = scores_all
    assert not np.isnan(scores_all).any()

    # full-devset metrics: playable turns ranked, non-playable scored 0
    per_turn = []
    for (sid, tn), g in slim.groupby(["session_id", "turn_number"], sort=False):
        gt = g.label == 1
        if not gt.any():
            continue
        order = g.score.rank(ascending=False, method="first")
        r = float(order[gt].iloc[0])
        per_turn.append((sid, tn, r))
    pt = pd.DataFrame(per_turn, columns=["session_id", "turn_number", "gt_rank"])
    n_total = 8000
    n_playable = len(pt)
    res = {}
    for k in (1, 5, 10, 20, 50):
        res[f"hit@{k}"] = float((pt.gt_rank <= k).sum() / n_total)
    res["ndcg@20"] = float(sum(1 / math.log2(r + 1) for r in pt.gt_rank if r <= 20) / n_total)
    res["n_playable"] = n_playable
    res["playable_share"] = n_playable / n_total
    res["conditional_ndcg@20"] = res["ndcg@20"] * n_total / n_playable
    (out / "metrics.json").write_text(json.dumps(res, indent=2))
    pt.to_parquet(out / "per_turn_ranks.parquet")
    print(json.dumps(res, indent=2), flush=True)


if __name__ == "__main__":
    main()
