"""
Modal cloud pipeline for Music CRS.

Config: modal/config.yaml (volume names, container paths)

Volumes are created automatically on first run — no manual setup needed.

Secret (.env in project root):
    HF_TOKEN=hf_...

Usage:
    # Smoke test (5 sessions)
    modal run modal/app.py::run_inference --num-sessions 5

    # TalkPlay smoke test
    modal run modal/app.py::run_talkplay_inference --tid talkplay_qwen3_4b_devset_smoke --num-sessions 10

    # Full devset
    modal run modal/app.py::run_inference --tid llama1b_bm25_devset --batch-size 64

    # Blindset
    modal run modal/app.py::run_inference_blindset --tid llama1b_bm25_blindset_A

    # Evaluate (after inference)
    modal run modal/app.py::run_evaluate --tid llama1b_bm25_devset
"""

import json
from pathlib import Path

import modal
from datasets import load_dataset
from omegaconf import OmegaConf


def _config_path() -> Path:
    """Find modal/config.yaml locally and when Modal imports this file as /root/app.py."""
    candidates = [
        Path(__file__).parent / "config.yaml",
        Path.cwd() / "modal" / "config.yaml",
        Path("/app/modal/config.yaml"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not find modal/config.yaml. Checked: "
        + ", ".join(str(path) for path in candidates)
    )


ENV_SECRET = modal.Secret.from_dotenv(__file__)


# Load config from modal/config.yaml
_cfg = OmegaConf.load(_config_path())

APP_NAME = _cfg.app_name
HF_CACHE_VOLUME = _cfg.volumes.hf_cache
RESULTS_VOLUME = _cfg.volumes.results
HF_CACHE_DIR = _cfg.container.hf_cache_dir
EXP_DIR = _cfg.container.exp_dir
INFERENCE_GPU = list(_cfg.inference.gpu)
DEVSET_BATCH_SIZE = int(_cfg.inference.devset_batch_size)
BLINDSET_BATCH_SIZE = int(_cfg.inference.blindset_batch_size)

app = modal.App(APP_NAME)

hf_cache_vol = modal.Volume.from_name(HF_CACHE_VOLUME, create_if_missing=True)
results_vol = modal.Volume.from_name(RESULTS_VOLUME, create_if_missing=True)

# Build image: uv_sync reads pyproject.toml + uv.lock for reproducible installs.
# Source files are copied separately (uv_sync uses --no-install-project).
image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_sync(".")
    .uv_pip_install(
        "sqlparse>=0.5.3",
        "polars>=1.8.2",
        "vector-quantize-pytorch>=1.14.8",
    )
    .add_local_dir(
        ".",
        "/app",
        copy=True,
        ignore=[".*", "__pycache__", "*.pyc", ".venv", "exp", "cache", "submission*"],
    )
    .env({"PYTHONPATH": "/app"})
)

_VOLUME_MOUNTS = {
    HF_CACHE_DIR: hf_cache_vol,
    EXP_DIR: results_vol,
}


@app.function(
    image=image,
    gpu=INFERENCE_GPU,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    timeout=7200,
)
def _inference_devset(tid: str, batch_size: int, num_sessions: int, clear_cache: bool):
    import subprocess
    import sys

    cmd = [
        sys.executable, "/app/run_inference_devset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
        "--exp_dir", EXP_DIR,
    ]
    if num_sessions > 0:
        cmd += ["--num_sessions", str(num_sessions)]
    if clear_cache:
        cmd += ["--clear_cache"]

    result = subprocess.run(cmd, cwd="/app")
    if result.returncode != 0:
        raise RuntimeError(f"Inference failed (exit {result.returncode})")
    results_vol.commit()
    print(f"Results saved to volume: inference/devset/{tid}.json")


