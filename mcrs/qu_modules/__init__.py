from .base import (
    PassthroughQU,
    LastUserTurnQU,
    UserTurnsOnlyQU,
    LastNUserTurnsQU,
    NoMusicHistoryQU,
)
from .llm_rewrite import LLMRewriteQU


def load_qu_module(
    qu_type: str,
    cache_dir: str = "./cache",
    device: str = "cpu",
    attn_implementation: str = "eager",
    dtype=None,
    **qu_kwargs,
):
    if qu_type == "passthrough":
        return PassthroughQU()
    elif qu_type == "last_user_turn":
        return LastUserTurnQU()
    elif qu_type == "user_turns_only":
        return UserTurnsOnlyQU()
    elif qu_type == "last_2_user_turns":
        return LastNUserTurnsQU(n=2)
    elif qu_type == "last_3_user_turns":
        return LastNUserTurnsQU(n=3)
    elif qu_type == "no_music_history":
        return NoMusicHistoryQU()
    elif qu_type == "llm_rewrite":
        from .llm_rewrite import build_model_adapter
        backend = qu_kwargs.get("backend", "local")
        adapter = build_model_adapter(
            model_name=qu_kwargs["model_name"],
            device=device,
            attn_implementation=attn_implementation,
            dtype=dtype,
            backend=backend,
            api_base=qu_kwargs.get("api_base"),
            api_key=qu_kwargs.get("api_key"),
            temperature=float(qu_kwargs.get("temperature", 0.0)),
        )
        return LLMRewriteQU(
            model_name=qu_kwargs["model_name"],
            prompt_name=qu_kwargs["prompt_name"],
            max_new_tokens=int(qu_kwargs.get("max_new_tokens", 96)),
            device=device,
            attn_implementation=attn_implementation,
            dtype=dtype,
            audit_path=qu_kwargs.get("audit_path"),
            stats_path=qu_kwargs.get("stats_path"),
            adapter=adapter,
        )
    else:
        raise ValueError(f"Unsupported QU type: {qu_type}")
