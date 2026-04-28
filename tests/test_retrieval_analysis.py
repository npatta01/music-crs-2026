import json
from pathlib import Path

import pandas as pd
import pytest

from mcrs.analysis.retrieval_analysis import (
    K_VALUES,
    build_failure_view,
    compute_pairwise_complementarity,
    evaluate_run,
    load_ground_truth,
    load_run,
    rrf_fuse_runs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_EXP_DIR = PROJECT_ROOT / "evaluator" / "exp"


def _prediction_row(session_id, turn_number, predicted_track_ids):
    return {
        "session_id": session_id,
        "user_id": "user-1",
        "turn_number": turn_number,
        "predicted_track_ids": predicted_track_ids,
        "predicted_response": "",
    }


def test_load_run_raises_for_missing_tid():
    with pytest.raises(FileNotFoundError):
        load_run("devset", "definitely_missing_tid", exp_dir=EVAL_EXP_DIR)


def test_load_run_rejects_duplicate_track_ids(tmp_path):
    exp_dir = tmp_path / "exp"
    target = exp_dir / "inference" / "devset"
    target.mkdir(parents=True)
    (target / "dup_case.json").write_text(
        json.dumps(
            [
                _prediction_row(
                    "session-1",
                    1,
                    ["track-1", "track-1", "track-2"],
                )
            ]
        )
    )

    with pytest.raises(ValueError, match="duplicate"):
        load_run("devset", "dup_case", exp_dir=exp_dir)


def test_evaluate_run_reproduces_control_metrics_within_rounding_tolerance():
    ground_truth = load_ground_truth("devset", exp_dir=EVAL_EXP_DIR)

    controls = {
        "bm25_devset_retrieval_only_with_tag_list": {
            "ndcg@20": 0.096966835,
            "hit@1000": 0.6311,
        },
        "dense_qwen3_embedding_8b_devset": {
            "ndcg@20": 0.102467098,
            "hit@1000": 0.6934,
        },
    }

    for tid, expected in controls.items():
        predictions = load_run("devset", tid, exp_dir=EVAL_EXP_DIR)
        _, aggregate = evaluate_run(predictions, ground_truth)

        assert round(aggregate["ndcg@20"], 4) == round(expected["ndcg@20"], 4)
        assert round(aggregate["hit@1000"], 4) == round(expected["hit@1000"], 4)


def test_evaluate_run_rejects_mismatched_prediction_coverage():
    ground_truth = pd.DataFrame(
        [
            {
                "session_id": "session-1",
                "turn_number": 1,
                "ground_truth_track_id": "track-a",
            },
            {
                "session_id": "session-1",
                "turn_number": 2,
                "ground_truth_track_id": "track-b",
            },
        ]
    )
    predictions = pd.DataFrame(
        [
            _prediction_row("session-1", 1, ["track-a", "track-x"]),
        ]
    )

    with pytest.raises(ValueError, match="coverage"):
        evaluate_run(predictions, ground_truth)


def test_compute_pairwise_complementarity_classifies_hits_and_misses():
    run_a = pd.DataFrame(
        [
            {"session_id": "s1", "turn_number": 1, "gt_rank": 15.0},
            {"session_id": "s2", "turn_number": 1, "gt_rank": None},
            {"session_id": "s3", "turn_number": 1, "gt_rank": 1200.0},
        ]
    )
    run_b = pd.DataFrame(
        [
            {"session_id": "s1", "turn_number": 1, "gt_rank": None},
            {"session_id": "s2", "turn_number": 1, "gt_rank": 400.0},
            {"session_id": "s3", "turn_number": 1, "gt_rank": 1500.0},
        ]
    )

    comparison = compute_pairwise_complementarity(run_a, run_b, "sparse", "dense", k=1000)

    labels = {
        (row.session_id, row.turn_number): row.complementarity
        for row in comparison.itertuples(index=False)
    }

    assert labels[("s1", 1)] == "sparse_only"
    assert labels[("s2", 1)] == "dense_only"
    assert labels[("s3", 1)] == "both_or_neither"


def test_rrf_fuse_runs_orders_by_accumulated_rrf_score():
    run_a = pd.DataFrame(
        [
            _prediction_row("session-1", 1, ["track-a", "track-b", "track-c"]),
        ]
    )
    run_b = pd.DataFrame(
        [
            _prediction_row("session-1", 1, ["track-b", "track-d", "track-a"]),
        ]
    )

    fused = rrf_fuse_runs([run_a, run_b], ["run_a", "run_b"], rrf_k=60, topk=4)

    assert fused.iloc[0]["predicted_track_ids"] == ["track-b", "track-a", "track-d", "track-c"]
    assert fused.iloc[0]["source_tids"] == ["run_a", "run_b"]


def test_build_failure_view_returns_top20_candidates_and_gold_row():
    predictions = pd.DataFrame(
        [
            {
                **_prediction_row(
                    "session-1",
                    1,
                    [f"track-{i}" for i in range(25)],
                ),
                "gt_rank": 22.0,
            }
        ]
    )
    track_meta = pd.DataFrame(
        [
            {"track_id": f"track-{i}", "track_name": [f"Track {i}"], "artist_name": ["Artist"]}
            for i in range(25)
        ]
    )

    failure_view = build_failure_view(
        predictions,
        track_meta,
        session_id="session-1",
        turn_number=1,
        gold_track_id="track-21",
    )

    assert failure_view["gold_track"]["track_id"] == "track-21"
    assert len(failure_view["top20_candidates"]) == 20
    assert failure_view["top20_candidates"][0]["track_id"] == "track-0"


def test_k_values_include_required_cutoffs():
    assert K_VALUES == [20, 100, 200, 500, 1000]
