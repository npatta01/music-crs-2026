"""vLLM OpenAI-compatible embedding services on Modal (app: music-crs-vllm).

Scale-to-zero web endpoints serving Qwen3-Embedding models. Reached only through
LiteLLM (api_base), so the existing LiteLLM file cache applies unchanged and a
cache hit never wakes the GPU.

Deploy:   modal deploy modal/vllm_serve.py
Pre-warm: modal run modal/vllm_serve.py::download --model qwen3-embedding-4b
Smoke:    modal run modal/vllm_serve.py::smoke --model qwen3-embedding-4b
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
