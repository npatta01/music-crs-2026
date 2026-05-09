import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pandas as pd


EVALUATOR_DIR = Path(__file__).resolve().parents[1] / "evaluator"
if str(EVALUATOR_DIR) not in sys.path:
    sys.path.insert(0, str(EVALUATOR_DIR))

import evaluate_devset  # noqa: E402


def _prediction_row(session_id: str, turn_number: int, predicted_track_ids: list[str]):
    return {
        "session_id": session_id,
        "turn_number": turn_number,
        "predicted_track_ids": predicted_track_ids,
        "predicted_response": "",
    }


def _ground_truth_row(session_id: str, turn_number: int, ground_truth_track_id: str):
    return {
        "session_id": session_id,
        "turn_number": turn_number,
        "ground_truth_track_id": ground_truth_track_id,
    }


def test_evaluate_devset_supports_top20_prediction_depth():
    predictions = pd.DataFrame(
        [
            _prediction_row("s1", 1, [f"track-{idx}" for idx in range(1, 21)]),
            _prediction_row("s1", 2, [f"track-{idx}" for idx in range(21, 41)]),
        ]
    )
    ground_truth = pd.DataFrame(
        [
            _ground_truth_row("s1", 1, "track-1"),
            _ground_truth_row("s1", 2, "track-25"),
        ]
    )

    _, agg = evaluate_devset.evaluate(predictions, ground_truth)

    assert agg["min_pool_depth"] == 20
    assert agg["max_pool_depth"] == 20
    assert agg["supported_k_values"] == [1, 5, 10, 20]
    assert agg["supported_mrr_k_values"] == []
    assert agg["full_1000_diagnostics_available"] is False
    assert agg["ndcg@20"] is not None
    assert agg["hit@20"] is not None
    assert agg["recall@20"] is not None
    assert agg["ndcg@50"] is None
    assert agg["hit@50"] is None
    assert agg["recall@50"] is None
    assert agg["mrr@100"] is None
    assert agg["pct_gt_not_in_top100"] is None
    assert agg["per_turn"]["1"]["hit@100"] is None


def test_evaluate_devset_preserves_deep_metrics_for_1000_depth_runs():
    predictions = pd.DataFrame(
        [
            _prediction_row("s1", 1, [f"track-{idx}" for idx in range(1, 1001)]),
            _prediction_row("s1", 2, [f"track-{idx}" for idx in range(1001, 2001)]),
        ]
    )
    ground_truth = pd.DataFrame(
        [
            _ground_truth_row("s1", 1, "track-400"),
            _ground_truth_row("s1", 2, "track-1500"),
        ]
    )

    _, agg = evaluate_devset.evaluate(predictions, ground_truth)

    assert agg["min_pool_depth"] == 1000
    assert agg["max_pool_depth"] == 1000
    assert agg["supported_k_values"] == evaluate_devset.K_VALUES
    assert agg["supported_mrr_k_values"] == evaluate_devset.MRR_K_VALUES
    assert agg["full_1000_diagnostics_available"] is True
    assert agg["ndcg@1000"] is not None
    assert agg["hit@1000"] is not None
    assert agg["recall@1000"] is not None
    assert agg["mrr@1000"] is not None
    assert agg["pct_gt_not_in_top1000"] is not None
    assert agg["per_turn"]["1"]["hit@100"] is not None


def test_evaluate_devset_uses_min_depth_for_supported_cutoffs_and_prints_na():
    predictions = pd.DataFrame(
        [
            _prediction_row("s1", 1, [f"track-{idx}" for idx in range(1, 21)]),
            _prediction_row("s1", 2, [f"track-{idx}" for idx in range(21, 122)]),
        ]
    )
    ground_truth = pd.DataFrame(
        [
            _ground_truth_row("s1", 1, "track-2"),
            _ground_truth_row("s1", 2, "track-30"),
        ]
    )

    _, agg = evaluate_devset.evaluate(predictions, ground_truth)
    agg["catalog_diversity"] = 0.1
    agg["catalog_diversity@100"] = None
    agg["lexical_diversity"] = 0.0

    assert agg["min_pool_depth"] == 20
    assert agg["max_pool_depth"] == 101
    assert agg["supported_k_values"] == [1, 5, 10, 20]
    assert agg["hit@100"] is None

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        evaluate_devset.print_report(agg, "mixed-depth")

    report = stdout.getvalue()
    assert "N/A" in report
    assert "mixed-depth" in report
