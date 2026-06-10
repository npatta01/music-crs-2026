from __future__ import annotations

import importlib.util
import json
import re as _re
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


def _load_module(name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    sys.path.insert(0, str(module_path.parent))
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _base_eval_metrics(module) -> dict:
    metrics = {
        "n_turns_evaluated": 1,
        "require_full_diagnostic_depth": False,
        "full_diagnostic_depth": module.REQUIRED_DIAGNOSTIC_DEPTH,
        "available_cutoffs": list(module.K_VALUES),
        "min_pool_depth": 1000,
        "max_pool_depth": 1000,
        "n_shallow_rows": 0,
        "mrr": 0.0,
        "mean_rank_when_found": None,
        "median_rank_when_found": None,
        "pct_gt_not_in_top20": 1.0,
        "pct_gt_not_in_top100": 1.0,
        "pct_gt_not_in_top200": 1.0,
        "pct_gt_not_in_top500": 1.0,
        "pct_gt_not_in_top1000": 1.0,
        "per_turn": {},
        "_recommended_20": [],
        "_recommended_100": [],
        "_responses": [],
    }
    for k in module.K_VALUES:
        metrics[f"ndcg@{k}"] = 0.0
        metrics[f"hit@{k}"] = 0.0
        metrics[f"recall@{k}"] = 0.0
    for k in module.MRR_K_VALUES:
        metrics[f"mrr@{k}"] = 0.0
    return metrics


def _write_config(root: Path, tid: str):
    config_dir = root / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / f"{tid}.yaml").write_text("lm_type: dummy\n", encoding="utf-8")


def test_resolve_split_rejects_unknown_non_devset_tid():
    module = _load_module("run_experiment_module", "run_experiment.py")

    with pytest.raises(ValueError):
        module.resolve_split("custom_run", None)


def test_local_devset_runs_inference_then_ground_truth_then_eval(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_local", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")

    commands: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, cwd=None: commands.append(([str(part) for part in cmd], Path(cwd))),
    )

    exit_code = module.main(
        [
            "--backend",
            "local",
            "--tid",
            "foo_devset",
            "--batch_size",
            "4",
            "--exp_dir",
            str(project_root / "artifacts"),
        ]
    )

    assert exit_code == 0
    assert commands == [
        (
            [
                "/usr/bin/python3",
                "run_inference_devset.py",
                "--tid",
                "foo_devset",
                "--batch_size",
                "4",
                "--exp_dir",
                str(project_root / "artifacts"),
            ],
            project_root,
        ),
        (
            [
                "/usr/bin/python3",
                "evaluator/make_ground_truth.py",
                "--exp_dir",
                str(project_root / "artifacts"),
            ],
            project_root,
        ),
        (
            [
                "/usr/bin/python3",
                "evaluator/evaluate_devset.py",
                "--tid",
                "foo_devset",
                "--eval_dataset",
                "devset",
                "--exp_dir",
                str(project_root / "artifacts"),
            ],
            project_root,
        ),
    ]


def test_local_devset_forwards_session_ids_file_to_evaluation(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_local_subset", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")
    session_ids_file = project_root / "sessions.json"
    session_ids_file.write_text('{"session_ids":["s1"]}', encoding="utf-8")

    commands: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, cwd=None: commands.append(([str(part) for part in cmd], Path(cwd))),
    )

    exit_code = module.main(
        [
            "--backend",
            "local",
            "--tid",
            "foo_devset",
            "--session_ids_file",
            str(session_ids_file),
            "--exp_dir",
            str(project_root / "artifacts"),
        ]
    )

    assert exit_code == 0
    assert commands[-1][0] == [
        "/usr/bin/python3",
        "evaluator/evaluate_devset.py",
        "--tid",
        "foo_devset",
        "--eval_dataset",
        "devset",
        "--exp_dir",
        str(project_root / "artifacts"),
        "--session_ids_file",
        str(session_ids_file),
    ]


def test_local_num_sessions_materializes_shared_subset_file(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_local_num_sessions", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")

    commands: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, cwd=None: commands.append(([str(part) for part in cmd], Path(cwd))),
    )
    monkeypatch.setattr(
        module,
        "load_dataset",
        lambda *args, **kwargs: [{"session_id": f"s{i}"} for i in range(10)],
    )

    exit_code = module.main(
        [
            "--backend",
            "local",
            "--tid",
            "foo_devset",
            "--num_sessions",
            "3",
            "--exp_dir",
            str(project_root / "artifacts"),
        ]
    )

    subset_file = project_root / "artifacts" / "subsets" / "foo_devset_num_sessions_3.json"
    assert exit_code == 0
    assert json.loads(subset_file.read_text(encoding="utf-8")) == {
        "session_ids": ["s6", "s9", "s0"]
    }
    assert commands[0][0][-2:] == ["--session_ids_file", str(subset_file)]
    assert "--num_sessions" not in commands[0][0]
    assert commands[-1][0][-2:] == ["--session_ids_file", str(subset_file)]


