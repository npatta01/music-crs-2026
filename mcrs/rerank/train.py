"""Train the LambdaMART reranker with session-level cross-validation.

``LGBMRanker(objective="lambdarank")`` over the feature matrix from ``features.py``. Splits
are **by ``session_id``** (``GroupKFold``) so all turns of a session stay on one side. Within
each fold's training sessions an inner session-split is held out for early stopping, so the
outer fold stays a clean report split (no tuning on the report split -- leakage guard #6).

Outputs (under ``--out-dir``): per-fold boosters, an out-of-fold (OOF) score table covering
every row exactly once, per-fold gain importances, and a training summary.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
# sklearn is imported lazily inside train_cv / train_single so the online serving path
# (which imports `to_model_matrix` from here) doesn't require scikit-learn in the Modal image.

from mcrs.rerank.features import (
    CATEGORICAL_FEATURES,
    CATEGORICAL_LEVELS,
    feature_columns,
    monotone_constraints,
)

GROUP_KEYS = ["session_id", "turn_number"]

DEFAULT_PARAMS: dict[str, Any] = {
    "objective": "lambdarank",
    "metric": "ndcg",
    "n_estimators": 600,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 200,  # high min_data_in_leaf (regularised)
    "reg_lambda": 5.0,         # lambda_l2
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}


def to_model_matrix(frame: pd.DataFrame, feat_cols: list[str]) -> pd.DataFrame:
    """Cast features for LightGBM: categoricals as ``category``, everything else float32.

    LightGBM does not accept pandas nullable extension dtypes (Int8/Float64); casting the
    numeric block to float32 turns ``<NA>`` into ``NaN`` (which LightGBM handles natively).
    """
    out = {}
    for c in feat_cols:
        if c in CATEGORICAL_FEATURES:
            # Pinned levels => identical category codes at train and serve time.
            out[c] = pd.Categorical(frame[c], categories=CATEGORICAL_LEVELS[c])
        else:
            # NA-safe cast: the raw online feature frame can carry object/nullable columns
            # containing <NA> (the offline parquet round-trip masked this, and older pandas
            # raises on `.astype("float32")` over NAType). `to_numeric(coerce)` maps any NA /
            # non-numeric to NaN first, which LightGBM handles natively.
            out[c] = pd.to_numeric(frame[c], errors="coerce").astype("float32")
    return pd.DataFrame(out, index=frame.index)


def _ordered_group_sizes(frame: pd.DataFrame) -> np.ndarray:
    """Group sizes for LightGBM, assuming ``frame`` is already sorted by GROUP_KEYS."""
    return frame.groupby(GROUP_KEYS, sort=False).size().to_numpy()


def _has_positive(frame: pd.DataFrame) -> pd.Series:
    g = frame.groupby(GROUP_KEYS, sort=False)["label"].transform("max")
    return g > 0


def train_cv(
    frame: pd.DataFrame,
    out_dir: str | Path,
    n_splits: int = 5,
    params: dict[str, Any] | None = None,
    early_stopping_rounds: int = 40,
    inner_val_frac: float = 0.1,
    seed: int = 42,
) -> dict[str, Any]:
    from sklearn.model_selection import GroupKFold, GroupShuffleSplit

    out = Path(out_dir)
    (out / "models").mkdir(parents=True, exist_ok=True)
    params = {**DEFAULT_PARAMS, **(params or {})}

    feat_cols = feature_columns(frame)
    mono = monotone_constraints(feat_cols)
    cat_feats = [c for c in CATEGORICAL_FEATURES if c in feat_cols]
    sessions = frame["session_id"].to_numpy()

    oof = np.full(len(frame), np.nan)
    oof_fold = np.full(len(frame), -1, dtype=int)
    importances: list[dict[str, float]] = []
    fold_best: list[dict[str, Any]] = []

    gkf = GroupKFold(n_splits=n_splits)
    for fold, (tr_idx, va_idx) in enumerate(gkf.split(frame, frame["label"], groups=sessions)):
        tr = frame.iloc[tr_idx]
        # inner session split of the training fold for early stopping
        gss = GroupShuffleSplit(n_splits=1, test_size=inner_val_frac, random_state=seed + fold)
        fit_pos, es_pos = next(gss.split(tr, groups=tr["session_id"].to_numpy()))
        fit = tr.iloc[fit_pos]
        es = tr.iloc[es_pos]

        # drop no-positive groups (no lambdarank gradient) and sort by group for `group=`
        fit = fit[_has_positive(fit)].sort_values(GROUP_KEYS, kind="stable")
        es = es[_has_positive(es)].sort_values(GROUP_KEYS, kind="stable")

        model = lgb.LGBMRanker(**params, monotone_constraints=mono)
        model.fit(
            to_model_matrix(fit, feat_cols), fit["label"].to_numpy(),
            group=_ordered_group_sizes(fit),
            eval_set=[(to_model_matrix(es, feat_cols), es["label"].to_numpy())],
            eval_group=[_ordered_group_sizes(es)],
            eval_at=[20],
            categorical_feature=cat_feats,
            callbacks=[lgb.early_stopping(early_stopping_rounds, verbose=False),
                       lgb.log_evaluation(period=0)],
        )

        va = frame.iloc[va_idx]
        oof[va_idx] = model.predict(to_model_matrix(va, feat_cols))
        oof_fold[va_idx] = fold

        model.booster_.save_model(str(out / "models" / f"fold{fold}.txt"))
        gains = dict(zip(model.booster_.feature_name(),
                         model.booster_.feature_importance(importance_type="gain")))
        importances.append({k: float(v) for k, v in gains.items()})
        best = model.best_score_.get("valid_0", {})
        fold_best.append({"fold": fold, "best_iteration": int(model.best_iteration_ or params["n_estimators"]),
                          "valid_ndcg@20": float(best.get("ndcg@20", float("nan"))),
                          "n_fit_rows": int(len(fit)), "n_val_rows": int(len(va))})
        print(f"[fold {fold}] inner-val ndcg@20={best.get('ndcg@20'):.4f} "
              f"best_iter={model.best_iteration_}")

    oof_df = frame[GROUP_KEYS + ["track_id", "label"]].copy()
    oof_df["score"] = oof
    oof_df["fold"] = oof_fold
    oof_df.to_parquet(out / "oof.parquet", index=False)

    # mean gain importance across folds
    all_feats = sorted({k for imp in importances for k in imp})
    mean_gain = {f: float(np.mean([imp.get(f, 0.0) for imp in importances])) for f in all_feats}
    with open(out / "importance.json", "w") as fh:
        json.dump({"mean_gain": mean_gain, "per_fold": importances}, fh, indent=2)

    summary = {
        "n_splits": n_splits,
        "n_features": len(feat_cols),
        "params": params,
        "folds": fold_best,
        "mean_inner_val_ndcg@20": float(np.nanmean([f["valid_ndcg@20"] for f in fold_best])),
        "out_dir": str(out),
    }
    with open(out / "train_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def train_single(
    frame: pd.DataFrame,
    out_dir: str | Path,
    params: dict[str, Any] | None = None,
    val_frac: float = 0.1,
    early_stopping_rounds: int = 50,
    seed: int = 42,
    max_pool_depth: int | None = None,
) -> dict[str, Any]:
    """Train ONE deployable model on all turns (no CV); save model.txt + model.features.json.

    Used for the deployable Phase-2 model (trained on the train split; devset is the held-out
    report). An inner session split is held out only for early stopping. ``max_pool_depth`` (the
    per-branch cap used to build the training dataset) is recorded in the model card so the
    online reranker serves with the SAME cap -- within-group features (z-scores, aggregates)
    depend on the candidate set, so a serve/train cap mismatch silently corrupts the ranking.
    """
    from sklearn.model_selection import GroupShuffleSplit

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    params = {**DEFAULT_PARAMS, **(params or {})}
    feat_cols = feature_columns(frame)
    mono = monotone_constraints(feat_cols)
    cat_feats = [c for c in CATEGORICAL_FEATURES if c in feat_cols]

    frame = frame[_has_positive(frame)]
    gss = GroupShuffleSplit(n_splits=1, test_size=val_frac, random_state=seed)
    fit_pos, es_pos = next(gss.split(frame, groups=frame["session_id"].to_numpy()))
    fit = frame.iloc[fit_pos].sort_values(GROUP_KEYS, kind="stable")
    es = frame.iloc[es_pos].sort_values(GROUP_KEYS, kind="stable")

    model = lgb.LGBMRanker(**params, monotone_constraints=mono)
    model.fit(
        to_model_matrix(fit, feat_cols), fit["label"].to_numpy(),
        group=_ordered_group_sizes(fit),
        eval_set=[(to_model_matrix(es, feat_cols), es["label"].to_numpy())],
        eval_group=[_ordered_group_sizes(es)],
        eval_at=[20], categorical_feature=cat_feats,
        callbacks=[lgb.early_stopping(early_stopping_rounds, verbose=False),
                   lgb.log_evaluation(period=0)],
    )
    model.booster_.save_model(str(out / "model.txt"))
    with open(out / "model.features.json", "w") as fh:
        json.dump({"feature_columns": feat_cols, "categorical_features": cat_feats,
                   "n_features": len(feat_cols), "max_pool_depth": max_pool_depth}, fh, indent=2)
    summary = {
        "model_path": str(out / "model.txt"),
        "n_features": len(feat_cols),
        "best_iteration": int(model.best_iteration_ or params["n_estimators"]),
        "inner_val_ndcg@20": float(model.best_score_.get("valid_0", {}).get("ndcg@20", float("nan"))),
        "n_fit_rows": int(len(fit)),
    }
    with open(out / "train_single_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Train the LambdaMART reranker.")
    p.add_argument("--features", default="exp/rerank/dataset/features.parquet")
    p.add_argument("--out-dir", default="exp/rerank/model")
    p.add_argument("--single", action="store_true",
                   help="Train ONE deployable model (model.txt + model.features.json) instead of CV.")
    p.add_argument("--n-splits", type=int, default=5)
    p.add_argument("--num-leaves", type=int, default=None)
    p.add_argument("--n-estimators", type=int, default=None)
    p.add_argument("--early-stopping", type=int, default=40)
    args = p.parse_args(argv)

    frame = pd.read_parquet(args.features)
    overrides: dict[str, Any] = {}
    if args.num_leaves is not None:
        overrides["num_leaves"] = args.num_leaves
    if args.n_estimators is not None:
        overrides["n_estimators"] = args.n_estimators
    if args.single:
        # Carry the dataset's per-branch cap into the model card (serve must match train).
        cap = None
        summary_path = Path(args.features).parent / "build_summary.json"
        if summary_path.exists():
            cap = json.loads(summary_path.read_text()).get("max_pool_depth")
        summary = train_single(frame, args.out_dir, params=overrides,
                               early_stopping_rounds=args.early_stopping, max_pool_depth=cap)
    else:
        summary = train_cv(frame, args.out_dir, n_splits=args.n_splits,
                           params=overrides, early_stopping_rounds=args.early_stopping)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
