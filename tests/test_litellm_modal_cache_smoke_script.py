from __future__ import annotations


def test_qwen_0_6b_chat_profile_sets_model_and_prompt():
    from scripts.smoke_litellm_modal_cache import resolve_chat_options

    model, prompt = resolve_chat_options(
        chat_profile="qwen-0.6b",
        chat_model=None,
        chat_prompt="Write one short sentence recommending an atmospheric synthwave track.",
    )

    assert model == "huggingface/featherless-ai/Qwen/Qwen3-0.6B"
    assert prompt == "Reply with exactly: ok /no_think"


def test_qwen_0_6b_chat_profile_preserves_explicit_prompt():
    from scripts.smoke_litellm_modal_cache import resolve_chat_options

    model, prompt = resolve_chat_options(
        chat_profile="qwen-0.6b",
        chat_model=None,
        chat_prompt="custom prompt",
    )

    assert model == "huggingface/featherless-ai/Qwen/Qwen3-0.6B"
    assert prompt == "custom prompt"
