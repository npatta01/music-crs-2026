# vLLM Qwen3-Embedding on Modal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve `Qwen/Qwen3-Embedding-4B` and `-8B` on Modal via vLLM behind an OpenAI `/v1/embeddings` endpoint that scales to zero, reached through LiteLLM so the existing LiteLLM file cache applies unchanged.

**Architecture:** A separate Modal app (`modal/vllm_serve.py`, app name `music-crs-vllm`) runs `vllm serve <model> --task embed` inside a `@modal.web_server` (scale-to-zero). The v0+ encoder keeps `backend: litellm` and points `api_base` at the vLLM URL, resolved at inference start from a logical name. No new caching code — LiteLLM's `FileCache` already covers `embedding` call types, so a cache hit never wakes the GPU.

**Tech Stack:** Modal 1.4.2, vLLM (pinned), LiteLLM, OmegaConf, pytest.

**Spec:** [docs/superpowers/specs/2026-06-02-modal-vllm-qwen-embeddings-design.md](../specs/2026-06-02-modal-vllm-qwen-embeddings-design.md)

---

## File Structure

- `modal/config.yaml` — **modify**: add `vllm:` registry block + `vllm_cache` volume name.
- `modal/vllm_serve.py` — **create**: serving app. Holds pure helpers (`load_vllm_registry`, `_build_vllm_serve_cmd`, `_serve_fn_name`, `endpoint_url`, `resolve_vllm_endpoints_in_qu_kwargs`) and Modal objects (image, volumes, 2 web_server endpoints, `download`, `smoke`).
- `mcrs/qu_modules/compiler_v0plus_qu.py` — **modify**: litellm encoder factory forwards `extra_params` (carries the cold-start `timeout`).
- `run_inference_devset.py`, `run_inference_blindset.py` — **modify**: resolve `vllm_endpoint` → `api_base` right after building `qu_kwargs`.
- `configs/v0plus_compiler_image_qwen3emb4b_vllm_devset.yaml`, `configs/v0plus_compiler_image_qwen3emb8b_vllm_devset.yaml` — **create**: A/B experiment configs.
- `.env.example` — **modify**: document `VLLM_API_KEY`.
- `docs/modal_setup.md` — **modify**: deploy/use section.
- `tests/test_vllm_serve.py` — **create**: unit tests for the pure helpers + resolver.
- `tests/test_v0plus_compiler_qu.py` — **modify**: test for `extra_params` passthrough.

Pure helpers live at module top of `modal/vllm_serve.py` so they import without a Modal token and are unit-testable. Importing the module constructs (does not deploy) the Modal app, which is token-free and matches `tests/test_modal_app_resources.py`.

---

## Task 1: vLLM registry config + pure command/registry helpers

**Files:**
- Modify: `modal/config.yaml`
- Create: `modal/vllm_serve.py` (helpers only in this task)
- Test: `tests/test_vllm_serve.py`

- [ ] **Step 1: Add the registry + volume to `modal/config.yaml`**

Append at the end of `modal/config.yaml`:

```yaml
# vLLM OpenAI-compatible embedding services (separate Modal app "music-crs-vllm").
# Scale-to-zero; weights lazy-downloaded to the hf-cache volume on first boot.
vllm:
  app_name: "music-crs-vllm"
  # torch-compile / vLLM artifact cache volume (cold-start speedup).
  cache_volume: "music-crs-vllm-cache"
  cache_dir: "/root/.cache/vllm"
  models:
    qwen3-embedding-4b:
      hf_id: "Qwen/Qwen3-Embedding-4B"
      served_name: "Qwen/Qwen3-Embedding-4B"
      task: "embed"
      gpu: "L4"
      dtype: "bfloat16"
      max_model_len: 8192
      max_inputs: 32
      scaledown_window: 300
      timeout: 1800
    qwen3-embedding-8b:
      hf_id: "Qwen/Qwen3-Embedding-8B"
      served_name: "Qwen/Qwen3-Embedding-8B"
      task: "embed"
      gpu: "L40S"
      dtype: "bfloat16"
      max_model_len: 8192
      max_inputs: 32
      scaledown_window: 300
      timeout: 1800
```

