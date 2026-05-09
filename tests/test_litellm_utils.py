from mcrs.litellm_utils import normalize_proxy_model_name


def test_normalize_proxy_model_name_ensures_openai_provider_prefix():
    assert normalize_proxy_model_name("qwen3.5-9b") == "openai/qwen3.5-9b"
    assert normalize_proxy_model_name("text-embedding-3-small") == "openai/text-embedding-3-small"


def test_normalize_proxy_model_name_keeps_existing_provider_paths():
    assert normalize_proxy_model_name("openai/qwen3.5-9b") == "openai/qwen3.5-9b"
    assert normalize_proxy_model_name("google/gemma-3-4b-it") == "google/gemma-3-4b-it"
