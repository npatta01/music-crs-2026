try:
    import torch
except ModuleNotFoundError:  # pragma: no cover
    torch = None

def load_crs_baseline(
    lm_type="meta-llama/Llama-3.2-1B-Instruct",
    retrieval_type="bm25",
    qu_type="passthrough",
    pipeline_type="baseline",
    planner_backend=None,
    planner_model_name=None,
    item_db_name: str = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata",
    user_db_name: str = "talkpl-ai/TalkPlayData-Challenge-User-Metadata",
    track_split_types: list[str] = ["all_tracks"],
    user_split_types: list[str] = ["all_users"],
    corpus_types: list[str] = ["track_name", "artist_name", "album_name"],
    cache_dir="./cache",
    device="cuda",
    attn_implementation="eager",
    dtype=None,
    retrieval_topk: int = 20,
    retrieval_config: dict | None = None,
    qu_kwargs=None,
    lm_kwargs=None,
    toolcalling_config=None,
):
    if dtype is None:
        if torch is None:
            raise ModuleNotFoundError(
                "torch is required to use mcrs.load_crs_baseline (install torch or pass dtype explicitly)."
            )
        dtype = torch.bfloat16

    if pipeline_type == "agentic":
        if planner_backend not in {None, "litellm_chat_completions"}:
            raise ValueError(f"Unsupported planner_backend: {planner_backend}")
        if not planner_model_name:
            raise ValueError("planner_model_name is required for pipeline_type='agentic'")
        from .agentic import AgenticToolCallingCRS

        return AgenticToolCallingCRS(
            planner_model_name=planner_model_name,
            item_db_name=item_db_name,
            user_db_name=user_db_name,
            track_split_types=track_split_types,
            user_split_types=user_split_types,
            cache_dir=cache_dir,
            corpus_types=corpus_types,
            retrieval_topk=retrieval_topk,
            toolcalling_config=toolcalling_config,
        )

    from .crs_baseline import CRS_BASELINE

    return CRS_BASELINE(
        lm_type,
        retrieval_type,
        qu_type,
        item_db_name,
        user_db_name,
        track_split_types,
        user_split_types,
        corpus_types,
        cache_dir,
        device,
        attn_implementation,
        dtype,
        retrieval_topk,
        retrieval_config,
        qu_kwargs=qu_kwargs,
        lm_kwargs=lm_kwargs,
    )