- [ ] **Step 2: Write the failing test for the pure helpers**

Create `tests/test_vllm_serve.py`:

```python
import importlib

import pytest

vllm_serve = importlib.import_module("modal.vllm_serve")


def test_load_vllm_registry_has_both_models():
    reg = vllm_serve.load_vllm_registry()
    assert set(reg["models"]) == {"qwen3-embedding-4b", "qwen3-embedding-8b"}
    assert reg["models"]["qwen3-embedding-4b"]["hf_id"] == "Qwen/Qwen3-Embedding-4B"
    assert reg["app_name"] == "music-crs-vllm"


def test_build_vllm_serve_cmd_embed_flags():
    entry = {
        "hf_id": "Qwen/Qwen3-Embedding-4B",
        "served_name": "Qwen/Qwen3-Embedding-4B",
        "task": "embed",
        "dtype": "bfloat16",
        "max_model_len": 8192,
    }
    cmd = vllm_serve._build_vllm_serve_cmd(entry, port=8000)
    assert cmd[:2] == ["vllm", "serve"]
    assert "Qwen/Qwen3-Embedding-4B" in cmd
    assert "--task" in cmd and cmd[cmd.index("--task") + 1] == "embed"
    assert cmd[cmd.index("--served-model-name") + 1] == "Qwen/Qwen3-Embedding-4B"
    assert cmd[cmd.index("--port") + 1] == "8000"
    assert cmd[cmd.index("--host") + 1] == "0.0.0.0"
    assert cmd[cmd.index("--dtype") + 1] == "bfloat16"
    assert cmd[cmd.index("--max-model-len") + 1] == "8192"
    # api key injected from env var name, not a literal secret
    assert "--api-key" in cmd


def test_serve_fn_name_maps_key():
    assert vllm_serve._serve_fn_name("qwen3-embedding-4b") == "serve_qwen3_embedding_4b"
    assert vllm_serve._serve_fn_name("qwen3-embedding-8b") == "serve_qwen3_embedding_8b"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vllm_serve.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modal.vllm_serve'`.

- [ ] **Step 4: Create `modal/vllm_serve.py` with the pure helpers**

```python
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
    return Path(__file__).resolve().parent / "config.yaml"


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
        f"${VLLM_API_KEY_ENV}",
    ]
    if entry.get("dtype"):
        cmd += ["--dtype", str(entry["dtype"])]
    if entry.get("max_model_len"):
        cmd += ["--max-model-len", str(entry["max_model_len"])]
    cmd += ["--tensor-parallel-size", "1"]
    return cmd
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_vllm_serve.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add modal/config.yaml modal/vllm_serve.py tests/test_vllm_serve.py
git commit -m "feat(vllm): config registry + pure vllm-serve cmd helpers"
```

---

## Task 2: Modal serving app — image, volumes, endpoints, download

**Files:**
- Modify: `modal/vllm_serve.py`
- Test: `tests/test_vllm_serve.py`

- [ ] **Step 1: Write the failing test for app wiring**

Append to `tests/test_vllm_serve.py`:

```python
def test_app_defines_both_serve_endpoints():
    app = vllm_serve.app
    names = set(app.registered_functions.keys())
    assert "serve_qwen3_embedding_4b" in names
    assert "serve_qwen3_embedding_8b" in names


def test_image_installs_vllm():
    # The dockerfile commands should reference a pinned vllm.
    cmds = " ".join(vllm_serve._vllm_image.dockerfile_commands or [])
    assert "vllm" in cmds
```

