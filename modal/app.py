"""
Modal cloud pipeline for Music CRS.

Config: modal/config.yaml (volume names, container paths)

Volumes are created automatically on first run — no manual setup needed.

Secret (.env in project root):
    HF_TOKEN=hf_...

Usage:
    # Smoke test (5 sessions, with matching local evaluation subset)
    python run_experiment.py --backend modal --tid state_ranker_v10_rrf_devset --num_sessions 5

    # Latest full devset learned-ranker experiment
    python run_experiment.py --backend modal --tid state_ranker_v10_lgbm_devset --batch_size 8

    # Blindset
    python run_experiment.py --backend modal --tid state_ranker_v10_lgbm_blindset_A --eval_dataset blindset_A
"""

import json
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
CACHE_VOLUME = _cfg.volumes.cache
HF_CACHE_DIR = _cfg.container.hf_cache_dir
EXP_DIR = _cfg.container.exp_dir
MODELS_DIR = _cfg.container.models_dir
CACHE_DIR = _cfg.container.cache_dir
LITELLM_CACHE_DIR = _cfg.container.litellm_cache_dir
EMBEDDING_CACHE_DIR = _cfg.container.embedding_cache_dir
LITELLM_CACHE_BACKEND = str(_cfg.litellm_cache.backend)
INFERENCE_GPU = list(_cfg.inference.gpu)
DEVSET_BATCH_SIZE = int(_cfg.inference.devset_batch_size)
BLINDSET_BATCH_SIZE = int(_cfg.inference.blindset_batch_size)
LANCEDB_INFERENCE_CPU = float(_cfg.lancedb.inference_cpu)
LANCEDB_INFERENCE_MEMORY = int(_cfg.lancedb.inference_memory)
LANCEDB_QUERY_CPU = float(_cfg.lancedb.query_cpu)
LANCEDB_QUERY_MEMORY = int(_cfg.lancedb.query_memory)
LANCEDB_QUERY_SCALEDOWN_WINDOW = int(_cfg.lancedb.query_scaledown_window)
LANCEDB_QUERY_MAX_CONTAINERS = int(_cfg.lancedb.query_max_containers)
LITELLM_CPU = float(_cfg.litellm.cpu)
LITELLM_MEMORY = int(_cfg.litellm.memory)
LITELLM_SCALEDOWN_WINDOW = int(_cfg.litellm.scaledown_window)
LITELLM_MAX_CONTAINERS = int(_cfg.litellm.max_containers)
LITELLM_EMBEDDING_MODEL = str(_cfg.litellm.embedding_model)
LITELLM_CHAT_MODEL = str(_cfg.litellm.chat_model)
LITELLM_SMALL_CHAT_MODEL = str(_cfg.litellm.small_chat_model)

QWEN3_ENCODER_GPU = str(_cfg.qwen3_encoder.gpu)
QWEN3_ENCODER_CPU = float(_cfg.qwen3_encoder.cpu)
QWEN3_ENCODER_MEMORY = int(_cfg.qwen3_encoder.memory)
QWEN3_ENCODER_TIMEOUT = int(_cfg.qwen3_encoder.timeout)
QWEN3_ENCODER_SCALEDOWN_WINDOW = int(_cfg.qwen3_encoder.scaledown_window)
QWEN3_ENCODER_MAX_CONTAINERS = int(_cfg.qwen3_encoder.max_containers)
QWEN3_ENCODER_TORCH_DTYPE = str(_cfg.qwen3_encoder.torch_dtype)
QWEN3_ENCODER_BATCH_SIZE = int(_cfg.qwen3_encoder.batch_size)

app = modal.App(APP_NAME)

hf_cache_vol = modal.Volume.from_name(HF_CACHE_VOLUME, create_if_missing=True)
results_vol = modal.Volume.from_name(RESULTS_VOLUME, create_if_missing=True)
models_vol = modal.Volume.from_name(MODELS_VOLUME, create_if_missing=True)
# Single unified cache volume. Mounted at CACHE_DIR; the LiteLLM file cache lives
# under LITELLM_CACHE_DIR and the GPU-encoder DiskVectorCache under
# EMBEDDING_CACHE_DIR, both subdirs of CACHE_DIR.
cache_vol = modal.Volume.from_name(CACHE_VOLUME, create_if_missing=True, version=2)

# Build image: uv_sync reads pyproject.toml + uv.lock for reproducible installs.
# Source files are copied separately (uv_sync uses --no-install-project).
image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_sync(".")
    .add_local_dir(
        ".",
        "/app",
        copy=True,
        ignore=[".*", "__pycache__", "*.pyc", ".venv", "exp", "cache", "submission*",
                "models/biencoder*"],  # 15GB b1 encoder lives on a volume / cache-served, never bundle it
    )
    .env(
        {
            "PYTHONPATH": "/app",
            "MCRS_LITELLM_CACHE_BACKEND": "file",
            "MCRS_LITELLM_CACHE_DIR": LITELLM_CACHE_DIR,
        }
    )
)

_VOLUME_MOUNTS = {
    HF_CACHE_DIR: hf_cache_vol,
    EXP_DIR: results_vol,
    MODELS_DIR: models_vol,
    CACHE_DIR: cache_vol,  # unified LiteLLM (LLM + embeddings) + GPU-encoder cache
}

DEFAULT_REMOTE_LANCEDB_URI = f"{MODELS_DIR}/lancedb"
RETRIEVAL_SERVICE_CACHE_SIZE = 8
QWEN_GENERATED_MODEL_SIZES = ("4b", "8b")
QWEN_GENERATED_DOCUMENT_KINDS = ("metadata", "attributes")


def _default_lancedb_retrieval_config(topk: int = 1000) -> dict:
    from mcrs.milvus.indexing import BM25_WITH_TAG_LIST_CORPUS_FIELDS

    return {
        "db_uri": DEFAULT_REMOTE_LANCEDB_URI,
        "table_name": "music_track_catalog",
        "searches": [
            {
                "name": "bm25_with_tag_list",
                "kind": "fts_compat",
                "corpus_fields": list(BM25_WITH_TAG_LIST_CORPUS_FIELDS),
                "weight": 1.0,
                "topk": max(int(topk), 1000),
            }
        ],
        "fusion": {"method": "weighted_rrf"},
        "device": "cpu",
    }


def _retrieval_config_cache_key(config: dict) -> str:
    return json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)


def _ensure_query_lancedb_fts_only(config: dict) -> None:
    searches = config.get("searches") or []
    if any(search.get("kind") == "dense_vector" for search in searches if isinstance(search, dict)):
        raise ValueError(
            "query_lancedb is FTS-only; use ModalRetrievalService with an embedding client for dense_vector"
        )


def _api_key_for_litellm_model(
    model_name: str,
    api_base: str | None,
    *,
    hf_token: str | None,
    openrouter_api_key: str | None,
    deepinfra_api_key: str | None = None,
) -> str | None:
    if api_base and "deepinfra.com" in api_base:
        return deepinfra_api_key
    if model_name.startswith("openrouter/"):
        return openrouter_api_key
    if api_base and "openrouter.ai" in api_base:
        return openrouter_api_key
    if model_name.startswith("huggingface/"):
        return hf_token
    return None


def _vllm_serve_fn_name(model_key: str) -> str:
    return "serve_" + model_key.replace("-", "_")


def _vllm_endpoint_url(model_key: str) -> str:
    fn = modal.Function.from_name(str(_cfg.vllm.app_name), _vllm_serve_fn_name(model_key))
    return fn.get_web_url().rstrip("/") + "/v1"


def _tid_config(tid: str):
    return OmegaConf.load(Path.cwd() / "configs" / f"{tid}.yaml")


def _tid_uses_cpu(tid: str) -> bool:
    config = _tid_config(tid)
    return str(config.get("device", "")).lower() == "cpu"


def _populate_inference_env(env: dict[str, str], *, lancedb_uri: str | None = None) -> None:
    if lancedb_uri:
        env["MCRS_LANCEDB_URI"] = lancedb_uri
    # Tell run_inference_devset.py where to find the shared LiteLLM file cache so
    # repeated LLM extraction calls on the same conversation are served from cache.
    env["MCRS_LITELLM_CACHE_BACKEND"] = LITELLM_CACHE_BACKEND
    env["MCRS_LITELLM_CACHE_DIR"] = LITELLM_CACHE_DIR
    # Point the client-side multimodal (CLAP / SigLIP) vector cache at the same
    # shared volume dir the encoder service commits to, so repeated query texts
    # are served without a Modal RPC and prior committed vectors are reused.
    env["MCRS_EMBEDDING_CACHE_DIR"] = EMBEDDING_CACHE_DIR
    # Reranker artifacts directory (model_full.txt, meta.json, etc.) on the
    # cache volume; configs reference it via ${oc.env:MCRS_RERANKER_DIR,...}.
    env.setdefault("MCRS_RERANKER_DIR", f"{CACHE_DIR}/rerank")
    # Cache root for volume-backed files referenced via ${oc.env:MCRS_CACHE_DIR,...}
    # (e.g. tag_embedding_index). Defaults to ./cache for local runs.
    env.setdefault("MCRS_CACHE_DIR", CACHE_DIR)


def _apply_inference_env(*, lancedb_uri: str | None = None) -> None:
    import os

    _populate_inference_env(os.environ, lancedb_uri=lancedb_uri)


