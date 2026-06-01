def prediction_search_dir(split: str) -> str:
    """Directory where inference scripts write prediction JSON for a split."""
    return f"exp/inference/{split}"
