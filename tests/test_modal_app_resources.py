from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from omegaconf import OmegaConf


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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

    assert float(config.lancedb.inference_cpu) >= 8.0
    assert int(config.lancedb.inference_memory) >= 32768
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


def test_modal_litellm_service_scales_to_zero_and_uses_cache_volume():
    keywords = _modal_class_decorator_keywords("ModalLiteLLMService")

    assert isinstance(keywords["min_containers"], ast.Constant)
    assert keywords["min_containers"].value == 0
    assert _name(keywords["cpu"]) == "LITELLM_CPU"
    assert _name(keywords["memory"]) == "LITELLM_MEMORY"
    assert _name(keywords["scaledown_window"]) == "LITELLM_SCALEDOWN_WINDOW"
    assert _name(keywords["max_containers"]) == "LITELLM_MAX_CONTAINERS"


def test_modal_litellm_disk_cache_dependency_is_installed():
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
