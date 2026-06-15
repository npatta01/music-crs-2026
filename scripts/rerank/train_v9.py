"""v9 reranker training — user-grouped 5-fold CV + lockbox + label weights.

Protocol (locked):
- features_v9 (NaN-missing preserved; LightGBM native missing handling)
- model features = all columns minus ids/label minus rrf_rank/rrf_score
  (rrf kept in the parquet only as the eval baseline)
- user-grouped folds (seed 13), lockbox users (exp/analysis/rerank/
  lockbox_users.json) excluded from CV and scored by the 5-fold ensemble
- nested early stopping: 10% of each fold's TRAIN users held out for ES
- per-row sample weights from label_weights_v9 (turn-level label quality)
- monotone constraint: is_played_track -1
- selection metric: plain all-turns OOF ndcg@20 (by-turn reported as diagnostic)

Memory recipe (18GB machine, hard-won): stream-build a float32 disk memmap with
per-batch flush; ONE PROCESS PER FOLD (driver below) so each fold's contiguous
train copy is reclaimed by the OS on exit.

  # build matrix + folds, then run folds sequentially, then finalize:
  python scripts/rerank/train_v9.py --stage build
  for f in 0 1 2 3 4; do python scripts/rerank/train_v9.py --stage fold --fold $f; done
  python scripts/rerank/train_v9.py --stage finalize
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "exp/analysis/rerank/train_v9"
FEATURES = ROOT / "exp/analysis/rerank/features_v9"
SIDECAR = ROOT / "exp/analysis/rerank/constraint_features.parquet"
WEIGHTS = ROOT / "exp/analysis/rerank/label_weights_v9.parquet"
GT_PATH = ROOT / "exp/ground_truth/devset.json"
LOCKBOX = ROOT / "exp/analysis/rerank/lockbox_users.json"

ID_COLS = ["session_id", "turn_number", "track_id", "label"]
EVAL_ONLY = ["rrf_rank", "rrf_score"]
# Monotone-decreasing features: higher value can only LOWER the score. Replay
# prevention (is_played_track) plus the pivot-away demote signals — a candidate
# that IS the artist the user pivoted away from must not be promoted over a
# fresh artist (over-anchor fix, knowledge/overanchor_report.html).
MONOTONE_DECREASING = (
    "is_played_track",
    "same_artist_as_abandoned",
    "x_same_artist_wants_new",
    "violates_new_artist",
)
CATEGORICALS = ["age_group", "gender", "goal_category", "goal_specificity",
                "request_type", "intent_mode", "target_artist_mode",
                "temporal_strength"]

LGB_PARAMS = dict(
    objective="lambdarank", learning_rate=0.025, num_leaves=127,
    min_data_in_leaf=50, lambdarank_truncation_level=200,
    metric="ndcg", ndcg_eval_at=[20], verbosity=-1, num_threads=0,
)
N_FOLDS = 5
SEED = 13
ES_ROUNDS = 100
MAX_ROUNDS = 3000


def _ids_and_folds():
    """Shared identity arrays + fold assignment (deterministic)."""
    sid_codes = np.load(OUT / "sid_codes.npy")
    turn_arr = np.load(OUT / "turn_arr.npy")
    sid_uniq = json.load(open(OUT / "sid_uniq.json"))
    meta = json.load(open(OUT / "meta.json"))
    return sid_codes, turn_arr, sid_uniq, meta


def stage_build():
    import pyarrow.dataset as pds
    import pyarrow.parquet as pq

    OUT.mkdir(parents=True, exist_ok=True)
    ds = pds.dataset(str(FEATURES))
    names = ds.schema.names
    feature_cols = [c for c in names if c not in ID_COLS and c not in EVAL_ONLY]
    extra_names = [c for c in pq.read_schema(str(SIDECAR)).names
                   if c not in ("session_id", "turn_number", "track_id")]
    all_cols = feature_cols + extra_names
    n = ds.count_rows()
    print(f"{n:,} rows x {len(all_cols)} model features", flush=True)

    # identities (ints only)
    sid_codes, sid_uniq = pd.factorize(
        ds.to_table(columns=["session_id"]).column("session_id").to_pandas(), sort=True)
    sid_codes = sid_codes.astype(np.int32)
    turn_arr = ds.to_table(columns=["turn_number"]).column("turn_number").to_numpy().astype(np.int8)
    trk_codes, trk_uniq = pd.factorize(
        ds.to_table(columns=["track_id"]).column("track_id").to_pandas(), sort=True)
    trk_codes = trk_codes.astype(np.int32)
    y = ds.to_table(columns=["label"]).column("label").to_numpy().astype(np.int8)
    rrf_rank = ds.to_table(columns=["rrf_rank"]).column("rrf_rank").to_numpy().astype(np.float32)
    np.save(OUT / "sid_codes.npy", sid_codes)
    np.save(OUT / "turn_arr.npy", turn_arr)
    np.save(OUT / "trk_codes.npy", trk_codes)
    np.save(OUT / "y.npy", y)
    np.save(OUT / "rrf_rank.npy", rrf_rank)
    json.dump(list(sid_uniq), open(OUT / "sid_uniq.json", "w"))
    json.dump(list(trk_uniq), open(OUT / "trk_uniq.json", "w"))
    gc.collect()

    # X memmap: numeric streamed (NaN PRESERVED), categoricals factorized
    X = np.lib.format.open_memmap(str(OUT / "X.npy"), mode="w+",
                                  dtype=np.float32, shape=(n, len(all_cols)))
    num_cols = [(j, c) for j, c in enumerate(feature_cols) if c not in CATEGORICALS]
    cursor = 0
    for batch in ds.to_batches(columns=[c for _, c in num_cols], batch_size=2_000_000):
        m = batch.num_rows
        for k, (j, c) in enumerate(num_cols):
            X[cursor:cursor + m, j] = batch.column(k).to_numpy(
                zero_copy_only=False).astype(np.float32)   # NaN preserved
        cursor += m
        X.flush()
        print(f"  numeric {cursor:,}/{n:,}", flush=True)
    cat_maps = {}
    cat_idx = []
    for j, c in enumerate(feature_cols):
        if c not in CATEGORICALS:
            continue
        col = ds.to_table(columns=[c]).column(c)
        codes, uniques = pd.factorize(col.to_pandas().fillna(""), sort=True)
        X[:, j] = codes.astype(np.float32)
        cat_maps[c] = {str(v): i for i, v in enumerate(uniques)}
        cat_idx.append(j)
        del col, codes
        X.flush(); gc.collect()
        print(f"  categorical {c}", flush=True)

    # sidecar join (int keys)
    t = pq.read_table(str(SIDECAR))
    rs = pd.Index(sid_uniq).get_indexer(t.column("session_id").to_pandas()).astype(np.int64)
    rt = pd.Index(trk_uniq).get_indexer(t.column("track_id").to_pandas()).astype(np.int64)
    rturn = t.column("turn_number").to_numpy().astype(np.int64)
    assert (rs >= 0).all() and (rt >= 0).all(), "sidecar keys outside features keyset"
    key_left = (sid_codes.astype(np.int64) * 10 + turn_arr) * len(trk_uniq) + trk_codes
    key_right = (rs * 10 + rturn) * len(trk_uniq) + rt
    lo = np.argsort(key_left, kind="stable")
    ro = np.argsort(key_right, kind="stable")
    assert len(key_right) == n and (key_left[lo] == key_right[ro]).all(), "sidecar keyset mismatch"
    base = len(feature_cols)
    for k, cname in enumerate(extra_names):
        vals = np.nan_to_num(t.column(cname).to_numpy(
            zero_copy_only=False).astype(np.float32), nan=0.0)
        col = np.empty(n, dtype=np.float32)
        col[lo] = vals[ro]
        X[:, base + k] = col
        del col
    del t, key_left, key_right, lo, ro
    X.flush(); gc.collect()
    print("  sidecar joined", flush=True)

    # per-row weights from per-turn label weights
    w = pq.read_table(str(WEIGHTS)).to_pandas()
    wmap = {(r.session_id, int(r.turn_number)): float(r.weight) for r in w.itertuples()}
    row_w = np.fromiter(
        (wmap.get((sid_uniq[s], int(t_)), 1.0) for s, t_ in zip(sid_codes, turn_arr)),
        dtype=np.float32, count=n)
    np.save(OUT / "row_weights.npy", row_w)
    print(f"  weights: mean {row_w.mean():.3f}, <1 share {(row_w < 1).mean():.3f}", flush=True)

    # folds: lockbox users excluded from CV; remaining users -> 5 folds (seed 13);
    # within each fold's train users, 10% (seed 13) held out for early stopping
    sess_user = {str(r["session_id"]): str(r["user_id"]) for r in json.load(open(GT_PATH))}
    _lb_raw = json.load(open(LOCKBOX))
    lockbox_users = set(_lb_raw["users"] if isinstance(_lb_raw, dict) else _lb_raw)
    users = sorted({sess_user.get(s, s) for s in sid_uniq})
    cv_users = [u for u in users if u not in lockbox_users]
    rng = random.Random(SEED)
    rng.shuffle(cv_users)
    fold_of_user = {u: i % N_FOLDS for i, u in enumerate(cv_users)}
    sid_fold = np.array(
        [fold_of_user.get(sess_user.get(s, s), -1) for s in sid_uniq], dtype=np.int8)  # -1 = lockbox
    np.save(OUT / "sid_fold.npy", sid_fold)
    json.dump({"cols": all_cols, "cat_idx": cat_idx, "n": int(n),
               "n_feature_cols": len(feature_cols)},
              open(OUT / "meta.json", "w"))
    json.dump(cat_maps, open(OUT / "cat_maps_v9.json", "w"))
    print(f"build done: lockbox sessions {(sid_fold == -1).sum()} of {len(sid_uniq)}", flush=True)


def _grouped(idx, sid_codes, turn_arr):
    order = np.lexsort((turn_arr[idx], sid_codes[idx]))
    idx = idx[order]
    keys = sid_codes[idx].astype(np.int64) * 10 + turn_arr[idx]
    _, starts = np.unique(keys, return_index=True)
    groups = np.diff(np.append(np.sort(starts), len(idx)))
    return idx, groups


def stage_fold(fold: int):
    import lightgbm as lgb

    sid_codes, turn_arr, sid_uniq, meta = _ids_and_folds()
    sid_fold = np.load(OUT / "sid_fold.npy")
    y = np.load(OUT / "y.npy")
    row_w = np.load(OUT / "row_weights.npy")
    X = np.load(str(OUT / "X.npy"), mmap_mode="r")
    all_cols = meta["cols"]
    cat_idx = meta["cat_idx"]

    row_fold = sid_fold[sid_codes]
    # ES split: 10% of this fold's TRAIN users (deterministic per fold)
    sess_user = {str(r["session_id"]): str(r["user_id"]) for r in json.load(open(GT_PATH))}
    train_users = sorted({sess_user.get(s, s) for i, s in enumerate(sid_uniq)
                          if sid_fold[i] not in (fold, -1)})
    rng = random.Random(1000 + fold)
    rng.shuffle(train_users)
    es_users = set(train_users[: max(1, len(train_users) // 10)])
    sid_es = np.array([sess_user.get(s, s) in es_users for s in sid_uniq])
    row_es = sid_es[sid_codes]

    tr_mask = (row_fold != fold) & (row_fold != -1) & (~row_es)
    es_mask = (row_fold != fold) & (row_fold != -1) & row_es
    tr_idx = np.flatnonzero(tr_mask)
    es_idx = np.flatnonzero(es_mask)
    tr_idx, tr_groups = _grouped(tr_idx, sid_codes, turn_arr)
    es_idx, es_groups = _grouped(es_idx, sid_codes, turn_arr)
    print(f"fold {fold}: train {len(tr_idx):,} rows / es {len(es_idx):,}", flush=True)

    mono = [(-1 if c in MONOTONE_DECREASING else 0) for c in all_cols]
    params = dict(LGB_PARAMS, monotone_constraints=mono)

    Xtr = np.ascontiguousarray(X[tr_idx])
    dtrain = lgb.Dataset(Xtr, label=y[tr_idx], group=tr_groups, weight=row_w[tr_idx],
                         feature_name=all_cols, categorical_feature=cat_idx,
                         free_raw_data=True)
    dtrain.construct()
    del Xtr; gc.collect()
    Xes = np.ascontiguousarray(X[es_idx])
    dvalid = lgb.Dataset(Xes, label=y[es_idx], group=es_groups, weight=row_w[es_idx],
                         reference=dtrain, free_raw_data=False)
    dvalid.construct()
    del Xes; gc.collect()

    booster = lgb.train(params, dtrain, num_boost_round=MAX_ROUNDS,
                        valid_sets=[dvalid], valid_names=["es"],
                        callbacks=[lgb.early_stopping(ES_ROUNDS, verbose=False),
                                   lgb.log_evaluation(200)])
    best = booster.best_iteration or MAX_ROUNDS
    booster.save_model(str(OUT / f"model_fold{fold}.txt"), num_iteration=best)
    del dtrain, dvalid; gc.collect()

    # score this fold's test rows + lockbox rows (chunked from memmap)
    for tag, mask in [("test", row_fold == fold), ("lockbox", row_fold == -1)]:
        idx = np.flatnonzero(mask)
        scores = np.empty(len(idx), dtype=np.float32)
        for lo_i in range(0, len(idx), 2_000_000):
            sl = idx[lo_i:lo_i + 2_000_000]
            scores[lo_i:lo_i + len(sl)] = booster.predict(
                X[sl], num_iteration=best)
            gc.collect()
        np.save(OUT / f"scores_{tag}_fold{fold}.npy", scores)
        np.save(OUT / f"idx_{tag}_fold{fold}.npy", idx)
    print(f"fold {fold} done: best_iter {best}", flush=True)


def _per_turn_metrics(sub: pd.DataFrame, denom: int):
    res = {}
    pt = []
    for (sid, tn), g in sub.groupby(["sid", "turn"], sort=False):
        gt = g[g.y == 1]
        if not len(gt):
            continue
        r = int((g.score > float(gt.score.iloc[0])).sum()) + 1
        pt.append((sid, int(tn), r))
    ranks = np.array([r for _, _, r in pt])
    for k in (1, 5, 10, 20):
        res[f"hit@{k}"] = float((ranks <= k).sum() / denom)
    res["ndcg@20"] = float(sum(1 / math.log2(r + 1) for r in ranks if r <= 20) / denom)
    res["n_playable"] = int(len(ranks))
    return res, pt


def stage_finalize():
    sid_codes, turn_arr, sid_uniq, meta = _ids_and_folds()
    sid_fold = np.load(OUT / "sid_fold.npy")
    y = np.load(OUT / "y.npy")
    rrf_rank = np.load(OUT / "rrf_rank.npy")
    n = meta["n"]

    scores = np.full(n, np.nan, dtype=np.float32)
    lock_scores = np.zeros(n, dtype=np.float64)
    for f in range(N_FOLDS):
        idx = np.load(OUT / f"idx_test_fold{f}.npy")
        scores[idx] = np.load(OUT / f"scores_test_fold{f}.npy")
        li = np.load(OUT / f"idx_lockbox_fold{f}.npy")
        lock_scores[li] += np.load(OUT / f"scores_lockbox_fold{f}.npy")
    lock_idx = np.flatnonzero(sid_fold[sid_codes] == -1)
    scores[lock_idx] = (lock_scores[lock_idx] / N_FOLDS).astype(np.float32)
    assert not np.isnan(scores).any(), "rows without scores"

    df = pd.DataFrame({
        "sid": np.asarray(sid_uniq, dtype=object)[sid_codes],
        "turn": turn_arr.astype(int), "y": y, "score": scores,
        "rrf_rank": rrf_rank,
        "lockbox": sid_fold[sid_codes] == -1,
    })
    # cold flag per turn from the X column has_user_vec
    X = np.load(str(OUT / "X.npy"), mmap_mode="r")
    huv_col = meta["cols"].index("has_user_vec")
    df["has_user_vec"] = np.asarray(X[:, huv_col])

    gt_rows = json.load(open(GT_PATH))
    denom_all = len(gt_rows)  # 8000

    out = {}
    res, pt = _per_turn_metrics(df, denom_all)
    out["model_full"] = res
    # RRF baseline on identical pools
    rrf_pt = df[df.y == 1][["sid", "turn", "rrf_rank"]]
    rr = rrf_pt.rrf_rank.to_numpy()
    out["rrf_full"] = {
        "ndcg@20": float(sum(1 / math.log2(r + 1) for r in rr if r <= 20) / denom_all),
        "hit@20": float((rr <= 20).sum() / denom_all),
    }
    # cv-only / lockbox-only
    for tag, m in [("cv_only", ~df.lockbox), ("lockbox_only", df.lockbox)]:
        sub = df[m]
        n_sess = sub.sid.nunique()
        if n_sess == 0:
            out[tag] = {"note": "empty subset"}
            continue
        denom = int(n_sess * 8)
        out[tag], _ = _per_turn_metrics(sub, denom)
        rrl = sub[sub.y == 1].rrf_rank.to_numpy()
        out[tag]["rrf_ndcg@20"] = float(sum(1 / math.log2(r + 1) for r in rrl if r <= 20) / denom)
    # cold-user slice (turn-level)
    cold = df[df.has_user_vec == 0]
    cold_sess_turns = cold.groupby(["sid", "turn"]).ngroups
    if cold_sess_turns:
        res_c, _ = _per_turn_metrics(cold, cold_sess_turns)
        rrc = cold[cold.y == 1].rrf_rank.to_numpy()
        res_c["rrf_ndcg@20"] = float(sum(1 / math.log2(r + 1) for r in rrc if r <= 20) / cold_sess_turns)
        res_c["note"] = "conditional (denominator = cold playable turns)"
        out["cold_slice"] = res_c
    # by-turn diagnostic
    by_turn = {}
    for t in range(1, 9):
        sub = df[df.turn == t]
        denom_t = denom_all // 8
        r_, _ = _per_turn_metrics(sub, denom_t)
        rrt = sub[sub.y == 1].rrf_rank.to_numpy()
        by_turn[t] = {"model_ndcg@20": r_["ndcg@20"],
                      "rrf_ndcg@20": float(sum(1 / math.log2(r + 1) for r in rrt if r <= 20) / denom_t)}
    out["by_turn"] = by_turn

    json.dump(out, open(OUT / "metrics.json", "w"), indent=2)
    pd.DataFrame(pt, columns=["session_id", "turn_number", "gt_rank"]).to_parquet(
        OUT / "per_turn_ranks.parquet")
    print(json.dumps(out, indent=2), flush=True)


def stage_full_model():
    """Train a single model on ALL devset rows (including lockbox) at the
    median best_iteration across the 5 CV folds. Saved as model_full.txt."""
    import lightgbm as lgb
    import statistics

    sid_codes, turn_arr, sid_uniq, meta = _ids_and_folds()
    sid_fold = np.load(OUT / "sid_fold.npy")
    y = np.load(OUT / "y.npy")
    row_w = np.load(OUT / "row_weights.npy")
    X = np.load(str(OUT / "X.npy"), mmap_mode="r")
    all_cols = meta["cols"]
    cat_idx = meta["cat_idx"]

    best_iters = []
    for f in range(N_FOLDS):
        b = lgb.Booster(model_file=str(OUT / f"model_fold{f}.txt"))
        best_iters.append(b.num_trees())
        del b
    n_rounds = int(statistics.median(best_iters))
    print(f"Fold best_iters: {best_iters}  →  full model rounds: {n_rounds}", flush=True)

    all_idx, all_groups = _grouped(np.arange(len(sid_codes)), sid_codes, turn_arr)
    Xall = np.ascontiguousarray(X[all_idx])
    mono = [(-1 if c in MONOTONE_DECREASING else 0) for c in all_cols]
    params = dict(LGB_PARAMS, monotone_constraints=mono)
    dtrain = lgb.Dataset(Xall, label=y[all_idx], group=all_groups,
                         weight=row_w[all_idx], feature_name=all_cols,
                         categorical_feature=cat_idx, free_raw_data=True)
    dtrain.construct()
    del Xall; gc.collect()

    booster = lgb.train(params, dtrain, num_boost_round=n_rounds,
                        callbacks=[lgb.log_evaluation(200)])
    booster.save_model(str(OUT / "model_full.txt"))
    print(f"Saved model_full.txt ({n_rounds} rounds)", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", required=True,
                    choices=["build", "fold", "finalize", "full_model"])
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--out-dir", type=str, default=None,
                    help="Override output directory (default: exp/analysis/rerank/train_v9)")
    ap.add_argument("--features-dir", type=str, default=None,
                    help="Override features_v9 parquet directory")
    ap.add_argument("--sidecar", type=str, default=None,
                    help="Override constraint_features.parquet path")
    ap.add_argument("--weights", type=str, default=None,
                    help="Override label_weights_v9.parquet path")
    ap.add_argument("--lockbox", type=str, default=None,
                    help="Override lockbox_users.json path")
    ap.add_argument("--gt", type=str, default=None,
                    help="Override ground_truth devset.json path")
    a = ap.parse_args()
    if a.out_dir:
        OUT = Path(a.out_dir)
    if a.features_dir:
        FEATURES = Path(a.features_dir)
    if a.sidecar:
        SIDECAR = Path(a.sidecar)
    if a.weights:
        WEIGHTS = Path(a.weights)
    if a.lockbox:
        LOCKBOX = Path(a.lockbox)
    if a.gt:
        GT_PATH = Path(a.gt)
    if a.stage == "build":
        stage_build()
    elif a.stage == "fold":
        stage_fold(a.fold)
    elif a.stage == "finalize":
        stage_finalize()
    else:
        stage_full_model()
