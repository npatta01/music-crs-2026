"""vLLM OpenAI-compatible embedding services on Modal (app: music-crs-vllm).

Scale-to-zero web endpoints serving Qwen3-Embedding models. Reached only through
LiteLLM (api_base), so the existing LiteLLM file cache applies unchanged and a
cache hit never wakes the GPU.

Deploy:   modal deploy modal/vllm_serve.py
Pre-warm: modal run modal/vllm_serve.py::download --model qwen3-embedding-4b
Smoke:    modal run modal/vllm_serve.py::smoke --model qwen3-embedding-4b
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import modal
import yaml

VLLM_PORT = 8000
# Name of the env var (provided via the dotenv secret) holding the vLLM server key.
VLLM_API_KEY_ENV = "VLLM_API_KEY"


def _config_path() -> Path:
    """Find modal/config.yaml locally and when Modal imports this file in-container."""
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


def load_vllm_registry(config_path: Path | None = None) -> dict[str, Any]:
    """Load the `vllm:` block from modal/config.yaml as a plain dict."""
    path = config_path or _config_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    vllm = data.get("vllm")
    if not vllm or "models" not in vllm:
        raise ValueError("modal/config.yaml is missing a `vllm.models` block")
    return vllm


def _serve_fn_name(model_key: str) -> str:
    """Logical model key -> deployed web_server function name."""
    return "serve_" + model_key.replace("-", "_")


def _build_vllm_serve_cmd(entry: dict[str, Any], *, port: int = VLLM_PORT) -> list[str]:
    """Build the `vllm serve ...` argv for one model entry.

    --api-key is passed by shell-expanded env reference so the literal key never
    appears in the argv we construct here (it is resolved at exec time).
    """
    cmd = [
        "vllm",
        "serve",
        str(entry["hf_id"]),
        "--task",
        str(entry.get("task", "embed")),
        "--served-model-name",
        str(entry["served_name"]),
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--api-key",
        # literal $VLLM_API_KEY — expanded by the shell at exec time (Task 2 runs with shell=True)
        f"${VLLM_API_KEY_ENV}",
    ]
    if entry.get("dtype"):
        cmd += ["--dtype", str(entry["dtype"])]
    if entry.get("max_model_len"):
        cmd += ["--max-model-len", str(entry["max_model_len"])]
    cmd += ["--tensor-parallel-size", "1"]
    return cmd


# ---------------------------------------------------------------------------
# Modal app objects — image, volumes, scale-to-zero web endpoints, download
# ---------------------------------------------------------------------------

# 0.11.2 (not 0.11.0): 0.11.0 pins only `transformers>=4.55.2`, so pip pulls
# transformers 5.x which removed `all_special_tokens_extended` and crashes vLLM's
# tokenizer at startup. 0.11.2 pins `transformers<5,>=4.56.0`, forcing a compatible 4.x.
VLLM_VERSION = "0.11.2"

# argv tokens are space-joined into a shell command (shell=True is needed so the
# literal $VLLM_API_KEY expands from the dotenv secret). Every other token must be
# free of shell metacharacters/whitespace, or the command would mis-tokenize.
_SAFE_VLLM_TOKEN = re.compile(r"^[\w./:@,=-]+$")

_registry = load_vllm_registry()
_HF_CACHE_DIR = "/root/.cache/huggingface"
_VLLM_CACHE_DIR = str(_registry.get("cache_dir", "/root/.cache/vllm"))

app = modal.App(_registry["app_name"])

ENV_SECRET = modal.Secret.from_dotenv(__file__)  # mirror modal/app.py

_vllm_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(f"vllm=={VLLM_VERSION}", "huggingface_hub[hf_transfer]", "pyyaml")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "VLLM_USE_V1": "1"})
    .add_local_file("modal/config.yaml", "/app/modal/config.yaml")
)

hf_cache_vol = modal.Volume.from_name("music-crs-hf-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name(_registry["cache_volume"], create_if_missing=True)

_VOLUMES = {_HF_CACHE_DIR: hf_cache_vol, _VLLM_CACHE_DIR: vllm_cache_vol}


def _run_vllm_serve(model_key: str) -> None:
    """Launch the vLLM OpenAI server for `model_key` (called inside the container)."""
    import os
    import subprocess

    entry = _registry["models"][model_key]
    cmd = _build_vllm_serve_cmd(entry, port=VLLM_PORT)
    for token in cmd:
        if token == f"${VLLM_API_KEY_ENV}":
            continue
        if not _SAFE_VLLM_TOKEN.match(token):
            raise ValueError(
                f"Unsafe token in vLLM serve command (breaks shell=True): {token!r}"
            )
    # shell=True so the literal $VLLM_API_KEY in the argv is expanded from the
    # dotenv secret at exec time.
    subprocess.Popen(" ".join(cmd), shell=True, env={**os.environ})


# ---------------------------------------------------------------------------
# Two explicit top-level endpoints. Modal requires the decorated function to be
# defined in *global* scope (a nested/closure function raises LocalFunctionError
# at deploy unless serialized=True), so these are written out per-model rather
# than produced by a factory. Per-model resource args come from the registry.
# Decorator order: @app.function outermost, @modal.web_server innermost.
# ---------------------------------------------------------------------------

_ENTRY_4B = _registry["models"]["qwen3-embedding-4b"]
_ENTRY_8B = _registry["models"]["qwen3-embedding-8b"]


@app.function(
    name=_serve_fn_name("qwen3-embedding-4b"),
    image=_vllm_image,
    gpu=str(_ENTRY_4B["gpu"]),
    volumes=_VOLUMES,
    secrets=[ENV_SECRET],
    timeout=int(_ENTRY_4B["timeout"]),
    scaledown_window=int(_ENTRY_4B["scaledown_window"]),
    min_containers=0,
    max_containers=int(_ENTRY_4B.get("max_containers", 1)),
)
@modal.concurrent(max_inputs=int(_ENTRY_4B["max_inputs"]))
@modal.web_server(port=VLLM_PORT, startup_timeout=10 * 60)
def serve_qwen3_embedding_4b():
    _run_vllm_serve("qwen3-embedding-4b")


@app.function(
    name=_serve_fn_name("qwen3-embedding-8b"),
    image=_vllm_image,
    gpu=str(_ENTRY_8B["gpu"]),
    volumes=_VOLUMES,
    secrets=[ENV_SECRET],
    timeout=int(_ENTRY_8B["timeout"]),
    scaledown_window=int(_ENTRY_8B["scaledown_window"]),
    min_containers=0,
    max_containers=int(_ENTRY_8B.get("max_containers", 1)),
)
@modal.concurrent(max_inputs=int(_ENTRY_8B["max_inputs"]))
@modal.web_server(port=VLLM_PORT, startup_timeout=10 * 60)
def serve_qwen3_embedding_8b():
    _run_vllm_serve("qwen3-embedding-8b")


def endpoint_url(model_key: str) -> str:
    """Resolve the live web URL for a deployed serve endpoint, with `/v1` suffix."""
    fn = modal.Function.from_name(_registry["app_name"], _serve_fn_name(model_key))
    base = fn.get_web_url().rstrip("/")
    return base + "/v1"


def _resolve_encoder_vllm_endpoint(enc_cfg: Any) -> None:
    if isinstance(enc_cfg, dict) and enc_cfg.get("vllm_endpoint"):
        enc_cfg["api_base"] = endpoint_url(enc_cfg.pop("vllm_endpoint"))


def resolve_vllm_endpoints_in_qu_kwargs(qu_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Resolve logical vLLM endpoint keys in top-level and named encoders.

    If an encoder declares `vllm_endpoint: <key>`, replace it with a live Modal
    OpenAI-compatible `api_base`. No-op when absent. Mutates and returns the dict
    in place.
    """
    _resolve_encoder_vllm_endpoint(qu_kwargs.get("encoder"))
    encoders = qu_kwargs.get("encoders")
    if isinstance(encoders, dict):
        for enc_cfg in encoders.values():
            _resolve_encoder_vllm_endpoint(enc_cfg)
    return qu_kwargs


