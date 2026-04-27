class DUMMY_LM:
    """No-op LM that returns empty strings — for retrieval-only experiments."""

    def response_generation(self, system_prompt, session_memory, recommend_item) -> str:
        return ""

    def batch_response_generation(self, system_prompts, session_memories, recommend_items) -> list[str]:
        return [""] * len(system_prompts)
