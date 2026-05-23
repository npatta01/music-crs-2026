"""
Modal cloud pipeline for Music CRS.

Config: modal/config.yaml (volume names, container paths)

Volumes are created automatically on first run — no manual setup needed.

Secret (.env in project root):
    HF_TOKEN=hf_...

Usage:
    # Smoke test (5 sessions, with matching local evaluation subset)
    python run_experiment.py --backend modal --tid bm25_devset_retrieval_only_with_tag_list --num_sessions 5

    # Full devset
    python run_experiment.py --backend modal --tid lancedb_fts_with_tag_list_devset --batch_size 64

    # Blindset, after adding a split-specific config under configs/
    python run_experiment.py --backend modal --tid my_blindset_A_config --eval_dataset blindset_A
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
LITELLM_CACHE_VOLUME = _cfg.volumes.litellm_cache
HF_CACHE_DIR = _cfg.container.hf_cache_dir
EXP_DIR = _cfg.container.exp_dir
MODELS_DIR = _cfg.container.models_dir
LITELLM_CACHE_DIR = _cfg.container.litellm_cache_dir
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

app = modal.App(APP_NAME)

hf_cache_vol = modal.Volume.from_name(HF_CACHE_VOLUME, create_if_missing=True)
results_vol = modal.Volume.from_name(RESULTS_VOLUME, create_if_missing=True)
models_vol = modal.Volume.from_name(MODELS_VOLUME, create_if_missing=True)
litellm_cache_vol = modal.Volume.from_name(LITELLM_CACHE_VOLUME, create_if_missing=True)

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
RETRIEVAL_SERVICE_CACHE_SIZE = 8


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
) -> str | None:
    if model_name.startswith("openrouter/"):
        return openrouter_api_key
    if api_base and "openrouter.ai" in api_base:
        return openrouter_api_key
    if model_name.startswith("huggingface/"):
        return hf_token
    return None


def _tid_config(tid: str):
    return OmegaConf.load(Path.cwd() / "configs" / f"{tid}.yaml")


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
    volumes={LITELLM_CACHE_DIR: litellm_cache_vol},
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
        from litellm.caching.caching import Cache

        litellm.success_callback = [self._track_cache_hit]
        litellm.cache = Cache(
            type="disk",
            supported_call_types=["completion", "acompletion", "embedding", "aembedding"],
            namespace="music-crs",
            disk_cache_dir=LITELLM_CACHE_DIR,
        )
        self.last_cache_hit = None
        self.hf_token = os.environ.get("HF_TOKEN")
        self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
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
            cache={"ttl": 86400},
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
        cache_control = {"ttl": 86400}
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


@app.local_entrypoint()
def run_inference(
    tid: str = "bm25_devset_retrieval_only_with_tag_list",
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
    tid: str = "bm25_devset_retrieval_only_with_tag_list",
    batch_size: int = BLINDSET_BATCH_SIZE,
    eval_dataset: str = "blindset_A",
):
    """Run blindset inference on the configured fast GPU fallback policy."""
    inference_fn = _inference_blindset_cpu if _tid_uses_cpu(tid) else _inference_blindset
    inference_fn.remote(tid=tid, batch_size=batch_size, eval_dataset=eval_dataset)


@app.local_entrypoint()
def run_evaluate(
    tid: str = "bm25_devset_retrieval_only_with_tag_list",
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