@app.function(
    image=image,
    gpu=INFERENCE_GPU,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    timeout=21600,
)
def _inference_talkplay_devset(
    tid: str,
    batch_size: int,
    num_sessions: int,
    clear_cache: bool,
    session_ids_json: str = "",
    output_suffix: str = "",
):
    import subprocess
    import sys
    from pathlib import Path

    cmd = [
        sys.executable, "/app/run_inference_talkplay_devset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
        "--exp_dir", EXP_DIR,
        "--device", "cuda",
    ]
    if session_ids_json:
        session_ids_path = Path("/tmp") / f"{tid}_session_ids.json"
        session_ids_path.write_text(
            json.dumps({"session_ids": json.loads(session_ids_json)}),
            encoding="utf-8",
        )
        cmd += ["--session_ids_file", str(session_ids_path)]
    if output_suffix:
        cmd += ["--output_suffix", output_suffix]
    if num_sessions > 0:
        cmd += ["--num_sessions", str(num_sessions)]
    if clear_cache:
        cmd += ["--clear_cache"]

    result = subprocess.run(cmd, cwd="/app")
    if result.returncode != 0:
        raise RuntimeError(f"TalkPlay inference failed (exit {result.returncode})")
    results_vol.commit()
    print(f"Results saved to volume: inference/devset/{tid}.json")


@app.function(
    image=image,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    timeout=3600,
)
def _merge_talkplay_devset_shards(tid: str, shard_suffixes: list[str]):
    import json

    output_dir = Path(EXP_DIR) / "inference" / "devset"
    merged_predictions = []
    merged_traces = []
    for suffix in shard_suffixes:
        shard_stem = f"{tid}.{suffix}"
        prediction_path = output_dir / f"{shard_stem}.json"
        trace_path = output_dir / f"{shard_stem}_trace.json"
        with prediction_path.open("r", encoding="utf-8") as f:
            merged_predictions.extend(json.load(f))
        with trace_path.open("r", encoding="utf-8") as f:
            merged_traces.extend(json.load(f))

    merged_predictions.sort(key=lambda row: (row["session_id"], row["turn_number"]))
    merged_traces.sort(key=lambda row: (row["session_id"], row["turn_number"]))

    with (output_dir / f"{tid}.json").open("w", encoding="utf-8") as f:
        json.dump(merged_predictions, f, ensure_ascii=False)
    with (output_dir / f"{tid}_trace.json").open("w", encoding="utf-8") as f:
        json.dump(merged_traces, f, ensure_ascii=False)
    results_vol.commit()
    print(f"Merged {len(shard_suffixes)} TalkPlay shards into inference/devset/{tid}.json")


@app.function(
    image=image,
    gpu=INFERENCE_GPU,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    timeout=7200,
)
def _inference_blindset(tid: str, batch_size: int, eval_dataset: str):
    import subprocess
    import sys

    cmd = [
        sys.executable, "/app/run_inference_blindset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
        "--eval_dataset", eval_dataset,
        "--exp_dir", EXP_DIR,
    ]
    result = subprocess.run(cmd, cwd="/app")
    if result.returncode != 0:
        raise RuntimeError(f"Inference failed (exit {result.returncode})")
    results_vol.commit()
    print(f"Results saved to volume: inference/{eval_dataset}/{tid}.json")


@app.function(
    image=image,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    timeout=3600,
)
def _evaluate(tid: str, split: str):
    """
    Evaluate predictions using evaluator/.

    The evaluator scripts use relative exp/ paths. Running them with
    cwd=/root means exp/ resolves to /root/exp = the results volume mount.
    PYTHONPATH=/app/evaluator makes the metrics package importable.
    """
    import subprocess
    import sys

    cwd = str(Path(EXP_DIR).parent)  # /root — so exp/ → /root/exp (volume)
    env = {"PYTHONPATH": "/app/evaluator"}

    # Step 1: generate ground truth if not already cached in the volume
    gt_path = Path(EXP_DIR) / "ground_truth" / "devset.json"
    if not gt_path.exists():
        print("Generating ground truth...")
        result = subprocess.run(
            [sys.executable, "/app/evaluator/make_ground_truth.py"],
            cwd=cwd, env={**__import__("os").environ, **env},
        )
        if result.returncode != 0:
            raise RuntimeError(f"make_ground_truth failed (exit {result.returncode})")
        results_vol.commit()

    # Step 2: score predictions
    result = subprocess.run(
        [
            sys.executable, "/app/evaluator/evaluate_devset.py",
            "--tid", tid,
            "--eval_dataset", split,
        ],
        cwd=cwd, env={**__import__("os").environ, **env},
    )
    if result.returncode != 0:
        raise RuntimeError(f"Evaluation failed (exit {result.returncode})")
    results_vol.commit()


