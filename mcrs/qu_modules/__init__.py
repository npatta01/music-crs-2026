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
        return LLMRewriteQU(
            model_name=qu_kwargs["model_name"],
            prompt_name=qu_kwargs["prompt_name"],
            max_new_tokens=int(qu_kwargs.get("max_new_tokens", 96)),
            device=device,
            attn_implementation=attn_implementation,
            dtype=dtype,
            audit_path=qu_kwargs.get("audit_path"),
            stats_path=qu_kwargs.get("stats_path"),
        )
    else:
        raise ValueError(f"Unsupported QU type: {qu_type}")