def test_modal_num_sessions_sends_same_subset_to_remote_and_eval(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_modal_num_sessions", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")

    commands: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, cwd=None: commands.append(([str(part) for part in cmd], Path(cwd))),
    )
    monkeypatch.setattr(
        module,
        "load_dataset",
        lambda *args, **kwargs: [{"session_id": f"s{i}"} for i in range(10)],
    )

    exit_code = module.main(
        [
            "--backend",
            "modal",
            "--tid",
            "foo_devset",
            "--num_sessions",
            "3",
            "--exp_dir",
            str(project_root / "artifacts"),
        ]
    )

    subset_file = project_root / "artifacts" / "subsets" / "foo_devset_num_sessions_3.json"
    assert exit_code == 0
    assert commands[0][0] == [
        "/usr/bin/python3",
        "-m",
        "modal",
        "run",
        "modal/app.py::run_inference",
        "--tid",
        "foo_devset",
        "--batch-size",
        "16",
        "--session-ids-json",
        '["s6", "s9", "s0"]',
    ]
    assert commands[-1][0][-2:] == ["--session_ids_file", str(subset_file)]


def test_num_sessions_and_session_ids_file_are_mutually_exclusive(tmp_path):
    module = _load_module("run_experiment_module_subset_validation", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")
    session_ids_file = project_root / "sessions.json"
    session_ids_file.write_text('{"session_ids":["s1"]}', encoding="utf-8")
    module.PROJECT_ROOT = project_root

    with pytest.raises(ValueError, match="Use either --num_sessions or --session_ids_file"):
        module.main(
            [
                "--backend",
                "local",
                "--tid",
                "foo_devset",
                "--num_sessions",
                "3",
                "--session_ids_file",
                str(session_ids_file),
            ]
        )


def test_modal_blindset_downloads_into_requested_exp_dir(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_modal", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_blindset_A")

    commands: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, cwd=None: commands.append(([str(part) for part in cmd], Path(cwd))),
    )

    exit_code = module.main(
        [
            "--backend",
            "modal",
            "--tid",
            "foo_blindset_A",
            "--batch_size",
            "8",
            "--exp_dir",
            str(project_root / "exp-out"),
        ]
    )

    assert exit_code == 0
    assert commands == [
        (
            [
                "/usr/bin/python3",
                "-m",
                "modal",
                "run",
                "modal/app.py::run_inference_blindset",
                "--tid",
                "foo_blindset_A",
                "--batch-size",
                "8",
                "--eval-dataset",
                "blindset_A",
            ],
            project_root,
        ),
        (
            [
                "/usr/bin/python3",
                "modal/download_results.py",
                "--tid",
                "foo_blindset_A",
                "--split",
                "blindset_A",
                "--out-dir",
                str(project_root / "exp-out"),
                "--overwrite",
            ],
            project_root,
        ),
    ]