Note: if `registered_functions` / `dockerfile_commands` accessors differ in modal 1.4.2, adapt to the equivalent (mirror how `tests/test_modal_app_resources.py` introspects `modal/app.py`). Confirm by reading that test first.

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vllm_serve.py -k "app_defines or image_installs" -v`
Expected: FAIL — `AttributeError: module 'modal.vllm_serve' has no attribute 'app'`.

- [ ] **Step 3: Add the Modal app, image, volumes, and endpoints to `modal/vllm_serve.py`**

Append after the pure helpers:

```python
import modal

VLLM_VERSION = "0.11.0"  # confirm latest stable supporting Qwen3-Embedding pooling

_registry = load_vllm_registry()
_HF_CACHE_DIR = "/root/.cache/huggingface"
_VLLM_CACHE_DIR = str(_registry.get("cache_dir", "/root/.cache/vllm"))

app = modal.App(_registry["app_name"])

ENV_SECRET = modal.Secret.from_dotenv(Path(__file__).resolve().parent.parent / ".env")

_vllm_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(f"vllm=={VLLM_VERSION}", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "VLLM_USE_V1": "1"})
)

hf_cache_vol = modal.Volume.from_name("music-crs-hf-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name(
    _registry["cache_volume"], create_if_missing=True
)

_VOLUMES = {_HF_CACHE_DIR: hf_cache_vol, _VLLM_CACHE_DIR: vllm_cache_vol}


def _run_vllm_serve(model_key: str) -> None:
    """Launch the vLLM OpenAI server for `model_key` (called inside the container)."""
    import os
    import subprocess

    entry = _registry["models"][model_key]
    cmd = _build_vllm_serve_cmd(entry, port=VLLM_PORT)
    # Expand $VLLM_API_KEY from the dotenv secret at exec time.
    subprocess.Popen(" ".join(cmd), shell=True, env={**os.environ})


def _register_serve_endpoint(model_key: str):
    entry = _registry["models"][model_key]

    @app.function(
        name=_serve_fn_name(model_key),
        image=_vllm_image,
        gpu=str(entry["gpu"]),
        volumes=_VOLUMES,
        secrets=[ENV_SECRET],
        timeout=int(entry["timeout"]),
        scaledown_window=int(entry["scaledown_window"]),
        min_containers=0,
    )
    @modal.concurrent(max_inputs=int(entry["max_inputs"]))
    @modal.web_server(port=VLLM_PORT, startup_timeout=10 * 60)
    def _serve():
        _run_vllm_serve(model_key)

    return _serve


# Materialize one endpoint per registry model.
serve_qwen3_embedding_4b = _register_serve_endpoint("qwen3-embedding-4b")
serve_qwen3_embedding_8b = _register_serve_endpoint("qwen3-embedding-8b")


@app.function(image=_vllm_image, volumes=_VOLUMES, timeout=3600)
def download(model: str = "qwen3-embedding-4b") -> str:
    """Optional pre-warm: download weights into the hf-cache volume and commit."""
    from huggingface_hub import snapshot_download

    entry = _registry["models"][model]
    path = snapshot_download(entry["hf_id"])
    hf_cache_vol.commit()
    return path
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_vllm_serve.py -v`
Expected: PASS (5 tests). If `registered_functions` accessor differs, fix the test to match modal 1.4.2 (see Step 1 note) — the app/image must still be defined.

- [ ] **Step 5: Verify the module imports cleanly without a Modal token**

Run: `.venv/bin/python -c "import modal.vllm_serve as v; print(v.app.name, list(v._registry['models']))"`
Expected: prints `music-crs-vllm ['qwen3-embedding-4b', 'qwen3-embedding-8b']` with no auth error.

- [ ] **Step 6: Commit**

```bash
git add modal/vllm_serve.py tests/test_vllm_serve.py
git commit -m "feat(vllm): scale-to-zero Modal embedding endpoints + pre-warm download"
```

---

## Task 3: Endpoint URL resolver (`endpoint_url` + qu_kwargs rewrite)

**Files:**
- Modify: `modal/vllm_serve.py`
- Test: `tests/test_vllm_serve.py`

- [ ] **Step 1: Write the failing test (Modal SDK mocked)**

Append to `tests/test_vllm_serve.py`:

```python
def test_endpoint_url_appends_v1(monkeypatch):
    class _FakeFn:
        def get_web_url(self):
            return "https://ws--music-crs-vllm-serve-qwen3-embedding-4b.modal.run"

    monkeypatch.setattr(
        vllm_serve.modal.Function, "from_name", staticmethod(lambda *a, **k: _FakeFn())
    )
    url = vllm_serve.endpoint_url("qwen3-embedding-4b")
    assert url.endswith("/v1")
    assert "serve-qwen3-embedding-4b" in url


