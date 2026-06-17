from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module(name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    sys.path.insert(0, str(module_path.parent))
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_pipeline_config(path: Path, *, backend: str = "local") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
id: pipe_devset
split: devset
backend: {backend}
artifacts_root: artifacts/runs
retrieval:
  tid: retr_devset
  batch_size: 7
  num_shards: 2
  num_workers: 1
rerank:
  enabled: true
  model_ref: models/reranker_v10
  pool_k: 500
explanation:
  enabled: true
  lm_type: dummy
evaluation:
  enabled: true
""".strip(),
        encoding="utf-8",
    )

def test_only_retrieval_builds_local_run_experiment_command(tmp_path, monkeypatch):
    module = _load_module("run_pipeline_local", "run_pipeline.py")
    config_path = tmp_path / "configs" / "pipelines" / "pipe.yaml"
    _write_pipeline_config(config_path)
    commands: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "make_run_id", lambda pipeline_id: "run123")
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, cwd=None: commands.append(([str(part) for part in cmd], Path(cwd))),
    )

    assert module.main(["--config", str(config_path), "--only", "retrieval"]) == 0

    assert commands == [
        (
            [
                "/usr/bin/python3",
                "run_experiment.py",
                "--backend",
                "local",
                "--tid",
                "retr_devset",
                "--batch_size",
                "7",
                "--exp_dir",
                str(tmp_path / "artifacts" / "runs" / "run123" / "retrieval"),
                "--num_shards",
                "2",
                "--num_workers",
                "1",
            ],
            tmp_path,
        )
    ]

def test_modal_retrieval_forwards_backend_and_num_sessions(tmp_path, monkeypatch):
    module = _load_module("run_pipeline_modal", "run_pipeline.py")
    config_path = tmp_path / "configs" / "pipelines" / "pipe.yaml"
    _write_pipeline_config(config_path, backend="modal")
    commands: list[list[str]] = []

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "make_run_id", lambda pipeline_id: "run123")
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, cwd=None: commands.append([str(part) for part in cmd]),
    )

    assert module.main(
        ["--config", str(config_path), "--only", "retrieval", "--num-sessions", "1"]
    ) == 0

    assert commands[0][:8] == [
        "/usr/bin/python3",
        "run_experiment.py",
        "--backend",
        "modal",
        "--tid",
        "retr_devset",
        "--batch_size",
        "7",
    ]
    assert "--num_sessions" in commands[0]
    assert commands[0][commands[0].index("--num_sessions") + 1] == "1"

def test_only_rerank_uses_existing_retrieval_run(tmp_path, monkeypatch):
    module = _load_module("run_pipeline_rerank", "run_pipeline.py")
    config_path = tmp_path / "configs" / "pipelines" / "pipe.yaml"
    _write_pipeline_config(config_path)
    retrieval_run = tmp_path / "prior"
    commands: list[list[str]] = []

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, cwd=None: commands.append([str(part) for part in cmd]),
    )

    assert module.main(
        [
            "--config",
            str(config_path),
            "--only",
            "rerank",
            "--retrieval-run",
            str(retrieval_run),
            "--run-id",
            "rerankA",
            "--model-ref",
            "models/reranker_candidate",
        ]
    ) == 0

    assert commands == [
        [
            "/usr/bin/python3",
            "scripts/rerank/replay_lgbm.py",
            "--trace",
            str(retrieval_run / "retrieval" / "inference" / "devset" / "retr_devset_trace.jsonl"),
            "--out-exp-dir",
            str(tmp_path / "artifacts" / "runs" / "rerankA" / "rerank"),
            "--out-tid",
            "pipe_devset",
            "--split",
            "devset",
            "--model-ref",
            "models/reranker_candidate",
            "--model-version",
            "lgbm_v10",
            "--db-uri",
            "cache/lancedb",
            "--tag-index",
            "cache/tag_embedding_index/qwen_0_6b.npz",
            "--embed-memo",
            "exp/analysis/rerank/q06_memo.json",
            "--msg-store",
            "exp/analysis/rerank/raw_msg_store",
            "--dataset-split",
            "test",
            "--pool-k",
            "500",
            "--top-k-out",
            "1000",
            "--output-topk",
            "20",
        ]
    ]


def test_rerank_can_run_parallel_shards_and_merge_without_traces(tmp_path, monkeypatch):
    module = _load_module("run_pipeline_rerank_parallel", "run_pipeline.py")
    config_path = tmp_path / "configs" / "pipelines" / "pipe.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
id: pipe_devset
split: devset
backend: local
artifacts_root: artifacts/runs
retrieval:
  tid: retr_devset
rerank:
  enabled: true
  model_ref: models/reranker_v10
  pool_k: 500
  num_shards: 3
  num_workers: 2
  write_trace: false
explanation:
  enabled: false
evaluation:
  enabled: false
""".strip(),
        encoding="utf-8",
    )
    retrieval_run = tmp_path / "prior"
    commands: list[list[str]] = []
    parallel_calls: list[tuple[list[list[str]], Path, int, Path]] = []

    def fake_parallel(cmds, cwd, max_workers, log_dir):
        parallel_calls.append(
            (
                [[str(part) for part in cmd] for cmd in cmds],
                Path(cwd),
                max_workers,
                Path(log_dir),
            )
        )

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, cwd=None: commands.append([str(part) for part in cmd]),
    )
    monkeypatch.setattr(module, "run_commands_parallel", fake_parallel, raising=False)

    assert module.main(
        [
            "--config",
            str(config_path),
            "--only",
            "rerank",
            "--retrieval-run",
            str(retrieval_run),
            "--run-id",
            "rerankA",
        ]
    ) == 0

    assert len(parallel_calls) == 1
    shard_cmds, cwd, max_workers, log_dir = parallel_calls[0]
    assert cwd == tmp_path
    assert max_workers == 2
    assert log_dir == tmp_path / "logs" / "pipeline_rerank" / "rerankA"
    assert len(shard_cmds) == 3
    for shard_id, cmd in enumerate(shard_cmds):
        assert "--num-shards" in cmd
        assert cmd[cmd.index("--num-shards") + 1] == "3"
        assert "--shard-id" in cmd
        assert cmd[cmd.index("--shard-id") + 1] == str(shard_id)
        assert "--output-suffix" in cmd
        assert cmd[cmd.index("--output-suffix") + 1] == f".run_rerankA.shard_{shard_id}"
        assert "--no-trace-output" in cmd

    assert commands == [
        [
            "/usr/bin/python3",
            "scripts/merge_shard_results.py",
            "--tid",
            "pipe_devset",
            "--num_shards",
            "3",
            "--run_id",
            "rerankA",
            "--split",
            "devset",
            "--exp-dir",
            str(tmp_path / "artifacts" / "runs" / "rerankA" / "rerank"),
        ]
    ]

