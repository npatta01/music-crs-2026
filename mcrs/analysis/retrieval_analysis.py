from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXP_DIR = PROJECT_ROOT / "evaluator" / "exp"
EVALUATOR_ROOT = PROJECT_ROOT / "evaluator"

if str(EVALUATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATOR_ROOT))

from metrics import compute_recsys_metrics  # noqa: E402
from metrics.metrics_recsys import get_rank, get_reciprocal_rank  # noqa: E402


K_VALUES = [20, 100, 200, 500, 1000]


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _resolve_exp_dir(exp_dir: str | Path | None) -> Path:
    return Path(exp_dir) if exp_dir is not None else DEFAULT_EXP_DIR


def _prediction_path(split: str, tid: str, exp_dir: str | Path | None = None) -> Path:
    return _resolve_exp_dir(exp_dir) / "inference" / split / f"{tid}.json"


def _ground_truth_path(split: str, exp_dir: str | Path | None = None) -> Path:
    return _resolve_exp_dir(exp_dir) / "ground_truth" / f"{split}.json"


def _normalize_prediction_df(df_predictions: pd.DataFrame, tid: str | None = None) -> pd.DataFrame:
    required = {"session_id", "turn_number", "predicted_track_ids"}
    missing = required - set(df_predictions.columns)
    if missing:
        raise ValueError(f"Prediction rows are missing required columns: {sorted(missing)}")

    df_predictions = df_predictions.copy()
    if tid is not None:
        df_predictions["tid"] = tid
    if "predicted_response" not in df_predictions.columns:
        df_predictions["predicted_response"] = ""

    duplicate_pairs = df_predictions.duplicated(subset=["session_id", "turn_number"], keep=False)
    if duplicate_pairs.any():
        raise ValueError("Prediction rows must be unique per (session_id, turn_number).")

    for row in df_predictions.itertuples(index=False):
        track_ids = list(row.predicted_track_ids)
        if len(track_ids) != len(set(track_ids)):
            raise ValueError(
                "Prediction rows must not contain duplicate track ids. "
                f"Found duplicate ids for {row.session_id}/turn-{row.turn_number}."
            )

    return df_predictions


def _validate_coverage(df_predictions: pd.DataFrame, df_ground_truth: pd.DataFrame) -> None:
    pred_keys = set(zip(df_predictions["session_id"], df_predictions["turn_number"]))
    gt_keys = set(zip(df_ground_truth["session_id"], df_ground_truth["turn_number"]))
    if pred_keys != gt_keys:
        missing_preds = sorted(gt_keys - pred_keys)[:3]
        extra_preds = sorted(pred_keys - gt_keys)[:3]
        raise ValueError(
            "Prediction coverage does not match ground truth coverage. "
            f"Missing examples: {missing_preds}. Extra examples: {extra_preds}."
        )


def _require_depth(df_predictions: pd.DataFrame, k_values: list[int]) -> None:
    required_depth = max(k_values)
    too_shallow = df_predictions[
        df_predictions["predicted_track_ids"].map(len) < required_depth
    ][["session_id", "turn_number"]]
    if too_shallow.empty:
        return

    examples = ", ".join(
        f"{row.session_id}/turn-{row.turn_number}"
        for row in too_shallow.head(3).itertuples(index=False)
    )
    raise ValueError(
        f"Cannot compute top-{required_depth} diagnostics because prediction rows are too shallow. "
        f"Examples: {examples}."
    )


def load_run(split: str, tid: str, exp_dir: str | Path | None = None) -> pd.DataFrame:
    path = _prediction_path(split, tid, exp_dir=exp_dir)
    if not path.exists():
        raise FileNotFoundError(f"Prediction file not found: {path}")

    with path.open() as handle:
        raw_predictions = json.load(handle)

    df_predictions = pd.DataFrame(raw_predictions)
    return _normalize_prediction_df(df_predictions, tid=tid)


