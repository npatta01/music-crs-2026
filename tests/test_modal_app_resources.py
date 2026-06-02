from __future__ import annotations

import ast
import importlib.util
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

from omegaconf import OmegaConf


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_modal_app_module():
    spec = importlib.util.spec_from_file_location("modal_app_under_test", PROJECT_ROOT / "modal" / "app.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _modal_function_decorator_keywords(function_name: str) -> dict[str, ast.AST]:
    tree = ast.parse((PROJECT_ROOT / "modal" / "app.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "function"
                ):
                    return {keyword.arg: keyword.value for keyword in decorator.keywords}
    raise AssertionError(f"Could not find @app.function decorator for {function_name}")


def _modal_class_decorator_keywords(class_name: str) -> dict[str, ast.AST]:
    tree = ast.parse((PROJECT_ROOT / "modal" / "app.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "cls"
                ):
                    return {keyword.arg: keyword.value for keyword in decorator.keywords}
    raise AssertionError(f"Could not find @app.cls decorator for {class_name}")


def _modal_class_method_arguments(class_name: str, method_name: str) -> list[str]:
    tree = ast.parse((PROJECT_ROOT / "modal" / "app.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return [argument.arg for argument in item.args.args]
    raise AssertionError(f"Could not find {class_name}.{method_name}")


def _name(node: ast.AST) -> str:
    assert isinstance(node, ast.Name)
    return node.id


def test_lancedb_modal_cpu_resource_config_is_explicit():
    config = OmegaConf.load(PROJECT_ROOT / "modal" / "config.yaml")

    # Inference container is async-I/O bound (LLM extractor calls dominate);
    # 2 cores / 16 GiB is the measured-headroom right-size for max_in_flight=8.
    # If max_in_flight is pushed back to 16+, this floor needs to be raised
    # alongside the config bump. Memory floor still ≥ 16384 to hold the
    # in-memory LanceDB catalog scan + eager vector loads.
    assert float(config.lancedb.inference_cpu) >= 2.0
    assert int(config.lancedb.inference_memory) >= 16384
    assert float(config.lancedb.query_cpu) >= 4.0
    assert int(config.lancedb.query_memory) >= 16384


def test_lancedb_cpu_functions_request_configured_cpu_and_memory():
    devset_keywords = _modal_function_decorator_keywords("_inference_devset_cpu")
    blindset_keywords = _modal_function_decorator_keywords("_inference_blindset_cpu")
    query_keywords = _modal_function_decorator_keywords("query_lancedb")

    assert _name(devset_keywords["cpu"]) == "LANCEDB_INFERENCE_CPU"
    assert _name(devset_keywords["memory"]) == "LANCEDB_INFERENCE_MEMORY"
    assert _name(blindset_keywords["cpu"]) == "LANCEDB_INFERENCE_CPU"
    assert _name(blindset_keywords["memory"]) == "LANCEDB_INFERENCE_MEMORY"

    assert _name(query_keywords["cpu"]) == "LANCEDB_QUERY_CPU"
    assert _name(query_keywords["memory"]) == "LANCEDB_QUERY_MEMORY"


def test_modal_retrieval_service_scales_to_zero():
    keywords = _modal_class_decorator_keywords("ModalRetrievalService")

    assert isinstance(keywords["min_containers"], ast.Constant)
    assert keywords["min_containers"].value == 0
    assert _name(keywords["cpu"]) == "LANCEDB_QUERY_CPU"
    assert _name(keywords["memory"]) == "LANCEDB_QUERY_MEMORY"
    assert _name(keywords["scaledown_window"]) == "LANCEDB_QUERY_SCALEDOWN_WINDOW"
    assert _name(keywords["max_containers"]) == "LANCEDB_QUERY_MAX_CONTAINERS"


def test_modal_lancedb_query_default_uses_schema_compatible_fts():
    source = (PROJECT_ROOT / "modal" / "app.py").read_text(encoding="utf-8")

    assert '"kind": "fts_compat"' in source
    assert '"kind": "fts_bm25s_compat"' not in source


def test_modal_litellm_service_scales_to_zero():
    keywords = _modal_class_decorator_keywords("ModalLiteLLMService")

    assert isinstance(keywords["min_containers"], ast.Constant)
    assert keywords["min_containers"].value == 0
    assert _name(keywords["cpu"]) == "LITELLM_CPU"
    assert _name(keywords["memory"]) == "LITELLM_MEMORY"
    assert _name(keywords["scaledown_window"]) == "LITELLM_SCALEDOWN_WINDOW"
    assert _name(keywords["max_containers"]) == "LITELLM_MAX_CONTAINERS"


def test_modal_litellm_cache_uses_file_backend_on_new_v2_volume():
    config = OmegaConf.load(PROJECT_ROOT / "modal" / "config.yaml")
    source = (PROJECT_ROOT / "modal" / "app.py").read_text(encoding="utf-8")

    assert config.litellm_cache.backend == "file"
    assert config.volumes.litellm_cache == "music-crs-litellm-cache-v2"
    assert 'modal.Volume.from_name(LITELLM_CACHE_VOLUME, create_if_missing=True, version=2)' in source
    assert '"MCRS_LITELLM_CACHE_BACKEND": "file"' in source
    assert '"MCRS_LITELLM_CACHE_DIR": LITELLM_CACHE_DIR' in source


def test_modal_litellm_cache_dependency_is_installed():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert any(dependency.startswith("litellm[caching]") for dependency in dependencies)


def test_modal_litellm_defaults_use_openrouter_models():
    config = OmegaConf.load(PROJECT_ROOT / "modal" / "config.yaml")

    assert config.litellm.embedding_model == "openrouter/openai/text-embedding-3-small"
    assert config.litellm.chat_model == "openrouter/google/gemma-3-4b-it"
    assert config.litellm.small_chat_model == "huggingface/featherless-ai/Qwen/Qwen3-0.6B"


def test_modal_litellm_smoke_methods_accept_model_overrides():
    embed_args = _modal_class_method_arguments("ModalLiteLLMService", "embed_once_with_cache_status")
    chat_args = _modal_class_method_arguments("ModalLiteLLMService", "chat_once_with_cache_status")

    assert embed_args == ["self", "text", "model_name", "api_base"]
    assert chat_args == ["self", "prompt", "model_name", "api_base"]


def test_modal_retrieval_methods_accept_request_retrieval_config():
    retrieve_args = _modal_class_method_arguments("ModalRetrievalService", "retrieve")
    batch_args = _modal_class_method_arguments("ModalRetrievalService", "retrieve_batch")

    assert retrieve_args == ["self", "query", "topk", "retrieval_config"]
    assert batch_args == ["self", "queries", "topk", "retrieval_config"]


def test_modal_retrieval_config_services_are_cached(monkeypatch):
    module = _load_modal_app_module()
    created_configs = []

    class FakeRetriever:
        pass

    class FakeService:
        def __init__(self, retriever, embedding_client):
            self.retriever = retriever
            self.embedding_client = embedding_client

    def fake_from_retrieval_config(config, embedding_client=None):
        created_configs.append(config)
        assert embedding_client == "embedder"
        return FakeRetriever()

    monkeypatch.setattr(
        "mcrs.lancedb.retriever.LanceDbRetriever.from_retrieval_config",
        fake_from_retrieval_config,
    )
    monkeypatch.setattr("mcrs.retrieval_services.RetrievalService", FakeService)

    modal_retrieval_service = module.ModalRetrievalService._get_user_cls()
    service = modal_retrieval_service.__new__(modal_retrieval_service)
    service.service = object()
    service.embedding_client = "embedder"
    service._retrieval_service_cache = {}
    service._retrieval_service_cache_order = []

    retrieval_config = {
        "searches": [
            {
                "name": "metadata_dense",
                "kind": "dense_vector",
                "vector_field": "metadata_qwen3_embedding_0_6b",
                "topk": 1000,
            }
        ]
    }
    first = service._service_for_retrieval_config(retrieval_config, topk=20)
    second = service._service_for_retrieval_config(dict(retrieval_config), topk=20)

    assert first is second
    assert len(created_configs) == 1


def test_modal_litellm_unknown_model_does_not_use_hf_token():
    module = _load_modal_app_module()
    modal_litellm_service = module.ModalLiteLLMService._get_user_cls()
    service = modal_litellm_service.__new__(modal_litellm_service)
    service.hf_token = "hf-secret"
    service.openrouter_api_key = "or-secret"
    # ModalLiteLLMService now also stashes a deepinfra_api_key so the routing
    # helper can pin BYOK on DeepInfra api_bases (e.g. the v0+ Qwen3 encoder
    # route). The test sets a sentinel so we can assert it isn't accidentally
    # used for non-DeepInfra models.
    service.deepinfra_api_key = "di-secret"

    assert service._api_key_for_model("openrouter/google/gemma-3-4b-it", None) == "or-secret"
    assert service._api_key_for_model("huggingface/featherless-ai/Qwen/Qwen3-0.6B", None) == "hf-secret"
    assert service._api_key_for_model("openai/text-embedding-3-small", None) is None


def test_modal_litellm_cache_lookup_logs_failure(monkeypatch, capsys):
    module = _load_modal_app_module()

    class FakeCache:
        def get_cache(self, **kwargs):
            raise RuntimeError("cache unavailable")

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(cache=FakeCache()))

    assert module.ModalLiteLLMService._cache_hit_before_call({"model": "x"}) is None
    captured = capsys.readouterr()
    assert "LiteLLM cache lookup failed" in captured.out


def test_query_lancedb_rejects_dense_vector_config():
    module = _load_modal_app_module()

    try:
        module._ensure_query_lancedb_fts_only(
            {
                "searches": [
                    {
                        "name": "metadata_dense",
                        "kind": "dense_vector",
                        "vector_field": "metadata_qwen3_embedding_0_6b",
                    }
                ]
            }
        )
    except ValueError as exc:
        assert "query_lancedb is FTS-only" in str(exc)
    else:
        raise AssertionError("Expected dense_vector config to be rejected")


def _class_volume_dir_consts(class_name: str) -> set[str]:
    """Constant names used as keys in a Modal class's `volumes=` dict literal."""
    tree = ast.parse((PROJECT_ROOT / "modal" / "app.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    for keyword in decorator.keywords:
                        if keyword.arg == "volumes":
                            if not isinstance(keyword.value, ast.Dict):
                                raise AssertionError(
                                    f"{class_name} volumes= is not a dict literal"
                                )
                            return {
                                k.id
                                for k in keyword.value.keys
                                if isinstance(k, ast.Name)
                            }
            raise AssertionError(f"Could not find volumes= kwarg on {class_name} decorator")
    raise AssertionError(f"Could not find class {class_name} in modal/app.py")


def test_gpu_encoders_mount_embedding_cache():
    assert "EMBEDDING_CACHE_DIR" in _class_volume_dir_consts("Qwen3Encoder")
    assert "EMBEDDING_CACHE_DIR" in _class_volume_dir_consts("MultimodalTextEncoder")