def test_resolve_vllm_endpoints_rewrites_encoder(monkeypatch):
    monkeypatch.setattr(
        vllm_serve, "endpoint_url", lambda key: f"https://fake/{key}/v1"
    )
    qu = {"encoder": {"backend": "litellm", "vllm_endpoint": "qwen3-embedding-4b"}}
    out = vllm_serve.resolve_vllm_endpoints_in_qu_kwargs(qu)
    assert out["encoder"]["api_base"] == "https://fake/qwen3-embedding-4b/v1"
    assert "vllm_endpoint" not in out["encoder"]


def test_resolve_vllm_endpoints_noop_without_key():
    qu = {"encoder": {"backend": "litellm", "api_base": "https://x/v1"}}
    out = vllm_serve.resolve_vllm_endpoints_in_qu_kwargs(qu)
    assert out["encoder"]["api_base"] == "https://x/v1"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vllm_serve.py -k resolve -v`
Expected: FAIL — `AttributeError: ... has no attribute 'resolve_vllm_endpoints_in_qu_kwargs'`.

- [ ] **Step 3: Add the resolver functions to `modal/vllm_serve.py`**

Append:

```python
def endpoint_url(model_key: str) -> str:
    """Resolve the live web URL for a deployed serve endpoint, with `/v1` suffix."""
    fn = modal.Function.from_name(_registry["app_name"], _serve_fn_name(model_key))
    base = fn.get_web_url().rstrip("/")
    return base + "/v1"


def resolve_vllm_endpoints_in_qu_kwargs(qu_kwargs: dict[str, Any]) -> dict[str, Any]:
    """If encoder declares `vllm_endpoint: <key>`, replace it with a resolved
    `api_base`. No-op when absent. Mutates and returns the dict in place."""
    enc = qu_kwargs.get("encoder")
    if isinstance(enc, dict) and enc.get("vllm_endpoint"):
        enc["api_base"] = endpoint_url(enc.pop("vllm_endpoint"))
    return qu_kwargs
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_vllm_serve.py -k "endpoint_url or resolve" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add modal/vllm_serve.py tests/test_vllm_serve.py
git commit -m "feat(vllm): logical-endpoint resolver for encoder api_base"
```

---

## Task 4: Forward `extra_params` (cold-start timeout) in the litellm encoder factory

**Files:**
- Modify: `mcrs/qu_modules/compiler_v0plus_qu.py` (litellm branch of the encoder factory, ~line 190)
- Test: `tests/test_v0plus_compiler_qu.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_v0plus_compiler_qu.py` (import the encoder factory the same way existing tests in that file do; confirm the function name by reading the file — it is the `build`/`_build_encoder` helper that branches on `enc_cfg["backend"]`):

```python
def test_litellm_encoder_forwards_extra_params():
    from mcrs.qu_modules.compiler_v0plus_qu import _build_encoder  # adjust to real name

    enc = _build_encoder(
        {
            "backend": "litellm",
            "model_name": "openai/Qwen/Qwen3-Embedding-4B",
            "api_base": "https://fake/v1",
            "api_key": "k",
            "extra_params": {"timeout": 600},
        }
    )
    assert enc.extra_params == {"timeout": 600}
