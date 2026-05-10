from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BLINDSET_PATTERN = re.compile(r"(blindset_[A-Za-z0-9]+)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a Music CRS experiment locally or via Modal."
    )
    parser.add_argument(
        "--backend",
        choices=("local", "modal"),
        default="local",
        help="Execution backend for the experiment.",
    )
    parser.add_argument(
        "--tid",
        required=True,
        help="Task identifier matching config/{tid}.yaml.",
    )
    parser.add_argument(
        "--eval_dataset",
        default=None,
        help="Optional explicit split override, e.g. blindset_A.",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=16,
        help="Batch size to forward to the underlying inference command.",
    )
    parser.add_argument(
        "--num_sessions",
        type=int,
        default=0,
        help="Optional devset smoke-test size. Supported on devset runs only.",
    )
    parser.add_argument(
        "--session_ids_file",
        default=None,
        help="Optional devset subset file with {session_ids:[...]} for local runs.",
    )
    parser.add_argument(
        "--exp_dir",
        default="exp",
        help="Local artifact root. Defaults to repo-root exp/.",
    )
    parser.add_argument(
        "--clear_cache",
        action="store_true",
        help="Clear cached retrieval artifacts before inference when supported.",
    )
    return parser


def resolve_split(tid: str, eval_dataset: str | None) -> str:
    if eval_dataset:
        return eval_dataset
    if "devset" in tid:
        return "devset"
    match = BLINDSET_PATTERN.search(tid)
    if match:
        return match.group(1)
    raise ValueError(
        "Could not infer the evaluation split from the tid. "
        "Pass --eval_dataset explicitly."
    )


def resolve_exp_dir(exp_dir: str) -> Path:
    path = Path(exp_dir)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def require_config(tid: str) -> Path:
    config_path = PROJECT_ROOT / "config" / f"{tid}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No config found at {config_path}")
    return config_path


def run_command(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, check=True)


def ensure_ground_truth(exp_dir: Path) -> None:
    ground_truth_path = exp_dir / "ground_truth" / "devset.json"
    if ground_truth_path.exists():
        return
    run_command(
        [
            sys.executable,
            "evaluator/make_ground_truth.py",
            "--exp_dir",
            str(exp_dir),
        ],
        cwd=PROJECT_ROOT,
    )


def run_evaluation(tid: str, exp_dir: Path, split: str) -> None:
    run_command(
        [
            sys.executable,
            "evaluator/evaluate_devset.py",
            "--tid",
            tid,
            "--eval_dataset",
            split,
            "--exp_dir",
            str(exp_dir),
        ],
        cwd=PROJECT_ROOT,
    )


def validate_args(args: argparse.Namespace, split: str) -> None:
    if split != "devset" and args.num_sessions:
        raise ValueError("--num_sessions is only supported for devset runs.")
    if split != "devset" and args.session_ids_file:
        raise ValueError("--session_ids_file is only supported for devset runs.")
    if args.backend == "modal" and args.session_ids_file:
        raise ValueError(
            "--session_ids_file is only supported for the local backend."
        )
    if args.backend == "modal" and split != "devset" and args.clear_cache:
        raise ValueError(
            "--clear_cache is not supported for Modal blindset runs."
        )


def run_local(args: argparse.Namespace, split: str, exp_dir: Path) -> None:
    if split == "devset":
        cmd = [
            sys.executable,
            "run_inference_devset.py",
            "--tid",
            args.tid,
            "--batch_size",
            str(args.batch_size),
            "--exp_dir",
            str(exp_dir),
        ]
        if args.num_sessions > 0:
            cmd.extend(["--num_sessions", str(args.num_sessions)])
        if args.session_ids_file:
            cmd.extend(["--session_ids_file", args.session_ids_file])
        if args.clear_cache:
            cmd.append("--clear_cache")
        run_command(cmd, cwd=PROJECT_ROOT)
        ensure_ground_truth(exp_dir)
        run_evaluation(args.tid, exp_dir, split)
        return

    cmd = [
        sys.executable,
        "run_inference_blindset.py",
        "--tid",
        args.tid,
        "--batch_size",
        str(args.batch_size),
        "--eval_dataset",
        split,
        "--exp_dir",
        str(exp_dir),
    ]
    if args.clear_cache:
        cmd.append("--clear_cache")
    run_command(cmd, cwd=PROJECT_ROOT)


def run_modal(args: argparse.Namespace, split: str, exp_dir: Path) -> None:
    if split == "devset":
        cmd = [
            sys.executable,
            "-m",
            "modal",
            "run",
            "modal/app.py::run_inference",
            "--tid",
            args.tid,
            "--batch-size",
            str(args.batch_size),
        ]
        if args.num_sessions > 0:
            cmd.extend(["--num-sessions", str(args.num_sessions)])
        if args.clear_cache:
            cmd.append("--clear-cache")
        run_command(cmd, cwd=PROJECT_ROOT)
        run_command(
            [
                sys.executable,
                "modal/download_results.py",
                "--tid",
                args.tid,
                "--out-dir",
                str(exp_dir),
            ],
            cwd=PROJECT_ROOT,
        )
        ensure_ground_truth(exp_dir)
        run_evaluation(args.tid, exp_dir, split)
        return

    run_command(
        [
            sys.executable,
            "-m",
            "modal",
            "run",
            "modal/app.py::run_inference_blindset",
            "--tid",
            args.tid,
            "--batch-size",
            str(args.batch_size),
            "--eval-dataset",
            split,
        ],
        cwd=PROJECT_ROOT,
    )
    run_command(
        [
            sys.executable,
            "modal/download_results.py",
            "--tid",
            args.tid,
            "--split",
            split,
            "--out-dir",
            str(exp_dir),
        ],
        cwd=PROJECT_ROOT,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    require_config(args.tid)
    split = resolve_split(args.tid, args.eval_dataset)
    exp_dir = resolve_exp_dir(args.exp_dir)
    validate_args(args, split)

    if args.backend == "local":
        run_local(args, split, exp_dir)
    else:
        run_modal(args, split, exp_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