def _run_inference_command(cmd: list[str], *, lancedb_uri: str | None = None) -> None:
    import os
    import subprocess

    env = os.environ.copy()
    _populate_inference_env(env, lancedb_uri=lancedb_uri)

    result = subprocess.run(cmd, cwd="/app", env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Inference failed (exit {result.returncode})")


def _session_ids_file_path(session_ids_json: str) -> str:
    path = Path("/tmp/session_ids.json")
    session_ids = json.loads(session_ids_json)
    path.write_text(json.dumps({"session_ids": session_ids}), encoding="utf-8")
    return str(path)


def _session_ids_file_arg(session_ids_json: str | None) -> list[str]:
    if not session_ids_json:
        return []
    return ["--session_ids_file", _session_ids_file_path(session_ids_json)]


def _shards_for_worker(worker_id: int, num_workers: int, num_shards: int) -> list[int]:
    if num_workers < 1:
        raise ValueError("num_workers must be >= 1")
    if num_shards < 1:
        raise ValueError("num_shards must be >= 1")
    if not (0 <= worker_id < num_workers):
        raise ValueError(f"worker_id={worker_id} out of range for num_workers={num_workers}")
    start = (worker_id * num_shards) // num_workers
    end = ((worker_id + 1) * num_shards) // num_workers
    return list(range(start, end))


def _run_devset_grouped_in_process(
    *,
    tid: str,
    batch_size: int,
    clear_cache: bool,
    num_shards: int,
    shard_ids_json: str,
    run_id: str,
    session_ids_json: str | None = None,
    lancedb_uri: str | None = None,
) -> list[int]:
    import os
    from types import SimpleNamespace

    import run_inference_devset

    if not run_id:
        raise ValueError("Grouped inference requires a non-empty run_id.")
    os.chdir("/app")
    _apply_inference_env(lancedb_uri=lancedb_uri)
    shard_ids = [int(shard_id) for shard_id in json.loads(shard_ids_json)]
    output_suffixes = {
        shard_id: f".run_{run_id}.shard_{shard_id}"
        for shard_id in shard_ids
    }
    args = SimpleNamespace(
        tid=tid,
        batch_size=batch_size,
        session_ids_file=_session_ids_file_path(session_ids_json) if session_ids_json else None,
        num_sessions=0,
        exp_dir=EXP_DIR,
        clear_cache=clear_cache,
        num_shards=num_shards,
        output_suffix="",
    )
    run_inference_devset.run_grouped(args, shard_ids=shard_ids, output_suffixes=output_suffixes)
    return shard_ids


def _run_blindset_grouped_in_process(
    *,
    tid: str,
    batch_size: int,
    eval_dataset: str,
    num_shards: int,
    shard_ids_json: str,
    run_id: str,
    lancedb_uri: str | None = None,
) -> list[int]:
    import os
    from types import SimpleNamespace

    import run_inference_blindset

    if not run_id:
        raise ValueError("Grouped inference requires a non-empty run_id.")
    os.chdir("/app")
    _apply_inference_env(lancedb_uri=lancedb_uri)
    shard_ids = [int(shard_id) for shard_id in json.loads(shard_ids_json)]
    output_suffixes = {
        shard_id: f".run_{run_id}.shard_{shard_id}"
        for shard_id in shard_ids
    }
    args = SimpleNamespace(
        tid=tid,
        eval_dataset=eval_dataset,
        batch_size=batch_size,
        exp_dir=EXP_DIR,
        clear_cache=False,
        num_shards=num_shards,
        output_suffix="",
    )
    run_inference_blindset.run_grouped(args, shard_ids=shard_ids, output_suffixes=output_suffixes)
    return shard_ids


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
    num_shards: int = 1,
    shard_id: int = 0,
    output_suffix: str = "",
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
    if num_shards > 1:
        cmd += ["--num_shards", str(num_shards), "--shard_id", str(shard_id)]
    if output_suffix:
        cmd += ["--output_suffix", output_suffix]

    _run_inference_command(cmd)
    results_vol.commit()
    cache_vol.commit()
    print(f"Results saved to volume: inference/devset/{tid}{output_suffix}.json")


# LightGBM (+ pylance) added on top of the base image for the online LambdaMART
# reranker configs. Defined before the first decorator that references it, since
# Python evaluates decorator expressions at module-import time.
rerank_image = image.uv_pip_install("lightgbm==4.6.0", "pylance")


@app.function(
    image=rerank_image,  # lightgbm needed for online LambdaMART reranker configs
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
    num_shards: int = 1,
    shard_id: int = 0,
    output_suffix: str = "",
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
    if num_shards > 1:
        cmd += ["--num_shards", str(num_shards), "--shard_id", str(shard_id)]
    if output_suffix:
        cmd += ["--output_suffix", output_suffix]

    _run_inference_command(cmd, lancedb_uri=DEFAULT_REMOTE_LANCEDB_URI)
    results_vol.commit()
    cache_vol.commit()
    print(f"CPU results saved to volume: inference/devset/{tid}{output_suffix}.json")


@app.function(
    image=image,
    gpu=INFERENCE_GPU,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    timeout=7200,
)
def _inference_devset_grouped(
    tid: str,
    batch_size: int,
    clear_cache: bool,
    num_shards: int,
    shard_ids_json: str,
    run_id: str,
    session_ids_json: str | None = None,
):
    shard_ids = _run_devset_grouped_in_process(
        tid=tid,
        batch_size=batch_size,
        clear_cache=clear_cache,
        num_shards=num_shards,
        shard_ids_json=shard_ids_json,
        run_id=run_id,
        session_ids_json=session_ids_json,
    )
    results_vol.commit()
    cache_vol.commit()
    print(f"Grouped results saved for devset shards {shard_ids}.")


@app.function(
    image=rerank_image,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    cpu=LANCEDB_INFERENCE_CPU,
    memory=LANCEDB_INFERENCE_MEMORY,
    timeout=7200,
)
def _inference_devset_cpu_grouped(
    tid: str,
    batch_size: int,
    clear_cache: bool,
    num_shards: int,
    shard_ids_json: str,
    run_id: str,
    session_ids_json: str | None = None,
):
    shard_ids = _run_devset_grouped_in_process(
        tid=tid,
        batch_size=batch_size,
        clear_cache=clear_cache,
        num_shards=num_shards,
        shard_ids_json=shard_ids_json,
        run_id=run_id,
        session_ids_json=session_ids_json,
        lancedb_uri=DEFAULT_REMOTE_LANCEDB_URI,
    )
    results_vol.commit()
    cache_vol.commit()
    print(f"CPU grouped results saved for devset shards {shard_ids}.")


@app.function(
    image=image,
    gpu=INFERENCE_GPU,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    timeout=7200,
)
def _inference_blindset(
    tid: str,
    batch_size: int,
    eval_dataset: str,
    num_shards: int = 1,
    shard_id: int = 0,
    output_suffix: str = "",
):
    import sys

    cmd = [
        sys.executable, "/app/run_inference_blindset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
        "--eval_dataset", eval_dataset,
        "--exp_dir", EXP_DIR,
    ]
    if num_shards > 1:
        cmd += ["--num_shards", str(num_shards), "--shard_id", str(shard_id)]
    if output_suffix:
        cmd += ["--output_suffix", output_suffix]
    _run_inference_command(cmd)
    results_vol.commit()
    cache_vol.commit()
    print(f"Results saved to volume: inference/{eval_dataset}/{tid}{output_suffix}.json")


@app.function(
    image=rerank_image,  # includes lightgbm for the online LambdaMART reranker
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    cpu=LANCEDB_INFERENCE_CPU,
    memory=LANCEDB_INFERENCE_MEMORY,
    timeout=7200,
)
def _inference_blindset_cpu(
    tid: str,
    batch_size: int,
    eval_dataset: str,
    num_shards: int = 1,
    shard_id: int = 0,
    output_suffix: str = "",
):
    import sys

    cmd = [
        sys.executable, "/app/run_inference_blindset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
        "--eval_dataset", eval_dataset,
        "--exp_dir", EXP_DIR,
    ]
    if num_shards > 1:
        cmd += ["--num_shards", str(num_shards), "--shard_id", str(shard_id)]
    if output_suffix:
        cmd += ["--output_suffix", output_suffix]
    _run_inference_command(cmd, lancedb_uri=DEFAULT_REMOTE_LANCEDB_URI)
    results_vol.commit()
    cache_vol.commit()
    print(f"CPU results saved to volume: inference/{eval_dataset}/{tid}{output_suffix}.json")


@app.function(
    image=image,
    gpu=INFERENCE_GPU,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    timeout=7200,
)
def _inference_blindset_grouped(
    tid: str,
    batch_size: int,
    eval_dataset: str,
    num_shards: int,
    shard_ids_json: str,
    run_id: str,
):
    shard_ids = _run_blindset_grouped_in_process(
        tid=tid,
        batch_size=batch_size,
        eval_dataset=eval_dataset,
        num_shards=num_shards,
        shard_ids_json=shard_ids_json,
        run_id=run_id,
    )
    results_vol.commit()
    cache_vol.commit()
    print(f"Grouped results saved for {eval_dataset} shards {shard_ids}.")


@app.function(
    image=rerank_image,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    cpu=LANCEDB_INFERENCE_CPU,
    memory=LANCEDB_INFERENCE_MEMORY,
    timeout=7200,
)
def _inference_blindset_cpu_grouped(
    tid: str,
    batch_size: int,
    eval_dataset: str,
    num_shards: int,
    shard_ids_json: str,
    run_id: str,
):
    shard_ids = _run_blindset_grouped_in_process(
        tid=tid,
        batch_size=batch_size,
        eval_dataset=eval_dataset,
        num_shards=num_shards,
        shard_ids_json=shard_ids_json,
        run_id=run_id,
        lancedb_uri=DEFAULT_REMOTE_LANCEDB_URI,
    )
    results_vol.commit()
    cache_vol.commit()
    print(f"CPU grouped results saved for {eval_dataset} shards {shard_ids}.")


# NOTE: the deprecated offline staged-rerank path (_inference_blindset_reranked /
# run_blindset_reranked, which shelled scripts/rerank/run_blindA_reranked_pipeline.py)
# was removed. The reranker is now served ONLINE in-pipeline via the config-driven
# LgbmOnlineReranker — run the rr2 configs through run_inference_blindset /
# run_inference_sharded instead (e.g. tid=state_ranker_v10_lgbm_blindset_A).


# ── Feature engineering on Modal ──────────────────────────────────────────────
# All inputs live on volumes already:
#   Traces  → music-crs-results  at EXP_DIR/inference/devset/<tid>.run_<run_id>.shard_N_trace.jsonl
#   LanceDB → music-crs-models   at MODELS_DIR/lancedb
#   Tag idx → music-crs-cache    at CACHE_DIR/tag_embedding_index/qwen_0_6b.npz
#   Memo    → music-crs-cache    at CACHE_DIR/rerank/q06_memo.json
#   GT      → music-crs-cache    at CACHE_DIR/rerank/ground_truth_devset.json  (upload once)
#
# One-time upload:
#   modal volume put music-crs-cache exp/ground_truth/devset.json rerank/ground_truth_devset.json
#
# Run:
#   modal run modal/app.py::run_build_features_modal --tid <tid> --run-id <run_id> --n-shards <N>
#
# Download features after:
#   modal volume get music-crs-cache rerank/features_v9/ exp/analysis/rerank/features_v9/
#   modal volume get music-crs-cache rerank/constraint_features.parquet exp/analysis/rerank/


@app.function(
    image=rerank_image,  # build_features Catalog.to_lance() needs pylance (lance module)
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    cpu=4,
    memory=16384,
    timeout=3600,
)
def _build_features_shard(shard_idx: int, trace_path: str, out_dir: str, pool_k: int = 500):
    """Build LTR features for one trace shard. Writes shard_{N}.parquet to out_dir.

    pool_k truncates each branch's pool before features are computed; it must
    match the serving reranker's pool_k (rr2 configs use 500) for train/serve
    value parity (the per-pool features z__score__*/ratio__*/pct_* normalize
    over the truncated pool).
    """
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable, "/app/scripts/rerank/build_features.py",
            "--trace", trace_path,
            "--ground-truth", f"{CACHE_DIR}/rerank/ground_truth_devset.json",
            "--db-uri", DEFAULT_REMOTE_LANCEDB_URI,
            "--tag-index", f"{CACHE_DIR}/tag_embedding_index/qwen_0_6b.npz",
            "--embed-memo", f"{CACHE_DIR}/rerank/q06_memo.json",
            "--branch-names", f"{CACHE_DIR}/rerank/branch_names.json",
            "--msg-store", f"{CACHE_DIR}/rerank/raw_msg_store",
            "--out", f"{out_dir}/shard_{shard_idx}.parquet",
            "--pool-k", str(pool_k),
            "--num-shards", "1",
            "--offline",
        ],
        capture_output=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"feature build shard {shard_idx} failed (exit {result.returncode})")
    cache_vol.commit()
    print(f"shard {shard_idx} features done → {out_dir}/shard_{shard_idx}.parquet", flush=True)


@app.function(
    image=rerank_image,  # build_constraint_features opens the LanceDB catalog (pylance)
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    cpu=4,
    memory=16384,
    timeout=3600,
)
def _build_constraint_features(trace_glob: str, features_dir: str, out_path: str):
    """Build constraint sidecar (is_played_track, rejected_*, violates_new_artist)."""
    import subprocess
    import sys

    # The 50 shard writers commit asynchronously; a freshly-spawned reader can
    # otherwise see a pre-commit snapshot of a shard parquet (truncated footer →
    # ArrowInvalid "magic bytes not found"). reload() forces the latest commits.
    cache_vol.reload()
    result = subprocess.run(
        [
            sys.executable, "/app/scripts/rerank/build_constraint_features.py",
            "--trace-glob", trace_glob,
            "--features", features_dir,
            "--db-uri", DEFAULT_REMOTE_LANCEDB_URI,
            "--out", out_path,
        ],
        capture_output=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"constraint features failed (exit {result.returncode})")
    cache_vol.commit()
    print(f"constraint features done → {out_path}", flush=True)