```

If the factory function is named differently (e.g. `build_text_embedder`), use that name — read the file to confirm before writing the test.

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_v0plus_compiler_qu.py -k forwards_extra_params -v`
Expected: FAIL — `assert {} == {'timeout': 600}` (extra_params not forwarded).

- [ ] **Step 3: Forward `extra_params` in the litellm branch**

In `mcrs/qu_modules/compiler_v0plus_qu.py`, the litellm branch currently ends:

```python
        return LiteLLMEmbeddingClient(
            model_name=enc_cfg.get("model_name", "openai/Qwen/Qwen3-Embedding-0.6B"),
            api_base=enc_cfg.get("api_base", "https://api.deepinfra.com/v1/openai"),
            api_key=api_key,
            batch_size=int(enc_cfg.get("batch_size", 32)),
            encoding_format=enc_cfg.get("encoding_format", "float"),
        )
```

Add one line forwarding `extra_params`:

```python
        return LiteLLMEmbeddingClient(
            model_name=enc_cfg.get("model_name", "openai/Qwen/Qwen3-Embedding-0.6B"),
            api_base=enc_cfg.get("api_base", "https://api.deepinfra.com/v1/openai"),
            api_key=api_key,
            batch_size=int(enc_cfg.get("batch_size", 32)),
            encoding_format=enc_cfg.get("encoding_format", "float"),
            extra_params=dict(enc_cfg.get("extra_params") or {}),
        )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_v0plus_compiler_qu.py -k forwards_extra_params -v`
Expected: PASS.

- [ ] **Step 5: Run the full file to confirm no regressions**

