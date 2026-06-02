import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_vllm_serve_module():
    spec = importlib.util.spec_from_file_location(
        "vllm_serve_under_test", PROJECT_ROOT / "modal" / "vllm_serve.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


vllm_serve = _load_vllm_serve_module()


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
    assert "--api-key" in cmd
    assert cmd[cmd.index("--api-key") + 1] == "$VLLM_API_KEY"


def test_serve_fn_name_maps_key():
    assert vllm_serve._serve_fn_name("qwen3-embedding-4b") == "serve_qwen3_embedding_4b"
    assert vllm_serve._serve_fn_name("qwen3-embedding-8b") == "serve_qwen3_embedding_8b"


def test_build_vllm_serve_cmd_omits_optional_flags():
    entry = {"hf_id": "X/Y", "served_name": "X/Y", "task": "embed"}
    cmd = vllm_serve._build_vllm_serve_cmd(entry, port=8000)
    assert "--dtype" not in cmd
    assert "--max-model-len" not in cmd
    assert cmd[cmd.index("--tensor-parallel-size") + 1] == "1"


def test_app_defines_both_serve_endpoints():
    assert isinstance(vllm_serve.app, vllm_serve.modal.App)
    assert vllm_serve.serve_qwen3_embedding_4b is not None
    assert vllm_serve.serve_qwen3_embedding_8b is not None


def test_image_is_modal_image():
    assert isinstance(vllm_serve._vllm_image, vllm_serve.modal.Image)


def test_safe_vllm_token_regex():
    assert vllm_serve._SAFE_VLLM_TOKEN.match("Qwen/Qwen3-Embedding-4B")
    assert vllm_serve._SAFE_VLLM_TOKEN.match("bfloat16")
    assert vllm_serve._SAFE_VLLM_TOKEN.match("8192")
    assert not vllm_serve._SAFE_VLLM_TOKEN.match("bad model")   # space
    assert not vllm_serve._SAFE_VLLM_TOKEN.match("a;rm -rf")    # metachar
