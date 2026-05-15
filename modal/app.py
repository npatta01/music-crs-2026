"""
Modal cloud pipeline for Music CRS.

Config: modal/config.yaml (volume names, container paths)

Volumes are created automatically on first run — no manual setup needed.

Secret (.env in project root):
    HF_TOKEN=hf_...

Usage:
    # Smoke test (5 sessions, with matching local evaluation subset)
    python run_experiment.py --backend modal --tid llama1b_bm25_devset --num_sessions 5

    # Full devset
    python run_experiment.py --backend modal --tid llama1b_bm25_devset --batch_size 64

    # Blindset
    python run_experiment.py --backend modal --tid llama1b_bm25_blindset_A --eval_dataset blindset_A
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
MODELS_VOLUME = _cfg.volumes.models
HF_CACHE_DIR = _cfg.container.hf_cache_dir
EXP_DIR = _cfg.container.exp_dir
MODELS_DIR = _cfg.container.models_dir
INFERENCE_GPU = list(_cfg.inference.gpu)
DEVSET_BATCH_SIZE = int(_cfg.inference.devset_batch_size)
BLINDSET_BATCH_SIZE = int(_cfg.inference.blindset_batch_size)
LANCEDB_INFERENCE_CPU = float(_cfg.lancedb.inference_cpu)
LANCEDB_INFERENCE_MEMORY = int(_cfg.lancedb.inference_memory)
LANCEDB_QUERY_CPU = float(_cfg.lancedb.query_cpu)
LANCEDB_QUERY_MEMORY = int(_cfg.lancedb.query_memory)

app = modal.App(APP_NAME)

hf_cache_vol = modal.Volume.from_name(HF_CACHE_VOLUME, create_if_missing=True)
results_vol = modal.Volume.from_name(RESULTS_VOLUME, create_if_missing=True)
models_vol = modal.Volume.from_name(MODELS_VOLUME, create_if_missing=True)

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
    MODELS_DIR: models_vol,
}

DEFAULT_REMOTE_LANCEDB_URI = f"{MODELS_DIR}/lancedb"


def _tid_config(tid: str):
    return OmegaConf.load(Path.cwd() / "config" / f"{tid}.yaml")


def _tid_uses_cpu(tid: str) -> bool:
    config = _tid_config(tid)
    return str(config.get("device", "")).lower() == "cpu"


def _run_inference_command(cmd: list[str], *, lancedb_uri: str | None = None) -> None:
    import os
    import subprocess

    env = os.environ.copy()
    if lancedb_uri:
        env["MCRS_LANCEDB_URI"] = lancedb_uri

    result = subprocess.run(cmd, cwd="/app", env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Inference failed (exit {result.returncode})")


def _session_ids_file_arg(session_ids_json: str | None) -> list[str]:
    if not session_ids_json:
        return []
    import json

    path = Path("/tmp/session_ids.json")
    session_ids = json.loads(session_ids_json)
    path.write_text(json.dumps({"session_ids": session_ids}), encoding="utf-8")
    return ["--session_ids_file", str(path)]


@app.function(
    image=image,
    gpu=INFERENCE_GPU,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    timeout=7200,
)
def _inference_devset(
    tid: str,
    batch_size: int,
    num_sessions: int,
    clear_cache: bool,
    session_ids_json: str | None = None,
):
    import sys

    cmd = [
        sys.executable, "/app/run_inference_devset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
        "--exp_dir", EXP_DIR,
    ]
    if session_ids_json:
        cmd += _session_ids_file_arg(session_ids_json)
    elif num_sessions > 0:
        cmd += ["--num_sessions", str(num_sessions)]
    if clear_cache:
        cmd += ["--clear_cache"]

    _run_inference_command(cmd)
    results_vol.commit()
    print(f"Results saved to volume: inference/devset/{tid}.json")


@app.function(
    image=image,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    cpu=LANCEDB_INFERENCE_CPU,
    memory=LANCEDB_INFERENCE_MEMORY,
    timeout=7200,
)
def _inference_devset_cpu(
    tid: str,
    batch_size: int,
    num_sessions: int,
    clear_cache: bool,
    session_ids_json: str | None = None,
):
    import sys

    cmd = [
        sys.executable, "/app/run_inference_devset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
        "--exp_dir", EXP_DIR,
    ]
    if session_ids_json:
        cmd += _session_ids_file_arg(session_ids_json)
    elif num_sessions > 0:
        cmd += ["--num_sessions", str(num_sessions)]
    if clear_cache:
        cmd += ["--clear_cache"]

    _run_inference_command(cmd, lancedb_uri=DEFAULT_REMOTE_LANCEDB_URI)
    results_vol.commit()
    print(f"CPU results saved to volume: inference/devset/{tid}.json")


@app.function(
    image=image,
    gpu=INFERENCE_GPU,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    timeout=7200,
)
def _inference_blindset(tid: str, batch_size: int, eval_dataset: str):
    import sys

    cmd = [
        sys.executable, "/app/run_inference_blindset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
        "--eval_dataset", eval_dataset,
        "--exp_dir", EXP_DIR,
    ]
    _run_inference_command(cmd)
    results_vol.commit()
    print(f"Results saved to volume: inference/{eval_dataset}/{tid}.json")


@app.function(
    image=image,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    cpu=LANCEDB_INFERENCE_CPU,
    memory=LANCEDB_INFERENCE_MEMORY,
    timeout=7200,
)
def _inference_blindset_cpu(tid: str, batch_size: int, eval_dataset: str):
    import sys

    cmd = [
        sys.executable, "/app/run_inference_blindset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
        "--eval_dataset", eval_dataset,
        "--exp_dir", EXP_DIR,
    ]
    _run_inference_command(cmd, lancedb_uri=DEFAULT_REMOTE_LANCEDB_URI)
    results_vol.commit()
    print(f"CPU results saved to volume: inference/{eval_dataset}/{tid}.json")


@app.function(
    image=image,
    volumes={MODELS_DIR: models_vol},
    cpu=LANCEDB_QUERY_CPU,
    memory=LANCEDB_QUERY_MEMORY,
    timeout=600,
)
def query_lancedb(
    query: str,
    topk: int = 20,
    retrieval_config: dict | None = None,
) -> list[str]:
    from mcrs.milvus.indexing import BM25_WITH_TAG_LIST_CORPUS_FIELDS
    from mcrs.retrieval_modules.lancedb import LANCEDB_MODEL

    config = dict(retrieval_config or {})
    config.setdefault("db_uri", DEFAULT_REMOTE_LANCEDB_URI)
    config.setdefault("table_name", "music_track_catalog")
    config.setdefault(
        "searches",
        [
            {
                "name": "bm25_with_tag_list",
                "kind": "fts_bm25s_compat",
                "corpus_fields": list(BM25_WITH_TAG_LIST_CORPUS_FIELDS),
                "weight": 1.0,
                "topk": max(int(topk), 1000),
            }
        ],
    )
    config.setdefault("fusion", {"method": "weighted_rrf"})
    config["device"] = "cpu"

    model = LANCEDB_MODEL(
        dataset_name="unused",
        split_types=["all_tracks"],
        corpus_types=[],
        retrieval_config=config,
    )
    return model.text_to_item_retrieval(query, topk=topk)


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
    session_ids_json: str | None = None,
):
    """Run devset inference on the configured fast GPU fallback policy."""
    inference_fn = _inference_devset_cpu if _tid_uses_cpu(tid) else _inference_devset
    inference_fn.remote(
        tid=tid,
        batch_size=batch_size,
        num_sessions=num_sessions,
        clear_cache=clear_cache,
        session_ids_json=session_ids_json,
    )


@app.local_entrypoint()
def run_inference_blindset(
    tid: str = "llama1b_bm25_blindset_A",
    batch_size: int = BLINDSET_BATCH_SIZE,
    eval_dataset: str = "blindset_A",
):
    """Run blindset inference on the configured fast GPU fallback policy."""
    inference_fn = _inference_blindset_cpu if _tid_uses_cpu(tid) else _inference_blindset
    inference_fn.remote(tid=tid, batch_size=batch_size, eval_dataset=eval_dataset)


@app.local_entrypoint()
def run_evaluate(
    tid: str = "llama1b_bm25_devset",
    split: str = "devset",
):
    """Score predictions using the evaluator submodule (CPU)."""
    _evaluate.remote(tid=tid, split=split)


@app.local_entrypoint()
def upload_lancedb_index(
    local_db_dir: str = "cache/lancedb",
    remote_dir: str = "lancedb",
):
    """Upload a locally built LanceDB directory into the Modal models volume."""
    local_path = Path(local_db_dir).resolve()
    if not local_path.exists():
        raise FileNotFoundError(f"Local LanceDB directory does not exist: {local_path}")
    remote_path = f"/{remote_dir.strip('/')}"
    with models_vol.batch_upload() as batch:
        batch.put_directory(str(local_path), remote_path)
    print(f"Uploaded {local_path} to volume {MODELS_VOLUME}:{remote_path}")


@app.local_entrypoint()
def smoke_lancedb_query(
    query: str = "dark atmospheric synthwave",
    topk: int = 20,
):
    """Smoke-test the private Modal LanceDB query function."""
    track_ids = query_lancedb.remote(query=query, topk=topk)
    print(track_ids)