Run: `.venv/bin/python -m pytest tests/test_v0plus_compiler_qu.py -v`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add mcrs/qu_modules/compiler_v0plus_qu.py tests/test_v0plus_compiler_qu.py
git commit -m "feat(encoder): forward extra_params (cold-start timeout) in litellm encoder"
```

---

## Task 5: Hook the resolver into the inference entrypoints

**Files:**
- Modify: `run_inference_devset.py` (after `qu_kwargs` is built, ~line 92, before `load_crs_baseline`)
- Modify: `run_inference_blindset.py` (equivalent point — read the file to find it)

- [ ] **Step 1: Add resolution in `run_inference_devset.py`**

After the block that builds `qu_kwargs` (the `if raw_qu_kwargs is None ... else dict(raw_qu_kwargs)` chain ending at the line before `music_crs = load_crs_baseline(`), insert:

```python
    # Resolve any logical vLLM endpoint (encoder.vllm_endpoint) into a live
    # Modal web URL (encoder.api_base). No-op when not present, and only imports
    # Modal when a vllm_endpoint is actually declared.
    if isinstance(qu_kwargs.get("encoder"), dict) and qu_kwargs["encoder"].get(
        "vllm_endpoint"
    ):
        import importlib

        importlib.import_module("modal.vllm_serve").resolve_vllm_endpoints_in_qu_kwargs(
            qu_kwargs
        )
```

- [ ] **Step 2: Verify the devset runner still imports/parses**

Run: `.venv/bin/python -c "import ast; ast.parse(open('run_inference_devset.py').read()); print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Add the same resolution in `run_inference_blindset.py`**

Read `run_inference_blindset.py`, find where it builds `qu_kwargs` before constructing the CRS, and insert the identical block from Step 1.

- [ ] **Step 4: Verify the blindset runner parses**

Run: `.venv/bin/python -c "import ast; ast.parse(open('run_inference_blindset.py').read()); print('ok')"`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add run_inference_devset.py run_inference_blindset.py
git commit -m "feat(inference): resolve encoder vllm_endpoint -> api_base at startup"
```

---

## Task 6: A/B experiment configs

**Files:**
- Create: `configs/v0plus_compiler_image_qwen3emb4b_vllm_devset.yaml`
- Create: `configs/v0plus_compiler_image_qwen3emb8b_vllm_devset.yaml`

- [ ] **Step 1: Read the canonical config to copy faithfully**

Run: `sed -n '1,200p' configs/v0plus_compiler_image_devset.yaml`
Copy the entire file content; you will change only the `encoder:` block.

- [ ] **Step 2: Create the 4B config**

Create `configs/v0plus_compiler_image_qwen3emb4b_vllm_devset.yaml` as a verbatim copy of `configs/v0plus_compiler_image_devset.yaml`, replacing the `encoder:` block with:

```yaml
  encoder:
    backend: "litellm"
    model_name: "openai/Qwen/Qwen3-Embedding-4B"
    # api_base is resolved at runtime from this logical endpoint name.
    vllm_endpoint: "qwen3-embedding-4b"
    api_key: "${oc.env:VLLM_API_KEY,EMPTY}"
    batch_size: 32
    encoding_format: "float"
    # Absorb scale-to-zero cold starts (first embed after idle can take 30-90s+).
    extra_params:
      timeout: 600
```

- [ ] **Step 3: Create the 8B config**

Create `configs/v0plus_compiler_image_qwen3emb8b_vllm_devset.yaml` identically, but with:

```yaml
  encoder:
    backend: "litellm"
    model_name: "openai/Qwen/Qwen3-Embedding-8B"
    vllm_endpoint: "qwen3-embedding-8b"
    api_key: "${oc.env:VLLM_API_KEY,EMPTY}"
    batch_size: 32
    encoding_format: "float"
    extra_params:
      timeout: 600
```

- [ ] **Step 4: Verify both configs load under OmegaConf**

Run:
```bash
.venv/bin/python -c "
from omegaconf import OmegaConf
for t in ['qwen3emb4b','qwen3emb8b']:
    c=OmegaConf.load(f'configs/v0plus_compiler_image_{t}_vllm_devset.yaml')
    enc=c.qu_kwargs.encoder
    assert enc.backend=='litellm' and enc.vllm_endpoint==f'qwen3-embedding-{t[5:7]}b'.replace('emb','-embedding-')[:18] or True
    print(t, 'ok', enc.model_name)
"
```
Expected: prints `qwen3emb4b ok openai/Qwen/Qwen3-Embedding-4B` and the 8B line. (The assert is a smoke parse; the print is the real check.)

- [ ] **Step 5: Commit**

```bash
git add configs/v0plus_compiler_image_qwen3emb4b_vllm_devset.yaml configs/v0plus_compiler_image_qwen3emb8b_vllm_devset.yaml
git commit -m "feat(configs): A/B vLLM Qwen3-Embedding 4B/8B devset configs"
```

---

## Task 7: Secret docs, smoke entrypoint, and modal_setup docs

**Files:**
- Modify: `.env.example`
- Modify: `modal/vllm_serve.py` (add `smoke`)
- Modify: `docs/modal_setup.md`

- [ ] **Step 1: Document the secret in `.env.example`**

Add to `.env.example`:

```
# Shared bearer key for the self-hosted vLLM embedding endpoints (modal/vllm_serve.py).
VLLM_API_KEY=change-me
```

- [ ] **Step 2: Add the `smoke` entrypoint to `modal/vllm_serve.py`**

Append:

```python
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

    cache_dir = os.environ.get("MCRS_LITELLM_CACHE_DIR", "/tmp/mcrs-vllm-smoke-cache")
    setup_litellm_cache(cache_dir=cache_dir)

    entry = _registry["models"][model]
    api_base = endpoint_url(model)
    kwargs = dict(
        model=f"openai/{entry['served_name']}",
        input=[text],
        api_base=api_base,
        api_key=os.environ.get(VLLM_API_KEY_ENV, "EMPTY"),
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
```

- [ ] **Step 3: Verify the module still imports**

Run: `.venv/bin/python -c "import modal.vllm_serve; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Add a deploy/use section to `docs/modal_setup.md`**

Append a `## vLLM embedding services` section documenting:
- `modal deploy modal/vllm_serve.py` to deploy both endpoints.
- Scale-to-zero behavior + `scaledown_window`; first-hit cold start.
- `VLLM_API_KEY` in `.env`.
- Optional pre-warm: `modal run modal/vllm_serve.py::download --model qwen3-embedding-4b`.
- Smoke: `modal run modal/vllm_serve.py::smoke --model qwen3-embedding-4b`.
- That configs reference the service via `encoder.vllm_endpoint` (resolved to `api_base`), and caching reuses the LiteLLM file cache so a cache hit never wakes the GPU.

- [ ] **Step 5: Run the full unit test suite for this feature**

Run: `.venv/bin/python -m pytest tests/test_vllm_serve.py tests/test_v0plus_compiler_qu.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .env.example modal/vllm_serve.py docs/modal_setup.md
git commit -m "feat(vllm): cost-gated smoke entrypoint + secret/docs"
```

---

## Task 8: GPU verification (gated — requires explicit approval)

> Per the project rule "Modal full-devset runs need approval": do NOT run this without the user's go-ahead. It wakes a GPU and incurs cost.

- [ ] **Step 1: Deploy the serving app**

Run: `modal deploy modal/vllm_serve.py`
Expected: deploy succeeds; two web endpoints printed.

- [ ] **Step 2: (Optional) Pre-warm 4B weights into the volume**

Run: `modal run modal/vllm_serve.py::download --model qwen3-embedding-4b`
Expected: prints a snapshot path; volume committed.

- [ ] **Step 3: Run the cache-hit smoke test**

Run: `modal run modal/vllm_serve.py::smoke --model qwen3-embedding-4b`
Expected: prints `dim=2560 cache_hit_second=True vectors_match=True` (dim per Qwen3-Embedding-4B) and exits 0.

- [ ] **Step 4: Tiny end-to-end devset slice (50 sessions) on 4B**

Run: `python run_experiment.py --backend modal --tid v0plus_compiler_image_qwen3emb4b_vllm_devset --num_sessions 50`
Expected: completes; report the slice NDCG@20 vs the canonical `v0plus_compiler_image_devset` slice. Do not launch the full devset without separate approval.

---

## Self-Review

**Spec coverage:**
- §1 serving app → Tasks 1–2. §2 weights/volume + pre-warm → Task 2 (`download`) + image env. §3 resolver → Task 3 + Task 5 wiring. §4 caching (no new code) → relies on existing `setup_litellm_cache`; exercised by Task 7 smoke. §5 config/auth → Tasks 1, 6, 7. §6 cold-start timeout → Task 4 (`extra_params`) + Task 6 configs (`timeout: 600`) + `startup_timeout`. §7 tests → Tasks 1–4 (unit) + Task 7/8 (smoke). Deliverables 1–6 all mapped. No gaps.

**Placeholder scan:** No TBD/TODO. Two explicit "confirm against modal 1.4.2 / read the file to confirm the real name" notes (registry-introspection accessor in Task 2 Step 1; encoder-factory function name in Task 4 Step 1) are verification instructions with concrete fallbacks, not unfinished code.

**Type consistency:** Helper names are stable across tasks — `load_vllm_registry`, `_build_vllm_serve_cmd`, `_serve_fn_name`, `endpoint_url`, `resolve_vllm_endpoints_in_qu_kwargs`, `_register_serve_endpoint`. `VLLM_API_KEY_ENV` / `VLLM_PORT` constants reused consistently. Config keys (`vllm.models.<key>.{hf_id,served_name,task,gpu,dtype,max_model_len,max_inputs,scaledown_window,timeout}`, `vllm.app_name`, `vllm.cache_volume`, `vllm.cache_dir`) match between Task 1 YAML and every consumer.

**Known confirm-at-impl items (from spec):** exact pinned vLLM version (`0.11.0` placeholder — verify newest stable with Qwen3-Embedding pooling); whether `--task embed` is required vs auto-detected (harmless if explicit); final 4B/8B GPU choices after a throughput check.
