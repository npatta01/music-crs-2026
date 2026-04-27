"""
Modal cloud pipeline for Music CRS.

Config: modal/config.yaml (volume names, container paths)

Volumes are created automatically on first run — no manual setup needed.

Secret (.env in project root):
    HF_TOKEN=hf_...

Usage:
    # Smoke test (5 sessions)
    modal run modal/app.py::run_inference --num-sessions 5

    # Full devset
    modal run modal/app.py::run_inference --tid llama1b_bm25_devset --batch-size 64

    # Blindset
    modal run modal/app.py::run_inference_blindset --tid llama1b_bm25_blindset_A

    # Evaluate (after inference)
    modal run modal/app.py::run_evaluate --tid llama1b_bm25_devset
"""

from pathlib import Path

import modal
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
def _inference_devset(tid: str, batch_size: int, num_sessions: int):
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
):
    """Run devset inference on the configured fast GPU fallback policy."""
    _inference_devset.remote(tid=tid, batch_size=batch_size, num_sessions=num_sessions)


@app.local_entrypoint()
def run_inference_blindset(
    tid: str = "llama1b_bm25_blindset_A",
    batch_size: int = BLINDSET_BATCH_SIZE,
    eval_dataset: str = "blindset_A",
):
    """Run blindset inference on the configured fast GPU fallback policy."""
    _inference_blindset.remote(tid=tid, batch_size=batch_size, eval_dataset=eval_dataset)


@app.local_entrypoint()
def run_evaluate(
    tid: str = "llama1b_bm25_devset",
    split: str = "devset",
):
    """Score predictions using the evaluator submodule (CPU)."""
    _evaluate.remote(tid=tid, split=split)
