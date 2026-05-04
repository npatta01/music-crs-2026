"""Agents package entry point for constructing a configured TalkPlay music
recommendation agent.

Exposes `load_talkplay_agent` for convenient creation of a
`MusicRecommendationAgent`, including its `LLM`, tools, and data stores.
"""
from tpa.agents.agent_class import MusicRecommendationAgent
from tpa.agents.model import LLM, LITELLM_LLM
from tpa.environments import ToolExecutor, MusicCatalog, UserProfileDB

__all__ = ["MusicRecommendationAgent", "load_talkplay_agent"]

def load_talkplay_agent(
    cache_dir: str = "./cache",
    model_name: str = "Qwen/Qwen3-4B",
    device: str = "cuda",
    llm_backend: str = "local",
    llm_kwargs: dict | None = None,
    enabled_tools=None,
    embedding_enabled_retrievers=None,
    embedding_enabled_corpora=None,
    load_semantic_ids: bool = True,
    tool_calling_max_new_tokens: int = 8192 * 8,
    response_max_new_tokens: int = 2048,
    generate_response: bool = True,
):
    """Load and initialize a TalkPlay music recommendation agent.
    Args:
        cache_dir (str, optional): Directory path for caching data and models.
            Defaults to "./cache".
        model_name (str, optional): Name of the language model to use for the agent.
            Defaults to "Qwen/Qwen3-4B-AWQ".
    Returns:
        MusicRecommendationAgent: A fully configured music recommendation agent ready
            for use.
    """
    tool_executor = ToolExecutor(
        cache_dir=cache_dir,
        device=device,
        enabled_tools=enabled_tools,
        embedding_enabled_retrievers=embedding_enabled_retrievers,
        embedding_enabled_corpora=embedding_enabled_corpora,
    )
    llm_kwargs = dict(llm_kwargs or {})
    llm_kwargs.setdefault("max_new_tokens", tool_calling_max_new_tokens)
    if llm_backend == "local":
        llm = LLM(model_name=model_name, tools=tool_executor.tools, device=device, **llm_kwargs)
    elif llm_backend == "litellm":
        llm = LITELLM_LLM(model_name=model_name, tools=tool_executor.tools, device=device, **llm_kwargs)
    else:
        raise ValueError(f"Unsupported TalkPlay llm_backend: {llm_backend}")
    user_profiler = UserProfileDB(cache_dir=cache_dir)
    music_catalog = MusicCatalog(cache_dir=cache_dir, load_semantic_ids=load_semantic_ids)
    agent = MusicRecommendationAgent(
        tool_executor=tool_executor,
        llm=llm,
        user_db=user_profiler,
        item_db=music_catalog,
        cache_dir=cache_dir,
        tool_calling_max_new_tokens=tool_calling_max_new_tokens,
        response_max_new_tokens=response_max_new_tokens,
        generate_response=generate_response,
    )
    return agent
