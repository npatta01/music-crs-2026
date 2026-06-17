from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import random
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from datasets import load_dataset
from omegaconf import OmegaConf


PROJECT_ROOT = Path(__file__).resolve().parent
BLINDSET_PATTERN = re.compile(r"(blindset_[A-Za-z0-9]+)")
DEFAULT_TEST_DATASET = "talkpl-ai/TalkPlayData-Challenge-Dataset"
SUBSET_RANDOM_SEED = 0


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
        help="Task identifier matching configs/{tid}.yaml.",
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
        help="Optional devset subset file with {session_ids:[...]}. Works on the "
             "local and Modal backends, single-run or sharded (the workers filter "
             "to the subset, then split it across --num_shards).",
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
    parser.add_argument(
        "--allow_uncached_litellm",
        action="store_true",
        help=(
            "Forward to local inference to permit LiteLLM extraction without a "
            "configured cache. Intended only for tiny debug runs."
        ),
    )
    parser.add_argument(
        "--num_shards",
        type=int,
        default=1,
        help="Number of local and Modal shards. >1 runs session-sharded inference. "
             "Default 1 = single run.",
    )
    parser.add_argument(
        "--num_workers",
        type=int,
        default=0,
        help="Number of workers for a sharded run. Local default is min(2, "
             "--num_shards); Modal default is --num_shards.",
    )
    parser.add_argument(
        "--run_id",
        default=None,
        help="Optional run id override for a sharded run (retry/resume). "
             "Generated automatically when omitted.",
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


def make_run_id() -> str:
    """One run id per sharded run: {UTC timestamp}-{short random hex}.

    Example: 20260603T074512Z-a3f91c. Scopes every shard's artifacts so a
    re-run never collides with — or silently merges — a prior run's files.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(3)}"


def require_config(tid: str) -> Path:
    config_path = PROJECT_ROOT / "configs" / f"{tid}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No config found at {config_path}")
    return config_path


def _test_dataset_name(tid: str) -> str:
    config = OmegaConf.load(PROJECT_ROOT / "configs" / f"{tid}.yaml")
    return str(config.get("test_dataset_name", DEFAULT_TEST_DATASET))


def materialize_num_sessions_file(tid: str, exp_dir: Path, num_sessions: int) -> str:
    dataset = load_dataset(_test_dataset_name(tid), split="test")
    n = min(num_sessions, len(dataset))
    indices = random.Random(SUBSET_RANDOM_SEED).sample(range(len(dataset)), n)
    session_ids = [str(dataset[index]["session_id"]) for index in indices]
    path = exp_dir / "subsets" / f"{tid}_num_sessions_{n}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"session_ids": session_ids}, indent=2), encoding="utf-8")
    return str(path)


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


def _log_path_for_command(log_dir: Path, index: int, cmd: list[str]) -> Path:
    if "--shard_ids" in cmd:
        try:
            shard_ids = cmd[cmd.index("--shard_ids") + 1].replace(",", "-")
            return log_dir / f"shards_{shard_ids}.log"
        except IndexError:
            pass
    if "--shard_id" in cmd:
        try:
            shard_id = cmd[cmd.index("--shard_id") + 1]
            return log_dir / f"shard_{shard_id}.log"
        except IndexError:
            pass
    return log_dir / f"shard_{index}.log"


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
            log_path = _log_path_for_command(log_dir, index, cmd)
            futures[executor.submit(run_command_logged, cmd, cwd, log_path)] = log_path

        for future in as_completed(futures):
            log_path = futures[future]
            try:
                future.result()
            except subprocess.CalledProcessError:
                print(f"[local-shards] shard failed; see log: {log_path}", file=sys.stderr)
                raise


def local_shard_paths(
    exp_dir: Path,
    split: str,
    tid: str,
    run_id: str,
    shard_id: int,
) -> tuple[Path, Path, Path]:
    stem = f"{tid}.run_{run_id}.shard_{shard_id}"
    inference_dir = exp_dir / "inference" / split
    return (
        inference_dir / f"{stem}.json",
        inference_dir / f"{stem}_trace.jsonl",
        inference_dir / f"{stem}_complete.json",
    )


def _count_jsonl_records(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _prediction_count(path: Path) -> int | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, list):
        return None
    return len(payload)


def _completion_marker_valid(marker_path: Path, prediction_count: int) -> bool:
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        marker.get("predictions") == prediction_count
        and marker.get("trace_records") == prediction_count
    )


def local_shard_complete(
    exp_dir: Path,
    split: str,
    tid: str,
    run_id: str,
    shard_id: int,
) -> bool:
    pred_path, trace_path, marker_path = local_shard_paths(
        exp_dir, split, tid, run_id, shard_id
    )
    if not (pred_path.exists() and trace_path.exists()):
        return False
    prediction_count = _prediction_count(pred_path)
    if prediction_count is None:
        return False
    if marker_path.exists() and _completion_marker_valid(marker_path, prediction_count):
        return True
    try:
        return _count_jsonl_records(trace_path) == prediction_count
    except OSError:
        return False


def group_shard_ids(shard_ids: list[int], num_workers: int) -> list[list[int]]:
    worker_count = min(num_workers, len(shard_ids))
    if worker_count <= 0:
        return []
    return [shard_ids[index::worker_count] for index in range(worker_count)]


def local_shard_suffix(run_id: str, shard_id: int) -> str:
    return f".run_{run_id}.shard_{shard_id}"


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


def run_evaluation(
    tid: str,
    exp_dir: Path,
    split: str,
    session_ids_file: str | None = None,
) -> None:
    cmd = [
        sys.executable,
        "evaluator/evaluate_devset.py",
        "--tid",
        tid,
        "--eval_dataset",
        split,
        "--exp_dir",
        str(exp_dir),
    ]
    if session_ids_file:
        cmd.extend(["--session_ids_file", session_ids_file])
    run_command(cmd, cwd=PROJECT_ROOT)
    if split == "devset":
        augment_scores_with_branch_diagnostics(tid, exp_dir, split)


def augment_scores_with_branch_diagnostics(tid: str, exp_dir: Path, split: str) -> None:
    """Fold branch union coverage into the scores JSON so every devset run
    captures union@k / fusion_efficiency@k (not just the evaluator's hit@k).

    Runs scripts/branch_diagnostics.py (streaming, so it scales to the full
    trace) against the trace sidecar + ground truth, writes the full diagnostics
    sidecar, and merges the headline union metrics into {tid}.json. Best-effort:
    a missing trace or a non-v0+ run (no branch payload) is logged and skipped,
    never fails the experiment.
    """
    trace = exp_dir / "inference" / split / f"{tid}_trace.jsonl"
    ground_truth = exp_dir / "ground_truth" / "devset.json"
    scores = exp_dir / "scores" / split / f"{tid}.json"
    if not (trace.exists() and ground_truth.exists() and scores.exists()):
        print(f"[branch-diagnostics] skipped: trace/ground-truth/scores not all present for {tid}")
        return

    sidecar = exp_dir / "scores" / split / f"{tid}_branch_diagnostics.json"
    try:
        run_command(
            [
                sys.executable,
                "scripts/branch_diagnostics.py",
                "--trace", str(trace),
                "--ground-truth", str(ground_truth),
                "--out", str(sidecar),
            ],
            cwd=PROJECT_ROOT,
        )
    except subprocess.CalledProcessError:
        print("[branch-diagnostics] skipped: non-v0+ trace or diagnostics error (union@k not added)")
        return

    try:
        diag = json.loads(sidecar.read_text(encoding="utf-8"))
        sc = json.loads(scores.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[branch-diagnostics] skipped: could not merge metrics: {exc}")
        return

    for k in (20, 50, 100, 200, 1000):
        if f"unionhit@{k}" in diag:
            sc[f"union@{k}"] = diag[f"unionhit@{k}"]
        eff = diag.get(f"fusion_efficiency@{k}")
        if eff is not None:
            sc[f"fusion_efficiency@{k}"] = eff
    scores.write_text(json.dumps(sc, indent=2), encoding="utf-8")
    print(f"[branch-diagnostics] merged union@k / fusion_efficiency@k into {scores}")


def validate_args(args: argparse.Namespace, split: str) -> None:
    if split != "devset" and args.num_sessions:
        raise ValueError("--num_sessions is only supported for devset runs.")
    if split != "devset" and args.session_ids_file:
        raise ValueError("--session_ids_file is only supported for devset runs.")
    if args.num_sessions and args.session_ids_file:
        raise ValueError("Use either --num_sessions or --session_ids_file, not both.")
    if args.backend == "modal" and split != "devset" and args.clear_cache:
        raise ValueError(
            "--clear_cache is not supported for Modal blindset runs."
        )
    if args.num_shards < 1:
        raise ValueError("--num_shards must be >= 1.")
    if args.num_workers < 0:
        raise ValueError("--num_workers must be >= 0.")
    if args.num_workers and args.num_shards == 1:
        raise ValueError("--num_workers only applies to sharded runs (--num_shards > 1).")
    if args.num_shards > 1 and args.backend == "local" and split != "devset":
        raise ValueError("--num_shards > 1 with --backend local is only supported for devset runs.")
    if args.num_shards > 1 and args.backend == "local" and args.clear_cache:
        raise ValueError("--clear_cache is not supported with local sharded runs.")
    if args.num_shards > 1 and args.num_sessions:
        raise ValueError(
            "--num_sessions cannot be combined with --num_shards > 1: "
            "run a smoke test (--num_sessions) OR a sharded full run, not both."
        )
    if args.run_id and args.num_shards == 1:
        raise ValueError(
            "--run_id only applies to sharded runs (--num_shards > 1)."
        )
    if args.num_shards > 1:
        if args.num_workers == 0:
            if args.backend == "local":
                args.num_workers = min(2, args.num_shards)
            else:
                args.num_workers = args.num_shards
        if not (1 <= args.num_workers <= args.num_shards):
            raise ValueError("--num_workers must be between 1 and --num_shards.")
    else:
        args.num_workers = 1


def run_local(args: argparse.Namespace, split: str, exp_dir: Path) -> None:
    if split == "devset":
        session_ids_file = args.session_ids_file
        if args.num_sessions > 0:
            session_ids_file = materialize_num_sessions_file(args.tid, exp_dir, args.num_sessions)
        if args.num_shards > 1:
            run_local_sharded_devset(args, exp_dir, split, session_ids_file=session_ids_file)
            return
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
        if session_ids_file:
            cmd.extend(["--session_ids_file", session_ids_file])
        if args.clear_cache:
            cmd.append("--clear_cache")
        if args.allow_uncached_litellm:
            cmd.append("--allow_uncached_litellm")
        run_command(cmd, cwd=PROJECT_ROOT)
        ensure_ground_truth(exp_dir)
        run_evaluation(args.tid, exp_dir, split, session_ids_file=session_ids_file)
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
    if args.allow_uncached_litellm:
        cmd.append("--allow_uncached_litellm")
    run_command(cmd, cwd=PROJECT_ROOT)


def run_local_sharded_devset(
    args: argparse.Namespace,
    exp_dir: Path,
    split: str,
    session_ids_file: str | None = None,
) -> None:
    run_id = args.run_id or make_run_id()
    print(f"Local sharded run_id: {run_id} (re-run with --run_id {run_id} to retry)")

    pending_shard_ids: list[int] = []
    for shard_id in range(args.num_shards):
        if local_shard_complete(exp_dir, split, args.tid, run_id, shard_id):
            print(f"[local-shards] skip complete shard {shard_id}/{args.num_shards}")
            continue
        pending_shard_ids.append(shard_id)

    shard_commands: list[list[str]] = []
    for shard_group in group_shard_ids(pending_shard_ids, args.num_workers):
        output_suffixes = {
            str(shard_id): local_shard_suffix(run_id, shard_id)
            for shard_id in shard_group
        }
        cmd = [
            sys.executable,
            "run_inference_devset.py",
            "--tid",
            args.tid,
            "--batch_size",
            str(args.batch_size),
            "--exp_dir",
            str(exp_dir),
            "--num_shards",
            str(args.num_shards),
        ]
        if session_ids_file:
            cmd.extend(["--session_ids_file", session_ids_file])
        if args.allow_uncached_litellm:
            cmd.append("--allow_uncached_litellm")
        cmd.extend(
            [
                "--shard_ids",
                ",".join(str(shard_id) for shard_id in shard_group),
                "--output_suffixes_json",
                json.dumps(output_suffixes),
            ]
        )
        shard_commands.append(cmd)

    log_dir = PROJECT_ROOT / "logs" / "local_shards" / run_id
    if shard_commands:
        print(
            f"Launching {len(shard_commands)} local workers for "
            f"{len(pending_shard_ids)}/{args.num_shards} pending shards "
            f"with {args.num_workers} workers; logs: {log_dir}"
        )
        run_commands_parallel(
            shard_commands,
            cwd=PROJECT_ROOT,
            max_workers=min(args.num_workers, len(shard_commands)),
            log_dir=log_dir,
        )
    else:
        print(f"[local-shards] all {args.num_shards} shards complete; merging existing outputs")

    run_command(
        [
            sys.executable,
            "scripts/merge_shard_results.py",
            "--tid",
            args.tid,
            "--num_shards",
            str(args.num_shards),
            "--run_id",
            run_id,
            "--split",
            split,
            "--exp-dir",
            str(exp_dir),
        ],
        cwd=PROJECT_ROOT,
    )
    ensure_ground_truth(exp_dir)
    run_evaluation(args.tid, exp_dir, split, session_ids_file=session_ids_file)


def run_modal_sharded(args: argparse.Namespace, split: str, exp_dir: Path) -> None:
    run_id = args.run_id or make_run_id()
    print(f"Sharded run_id: {run_id} (re-run with --run_id {run_id} to retry)")

    sharded_cmd = [
        sys.executable,
        "-m",
        "modal",
        "run",
        "modal/app.py::run_inference_sharded",
        "--tid",
        args.tid,
        "--eval-dataset",
        split,
        "--num-shards",
        str(args.num_shards),
        "--num-workers",
        str(args.num_workers),
        "--run-id",
        run_id,
        "--batch-size",
        str(args.batch_size),
    ]
    # A curated session subset is filtered first, then split across shards by
    # the workers (run_inference_devset.py). This keeps per-shard wall time
    # short for sparse capability slices (e.g. visual turns) instead of one
    # long single-container run.
    session_ids_file = args.session_ids_file
    if session_ids_file:
        session_ids_json = json.dumps(
            json.loads(Path(session_ids_file).read_text(encoding="utf-8"))["session_ids"]
        )
        sharded_cmd.extend(["--session-ids-json", session_ids_json])
    if args.clear_cache:
        sharded_cmd.append("--clear-cache")
    run_command(sharded_cmd, cwd=PROJECT_ROOT)

    # --overwrite: the run we just executed produced fresh remote artifacts;
    # download_results.py skips files that already exist locally, so without this
    # a re-run would silently keep the stale local copy.
    run_command(
        [
            sys.executable,
            "modal/download_results.py",
            "--tid",
            args.tid,
            "--split",
            split,
            "--run-id",
            run_id,
            "--out-dir",
            str(exp_dir),
            "--overwrite",
        ],
        cwd=PROJECT_ROOT,
    )
    run_command(
        [
            sys.executable,
            "scripts/merge_shard_results.py",
            "--tid",
            args.tid,
            "--num_shards",
            str(args.num_shards),
            "--run_id",
            run_id,
            "--split",
            split,
            "--exp-dir",
            str(exp_dir),
        ],
        cwd=PROJECT_ROOT,
    )

    if split == "devset":
        ensure_ground_truth(exp_dir)
        run_evaluation(args.tid, exp_dir, split, session_ids_file=session_ids_file)


def run_modal(args: argparse.Namespace, split: str, exp_dir: Path) -> None:
    if split == "devset":
        # Accept either a user-provided curated subset (--session_ids_file) or a
        # random smoke subset (--num_sessions); both reach the remote run as
        # --session-ids-json and are forwarded to evaluation. num_shards is
        # guaranteed 1 here (validate_args rejects session subsets with shards>1).
        session_ids_file = args.session_ids_file
        if args.num_sessions > 0:
            session_ids_file = materialize_num_sessions_file(args.tid, exp_dir, args.num_sessions)
        session_ids_json = None
        if session_ids_file:
            session_ids_json = json.dumps(
                json.loads(Path(session_ids_file).read_text(encoding="utf-8"))["session_ids"]
            )
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
        if session_ids_json:
            cmd.extend(["--session-ids-json", session_ids_json])
        if args.clear_cache:
            cmd.append("--clear-cache")
        run_command(cmd, cwd=PROJECT_ROOT)
        # --overwrite: refresh the local copy with the run we just produced;
        # download_results.py otherwise skips files that already exist locally.
        run_command(
            [
                sys.executable,
                "modal/download_results.py",
                "--tid",
                args.tid,
                "--out-dir",
                str(exp_dir),
                "--overwrite",
            ],
            cwd=PROJECT_ROOT,
        )
        ensure_ground_truth(exp_dir)
        run_evaluation(args.tid, exp_dir, split, session_ids_file=session_ids_file)
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
    # --overwrite: refresh the local copy with the run we just produced;
    # download_results.py otherwise skips files that already exist locally.
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
            "--overwrite",
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
    elif args.num_shards > 1:
        run_modal_sharded(args, split, exp_dir)
    else:
        run_modal(args, split, exp_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