def test_evaluate_main_uses_custom_exp_dir(tmp_path, monkeypatch):
    module = _load_module("evaluate_devset_module", "evaluator/evaluate_devset.py")
    exp_dir = tmp_path / "artifacts"
    (exp_dir / "ground_truth").mkdir(parents=True)
    (exp_dir / "inference" / "devset").mkdir(parents=True)
    (exp_dir / "ground_truth" / "devset.json").write_text(
        json.dumps(
            [
                {
                    "session_id": "s1",
                    "user_id": "u1",
                    "turn_number": 1,
                    "ground_truth_track_id": "track-1",
                }
            ]
        ),
        encoding="utf-8",
    )
    (exp_dir / "inference" / "devset" / "foo_devset.json").write_text(
        json.dumps(
            [
                {
                    "session_id": "s1",
                    "user_id": "u1",
                    "turn_number": 1,
                    "predicted_track_ids": ["track-1"] * 1000,
                    "predicted_response": "hello",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        module,
        "evaluate",
        lambda df_predictions, df_ground_truth: (
            pd.DataFrame(
                [
                    {
                        "session_id": "s1",
                        "turn_number": 1,
                        "gt_rank": 1,
                    }
                ]
            ),
            _base_eval_metrics(module),
        ),
    )
    monkeypatch.setattr(module, "print_report", lambda *args, **kwargs: None)

    import datasets

    monkeypatch.setattr(datasets, "load_dataset", lambda *args, **kwargs: [1, 2, 3])

    args = SimpleNamespace(
        tid="foo_devset",
        eval_dataset="devset",
        session_ids_file=None,
        exp_dir=str(exp_dir),
    )

    module.main(args)

    assert (exp_dir / "scores" / "devset" / "foo_devset.json").exists()
    assert (exp_dir / "scores" / "devset" / "foo_devset_samples.csv").exists()


def test_evaluate_reports_numeric_metrics_for_shallow_cutoffs():
    module = _load_module("evaluate_devset_shallow_module", "evaluator/evaluate_devset.py")

    df_predictions = pd.DataFrame(
        [
            {
                "session_id": "s1",
                "turn_number": 1,
                "predicted_track_ids": [f"track-{i}" for i in range(200)],
                "predicted_response": "",
            }
        ]
    )
    df_ground_truth = pd.DataFrame(
        [
            {
                "session_id": "s1",
                "turn_number": 1,
                "ground_truth_track_id": "track-0",
            }
        ]
    )

    df_results, agg = module.evaluate(df_predictions, df_ground_truth)

    assert agg["require_full_diagnostic_depth"] is False
    assert agg["full_diagnostic_depth"] == 1000
    assert agg["available_cutoffs"] == module.K_VALUES
    assert agg["min_pool_depth"] == 200
    assert agg["max_pool_depth"] == 200
    assert agg["n_shallow_rows"] == 1
    assert agg["ndcg@20"] == 1.0
    assert agg["hit@20"] == 1.0
    assert agg["mrr"] == 1.0
    assert agg["ndcg@500"] == 1.0
    assert agg["hit@500"] == 1.0
    assert agg["recall@500"] == 1.0
    assert agg["mrr@500"] == 1.0
    assert agg["pct_gt_not_in_top500"] == 0.0
    assert df_results.loc[0, "ndcg@500"] == 1.0
    assert df_results.loc[0, "hit@500"] == 1.0
    assert df_results.loc[0, "rr@500"] == 1.0


def test_evaluate_reports_missing_prediction_key_clearly():
    module = _load_module("evaluate_devset_missing_key_module", "evaluator/evaluate_devset.py")

    df_predictions = pd.DataFrame(
        [
            {
                "session_id": "s1",
                "turn_number": 1,
                "predicted_track_ids": ["track-1"],
                "predicted_response": "",
            }
        ]
    )
    df_ground_truth = pd.DataFrame(
        [
            {
                "session_id": "s1",
                "turn_number": 1,
                "ground_truth_track_id": "track-1",
            },
            {
                "session_id": "s1",
                "turn_number": 2,
                "ground_truth_track_id": "track-2",
            },
        ]
    )

    with pytest.raises(KeyError, match="No prediction for session_id=s1 turn_number=2"):
        module.evaluate(df_predictions, df_ground_truth)


def test_evaluate_full_depth_keeps_all_metric_keys_numeric():
    module = _load_module("evaluate_devset_full_module", "evaluator/evaluate_devset.py")

    df_predictions = pd.DataFrame(
        [
            {
                "session_id": "s1",
                "turn_number": 1,
                "predicted_track_ids": [f"track-{i}" for i in range(1000)],
                "predicted_response": "",
            }
        ]
    )
    df_ground_truth = pd.DataFrame(
        [
            {
                "session_id": "s1",
                "turn_number": 1,
                "ground_truth_track_id": "track-0",
            }
        ]
    )

    df_results, agg = module.evaluate(df_predictions, df_ground_truth)

    assert agg["require_full_diagnostic_depth"] is False
    assert agg["available_cutoffs"] == module.K_VALUES
    assert agg["min_pool_depth"] == 1000
    assert agg["max_pool_depth"] == 1000
    assert agg["n_shallow_rows"] == 0
    assert agg["ndcg@1000"] == 1.0
    assert agg["hit@1000"] == 1.0
    assert agg["recall@1000"] == 1.0
    assert agg["mrr@1000"] == 1.0
    assert agg["pct_gt_not_in_top1000"] == 0.0
    assert df_results.loc[0, "ndcg@1000"] == 1.0
    assert df_results.loc[0, "hit@1000"] == 1.0
    assert df_results.loc[0, "rr@1000"] == 1.0


def test_evaluate_per_turn_reports_deep_cutoffs_for_mixed_depth_rows():
    module = _load_module("evaluate_devset_mixed_depth_module", "evaluator/evaluate_devset.py")

    df_predictions = pd.DataFrame(
        [
            {
                "session_id": "s1",
                "turn_number": 1,
                "predicted_track_ids": [f"track-{i}" for i in range(20)],
                "predicted_response": "",
            },
            {
                "session_id": "s2",
                "turn_number": 1,
                "predicted_track_ids": [f"track-{i}" for i in range(100)],
                "predicted_response": "",
            },
        ]
    )
    df_ground_truth = pd.DataFrame(
        [
            {
                "session_id": "s1",
                "turn_number": 1,
                "ground_truth_track_id": "track-0",
            },
            {
                "session_id": "s2",
                "turn_number": 1,
                "ground_truth_track_id": "track-0",
            },
        ]
    )

    _, agg = module.evaluate(df_predictions, df_ground_truth)

    assert agg["available_cutoffs"] == module.K_VALUES
    assert agg["hit@100"] == 1.0
    assert agg["ndcg@100"] == 1.0
    assert agg["per_turn"]["1"]["ndcg@20"] == 1.0
    assert agg["per_turn"]["1"]["hit@20"] == 1.0
    assert agg["per_turn"]["1"]["hit@100"] == 1.0


def test_main_reports_catalog_diversity_for_shallow_cutoffs(tmp_path, monkeypatch):
    module = _load_module("evaluate_devset_main_shallow_diversity_module", "evaluator/evaluate_devset.py")

    exp_dir = tmp_path / "artifacts"
    inference_dir = exp_dir / "inference" / "devset"
    ground_truth_dir = exp_dir / "ground_truth"
    inference_dir.mkdir(parents=True)
    ground_truth_dir.mkdir(parents=True)

    predictions = [
        {
            "session_id": "s1",
            "turn_number": 1,
            "predicted_track_ids": [f"track-{i}" for i in range(20)],
            "predicted_response": "response",
        }
    ]
    ground_truth = [
        {
            "session_id": "s1",
            "turn_number": 1,
            "ground_truth_track_id": "track-0",
        }
    ]

    (inference_dir / "foo_devset.json").write_text(json.dumps(predictions), encoding="utf-8")
    (ground_truth_dir / "devset.json").write_text(json.dumps(ground_truth), encoding="utf-8")

    monkeypatch.setattr(module, "print_report", lambda *args, **kwargs: None)

    import datasets

    monkeypatch.setattr(datasets, "load_dataset", lambda *args, **kwargs: [1, 2, 3])

    args = SimpleNamespace(
        tid="foo_devset",
        eval_dataset="devset",
        session_ids_file=None,
        exp_dir=str(exp_dir),
    )

    module.main(args)

    score_path = exp_dir / "scores" / "devset" / "foo_devset.json"
    payload = json.loads(score_path.read_text(encoding="utf-8"))

    assert payload["available_cutoffs"] == module.K_VALUES
    assert payload["catalog_diversity"] == pytest.approx(20 / 3)
    assert payload["catalog_diversity@100"] == pytest.approx(20 / 3)


def test_make_run_id_format():
    module = _load_module("run_experiment_module_runid", "run_experiment.py")
    run_id = module.make_run_id()
    assert _re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{6}", run_id), run_id


def test_local_sharding_rejected(tmp_path):
    module = _load_module("run_experiment_module_local_shard_reject", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")
    module.PROJECT_ROOT = project_root
    with pytest.raises(ValueError, match="requires --backend modal"):
        module.main([
            "--backend", "local", "--tid", "foo_devset", "--num_shards", "5",
        ])


def test_num_sessions_with_sharding_rejected(tmp_path):
    module = _load_module("run_experiment_module_smoke_shard_reject", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")
    module.PROJECT_ROOT = project_root
    with pytest.raises(ValueError, match="cannot be combined with --num_shards"):
        module.main([
            "--backend", "modal", "--tid", "foo_devset",
            "--num_shards", "5", "--num_sessions", "3",
        ])


def test_run_id_requires_sharding(tmp_path):
    module = _load_module("run_experiment_module_runid_reject", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")
    module.PROJECT_ROOT = project_root
    with pytest.raises(ValueError, match="--run_id only applies"):
        module.main([
            "--backend", "modal", "--tid", "foo_devset", "--run_id", "abc",
        ])


_FIXED_RUN_ID = "20260603T074512Z-a3f91c"


def test_modal_sharded_devset_builds_command_then_download_merge_eval(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_shard_devset", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")

    commands: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(module, "make_run_id", lambda: _FIXED_RUN_ID)
    monkeypatch.setattr(
        module, "run_command",
        lambda cmd, cwd=None: commands.append(([str(p) for p in cmd], Path(cwd))),
    )

    exp = project_root / "artifacts"
    exit_code = module.main([
        "--backend", "modal", "--tid", "foo_devset",
        "--batch_size", "64", "--num_shards", "5", "--exp_dir", str(exp),
    ])

    assert exit_code == 0
    assert commands[0][0] == [
        "/usr/bin/python3", "-m", "modal", "run",
        "modal/app.py::run_inference_sharded",
        "--tid", "foo_devset",
        "--eval-dataset", "devset",
        "--num-shards", "5",
        "--run-id", _FIXED_RUN_ID,
        "--batch-size", "64",
    ]
    assert commands[1][0] == [
        "/usr/bin/python3", "modal/download_results.py",
        "--tid", "foo_devset",
        "--split", "devset",
        "--run-id", _FIXED_RUN_ID,
        "--out-dir", str(exp),
        "--overwrite",
    ]
    assert commands[2][0] == [
        "/usr/bin/python3", "scripts/merge_shard_results.py",
        "--tid", "foo_devset",
        "--num_shards", "5",
        "--run_id", _FIXED_RUN_ID,
        "--split", "devset",
        "--exp-dir", str(exp),
    ]
    # devset -> ground truth then evaluation
    assert commands[3][0][:2] == ["/usr/bin/python3", "evaluator/make_ground_truth.py"]
    assert commands[4][0][:2] == ["/usr/bin/python3", "evaluator/evaluate_devset.py"]


def test_modal_sharded_blindset_merges_without_eval(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_shard_blindset", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_blindset_A")

    commands: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(module, "make_run_id", lambda: _FIXED_RUN_ID)
    monkeypatch.setattr(
        module, "run_command",
        lambda cmd, cwd=None: commands.append(([str(p) for p in cmd], Path(cwd))),
    )

    exp = project_root / "artifacts"
    exit_code = module.main([
        "--backend", "modal", "--tid", "foo_blindset_A",
        "--eval_dataset", "blindset_A", "--batch_size", "64",
        "--num_shards", "5", "--exp_dir", str(exp),
    ])

    assert exit_code == 0
    assert commands[0][0] == [
        "/usr/bin/python3", "-m", "modal", "run",
        "modal/app.py::run_inference_sharded",
        "--tid", "foo_blindset_A",
        "--eval-dataset", "blindset_A",
        "--num-shards", "5",
        "--run-id", _FIXED_RUN_ID,
        "--batch-size", "64",
    ]
    assert commands[1][0][:6] == [
        "/usr/bin/python3", "modal/download_results.py",
        "--tid", "foo_blindset_A", "--split", "blindset_A",
    ]
    assert commands[2][0][:2] == ["/usr/bin/python3", "scripts/merge_shard_results.py"]
    # No ground truth, no evaluation for blindset.
    assert len(commands) == 3


def test_modal_sharded_run_id_override_threaded(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_shard_override", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_blindset_A")

    commands: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module, "run_command",
        lambda cmd, cwd=None: commands.append(([str(p) for p in cmd], Path(cwd))),
    )

    module.main([
        "--backend", "modal", "--tid", "foo_blindset_A",
        "--eval_dataset", "blindset_A", "--num_shards", "3",
        "--run_id", "CUSTOMID", "--exp_dir", str(project_root / "artifacts"),
    ])

    assert "--run-id" in commands[0][0]
    assert commands[0][0][commands[0][0].index("--run-id") + 1] == "CUSTOMID"
    assert commands[1][0][commands[1][0].index("--run-id") + 1] == "CUSTOMID"
    assert commands[2][0][commands[2][0].index("--run_id") + 1] == "CUSTOMID"


def test_modal_default_num_shards_uses_single_run_entrypoint(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_modal_single", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")

    commands: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module, "run_command",
        lambda cmd, cwd=None: commands.append(([str(p) for p in cmd], Path(cwd))),
    )

    module.main([
        "--backend", "modal", "--tid", "foo_devset",
        "--exp_dir", str(project_root / "artifacts"),
    ])

    # Single-run path: the plain run_inference entrypoint, never the sharded one.
    assert commands[0][0][:5] == [
        "/usr/bin/python3", "-m", "modal", "run", "modal/app.py::run_inference",
    ]
    assert all("run_inference_sharded" not in part for part in commands[0][0])
