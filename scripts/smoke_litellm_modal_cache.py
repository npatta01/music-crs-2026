from __future__ import annotations

import argparse
import json

import modal


DEFAULT_CHAT_PROMPT = "Write one short sentence recommending an atmospheric synthwave track."
CHAT_PROFILES = {
    "qwen-0.6b": {
        "model": "huggingface/featherless-ai/Qwen/Qwen3-0.6B",
        "prompt": "Reply with exactly: ok /no_think",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test Modal LiteLLM cache for embedding and chat.")
    parser.add_argument("--app-name", default="music-crs")
    parser.add_argument("--class-name", default="ModalLiteLLMService")
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--embedding-api-base", default=None)
    parser.add_argument("--embedding-text", default="dark atmospheric synthwave with neon texture")
    parser.add_argument("--chat-profile", choices=sorted(CHAT_PROFILES), default=None)
    parser.add_argument("--chat-model", default=None)
    parser.add_argument("--chat-api-base", default=None)
    parser.add_argument("--chat-prompt", default=DEFAULT_CHAT_PROMPT)
    parser.add_argument("--skip-embedding", action="store_true")
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument(
        "--allow-provider-errors",
        action="store_true",
        help="Print provider errors instead of failing before later checks run.",
    )
    return parser


def resolve_chat_options(
    chat_profile: str | None,
    chat_model: str | None,
    chat_prompt: str,
) -> tuple[str | None, str]:
    if chat_profile is None:
        return chat_model, chat_prompt

    profile = CHAT_PROFILES[chat_profile]
    resolved_model = chat_model or profile["model"]
    resolved_prompt = chat_prompt
    if chat_prompt == DEFAULT_CHAT_PROMPT:
        resolved_prompt = profile["prompt"]
    return resolved_model, resolved_prompt


def _check_cache_hit(name: str, first: dict, second: dict, allow_provider_errors: bool) -> None:
    for label, result in (("first", first), ("second", second)):
        if result.get("ok") is False:
            if allow_provider_errors:
                return
            error_type = result.get("error_type", "ProviderError")
            error = result.get("error", "")
            raise SystemExit(f"{name} {label} call failed: {error_type}: {error}")

    if second.get("cache_hit") is not True:
        raise SystemExit(f"Expected second {name} call to be a LiteLLM cache hit")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service_cls = modal.Cls.from_name(args.app_name, args.class_name)
    service = service_cls()
    chat_model, chat_prompt = resolve_chat_options(
        chat_profile=args.chat_profile,
        chat_model=args.chat_model,
        chat_prompt=args.chat_prompt,
    )

    result = {}
    if not args.skip_embedding:
        embed_first = service.embed_once_with_cache_status.remote(
            text=args.embedding_text,
            model_name=args.embedding_model,
            api_base=args.embedding_api_base,
        )
        embed_second = service.embed_once_with_cache_status.remote(
            text=args.embedding_text,
            model_name=args.embedding_model,
            api_base=args.embedding_api_base,
        )
        result["embedding_first"] = embed_first
        result["embedding_second"] = embed_second

    if not args.skip_chat:
        chat_first = service.chat_once_with_cache_status.remote(
            prompt=chat_prompt,
            model_name=chat_model,
            api_base=args.chat_api_base,
        )
        chat_second = service.chat_once_with_cache_status.remote(
            prompt=chat_prompt,
            model_name=chat_model,
            api_base=args.chat_api_base,
        )
        result["chat_first"] = chat_first
        result["chat_second"] = chat_second

    print(json.dumps(result, indent=2))

    if not args.skip_embedding:
        _check_cache_hit(
            "embedding",
            result["embedding_first"],
            result["embedding_second"],
            args.allow_provider_errors,
        )
    if not args.skip_chat:
        _check_cache_hit(
            "chat",
            result["chat_first"],
            result["chat_second"],
            args.allow_provider_errors,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
