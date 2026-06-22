from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf


PROJECT_ROOT = Path(__file__).resolve().parent
STAGES = ("retrieval", "rerank", "explanation", "evaluation")
DEFAULT_TEST_DATASET = "talkpl-ai/TalkPlayData-Challenge-Dataset"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run staged Music CRS experiments.")
    parser.add_argument("--config", required=True, help="Pipeline config YAML path.")
    parser.add_argument("--run-id", default=None, help="Optional output run id.")
    parser.add_argument(
        "--only",
        choices=STAGES,
        default=None,
        help="Run only one stage.",
    )
    parser.add_argument(
        "--from",
        dest="from_stage",
        choices=STAGES,
        default=None,
        help="Run from this stage through the end.",
    )
    parser.add_argument(
        "--retrieval-run",
        default=None,
        help="Existing exp/pipeline/runs/<run_id> directory to use as retrieval input.",
    )
    parser.add_argument("--model-ref", default=None, help="Override rerank.model_ref.")
    parser.add_argument("--backend", choices=("local", "modal"), default=None)
    parser.add_argument("--num-sessions", type=int, default=None)
    parser.add_argument("--session-ids-file", default=None)
    parser.add_argument("--offline-rerank", action="store_true")
    return parser


def make_run_id(pipeline_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_id = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in pipeline_id)
    return f"{safe_id}-{stamp}-{secrets.token_hex(3)}"


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def config_hash(config: dict[str, Any]) -> str:
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_config(path: str | Path) -> dict[str, Any]:
    cfg = OmegaConf.load(resolve_path(path))
    return OmegaConf.to_container(cfg, resolve=True) or {}


def _load_dotenv() -> None:
    dotenv_path = PROJECT_ROOT / ".env"
    if not dotenv_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
        return
    load_dotenv(dotenv_path)


def config_for_tid(tid: str) -> dict[str, Any]:
    path = PROJECT_ROOT / "configs" / f"{tid}.yaml"
    if not path.exists():
        return {}
    cfg = OmegaConf.load(path)
    return OmegaConf.to_container(cfg, resolve=True) or {}


def rerank_dataset_name(cfg: dict[str, Any], rerank_cfg: dict[str, Any]) -> str:
    retrieval_cfg = dict(cfg.get("retrieval") or {})
    if rerank_cfg.get("dataset_name"):
        return str(rerank_cfg["dataset_name"])
    if cfg.get("dataset_name"):
        return str(cfg["dataset_name"])
    if retrieval_cfg.get("dataset_name"):
        return str(retrieval_cfg["dataset_name"])

    retrieval_tid = retrieval_cfg.get("tid")
    if retrieval_tid:
        retrieval_source_cfg = config_for_tid(str(retrieval_tid))
        if retrieval_source_cfg.get("test_dataset_name"):
            return str(retrieval_source_cfg["test_dataset_name"])
    return DEFAULT_TEST_DATASET


def run_command(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, check=True)


