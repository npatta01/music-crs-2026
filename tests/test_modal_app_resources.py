from __future__ import annotations

import ast
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
