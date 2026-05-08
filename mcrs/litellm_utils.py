"""Utilities for proxy-backed LiteLLM model naming."""


def normalize_proxy_model_name(model_name: str) -> str:
    """Ensure LiteLLM SDK calls use an OpenAI-compatible provider prefix."""
    if "/" not in model_name:
        return f"openai/{model_name}"
    return model_name


def normalize_openai_client_model_name(model_name: str) -> str:
    """Keep the proxy-visible model id unchanged for OpenAI-compatible client calls."""
    return model_name
