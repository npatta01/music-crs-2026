from .base import (
    PassthroughQU,
    LastUserTurnQU,
    UserTurnsOnlyQU,
    LastNUserTurnsQU,
    NoMusicHistoryQU,
)


def load_qu_module(qu_type: str):
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
    else:
        raise ValueError(f"Unsupported QU type: {qu_type}")