@app.function(
    image=rerank_image,  # build_label_weights opens the LanceDB catalog (pylance)
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    cpu=4,
    memory=16384,
    timeout=3600,
)
def _build_label_weights(trace_glob: str, out_path: str):
    """Build train-time label-quality weights (next-turn-rejection downweighting)."""
    import subprocess
    import sys

    cache_vol.reload()  # see all shard commits (avoid pre-commit truncated read)
    result = subprocess.run(
        [
            sys.executable, "/app/scripts/rerank/build_label_weights.py",
            "--trace-glob", trace_glob,
            "--ground-truth", f"{CACHE_DIR}/rerank/ground_truth_devset.json",
            "--db-uri", DEFAULT_REMOTE_LANCEDB_URI,
            "--out", out_path,
        ],
        capture_output=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"label weights failed (exit {result.returncode})")
    cache_vol.commit()
    print(f"label weights done → {out_path}", flush=True)


@app.local_entrypoint()
def run_build_features_modal(
    tid: str = "state_ranker_v10_rrf_devset",
    run_id: str = "20260611T035130Z-2e6dfc",
    n_shards: int = 5,
    out_name: str = "features_v9",
    skip_constraint: bool = False,
    pool_k: int = 500,
):
    """Build LTR features from sharded trace files on Modal.

    pool_k defaults to 500 to match the rr2 serving configs (qu_kwargs.reranker
    .pool_k). Keep them equal — the per-pool features normalize over the pool
    truncated to pool_k, so a build/serve mismatch is train/serve value drift.

    Prereq (one-time upload):
      modal volume put music-crs-cache exp/ground_truth/devset.json rerank/ground_truth_devset.json

    Example:
      modal run modal/app.py::run_build_features_modal \\
          --tid state_ranker_v10_rrf_devset --run-id 20260613T095225Z-8aec6e --n-shards 50

    Download after:
      modal volume get music-crs-cache rerank/<out_name>/ exp/analysis/rerank/<out_name>/
      modal volume get music-crs-cache rerank/constraint_features.parquet exp/analysis/rerank/
    """
    out_dir = f"{CACHE_DIR}/rerank/{out_name}"
    trace_paths = [
        f"{EXP_DIR}/inference/devset/{tid}.run_{run_id}.shard_{i}_trace.jsonl"
        for i in range(n_shards)
    ]
    trace_glob = f"{EXP_DIR}/inference/devset/{tid}.run_{run_id}.shard_*_trace.jsonl"

    # Keep the canonical sidecar name for the default build; isolate it for any
    # other out_name (e.g. validation runs) so they never clobber the training
    # input the train pipeline reads (rerank/constraint_features.parquet).
    suffix = "" if out_name == "features_v9" else f"_{out_name}"
    constraint_file = f"constraint_features{suffix}.parquet"
    weights_file = f"label_weights_v9{suffix}.parquet"

    print(f"Building features from {n_shards} trace shards → {out_dir} (pool_k={pool_k})")
    list(_build_features_shard.starmap(
        [(i, path, out_dir, pool_k) for i, path in enumerate(trace_paths)]
    ))
    if skip_constraint:
        print("Skipping constraint sidecar + label weights (skip_constraint=True).")
        print(f"Done. Download with:")
        print(f"  modal volume get music-crs-cache rerank/{out_name}/ exp/analysis/rerank/{out_name}/")
        return
    # Both training sidecars read the catalog + traces; run them in parallel.
    print("All feature shards done. Building constraint sidecar + label weights …")
    handles = [
        _build_constraint_features.spawn(
            trace_glob=trace_glob, features_dir=out_dir,
            out_path=f"{CACHE_DIR}/rerank/{constraint_file}"),
        _build_label_weights.spawn(
            trace_glob=trace_glob, out_path=f"{CACHE_DIR}/rerank/{weights_file}"),
    ]
    for h in handles:
        h.get()
    print(f"Done. Download with:")
    print(f"  modal volume get music-crs-cache rerank/{out_name}/ exp/analysis/rerank/{out_name}/")
    print(f"  modal volume get music-crs-cache rerank/{constraint_file} exp/analysis/rerank/")
    print(f"  modal volume get music-crs-cache rerank/{weights_file} exp/analysis/rerank/")


@app.local_entrypoint()
def run_build_features_for_ranker(
    lineage: str = "v10",
    tid: str = "state_ranker_v10_rrf_devset",
    run_id: str = "",
    n_shards: int = 50,
    pool_k: int = 500,
):
    """Build ranker features under a lineage-scoped cache namespace.

    For v10 this writes:
      /root/cache/rerank/v10/features/
      /root/cache/rerank/v10/constraint_features.parquet
      /root/cache/rerank/v10/label_weights.parquet
    """
    if not run_id:
        raise ValueError("--run-id is required so feature builds never mix runs")
    paths = _ranker_remote_paths(lineage)
    out_dir = paths["features_dir"]
    trace_paths = [
        f"{EXP_DIR}/inference/devset/{tid}.run_{run_id}.shard_{i}_trace.jsonl"
        for i in range(n_shards)
    ]
    trace_glob = f"{EXP_DIR}/inference/devset/{tid}.run_{run_id}.shard_*_trace.jsonl"

    print(f"Building {lineage} features from {n_shards} trace shards → {out_dir} (pool_k={pool_k})")
    list(_build_features_shard.starmap(
        [(i, path, out_dir, pool_k) for i, path in enumerate(trace_paths)]
    ))
    print("All feature shards done. Building lineage-scoped constraint sidecar + label weights …")
    handles = [
        _build_constraint_features.spawn(
            trace_glob=trace_glob,
            features_dir=out_dir,
            out_path=paths["sidecar"],
        ),
        _build_label_weights.spawn(
            trace_glob=trace_glob,
            out_path=paths["weights"],
        ),
    ]
    for h in handles:
        h.get()
    rel_features = out_dir.replace(f"{CACHE_DIR}/", "")
    rel_sidecar = paths["sidecar"].replace(f"{CACHE_DIR}/", "")
    rel_weights = paths["weights"].replace(f"{CACHE_DIR}/", "")
    print("Done. Download with:")
    print(f"  modal volume get music-crs-cache {rel_features}/ exp/analysis/rerank/{lineage}/features/")
    print(f"  modal volume get music-crs-cache {rel_sidecar} exp/analysis/rerank/{lineage}/")
    print(f"  modal volume get music-crs-cache {rel_weights} exp/analysis/rerank/{lineage}/")


@app.local_entrypoint()
def run_sidecars_then_train(
    lineage: str,
    tid: str = "state_ranker_v10_rrf_devset",
    run_id: str = "",
):
    """Recovery path: rebuild only the constraint + label sidecars from feature
    shards that already exist on the volume, then train — skips the (expensive)
    50-shard feature rebuild. Use when shard build succeeded but the sidecar
    stage hit the volume-commit read race."""
    if not run_id:
        raise ValueError("--run-id is required so sidecars never mix runs")
    paths = _ranker_remote_paths(lineage)
    trace_glob = f"{EXP_DIR}/inference/devset/{tid}.run_{run_id}.shard_*_trace.jsonl"
    print(f"[{lineage}] rebuilding sidecars from existing shards in {paths['features_dir']} …")
    handles = [
        _build_constraint_features.spawn(
            trace_glob=trace_glob,
            features_dir=paths["features_dir"],
            out_path=paths["sidecar"],
        ),
        _build_label_weights.spawn(trace_glob=trace_glob, out_path=paths["weights"]),
    ]
    for h in handles:
        h.get()
    print(f"[{lineage}] sidecars done → training …")
    _run_train_lgbm_ranker(lineage=lineage)


# ── LightGBM CV training (CPU) ──────────────────────────────────────────────────
# build → 5 parallel CV folds → finalize → full_model. Training is CPU-only: the
# PyPI lightgbm wheel has no GPU/CUDA build (device_type='gpu' raises "GPU Tree
# Learner was not enabled"), and at this data scale CPU lambdarank is fast.
# Prereq: the feature parquet + sidecars on cache_vol (run_build_features_modal).
#   python -m modal run modal/app.py::run_train_v9

_TRAIN_IMAGE = (
    # Plain CPU base (NOT nvidia/cuda — training never uses the GPU; the cuda base
    # only added a misleading "NVIDIA driver not detected" banner and bulk).
    modal.Image.debian_slim(python_version="3.11")
    # libgomp1: lightgbm's native extension dlopens the OpenMP runtime
    # (libgomp.so.1) at import.
    .apt_install("libgomp1")
    # omegaconf: Modal imports the whole modal/app.py module in every container
    # (to locate the @app.function), and app.py's top-level imports include
    # `from omegaconf import OmegaConf`. Training only shells out to train_v9.py
    # (lightgbm/numpy/pandas/pyarrow), but the module-import still needs omegaconf.
    .pip_install("lightgbm>=4.6.0", "numpy", "pandas", "pyarrow>=16.0", "omegaconf")
    .add_local_file(
        "scripts/rerank/train_v9.py",
        "/app/train_v9.py",
        copy=True,
    )
    # app.py reads modal/config.yaml at module-import time (OmegaConf.load via
    # _config_path → /app/modal/config.yaml). Without it the container can't
    # import app.py to locate the train function.
    .add_local_file(
        "modal/config.yaml",
        "/app/modal/config.yaml",
        copy=True,
    )
)

# Paths inside the cache volume for training data
_TRAIN_V9_REMOTE_DIR   = f"{CACHE_DIR}/rerank/train_v9"
_TRAIN_FEATURES_DIR    = f"{CACHE_DIR}/rerank/features_v9"
_TRAIN_SIDECAR         = f"{CACHE_DIR}/rerank/constraint_features.parquet"
_TRAIN_WEIGHTS         = f"{CACHE_DIR}/rerank/label_weights_v9.parquet"
_TRAIN_LOCKBOX         = f"{CACHE_DIR}/rerank/lockbox_users.json"
_TRAIN_GT              = f"{CACHE_DIR}/rerank/ground_truth_devset.json"


def _ranker_remote_paths(lineage: str = "v9") -> dict[str, str]:
    if lineage == "v9":
        return {
            "train_dir": _TRAIN_V9_REMOTE_DIR,
            "features_dir": _TRAIN_FEATURES_DIR,
            "sidecar": _TRAIN_SIDECAR,
            "weights": _TRAIN_WEIGHTS,
        }
    safe = str(lineage).strip().strip("/")
    if not safe or "/" in safe or ".." in safe:
        raise ValueError(f"Invalid ranker lineage: {lineage!r}")
    base = f"{CACHE_DIR}/rerank/{safe}"
    return {
        "train_dir": f"{base}/train",
        "features_dir": f"{base}/features",
        "sidecar": f"{base}/constraint_features.parquet",
        "weights": f"{base}/label_weights.parquet",
    }