@app.function(image=_vllm_image, timeout=120)
def resolve_check(model: str = "qwen3-embedding-4b") -> str:
    """In-container check that the deployed endpoint URL resolves from inside a
    Modal container (the same cross-app Function.from_name lookup the inference
    app performs). Run: modal run modal/vllm_serve.py::resolve_check"""
    url = endpoint_url(model)
    print(f"in-container endpoint_url({model}) = {url}")
    return url


@app.function(image=_vllm_image, volumes=_VOLUMES, timeout=3600)
def download(model: str = "qwen3-embedding-4b") -> str:
    """Optional pre-warm: download weights into the hf-cache volume and commit."""
    from huggingface_hub import snapshot_download

    entry = _registry["models"][model]
    path = snapshot_download(entry["hf_id"])
    hf_cache_vol.commit()
    return path


@app.local_entrypoint()
def smoke(model: str = "qwen3-embedding-4b", text: str = "a melancholic indie folk song"):
    """Cost-gated GPU smoke test: embed `text` twice via LiteLLM against the vLLM
    endpoint and assert the second call is a cache hit with matching vectors.

    Run only with explicit approval (wakes a GPU):
        modal deploy modal/vllm_serve.py
        modal run modal/vllm_serve.py::smoke --model qwen3-embedding-4b
    """
    import os

    import litellm

    from mcrs.litellm_cache import setup_litellm_cache

    # local_entrypoint runs on the client, so `secrets=[ENV_SECRET]` does NOT apply
    # here — load VLLM_API_KEY from the same .env the deployed server reads, unless
    # it's already exported. Without this the client would send "EMPTY" and the
    # deployed endpoint (started with --api-key $VLLM_API_KEY) returns 401.
    if VLLM_API_KEY_ENV not in os.environ:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            for raw in env_path.read_text(encoding="utf-8").splitlines():
                raw = raw.strip()
                if raw.startswith(f"{VLLM_API_KEY_ENV}="):
                    os.environ[VLLM_API_KEY_ENV] = raw.split("=", 1)[1]
                    break

    api_key = os.environ.get(VLLM_API_KEY_ENV)
    if not api_key:
        raise RuntimeError(
            f"{VLLM_API_KEY_ENV} not found in the environment or {Path(__file__).resolve().parent.parent / '.env'}; "
            "set it so the smoke client matches the deployed endpoint's --api-key."
        )

    cache_dir = os.environ.get("MCRS_LITELLM_CACHE_DIR", "/tmp/mcrs-vllm-smoke-cache")
    setup_litellm_cache(cache_dir=cache_dir)

    entry = _registry["models"][model]
    api_base = endpoint_url(model)
    kwargs = dict(
        model=f"openai/{entry['served_name']}",
        input=[text],
        api_base=api_base,
        api_key=api_key,
        encoding_format="float",
        timeout=600,
    )

    first = litellm.embedding(**kwargs)
    second = litellm.embedding(**kwargs)
    v1 = first.data[0]["embedding"]
    v2 = second.data[0]["embedding"]
    hit = bool(getattr(second, "_hidden_params", {}).get("cache_hit"))
    print(f"dim={len(v1)} cache_hit_second={hit} vectors_match={v1 == v2}")
    assert v1 == v2, "cached vector must match the fresh vector"
    assert hit, "second identical embedding call should be a cache hit"
