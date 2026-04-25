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
    modal run modal/app.py::run_inference --tid llama1b_bm25_devset --batch-size 16

    # Blindset
    modal run modal/app.py::run_inference_blindset --tid llama1b_bm25_blindset_A

    # Evaluate (after inference)
    modal run modal/app.py::run_evaluate --tid llama1b_bm25_devset
"""

from pathlib import Path

import modal
from omegaconf import OmegaConf

# Load config from modal/config.yaml
_cfg = OmegaConf.load(Path(__file__).parent / "config.yaml")

APP_NAME = _cfg.app_name
HF_CACHE_VOLUME = _cfg.volumes.hf_cache
RESULTS_VOLUME = _cfg.volumes.results
HF_CACHE_DIR = _cfg.container.hf_cache_dir
EXP_DIR = _cfg.container.exp_dir

app = modal.App(APP_NAME)

hf_cache_vol = modal.Volume.from_name(HF_CACHE_VOLUME, create_if_missing=True)
results_vol = modal.Volume.from_name(RESULTS_VOLUME, create_if_missing=True)

# Build image from pyproject.toml + uv.lock for reproducible installs
image = (
    modal.Image.debian_slim(python_version="3.12")
    .run_commands("pip install uv")
    .copy_local_file("pyproject.toml", "/app/pyproject.toml")
    .copy_local_file("uv.lock", "/app/uv.lock")
    .run_commands(
        # Export locked deps to requirements format, then install into system Python
        "cd /app && uv export --frozen --no-dev -o /tmp/requirements.txt"
        " && uv pip install --system -r /tmp/requirements.txt"
    )
    .copy_local_dir(
        ".",
        "/app",
        ignore=[".*", "__pycache__", "*.pyc", ".venv", "exp", "cache", "submission*", "evaluator"],
    )
    .run_commands("cd /app && pip install -e . --no-deps --quiet")
)

_VOLUME_MOUNTS = {
    HF_CACHE_DIR: hf_cache_vol,
    EXP_DIR: results_vol,
}


@app.function(
    image=image,
    gpu=modal.gpu.A10G(),
    volumes=_VOLUME_MOUNTS,
    secrets=[modal.Secret.from_dotenv()],
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
    gpu=modal.gpu.A10G(),
    volumes=_VOLUME_MOUNTS,
    secrets=[modal.Secret.from_dotenv()],
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
    secrets=[modal.Secret.from_dotenv()],
    timeout=3600,
)
def _evaluate(tid: str, split: str):
    import subprocess
    import sys

    cmd = [
        sys.executable, "/app/run_evaluate.py",
        "--tid", tid,
        "--split", split,
        "--exp_dir", EXP_DIR,
    ]
    result = subprocess.run(cmd, cwd="/app")
    if result.returncode != 0:
        raise RuntimeError(f"Evaluation failed (exit {result.returncode})")
    results_vol.commit()


@app.local_entrypoint()
def run_inference(
    tid: str = "llama1b_bm25_devset",
    batch_size: int = 16,
    num_sessions: int = 0,
):
    """Run devset inference on A10G GPU."""
    _inference_devset.remote(tid=tid, batch_size=batch_size, num_sessions=num_sessions)


@app.local_entrypoint()
def run_inference_blindset(
    tid: str = "llama1b_bm25_blindset_A",
    batch_size: int = 16,
    eval_dataset: str = "blindset_A",
):
    """Run blindset inference on A10G GPU."""
    _inference_blindset.remote(tid=tid, batch_size=batch_size, eval_dataset=eval_dataset)


@app.local_entrypoint()
def run_evaluate(
    tid: str = "llama1b_bm25_devset",
    split: str = "devset",
):
    """Score predictions from the results volume (CPU)."""
    _evaluate.remote(tid=tid, split=split)
