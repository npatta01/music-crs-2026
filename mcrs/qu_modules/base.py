from typing import List


def _render_role(role: str) -> str:
    return "assistant" if role == "music" else role


class PassthroughQU:
    """QU module that returns the conversation text unchanged (current behavior).

    Music turns (role="music") are rendered with the "assistant:" prefix so the
    output is byte-identical to the legacy parser, which used to relabel music
    turns as assistant before the QU saw them.
    """

    def transform_query(self, session_memory: list) -> str:
        return "\n".join(
            f"{_render_role(turn['role'])}: {turn['content']}"
            for turn in session_memory
        )

    def batch_transform_queries(self, session_memories: List[list]) -> List[str]:
        return [self.transform_query(memory) for memory in session_memories]


class LastUserTurnQU:
    """Return only the last user turn's content."""

    def transform_query(self, session_memory: list) -> str:
        for turn in reversed(session_memory):
            if turn["role"] == "user":
                return turn["content"]
        return ""

    def batch_transform_queries(self, session_memories: List[list]) -> List[str]:
        return [self.transform_query(memory) for memory in session_memories]


class UserTurnsOnlyQU:
    """Concatenate every user turn's content, in order."""

    def transform_query(self, session_memory: list) -> str:
        return "\n".join(
            turn["content"] for turn in session_memory if turn["role"] == "user"
        )

    def batch_transform_queries(self, session_memories: List[list]) -> List[str]:
        return [self.transform_query(memory) for memory in session_memories]


class LastNUserTurnsQU:
    """Concatenate the last N user turns' content, in chronological order."""

    def __init__(self, n: int):
        self.n = n

    def transform_query(self, session_memory: list) -> str:
        user_contents = [t["content"] for t in session_memory if t["role"] == "user"]
        return "\n".join(user_contents[-self.n:])

    def batch_transform_queries(self, session_memories: List[list]) -> List[str]:
        return [self.transform_query(memory) for memory in session_memories]


class NoMusicHistoryQU:
    """Same formatting as PassthroughQU, but skips music-recommendation turns."""

    def transform_query(self, session_memory: list) -> str:
        return "\n".join(
            f"{turn['role']}: {turn['content']}"
            for turn in session_memory
            if turn["role"] != "music"
        )

    def batch_transform_queries(self, session_memories: List[list]) -> List[str]:
        return [self.transform_query(memory) for memory in session_memories]