def load_ground_truth(split: str = "devset", exp_dir: str | Path | None = None) -> pd.DataFrame:
    path = _ground_truth_path(split, exp_dir=exp_dir)
    if not path.exists():
        raise FileNotFoundError(f"Ground-truth file not found: {path}")

    with path.open() as handle:
        ground_truth = json.load(handle)

    df_ground_truth = pd.DataFrame(ground_truth)
    required = {"session_id", "turn_number", "ground_truth_track_id"}
    missing = required - set(df_ground_truth.columns)
    if missing:
        raise ValueError(f"Ground truth rows are missing required columns: {sorted(missing)}")
    return df_ground_truth


def evaluate_run(
    df_predictions: pd.DataFrame,
    df_ground_truth: pd.DataFrame,
    k_values: list[int] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    k_values = k_values or K_VALUES
    df_predictions = _normalize_prediction_df(df_predictions)
    df_ground_truth = df_ground_truth.copy()

    _validate_coverage(df_predictions, df_ground_truth)
    _require_depth(df_predictions, k_values)

    predictions_by_key = {
        (row.session_id, row.turn_number): row
        for row in df_predictions.itertuples(index=False)
    }

    rows: list[dict[str, Any]] = []
    reciprocal_ranks: list[float] = []

    for gt_row in df_ground_truth.itertuples(index=False):
        pred_row = predictions_by_key[(gt_row.session_id, gt_row.turn_number)]
        predicted_track_ids = list(pred_row.predicted_track_ids)
        gt_track_id = gt_row.ground_truth_track_id

        recsys_metrics = compute_recsys_metrics(predicted_track_ids, [gt_track_id], k_values)
        rank = get_rank([gt_track_id], predicted_track_ids)
        reciprocal_rank = get_reciprocal_rank(gt_track_id, predicted_track_ids)
        reciprocal_ranks.append(reciprocal_rank)

        rows.append(
            {
                "session_id": gt_row.session_id,
                "turn_number": gt_row.turn_number,
                "gt_track_id": gt_track_id,
                "gt_rank": float(rank) if rank is not None else np.nan,
                "predicted_track_ids": predicted_track_ids,
                "predicted_response": pred_row.predicted_response,
                "rr": reciprocal_rank,
                **recsys_metrics,
            }
        )

    df_results = pd.DataFrame(rows)
    metric_columns = [
        column
        for column in df_results.columns
        if column
        not in {"session_id", "turn_number", "gt_track_id", "gt_rank", "predicted_track_ids", "predicted_response"}
    ]
    turnwise_means = df_results[metric_columns + ["turn_number"]].groupby("turn_number").mean()
    macro_averages = turnwise_means.mean(axis=0).to_dict()

    aggregate = {
        "n_turns_evaluated": int(len(df_results)),
        **{f"ndcg@{k}": float(macro_averages.get(f"ndcg@{k}", 0.0)) for k in k_values},
        **{f"hit@{k}": float(macro_averages.get(f"hit@{k}", 0.0)) for k in k_values},
        **{f"recall@{k}": float(macro_averages.get(f"recall@{k}", 0.0)) for k in k_values},
        "mrr": _mean(reciprocal_ranks),
    }
    return df_results, aggregate


def compute_pairwise_complementarity(
    run_a_instances: pd.DataFrame,
    run_b_instances: pd.DataFrame,
    run_a_name: str,
    run_b_name: str,
    k: int = 1000,
) -> pd.DataFrame:
    left_columns = ["session_id", "turn_number", "gt_rank"]
    if "gt_track_id" in run_a_instances.columns:
        left_columns.insert(2, "gt_track_id")
    left = run_a_instances[left_columns].rename(columns={"gt_rank": f"{run_a_name}_gt_rank"})
    right = run_b_instances[["session_id", "turn_number", "gt_rank"]].rename(
        columns={"gt_rank": f"{run_b_name}_gt_rank"}
    )
    merged = left.merge(right, on=["session_id", "turn_number"], how="inner", validate="one_to_one")

    def _is_hit(rank_value: Any) -> bool:
        if rank_value is None or (isinstance(rank_value, float) and math.isnan(rank_value)):
            return False
        return float(rank_value) <= k

    run_a_hits = merged[f"{run_a_name}_gt_rank"].map(_is_hit)
    run_b_hits = merged[f"{run_b_name}_gt_rank"].map(_is_hit)

    merged["run_a_hit"] = run_a_hits
    merged["run_b_hit"] = run_b_hits
    merged["complementarity"] = np.select(
        [run_a_hits & ~run_b_hits, ~run_a_hits & run_b_hits],
        [f"{run_a_name}_only", f"{run_b_name}_only"],
        default="both_or_neither",
    )
    return merged


def rrf_fuse_runs(
    run_dfs: list[pd.DataFrame],
    source_tids: list[str],
    rrf_k: int = 60,
    topk: int = 1000,
) -> pd.DataFrame:
    if len(run_dfs) != len(source_tids):
        raise ValueError("run_dfs and source_tids must have the same length.")
    if not run_dfs:
        raise ValueError("At least one run is required for RRF fusion.")

    normalized_runs = [_normalize_prediction_df(df) for df in run_dfs]
    base_keys = normalized_runs[0][["session_id", "turn_number"]].sort_values(
        by=["session_id", "turn_number"]
    )
    base_key_set = set(map(tuple, base_keys.to_records(index=False)))

    fused_rows = []
    for key in base_key_set:
        session_id, turn_number = key
        score_map: dict[str, float] = {}
        best_rank_map: dict[str, int] = {}
        user_id = None
        predicted_response = ""

        for run_df in normalized_runs:
            row = run_df[
                (run_df["session_id"] == session_id) & (run_df["turn_number"] == turn_number)
            ]
            if row.empty:
                raise ValueError(
                    "All runs must contain identical (session_id, turn_number) coverage for RRF fusion."
                )

            row_data = row.iloc[0]
            user_id = user_id or row_data.get("user_id")
            predicted_response = predicted_response or row_data.get("predicted_response", "")
            for rank_index, track_id in enumerate(row_data["predicted_track_ids"][:topk], start=1):
                score_map[track_id] = score_map.get(track_id, 0.0) + 1.0 / (rrf_k + rank_index)
                best_rank_map[track_id] = min(best_rank_map.get(track_id, rank_index), rank_index)

        fused_track_ids = [
            track_id
            for track_id, _ in sorted(
                score_map.items(),
                key=lambda item: (-item[1], best_rank_map[item[0]], item[0]),
            )[:topk]
        ]
        fused_rows.append(
            {
                "session_id": session_id,
                "turn_number": turn_number,
                "user_id": user_id,
                "predicted_track_ids": fused_track_ids,
                "predicted_response": predicted_response,
                "source_tids": list(source_tids),
            }
        )

    return pd.DataFrame(fused_rows).sort_values(["session_id", "turn_number"]).reset_index(drop=True)


def _metadata_lookup(track_meta: pd.DataFrame | dict[str, Any], track_id: str) -> dict[str, Any] | None:
    if isinstance(track_meta, pd.DataFrame):
        row = track_meta[track_meta["track_id"] == track_id]
        if row.empty:
            return None
        return row.iloc[0].to_dict()
    if isinstance(track_meta, dict):
        row = track_meta.get(track_id)
        if row is None:
            return None
        return row if isinstance(row, dict) else dict(row)
    return None


def build_failure_view(
    df_predictions: pd.DataFrame,
    track_meta: pd.DataFrame | dict[str, Any],
    session_id: str,
    turn_number: int,
    gold_track_id: str,
) -> dict[str, Any]:
    df_predictions = _normalize_prediction_df(df_predictions)
    row = df_predictions[
        (df_predictions["session_id"] == session_id) & (df_predictions["turn_number"] == turn_number)
    ]
    if row.empty:
        raise KeyError(f"No prediction row found for {session_id}/turn-{turn_number}.")

    prediction_row = row.iloc[0]
    top20_ids = list(prediction_row["predicted_track_ids"][:20])
    top20_candidates = []
    for rank, track_id in enumerate(top20_ids, start=1):
        metadata = _metadata_lookup(track_meta, track_id) or {"track_id": track_id}
        top20_candidates.append({"rank": rank, **metadata})

    gold_metadata = _metadata_lookup(track_meta, gold_track_id) or {"track_id": gold_track_id}
    return {
        "session_id": session_id,
        "turn_number": turn_number,
        "gold_track": gold_metadata,
        "gold_rank": prediction_row.get("gt_rank"),
        "top20_candidates": top20_candidates,
    }