def _train_cmd(stage: str, fold: int | None = None, lineage: str = "v9") -> list:
    import sys
    paths = _ranker_remote_paths(lineage)
    cmd = [
        # sys.executable, not a hardcoded path — the interpreter location varies
        # by base image.
        sys.executable, "/app/train_v9.py",
        "--stage", stage,
        "--out-dir", paths["train_dir"],
        "--features-dir", paths["features_dir"],
        "--sidecar", paths["sidecar"],
        "--weights", paths["weights"],
        "--lockbox", _TRAIN_LOCKBOX,
        "--gt", _TRAIN_GT,
    ]
    if fold is not None:
        cmd += ["--fold", str(fold)]
    return cmd


@app.function(
    image=_TRAIN_IMAGE,
    cpu=8,
    memory=32768,
    timeout=3600,
    volumes={CACHE_DIR: cache_vol},
)
def _train_build_cpu(lineage: str = "v9"):
    """Build the feature matrix (X.npy + id arrays) from parquet on the volume."""
    import subprocess
    cache_vol.reload()
    result = subprocess.run(_train_cmd("build", lineage=lineage), capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(f"build stage failed (exit {result.returncode})")
    cache_vol.commit()
    print("build complete", flush=True)


@app.function(
    image=_TRAIN_IMAGE,
    cpu=8,
    memory=32768,
    timeout=3600,
    volumes={CACHE_DIR: cache_vol},
)
def _train_fold(fold: int, lineage: str = "v9"):
    """Run one LambdaMART CV fold. Reads/writes artifacts from cache_vol.

    CPU, not GPU: the PyPI lightgbm wheel is built without GPU/CUDA support
    (device_type='gpu' raises "GPU Tree Learner was not enabled in this build").
    At this data scale (~1.2M rows × 148 cols) CPU lambdarank is fast enough.
    """
    import subprocess
    result = subprocess.run(_train_cmd("fold", fold=fold, lineage=lineage), capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(f"fold {fold} failed (exit {result.returncode})")
    cache_vol.commit()
    print(f"fold {fold} complete", flush=True)


@app.function(
    image=_TRAIN_IMAGE,
    cpu=4,
    memory=16384,
    timeout=1800,
    volumes={CACHE_DIR: cache_vol},
)
def _train_finalize_cpu(lineage: str = "v9"):
    """Aggregate fold scores, train full model, report OOF metrics."""
    import subprocess
    result = subprocess.run(_train_cmd("finalize", lineage=lineage), capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(f"finalize failed (exit {result.returncode})")
    cache_vol.commit()
    print("finalize complete", flush=True)


@app.function(
    image=_TRAIN_IMAGE,
    cpu=4,
    memory=16384,
    timeout=1800,
    volumes={CACHE_DIR: cache_vol},
)
def _train_full_model_cpu(lineage: str = "v9"):
    """Train the single full-data model at the CV-median round count.

    This is the stage that writes model_full.txt — the artifact published into
    the committed models/reranker_<lineage>/ bundle (the active config loads
    models/reranker_v10/). finalize only reports OOF metrics.
    """
    import subprocess
    result = subprocess.run(_train_cmd("full_model", lineage=lineage), capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(f"full_model failed (exit {result.returncode})")
    cache_vol.commit()
    print("full_model complete → model_full.txt", flush=True)


@app.local_entrypoint()
def run_train_v9():
    """Full training pipeline on Modal (CPU): build → 5× CV fold → finalize → full_model.

    Always rebuilds the feature matrix from scratch — no cached X.npy reuse, so a
    stale matrix can never silently train the wrong model.

    Stages, all reading/writing the cache volume under rerank/train_v9/:
      build       — assemble the feature matrix (X.npy + id arrays) from the
                    features_v9 parquet (produced by run_build_features_modal,
                    which routes through the SAME compute_turn_features the
                    online reranker uses → train/serve schema parity).
      fold ×5     — user-grouped CV folds, run in parallel.
      finalize    — OOF metrics + by-turn/cold-slice diagnostics (no model file).
      full_model  — the served model: model_full.txt at the CV-median rounds.

    One-time data upload (run from repo root), OR build on Modal first via
    run_build_features_modal (writes features_v9/ + constraint_features.parquet
    straight to the cache volume):
      modal volume put music-crs-cache exp/analysis/rerank/label_weights_v9.parquet rerank/label_weights_v9.parquet
      modal volume put music-crs-cache exp/analysis/rerank/lockbox_users.json       rerank/lockbox_users.json
      modal volume put music-crs-cache exp/ground_truth/devset.json                 rerank/ground_truth_devset.json
    """
    _run_train_lgbm_ranker(lineage="v9")


@app.local_entrypoint()
def run_train_lgbm_ranker(lineage: str = "v10"):
    """Train a LightGBM ranker for the requested lineage.

    v10 reads/writes under /root/cache/rerank/v10 so old v9 scratch cannot be
    accidentally reused.
    """
    _run_train_lgbm_ranker(lineage=lineage)


@app.function(
    image=_TRAIN_IMAGE,
    cpu=2,
    memory=4096,
    timeout=21600,  # 6h ceiling; only coordinates the stage functions
    volumes={CACHE_DIR: cache_vol},
)
def _train_orchestrate_remote(lineage: str = "v10"):
    """Run the full build -> fold x5 -> finalize -> full_model pipeline
    server-side. The heavy work runs in the stage functions' own containers; this
    just coordinates them, so the pipeline survives local-driver disconnects."""
    _run_train_lgbm_ranker(lineage=lineage)


@app.local_entrypoint()
def run_train_lgbm_ranker_detached(lineage: str = "v10"):
    """Fire the full training pipeline server-side and return immediately.

    Unlike run_train_lgbm_ranker (orchestrated from the local driver, which dies
    if the client disconnects mid-build), this spawns one remote orchestrator
    that runs every stage on Modal. Poll rerank/<lineage>/train/metrics.json on
    the cache volume to detect completion.
    """
    call = _train_orchestrate_remote.spawn(lineage)
    print(f"SPAWNED remote training orchestrator: call_id={call.object_id} lineage={lineage}")


def _run_train_lgbm_ranker(lineage: str) -> None:
    import time
    t0 = time.time()
    paths = _ranker_remote_paths(lineage)

    def _lap(label, since):
        print(f"  [{label}] {time.time() - since:.0f}s (total {time.time() - t0:.0f}s)", flush=True)

    print(f"Training lineage={lineage} using features {paths['features_dir']}")
    print("Step 1/4: building feature matrix on Modal …")
    s = time.time(); _train_build_cpu.remote(lineage); _lap("build", s)
    print("Step 2/4: training 5 CV folds in parallel …")
    s = time.time(); list(_train_fold.starmap([(f, lineage) for f in range(5)])); _lap("folds", s)
    print("Step 3/4: finalize + OOF metrics …")
    s = time.time(); _train_finalize_cpu.remote(lineage); _lap("finalize", s)
    print("Step 4/4: training full-data model → model_full.txt …")
    s = time.time(); _train_full_model_cpu.remote(lineage); _lap("full_model", s)
    print(f"Training complete in {time.time() - t0:.0f}s total.")
    print("Fetch the served-bundle artifacts:")
    rel_train = paths["train_dir"].replace(f"{CACHE_DIR}/", "")
    print(f"  modal volume get music-crs-cache {rel_train}/model_full.txt   exp/analysis/rerank/{lineage}/train/")
    print(f"  modal volume get music-crs-cache {rel_train}/meta.json        exp/analysis/rerank/{lineage}/train/")
    print(f"  modal volume get music-crs-cache {rel_train}/cat_maps.json    exp/analysis/rerank/{lineage}/train/")
    print(f"Then publish into the committed bundle (models/reranker_{lineage}/):")
    print(f"  cp exp/analysis/rerank/{lineage}/train/model_full.txt   models/reranker_{lineage}/model.txt")
    print(f"  cp exp/analysis/rerank/{lineage}/train/meta.json        models/reranker_{lineage}/meta.json")
    print(f"  cp exp/analysis/rerank/{lineage}/train/cat_maps.json    models/reranker_{lineage}/cat_maps.json")


@app.cls(
    image=image,
    volumes={MODELS_DIR: models_vol},
    secrets=[ENV_SECRET],
    cpu=LANCEDB_QUERY_CPU,
    memory=LANCEDB_QUERY_MEMORY,
    timeout=600,
    min_containers=0,
    max_containers=LANCEDB_QUERY_MAX_CONTAINERS,
    scaledown_window=LANCEDB_QUERY_SCALEDOWN_WINDOW,
)
class ModalRetrievalService:
    @modal.enter()
    def setup(self):
        import os

        from mcrs.embeddings import LiteLLMEmbeddingClient
        from mcrs.lancedb.retriever import LanceDbRetriever
        from mcrs.retrieval_services import RetrievalService

        embedding_client = None
        embedding_model = os.environ.get("MCRS_EMBEDDING_MODEL")
        if embedding_model:
            embedding_client = LiteLLMEmbeddingClient(
                model_name=embedding_model,
                api_base=os.environ.get("MCRS_EMBEDDING_API_BASE"),
                api_key=os.environ.get("MCRS_EMBEDDING_API_KEY") or os.environ.get("HF_TOKEN"),
                batch_size=int(os.environ.get("MCRS_EMBEDDING_BATCH_SIZE", "128")),
            )
        retriever = LanceDbRetriever.from_retrieval_config(
            _default_lancedb_retrieval_config(),
            embedding_client=embedding_client,
        )
        self.embedding_client = embedding_client
        self.service = RetrievalService(retriever=retriever, embedding_client=embedding_client)
        self._retrieval_service_cache = {}
        self._retrieval_service_cache_order = []

    def _service_for_retrieval_config(self, retrieval_config: dict | None, topk: int):
        if retrieval_config is None:
            return self.service

        from mcrs.lancedb.retriever import LanceDbRetriever
        from mcrs.retrieval_services import RetrievalService

        config = _default_lancedb_retrieval_config(topk=topk)
        config.update(dict(retrieval_config))
        cache_key = _retrieval_config_cache_key(config)
        cached_service = self._retrieval_service_cache.get(cache_key)
        if cached_service is not None:
            return cached_service

        retriever = LanceDbRetriever.from_retrieval_config(
            config,
            embedding_client=self.embedding_client,
        )
        service = RetrievalService(retriever=retriever, embedding_client=self.embedding_client)
        self._retrieval_service_cache[cache_key] = service
        self._retrieval_service_cache_order.append(cache_key)
        while len(self._retrieval_service_cache_order) > RETRIEVAL_SERVICE_CACHE_SIZE:
            old_key = self._retrieval_service_cache_order.pop(0)
            self._retrieval_service_cache.pop(old_key, None)
        return service

    @modal.method()
    def retrieve(
        self,
        query: str,
        topk: int = 20,
        retrieval_config: dict | None = None,
    ) -> list[str]:
        service = self._service_for_retrieval_config(retrieval_config, topk=topk)
        return service.retrieve(query, topk=topk)

    @modal.method()
    def retrieve_batch(
        self,
        queries: list[str],
        topk: int = 20,
        retrieval_config: dict | None = None,
    ) -> list[list[str]]:
        service = self._service_for_retrieval_config(retrieval_config, topk=topk)
        return service.retrieve_batch(queries, topk=topk)

    @modal.method()
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self.service.embed_batch(texts)


@app.cls(
    image=image,
    gpu=QWEN3_ENCODER_GPU,
    volumes={HF_CACHE_DIR: hf_cache_vol, CACHE_DIR: cache_vol},
    secrets=[ENV_SECRET],
    cpu=QWEN3_ENCODER_CPU,
    memory=QWEN3_ENCODER_MEMORY,
    timeout=QWEN3_ENCODER_TIMEOUT,
    min_containers=0,
    max_containers=QWEN3_ENCODER_MAX_CONTAINERS,
    scaledown_window=QWEN3_ENCODER_SCALEDOWN_WINDOW,
)
class Qwen3Encoder:
    """GPU-backed Qwen3-Embedding-0.6B query encoder.

    Replaces the per-turn CPU encode (~1-2 s) with a remote GPU call
    (~50 ms on T4). Used by the v0+ compiler via
    `mcrs.embeddings.modal_qwen3_client.ModalQwen3EmbeddingClient` when
    `encoder.backend: "modal"` is set in the compiler config.

    Scales to zero after `scaledown_window` seconds; cold start ~30 s
    (model load from HF cache volume). Deploy via:
        modal deploy modal/app.py
    """

    @modal.enter()
    def setup(self):
        self._cache_enabled = False  # set True after cache init; keeps @modal.exit() safe if setup raises
        import os

        os.environ.setdefault("HF_HOME", HF_CACHE_DIR)
        from mcrs.embeddings.qwen3_embedding import Qwen3EmbeddingClient

        self.client = Qwen3EmbeddingClient(
            device="cuda",
            torch_dtype_name=QWEN3_ENCODER_TORCH_DTYPE,
            batch_size=QWEN3_ENCODER_BATCH_SIZE,
        )
        # Eager-load the model + tokenizer so the first remote call doesn't
        # pay the load tax on the request path.
        self.client._ensure_loaded()

        from mcrs.embeddings.embedding_cache import (
            CachedTextEmbedder,
            DiskVectorCache,
        )

        cache_enabled = os.environ.get("EMBEDDING_CACHE_ENABLED", "1") != "0"
        self._cache_enabled = cache_enabled
        self.client = CachedTextEmbedder(
            self.client,
            DiskVectorCache(EMBEDDING_CACHE_DIR),
            f"qwen3:Qwen3-Embedding-0.6B:dtype={QWEN3_ENCODER_TORCH_DTYPE}",
            enabled=cache_enabled,
        )

    @modal.method()
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self.client.embed_batch(texts)

    @modal.exit()
    def _commit_embedding_cache(self):
        if self._cache_enabled:
            cache_vol.commit()


@app.cls(
    image=image,
    volumes={CACHE_DIR: cache_vol},
    secrets=[ENV_SECRET],
    cpu=LITELLM_CPU,
    memory=LITELLM_MEMORY,
    timeout=600,
    min_containers=0,
    max_containers=LITELLM_MAX_CONTAINERS,
    scaledown_window=LITELLM_SCALEDOWN_WINDOW,
)
class ModalLiteLLMService:
    @modal.enter()
    def setup(self):
        import os

        import litellm
        from mcrs.litellm_cache import setup_litellm_cache

        litellm.success_callback = [self._track_cache_hit]
        setup_litellm_cache(
            backend=LITELLM_CACHE_BACKEND,
            cache_dir=LITELLM_CACHE_DIR,
            supported_call_types=["completion", "acompletion", "embedding", "aembedding"],
        )
        self.last_cache_hit = None
        self.hf_token = os.environ.get("HF_TOKEN")
        self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
        self.deepinfra_api_key = os.environ.get("DEEPINFRA_API_KEY")
        self.default_embedding_model = os.environ.get("MCRS_TEST_EMBEDDING_MODEL", LITELLM_EMBEDDING_MODEL)
        self.default_chat_model = os.environ.get("MCRS_TEST_CHAT_MODEL", LITELLM_CHAT_MODEL)

    @staticmethod
    def _cache_hit_from_response(completion_response) -> bool | None:
        hidden = getattr(completion_response, "_hidden_params", None)
        if isinstance(hidden, dict) and "cache_hit" in hidden:
            return bool(hidden["cache_hit"])
        return None

    def _track_cache_hit(self, kwargs, completion_response, start_time, end_time):
        cache_hit = kwargs.get("cache_hit")
        if cache_hit is None:
            cache_hit = self._cache_hit_from_response(completion_response)
        self.last_cache_hit = None if cache_hit is None else bool(cache_hit)

    @modal.method()
    def embed_once_with_cache_status(
        self,
        text: str,
        model_name: str | None = None,
        api_base: str | None = None,
    ) -> dict:
        from mcrs.embeddings import LiteLLMEmbeddingClient

        selected_model = model_name or self.default_embedding_model
        selected_api_base = api_base
        embedder = LiteLLMEmbeddingClient(
            model_name=selected_model,
            api_base=selected_api_base,
            api_key=self._api_key_for_model(selected_model, selected_api_base),
            batch_size=8,
            cache={},
        )
        self.last_cache_hit = None
        cache_hit_before = self._cache_hit_before_call(embedder.build_request_kwargs([text]))
        try:
            vector = embedder.embed_one(text)
        except Exception as exc:
            return self._error_response("embedding", selected_model, exc)
        return {
            "kind": "embedding",
            "ok": True,
            "model": embedder.model_name,
            "cache_hit": self._cache_status(cache_hit_before),
            "dimensions": len(vector),
        }

    @modal.method()
    def chat_once_with_cache_status(
        self,
        prompt: str,
        model_name: str | None = None,
        api_base: str | None = None,
    ) -> dict:
        from mcrs.lm_modules.litellm_client import LiteLLMChatClient

        selected_model = model_name or self.default_chat_model
        selected_api_base = api_base
        chat_client = LiteLLMChatClient(
            model_name=selected_model,
            api_base=selected_api_base,
            api_key=self._api_key_for_model(selected_model, selected_api_base),
            temperature=0.0,
            max_tokens=32,
        )
        self.last_cache_hit = None
        messages = [{"role": "user", "content": prompt}]
        cache_control = {}
        cache_hit_before = self._cache_hit_before_call(
            chat_client.build_request_kwargs(messages=messages, cache=cache_control)
        )
        try:
            content = chat_client.chat(
                messages,
                cache=cache_control,
            )
        except Exception as exc:
            return self._error_response("chat", selected_model, exc)
        return {
            "kind": "chat",
            "ok": True,
            "model": chat_client.model_name,
            "cache_hit": self._cache_status(cache_hit_before),
            "content": content,
        }

    @staticmethod
    def _cache_hit_before_call(call_kwargs: dict) -> bool | None:
        import litellm

        if litellm.cache is None:
            return None
        try:
            return litellm.cache.get_cache(**call_kwargs) is not None
        except Exception as exc:
            print(f"LiteLLM cache lookup failed: {type(exc).__name__}: {exc}")
            return None

    def _cache_status(self, cache_hit_before: bool | None) -> bool | None:
        if cache_hit_before is not None:
            return cache_hit_before
        return self.last_cache_hit

    def _api_key_for_model(self, model_name: str, api_base: str | None) -> str | None:
        return _api_key_for_litellm_model(
            model_name,
            api_base,
            hf_token=self.hf_token,
            openrouter_api_key=self.openrouter_api_key,
            deepinfra_api_key=self.deepinfra_api_key,
        )

    def _error_response(self, kind: str, model_name: str, exc: Exception) -> dict:
        return {
            "kind": kind,
            "ok": False,
            "model": model_name,
            "cache_hit": self.last_cache_hit,
            "error_type": type(exc).__name__,
            "error": str(exc).splitlines()[0][:1000],
        }


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
    from mcrs.retrieval_modules.lancedb import LANCEDB_MODEL

    config = dict(retrieval_config or {})
    defaults = _default_lancedb_retrieval_config(topk=topk)
    for key, value in defaults.items():
        config.setdefault(key, value)
    config["device"] = "cpu"
    _ensure_query_lancedb_fts_only(config)

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


def _qwen_generated_embedding_field(document_kind: str, model_size: str) -> str:
    if document_kind not in QWEN_GENERATED_DOCUMENT_KINDS:
        raise ValueError(f"Unsupported Qwen document kind: {document_kind!r}")
    normalized_size = model_size.lower()
    if normalized_size not in QWEN_GENERATED_MODEL_SIZES:
        raise ValueError(f"Unsupported Qwen model size: {model_size!r}")
    return f"{document_kind}-qwen3_embedding_{normalized_size}"


def _qwen_generated_model_name(model_size: str) -> str:
    normalized_size = model_size.lower()
    if normalized_size == "4b":
        return "openai/Qwen/Qwen3-Embedding-4B"
    if normalized_size == "8b":
        return "openai/Qwen/Qwen3-Embedding-8B"
    raise ValueError(f"Unsupported Qwen model size: {model_size!r}")


def _render_qwen_item_document(metadata_row: dict, document_kind: str) -> str:
    from mcrs.embeddings.qwen3_embedding import (
        talkplay_attributes_document_template,
        talkplay_metadata_document_template,
    )

    if document_kind == "metadata":
        return talkplay_metadata_document_template(metadata_row) or "music track"
    if document_kind == "attributes":
        attributes = {
            "tags": metadata_row.get("tag_list") or metadata_row.get("tags") or [],
            "tempo": metadata_row.get("tempo") or [],
            "key": metadata_row.get("key") or [],
            "chord": metadata_row.get("chord") or [],
        }
        return talkplay_attributes_document_template(attributes) or "music attributes"
    raise ValueError(f"Unsupported Qwen document kind: {document_kind!r}")


def _embedding_from_litellm_cached_response(value) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if not isinstance(value, dict):
        return None

    response = value.get("response", value)
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            return None
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if not data:
        return None
    first = data[0]
    embedding = first.get("embedding") if isinstance(first, dict) else getattr(first, "embedding", None)
    if embedding is None:
        return None
    return [float(number) for number in embedding]


def _cached_litellm_embedding_vector(request_kwargs: dict) -> list[float] | None:
    import litellm

    cache = getattr(litellm, "cache", None)
    get_cache = getattr(cache, "get_cache", None)
    if get_cache is None:
        return None
    try:
        return _embedding_from_litellm_cached_response(get_cache(**request_kwargs))
    except Exception as exc:  # noqa: BLE001 - cache read failures should degrade to API calls
        print(f"LiteLLM embedding cache lookup failed: {type(exc).__name__}: {exc}")
        return None


# Per-process state for the ProcessPoolExecutor fan-out. A fresh catalog build
# is dominated by ~188k per-item embedding cache lookups whose hot work (litellm
# machinery + JSON vector decode) holds the GIL, so a ThreadPoolExecutor pins
# everything to one core. ProcessPoolExecutor gives each worker its own
# interpreter/GIL so the container's CPUs are actually used. Each worker process
# configures its own litellm cache (via the initializer) and lazily builds one
# embedding client per model size; clients/cache cannot be pickled across the
# process boundary, so they are rebuilt inside the worker rather than passed in.
_QWEN_WORKER_CTX: dict = {}


def _init_qwen_embed_worker(
    cache_backend,
    cache_dir,
    api_base_by_model_size,
    api_key,
    timeout_s,
    request_delay_s,
    client_factory=None,
    setup_cache=True,
):
    """ProcessPoolExecutor initializer: set up the litellm cache + clients once per process."""
    from mcrs.embeddings import LiteLLMEmbeddingClient

    if setup_cache:
        from mcrs.litellm_cache import setup_litellm_cache

        setup_litellm_cache(
            backend=cache_backend,
            cache_dir=cache_dir,
            supported_call_types=["embedding", "aembedding"],
        )

    factory = client_factory or LiteLLMEmbeddingClient
    _QWEN_WORKER_CTX.clear()
    _QWEN_WORKER_CTX["clients"] = {
        model_size: factory(
            model_name=_qwen_generated_model_name(model_size),
            api_base=api_base,
            api_key=api_key,
            batch_size=1,
            encoding_format="float",
            cache={},
            extra_params={"timeout": int(timeout_s)},
        )
        for model_size, api_base in api_base_by_model_size.items()
    }
    _QWEN_WORKER_CTX["request_delay_s"] = float(request_delay_s)


def _qwen_embed_worker(task):
    """ProcessPoolExecutor worker: cache lookup first, endpoint on miss.

    Returns ``(row_index, track_id, field_name, vector, cache_hit)``. Relies on
    ``_QWEN_WORKER_CTX`` populated by :func:`_init_qwen_embed_worker`.
    """
    import time

    row_index, track_id, model_size, document_kind, document = task
    client = _QWEN_WORKER_CTX["clients"][model_size]
    request_kwargs = client.build_request_kwargs([document])
    field_name = _qwen_generated_embedding_field(document_kind, model_size)

    cached_vector = _cached_litellm_embedding_vector(request_kwargs)
    if cached_vector is not None:
        return row_index, track_id, field_name, cached_vector, True

    vector = client.embed_one(document)
    request_delay_s = _QWEN_WORKER_CTX.get("request_delay_s", 0.0)
    if request_delay_s > 0:
        time.sleep(float(request_delay_s))
    return row_index, track_id, field_name, vector, False


def _build_generated_qwen_embedding_rows(
    metadata_rows: list[dict],
    *,
    model_sizes: tuple[str, ...] = QWEN_GENERATED_MODEL_SIZES,
    document_kinds: tuple[str, ...] = QWEN_GENERATED_DOCUMENT_KINDS,
    api_base_by_model_size: dict[str, str],
    api_key: str,
    client_factory=None,
    request_delay_s: float = 0.0,
    timeout_s: int = 600,
    max_in_flight: int = 1,
    cache_backend: str | None = None,
    cache_dir: str | None = None,
    executor_factory=None,
) -> tuple[list[dict], dict]:
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, wait
    import time

    from mcrs.embeddings import LiteLLMEmbeddingClient

    max_workers = max(1, int(max_in_flight))
    # A ProcessPoolExecutor cannot carry an injected client_factory (closures are
    # not picklable / monkeypatches do not cross the process boundary), so the
    # injected-factory case stays in-process on threads. Real Modal builds pass no
    # factory and fan out across processes to use every CPU.
    use_processes = client_factory is None and max_workers > 1

    clients = {}
    if not use_processes:
        client_factory = client_factory or LiteLLMEmbeddingClient
        clients = {
            model_size: client_factory(
                model_name=_qwen_generated_model_name(model_size),
                api_base=api_base_by_model_size[model_size],
                api_key=api_key,
                batch_size=1,
                encoding_format="float",
                cache={},
                extra_params={"timeout": int(timeout_s)},
            )
            for model_size in model_sizes
        }
    stats = {
        "rows": len(metadata_rows),
        "cache_hits": 0,
        "endpoint_requests": 0,
    }
    generated_rows: list[dict] = [
        {"track_id": str(metadata_row["track_id"])}
        for metadata_row in metadata_rows
    ]
    total_expected = len(metadata_rows) * len(model_sizes) * len(document_kinds)

    def _tasks():
        for row_index, metadata_row in enumerate(metadata_rows):
            track_id = str(metadata_row["track_id"])
            for model_size in model_sizes:
                for document_kind in document_kinds:
                    document = _render_qwen_item_document(metadata_row, document_kind)
                    yield row_index, track_id, model_size, document_kind, document

    def _embed_task(row_index: int, track_id: str, model_size: str, document_kind: str, document: str):
        client = clients[model_size]
        request_kwargs = client.build_request_kwargs([document])
        cached_vector = _cached_litellm_embedding_vector(request_kwargs)
        field_name = _qwen_generated_embedding_field(document_kind, model_size)
        if cached_vector is not None:
            return row_index, track_id, field_name, cached_vector, True

        vector = client.embed_one(document)
        if request_delay_s > 0:
            time.sleep(float(request_delay_s))
        return row_index, track_id, field_name, vector, False

    def _handle_result(result) -> None:
        row_index, track_id, field_name, vector, cache_hit = result
        generated_rows[row_index][field_name] = vector
        if cache_hit:
            stats["cache_hits"] += 1
        else:
            stats["endpoint_requests"] += 1
        completed = stats["cache_hits"] + stats["endpoint_requests"]
        if completed == 1 or completed % 2048 == 0 or completed == total_expected:
            print(
                "vLLM Qwen catalog embeddings: "
                f"{completed}/{total_expected} requests "
                f"({track_id}); endpoint_requests={stats['endpoint_requests']} "
                f"cache_hits={stats['cache_hits']}"
            )

    task_iter = _tasks()
    if max_workers == 1:
        for task in task_iter:
            _handle_result(_embed_task(*task))
        return generated_rows, stats

    worker_count = min(max_workers, total_expected) or 1
    if use_processes:
        # Each worker process rebuilds its own clients + litellm cache via the
        # initializer; submit the bare 5-tuple task to the module-level worker.
        if executor_factory is None:
            def executor_factory():
                return ProcessPoolExecutor(
                    max_workers=worker_count,
                    initializer=_init_qwen_embed_worker,
                    initargs=(
                        cache_backend,
                        cache_dir,
                        dict(api_base_by_model_size),
                        api_key,
                        int(timeout_s),
                        float(request_delay_s),
                    ),
                )

        def submit_one(pool, task):
            return pool.submit(_qwen_embed_worker, task)
    else:
        if executor_factory is None:
            def executor_factory():
                return ThreadPoolExecutor(max_workers=worker_count)

        def submit_one(pool, task):
            return pool.submit(_embed_task, *task)

    # Count lazily without materializing all futures. Submit only a bounded
    # window so a full-catalog rebuild does not hold 188k Future objects.
    pending = set()
    with executor_factory() as pool:
        while len(pending) < worker_count:
            try:
                task = next(task_iter)
            except StopIteration:
                break
            pending.add(submit_one(pool, task))

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                _handle_result(future.result())
            while len(pending) < worker_count:
                try:
                    task = next(task_iter)
                except StopIteration:
                    break
                pending.add(submit_one(pool, task))

    return generated_rows, stats


@app.function(
    image=image,
    volumes=_VOLUME_MOUNTS,
    secrets=[ENV_SECRET],
    cpu=8.0,
    memory=131072,
    timeout=24 * 3600,
)
def _build_lancedb_with_vllm_qwen_embeddings(
    model_sizes: list[str] | None = None,
    document_kinds: list[str] | None = None,
    request_delay_s: float = 0.0,
    max_in_flight: int = 16,
):
    import os
    import shutil

    from mcrs.lancedb.indexing import (
        GENERATED_QWEN_EMBEDDING_FIELDS,
        build_track_lancedb_table,
    )
    from mcrs.litellm_cache import setup_litellm_cache
    from mcrs.milvus.indexing import TRACK_METADATA_DATASET, TRACK_SPLIT, load_track_metadata_rows

    selected_model_sizes = tuple(model_sizes or QWEN_GENERATED_MODEL_SIZES)
    selected_document_kinds = tuple(document_kinds or QWEN_GENERATED_DOCUMENT_KINDS)
    generated_fields = tuple(
        _qwen_generated_embedding_field(document_kind, model_size)
        for model_size in selected_model_sizes
        for document_kind in selected_document_kinds
    )
    missing_expected_fields = set(generated_fields) - set(GENERATED_QWEN_EMBEDDING_FIELDS)
    if missing_expected_fields:
        raise ValueError(f"Generated field(s) are not registered in LanceDB indexing: {sorted(missing_expected_fields)}")

    api_key = os.environ.get("VLLM_API_KEY")
    if not api_key:
        raise RuntimeError("VLLM_API_KEY is required to call the self-hosted vLLM embedding endpoints")

    setup_litellm_cache(
        backend=LITELLM_CACHE_BACKEND,
        cache_dir=LITELLM_CACHE_DIR,
        supported_call_types=["embedding", "aembedding"],
    )

    api_base_by_model_size = {
        model_size: _vllm_endpoint_url(f"qwen3-embedding-{model_size}")
        for model_size in selected_model_sizes
    }
    metadata_rows = [
        dict(row)
        for row in load_track_metadata_rows(TRACK_METADATA_DATASET, TRACK_SPLIT)
    ]
    generated_rows, stats = _build_generated_qwen_embedding_rows(
        metadata_rows,
        model_sizes=selected_model_sizes,
        document_kinds=selected_document_kinds,
        api_base_by_model_size=api_base_by_model_size,
        api_key=api_key,
        request_delay_s=request_delay_s,
        max_in_flight=max_in_flight,
        cache_backend=LITELLM_CACHE_BACKEND,
        cache_dir=LITELLM_CACHE_DIR,
    )
    cache_vol.commit()

    # LanceDB commits via atomic rename; Modal Volume mounts can reject that
    # rename. Build on container-local disk first, then copy the finished DB
    # directory into the models volume.
    local_build_uri = "/tmp/mcrs-lancedb-vllm-qwen-build"
    summary = build_track_lancedb_table(
        db_uri=local_build_uri,
        table_name="music_track_catalog",
        include_embeddings=True,
        drop_existing=True,
        extra_embedding_rows=generated_rows,
        extra_embedding_fields=generated_fields,
    )

    remote_path = Path(DEFAULT_REMOTE_LANCEDB_URI)
    if remote_path.exists():
        shutil.rmtree(remote_path)
    remote_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(local_build_uri, remote_path)
    models_vol.commit()
    hf_cache_vol.commit()
    return {
        "summary": dict(
            db_uri=DEFAULT_REMOTE_LANCEDB_URI,
            table_name=summary.table_name,
            inserted_rows=summary.inserted_rows,
            metadata_row_count=summary.metadata_row_count,
            metadata_only_row_count=summary.metadata_only_row_count,
            include_embeddings=summary.include_embeddings,
        ),
        "stats": stats,
        "generated_fields": list(generated_fields),
    }


@app.local_entrypoint()
def run_inference(
    tid: str = "state_ranker_v10_lgbm_devset",
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
def run_inference_sharded(
    tid: str = "state_ranker_v10_lgbm_devset",
    eval_dataset: str = "devset",
    num_shards: int = 4,
    num_workers: int = 0,
    run_id: str = "",
    batch_size: int = DEVSET_BATCH_SIZE,
    clear_cache: bool = False,
    session_ids_json: str | None = None,
):
    """Run split-oriented, session-sharded inference across grouped workers.

    Generic over split: `eval_dataset == "devset"` runs the devset worker,
    anything else runs the blindset worker. GPU vs CPU is chosen internally
    from the tid's config (`_tid_uses_cpu`) — callers never pick a resource flavor.
    `num_shards` controls the logical output/checkpoint partition count, while
    `num_workers` controls how many Modal containers load the CRS and process
    groups of those shards. Each logical shard still writes run-scoped artifacts:
        inference/{split}/{tid}.run_{run_id}.shard_{i}.json
        inference/{split}/{tid}.run_{run_id}.shard_{i}_trace.jsonl   (devset only)
    Merge them with scripts/merge_shard_results.py --run_id {run_id}.

    A non-empty `run_id` is required (the run_experiment.py wrapper always
    passes one) so stale shard files from prior runs can never be merged in.
    """
    if not run_id:
        raise ValueError(
            "run_inference_sharded requires a non-empty --run-id "
            "(run_experiment.py generates one automatically)."
        )
    if num_shards < 1:
        raise ValueError("num_shards must be >= 1.")
    if num_workers <= 0:
        num_workers = num_shards
    if not (1 <= num_workers <= num_shards):
        raise ValueError("num_workers must be between 1 and num_shards.")

    is_devset = eval_dataset == "devset"
    if session_ids_json and not is_devset:
        raise ValueError("--session-ids-json is only supported for devset sharded runs.")
    uses_cpu = _tid_uses_cpu(tid)
    if is_devset:
        inference_fn = _inference_devset_cpu_grouped if uses_cpu else _inference_devset_grouped
    else:
        inference_fn = _inference_blindset_cpu_grouped if uses_cpu else _inference_blindset_grouped

    def _spawn_worker(worker_id: int, shard_ids: list[int]):
        shard_ids_json = json.dumps(shard_ids)
        if is_devset:
            return inference_fn.spawn(
                tid=tid,
                batch_size=batch_size,
                clear_cache=clear_cache,
                num_shards=num_shards,
                shard_ids_json=shard_ids_json,
                run_id=run_id,
                session_ids_json=session_ids_json,
            )
        return inference_fn.spawn(
            tid=tid,
            batch_size=batch_size,
            eval_dataset=eval_dataset,
            num_shards=num_shards,
            shard_ids_json=shard_ids_json,
            run_id=run_id,
        )

    # Resilient join: a single shard failure must NOT raise out of this local
    # entrypoint mid-run, or Modal SIGINTs every other in-progress shard
    # container (a cascade that loses the whole run over one transient error).
    # Catch per shard, retry the failures once, then fail loudly if any remain.
    def _join(pairs):
        ok, bad = [], []
        for worker_id, shard_ids, call in pairs:
            try:
                call.get()
                ok.extend(shard_ids)
                print(f"Worker {worker_id} complete (shards {shard_ids}).")
            except Exception as e:  # noqa: BLE001 — report and continue, never abort the run
                bad.append((worker_id, shard_ids))
                print(f"Worker {worker_id} FAILED for shards {shard_ids}: {type(e).__name__}: {e}")
        return ok, bad

    assignments = [
        (worker_id, _shards_for_worker(worker_id, num_workers, num_shards))
        for worker_id in range(num_workers)
    ]
    calls = [
        (worker_id, shard_ids, _spawn_worker(worker_id, shard_ids))
        for worker_id, shard_ids in assignments
    ]
    print(
        f"Spawned {num_workers} worker(s) for {num_shards} shard(s) "
        f"for {tid} (split={eval_dataset}, run_id={run_id}). "
        f"Assignments: {assignments}"
    )
    ok, failed = _join(calls)

    if failed:
        print(f"Retrying {len(failed)} failed worker group(s): {failed}")
        ok2, failed = _join([
            (worker_id, shard_ids, _spawn_worker(worker_id, shard_ids))
            for worker_id, shard_ids in failed
        ])
        ok += ok2

    if failed:
        failed_shards = [
            shard_id
            for _, shard_ids in failed
            for shard_id in shard_ids
        ]
        # All spawns joined — no healthy shard is still in flight, so raising
        # here does not trigger the SIGINT cascade. Fail loudly: an incomplete
        # run must not exit 0, or a later merge silently picks up a partial set.
        raise RuntimeError(
            f"{len(failed_shards)}/{num_shards} shard(s) failed after retry: {failed_shards}. "
            f"Sharded run is INCOMPLETE — re-run with the same --num-shards and "
            f"--run-id {run_id} before merging."
        )
    print(
        f"All {num_shards} shards complete. Per-shard outputs: "
        f"inference/{eval_dataset}/{tid}.run_{run_id}.shard_{{0..{num_shards-1}}}.json"
    )


@app.local_entrypoint()
def run_inference_blindset(
    tid: str = "state_ranker_v10_lgbm_blindset_A",
    batch_size: int = BLINDSET_BATCH_SIZE,
    eval_dataset: str = "blindset_A",
):
    """Run blindset inference on the configured fast GPU fallback policy."""
    inference_fn = _inference_blindset_cpu if _tid_uses_cpu(tid) else _inference_blindset
    inference_fn.remote(tid=tid, batch_size=batch_size, eval_dataset=eval_dataset)


@app.local_entrypoint()
def run_evaluate(
    tid: str = "state_ranker_v10_lgbm_devset",
    split: str = "devset",
):
    """Score predictions using the evaluator submodule (CPU)."""
    _evaluate.remote(tid=tid, split=split)


@app.function(
    image=image,
    secrets=[ENV_SECRET],
    volumes=_VOLUME_MOUNTS,
    cpu=LANCEDB_QUERY_CPU,
    memory=LANCEDB_QUERY_MEMORY,
    timeout=14400,
)
def _state_v1_retriever_matrix(
    variants_json: str,
    limit: int,
    output_prefix: str,
    sample_id_file: str,
    baseline_pools_json: str,
) -> dict:
    import json
    import subprocess
    import sys
    from pathlib import Path

    variants = json.loads(variants_json)
    analysis_dir = (
        Path("/app")
        / "experiments"
        / "analysis"
        / "devset_recall_gap_v0plus_all_retrievers_2026_06_06"
    )
    output_dir = Path(EXP_DIR) / "analysis" / "state_v1_retriever_matrix"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_json = output_dir / f"{output_prefix}.json"
    output_md = output_dir / f"{output_prefix}.md"
    output_csv = output_dir / f"{output_prefix}.csv"
    cmd = [
        sys.executable,
        "scripts/state_v1_retriever_matrix.py",
        "--analysis-dir",
        str(analysis_dir),
        "--lancedb-uri",
        DEFAULT_REMOTE_LANCEDB_URI,
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
        "--output-csv",
        str(output_csv),
    ]
    for variant in variants:
        cmd.extend(["--variant", str(variant)])
    if sample_id_file:
        sample_id_path = Path(sample_id_file)
        if not sample_id_path.is_absolute():
            sample_id_path = Path("/app") / sample_id_path
        cmd.extend(["--sample-id-file", str(sample_id_path)])
    if baseline_pools_json:
        baseline_pools_path = Path(baseline_pools_json)
        if not baseline_pools_path.is_absolute():
            baseline_pools_path = Path("/app") / baseline_pools_path
        cmd.extend(["--baseline-pools-json", str(baseline_pools_path)])
    if limit > 0:
        cmd.extend(["--limit", str(limit)])
    print("Running state_v1_retriever_matrix:", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd="/app", check=True)
    results_vol.commit()
    return {
        "summary": json.loads(output_json.read_text())["summary"],
        "json": str(output_json),
        "md": str(output_md),
        "csv": str(output_csv),
    }


@app.local_entrypoint()
def run_state_v1_retriever_matrix(
    variants_json: str = '["all_candidate_recall"]',
    limit: int = 0,
    output_prefix: str = "state_v1_retriever_matrix_modal",
    sample_id_file: str = "",
    baseline_pools_json: str = "",
):
    """Run the V1 retriever matrix inside Modal against remote LanceDB."""
    result = _state_v1_retriever_matrix.remote(
        variants_json=variants_json,
        limit=limit,
        output_prefix=output_prefix,
        sample_id_file=sample_id_file,
        baseline_pools_json=baseline_pools_json,
    )
    print(json.dumps(result, indent=2))


@app.local_entrypoint()
def upload_lancedb_index(
    local_db_dir: str = "cache/lancedb",
    remote_dir: str = "lancedb",
    overwrite: bool = False,
):
    """Upload a locally built LanceDB directory into the Modal models volume."""
    from mcrs.lancedb.modal_upload import upload_lancedb_directory_to_volume

    upload_lancedb_directory_to_volume(
        models_vol,
        local_db_dir,
        remote_dir=remote_dir,
        overwrite=overwrite,
        volume_name=MODELS_VOLUME,
    )


@app.local_entrypoint()
def build_lancedb_with_vllm_qwen_embeddings(
    model_sizes: str = "4b,8b",
    document_kinds: str = "metadata,attributes",
    request_delay_s: float = 0.0,
    max_in_flight: int = 16,
):
    """Rebuild Modal LanceDB with per-item cached vLLM Qwen 4B/8B item vectors.

    Each catalog item/document/model is sent as a separate LiteLLM embedding
    request so the file cache key is per item. Re-running the rebuild with the
    same text/model/api_base/api_key request shape should hit cache and skip the
    endpoint for already-cached items.
    """
    selected_model_sizes = [item.strip().lower() for item in model_sizes.split(",") if item.strip()]
    selected_document_kinds = [item.strip().lower() for item in document_kinds.split(",") if item.strip()]
    result = _build_lancedb_with_vllm_qwen_embeddings.remote(
        model_sizes=selected_model_sizes,
        document_kinds=selected_document_kinds,
        request_delay_s=request_delay_s,
        max_in_flight=max_in_flight,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


@app.local_entrypoint()
def smoke_lancedb_query(
    query: str = "dark atmospheric synthwave",
    topk: int = 20,
):
    """Smoke-test the private Modal LanceDB query function."""
    track_ids = query_lancedb.remote(query=query, topk=topk)
    print(track_ids)


# ---------------------------------------------------------------------------
# Text-side encoder catalog convention verification (SigLIP-2 / CLAP music)
# ---------------------------------------------------------------------------
#
# Sanity-checks before wiring SigLIP-text + CLAP-text branches into the v0+
# compiler: for N sampled catalog tracks, encode a short text description
# (artist + tags) and compare cosine similarity to the catalog's image /
# audio embedding for the same track. Compare against random-pair baseline.
#
# This is NOT a quality benchmark — it verifies the text-side encoder lives
# in the same shared space as the catalog vectors (catches normalization /
# pooling / model-variant mismatch cheaply before any retrieval run).

# SigLIP needs only the base image (transformers already there).
# CLAP needs laion_clap, which pins numpy==1.23.5 (unbuildable on py3.12).
# Install with --no-deps and rely on the base image's numpy / torch / transformers.
# laion_clap's other small deps (progressbar2, wget, h5py, librosa, soundfile)
# get added explicitly; we only call get_text_embedding so audio-I/O isn't on
# the hot path but the package imports it at module load.
# Clean Python 3.10 image — laion_clap's numpy==1.23.5 pin builds natively here
# (vs Py3.12 where distutils is gone). Self-contained, doesn't inherit the
# project's uv_sync env to avoid torch/torchaudio ABI conflicts.
_clap_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "libsndfile1", "ffmpeg")
    .pip_install(
        # Match laion_clap repo's tested set: torch>=2.4, torchaudio>=2.4,
        # torchvision>=0.19, transformers>=4.51.3. Older torch combos fail
        # because modern transformers disables its PyTorch backend below 2.4.
        "laion_clap==1.1.7",
        "torch>=2.4,<2.5",
        "torchaudio>=2.4,<2.5",
        "torchvision>=0.19,<0.20",
        # transformers 5.x removed top-level `from transformers import BertModel`,
        # which laion_clap's clap_module/model.py still does. Pin below 5.
        "transformers>=4.51.3,<5.0",
        "datasets>=2.18",
        "pyarrow",
        "huggingface_hub[hf_xet]",
        "numpy<2",
        # Needed because modal/app.py imports OmegaConf at module load.
        "omegaconf>=2.3",
    )
    .add_local_dir(
        ".",
        "/app",
        copy=True,
        ignore=[".*", "__pycache__", "*.pyc", ".venv", "exp", "cache", "submission*",
                "models/biencoder*"],  # 15GB b1 encoder lives on a volume / cache-served, never bundle it
    )
    .env({"PYTHONPATH": "/app"})
)


def _verify_textside_inner(
    modality: str,
    n: int,
    seed: int,
    normalize: bool,
    clap_ckpt_repo: str,
    clap_ckpt_filename: str,
) -> dict:
    """Cosine alignment check: text_for_track vs catalog_for_track."""
    import os
    import random

    import numpy as np
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download, snapshot_download

    os.environ.setdefault("HF_HOME", HF_CACHE_DIR)

    # 1. Locate catalog files on the HF cache volume — populate via
    #    snapshot_download (idempotent; no-op if already cached from
    #    prior inference runs).
    meta_dir = snapshot_download(
        repo_id="talkpl-ai/TalkPlayData-Challenge-Track-Metadata",
        repo_type="dataset",
        allow_patterns=["data/all_tracks-*.parquet"],
    )
    emb_dir = snapshot_download(
        repo_id="talkpl-ai/TalkPlayData-Challenge-Track-Embeddings",
        repo_type="dataset",
        allow_patterns=["data/all_tracks-*.parquet"],
    )
    meta_parquet = next(iter(Path(meta_dir).glob("data/all_tracks-*.parquet")))
    emb_parquet = next(iter(Path(emb_dir).glob("data/all_tracks-*.parquet")))

    meta = pq.read_table(
        str(meta_parquet),
        columns=["track_id", "track_name", "artist_name", "tag_list"],
    ).to_pylist()

    emb_col = "image-siglip2" if modality == "siglip2" else "audio-laion_clap"
    emb_tbl = pq.read_table(str(emb_parquet), columns=["track_id", emb_col])
    emb_by_id = dict(zip(emb_tbl["track_id"].to_pylist(), emb_tbl[emb_col].to_pylist()))

    rng = random.Random(seed)
    rng.shuffle(meta)

    texts: list[str] = []
    item_vecs: list[list[float]] = []
    for row in meta:
        if len(item_vecs) >= n:
            break
        v = emb_by_id.get(row["track_id"])
        if not v:
            continue
        item_vecs.append(v)
        artist = row.get("artist_name") or []
        tags = row.get("tag_list") or []
        parts = []
        if artist:
            parts.append(", ".join(artist))
        if tags:
            parts.append(", ".join(tags[:6]))
        texts.append(" - ".join(parts) if parts else "")

    print(f"[{modality}] sampled {len(item_vecs)} tracks, normalize={normalize}")

    # 2. Load the text-side encoder and encode.
    # Debug: confirm new modules made it into the image.
    import sys
    print(f"sys.path: {sys.path}")
    try:
        from pathlib import Path as _P
        emb_dir_listing = sorted(p.name for p in _P("/app/mcrs/embeddings").iterdir()) if _P("/app/mcrs/embeddings").exists() else "(/app/mcrs/embeddings missing)"
        print(f"/app/mcrs/embeddings contents: {emb_dir_listing}")
    except Exception as e:
        print(f"debug listing failed: {e}")
    if modality == "siglip2":
        from mcrs.embeddings.siglip2_text_embedding import SigLIP2TextEmbeddingClient

        client = SigLIP2TextEmbeddingClient(
            device="cuda",
            l2_normalize=normalize,
        )
    elif modality == "clap":
        # Download music checkpoint to the HF cache volume on first run.
        ckpt_path = hf_hub_download(
            repo_id=clap_ckpt_repo,
            filename=clap_ckpt_filename,
            cache_dir=HF_CACHE_DIR,
        )
        print(f"[clap] checkpoint at {ckpt_path}")
        from mcrs.embeddings.clap_text_embedding import ClapTextEmbeddingClient

        # CPU for verification (200 samples is fast; sidesteps torch/torchaudio
        # CUDA ABI issues in the clean Py3.10 image).
        client = ClapTextEmbeddingClient(
            ckpt_path=ckpt_path,
            device="cpu",
            l2_normalize=normalize,
        )
    else:
        raise ValueError(f"unknown modality: {modality}")

    text_vecs = np.asarray(client.embed_batch(texts), dtype=np.float32)
    item_arr = np.asarray(item_vecs, dtype=np.float32)

    if text_vecs.shape != item_arr.shape:
        raise RuntimeError(
            f"dim mismatch: text={text_vecs.shape} catalog={item_arr.shape}"
        )

    # 3. Cosines: same-track and random pairing.
    def _cosine_pairs(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        a_n = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-12)
        b_n = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-12)
        return np.einsum("ij,ij->i", a_n, b_n)

    cos_same = _cosine_pairs(text_vecs, item_arr)
    perm = list(range(len(text_vecs)))
    rng.shuffle(perm)
    cos_random = _cosine_pairs(text_vecs[perm], item_arr)

    stats = {
        "modality": modality,
        "n": len(item_vecs),
        "normalize": normalize,
        "text_dim": int(text_vecs.shape[1]),
        "catalog_dim": int(item_arr.shape[1]),
        "cos_same_mean": float(cos_same.mean()),
        "cos_same_std": float(cos_same.std()),
        "cos_same_p05": float(np.percentile(cos_same, 5)),
        "cos_same_p95": float(np.percentile(cos_same, 95)),
        "cos_random_mean": float(cos_random.mean()),
        "lift_over_random": float(cos_same.mean() - cos_random.mean()),
        "warning": [],
    }
    if stats["cos_same_mean"] < 0.05:
        stats["warning"].append("mean cosine very low — likely convention mismatch")
    if stats["lift_over_random"] < 0.02:
        stats["warning"].append("no detectable lift over random — encoders may be misaligned")

    print(f"[{modality}] result: {json.dumps(stats, indent=2)}")
    return stats


# SigLIP variant uses the base project image (transformers already installed).
@app.function(
    image=image,
    gpu="T4",
    volumes={HF_CACHE_DIR: hf_cache_vol},
    secrets=[ENV_SECRET],
    cpu=2.0,
    memory=8192,
    timeout=1200,
)
def verify_siglip_textside(
    n: int = 200, seed: int = 42, normalize: bool = False
) -> dict:
    return _verify_textside_inner(
        modality="siglip2",
        n=n,
        seed=seed,
        normalize=normalize,
        clap_ckpt_repo="",
        clap_ckpt_filename="",
    )


# CLAP variant needs laion_clap installed. Verification runs on CPU
# (200 samples is fast; avoids torch/torchaudio CUDA dependency in this image).
@app.function(
    image=_clap_image,
    volumes={HF_CACHE_DIR: hf_cache_vol},
    secrets=[ENV_SECRET],
    cpu=4.0,
    memory=16384,
    timeout=1800,
)
def verify_clap_textside(
    n: int = 200,
    seed: int = 42,
    normalize: bool = False,
    clap_ckpt_repo: str = "lukewys/laion_clap",
    clap_ckpt_filename: str = "music_audioset_epoch_15_esc_90.14.pt",
) -> dict:
    return _verify_textside_inner(
        modality="clap",
        n=n,
        seed=seed,
        normalize=normalize,
        clap_ckpt_repo=clap_ckpt_repo,
        clap_ckpt_filename=clap_ckpt_filename,
    )


@app.local_entrypoint()
def verify_textside(
    modality: str = "siglip2",
    n: int = 200,
    normalize: bool = False,
):
    """Run the text-side encoder catalog convention check on Modal.

    Examples:
        modal run modal/app.py::verify_textside --modality siglip2
        modal run modal/app.py::verify_textside --modality clap
        modal run modal/app.py::verify_textside --modality siglip2 --normalize
    """
    if modality == "siglip2":
        result = verify_siglip_textside.remote(n=n, normalize=normalize)
    elif modality == "clap":
        result = verify_clap_textside.remote(n=n, normalize=normalize)
    else:
        raise SystemExit(f"unknown modality: {modality}")
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Production text-side encoder service: combined SigLIP-2 + CLAP music
# ---------------------------------------------------------------------------
#
# Hosts both text encoders in one warm container so the v0+ compiler pays
# one cold start (~45 s for SigLIP weight load + CLAP ckpt load) instead of
# two, and one network hop per turn dispatches to the model that the branch
# needs. Compiler clients live in `mcrs.embeddings.modal_multimodal_client`.
#
# Container resources: T4 (16 GB VRAM) easily fits both models (~1 GB total).
# scaledown_window matches Qwen3Encoder so the smoke test pays no extra cold
# starts mid-run.


@app.cls(
    image=_clap_image,  # cached; includes torch 2.4 + transformers <5 + laion_clap 1.1.7
    gpu="T4",
    volumes={HF_CACHE_DIR: hf_cache_vol, CACHE_DIR: cache_vol},
    secrets=[ENV_SECRET],
    cpu=2.0,
    memory=8192,
    timeout=600,
    min_containers=0,
    # Part of the 10-GPU project budget (Qwen3Encoder 4 + vllm-8b 4 + this 2 = 10);
    # clap_text / SigLIP branches route here. min=0 keeps scale-to-zero.
    max_containers=2,
    scaledown_window=600,
)
class MultimodalTextEncoder:
    """Text-side service for SigLIP-2 (image space) + CLAP music (audio space).

    Per-call latency on T4 once warm: ~50 ms SigLIP, ~80 ms CLAP. Cold start:
    SigLIP weights from HF cache + CLAP ckpt from HF cache → ~45 s total.
    """

    @modal.enter()
    def setup(self) -> None:
        self._cache_enabled = False  # set True after cache init; keeps @modal.exit() safe if setup raises
        import os

        os.environ.setdefault("HF_HOME", HF_CACHE_DIR)
        from huggingface_hub import hf_hub_download

        from mcrs.embeddings.clap_text_embedding import ClapTextEmbeddingClient
        from mcrs.embeddings.siglip2_text_embedding import (
            SigLIP2TextEmbeddingClient,
        )

        self.siglip = SigLIP2TextEmbeddingClient(device="cuda")
        self.siglip._ensure_loaded()

        ckpt_path = hf_hub_download(
            repo_id="lukewys/laion_clap",
            filename="music_audioset_epoch_15_esc_90.14.pt",
            cache_dir=HF_CACHE_DIR,
        )
        self.clap = ClapTextEmbeddingClient(ckpt_path=ckpt_path, device="cuda")
        self.clap._ensure_loaded()

        from mcrs.embeddings.embedding_cache import (
            CachedTextEmbedder,
            DiskVectorCache,
        )

        from mcrs.embeddings.modal_multimodal_client import (
            cache_namespace_for_method,
        )

        store = DiskVectorCache(EMBEDDING_CACHE_DIR)
        cache_enabled = os.environ.get("EMBEDDING_CACHE_ENABLED", "1") != "0"
        self._cache_enabled = cache_enabled
        # Namespaces are shared with the client-side cache so both back the same
        # files on the cache volume (see mcrs/embeddings/modal_multimodal_client).
        self.siglip = CachedTextEmbedder(
            self.siglip,
            store,
            cache_namespace_for_method("embed_siglip_text"),
            enabled=cache_enabled,
        )
        self.clap = CachedTextEmbedder(
            self.clap,
            store,
            cache_namespace_for_method("embed_clap_text"),
            enabled=cache_enabled,
        )

    @modal.method()
    def embed_siglip_text(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self.siglip.embed_batch(texts)

    @modal.method()
    def embed_clap_text(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self.clap.embed_batch(texts)

    @modal.exit()
    def _commit_embedding_cache(self):
        if self._cache_enabled:
            cache_vol.commit()