def run_command_logged(cmd: list[str], cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write("$ " + " ".join(str(part) for part in cmd) + "\n")
        log_file.flush()
        subprocess.run(
            cmd,
            cwd=cwd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=True,
        )


def run_commands_parallel(
    commands: list[list[str]],
    cwd: Path,
    max_workers: int,
    log_dir: Path,
) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for index, cmd in enumerate(commands):
            log_path = log_dir / f"shard_{index}.log"
            futures[executor.submit(run_command_logged, cmd, cwd, log_path)] = log_path

        for future in as_completed(futures):
            log_path = futures[future]
            try:
                future.result()
            except subprocess.CalledProcessError:
                print(f"[pipeline-rerank] shard failed; see log: {log_path}", file=sys.stderr)
                raise


def selected_stages(args: argparse.Namespace) -> list[str]:
    if args.only and args.from_stage:
        raise ValueError("Use --only or --from, not both.")
    if args.only:
        return [args.only]
    if args.from_stage:
        start = STAGES.index(args.from_stage)
        return list(STAGES[start:])
    return list(STAGES)


def write_manifest(run_root: Path, update: dict[str, Any]) -> None:
    path = run_root / "manifest.json"
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
    else:
        manifest = {"stages": {}}
    for key, value in update.items():
        if key == "stages":
            manifest.setdefault("stages", {}).update(value)
        else:
            manifest[key] = value
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")


def stage_backend(pipeline_cfg: dict[str, Any], stage_cfg: dict[str, Any], args: argparse.Namespace) -> str:
    if args.backend:
        return args.backend
    return str(stage_cfg.get("backend") or pipeline_cfg.get("backend") or "local")


def pipeline_roots(
    cfg: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[str, Path, Path]:
    pipeline_id = str(cfg["id"])
    artifacts_root = resolve_path(cfg.get("artifacts_root", "exp/pipeline/runs"))
    run_id = args.run_id or make_run_id(pipeline_id)
    run_root = artifacts_root / run_id
    retrieval_root = resolve_path(args.retrieval_run) if args.retrieval_run else run_root
    run_root.mkdir(parents=True, exist_ok=True)
    return run_id, run_root, retrieval_root


def requested_num_sessions(cfg: dict[str, Any], args: argparse.Namespace) -> int | None:
    if args.num_sessions is not None:
        return args.num_sessions
    value = (cfg.get("retrieval") or {}).get("num_sessions")
    return int(value) if value else None


def session_ids_file_for_run(
    cfg: dict[str, Any],
    args: argparse.Namespace,
    retrieval_exp_dir: Path,
) -> str | None:
    retrieval_cfg = dict(cfg.get("retrieval") or {})
    explicit = args.session_ids_file or retrieval_cfg.get("session_ids_file")
    if explicit:
        return str(explicit)
    num_sessions = requested_num_sessions(cfg, args)
    if not num_sessions:
        return None
    tid = str(retrieval_cfg["tid"])
    return str(retrieval_exp_dir / "subsets" / f"{tid}_num_sessions_{num_sessions}.json")


def session_ids_file_from_manifest(retrieval_root: Path) -> str | None:
    path = retrieval_root / "manifest.json"
    if not path.exists():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    retrieval_stage = (manifest.get("stages") or {}).get("retrieval") or {}
    value = retrieval_stage.get("session_ids_file")
    return str(value) if value else None


def run_retrieval(
    cfg: dict[str, Any],
    args: argparse.Namespace,
    run_root: Path,
) -> tuple[Path, str | None]:
    retrieval_cfg = dict(cfg.get("retrieval") or {})
    tid = str(retrieval_cfg["tid"])
    backend = stage_backend(cfg, retrieval_cfg, args)
    exp_dir = run_root / "retrieval"
    cmd = [
        sys.executable,
        "run_experiment.py",
        "--backend",
        backend,
        "--tid",
        tid,
        "--batch_size",
        str(retrieval_cfg.get("batch_size", 16)),
        "--exp_dir",
        str(exp_dir),
    ]
    eval_dataset = retrieval_cfg.get("eval_dataset") or cfg.get("split")
    if eval_dataset and str(eval_dataset) != "devset":
        cmd.extend(["--eval_dataset", str(eval_dataset)])
    num_sessions = requested_num_sessions(cfg, args)
    if num_sessions:
        cmd.extend(["--num_sessions", str(num_sessions)])
    session_ids_file = args.session_ids_file or retrieval_cfg.get("session_ids_file")
    if session_ids_file:
        cmd.extend(["--session_ids_file", str(session_ids_file)])
    subset_run = bool(num_sessions or session_ids_file)
    num_shards = int(retrieval_cfg.get("num_shards", 1))
    if num_shards > 1 and not subset_run:
        cmd.extend(["--num_shards", str(num_shards)])
        num_workers = int(retrieval_cfg.get("num_workers", 0))
        if num_workers:
            cmd.extend(["--num_workers", str(num_workers)])
        run_id = retrieval_cfg.get("run_id")
        if run_id:
            cmd.extend(["--run_id", str(run_id)])
    if retrieval_cfg.get("clear_cache"):
        cmd.append("--clear_cache")
    run_command(cmd, cwd=PROJECT_ROOT)
    return exp_dir, session_ids_file_for_run(cfg, args, exp_dir)


def retrieval_trace_path(cfg: dict[str, Any], retrieval_root: Path) -> Path:
    split = str(cfg.get("split", "devset"))
    tid = str((cfg.get("retrieval") or {})["tid"])
    return retrieval_root / "retrieval" / "inference" / split / f"{tid}_trace.jsonl"


def run_rerank(
    cfg: dict[str, Any],
    args: argparse.Namespace,
    run_root: Path,
    retrieval_root: Path,
    run_id: str,
) -> Path:
    rerank_cfg = dict(cfg.get("rerank") or {})
    if not rerank_cfg.get("enabled", True):
        return run_root / "rerank"
    backend = stage_backend(cfg, rerank_cfg, args)
    if backend != "local":
        raise ValueError(
            "Staged LGBM replay currently runs locally over saved traces. "
            "Use retrieval.backend=modal to produce Modal traces, then rerank locally."
        )
    model_ref = args.model_ref or rerank_cfg["model_ref"]
    split = str(cfg.get("split", "devset"))
    out_tid = str(rerank_cfg.get("out_tid") or cfg["id"])
    exp_dir = run_root / "rerank"
    cmd = [
        sys.executable,
        "scripts/rerank/replay_lgbm.py",
        "--trace",
        str(retrieval_trace_path(cfg, retrieval_root)),
        "--out-exp-dir",
        str(exp_dir),
        "--out-tid",
        out_tid,
        "--split",
        split,
        "--model-ref",
        str(model_ref),
        "--model-version",
        str(rerank_cfg.get("model_version", "lgbm_v10")),
        "--db-uri",
        str(rerank_cfg.get("db_uri", "cache/lancedb")),
        "--tag-index",
        str(rerank_cfg.get("tag_index", "cache/tag_embedding_index/qwen_0_6b.npz")),
        "--embed-memo",
        str(rerank_cfg.get("embed_memo", "exp/analysis/rerank/q06_memo.json")),
        "--msg-store",
        str(rerank_cfg.get("msg_store", "exp/analysis/rerank/raw_msg_store")),
        "--dataset-name",
        rerank_dataset_name(cfg, rerank_cfg),
        # Matches build_features.py: TalkPlay devset rows live in the HF "test" split.
        "--dataset-split",
        str(rerank_cfg.get("dataset_split", "test")),
        "--pool-k",
        str(rerank_cfg.get("pool_k", 500)),
        "--top-k-out",
        str(rerank_cfg.get("top_k_out", 1000)),
        "--output-topk",
        str(rerank_cfg.get("output_topk", 20)),
    ]
    offline_rerank = bool(args.offline_rerank or rerank_cfg.get("offline", False))
    if offline_rerank:
        cmd.append("--offline")
    if rerank_cfg.get("require_cache_coverage", offline_rerank):
        cmd.append("--require-cache-coverage")

    num_shards = int(rerank_cfg.get("num_shards", 1))
    if num_shards < 1:
        raise ValueError("rerank.num_shards must be >= 1")
    num_workers = int(rerank_cfg.get("num_workers", num_shards))
    if num_workers < 1:
        raise ValueError("rerank.num_workers must be >= 1")
    num_workers = min(num_workers, num_shards)
    if not rerank_cfg.get("write_trace", True):
        cmd.append("--no-trace-output")

    if num_shards == 1:
        run_command(cmd, cwd=PROJECT_ROOT)
        return exp_dir

    shard_cmds = []
    for shard_id in range(num_shards):
        shard_cmd = list(cmd)
        shard_cmd.extend(
            [
                "--num-shards",
                str(num_shards),
                "--shard-id",
                str(shard_id),
                "--output-suffix",
                f".run_{run_id}.shard_{shard_id}",
            ]
        )
        shard_cmds.append(shard_cmd)

    run_commands_parallel(
        shard_cmds,
        PROJECT_ROOT,
        max_workers=num_workers,
        log_dir=PROJECT_ROOT / "logs" / "pipeline_rerank" / run_id,
    )
    run_command(
        [
            sys.executable,
            "scripts/merge_shard_results.py",
            "--tid",
            out_tid,
            "--num_shards",
            str(num_shards),
            "--run_id",
            run_id,
            "--split",
            split,
            "--exp-dir",
            str(exp_dir),
        ],
        cwd=PROJECT_ROOT,
    )
    return exp_dir


def apply_explanation(cfg: dict[str, Any], run_root: Path) -> None:
    explanation_cfg = dict(cfg.get("explanation") or {})
    if not explanation_cfg.get("enabled", True):
        return
    lm_type = str(explanation_cfg.get("lm_type", "dummy"))
    if lm_type != "dummy":
        raise ValueError(
            "Staged explanation replay currently supports lm_type=dummy only. "
            "Use the existing online inference path for non-dummy explanation generation."
        )
    split = str(cfg.get("split", "devset"))
    out_tid = str((cfg.get("rerank") or {}).get("out_tid") or cfg["id"])
    pred_path = run_root / "rerank" / "inference" / split / f"{out_tid}.json"
    rows = json.loads(pred_path.read_text(encoding="utf-8"))
    changed = False
    for row in rows:
        if row.get("predicted_response") is None:
            row["predicted_response"] = ""
            changed = True
    if changed:
        pred_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def run_evaluation(
    cfg: dict[str, Any],
    run_root: Path,
    args: argparse.Namespace,
    session_ids_file: str | None = None,
) -> None:
    evaluation_cfg = dict(cfg.get("evaluation") or {})
    if not evaluation_cfg.get("enabled", True):
        return
    split = str(cfg.get("split", "devset"))
    if split != "devset":
        return
    out_tid = str((cfg.get("rerank") or {}).get("out_tid") or cfg["id"])
    exp_dir = run_root / "rerank"
    gt = exp_dir / "ground_truth" / "devset.json"
    if not gt.exists():
        run_command(
            [sys.executable, "evaluator/make_ground_truth.py", "--exp_dir", str(exp_dir)],
            cwd=PROJECT_ROOT,
        )
    cmd = [
        sys.executable,
        "evaluator/evaluate_devset.py",
        "--tid",
        out_tid,
        "--eval_dataset",
        split,
        "--exp_dir",
        str(exp_dir),
    ]
    if session_ids_file is None:
        session_ids_file = args.session_ids_file or (cfg.get("retrieval") or {}).get("session_ids_file")
    if session_ids_file:
        cmd.extend(["--session_ids_file", str(session_ids_file)])
    run_command(cmd, cwd=PROJECT_ROOT)
    trace = exp_dir / "inference" / split / f"{out_tid}_trace.jsonl"
    scores = exp_dir / "scores" / split / f"{out_tid}.json"
    if trace.exists() and scores.exists():
        sidecar = exp_dir / "scores" / split / f"{out_tid}_branch_diagnostics.json"
        try:
            run_command(
                [
                    sys.executable,
                    "scripts/branch_diagnostics.py",
                    "--trace",
                    str(trace),
                    "--ground-truth",
                    str(gt),
                    "--out",
                    str(sidecar),
                ],
                cwd=PROJECT_ROOT,
            )
        except subprocess.CalledProcessError:
            print("[pipeline] branch diagnostics skipped", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _load_dotenv()
    cfg = load_config(args.config)
    if "id" not in cfg:
        raise ValueError("Pipeline config must include id")
    if not (cfg.get("retrieval") or {}).get("tid"):
        raise ValueError("Pipeline config must include retrieval.tid")
    if not (cfg.get("rerank") or {}).get("model_ref") and not args.model_ref:
        raise ValueError("Pipeline config must include rerank.model_ref or pass --model-ref")

    stages = selected_stages(args)
    if "rerank" in stages and "retrieval" not in stages and not args.retrieval_run:
        raise ValueError("--only rerank or --from rerank requires --retrieval-run")
    run_id, run_root, retrieval_root = pipeline_roots(cfg, args)
    retrieval_exp_dir = retrieval_root / "retrieval"
    session_ids_file = (
        args.session_ids_file
        or (cfg.get("retrieval") or {}).get("session_ids_file")
        or session_ids_file_from_manifest(retrieval_root)
        or session_ids_file_for_run(cfg, args, retrieval_exp_dir)
    )
    write_manifest(
        run_root,
        {
            "pipeline_id": cfg["id"],
            "run_id": run_id,
            "config_path": str(resolve_path(args.config)),
            "config_hash": config_hash(cfg),
            "split": str(cfg.get("split", "devset")),
            "retrieval_source_run": str(retrieval_root),
        },
    )

    if "retrieval" in stages:
        exp_dir, session_ids_file = run_retrieval(cfg, args, run_root)
        retrieval_root = run_root
        retrieval_stage = {"exp_dir": str(exp_dir)}
        if session_ids_file:
            retrieval_stage["session_ids_file"] = str(session_ids_file)
        write_manifest(run_root, {"stages": {"retrieval": retrieval_stage}})
    if "rerank" in stages:
        exp_dir = run_rerank(cfg, args, run_root, retrieval_root, run_id)
        write_manifest(run_root, {"stages": {"rerank": {"exp_dir": str(exp_dir)}}})
    if "explanation" in stages:
        apply_explanation(cfg, run_root)
        write_manifest(run_root, {"stages": {"explanation": {"lm_type": "dummy"}}})
    if "evaluation" in stages:
        run_evaluation(cfg, run_root, args, session_ids_file=session_ids_file)
        write_manifest(run_root, {"stages": {"evaluation": {"exp_dir": str(run_root / "rerank")}}})

    print(f"Pipeline run: {run_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