def test_rerank_only_requires_retrieval_run(tmp_path, monkeypatch):
    module = _load_module("run_pipeline_rerank_requires_source", "run_pipeline.py")
    config_path = tmp_path / "configs" / "pipelines" / "pipe.yaml"
    _write_pipeline_config(config_path)

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)

    try:
        module.main(["--config", str(config_path), "--only", "rerank", "--run-id", "r1"])
    except ValueError as exc:
        assert "--retrieval-run" in str(exc)
    else:
        raise AssertionError("expected rerank-only run without --retrieval-run to be rejected")

def test_non_dummy_explanation_replay_is_rejected(tmp_path, monkeypatch):
    module = _load_module("run_pipeline_explain", "run_pipeline.py")
    config_path = tmp_path / "pipe.yaml"
    config_path.write_text(
        """
id: pipe_devset
split: devset
artifacts_root: artifacts/runs
retrieval:
  tid: retr_devset
rerank:
  model_ref: models/reranker_v10
explanation:
  enabled: true
  lm_type: litellm
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)

    try:
        module.main(["--config", str(config_path), "--only", "explanation", "--run-id", "r1"])
    except ValueError as exc:
        assert "lm_type=dummy" in str(exc)
    else:
        raise AssertionError("expected non-dummy explanation replay to be rejected")

def test_dummy_explanation_does_not_rewrite_predictions_that_already_have_responses(tmp_path):
    module = _load_module("run_pipeline_explain_no_rewrite", "run_pipeline.py")
    pred_path = (
        tmp_path
        / "rerank"
        / "inference"
        / "devset"
        / "pipe_devset.json"
    )
    pred_path.parent.mkdir(parents=True)
    original = '[{"predicted_response":""}]'
    pred_path.write_text(original, encoding="utf-8")

    module.apply_explanation(
        {
            "id": "pipe_devset",
            "split": "devset",
            "rerank": {},
            "explanation": {"enabled": True, "lm_type": "dummy"},
        },
        tmp_path,
    )

    assert pred_path.read_text(encoding="utf-8") == original

def test_evaluation_uses_num_sessions_subset_file(tmp_path, monkeypatch):
    module = _load_module("run_pipeline_eval_subset", "run_pipeline.py")
    config_path = tmp_path / "configs" / "pipelines" / "pipe.yaml"
    _write_pipeline_config(config_path)
    run_root = tmp_path / "artifacts" / "runs" / "r1"
    (run_root / "rerank" / "ground_truth").mkdir(parents=True)
    (run_root / "rerank" / "ground_truth" / "devset.json").write_text("[]", encoding="utf-8")
    commands: list[list[str]] = []

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, cwd=None: commands.append([str(part) for part in cmd]),
    )

    assert module.main(
        [
            "--config",
            str(config_path),
            "--only",
            "evaluation",
            "--run-id",
            "r1",
            "--num-sessions",
            "1",
        ]
    ) == 0

    subset_file = (
        run_root
        / "retrieval"
        / "subsets"
        / "retr_devset_num_sessions_1.json"
    )
    assert commands[0][-2:] == ["--session_ids_file", str(subset_file)]
