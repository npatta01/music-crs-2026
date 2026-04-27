from typing import List


class PassthroughQU:
    """QU module that returns the conversation text unchanged (current behavior)."""

    def transform_query(self, session_memory: list) -> str:
        return "\n".join(
            f"{turn['role']}: {turn['content']}" for turn in session_memory
        )

    def batch_transform_queries(self, session_memories: List[list]) -> List[str]:
        return [self.transform_query(memory) for memory in session_memories]