@app.local_entrypoint()
def run_inference(
    tid: str = "llama1b_bm25_devset",
    batch_size: int = DEVSET_BATCH_SIZE,
    num_sessions: int = 0,
    clear_cache: bool = False,
):
    """Run devset inference on the configured fast GPU fallback policy."""
    _inference_devset.remote(
        tid=tid,
        batch_size=batch_size,
        num_sessions=num_sessions,
        clear_cache=clear_cache,
    )


@app.local_entrypoint()
def run_inference_blindset(
    tid: str = "llama1b_bm25_blindset_A",
    batch_size: int = BLINDSET_BATCH_SIZE,
    eval_dataset: str = "blindset_A",
):
    """Run blindset inference on the configured fast GPU fallback policy."""
    _inference_blindset.remote(tid=tid, batch_size=batch_size, eval_dataset=eval_dataset)


@app.local_entrypoint()
def run_talkplay_inference(
    tid: str = "talkplay_qwen3_4b_devset_smoke",
    batch_size: int = 1,
    num_sessions: int = 10,
    clear_cache: bool = False,
):
    """Run TalkPlay devset smoke inference on the configured GPU policy."""
    _inference_talkplay_devset.remote(
        tid=tid,
        batch_size=batch_size,
        num_sessions=num_sessions,
        clear_cache=clear_cache,
    )


def _split_session_ids(session_ids: list[str], num_shards: int) -> list[list[str]]:
    num_shards = max(1, min(num_shards, len(session_ids)))
    shards = [[] for _ in range(num_shards)]
    for idx, session_id in enumerate(session_ids):
        shards[idx % num_shards].append(session_id)
    return [shard for shard in shards if shard]


@app.local_entrypoint()
def run_talkplay_full_devset(
    tid: str = "talkplay_qwen3_4b_devset_smoke",
    num_shards: int = 40,
):
    """Run full TalkPlay devset inference in parallel shards, then merge outputs."""
    config = OmegaConf.load(Path("config") / f"{tid}.yaml")
    devset = load_dataset(config.test_dataset_name, split="test")
    session_ids = [item["session_id"] for item in devset]
    shards = _split_session_ids(session_ids, num_shards)
    print(f"Launching {len(shards)} TalkPlay shards for {len(session_ids)} dev sessions.")

    calls = []
    shard_suffixes = []
    for shard_idx, shard_session_ids in enumerate(shards):
        shard_suffix = f"shard_{shard_idx:03d}"
        shard_suffixes.append(shard_suffix)
        print(
            f"Starting shard {shard_idx + 1}/{len(shards)} with "
            f"{len(shard_session_ids)} sessions."
        )
        calls.append(
            _inference_talkplay_devset.spawn(
                tid=tid,
                batch_size=1,
                num_sessions=0,
                clear_cache=False,
                session_ids_json=json.dumps(shard_session_ids),
                output_suffix=shard_suffix,
            )
        )

    for shard_idx, call in enumerate(calls):
        print(f"Waiting for shard {shard_idx + 1}/{len(shards)}.")
        call.get(timeout=21600)

    _merge_talkplay_devset_shards.remote(tid=tid, shard_suffixes=shard_suffixes)


@app.local_entrypoint()
def run_evaluate(
    tid: str = "llama1b_bm25_devset",
    split: str = "devset",
):
    """Score predictions using the evaluator submodule (CPU)."""
    _evaluate.remote(tid=tid, split=split)
