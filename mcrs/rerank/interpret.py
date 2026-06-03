"""Interpretability + the popularity-prior acceptance gate.

LightGBM gain importance (always) plus SHAP (``TreeExplainer`` on a sample, best-effort).
The decision the issue cares about: did the model learn **intent-conditioned branch / match
weighting**, or did it collapse into a global popularity prior? This module computes the gain
share of the popularity-family features and fails the gate if popularity dominates -- in which
case a reranker win should be treated as a popularity artefact, not a learned ranker.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mcrs.rerank.branches import score_col

# Features that, if dominant, indicate a popularity/recency prior rather than intent routing.
POPULARITY_FEATURES = {
    "c__log_popularity",
    "c__release_year",
    "c__release_decade",
    score_col("lookup.era_popularity"),
    score_col("lookup.resolved_artist_discography"),
}


def _ranked_gain(importance: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(importance.items(), key=lambda kv: kv[1], reverse=True)


def gain_report(importance_path: str | Path) -> dict[str, Any]:
    mean_gain = json.load(open(importance_path))["mean_gain"]
    ranked = _ranked_gain(mean_gain)
    total = sum(mean_gain.values()) or 1.0
    pop_gain = sum(mean_gain.get(f, 0.0) for f in POPULARITY_FEATURES)
    top_feature = ranked[0][0] if ranked else None
    pop_share = pop_gain / total
    return {
        "top_15_by_gain": [{"feature": f, "gain": g, "share": g / total} for f, g in ranked[:15]],
        "popularity_gain_share": pop_share,
        "top_feature": top_feature,
        "top_feature_is_popularity": top_feature in POPULARITY_FEATURES,
    }


def shap_report(features_path: str | Path, model_path: str | Path,
                sample: int = 20_000, seed: int = 0) -> dict[str, Any] | None:
    """Mean |SHAP| per feature on a row sample. Best-effort: returns None on failure."""
    try:
        import lightgbm as lgb
        import shap

        from mcrs.rerank.features import feature_columns
        from mcrs.rerank.train import to_model_matrix

        frame = pd.read_parquet(features_path)
        feat_cols = feature_columns(frame)
        if len(frame) > sample:
            frame = frame.sample(sample, random_state=seed)
        X = to_model_matrix(frame, feat_cols)
        booster = lgb.Booster(model_file=str(model_path))
        explainer = shap.TreeExplainer(booster)
        vals = explainer.shap_values(X)
        mean_abs = np.abs(vals).mean(axis=0)
        ranked = sorted(zip(feat_cols, mean_abs.tolist()), key=lambda kv: kv[1], reverse=True)
        total = float(sum(v for _, v in ranked)) or 1.0
        return {
            "n_sampled": len(frame),
            "top_15_by_mean_abs_shap": [
                {"feature": f, "mean_abs_shap": v, "share": v / total} for f, v in ranked[:15]],
            "popularity_shap_share": sum(
                v for f, v in ranked if f in POPULARITY_FEATURES) / total,
        }
    except Exception as exc:  # pragma: no cover - shap/runtime variability
        return {"error": f"{type(exc).__name__}: {exc}"}


def interpret(
    out_dir: str | Path,
    model_dir: str | Path,
    features_path: str | Path,
    pop_share_threshold: float = 0.5,
    run_shap: bool = True,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    gains = gain_report(Path(model_dir) / "importance.json")

    gate_pass = (not gains["top_feature_is_popularity"]
                 and gains["popularity_gain_share"] < pop_share_threshold)
    report: dict[str, Any] = {
        "gain": gains,
        "acceptance_gate": {
            "popularity_gain_share": gains["popularity_gain_share"],
            "threshold": pop_share_threshold,
            "top_feature": gains["top_feature"],
            "passes_intent_conditioned_check": bool(gate_pass),
            "verdict": ("intent/branch/match features drive ranking"
                        if gate_pass else "popularity prior dominates -- treat win with suspicion"),
        },
    }
    if run_shap:
        report["shap"] = shap_report(features_path, Path(model_dir) / "models" / "fold0.txt")

    with open(out / "interpret_report.json", "w") as fh:
        json.dump(report, fh, indent=2)
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Interpretability + popularity-prior gate.")
    p.add_argument("--model-dir", default="exp/rerank/model")
    p.add_argument("--features", default="exp/rerank/dataset/features.parquet")
    p.add_argument("--out-dir", default="exp/rerank/model")
    p.add_argument("--pop-share-threshold", type=float, default=0.5)
    p.add_argument("--no-shap", action="store_true")
    args = p.parse_args(argv)

    report = interpret(args.out_dir, args.model_dir, args.features,
                       pop_share_threshold=args.pop_share_threshold, run_shap=not args.no_shap)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
