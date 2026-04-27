import os
from typing import Any

import pandas as pd


def chat_history_parser(conversations, music_crs, target_turn_number):
    """Parse conversation history up to a target turn.

    Music turns are converted from track IDs to the same metadata string used by
    the retriever-facing conversation formatter elsewhere in the pipeline.
    """
    df_conversation = pd.DataFrame(conversations)
    df_history = df_conversation[df_conversation["turn_number"] < target_turn_number]
    chat_history = []
    for turn_data in df_history.to_dict(orient="records"):
        current_content = turn_data["content"]
        if turn_data["role"] == "music":
            current_content = music_crs.item_db.id_to_metadata(turn_data["content"])
        chat_history.append(
            {
                "role": turn_data["role"],
                "content": current_content,
            }
        )

    df_current_turn = df_conversation[df_conversation["turn_number"] == target_turn_number]
    user_query = df_current_turn.iloc[0]["content"]
    return chat_history, user_query


def resolve_qu_kwargs_placeholders(qu_kwargs: dict[str, Any], tid: str, exp_dir: str | None = None) -> dict[str, Any]:
    """Replace known placeholder tokens in QU config values."""

    def _resolve(value):
        if isinstance(value, str):
            resolved = value.replace("<tid>", tid)
            if exp_dir is not None:
                if resolved.startswith("./exp/"):
                    return os.path.join(exp_dir, resolved[len("./exp/") :])
                if resolved.startswith("exp/"):
                    return os.path.join(exp_dir, resolved[len("exp/") :])
            return resolved
        if isinstance(value, list):
            return [_resolve(item) for item in value]
        if isinstance(value, dict):
            return {key: _resolve(item) for key, item in value.items()}
        return value

    return _resolve(qu_kwargs)
